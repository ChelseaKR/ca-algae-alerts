"""EPA CyAN: a separate satellite-estimate record kind that never decides a
status, never reads a gap as zero, and is matched only by name and place."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from paths import CYAN_CACHE, CYAN_WEEKLY

from caalgae import cyan, fetch, wording

NOW = dt.datetime(2026, 10, 12, 13, tzinfo=dt.UTC)


def waters() -> list[dict[str, Any]]:
    return [
        {
            "id": "ca-alameda-lake-alpha",
            "state": "CA",
            "name": "Lake Alpha",
            "center": {"lat": 37.80, "lon": -122.20},
        },
        {
            "id": "ca-kern-gamma-pond",
            "state": "CA",
            "name": "Gamma Pond",
            "center": {"lat": 35.60, "lon": -118.50},
        },
        {
            "id": "ca-x-no-center",
            "state": "CA",
            "name": "Beta Reservoir",
            "center": None,
        },
    ]


def test_weekly_parse_drops_unseen_weeks_and_keeps_newest_first() -> None:
    readings = cyan.parse_weekly(json.loads(CYAN_WEEKLY.read_text()))
    assert readings[0] == {
        "week_end": "2026-10-10",
        "cells_per_ml": 554626,
        "max_cells_per_ml": 602560,
        "valid_cells": 6,
    }
    assert "2026-08-22" not in {r["week_end"] for r in readings}  # validCellsCount 0
    assert [r["week_end"] for r in readings] == sorted(
        (r["week_end"] for r in readings), reverse=True
    )
    assert len(readings) <= cyan.KEEP_WEEKS


def test_matching_needs_state_name_and_place() -> None:
    cache = json.loads(CYAN_CACHE.read_text())
    matched = cyan.match(cache["lakes"], waters())
    assert {k: v["objectid"] for k, v in matched.items()} == {
        "ca-alameda-lake-alpha": 1
    }
    # Gamma Pond's CyAN lake is ~140 km away; Nevada's "Lake Alpha" is another
    # state; a water with no coordinates is never matched on name alone.


def test_blocks_are_satellite_estimates_and_an_empty_series_stays_empty() -> None:
    cache = json.loads(CYAN_CACHE.read_text())
    ws = [
        *waters(),
        {
            "id": "ca-lake-beta-reservoir",
            "state": "CA",
            "name": "Beta Reservoir",
            "center": {"lat": 39.05, "lon": -122.80},
        },
    ]
    out = cyan.blocks(cache, ws)
    assert out["ca-alameda-lake-alpha"]["record_kind"] == "satellite_estimate"
    assert out["ca-lake-beta-reservoir"]["readings"] == []


def test_cells_label_rounds_and_never_reads_zero_as_none() -> None:
    assert wording.cells_label(554626) == "about 550,000 cells/mL"
    assert wording.cells_label(0) == "below what the satellite can detect"


def test_due_weekly() -> None:
    assert cyan.is_due(cyan.empty_cache(), NOW)
    assert not cyan.is_due({"fetched_at": "2026-10-10T00:00:00Z"}, NOW)
    assert cyan.is_due({"fetched_at": "2026-10-01T00:00:00Z"}, NOW)


def test_cache_round_trip_and_version(tmp_path: Path) -> None:
    path = tmp_path / "c.json"
    cyan.save_cache(cyan.empty_cache(), path)
    assert cyan.load_cache(path) == cyan.empty_cache()
    assert cyan.load_cache(tmp_path / "none.json") == cyan.empty_cache()
    path.write_text('{"version": 9}')
    with pytest.raises(fetch.FetchError):
        cyan.load_cache(path)


@respx.mock
def test_refresh_checks_robots_lists_once_and_fetches_only_matches() -> None:
    respx.get("https://qed.epa.gov/robots.txt").mock(return_value=httpx.Response(404))
    lakes = json.loads(CYAN_CACHE.read_text())["lakes"]
    listing = respx.get(cyan.SEARCH_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "waterbodies": [
                    *lakes,
                    {
                        "objectid": 9,
                        "name": "Lake Ontario",
                        "state_abbr": "NY",
                        "areasqkm": 1,
                        "centroid_lat": 43,
                        "centroid_lng": -77,
                    },
                ]
            },
        )
    )
    series = respx.get(url__regex=r".*/location/data/.*").mock(
        return_value=httpx.Response(200, json=json.loads(CYAN_WEEKLY.read_text()))
    )
    slept: list[float] = []
    with fetch.make_client() as client:
        cache = cyan.refresh(
            client, cyan.empty_cache(), waters(), NOW, sleep=slept.append
        )
    assert listing.call_count == 1
    assert series.call_count == 1 and slept == [cyan.SPACING_SECONDS]
    assert list(cache["series"]) == ["1"]
    assert {lake["state_abbr"] for lake in cache["lakes"]} == {
        "CA"
    }  # NY dropped; NV not in STATES


@respx.mock
def test_refresh_refuses_a_robots_error() -> None:
    respx.get("https://qed.epa.gov/robots.txt").mock(return_value=httpx.Response(503))
    listing = respx.get(cyan.SEARCH_URL).mock(return_value=httpx.Response(200))
    with fetch.make_client() as client, pytest.raises(fetch.RobotsOffLimits):
        cyan.refresh(client, cyan.empty_cache(), waters(), NOW)
    assert not listing.called


@respx.mock
def test_refresh_failures() -> None:
    respx.get("https://qed.epa.gov/robots.txt").mock(return_value=httpx.Response(404))
    respx.get(cyan.SEARCH_URL).mock(
        return_value=httpx.Response(200, json={"waterbodies": []})
    )
    with (
        fetch.make_client() as client,
        pytest.raises(fetch.FetchError, match="no California"),
    ):
        cyan.refresh(client, cyan.empty_cache(), waters(), NOW)
