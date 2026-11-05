"""Missouri DNR harmful algal bloom cases (second state, 2026-10-12).

One ArcGIS MapServer layer, one request per run, explicit non-personal
fields only: the case id, the water body's name and type, the observation
date, the bloom status code, the case status and the dissipation date, plus
the point. Fields naming agencies, owners, reporters or free text are never
requested (docs/DECISIONS.md 0010).

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

Fail closed (docs/DECISIONS.md 0019, 0024). The department says it plans to
retire this layer. An answer that shows the layer is gone or no longer has
the shape read here (HTTP 404 or 410, an ArcGIS error, missing fields, too
few rows, no usable case), a layer that has stopped moving in season
(``check_fresh``), or a public viewer that no longer reads it
(``check_viewer``) raises ``LayerUnavailable``. The run then shows Missouri's
pages in their dated "data unavailable" mode rather than showing its last
records as current.
"""

from __future__ import annotations

import datetime as dt
import json
from collections import Counter
from typing import Any
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
QUERY_URL = (
    MO_DNR_HAB.dataset_url
    + "/query?where=1%3D1&outFields="
    + ",".join(FIELDS)
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


# Frozen layer (DECISIONS 0024): in season, a layer whose newest record is
# older than this is treated as unavailable. The measured worst in-season gap
# between reports was 22 days (21 in 2024, 22 in 2025, 18 in 2026).
FROZEN_AFTER_DAYS = 30
SEASON_START = (5, 15)
SEASON_END = (10, 15)
# The department's public HAB viewer ("HAB Public Viewer PROD", an ArcGIS
# Experience on www.arcgis.com, owner modnr_admin). Its data sources name the
# layer this pipeline reads; when the department moves the viewer to a new
# layer, this one stops being named there first (DECISIONS 0024).
VIEWER_ITEM_ID = "96d87e1fda0e445b90c23ce52d67a2d9"
VIEWER_DATA_URL = (
    f"https://www.arcgis.com/sharing/rest/content/items/{VIEWER_ITEM_ID}/data?f=json"
)


class LayerUnavailable(fetch.FetchError):
    """The layer is gone, changed, frozen or superseded. Unlike a passing
    network failure, this puts Missouri in its "data unavailable" mode at
    once (DECISIONS 0024)."""

    def __init__(self, message: str, kind: str = "changed") -> None:
        super().__init__(message)
        self.kind = kind


def in_season(day: dt.date) -> bool:
    return SEASON_START <= (day.month, day.day) <= SEASON_END


def check_fresh(records: list[Record], run_date: dt.date) -> None:
    """Refuse a layer that still answers but has stopped moving: in season,
    no record dated within ``FROZEN_AFTER_DAYS`` of the run. A record's date
    is its observation date, or its dissipation date for a dissipated case,
    so either kind of update counts. Out of season nothing is checked."""
    if not in_season(run_date) or not records:
        return
    newest = max(r.date for r in records)
    age = (run_date - newest).days
    if age > FROZEN_AFTER_DAYS:
        raise LayerUnavailable(
            f"Missouri layer looks frozen: in season, its newest record is from "
            f"{newest.isoformat()}, {age} days before the run",
            kind="frozen",
        )


def _urls(node: object) -> list[str]:
    if isinstance(node, dict):
        found = [v for k, v in node.items() if k == "url" and isinstance(v, str)]
        for value in node.values():
            found += _urls(value)
        return found
    if isinstance(node, list):
        return [u for item in node for u in _urls(item)]
    return []


def viewer_references_layer(body: bytes) -> bool:
    """Whether the viewer's data sources still name this pipeline's layer.
    An answer that is not a viewer definition with data sources is a
    passing failure (``fetch.FetchError``), never "superseded": only a
    readable list of data sources without the layer proves the move."""
    try:
        data = json.loads(body)
    except ValueError as error:
        raise fetch.FetchError(
            f"Missouri viewer answer is not JSON: {error}"
        ) from error
    sources = data.get("dataSources") if isinstance(data, dict) else None
    if not isinstance(sources, dict) or not sources:
        raise fetch.FetchError("Missouri viewer answer has no data sources")
    urls = {u.rstrip("/") for u in _urls(sources)}
    if not any("/rest/services/" in u for u in urls):
        raise fetch.FetchError("Missouri viewer data sources name no map service")
    return MO_DNR_HAB.dataset_url in urls


def fetch_viewer(client: httpx.Client) -> bytes:
    fetch.robots_allows(client, VIEWER_DATA_URL)
    response = client.get(VIEWER_DATA_URL)
    if response.status_code != 200:
        raise fetch.FetchError(f"Missouri viewer returned HTTP {response.status_code}")
    return response.content


def check_viewer(body: bytes) -> None:
    if not viewer_references_layer(body):
        raise LayerUnavailable(
            "Missouri's public HAB viewer no longer reads this layer; the "
            "department has moved its map to another source",
            kind="superseded",
        )


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
        raise LayerUnavailable(
            f"Missouri layer returned HTTP {response.status_code}", kind="gone"
        )
    if response.status_code != 200:
        raise fetch.FetchError(f"Missouri layer returned HTTP {response.status_code}")
    return response.content
