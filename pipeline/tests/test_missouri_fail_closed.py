"""Missouri fails closed (docs/DECISIONS.md 0019, amended by 0024): when the
department's layer is gone, changed or empty, Missouri's pages switch to
their dated "data unavailable" mode instead of showing its last records as
current. California is never held back by it. Also: the department's own
"general purposes only" caveat, verbatim, beside its data."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from paths import MO_POINTS, PAGE, TRAPS
from test_site import text_of

from caalgae import cli, fetch, missouri
from caalgae import history as hist
from caalgae.sources import MO_DNR_HAB, MO_MAP_CAVEAT, MO_MAP_CAVEAT_URL

RUN = dt.date(2026, 10, 12)


def layer(**changes: Any) -> bytes:
    """The real layer's answer, with top-level keys replaced."""
    data: dict[str, Any] = json.loads(MO_POINTS.read_bytes())
    data.update(changes)
    return json.dumps(data).encode()


def build(tmp: Path, *extra: str, run_today: str = "2026-10-12") -> Path:
    assert cli.main([
        "--fixture-page", str(PAGE), "--fixture-csv", str(TRAPS),
        "--run-today", run_today,
        "--history", str(tmp / "h.json"), "--site-out", str(tmp / "site"),
        "--snapshot-out", str(tmp / "s.json"), *extra,
    ]) == 0  # fmt: skip
    return tmp


def snap(tmp: Path) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads((tmp / "s.json").read_text())
    return loaded


def assert_missouri_absent(tmp: Path) -> None:
    s = snap(tmp)
    assert {w["state"] for w in s["waterbodies"]} == {"CA"}
    assert MO_DNR_HAB.id not in {src["id"] for src in s["sources"]}
    assert MO_DNR_HAB.id not in {f["source"] for f in s["source_files"]}
    site = tmp / "site"
    assert not (site / "state" / "mo").exists()
    assert not list((site / "water").glob("mo-*"))
    home = text_of(site / "index.html")
    assert "Missouri" not in home
    assert "Missouri" not in text_of(site / "about" / "index.html")
    assert "Missouri" not in text_of(
        site / "water" / "ca-alameda-lake-alpha" / "index.html"
    )
    assert "mo-" not in (site / "sitemap.xml").read_text()


def assert_missouri_unavailable(tmp: Path) -> None:
    """Every Missouri page is still built, with the dated notice, and none
    of them states a level or "No all-clear recorded" (0024)."""
    s = snap(tmp)
    assert {w["state"] for w in s["waterbodies"]} == {"CA", "MO"}
    mo = [m for m in s["state_status"] if m["state"] == "MO"]
    assert mo and mo[0]["mode"] == "unavailable" and mo[0]["since"]
    site = tmp / "site"
    pages = sorted((site / "water").glob("mo-*/index.html"))
    assert pages
    for page in [*pages, site / "state" / "mo" / "index.html"]:
        text = text_of(page)
        assert "stopped reaching Lake Notice" in text, page
        assert "No all-clear recorded" not in text, page
        assert "recommends no advisory" not in text, page
    assert "mo-" in (site / "sitemap.xml").read_text()
    assert "/water/mo-" not in (site / "advisories" / "index.html").read_text()


def assert_missouri_present(tmp: Path) -> None:
    s = snap(tmp)
    assert {w["state"] for w in s["waterbodies"]} == {"CA", "MO"}
    assert (tmp / "site" / "state" / "mo" / "index.html").exists()
    assert "Missouri" in text_of(tmp / "site" / "index.html")


# -- the layer's answer -----------------------------------------------------


@pytest.mark.parametrize(
    ("body", "match"),
    [
        (b"<html>Not found</html>", "not JSON"),
        (b"[]", "not a JSON object"),
        (b'{"error": {"code": 404, "message": "Service not found"}}', "error"),
        (layer(features=[]), "0 rows"),
        (layer(features=None), "0 rows"),
        (layer(fields=[{"name": "objectid"}, {"name": "WBName"}]), "fields"),
        (layer(fields=None), "fields"),
    ],
)
def test_a_gone_changed_or_empty_layer_is_unavailable(body: bytes, match: str) -> None:
    with pytest.raises(missouri.LayerUnavailable, match=match):
        missouri.normalize(body, RUN)


def test_a_layer_with_no_placeable_case_is_unavailable() -> None:
    data = json.loads(MO_POINTS.read_bytes())
    for f in data["features"]:
        f["attributes"]["HABODat"] = None
    with pytest.raises(missouri.LayerUnavailable, match="no case"):
        missouri.normalize(json.dumps(data).encode(), RUN)


def test_the_real_layer_is_not_unavailable() -> None:
    # Negative control: the shape checks pass the real answer.
    assert missouri.normalize(MO_POINTS.read_bytes(), RUN).rows_read == 278


@respx.mock
@pytest.mark.parametrize("code", [404, 410])
def test_a_retired_endpoint_is_unavailable(code: int) -> None:
    respx.get("https://gis.dnr.mo.gov/robots.txt").mock(
        return_value=httpx.Response(404)
    )
    respx.get(missouri.QUERY_URL).mock(return_value=httpx.Response(code))
    with fetch.make_client() as client, pytest.raises(missouri.LayerUnavailable):
        missouri.fetch_cases(client)


@respx.mock
def test_a_server_error_is_a_passing_failure_not_a_retirement() -> None:
    respx.get("https://gis.dnr.mo.gov/robots.txt").mock(
        return_value=httpx.Response(404)
    )
    respx.get(missouri.QUERY_URL).mock(return_value=httpx.Response(503))
    with fetch.make_client() as client, pytest.raises(fetch.FetchError) as caught:
        missouri.fetch_cases(client)
    assert not isinstance(caught.value, missouri.LayerUnavailable)


# -- the run and the site ---------------------------------------------------


def test_good_layer_shows_missouri(tmp_path: Path) -> None:
    # Negative control for the hidden builds below: the same build with the
    # real answer shows Missouri.
    assert_missouri_present(build(tmp_path, "--mo-fixture", str(MO_POINTS)))


@pytest.mark.parametrize(
    "body",
    [
        b'{"error": {"code": 404, "message": "Service not found"}}',
        layer(features=[]),
        layer(fields=[{"name": "objectid"}]),
    ],
)
def test_a_changed_layer_with_no_history_shows_no_missouri(
    tmp_path: Path, body: bytes, capsys: pytest.CaptureFixture[str]
) -> None:
    # Nothing was ever read, so there is nothing to show: no Missouri page.
    bad = tmp_path / "mo.json"
    bad.write_bytes(body)
    assert_missouri_absent(build(tmp_path, "--mo-fixture", str(bad)))
    captured = capsys.readouterr()
    assert "Missouri data unavailable" in captured.out + captured.err


def test_a_changed_layer_turns_missouri_unavailable_and_keeps_california(
    tmp_path: Path,
) -> None:
    # Yesterday's good read is in history; today the layer changed shape.
    # Missouri's last records are not shown as current, and stay in history.
    build(tmp_path, "--mo-fixture", str(MO_POINTS), run_today="2026-10-11")
    bad = tmp_path / "mo.json"
    bad.write_bytes(layer(fields=[{"name": "objectid"}]))
    assert_missouri_unavailable(build(tmp_path, "--mo-fixture", str(bad)))
    kept = hist.load(tmp_path / "h.json")
    assert any(e.record.source == MO_DNR_HAB.id for e in kept.entries.values())
    assert kept.outages[MO_DNR_HAB.id]["since"] == "2026-10-12"
    assert {w["state"] for w in snap(tmp_path)["waterbodies"]} >= {"CA"}


def namespace() -> argparse.Namespace:
    return argparse.Namespace(
        mo_fixture=None, mo_viewer_fixture=None, fixture_page=None
    )


def good_history(fetched_on: str) -> hist.History:
    normalized = missouri.normalize(MO_POINTS.read_bytes(), RUN)
    return hist.merge(
        hist.empty(),
        normalized.records,
        run_date=RUN,
        file_info={
            "source": MO_DNR_HAB.id, "url": MO_DNR_HAB.dataset_url,
            "file_name": "layer", "file_date": fetched_on,
            "fetched_at": f"{fetched_on}T14:00:00Z", "rows_read": 278,
            "quarantined": 0, "quarantined_by_reason": {},
        },
    )  # fmt: skip


@respx.mock
@pytest.mark.parametrize("code", [404, 410])
def test_a_retired_live_endpoint_makes_missouri_unavailable_at_once(code: int) -> None:
    respx.get("https://gis.dnr.mo.gov/robots.txt").mock(
        return_value=httpx.Response(404)
    )
    respx.get(missouri.QUERY_URL).mock(return_value=httpx.Response(code))
    now = dt.datetime(2026, 10, 12, 14, tzinfo=dt.UTC)
    history = good_history("2026-10-11")  # read yesterday, so recent
    _, _, mode = cli._missouri(namespace(), history, RUN, now)
    assert mode is not None and mode.mode == "unavailable"
    assert mode.reason is not None and mode.reason.startswith("gone:")


@respx.mock
@pytest.mark.parametrize(
    ("last_read", "expected"),
    [("2026-10-11", "stale_dated"), ("2026-10-09", "unavailable")],
)
def test_a_passing_failure_shows_missouri_only_while_its_read_is_recent(
    last_read: str, expected: str
) -> None:
    respx.get("https://gis.dnr.mo.gov/robots.txt").mock(
        return_value=httpx.Response(404)
    )
    respx.get(missouri.QUERY_URL).mock(return_value=httpx.Response(503))
    now = dt.datetime(2026, 10, 12, 14, tzinfo=dt.UTC)
    _, _, result = cli._missouri(namespace(), good_history(last_read), RUN, now)
    assert result is not None and result.mode == expected


@respx.mock
def test_a_network_error_is_a_passing_failure() -> None:
    respx.get("https://gis.dnr.mo.gov/robots.txt").mock(
        return_value=httpx.Response(404)
    )
    respx.get(missouri.QUERY_URL).mock(side_effect=httpx.ConnectTimeout("timed out"))
    now = dt.datetime(2026, 10, 12, 14, tzinfo=dt.UTC)
    _, _, mode = cli._missouri(namespace(), hist.empty(), RUN, now)
    assert mode is None  # no good read on record at all: nothing to show


# -- the department's caveat ------------------------------------------------


def test_missouri_pages_quote_the_departments_caveat_with_its_source(
    tmp_path: Path,
) -> None:
    built = build(tmp_path, "--mo-fixture", str(MO_POINTS))
    site = built / "site"
    mo_pages = sorted((site / "water").glob("mo-*/index.html"))
    assert mo_pages
    for page in [
        *mo_pages,
        site / "state" / "mo" / "index.html",
        site / "about" / "index.html",
    ]:
        assert MO_MAP_CAVEAT in text_of(page), page
        assert f'href="{MO_MAP_CAVEAT_URL}"' in page.read_text(encoding="utf-8"), page
    ca = site / "water" / "ca-alameda-lake-alpha" / "index.html"
    assert MO_MAP_CAVEAT not in text_of(ca)
