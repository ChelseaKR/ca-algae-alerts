"""The publish guard refuses a deploy that silently drops a state's pages
(docs/DECISIONS.md 0024). Every refusal has a negative control, and every
sabotage asserts that it applied."""

from __future__ import annotations

import dataclasses
import json
import re
import shutil
from pathlib import Path

import httpx
import pytest
import respx
from paths import MO_POINTS, PAGE, TRAPS

from caalgae import cli, publish_guard, sources

BASE = "https://lakenotice.com/"


def build(tmp: Path, run_today: str, *extra: str) -> Path:
    assert cli.main([
        "--fixture-page", str(PAGE), "--fixture-csv", str(TRAPS),
        "--run-today", run_today, "--base-url", BASE,
        "--history", str(tmp / "h.json"), "--site-out", str(tmp / "site"),
        *extra,
    ]) == 0  # fmt: skip
    return tmp / "site"


def keep_live(site: Path, tmp: Path) -> Path:
    live = tmp / "live-sitemap.xml"
    shutil.copy(site / "sitemap.xml", live)
    return live


def guard(site: Path, live: Path, *extra: str) -> int:
    return publish_guard.main([
        "--site-dir", str(site), "--base-url", BASE,
        "--live-sitemap-file", str(live), *extra,
    ])  # fmt: skip


def mo_count(path: Path) -> int:
    return len(
        re.findall(
            r"<loc>https://lakenotice\.com/(?:water/mo-|state/mo/)", path.read_text()
        )
    )


@pytest.fixture
def live_site(tmp_path: Path) -> tuple[Path, Path]:
    site = build(tmp_path, "2026-10-12", "--mo-fixture", str(MO_POINTS))
    live = keep_live(site, tmp_path)
    assert mo_count(live) > 0
    return site, live


def test_an_unchanged_build_passes(live_site: tuple[Path, Path]) -> None:
    site, live = live_site
    assert guard(site, live) == 0


def _hidden_build(tmp: Path) -> Path:
    """A build with no Missouri at all: what the old "hide" did."""
    other = tmp / "hidden"
    other.mkdir()
    site = build(other, "2026-10-12")
    assert mo_count(site / "sitemap.xml") == 0  # the sabotage applied
    return site


def test_a_state_that_vanishes_is_refused(
    live_site: tuple[Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    out = tmp_path / "gh-output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    _, live = live_site
    site = _hidden_build(tmp_path)
    assert guard(site, live) == 1
    err = capsys.readouterr().err
    assert f"MO: {mo_count(live)} sitemap URLs live, 0 in this build" in err
    assert "reason=MO:" in out.read_text()


def test_the_owner_override_lets_a_named_state_drop(
    live_site: tuple[Path, Path], tmp_path: Path
) -> None:
    _, live = live_site
    site = _hidden_build(tmp_path)
    assert guard(site, live, "--allow", "MO") == 0
    assert guard(site, live, "--allow", "CA") == 1  # another state's override does not
    assert guard(site, live, "--allow", "mo; rm") == 2


def test_a_switched_off_source_may_drop(
    live_site: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, live = live_site
    site = _hidden_build(tmp_path)
    off = dataclasses.replace(sources.MO_DNR_HAB, enabled=False)
    monkeypatch.setitem(sources.SOURCES, off.id, off)
    assert guard(site, live) == 0


def _drop_from_sitemap(site: Path, fraction: float) -> int:
    path = site / "sitemap.xml"
    text = path.read_text()
    urls = re.findall(
        r"<url><loc>https://lakenotice\.com/water/mo-[^<]+</loc>.*?</url>", text
    )
    n = int(len(urls) * fraction)
    for url in urls[:n]:
        text = text.replace(url, "")
    path.write_text(text)
    return n


def test_more_than_a_fifth_dropped_is_refused_and_less_passes(
    live_site: tuple[Path, Path],
) -> None:
    site, live = live_site
    before = mo_count(live)
    original = (site / "sitemap.xml").read_text()
    dropped = _drop_from_sitemap(site, 0.10)
    assert 0 < dropped <= publish_guard.MAX_DROP_FRACTION * before
    assert guard(site, live) == 0
    (site / "sitemap.xml").write_text(original)
    dropped = _drop_from_sitemap(site, 0.30)
    assert dropped > publish_guard.MAX_DROP_FRACTION * before  # the sabotage applied
    assert guard(site, live) == 1


def test_an_unavailable_state_past_30_days_may_leave_the_sitemap_but_not_404(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "gh-output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    site = build(tmp_path, "2026-10-11", "--mo-fixture", str(MO_POINTS))
    live = keep_live(site, tmp_path)
    bad = tmp_path / "mo.json"
    bad.write_bytes(b'{"error": {"code": 404}}')
    build(tmp_path, "2026-10-12", "--mo-fixture", str(bad))
    assert guard(site, live) == 0  # day 0: still in the sitemap
    assert (
        "unavailable=Missouri data unavailable since 2026-10-12: changed:"
        in out.read_text()
    )
    build(tmp_path, "2026-11-11", "--mo-fixture", str(bad))
    assert mo_count(site / "sitemap.xml") == 0  # day 30: noindex on purpose
    assert guard(site, live) == 0
    # A page that stopped being built would answer 404: refused.
    listed = re.findall(
        r"https://lakenotice\.com/(water/mo-[^<]+)</loc>", live.read_text()
    )
    page = site / listed[0]
    assert (page / "index.html").is_file()
    shutil.rmtree(page)
    assert guard(site, live) == 1


def test_an_unavailable_state_inside_30_days_may_not_leave_the_sitemap(
    tmp_path: Path,
) -> None:
    site = build(tmp_path, "2026-10-11", "--mo-fixture", str(MO_POINTS))
    live = keep_live(site, tmp_path)
    bad = tmp_path / "mo.json"
    bad.write_bytes(b"[]")
    build(tmp_path, "2026-10-12", "--mo-fixture", str(bad))
    _drop_from_sitemap(site, 1.0)
    assert guard(site, live) == 1


def test_no_live_sitemap_means_nothing_to_protect(
    live_site: tuple[Path, Path], tmp_path: Path
) -> None:
    site, _ = live_site
    assert guard(site, tmp_path / "missing.xml") == 0


def test_state_of_reads_water_state_and_county_paths() -> None:
    assert publish_guard.state_of(BASE + "water/mo-truman-lake/", BASE) == "MO"
    assert publish_guard.state_of(BASE + "state/mo/", BASE) == "MO"
    assert publish_guard.state_of(BASE + "county/alameda/", BASE) == "CA"
    assert publish_guard.state_of(BASE + "water/ca-alameda-lake-alpha/", BASE) == "CA"
    assert publish_guard.state_of(BASE + "about/", BASE) is None


@respx.mock
def test_fetch_live_reads_the_sitemap_and_reports_a_missing_one() -> None:
    respx.get(BASE + "sitemap.xml").mock(
        return_value=httpx.Response(
            200,
            text="<urlset><url><loc>https://lakenotice.com/state/mo/</loc></url></urlset>",
        )
    )
    urls, problem = publish_guard.fetch_live(BASE)
    assert urls == {"https://lakenotice.com/state/mo/"} and problem is None
    respx.get("https://example.org/sitemap.xml").mock(return_value=httpx.Response(404))
    assert publish_guard.fetch_live("https://example.org/") == (
        None,
        "live sitemap answered HTTP 404",
    )
    respx.get("https://down.example/sitemap.xml").mock(
        side_effect=httpx.ConnectError("x")
    )
    assert publish_guard.fetch_live("https://down.example/")[0] is None
    assert publish_guard.fetch_live("http://lakenotice.com/")[0] is None


def test_the_snapshot_the_guard_reads_is_the_built_one(
    live_site: tuple[Path, Path],
) -> None:
    site, _ = live_site
    snap = json.loads((site / "snapshot" / "v1.json").read_text())
    assert {m["state"] for m in snap["state_status"]} == {"CA", "MO"}
