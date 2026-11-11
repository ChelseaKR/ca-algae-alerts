"""EPA CyAN satellite estimates, a separate record kind (docs/DECISIONS.md 0010).

What this layer is, and what it never is:

- A **satellite estimate** of cyanobacteria abundance (cells/mL), from the
  weekly Sentinel-3 OLCI composite, for lakes of about 1 km² and larger.
- **Never an advisory, never the end of one, never "safe".** It is stored
  apart from advisory records and never reaches ``status.py``. It measures
  how much cyanobacteria there is, not toxins; clouds and ice leave gaps;
  small ponds and most rivers are not covered.

Requests, all to ``qed.epa.gov`` after its robots.txt is checked:

1. One list of every CyAN waterbody (``waterbody/search/?name=``).
2. For each of our California and Missouri waterbodies that matches a CyAN
   lake by name and distance, one weekly series at CyAN's own centroid.

The answers are cached in ``pipeline/data/cyan.json`` and refreshed at most
once every ``REFRESH_DAYS``, the composite's own cadence, with
``SPACING_SECONDS`` between requests. A failed refresh keeps the cache, and
every reading carries its own week, so an old estimate is shown with its date
and never as current.
"""

from __future__ import annotations

import datetime as dt
import json
import math
import re
import time
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

import httpx

from caalgae import fetch
from caalgae.sources import EPA_CYAN, SATELLITE_ESTIMATE

SEARCH_URL = "https://qed.epa.gov/cyanweb/waterbody/search/?name="
WEEKLY_URL = (
    "https://qed.epa.gov/cyanweb/cyan/cyano/location/data/{lat}/{lon}/all"
    "?type=olci&frequency=weekly"
)
STATES = ("CA", "MO")
REFRESH_DAYS = 6
KEEP_WEEKS = 8
SPACING_SECONDS = 2.0
CACHE_VERSION = 1
LAKE_FIELDS = (
    "objectid",
    "name",
    "state_abbr",
    "areasqkm",
    "centroid_lat",
    "centroid_lng",
)


class ShapeError(fetch.FetchError):
    """CyAN answered in a shape this pipeline does not read. Like any failed
    refresh, the cache is kept and the run goes on (source-outage audit,
    2026-11-05, finding 8): a changed field must never stop the advisories."""


def _number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def parse_lakes(body: Any) -> list[dict[str, Any]]:
    """California and Missouri lakes from the CyAN list, every field checked.
    A missing or mistyped field on one of our lakes is a changed format, so
    the whole list is refused rather than read in part."""
    if not isinstance(body, dict) or not isinstance(body.get("waterbodies"), list):
        raise ShapeError("CyAN list is not an object with a waterbodies list")
    lakes = []
    for lake in body["waterbodies"]:
        if not isinstance(lake, dict):
            raise ShapeError("CyAN list holds an entry that is not an object")
        if lake.get("state_abbr") not in STATES:
            continue
        missing = [k for k in LAKE_FIELDS if k not in lake]
        if missing:
            raise ShapeError(f"CyAN lake is missing {', '.join(missing)}")
        if not (
            isinstance(lake["objectid"], int)
            and not isinstance(lake["objectid"], bool)
            and isinstance(lake["name"], str)
            and all(
                _number(lake[k]) for k in ("areasqkm", "centroid_lat", "centroid_lng")
            )
        ):
            raise ShapeError(f"CyAN lake {lake.get('objectid')!r} has a mistyped field")
        lakes.append({k: lake[k] for k in LAKE_FIELDS})
    return lakes


def norm_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()


def km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))


def match(
    lakes: Iterable[dict[str, Any]], waters: Iterable[dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    """Our waterbody id -> the CyAN lake it is. Same state, same name, and
    our reported spots' center within a distance that grows with the lake
    (a 900 km² sea is matched farther out than a 2 km² reservoir).
    A water with no coordinates is never matched: a name alone is not enough.
    """
    by_name: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for lake in lakes:
        by_name.setdefault((lake["state_abbr"], norm_name(lake["name"])), []).append(
            lake
        )
    out: dict[str, dict[str, Any]] = {}
    for water in waters:
        center = water.get("center")
        candidates = by_name.get((water["state"], norm_name(water["name"])), [])
        if not center or not candidates:
            continue
        best = min(
            candidates,
            key=lambda c: km(
                center["lat"], center["lon"], c["centroid_lat"], c["centroid_lng"]
            ),
        )
        limit = max(15.0, 2.0 * math.sqrt(float(best["areasqkm"])))
        if (
            km(center["lat"], center["lon"], best["centroid_lat"], best["centroid_lng"])
            <= limit
        ):
            out[water["id"]] = best
    return out


def _week_end(text: str) -> dt.date | None:
    try:
        return dt.datetime.strptime(text[:10], "%m-%d-%Y").date()
    except ValueError:
        return None


def parse_weekly(body: Any) -> list[dict[str, Any]]:
    """Weekly readings, newest first. An entry with no valid cells is a
    week the satellite could not see the lake; it is dropped, never read as
    zero. An answer in another shape raises ``ShapeError``."""
    if not isinstance(body, dict):
        raise ShapeError("CyAN series is not an object")
    outputs = body.get("outputs") or []
    if not isinstance(outputs, list) or not all(isinstance(o, dict) for o in outputs):
        raise ShapeError("CyAN series outputs is not a list of objects")
    readings: list[dict[str, Any]] = []
    for o in outputs:
        end = _week_end(str(o.get("imageDate", "")))
        cells = o.get("cellConcentration")
        valid = o.get("validCellsCount")
        if o.get("satelliteImageFrequency") != "Weekly" or end is None:
            continue
        if (
            not isinstance(cells, int | float)
            or not isinstance(valid, int)
            or valid < 1
        ):
            continue
        maximum = o.get("maxCellConcentration")
        readings.append(
            {
                "week_end": end.isoformat(),
                "cells_per_ml": round(float(cells)),
                "max_cells_per_ml": round(float(maximum))
                if isinstance(maximum, int | float)
                else None,
                "valid_cells": valid,
            }
        )
    readings.sort(key=lambda r: str(r["week_end"]), reverse=True)
    return readings[:KEEP_WEEKS]


def empty_cache() -> dict[str, Any]:
    return {"version": CACHE_VERSION, "fetched_at": None, "lakes": [], "series": {}}


def load_cache(path: Path) -> dict[str, Any]:
    if not path.exists():
        return empty_cache()
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    if data.get("version") != CACHE_VERSION:
        raise fetch.FetchError(f"{path}: unknown CyAN cache version")
    return data


def save_cache(cache: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(cache, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )


def is_due(cache: dict[str, Any], now: dt.datetime) -> bool:
    fetched = cache.get("fetched_at")
    if not fetched:
        return True
    last = dt.datetime.fromisoformat(str(fetched).replace("Z", "+00:00"))
    return now - last >= dt.timedelta(days=REFRESH_DAYS)


def refresh(
    client: httpx.Client,
    cache: dict[str, Any],
    waters: list[dict[str, Any]],
    now: dt.datetime,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Fetch the list and the matched lakes' series. Raises on the first
    failure; the caller keeps the old cache."""
    fetch.robots_allows(client, SEARCH_URL)
    response = client.get(SEARCH_URL)
    if response.status_code != 200:
        raise fetch.FetchError(f"CyAN list returned HTTP {response.status_code}")
    lakes = parse_lakes(response.json())
    if not lakes:
        raise fetch.FetchError("CyAN list holds no California or Missouri lake")
    series: dict[str, Any] = {}
    for lake in {m["objectid"]: m for m in match(lakes, waters).values()}.values():
        sleep(SPACING_SECONDS)
        url = WEEKLY_URL.format(lat=lake["centroid_lat"], lon=lake["centroid_lng"])
        answer = client.get(url)
        if answer.status_code != 200:
            raise fetch.FetchError(f"CyAN series returned HTTP {answer.status_code}")
        series[str(lake["objectid"])] = parse_weekly(answer.json())
    return {
        "version": CACHE_VERSION,
        "fetched_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "lakes": sorted(lakes, key=lambda x: x["objectid"]),
        "series": series,
    }


def blocks(
    cache: dict[str, Any], waters: list[dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    """Each matched waterbody's satellite block for the snapshot. A matched
    lake with no usable week has ``readings: []``, shown as "no satellite
    reading on file", never as zero."""
    out = {}
    for water_id, lake in match(cache.get("lakes", []), waters).items():
        key = str(lake["objectid"])
        if key not in cache.get("series", {}):
            continue
        out[water_id] = {
            "source": EPA_CYAN.id,
            "record_kind": SATELLITE_ESTIMATE,
            "cyan_name": lake["name"],
            "cyan_objectid": lake["objectid"],
            "area_km2": round(float(lake["areasqkm"]), 1),
            "fetched_at": cache["fetched_at"],
            "readings": cache["series"][key],
        }
    return out
