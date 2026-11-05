"""Turn the FHAB Responses CSV into normalized advisory records.

Every row of the Responses file is one advisory action on one bloom report
(one reported location). The state's own vocabulary is kept verbatim in
``level``; ``tier`` is our mapping of it, used only to sort and to choose
words. The mapping never invents an all-clear:

- ``None`` is the state's explicit "no recommended advisory based on the
  available information" (disclaimer PDF on the dataset page). It is the
  only level that can end an advisory, and it is flagged ``explicit_no_advisory``.
- ``NA - refer to Report Details`` and a blank level say nothing about the
  water. They are kept in history and never change a status.
- A blank ``Advisory_End_Date`` is "unknown", never "ended" (the disclaimer:
  "A blank field should be interpreted as 'unknown' and not 'none.'").

Rows that cannot be placed honestly are quarantined with a reason, counted
in the snapshot, and never silently dropped.
"""

from __future__ import annotations

import csv
import dataclasses
import datetime as dt
import io
import re
from collections import Counter
from collections.abc import Iterable

from caalgae.sources import CA_SWRCB_FHAB

REQUIRED_COLUMNS = (
    "Response_Action_ID",
    "Bloom_Report_ID",
    "Water_Body_Name",
    "County",
    "Landmark",
    "Bloom_Latitude",
    "Bloom_Longitude",
    "Advisory_ID",
    "Advisory_Recommended",
    "Advisory_Date",
    "Advisory_End_Date",
    "Advisory_Detail",
    "Response_DateTimeStamp",
)

# Our tier for each level the state uses. Order matters only for "highest".
TIER_RANK = {
    "danger": 4,
    "warning": 3,
    "caution": 2,
    "other_advisory": 1,
}
ADVISORY_TIERS = frozenset(TIER_RANK)
LEVEL_TO_TIER = {
    "danger": "danger",
    "warning": "warning",
    "caution": "caution",
    # Advisories outside the caution/warning/danger scale. They are
    # advisories (a value other than "none"), shown in the state's words.
    "algal mat alert sign": "other_advisory",
    "algal mat general awareness sign": "other_advisory",
    "general awareness": "other_advisory",
    "visual observation": "other_advisory",
    # The state's explicit record that no advisory is recommended.
    "none": "no_advisory",
    # Says nothing about the water.
    "na - refer to report details": "not_classified",
}

# The Water Boards' first records are from 2016. A date before this, or
# after the file's own date, is a typo in the source (the cases file has
# observation dates in 2555 and 2626).
EARLIEST_PLAUSIBLE = dt.date(2016, 1, 1)

_SPACE = re.compile(r"\s+")
_CA_BBOX = (32.0, 42.5, -125.0, -113.5)

_COUNTY_WORDS = """Alameda Alpine Amador Butte Calaveras Colusa Contra_Costa
Del_Norte El_Dorado Fresno Glenn Humboldt Imperial Inyo Kern Kings Lake
Lassen Los_Angeles Madera Marin Mariposa Mendocino Merced Modoc Mono
Monterey Napa Nevada Orange Placer Plumas Riverside Sacramento San_Benito
San_Bernardino San_Diego San_Francisco San_Joaquin San_Luis_Obispo
San_Mateo Santa_Barbara Santa_Clara Santa_Cruz Shasta Sierra Siskiyou
Solano Sonoma Stanislaus Sutter Tehama Trinity Tulare Tuolumne Ventura
Yolo Yuba"""
# The 58 California counties.
CA_COUNTIES = frozenset(word.replace("_", " ") for word in _COUNTY_WORDS.split())


class SourceShapeError(ValueError):
    """The file is not the shape this reader was written for."""


@dataclasses.dataclass(frozen=True)
class Record:
    """One advisory action, normalized."""

    id: str
    source: str
    state: str
    site_id: str
    water_key: str
    water_name: str
    county_text: str
    landmark: str
    lat: float | None
    lon: float | None
    date: dt.date
    level: str
    tier: str
    explicit_no_advisory: bool
    end_date: dt.date | None
    detail: str
    stamp: dt.datetime | None
    record_kind: str = "official_advisory"
    # What an explicit no-advisory record means at this source: the state's
    # "None" in California, a dissipated bloom in Missouri.
    end_kind: str = "no_advisory_record"

    @property
    def is_advisory(self) -> bool:
        return self.tier in ADVISORY_TIERS

    @property
    def is_unrecognized(self) -> bool:
        """A level the state wrote that this pipeline has no reading for
        (DECISIONS 0025). Unlike a blank, it may be a new advisory spelling,
        so it decides its spot as "undetermined": an older "None" never
        shows through it."""
        return self.tier == "unknown" and bool(self.level)

    def sort_key(self) -> tuple[dt.date, dt.datetime, int]:
        return (self.date, self.stamp or dt.datetime.min, _int(self.id))


@dataclasses.dataclass
class Normalized:
    records: list[Record]
    quarantine: Counter[str]
    rows_read: int


def _int(text: str) -> int:
    try:
        return int(text)
    except ValueError:
        return -1


def clean(text: str | None) -> str:
    return _SPACE.sub(" ", (text or "").strip())


def parse_date(text: str) -> dt.date | None:
    """``10/9/2026 12:00:00 AM`` (the file's format) or ISO. Blank is None."""
    text = clean(text)
    if not text:
        return None
    for fmt in ("%m/%d/%Y %I:%M:%S %p", "%m/%d/%Y", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def parse_stamp(text: str) -> dt.datetime | None:
    text = clean(text)
    for fmt in ("%m/%d/%Y %I:%M:%S %p", "%Y-%m-%dT%H:%M:%S"):
        try:
            return dt.datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def parse_coordinate(lat_text: str, lon_text: str) -> tuple[float | None, float | None]:
    """A coordinate pair inside a box around California, or neither."""
    try:
        lat, lon = float(lat_text), float(lon_text)
    except ValueError:
        return None, None
    lat_min, lat_max, lon_min, lon_max = _CA_BBOX
    if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
        return round(lat, 6), round(lon, 6)
    return None, None


_BBOX = {"CA": _CA_BBOX, "MO": (35.9, 40.7, -95.9, -89.0)}


def parse_coordinate_any(
    lat: object, lon: object, state: str
) -> tuple[float | None, float | None]:
    """A numeric coordinate pair inside the state's box, or neither."""
    if not isinstance(lat, int | float) or not isinstance(lon, int | float):
        return None, None
    lat_min, lat_max, lon_min, lon_max = _BBOX[state]
    if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
        return round(float(lat), 6), round(float(lon), 6)
    return None, None


def water_key(name: str, county_text: str, state: str = "CA") -> str:
    """Case-insensitive identity for a waterbody within a county text.

    The source has no waterbody id; the same lake is typed as "Lake Perris"
    and "Lake perris". Bloom reports never change name or county (measured
    2026-10-12: 0 of 2,937 reports did).
    """
    return f"{state.lower()}|{clean(county_text).casefold()}|{clean(name).casefold()}"


def counties_of(county_text: str) -> list[str]:
    """California counties named in the source text, in source order.

    "Calaveras; Tuolumne" names two. "Nevada State" and "Arizona State" name
    none: those are other states, kept in the text but given no county page.
    """
    out: list[str] = []
    for part in clean(county_text).split(";"):
        part = clean(part)
        if part in CA_COUNTIES and part not in out:
            out.append(part)
    return out


def tier_of(level: str) -> str:
    return LEVEL_TO_TIER.get(clean(level).casefold(), "unknown")


def _check_columns(fieldnames: Iterable[str] | None) -> None:
    present = set(fieldnames or ())
    missing = [c for c in REQUIRED_COLUMNS if c not in present]
    if missing:
        raise SourceShapeError(f"the Responses file is missing columns: {missing}")


def _row_to_record(row: dict[str, str], file_date: dt.date) -> Record | str:
    """A record, or the quarantine reason."""
    response_id = clean(row["Response_Action_ID"])
    site_id = clean(row["Bloom_Report_ID"])
    name = clean(row["Water_Body_Name"])
    if not response_id:
        return "missing response id"
    if not site_id:
        # 44 rows on 2026-10-09: advisory actions linked to no bloom report,
        # so no location and no water body name.
        return "not linked to a bloom report"
    if not name:
        return "missing water body name"
    advisory_date = parse_date(row["Advisory_Date"])
    if advisory_date is None:
        return "missing or unreadable advisory date"
    if not EARLIEST_PLAUSIBLE <= advisory_date <= file_date:
        return "advisory date outside 2016 to the file's date"
    end_date = parse_date(row["Advisory_End_Date"])
    if end_date is not None and end_date < EARLIEST_PLAUSIBLE:
        end_date = None
    level = clean(row["Advisory_Recommended"])
    tier = tier_of(level)
    lat, lon = parse_coordinate(row["Bloom_Latitude"], row["Bloom_Longitude"])
    county_text = clean(row["County"])
    return Record(
        id=response_id,
        source=CA_SWRCB_FHAB.id,
        state=CA_SWRCB_FHAB.state,
        site_id=site_id,
        water_key=water_key(name, county_text),
        water_name=name,
        county_text=county_text,
        landmark=clean(row["Landmark"]),
        lat=lat,
        lon=lon,
        date=advisory_date,
        level=level,
        tier=tier,
        explicit_no_advisory=tier == "no_advisory",
        end_date=end_date,
        detail=clean(row["Advisory_Detail"]),
        stamp=parse_stamp(row["Response_DateTimeStamp"]),
    )


def normalize_csv(body: bytes, file_date: dt.date) -> Normalized:
    """Parse and normalize the whole file. Duplicated ids are a shape error."""
    text = body.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text, newline=""))
    _check_columns(reader.fieldnames)
    records: list[Record] = []
    quarantine: Counter[str] = Counter()
    seen: set[str] = set()
    rows = 0
    for row in reader:
        rows += 1
        result = _row_to_record(row, file_date)
        if isinstance(result, str):
            quarantine[result] += 1
            continue
        if result.id in seen:
            raise SourceShapeError(f"Response_Action_ID {result.id} appears twice")
        seen.add(result.id)
        records.append(result)
    if rows == 0:
        raise SourceShapeError("the Responses file has a header and no rows")
    return Normalized(records=records, quarantine=quarantine, rows_read=rows)
