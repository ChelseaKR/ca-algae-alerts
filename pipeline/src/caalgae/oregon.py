"""Oregon Health Authority recreational cyanobacteria advisories, built and
switched off.

DECISIONS 0037. oregon.gov's terms grant no reuse right, so under 0004 this
reader stays off (``LN_ENABLE_OREGON``) until OHA agrees in writing (asked
2026-11-02). Nothing here is fetched, merged, published or put in the
snapshot by default.

The advisories page on www.oregon.gov draws its table from a SharePoint list,
"CurrentCyanobacteriaAdvisories". www.oregon.gov's robots.txt disallows
``/_layouts`` and ``/_vti_bin`` paths, not ``/oha/`` or ``_api`` (read
2026-11-06). One request per run, explicit fields only: the list item's id,
the water's title and the agency's description of the stretch, the county,
the status, the date, and the agency's notes on the bloom and toxin. Author,
editor and timestamps are never requested.

Each list item is one water carrying its current status; OHA edits the item
when the status changes. A record's id therefore carries the status and its
date, so a change is a new record and the earlier one stays in history.

The agency's own words are the level, never a level of this project's:

===================================  =====================================
status                               treated as
===================================  =====================================
Advisory in effect                   an advisory
Precaution in effect                 an advisory (OHA's precaution)
Permanent Advisory                   an advisory
Advisory downgraded to precaution    an advisory (the page's legend)
Advisory has been lifted             an explicit end, dated by OHA
Precaution has been lifted           an explicit end, dated by OHA
(any other)                          undetermined (decision 0027)
===================================  =====================================

The list has no coordinates. A water that leaves the list is never read as
an end: OHA moves lifted waters to its yearly archive after the season.
Which event a lifted row's ``Date`` records is asked of OHA; until then the
date is shown as OHA's date for that status, nothing more.
"""

from __future__ import annotations

import datetime as dt
import html
import json
import re
from collections import Counter
from html.parser import HTMLParser
from typing import Any
from urllib.parse import quote
from zoneinfo import ZoneInfo

import httpx

from caalgae import fetch
from caalgae.normalize import Normalized, Record, clean, water_key
from caalgae.sources import OR_OHA_HAB

FIELDS = (
    "ID",
    "Title",
    "Waterbody",
    "County",
    "Status",
    "Date",
    "Details",
    "Toxin_x002f_Measure",
    "Display_x002d_On_x002d_Page",
)
TOP = 500
QUERY_URL = (
    OR_OHA_HAB.dataset_url
    + "?"
    + quote("$select", safe="")
    + "="
    + ",".join(FIELDS)
    + "&"
    + quote("$top", safe="")
    + f"={TOP}"
)
ACCEPT = "application/json;odata=nometadata"
PACIFIC = ZoneInfo("America/Los_Angeles")
EARLIEST_PLAUSIBLE = dt.date(2007, 1, 1)  # OHA's archive begins in 2007

ADVISORY_STATUSES = frozenset(
    {
        "Advisory in effect",
        "Precaution in effect",
        "Permanent Advisory",
        "Advisory downgraded to precaution",
    }
)
END_STATUSES = frozenset({"Advisory has been lifted", "Precaution has been lifted"})


class OregonRefused(fetch.FetchError):
    """The list's answer is not the shape read here. Refused whole."""


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"br", "div", "p"}:
            self.parts.append(" ")


_INVISIBLE = re.compile("[​‌‍﻿]")


def text_of(value: object) -> str:
    """The words of one of OHA's rich-text fields, without markup, zero-width
    spaces or non-breaking spaces. Not a string: empty."""
    if not isinstance(value, str):
        return ""
    parser = _Text()
    parser.feed(value)
    parser.close()
    words = html.unescape("".join(parser.parts)).replace("\xa0", " ")
    return clean(_INVISIBLE.sub("", words))


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "blank"


def _date(value: object) -> dt.date | None:
    if not isinstance(value, str):
        return None
    try:
        moment = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is None:
        return None
    return moment.astimezone(PACIFIC).date()


def _tier(status: str) -> str:
    if status in ADVISORY_STATUSES:
        return "other_advisory"
    if status in END_STATUSES:
        return "no_advisory"
    return "unknown"


def _record(item: dict[str, Any], run_date: dt.date) -> Record | str:
    item_id = item.get("ID")
    if not isinstance(item_id, int) or isinstance(item_id, bool):
        return "missing list item id"
    if item.get("Display_x002d_On_x002d_Page") is not True:
        return "not shown on OHA's page"
    name = text_of(item.get("Title"))
    if not name:
        return "missing water name"
    statuses = item.get("Status")
    if not isinstance(statuses, list) or len(statuses) != 1:
        return "status is not exactly one value"
    status = text_of(statuses[0])
    day = _date(item.get("Date"))
    if day is None:
        return "missing date"
    if not EARLIEST_PLAUSIBLE <= day <= run_date:
        return "date outside 2007 to the run date"
    county = text_of(item.get("County"))
    stretch = text_of(item.get("Waterbody")) or name
    notes = [
        n if n.endswith(".") else f"{n}."
        for n in (
            text_of(item.get("Details")),
            text_of(item.get("Toxin_x002f_Measure")),
        )
        if n
    ]
    tier = _tier(status)
    return Record(
        id=f"or-{item_id}-{day.isoformat()}-{_slug(status)}",
        source=OR_OHA_HAB.id,
        state="OR",
        site_id=f"or-{item_id}",
        water_key=water_key(name, county, "OR"),
        water_name=name,
        county_text=county,
        landmark=stretch,
        lat=None,
        lon=None,
        date=day,
        level=status,
        tier=tier,
        explicit_no_advisory=tier == "no_advisory",
        end_date=None,
        detail=" ".join(notes),
        stamp=None,
        end_kind="lifted",
    )


def _items(pages: list[bytes]) -> list[dict[str, Any]]:
    """The list's items, or a refusal of the whole answer."""
    if len(pages) != 1:
        raise OregonRefused(f"Oregon read is one answer, not {len(pages)}")
    try:
        data = json.loads(pages[0])
    except ValueError as error:
        raise OregonRefused(f"Oregon list answer is not JSON: {error}") from error
    if not isinstance(data, dict) or not isinstance(data.get("value"), list):
        raise OregonRefused("Oregon list answer has no item list")
    if "odata.nextLink" in data or "@odata.nextLink" in data:
        raise OregonRefused("Oregon list has more items than one answer carries")
    items: list[dict[str, Any]] = data["value"]
    if not items:
        raise OregonRefused("Oregon list returned no items")
    for item in items:
        missing = [f for f in FIELDS if not isinstance(item, dict) or f not in item]
        if missing:
            raise OregonRefused(f"Oregon list no longer has the fields {missing}")
    return items


def normalize(pages: list[bytes], run_date: dt.date) -> Normalized:
    items = _items(pages)
    records: dict[str, Record] = {}
    quarantine: Counter[str] = Counter()
    for item in items:
        result = _record(item, run_date)
        if isinstance(result, str):
            quarantine[result] += 1
        elif result.id in records:
            quarantine["the same list item twice"] += 1
        else:
            records[result.id] = result
    if not records:
        raise OregonRefused("Oregon list has no item this pipeline can place")
    return Normalized(
        records=list(records.values()), quarantine=quarantine, rows_read=len(items)
    )


def fetch_pages(client: httpx.Client) -> list[bytes]:
    fetch.robots_allows(client, QUERY_URL)
    response = client.get(QUERY_URL, headers={"Accept": ACCEPT})
    if response.status_code != 200:
        raise fetch.FetchError(f"Oregon list returned HTTP {response.status_code}")
    return [response.content]
