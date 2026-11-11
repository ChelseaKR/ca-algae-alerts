"""Kansas KDHE harmful algal bloom status, built and switched off.

DECISIONS 0037. The department publishes no reuse grant, so under 0004 this
reader stays off (``LN_ENABLE_KANSAS``) until KDHE agrees in writing. Nothing
here is fetched, merged, published or put in the snapshot by default.

One ArcGIS MapServer layer on KDHE's own host (``maps.kdhe.ks.gov``, whose
robots.txt answers 404: no rules under 0011): layer 6, "Lake Point All
Status", every status the department has set on a public water since 2010.
Explicit, non-personal fields only: the water's id and name, the status, the
date the status was set, and the point. The layer holds more rows than one
answer carries (3,116 on 2026-11-06, 2,000 per answer), so it is read in
pages, 5 seconds apart.

The department's own words are the level, never a level of this project's:

====================  =======================================
status                treated as
====================  =======================================
Watch                 an advisory, shown as "Watch"
Warning               an advisory, shown as "Warning"
Advisory              an advisory, shown as "Advisory"
Lake Hazard           an advisory, shown as "Lake Hazard"
Lifted                an explicit end, dated by KDHE
Historical Pending    decides nothing (meaning asked of KDHE)
MIXED                 decides nothing (meaning asked of KDHE)
(blank)               decides nothing
(any other)           undetermined (decision 0027)
====================  =======================================

None of these is mapped onto California's caution, warning and danger
scale: a Kansas "Warning" is KDHE's word, not the Water Boards'.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import time
from collections import Counter
from collections.abc import Callable
from typing import Any
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import httpx

from caalgae import fetch
from caalgae.normalize import Normalized, Record, clean, parse_coordinate_any, water_key
from caalgae.sources import KS_KDHE_HAB

FIELDS = (
    "waterbody_id",
    "waterbody_name",
    "status",
    "Status_Set_Date",
    "LATITUDE",
    "LONGITUDE",
)
PAGE_SIZE = 2000  # the layer's maxRecordCount, read 2026-11-06
MAX_PAGES = 5
POLITE_DELAY_SECONDS = 5.0
MIN_ROWS = 1000  # 3,116 on 2026-11-06; far fewer is a truncated answer
EARLIEST_PLAUSIBLE = dt.date(2010, 1, 1)  # the layer's first status: 2010-07-08
CENTRAL = ZoneInfo("America/Chicago")

ADVISORY_STATUSES = frozenset({"Watch", "Warning", "Advisory", "Lake Hazard"})
END_STATUS = "Lifted"
UNREAD_STATUSES = frozenset({"Historical Pending", "MIXED"})


class KansasRefused(fetch.FetchError):
    """The layer's answer is not the shape read here. Refused whole."""


def page_url(offset: int) -> str:
    query = {
        "where": "1=1",
        "outFields": ",".join(FIELDS),
        "returnGeometry": "false",
        "orderByFields": "SQLVW_ID",
        "resultOffset": str(offset),
        "resultRecordCount": str(PAGE_SIZE),
        "f": "json",
    }
    return f"{KS_KDHE_HAB.dataset_url}/query?{urlencode(query)}"


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "blank"


def _date(ms: object) -> dt.date | None:
    if not isinstance(ms, int | float) or isinstance(ms, bool):
        return None
    return dt.datetime.fromtimestamp(ms / 1000, tz=dt.UTC).astimezone(CENTRAL).date()


def _tier(status: str) -> str:
    if status in ADVISORY_STATUSES:
        return "other_advisory"
    if status == END_STATUS:
        return "no_advisory"
    if status in UNREAD_STATUSES or not status:
        return "not_classified"
    return "unknown"


def _record(attributes: dict[str, Any], run_date: dt.date) -> Record | str:
    water_id = clean(attributes.get("waterbody_id"))
    name = clean(attributes.get("waterbody_name"))
    if not water_id:
        return "missing water id"
    if not name:
        return "missing water name"
    day = _date(attributes.get("Status_Set_Date"))
    if day is None:
        return "missing status date"
    if not EARLIEST_PLAUSIBLE <= day <= run_date:
        return "status date outside 2010 to the run date"
    status = clean(attributes.get("status"))
    tier = _tier(status)
    lat, lon = parse_coordinate_any(
        attributes.get("LATITUDE"), attributes.get("LONGITUDE"), state="KS"
    )
    return Record(
        id=f"ks-{water_id}-{day.isoformat()}-{_slug(status)}",
        source=KS_KDHE_HAB.id,
        state="KS",
        site_id=f"ks-{water_id}",
        water_key=water_key(name, "", "KS"),
        water_name=name,
        county_text="",
        landmark=name,
        lat=lat,
        lon=lon,
        date=day,
        level=status,
        tier=tier,
        explicit_no_advisory=tier == "no_advisory",
        end_date=None,
        detail="",
        stamp=None,
        end_kind="lifted",
    )


def _page(body: bytes) -> dict[str, Any]:
    try:
        data = json.loads(body)
    except ValueError as error:
        raise KansasRefused(f"Kansas layer answer is not JSON: {error}") from error
    if not isinstance(data, dict):
        raise KansasRefused("Kansas layer answer is not a JSON object")
    if "error" in data:
        raise KansasRefused(f"Kansas layer answered an error: {data['error']}")
    if not isinstance(data.get("features"), list):
        raise KansasRefused("Kansas layer answer has no feature list")
    fields = data.get("fields")
    names = (
        {f.get("name") for f in fields if isinstance(f, dict)}
        if isinstance(fields, list)
        else set()
    )
    missing = [f for f in FIELDS if f not in names]
    if missing:
        raise KansasRefused(f"Kansas layer no longer has the fields {missing}")
    return data


def normalize(pages: list[bytes], run_date: dt.date) -> Normalized:
    """Every page of one read, in order. The last page must say it is the
    last; a read that stops early is refused, never taken as the whole."""
    if not pages:
        raise KansasRefused("Kansas read returned no pages")
    datas = [_page(body) for body in pages]
    if datas[-1].get("exceededTransferLimit"):
        raise KansasRefused("Kansas read stopped before the layer's last row")
    features = [f for data in datas for f in data["features"]]
    if len(features) < MIN_ROWS:
        raise KansasRefused(f"Kansas layer returned {len(features)} rows")
    records: dict[str, Record] = {}
    quarantine: Counter[str] = Counter()
    for feature in features:
        attributes = feature.get("attributes") if isinstance(feature, dict) else None
        if not isinstance(attributes, dict):
            quarantine["row without attributes"] += 1
            continue
        result = _record(attributes, run_date)
        if isinstance(result, str):
            quarantine[result] += 1
        elif result.id in records:
            quarantine["the same status on the same water and day twice"] += 1
        else:
            records[result.id] = result
    if not records:
        raise KansasRefused("Kansas layer has no status this pipeline can place")
    return Normalized(
        records=list(records.values()), quarantine=quarantine, rows_read=len(features)
    )


def fetch_pages(
    client: httpx.Client, sleep: Callable[[float], None] = time.sleep
) -> list[bytes]:
    """Robots first, then one page at a time until the layer says it is done."""
    fetch.robots_allows(client, page_url(0))
    pages: list[bytes] = []
    for index in range(MAX_PAGES):
        if index:
            sleep(POLITE_DELAY_SECONDS)
        response = client.get(page_url(index * PAGE_SIZE))
        if response.status_code != 200:
            raise fetch.FetchError(f"Kansas layer returned HTTP {response.status_code}")
        pages.append(response.content)
        try:
            more = bool(json.loads(response.content).get("exceededTransferLimit"))
        except (ValueError, AttributeError):
            return pages  # normalize() refuses it with the reason
        if not more:
            return pages
    raise KansasRefused(f"Kansas layer needs more than {MAX_PAGES} pages")
