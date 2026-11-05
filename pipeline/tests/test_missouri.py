"""Missouri, the second state: explicit fields only, its codes kept, and a
closed case never read as an all-clear."""

from __future__ import annotations

import datetime as dt
import json
from typing import Any

import httpx
import pytest
import respx
from paths import MO_POINTS

from caalgae import fetch, missouri
from caalgae import status as st

RUN = dt.date(2026, 10, 12)


def feature(**attrs: Any) -> dict[str, Any]:
    base = {"objectid": 1, "WBName": "Test Lake", "HABODat": 1791046800000,
            "BloomStat": "advise", "CaseStatus": "Active", "DissDat": None, "WBType": "lakepond"}  # fmt: skip
    return {"attributes": {**base, **attrs}, "geometry": {"x": -94.2, "y": 39.0}}


def test_real_layer_reads_with_counts() -> None:
    result = missouri.normalize(MO_POINTS.read_bytes(), RUN)
    assert result.rows_read == 278
    assert dict(result.quarantine) == {"missing observation date": 18}
    assert {r.state for r in result.records} == {"MO"}
    assert {r.source for r in result.records} == {"mo-dnr-hab"}
    assert all(r.id.startswith("mo-") for r in result.records)


def test_only_non_personal_fields_are_requested() -> None:
    assert set(missouri.FIELDS) == {
        "objectid",
        "WBName",
        "HABODat",
        "BloomStat",
        "CaseStatus",
        "DissDat",
        "WBType",
    }
    # PubInfo is the department's own public note, read since 0023.
    assert missouri.OPTIONAL_FIELDS == ("PubInfo",)
    assert "PubInfo" in missouri.QUERY_URL
    for personal in ("LeadAG", "WBOwn", "WBOwno", "HABDesc", "IConf"):
        assert personal not in missouri.QUERY_URL


def test_active_advisory() -> None:
    r = missouri._record(feature(), RUN)
    assert not isinstance(r, str)
    assert r.tier == "other_advisory"
    assert r.level == "Advisory (advise)"
    assert r.date == dt.date(2026, 10, 3)  # Central time
    s = st.site_status([r], RUN)
    assert s.kind == st.ADVISORY


def test_closed_case_without_a_dissipation_date_is_not_an_all_clear() -> None:
    r = missouri._record(feature(CaseStatus="Closed"), RUN)
    assert not isinstance(r, str)
    assert st.site_status([r], RUN).kind == st.ADVISORY
    assert r.detail == "Case closed."


def test_dissipated_with_a_date_is_an_explicit_end() -> None:
    r = missouri._record(
        feature(BloomStat="dissap", CaseStatus="Closed", DissDat=1791651600000), RUN
    )
    assert not isinstance(r, str)
    s = st.site_status([r], RUN)
    assert s.kind == st.NO_ADVISORY_RECORDED
    assert s.lift_kind == "dissipated"
    assert s.lift_date == dt.date(2026, 10, 10)


def test_advisory_with_a_dissipation_date_ends_on_it() -> None:
    r = missouri._record(feature(DissDat=1791651600000), RUN)
    assert not isinstance(r, str)
    s = st.site_status([r], RUN)
    assert (s.kind, s.lift_kind) == (st.NO_ADVISORY_RECORDED, "end_date")


def test_dissipated_without_a_date_decides_nothing() -> None:
    r = missouri._record(feature(BloomStat="dissap", CaseStatus="Closed"), RUN)
    assert not isinstance(r, str)
    assert r.tier == "not_classified"
    assert "no date recorded" in r.detail
    assert st.site_status([r], RUN).kind == st.UNDETERMINED


@pytest.mark.parametrize("code", ["notthr", "notver", "report", None])
def test_other_codes_decide_nothing(code: str | None) -> None:
    r = missouri._record(feature(BloomStat=code), RUN)
    assert not isinstance(r, str)
    assert st.site_status([r], RUN).kind == st.UNDETERMINED


def test_rows_that_cannot_be_placed_are_quarantined() -> None:
    assert missouri._record(feature(HABODat=None), RUN) == "missing observation date"
    assert missouri._record(feature(WBName="  "), RUN) == "missing water body name"
    assert missouri._record(feature(objectid=None), RUN) == "missing case id"
    assert (
        missouri._record(feature(HABODat=4102444800000), RUN)
        == "observation date outside 2016 to the run date"
    )


def test_coordinates_outside_missouri_are_dropped() -> None:
    f = feature()
    f["geometry"] = {"x": -122.0, "y": 37.0}
    r = missouri._record(f, RUN)
    assert not isinstance(r, str) and r.lat is None


def test_truncated_or_error_answers_are_refused() -> None:
    with pytest.raises(fetch.FetchError, match="rows"):
        missouri.normalize(json.dumps({"features": [feature()]}).encode(), RUN)
    with pytest.raises(fetch.FetchError, match="error"):
        missouri.normalize(b'{"error": {"code": 400}}', RUN)
    with pytest.raises(fetch.FetchError, match="more rows"):
        missouri.normalize(
            json.dumps({"features": [], "exceededTransferLimit": True}).encode(), RUN
        )


@respx.mock
def test_live_fetch_checks_robots_first() -> None:
    robots = respx.get("https://gis.dnr.mo.gov/robots.txt").mock(
        return_value=httpx.Response(404)
    )
    layer = respx.get(missouri.QUERY_URL).mock(
        return_value=httpx.Response(200, content=MO_POINTS.read_bytes())
    )
    with fetch.make_client() as client:
        assert missouri.fetch_cases(client) == MO_POINTS.read_bytes()
    assert robots.called and layer.called


@respx.mock
def test_a_robots_error_makes_the_host_off_limits() -> None:
    respx.get("https://gis.dnr.mo.gov/robots.txt").mock(
        return_value=httpx.Response(403, text="Invalid URL")
    )
    layer = respx.get(missouri.QUERY_URL).mock(return_value=httpx.Response(200))
    with fetch.make_client() as client, pytest.raises(fetch.RobotsOffLimits):
        missouri.fetch_cases(client)
    assert not layer.called


@respx.mock
def test_a_robots_disallow_is_obeyed() -> None:
    respx.get("https://gis.dnr.mo.gov/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nDisallow: /host/\n")
    )
    layer = respx.get(missouri.QUERY_URL).mock(return_value=httpx.Response(200))
    with (
        fetch.make_client() as client,
        pytest.raises(fetch.RobotsOffLimits, match="disallows"),
    ):
        missouri.fetch_cases(client)
    assert not layer.called


@respx.mock
def test_a_robots_redirect_to_a_non_robots_page_is_off_limits() -> None:
    respx.get("https://gis.dnr.mo.gov/robots.txt").mock(
        return_value=httpx.Response(
            302, headers={"location": "https://gis.dnr.mo.gov/login"}
        )
    )
    respx.get("https://gis.dnr.mo.gov/login").mock(
        return_value=httpx.Response(200, text="<html>sign in</html>")
    )
    layer = respx.get(missouri.QUERY_URL).mock(return_value=httpx.Response(200))
    with (
        fetch.make_client() as client,
        pytest.raises(fetch.RobotsOffLimits, match="redirected"),
    ):
        missouri.fetch_cases(client)
    assert not layer.called


@respx.mock
def test_a_robots_redirect_to_another_robots_file_is_read() -> None:
    respx.get("https://gis.dnr.mo.gov/robots.txt").mock(
        return_value=httpx.Response(
            301, headers={"location": "https://www.gis.dnr.mo.gov/robots.txt"}
        )
    )
    respx.get("https://www.gis.dnr.mo.gov/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nAllow: /\n")
    )
    respx.get(missouri.QUERY_URL).mock(
        return_value=httpx.Response(200, content=MO_POINTS.read_bytes())
    )
    with fetch.make_client() as client:
        assert missouri.fetch_cases(client) == MO_POINTS.read_bytes()
