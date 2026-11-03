"""New York's yearly harmful algal bloom summary: history only (DECISIONS 0016).

What this data is, and what it never is:

- **History.** New York State DEC's "Harmful Algal Blooms by Waterbody
  Summary: Beginning 2019" (data.ny.gov ``95my-wijm``) has one row per water
  per year in which DEC confirmed a harmful algal bloom there, with the first
  and last dates the bloom was reported that year and how many reports came in.
- **Never an advisory, never a current status, never an end.** A last report
  date is the last report that year, not the end of a bloom. A year with no
  row is not a finding that the water had no bloom. Nothing here alerts, and
  nothing here reaches the snapshot, ``status.py`` or the iPhone app.

Requests, all to ``data.ny.gov`` after its robots.txt is read and only when
someone runs ``python -m caalgae.newyork`` (about once a year, when DEC posts
a season; the daily publish never fetches New York):

1. robots.txt (``Crawl-delay: 1`` on 2026-11-02; we wait at least 2 s).
2. The dataset's metadata (``/api/views/95my-wijm.json``) for its update time.
3. The rows, explicit non-personal columns only, in one request
   (``/resource/95my-wijm.json``).

The rows are written byte for byte to ``pipeline/data/ny/``, with a sidecar
recording where and when they were read and their SHA-256. ``PINNED_SHA256``
pins that hash in code, so a changed file reaches the site only through a
reviewed commit that updates the pin.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import hashlib
import json
import math
import re
import sys
import time
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from typing import Any

import httpx

from caalgae import fetch
from caalgae.snapshot import slugify

DATASET_ID = "95my-wijm"
DATASET_NAME = "Harmful Algal Blooms by Waterbody Summary: Beginning 2019"
DATASET_PAGE_URL = (
    "https://data.ny.gov/Energy-Environment/"
    "Harmful-Algal-Blooms-by-Waterbody-Summary-Beginnin/95my-wijm"
)
META_URL = f"https://data.ny.gov/api/views/{DATASET_ID}.json"
ROWS_URL = f"https://data.ny.gov/resource/{DATASET_ID}.json"
FIELDS = (
    "waterbody_name",
    "county",
    "year",
    "bloom_type",
    "date_first_report",
    "date_last_report",
    "number_of_reports",
    "latitude",
    "longitude",
)
QUERY = {
    "$select": ",".join(FIELDS),
    "$order": "year,county,waterbody_name",
    "$limit": "50000",
}
# robots.txt asked for 1 s on 2026-11-02; we wait at least this long.
MIN_SPACING_SECONDS = 2.0
MAX_BODY_BYTES = 16 * 1024 * 1024

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "ny"
ROWS_FILE = f"{DATASET_ID}.rows.json"
META_FILE = f"{DATASET_ID}.meta.json"
# SHA-256 of pipeline/data/ny/95my-wijm.rows.json, read 2026-11-02 (DEC's rows
# last updated 2026-01-14, the 2025 season). Change it only in the commit
# that refreshes the file, after reviewing the diff (docs/DECISIONS.md 0016).
PINNED_SHA256 = "a9b3a0e8709adf3c19e4e39c49a03c8a2cb9d6bc97b6ad6c6f65470a389a3623"

# Thin-page rule (owner, 2026-11-02): a New York page may be indexed only when
# DEC's summary has at least MIN_YEARS bloom years or MIN_REPORTS reports for
# that water. Every other page is built with noindex and left out of the sitemap.
MIN_YEARS = 2
MIN_REPORTS = 5
# Rows with the same name whose points lie within this distance are one water.
# DEC repeats a water's point exactly from year to year (Seneca Lake's seven
# rows share one point across four county spellings); different waters that
# share a name are miles apart (the two Long Ponds in Suffolk County, 2.9 mi).
SAME_WATER_MILES = 1.0
_EARTH_RADIUS_MILES = 3958.8

# DEC's bloom type, as the dataset's column description defines its codes.
# Every row on 2026-11-02 reads "confirmed". Any other value is held back and
# counted, so a "suspicious" row is never shown as a confirmed bloom.
BLOOM_TYPE_LABEL = {"confirmed": "Confirmed bloom"}

AGENCY = "New York State Department of Environmental Conservation (DEC)"
NOTIFICATIONS_URL = (
    "https://dec.ny.gov/environmental-protection/water/water-quality/"
    "harmful-algal-blooms/notifications"
)
PROGRAM_URL = "https://dec.ny.gov/environmental-protection/water/water-quality/harmful-algal-blooms"
TERMS_URL = "https://data.ny.gov/dataset/OPEN-NY-Terms-Of-Use/77gx-ii52"
TERMS_READ_ON = "2026-11-02"
ATTRIBUTION = (
    "New York bloom history: New York State Department of Environmental "
    f'Conservation, "{DATASET_NAME}", via data.ny.gov under the OPEN-NY Terms '
    "of Use. DEC does not endorse this site."
)
# OPEN-NY Terms of Use (LAST MODIFIED: March 8, 2013), verbatim, read
# 2026-11-02 from the PDF at TERMS_URL. Quoted on the New York pages.
NO_VOUCH_CLAUSE = (
    "The State also does not vouch for the continued accuracy or currency of "
    "Content after it has been downloaded from OPEN-NY, nor the quality or "
    "accuracy of any analyses or re-uses of that Content."
)
REVOCATION_CLAUSE = (
    "The State reserves the right to modify, discontinue or remove any Content "
    "on OPEN-NY or terminate your access to OPEN-NY for any reason, without "
    "notice, at any time, and without liability to you. Upon termination, all "
    "licenses and other rights granted to you in these Terms of Use will "
    "immediately cease."
)


class NYDataError(RuntimeError):
    """The cached New York file is missing, altered or malformed."""


@dataclasses.dataclass(frozen=True)
class BloomYear:
    year: int
    first_report: dt.date
    last_report: dt.date
    reports: int
    label: str


@dataclasses.dataclass(frozen=True)
class Water:
    id: str
    slug: str
    name: str
    counties: tuple[str, ...]
    lat: float
    lon: float
    years: tuple[BloomYear, ...]  # newest first

    @property
    def year_count(self) -> int:
        return len(self.years)

    @property
    def report_count(self) -> int:
        return sum(y.reports for y in self.years)

    @property
    def first_year(self) -> int:
        return self.years[-1].year

    @property
    def last_year(self) -> int:
        return self.years[0].year

    @property
    def newest_report(self) -> dt.date:
        return max(y.last_report for y in self.years)

    @property
    def place(self) -> str:
        counties = list(self.counties)
        if len(counties) == 1:
            return f"{counties[0]} County"
        return f"{', '.join(counties[:-1])} and {counties[-1]} counties"


@dataclasses.dataclass(frozen=True)
class History:
    waters: tuple[Water, ...]
    rows_read: int
    unnamed_rows: int
    quarantine: dict[str, int]
    rows_updated_at: str
    fetched_at: str
    sha256: str

    @property
    def first_year(self) -> int:
        return min(w.first_year for w in self.waters)

    @property
    def last_year(self) -> int:
        return max(w.last_year for w in self.waters)


# -- reading the rows ----------------------------------------------------------

_DATE = re.compile(r"^(\d{4}-\d{2}-\d{2})(?:T00:00:00(?:\.000)?)?$")


def _date(value: Any) -> dt.date:
    match = _DATE.match(str(value or ""))
    if not match:
        raise ValueError("missing or malformed date")
    return dt.date.fromisoformat(match.group(1))


def _number(value: Any, reason: str) -> float:
    try:
        number = float(str(value))
    except ValueError:
        raise ValueError(reason) from None
    if not math.isfinite(number):
        raise ValueError(reason)
    return number


def _whole(value: Any) -> int:
    number = _number(value, "report count is not a positive whole number")
    if not number.is_integer() or number < 1:
        raise ValueError("report count is not a positive whole number")
    return int(number)


def _row(raw: dict[str, Any]) -> dict[str, Any]:
    """One checked row, or ValueError with the reason it is held back."""
    label = BLOOM_TYPE_LABEL.get(str(raw.get("bloom_type", "")).strip().casefold())
    if label is None:
        raise ValueError("bloom type other than confirmed")
    year = int(_number(raw.get("year"), "missing or malformed year"))
    first, last = (
        _date(raw.get("date_first_report")),
        _date(raw.get("date_last_report")),
    )
    if first.year != year or last.year != year:
        raise ValueError("report date outside the row's year")
    if last < first:
        raise ValueError("last report before first report")
    lat = _number(raw.get("latitude"), "point outside New York")
    lon = _number(raw.get("longitude"), "point outside New York")
    if not (40.0 <= lat <= 45.5 and -80.0 <= lon <= -71.5):
        raise ValueError("point outside New York")
    counties = tuple(
        sorted({c.strip() for c in str(raw.get("county", "")).split(",") if c.strip()})
    )
    if not counties:
        raise ValueError("no county")
    name = " ".join(str(raw.get("waterbody_name", "")).split())
    if not name:
        raise ValueError("no water name")
    return {
        "name": name,
        "counties": counties,
        "year": BloomYear(
            year, first, last, _whole(raw.get("number_of_reports")), label
        ),
        "lat": lat,
        "lon": lon,
    }


def is_unnamed(name: str) -> bool:
    """DEC's "Unnamed Water" and "Unnamed Tributary ..." rows name no single
    water, so they get no page."""
    return name.casefold().startswith("unnamed")


def miles_between(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * _EARTH_RADIUS_MILES * math.asin(math.sqrt(h))


def _clusters(rows: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Rows of one name, grouped so that rows within SAME_WATER_MILES of each
    other (directly or through a chain) are one water."""
    groups: list[list[dict[str, Any]]] = []
    for row in rows:
        point = (row["lat"], row["lon"])
        near = [
            g for g in groups
            if any(miles_between(point, (r["lat"], r["lon"])) <= SAME_WATER_MILES for r in g)
        ]  # fmt: skip
        merged = [row]
        for g in near:
            merged.extend(g)
            groups.remove(g)
        groups.append(merged)
    return groups


def _water(rows: list[dict[str, Any]], quarantine: Counter[str]) -> Water:
    rows = sorted(rows, key=lambda r: r["year"].year, reverse=True)
    years: list[BloomYear] = []
    for row in rows:
        if any(y.year == row["year"].year for y in years):
            quarantine["a second row for one water in one year"] += 1
            continue
        years.append(row["year"])
    newest = rows[0]
    counties = tuple(sorted({c for r in rows for c in r["counties"]}))
    return Water(
        id="",
        slug="",
        name=newest["name"],
        counties=counties,
        lat=newest["lat"],
        lon=newest["lon"],
        years=tuple(years),
    )


def _with_ids(waters: list[Water]) -> list[Water]:
    """``ny-<name>`` (``ny-seneca-lake``), as Missouri's ``mo-<name>``. A name
    that two waters share adds the county (``ny-orange-greenwood-lake``), and
    two waters of one name in one county (the Long Ponds in Suffolk County)
    add their point as well. The refresh prints any id that changes."""
    slugs = [slugify(w.name) for w in waters]
    shared = Counter(slugs)
    slugs = [
        f"{slugify(w.counties[0])}-{s}" if shared[s] > 1 else s
        for w, s in zip(waters, slugs, strict=True)
    ]
    shared = Counter(slugs)
    slugs = [
        f"{s}-{slugify(f'{w.lat:.3f} {abs(w.lon):.3f}')}" if shared[s] > 1 else s
        for w, s in zip(waters, slugs, strict=True)
    ]
    return [
        dataclasses.replace(w, id=f"ny-{s}", slug=s)
        for w, s in zip(waters, slugs, strict=True)
    ]


def parse(body: bytes) -> tuple[list[Water], int, int, dict[str, int]]:
    """The rows as waters, with the count read, unnamed and held back."""
    try:
        raw_rows = json.loads(body)
    except ValueError as error:
        raise NYDataError(f"the New York rows are not JSON: {error}") from error
    if not isinstance(raw_rows, list) or not raw_rows:
        raise NYDataError("the New York rows are not a non-empty list")
    quarantine: Counter[str] = Counter()
    by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    unnamed = 0
    for raw in raw_rows:
        try:
            row = _row(raw if isinstance(raw, dict) else {"bloom_type": None})
        except ValueError as error:
            quarantine[str(error)] += 1
            continue
        if is_unnamed(row["name"]):
            unnamed += 1
            continue
        by_name[" ".join(re.findall(r"[a-z0-9]+", row["name"].casefold()))].append(row)
    waters = [
        _water(group, quarantine)
        for name in sorted(by_name)
        for group in _clusters(by_name[name])
    ]
    waters = sorted(_with_ids(waters), key=lambda w: w.id)
    if len({w.id for w in waters}) != len(waters):
        raise NYDataError("two New York waters ended up with one id")
    return waters, len(raw_rows), unnamed, dict(sorted(quarantine.items()))


def sha256(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def load(directory: Path = DATA_DIR, *, pinned: str | None = PINNED_SHA256) -> History:
    """Read the cached rows. The file must match its sidecar's hash and, for
    the committed cache, the hash pinned in code."""
    try:
        body = (directory / ROWS_FILE).read_bytes()
        meta = json.loads((directory / META_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise NYDataError(f"the New York cache cannot be read: {error}") from error
    digest = sha256(body)
    if digest != meta.get("sha256"):
        raise NYDataError(f"{ROWS_FILE} does not match the hash in {META_FILE}")
    if pinned is not None and digest != pinned:
        raise NYDataError(
            f"{ROWS_FILE} is not the pinned file (sha256 {digest}); review the "
            "change and update newyork.PINNED_SHA256 in the same commit"
        )
    waters, rows_read, unnamed, quarantine = parse(body)
    return History(
        waters=tuple(waters),
        rows_read=rows_read,
        unnamed_rows=unnamed,
        quarantine=quarantine,
        rows_updated_at=str(meta["rows_updated_at"]),
        fetched_at=str(meta["fetched_at"]),
        sha256=digest,
    )


# -- which pages search engines may list -----------------------------------------


def meets_threshold(water: Water) -> bool:
    return water.year_count >= MIN_YEARS or water.report_count >= MIN_REPORTS


def rank_key(water: Water) -> tuple[int, int, str]:
    """Deepest history first: most reports, then most years, then by name."""
    return (-water.report_count, -water.year_count, water.id)


def indexed_ids(waters: Iterable[Water], limit: int | None) -> set[str]:
    """The waters whose pages may be indexed: those over the threshold, and of
    those only the first ``limit`` by ``rank_key`` while the rollout is staged."""
    eligible = sorted((w for w in waters if meets_threshold(w)), key=rank_key)
    if limit is not None:
        eligible = eligible[:limit]
    return {w.id for w in eligible}


# -- the yearly refresh -----------------------------------------------------------


def _get(
    client: httpx.Client, url: str, params: dict[str, str] | None
) -> httpx.Response:
    fetch.guard_url(url)
    try:
        response = client.get(url, params=params)
    except httpx.HTTPError as error:
        raise fetch.FetchError(f"GET {url} failed: {error}") from error
    if response.status_code != 200:
        raise fetch.FetchError(f"GET {url} returned HTTP {response.status_code}")
    if len(response.content) > MAX_BODY_BYTES:
        raise fetch.FetchError(f"GET {url} answered {len(response.content)} bytes")
    return response


def refresh(
    client: httpx.Client,
    directory: Path,
    now: dt.datetime,
    *,
    sleep: Callable[[float], None] = time.sleep,
) -> str:
    """Read robots.txt, the metadata and the rows; write the cache. Returns
    the new rows' SHA-256, which a person then pins in code."""
    parser = fetch.robots_allows(client, META_URL)
    delay = MIN_SPACING_SECONDS
    if parser is not None:
        if not parser.can_fetch(fetch.USER_AGENT, ROWS_URL):
            raise fetch.RobotsOffLimits(
                f"data.ny.gov's robots.txt disallows {ROWS_URL}"
            )
        asked = parser.crawl_delay(fetch.USER_AGENT)
        delay = max(delay, float(asked or 0))
    sleep(delay)
    meta = _get(client, META_URL, None).json()
    sleep(delay)
    rows = _get(client, ROWS_URL, QUERY)
    body = rows.content
    parse(body)  # refuse a file that would not load
    digest = sha256(body)
    updated = dt.datetime.fromtimestamp(int(meta["rowsUpdatedAt"]), dt.UTC)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / ROWS_FILE).write_bytes(body)
    sidecar = {
        "dataset": DATASET_ID,
        "dataset_name": str(meta.get("name", DATASET_NAME)),
        "url": str(rows.url),
        "fields": list(FIELDS),
        "rows_updated_at": updated.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "fetched_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "terms_url": TERMS_URL,
        "sha256": digest,
    }
    (directory / META_FILE).write_text(
        json.dumps(sidecar, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return digest


def page_changes(
    before: Iterable[Water], after: Iterable[Water]
) -> tuple[list[str], list[str]]:
    """Ids a refresh removes and adds. A removed id is a published page that
    would disappear, so the refresh prints each one for review."""
    old, new = {w.id for w in before}, {w.id for w in after}
    return sorted(old - new), sorted(new - old)


def main(argv: Sequence[str] | None = None) -> int:  # pragma: no cover - live only
    p = argparse.ArgumentParser(
        prog="python -m caalgae.newyork",
        description="Refresh the cached New York yearly bloom summary (about once a year).",
    )
    p.add_argument("--out", type=Path, default=DATA_DIR)
    args = p.parse_args(argv)
    try:
        before: tuple[Water, ...] = load(args.out, pinned=None).waters
    except NYDataError:
        before = ()
    try:
        with fetch.make_client() as client:
            digest = refresh(client, args.out, dt.datetime.now(dt.UTC))
    except (
        fetch.FetchError,
        NYDataError,
        httpx.HTTPError,
        KeyError,
        ValueError,
    ) as error:
        print(
            f"caalgae.newyork: refresh failed, cache unchanged: {error}",
            file=sys.stderr,
        )
        return 2
    history = load(args.out, pinned=None)
    print(
        f"caalgae.newyork: {history.rows_read} rows, {len(history.waters)} named waters, "
        f"{history.unnamed_rows} unnamed rows, held back {history.quarantine}; "
        f"DEC updated the rows {history.rows_updated_at}"
    )
    removed, added = page_changes(before, history.waters)
    print(f"caalgae.newyork: {len(added)} new water ids, {len(removed)} removed")
    for water_id in removed:
        print(f"caalgae.newyork: REMOVED {water_id} (its page would disappear)")
    print(f"caalgae.newyork: sha256 {digest}")
    if digest != PINNED_SHA256:
        print("caalgae.newyork: the file changed; review it and update PINNED_SHA256")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
