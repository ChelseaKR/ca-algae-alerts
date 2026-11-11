"""A state's "data unavailable since <date>" mode (docs/DECISIONS.md 0024).

Missouri's layer can stop being current in four ways: gone, changed, frozen
(still answering, no longer updated) or superseded (the department's own
viewer moved to another layer). Each one keeps every Missouri page up (HTTP
200), with a dated notice, no level headline, no "No all-clear recorded"
line, history labeled as read before the date, and a link to the
department's map; after 30 days the pages carry noindex and leave the
sitemap. Every detector has a negative control on the real answer, and every
sabotage asserts that it applied.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from paths import FIXTURES, MO_POINTS, PAGE, TRAPS
from test_site import text_of

from caalgae import cli, fetch, missouri
from caalgae import history as hist
from caalgae.sources import MO_DNR_HAB, MO_MAP_CAVEAT_URL

VIEWER = FIXTURES / "mo-hab-viewer-data-2026-11-05.json"
RUN = dt.date(2026, 10, 12)


def build(tmp: Path, run_today: str, *extra: str) -> dict[str, Any]:
    assert cli.main([
        "--fixture-page", str(PAGE), "--fixture-csv", str(TRAPS),
        "--run-today", run_today,
        "--history", str(tmp / "h.json"), "--site-out", str(tmp / "site"),
        "--snapshot-out", str(tmp / "s.json"), *extra,
    ]) == 0  # fmt: skip
    loaded: dict[str, Any] = json.loads((tmp / "s.json").read_text())
    return loaded


def mo_mode(snap: dict[str, Any]) -> dict[str, Any]:
    return next(m for m in snap["state_status"] if m["state"] == "MO")


def write(tmp: Path, name: str, body: bytes) -> str:
    path = tmp / name
    path.write_bytes(body)
    return str(path)


def superseded_viewer() -> bytes:
    before = VIEWER.read_text(encoding="utf-8")
    after = before.replace(
        MO_DNR_HAB.dataset_url,
        "https://gis.dnr.mo.gov/arcgis/rest/services/wqm/HAB_PUBLIC/MapServer/0",
    )
    assert after != before  # the sabotage applied
    assert MO_DNR_HAB.dataset_url not in after
    return after.encode()


# -- the frozen detector ------------------------------------------------------


def _records_newest_on(day: dt.date) -> list[Any]:
    records = missouri.normalize(MO_POINTS.read_bytes(), RUN).records
    shift = max(r.date for r in records) - day
    moved = [dataclasses.replace(r, date=r.date - shift) for r in records]
    assert max(r.date for r in moved) == day  # the sabotage applied
    return moved


def test_the_season_is_may_15_to_october_15() -> None:
    assert missouri.in_season(dt.date(2027, 5, 15))
    assert missouri.in_season(dt.date(2027, 10, 15))
    assert not missouri.in_season(dt.date(2027, 5, 14))
    assert not missouri.in_season(dt.date(2027, 10, 16))


def test_in_season_a_layer_with_no_record_in_30_days_is_frozen() -> None:
    records = _records_newest_on(dt.date(2027, 6, 1))
    missouri.check_fresh(records, dt.date(2027, 7, 1))  # 30 days: still fresh
    with pytest.raises(missouri.LayerUnavailable, match="frozen") as caught:
        missouri.check_fresh(records, dt.date(2027, 7, 2))  # 31 days
    assert caught.value.kind == "frozen"


def test_out_of_season_the_same_layer_is_not_frozen() -> None:
    records = _records_newest_on(dt.date(2027, 9, 1))
    missouri.check_fresh(records, dt.date(2027, 11, 5))


def test_the_real_layer_is_fresh() -> None:
    # Negative control: the real 2026-10-12 answer, in season, passes.
    records = missouri.normalize(MO_POINTS.read_bytes(), RUN).records
    assert missouri.in_season(RUN)
    missouri.check_fresh(records, RUN)


# -- the superseded detector --------------------------------------------------


def test_the_real_viewer_still_reads_the_layer() -> None:
    # Negative control: the PROD viewer as read on 2026-11-05.
    assert missouri.viewer_references_layer(VIEWER.read_bytes())
    missouri.check_viewer(VIEWER.read_bytes())


def test_a_viewer_that_moved_to_another_layer_supersedes_it() -> None:
    with pytest.raises(missouri.LayerUnavailable, match="no longer reads") as caught:
        missouri.check_viewer(superseded_viewer())
    assert caught.value.kind == "superseded"


@pytest.mark.parametrize(
    "body",
    [b"<html>sign in</html>", b"[]", b'{"dataSources": {}}', b'{"error": {"code": 403}}',
     b'{"dataSources": {"a": {"url": "https://example.com/x"}}}'],
)  # fmt: skip
def test_an_unreadable_viewer_is_a_passing_failure_never_superseded(
    body: bytes,
) -> None:
    with pytest.raises(fetch.FetchError) as caught:
        missouri.check_viewer(body)
    assert not isinstance(caught.value, missouri.LayerUnavailable)


# -- the run and the site -----------------------------------------------------


def assert_unavailable_pages(site: Path, since: str) -> None:
    pages = sorted((site / "water").glob("mo-*/index.html"))
    assert pages
    for page in [*pages, site / "state" / "mo" / "index.html"]:
        html = page.read_text(encoding="utf-8")
        text = text_of(page)
        assert "stopped reaching Lake Notice on" in text, page
        assert since in text, page
        assert f'href="{MO_MAP_CAVEAT_URL}"' in html, page
        for banned in (
            "No all-clear recorded",
            "recommends no advisory",
            "last posted",
        ):
            assert banned not in text, (page, banned)
        # The State's required disclaimer stays with the data.
        assert "THE STATE OF MISSOURI MAKES NO" in text, page
    water = text_of(pages[0])
    assert "Records read before" in water
    assert "No current status" in water


def test_a_superseded_layer_keeps_missouri_pages_up_unavailable(tmp_path: Path) -> None:
    good = build(tmp_path, "2026-10-11", "--mo-fixture", str(MO_POINTS),
                 "--mo-viewer-fixture", str(VIEWER))  # fmt: skip
    assert mo_mode(good)["mode"] == "live"  # negative control
    mo_pages = sorted(
        p.parent.name for p in (tmp_path / "site/water").glob("mo-*/index.html")
    )
    snap = build(tmp_path, "2026-10-12", "--mo-fixture", str(MO_POINTS),
                 "--mo-viewer-fixture", write(tmp_path, "v.json", superseded_viewer()))  # fmt: skip
    mode = mo_mode(snap)
    assert mode["mode"] == "unavailable"
    assert mode["since"] == "2026-10-12"
    assert mode["reason"].startswith("superseded:")
    assert mode["map_url"] == MO_MAP_CAVEAT_URL
    site = tmp_path / "site"
    assert (
        sorted(p.parent.name for p in (site / "water").glob("mo-*/index.html"))
        == mo_pages
    )
    assert_unavailable_pages(site, "Oct 12, 2026")
    # Missouri's last records are not current advisories anywhere.
    assert "/mo-" not in (site / "advisories/index.html").read_text()
    assert "data unavailable since Oct 12, 2026" in text_of(site / "index.html")
    titles = [
        (site / "water" / p / "index.html").read_text().split("</title>")[0]
        for p in mo_pages
    ]
    assert all("since Oct 12, 2026" in t for t in titles), titles


def test_a_frozen_layer_turns_unavailable_through_the_run(tmp_path: Path) -> None:
    data = json.loads(MO_POINTS.read_bytes())
    build(tmp_path, "2026-10-11", "--mo-fixture", str(MO_POINTS))
    # The same layer, unchanged, read in July 2027: nothing newer than 2026.
    snap = build(
        tmp_path,
        "2027-07-01",
        "--mo-fixture",
        write(tmp_path, "mo.json", json.dumps(data).encode()),
    )
    assert mo_mode(snap)["mode"] == "unavailable"
    assert mo_mode(snap)["reason"].startswith("frozen:")


def test_a_partial_answer_turns_unavailable_and_california_still_publishes(
    tmp_path: Path,
) -> None:
    """Source-outage audit finding 8: a partial answer used to raise
    HistoryError and stop California too."""
    build(tmp_path, "2026-10-11", "--mo-fixture", str(MO_POINTS))
    data = json.loads(MO_POINTS.read_bytes())
    data["features"] = data["features"][-200:]
    assert len(data["features"]) >= missouri.MIN_ROWS  # passes the shape checks
    snap = build(
        tmp_path,
        "2026-10-12",
        "--mo-fixture",
        write(tmp_path, "mo.json", json.dumps(data).encode()),
    )
    assert mo_mode(snap)["mode"] == "unavailable"
    assert mo_mode(snap)["reason"].startswith("partial:")
    assert snap["run_date"] == "2026-10-12"
    assert any(w["state"] == "CA" for w in snap["waterbodies"])


def _sitemap_mo(tmp: Path) -> int:
    return (tmp / "site" / "sitemap.xml").read_text().count("/water/mo-")


def test_pages_stay_indexed_for_30_days_then_noindex_but_stay_built(
    tmp_path: Path,
) -> None:
    build(tmp_path, "2026-10-11", "--mo-fixture", str(MO_POINTS))
    indexed = _sitemap_mo(tmp_path)
    assert indexed > 0
    bad = write(tmp_path, "mo.json", b'{"error": {"code": 404}}')
    build(tmp_path, "2026-10-12", "--mo-fixture", bad)
    assert _sitemap_mo(tmp_path) == indexed  # day 0
    build(tmp_path, "2026-11-10", "--mo-fixture", bad)
    assert _sitemap_mo(tmp_path) == indexed  # day 29
    snap = build(tmp_path, "2026-11-11", "--mo-fixture", bad)
    assert mo_mode(snap)["since"] == "2026-10-12"  # kept across runs
    assert _sitemap_mo(tmp_path) == 0  # day 30
    site = tmp_path / "site"
    assert "/state/mo/" not in (site / "sitemap.xml").read_text()
    pages = sorted((site / "water").glob("mo-*/index.html"))
    assert pages
    for page in [*pages, site / "state" / "mo" / "index.html"]:
        assert 'name="robots" content="noindex,follow"' in page.read_text(), page
    assert_unavailable_pages(site, "Oct 12, 2026")


def test_a_good_read_clears_the_outage(tmp_path: Path) -> None:
    build(tmp_path, "2026-10-11", "--mo-fixture", str(MO_POINTS))
    build(tmp_path, "2026-10-12", "--mo-fixture", write(tmp_path, "mo.json", b"[]"))
    assert MO_DNR_HAB.id in hist.load(tmp_path / "h.json").outages
    snap = build(tmp_path, "2026-10-13", "--mo-fixture", str(MO_POINTS))
    assert mo_mode(snap)["mode"] == "live"
    assert mo_mode(snap)["since"] is None
    assert MO_DNR_HAB.id not in hist.load(tmp_path / "h.json").outages
    page = next((tmp_path / "site" / "water").glob("mo-*/index.html"))
    assert "stopped reaching" not in text_of(page)


def test_a_live_build_carries_no_outage_wording(tmp_path: Path) -> None:
    """Negative control for the page checks: a live Missouri build has the
    normal headline, so the assertions above can fail."""
    snap = build(tmp_path, "2026-10-12", "--mo-fixture", str(MO_POINTS))
    assert mo_mode(snap)["mode"] == "live"
    site = tmp_path / "site"
    texts = [text_of(p) for p in (site / "water").glob("mo-*/index.html")]
    assert not any("stopped reaching" in t for t in texts)
    assert any("No all-clear recorded" in t for t in texts)


def namespace() -> Any:
    return cli._parse_args([])


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


def _mock_live(viewer: httpx.Response) -> None:
    respx.get("https://gis.dnr.mo.gov/robots.txt").mock(
        return_value=httpx.Response(404)
    )
    respx.get(missouri.QUERY_URL).mock(
        return_value=httpx.Response(200, content=MO_POINTS.read_bytes())
    )
    respx.get("https://www.arcgis.com/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\n")
    )
    respx.get(missouri.VIEWER_DATA_URL).mock(return_value=viewer)


@respx.mock
def test_live_the_viewer_check_reads_the_prod_experience() -> None:
    _mock_live(httpx.Response(200, content=superseded_viewer()))
    now = dt.datetime(2026, 10, 12, 14, tzinfo=dt.UTC)
    _, _, mode = cli._missouri(namespace(), good_history("2026-10-11"), RUN, now)
    assert mode is not None and mode.mode == "unavailable"


@respx.mock
@pytest.mark.parametrize("status", [200, 500])
def test_live_a_good_or_failed_viewer_read_never_hides_missouri(status: int) -> None:
    body = VIEWER.read_bytes() if status == 200 else b"oops"
    _mock_live(httpx.Response(status, content=body))
    now = dt.datetime(2026, 10, 12, 14, tzinfo=dt.UTC)
    _, _, mode = cli._missouri(namespace(), good_history("2026-10-11"), RUN, now)
    assert mode is not None and mode.mode == "live"


@respx.mock
def test_a_passing_failure_during_an_outage_never_brings_old_data_back() -> None:
    respx.get("https://gis.dnr.mo.gov/robots.txt").mock(
        return_value=httpx.Response(404)
    )
    respx.get(missouri.QUERY_URL).mock(return_value=httpx.Response(503))
    history = dataclasses.replace(
        good_history("2026-10-11"),
        outages={MO_DNR_HAB.id: {"since": "2026-10-12", "reason": "gone: HTTP 404"}},
    )
    now = dt.datetime(2026, 10, 13, 14, tzinfo=dt.UTC)
    # The last good read is 2 days old, which alone would show it dated.
    assert cli._missouri_recent(history, dt.date(2026, 10, 13))
    _, _, mode = cli._missouri(namespace(), history, dt.date(2026, 10, 13), now)
    assert mode is not None and mode.mode == "unavailable"
    assert mode.since == dt.date(2026, 10, 12)


def test_history_round_trips_the_outage(tmp_path: Path) -> None:
    h = dataclasses.replace(
        hist.empty(), outages={MO_DNR_HAB.id: {"since": "2026-10-12", "reason": "x"}}
    )
    hist.save(h, tmp_path / "h.json")
    assert hist.load(tmp_path / "h.json").outages == h.outages
    hist.save(hist.empty(), tmp_path / "e.json")
    assert "outages" not in (tmp_path / "e.json").read_text()
