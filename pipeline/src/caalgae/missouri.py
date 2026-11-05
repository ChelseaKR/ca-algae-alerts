"""Missouri DNR harmful algal bloom cases (second state, 2026-10-12).

One ArcGIS MapServer layer, one request per run, explicit non-personal
fields only: the case id, the water body's name and type, the observation
date, the bloom status code, the case status and the dissipation date, plus
the point. Fields naming agencies, owners or reporters are never requested
(docs/DECISIONS.md 0010). The one free-text field read is ``PubInfo``, the
department's own public note on a case, shown verbatim, quoted and credited
on the water's page (0023). It decides nothing.

Each row is one case, carrying its current status rather than a history of
updates. The department publishes no definitions of its status codes; the
plain-English labels below are this project's reading of them, shown beside
the code, and an owner decision to confirm (NOTES.md in the hand-off):

=========  ==================  ==================================
code       label shown         treated as
=========  ==================  ==================================
advise     Advisory            an advisory
notice     Notice              an advisory (conservative)
dissap     Dissipated          an explicit end, only with a date
notthr     Below threshold     decides nothing
notver     Not verified        decides nothing
report     Report              decides nothing
(blank)    blank               decides nothing
=========  ==================  ==================================

The end of an advisory is the department's dissipation date (``DissDat``),
an explicit field. A case marked closed without one is not an end: it stays
"last posted <date>, no all-clear recorded". A case with no observation
date cannot be placed in time and is quarantined.

Fail closed (docs/DECISIONS.md 0019). The department says it plans to retire
this layer. An answer that shows the layer is gone or no longer has the
shape read here (HTTP 404 or 410, an ArcGIS error, missing fields, too few
rows, no usable case) raises ``LayerUnavailable``, and the run then leaves
Missouri off the site rather than showing its last records as current.
"""

from __future__ import annotations

import datetime as dt
import json
from collections import Counter
from typing import Any, TypedDict
from zoneinfo import ZoneInfo

import httpx

from caalgae import fetch
from caalgae.normalize import Normalized, Record, clean, parse_coordinate_any, water_key
from caalgae.sources import MO_DNR_HAB

FIELDS = (
    "objectid",
    "WBName",
    "HABODat",
    "BloomStat",
    "CaseStatus",
    "DissDat",
    "WBType",
)
# Requested, but a layer without it still reads (0023): losing a note is not
# the layer changing shape.
OPTIONAL_FIELDS = ("PubInfo",)
QUERY_URL = (
    MO_DNR_HAB.dataset_url
    + "/query?where=1%3D1&outFields="
    + ",".join(FIELDS + OPTIONAL_FIELDS)
    + "&returnGeometry=true&outSR=4326&orderByFields=objectid&f=json"
)
CENTRAL = ZoneInfo("America/Chicago")
LABELS = {
    "advise": "Advisory",
    "notice": "Notice",
    "dissap": "Dissipated",
    "notthr": "Below threshold",
    "notver": "Not verified",
    "report": "Report",
}
ADVISORY_CODES = frozenset({"advise", "notice"})
MIN_ROWS = 50  # 278 on 2026-10-12; far fewer is a truncated answer
# HTTP answers that mean the layer itself is gone, not a passing outage.
GONE_STATUSES = frozenset({404, 410})
CLOSED_DETAIL = "Case closed."
# The department's placeholder note; it says nothing about the case, so the
# page does not quote it (0023). Compared casefolded, without a final period.
NO_NOTE = "no additional information"


class LayerUnavailable(fetch.FetchError):
    """The layer is gone or its answer no longer has the expected shape.
    Unlike a passing network failure, this hides Missouri at once."""


def _date(ms: object) -> dt.date | None:
    if not isinstance(ms, int | float):
        return None
    return dt.datetime.fromtimestamp(ms / 1000, tz=dt.UTC).astimezone(CENTRAL).date()


def level_label(code: str) -> str:
    return f"{LABELS[code]} ({code})" if code in LABELS else code


def _record(feature: dict[str, Any], file_date: dt.date) -> Record | str:
    a = feature.get("attributes", {})
    oid = a.get("objectid")
    name = clean(a.get("WBName"))
    if oid is None:
        return "missing case id"
    if not name:
        return "missing water body name"
    observed = _date(a.get("HABODat"))
    if observed is None:
        return "missing observation date"
    if not dt.date(2016, 1, 1) <= observed <= file_date:
        return "observation date outside 2016 to the run date"
    code = clean(a.get("BloomStat")).lower()
    dissipated = _date(a.get("DissDat"))
    case = clean(a.get("CaseStatus"))
    geometry = feature.get("geometry") or {}
    lat, lon = parse_coordinate_any(geometry.get("y"), geometry.get("x"), state="MO")
    detail = f"Case {case.lower()}." if case else ""
    note = clean(a.get("PubInfo"))
    if code in ADVISORY_CODES:
        tier, date, end = "other_advisory", observed, dissipated
    elif code == "dissap" and dissipated is not None:
        tier, date, end = "no_advisory", dissipated, None
    else:
        tier, date, end = ("not_classified" if code else "unknown"), observed, None
        if code == "dissap":
            detail = (detail + " Marked dissipated; no date recorded.").strip()
    return Record(
        id=f"mo-{oid}",
        source=MO_DNR_HAB.id,
        state="MO",
        site_id=f"mo-{oid}",
        water_key=water_key(name, "", "MO"),
        water_name=name,
        county_text="",
        landmark=name,
        lat=lat,
        lon=lon,
        date=date,
        level=level_label(code) if code else "",
        tier=tier,
        explicit_no_advisory=tier == "no_advisory",
        end_date=end,
        detail=detail,
        stamp=None,
        end_kind="dissipated",
        public_info=note,
    )


def normalize(body: bytes, run_date: dt.date) -> Normalized:
    try:
        data = json.loads(body)
    except ValueError as error:
        raise LayerUnavailable(f"Missouri layer answer is not JSON: {error}") from error
    if not isinstance(data, dict):
        raise LayerUnavailable("Missouri layer answer is not a JSON object")
    if "error" in data:
        raise LayerUnavailable(f"Missouri layer answered an error: {data['error']}")
    if data.get("exceededTransferLimit"):
        raise LayerUnavailable("Missouri layer has more rows than one answer carries")
    features = data.get("features")
    if not isinstance(features, list) or len(features) < MIN_ROWS:
        count = len(features) if isinstance(features, list) else 0
        raise LayerUnavailable(f"Missouri layer returned {count} rows")
    fields = data.get("fields")
    names = (
        {f.get("name") for f in fields if isinstance(f, dict)}
        if isinstance(fields, list)
        else set()
    )
    missing = [f for f in FIELDS if f not in names]
    if missing:
        raise LayerUnavailable(f"Missouri layer no longer has the fields {missing}")
    records: list[Record] = []
    quarantine: Counter[str] = Counter()
    for feature in features:
        result = _record(feature, run_date)
        if isinstance(result, str):
            quarantine[result] += 1
        else:
            records.append(result)
    if not records:
        raise LayerUnavailable("Missouri layer has no case this pipeline can place")
    return Normalized(records=records, quarantine=quarantine, rows_read=len(features))


def fetch_cases(client: httpx.Client) -> bytes:
    fetch.robots_allows(client, QUERY_URL)
    response = client.get(QUERY_URL)
    if response.status_code in GONE_STATUSES:
        raise LayerUnavailable(f"Missouri layer returned HTTP {response.status_code}")
    if response.status_code != 200:
        raise fetch.FetchError(f"Missouri layer returned HTTP {response.status_code}")
    return response.content


def _headline_cases(water: dict[str, Any]) -> list[dict[str, Any]]:
    """The water's cases its headline comes from: an advisory, at the
    headline's level, observed on the headline's date, with no end."""
    status = water["status"]
    if water["state"] != "MO" or status["kind"] != "advisory":
        return []
    return [
        r
        for r in water["records"]
        if r["source"] == MO_DNR_HAB.id
        and r["tier"] == "other_advisory"
        and r["level"] == status["level"]
        and r["date"] == status["posted"]
        and r["end_date"] is None
        and r["removed_from_source"] is None
    ]


def closed_note(water: dict[str, Any]) -> str | None:
    """For the status box: the department closed the headline's case without
    recording a dissipation date (batch LN-C). It ends nothing (0010)."""
    cases = _headline_cases(water)
    closed = sum(r["detail"].startswith(CLOSED_DETAIL) for r in cases)
    if not closed:
        return None
    if len(cases) == 1:
        return "The department marked this case closed without a dissipation date."
    if closed == len(cases):
        return (
            f"The department marked these {closed} cases closed without a "
            "dissipation date."
        )
    return (
        f"The department marked {closed} of these {len(cases)} cases closed "
        "without a dissipation date."
    )


class DepartmentNote(TypedDict):
    date: str
    level: str
    text: str


def department_notes(water: dict[str, Any]) -> list[DepartmentNote]:
    """Each case's PubInfo, verbatim, newest case first (0023). Cases with
    no note, or only the department's placeholder, are left out."""
    if water["state"] != "MO":
        return []
    return [
        {"date": r["date"], "level": r["level"], "text": r["public_info"]}
        for r in water["records"]
        if r.get("public_info")
        and r["public_info"].rstrip(".").casefold() != NO_NOTE
        and r["removed_from_source"] is None
    ]
