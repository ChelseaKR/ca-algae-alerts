"""Iowa DNR beach monitoring results (AQuIA), built and switched off.

DECISIONS 0038. No reuse terms were found for AQuIA data, so under 0004 this
reader stays off (``LN_ENABLE_IOWA``) until the Iowa DNR agrees in writing.
Nothing here is fetched, merged, published or put in the snapshot by default.

Two CSV downloads on the DNR's own host (``programs.iowadnr.gov``, whose
robots.txt answers 404: no rules under 0011): the state park beaches and the
county and city beaches, read 5 seconds apart. Explicit columns only: the
site's id and name, the sample date, the microcystin result, the posted
status and the DNR's comments. The E. coli columns are never read here.

One sign serves two causes. The DNR posts "Swimming is Not Recommended" for
indicator bacteria and for cyanobacteria toxins alike, so the sign alone
never makes an algae advisory. The microcystin result decides the cause,
against the DNR's own advisory threshold, "8 µg/L total microcystins":

=====================================  ===============  ======================
posted status                          microcystin      treated as
=====================================  ===============  ======================
Swimming is Not Recommended            over 8           an advisory, the
                                                        DNR's words
Swimming is Not Recommended            8, under 8,      decides nothing (the
                                       blank            sign may be bacteria)
Watch / General Information            under 8          an explicit end
Watch / General Information            over 8           undetermined (0027)
Watch / General Information            8 or blank       decides nothing
Beach Closed, Special Status,          any              decides nothing
Insufficient Data, County-City Beach,
(blank)
(any other)                            any              undetermined (0027)
=====================================  ===============  ======================

The beach page words the signs "Swimming is Not Recommended" and "Watch /
General Information"; AQuIA's status reference (read 2026-11-06) words them
"Swimming Not Recommended" and "Ok for Swimming". Both spellings are read,
and the level is always the file's own text. A result of exactly 8 decides
nothing, because the DNR's word is "exceed" and the threshold's own edge is
asked of the DNR. None of these is mapped onto California's caution,
warning and danger scale. The files carry no coordinates, so none is given.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import re
import time
from collections import Counter
from collections.abc import Callable

import httpx

from caalgae import fetch
from caalgae.normalize import Normalized, Record, clean, parse_date, water_key
from caalgae.sources import IA_DNR_BEACHES

FIELDS = ("siteID", "name", "sampleDate", "microcystin", "status", "comments")
DOWNLOADS = ("State", "CountyCity")
POLITE_DELAY_SECONDS = 5.0
THRESHOLD_UG_L = 8.0  # "8 µg/L total microcystins", the DNR's beach page
EARLIEST_PLAUSIBLE = dt.date(2000, 1, 1)

NOT_RECOMMENDED = frozenset({"Swimming is Not Recommended", "Swimming Not Recommended"})
NO_ADVISORY_SIGN = frozenset({"Watch / General Information", "Ok for Swimming"})
UNREAD_STATUSES = frozenset(
    {"Beach Closed", "Special Status", "Insufficient Data", "County-City Beach"}
)

_LESS_THAN = re.compile(r"^<\s*(\d+(?:\.\d+)?)$")
_NUMBER = re.compile(r"^\d+(?:\.\d+)?$")


class IowaRefused(fetch.FetchError):
    """A download is not the shape read here. Refused whole."""


def download_url(which: str) -> str:
    return f"{IA_DNR_BEACHES.dataset_url}/{which}"


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "blank"


def microcystin_side(text: str) -> str:
    """Where a result sits against the threshold: ``over``, ``under``,
    ``at`` or ``unread``. A reporting limit (``<0.3``) is under only when
    the limit itself is under the threshold. Anything else is unread, never
    a zero."""
    text = clean(text)
    below = _LESS_THAN.match(text)
    if below:
        return "under" if float(below.group(1)) <= THRESHOLD_UG_L else "unread"
    if not _NUMBER.match(text):
        return "unread"
    value = float(text)
    if value > THRESHOLD_UG_L:
        return "over"
    if value < THRESHOLD_UG_L:
        return "under"
    return "at"


def tier_of(status: str, side: str) -> str:
    if status in NOT_RECOMMENDED:
        return "other_advisory" if side == "over" else "not_classified"
    if status in NO_ADVISORY_SIGN:
        if side == "under":
            return "no_advisory"
        return "unknown" if side == "over" else "not_classified"
    if status in UNREAD_STATUSES or not status:
        return "not_classified"
    return "unknown"


def _detail(result: str, comments: str) -> str:
    notes = [f"Microcystin {result} ug/L."] if result else []
    if comments:
        notes.append(comments if comments.endswith(".") else f"{comments}.")
    return " ".join(notes)


def _record(row: dict[str, str], run_date: dt.date) -> Record | str:
    site = clean(row.get("siteID"))
    name = clean(row.get("name"))
    if not site:
        return "missing site id"
    if not name:
        return "missing beach name"
    day = parse_date(row.get("sampleDate") or "")
    if day is None:
        return "missing sample date"
    if not EARLIEST_PLAUSIBLE <= day <= run_date:
        return "sample date outside 2000 to the run date"
    status = clean(row.get("status"))
    result = clean(row.get("microcystin"))
    tier = tier_of(status, microcystin_side(result))
    return Record(
        id=f"ia-{site}-{day.isoformat()}-{_slug(status)}",
        source=IA_DNR_BEACHES.id,
        state="IA",
        site_id=f"ia-{site}",
        water_key=water_key(name, "", "IA"),
        water_name=name,
        county_text="",
        landmark=name,
        lat=None,
        lon=None,
        date=day,
        level=status,
        tier=tier,
        explicit_no_advisory=tier == "no_advisory",
        end_date=None,
        detail=_detail(result, clean(row.get("comments"))),
        stamp=None,
        end_kind="below_threshold",
    )


def _rows(body: bytes) -> list[dict[str, str]]:
    try:
        text = body.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise IowaRefused(f"Iowa download is not UTF-8 text: {error}") from error
    if text.lstrip().startswith("<"):
        raise IowaRefused("Iowa download answered a web page, not a CSV file")
    reader = csv.DictReader(io.StringIO(text))
    header = reader.fieldnames or []
    missing = [f for f in FIELDS if f not in header]
    if missing:
        raise IowaRefused(f"Iowa download no longer has the columns {missing}")
    return [dict(row) for row in reader]


def normalize(pages: list[bytes], run_date: dt.date) -> Normalized:
    """Both downloads, in order. Out of season the DNR publishes no rows;
    an empty read is refused, never taken as "no advisory"."""
    if len(pages) != len(DOWNLOADS):
        raise IowaRefused(f"Iowa read is {len(DOWNLOADS)} downloads, not {len(pages)}")
    rows = [row for body in pages for row in _rows(body)]
    if not rows:
        raise IowaRefused(
            "Iowa downloads have no rows (out of season the DNR publishes none); "
            "an empty read is not a reading"
        )
    records: dict[str, Record] = {}
    quarantine: Counter[str] = Counter()
    for row in rows:
        result = _record(row, run_date)
        if isinstance(result, str):
            quarantine[result] += 1
        elif result.id in records:
            quarantine["the same status on the same beach and day twice"] += 1
        else:
            records[result.id] = result
    if not records:
        raise IowaRefused("Iowa downloads have no row this pipeline can place")
    return Normalized(
        records=list(records.values()), quarantine=quarantine, rows_read=len(rows)
    )


def fetch_pages(
    client: httpx.Client, sleep: Callable[[float], None] = time.sleep
) -> list[bytes]:
    """Robots first, then each download, 5 seconds apart."""
    fetch.robots_allows(client, download_url(DOWNLOADS[0]))
    pages: list[bytes] = []
    for index, which in enumerate(DOWNLOADS):
        if index:
            sleep(POLITE_DELAY_SECONDS)
        response = client.get(download_url(which))
        if response.status_code != 200:
            raise fetch.FetchError(
                f"Iowa {which} download returned HTTP {response.status_code}"
            )
        pages.append(response.content)
    return pages
