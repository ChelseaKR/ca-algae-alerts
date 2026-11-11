"""A changed CyAN answer keeps the cache and never stops a run
(source-outage audit 2026-11-05, finding 8; DECISIONS 0030)."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from paths import CYAN_CACHE, CYAN_WEEKLY

from caalgae import cli, cyan, fetch
from caalgae import history as hist

NOW = dt.datetime(2026, 10, 12, 13, tzinfo=dt.UTC)


def _lakes() -> list[dict[str, Any]]:
    lakes: list[dict[str, Any]] = json.loads(CYAN_CACHE.read_text())["lakes"]
    return lakes


def _ours() -> list[dict[str, Any]]:
    return [lake for lake in _lakes() if lake["state_abbr"] in cyan.STATES]


def test_the_real_list_shape_parses() -> None:
    assert _ours() and cyan.parse_lakes({"waterbodies": _lakes()}) == _ours()


@pytest.mark.parametrize(
    "body",
    [
        [],
        {"waterbodies": {"0": {}}},
        {"items": []},
        {"waterbodies": ["Clear Lake"]},
    ],
)
def test_another_list_shape_is_refused(body: Any) -> None:
    with pytest.raises(cyan.ShapeError):
        cyan.parse_lakes(body)


def test_a_renamed_field_on_our_lake_is_refused() -> None:
    lake = dict(_ours()[0])
    lake["centroid_lon"] = lake.pop("centroid_lng")
    with pytest.raises(cyan.ShapeError, match="centroid_lng"):
        cyan.parse_lakes({"waterbodies": [lake]})


@pytest.mark.parametrize("field", ["areasqkm", "centroid_lat", "objectid"])
def test_a_mistyped_field_on_our_lake_is_refused(field: str) -> None:
    lake = dict(_ours()[0])
    lake[field] = "12.5"
    with pytest.raises(cyan.ShapeError, match="mistyped"):
        cyan.parse_lakes({"waterbodies": [lake]})


def test_another_states_odd_lake_is_ignored() -> None:
    odd = {"state_abbr": "NY", "name": "Lake Ontario"}  # no other fields
    assert cyan.parse_lakes({"waterbodies": [*_lakes(), odd]}) == _ours()


@pytest.mark.parametrize(
    "body", [[], "x", {"outputs": {"a": 1}}, {"outputs": ["2026-10-10"]}]
)
def test_another_series_shape_is_refused(body: Any) -> None:
    with pytest.raises(cyan.ShapeError):
        cyan.parse_weekly(body)


def test_the_real_series_still_parses() -> None:
    assert cyan.parse_weekly(json.loads(CYAN_WEEKLY.read_text()))


def test_a_shape_error_is_a_fetch_error_so_the_run_goes_on() -> None:
    assert issubclass(cyan.ShapeError, fetch.FetchError)


def _args(cache: Path) -> argparse.Namespace:
    return argparse.Namespace(fixture_page=None, cyan_cache=cache, cyan_refresh="force")


def _old_parse_lakes(body: Any) -> list[dict[str, Any]]:
    """The read before this change, kept to prove the sabotage applies."""
    return [
        {k: lake[k] for k in cyan.LAKE_FIELDS}
        for lake in body.get("waterbodies", [])
        if lake.get("state_abbr") in cyan.STATES
    ]


@respx.mock
def test_a_renamed_field_keeps_the_cache_and_the_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_path = tmp_path / "cyan.json"
    shutil.copy(CYAN_CACHE, cache_path)
    before = cache_path.read_text()
    lake = dict(_ours()[0])
    lake["centroid_lon"] = lake.pop("centroid_lng")
    respx.get("https://qed.epa.gov/robots.txt").mock(return_value=httpx.Response(404))
    respx.get(cyan.SEARCH_URL).mock(
        return_value=httpx.Response(200, json={"waterbodies": [lake]})
    )
    history = hist.History(entries={}, files=[])

    # The sabotage applies: read the old way, this answer crashes the run.
    with monkeypatch.context() as m:
        m.setattr(cyan, "parse_lakes", _old_parse_lakes)
        with pytest.raises(KeyError):
            cli._cyan(_args(cache_path), history, NOW.date(), NOW)

    kept = cli._cyan(_args(cache_path), history, NOW.date(), NOW)
    assert kept == json.loads(before)
    assert cache_path.read_text() == before
