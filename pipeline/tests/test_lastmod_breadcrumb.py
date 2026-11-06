"""Sitemap lastmod comes from the data a page renders, and a water page's
breadcrumb names its county. Each checker has a negative control that first
asserts the sabotage changed the output, then asserts the checker fails."""

from __future__ import annotations

import copy
import datetime as dt
import json
import re
from pathlib import Path
from typing import Any

import pytest
from paths import PAGE, SAMPLE, TRAPS

from caalgae import cli, site, where_to_check

_LD = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)
_NAV = re.compile(r'<nav aria-label="Breadcrumb".*?</nav>', re.S)
_LINK = re.compile(r'<a href="([^"]*)"[^>]*>(.*?)</a>', re.S)
_ENTRY = re.compile(r"<url><loc>([^<]+)</loc>(?:<lastmod>([^<]+)</lastmod>)?</url>")
_STATIC = ("about/", "privacy/", "support/", "terms/")


def found(match: re.Match[str] | None) -> re.Match[str]:
    assert match is not None
    return match


def build(tmp_path: Path, csv: Path, tag: str = "a") -> Path:
    out = tmp_path / f"site-{tag}"
    assert (
        cli.main(
            [
                "--fixture-page", str(PAGE),
                "--fixture-csv", str(csv),
                "--run-today", "2026-10-12",
                "--history", str(tmp_path / f"history-{tag}.json"),
                "--site-out", str(out),
                # lastmods here come from the snapshot's records; New York's
                # come from its own cache (test_newyork.py).
                "--ny-history", "off",
            ]
        )
        == 0
    )  # fmt: skip
    return out


@pytest.fixture(scope="module")
def traps(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build(tmp_path_factory.mktemp("lm-traps"), TRAPS)


@pytest.fixture(scope="module")
def sample(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build(tmp_path_factory.mktemp("lm-sample"), SAMPLE)


def snap_of(root: Path) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads((root / "snapshot" / "v1.json").read_text())
    return loaded


def entries(root: Path) -> dict[str, str | None]:
    return dict(_ENTRY.findall((root / "sitemap.xml").read_text()))


def newest_record(water: dict[str, Any]) -> str:
    return max(r["date"] for r in water["records"])


# -- lastmod --------------------------------------------------------------


def expected_lastmods(snap: dict[str, Any]) -> dict[str, str | None]:
    """Each URL's lastmod as the records say it should be. Written
    independently of site.py: it works from the records only."""
    run = snap["run_date"]
    base = site.DEFAULT_BASE_URL
    waters = {w["id"]: w for w in snap["waterbodies"]}
    dates = {i: newest_record(w) for i, w in waters.items() if newest_record(w) <= run}

    def newest(ids: list[str]) -> str | None:
        return max((dates[i] for i in ids if i in dates), default=None)

    expected: dict[str, str | None] = {}
    for wid in waters:
        expected[f"{base}water/{wid}/"] = dates.get(wid)
    counties: dict[str, list[str]] = {}
    states: dict[str, list[str]] = {}
    for wid, w in waters.items():
        for c in w["counties"]:
            counties.setdefault(site.slugify(c), []).append(wid)
        states.setdefault(w["state"].lower(), []).append(wid)
    for slug, ids in counties.items():
        expected[f"{base}county/{slug}/"] = newest(ids)
    for st, ids in states.items():
        expected[f"{base}state/{st}/"] = newest(ids)
    everything = newest(list(waters))
    for rel in ("", "advisories/", "dogs/"):
        expected[base + rel] = everything
    expected[f"{base}county/"] = newest([i for ids in counties.values() for i in ids])
    for rel in _STATIC:
        expected[base + rel] = None
    # A fixed fact about the page itself (its newest read date), not a record date.
    expected[base + "where-to-check/"] = where_to_check.AS_OF.isoformat()
    return expected


def lastmod_problems(root: Path) -> list[str]:
    """Disagreements between the sitemap and the dates the snapshot renders."""
    snap = snap_of(root)
    run = snap["run_date"]
    expected = expected_lastmods(snap)
    problems = []
    for loc, lastmod in entries(root).items():
        if loc not in expected:
            problems.append(f"{loc}: not a known page")
        elif (lastmod or None) != expected[loc]:
            problems.append(f"{loc}: lastmod {lastmod!r}, expected {expected[loc]!r}")
        if lastmod and lastmod > run and not loc.endswith("/where-to-check/"):
            problems.append(f"{loc}: lastmod {lastmod} is after run_date {run}")
    return problems


def test_lastmod_follows_the_rendered_data(sample: Path, traps: Path) -> None:
    for root in (sample, traps):
        assert lastmod_problems(root) == []


def test_lastmod_varies_and_static_pages_have_none(sample: Path) -> None:
    got = entries(sample)
    values = {v for v in got.values() if v}
    assert len(values) > 1, "every URL shares one lastmod"
    for rel in _STATIC:
        assert got[site.DEFAULT_BASE_URL + rel] in (None, "")
    assert "<lastmod></lastmod>" not in (sample / "sitemap.xml").read_text()


def test_lastmod_is_a_record_date_not_the_run_date(sample: Path) -> None:
    snap = snap_of(sample)
    record_dates = {r["date"] for w in snap["waterbodies"] for r in w["records"]}
    for loc, lastmod in entries(sample).items():
        if "/water/" in loc:
            assert lastmod in record_dates


def test_two_builds_of_one_snapshot_are_byte_identical(
    sample: Path, tmp_path: Path
) -> None:
    again = tmp_path / "again"
    site.build_site(snap_of(sample), again)
    assert (again / "sitemap.xml").read_bytes() == (sample / "sitemap.xml").read_bytes()


def test_lastmod_never_reads_the_clock(
    sample: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Frozen(dt.date):
        @classmethod
        def today(cls) -> Frozen:  # pragma: no cover - must not be called
            raise AssertionError("the sitemap read the wall clock")

    monkeypatch.setattr(site.dt, "date", Frozen)
    out = tmp_path / "frozen"
    site.build_site(snap_of(sample), out)
    assert (out / "sitemap.xml").read_bytes() == (sample / "sitemap.xml").read_bytes()


def test_future_record_gets_no_lastmod_and_moves_no_aggregate(
    sample: Path, tmp_path: Path
) -> None:
    snap = copy.deepcopy(snap_of(sample))
    before = entries(sample)
    victim = next(
        w
        for w in snap["waterbodies"]
        if f"{site.DEFAULT_BASE_URL}water/{w['id']}/" in before
    )
    victim["records"][0]["date"] = "2027-03-01"
    out = tmp_path / "future"
    site.build_site(snap, out)
    after = entries(out)
    loc = f"{site.DEFAULT_BASE_URL}water/{victim['id']}/"
    assert loc in after and not after[loc]
    assert before[loc]
    # Every record-derived lastmod stays within run_date; the where-to-check
    # page carries its own fixed data date instead.
    assert all(
        not v or v <= snap["run_date"]
        for k, v in after.items()
        if not k.endswith("/where-to-check/")
    )
    assert max(v for v in after.values() if v) <= max(v for v in before.values() if v)
    assert lastmod_problems_for(out, snap) == []


def lastmod_problems_for(root: Path, snap: dict[str, Any]) -> list[str]:
    (root / "snapshot" / "v1.json").write_text(json.dumps(snap), encoding="utf-8")
    return lastmod_problems(root)


def test_negative_control_build_date_lastmod(sample: Path, tmp_path: Path) -> None:
    bad = tmp_path / "bad"
    bad.mkdir()
    (bad / "snapshot").mkdir()
    (bad / "snapshot" / "v1.json").write_text((sample / "snapshot/v1.json").read_text())
    run = snap_of(sample)["run_date"]
    original = (sample / "sitemap.xml").read_text()
    sabotaged = re.sub(
        r"<lastmod>[^<]+</lastmod>", f"<lastmod>{run}</lastmod>", original
    )
    sabotaged = sabotaged.replace(
        "</loc></url>", f"</loc><lastmod>{run}</lastmod></url>"
    )
    assert sabotaged != original  # the sabotage applied
    assert set(_ENTRY.findall(sabotaged)) != set(_ENTRY.findall(original))
    (bad / "sitemap.xml").write_text(sabotaged)
    problems = lastmod_problems(bad)
    assert problems
    assert any("expected" in p for p in problems)


def test_negative_control_future_lastmod(sample: Path, tmp_path: Path) -> None:
    bad = tmp_path / "bad-future"
    bad.mkdir()
    (bad / "snapshot").mkdir()
    (bad / "snapshot" / "v1.json").write_text((sample / "snapshot/v1.json").read_text())
    original = (sample / "sitemap.xml").read_text()
    sabotaged = re.sub(
        r"<lastmod>[^<]+</lastmod>", "<lastmod>2099-01-01</lastmod>", original, count=1
    )
    assert sabotaged != original
    assert "2099" in sabotaged
    (bad / "sitemap.xml").write_text(sabotaged)
    assert any("after run_date" in p for p in lastmod_problems(bad))


# -- breadcrumb -----------------------------------------------------------


def visible_trail(page: Path) -> list[tuple[str, str]]:
    nav = _NAV.search(page.read_text(encoding="utf-8"))
    assert nav, f"{page}: no visible breadcrumb"
    return [
        (re.sub(r"<[^>]+>", "", n).strip(), h) for h, n in _LINK.findall(nav.group(0))
    ]


def ld_trail(page: Path) -> list[tuple[str, str]]:
    raw = page.read_text(encoding="utf-8")
    data = json.loads(found(_LD.search(raw)).group(1))
    nodes = data.get("@graph", [data])
    crumbs = next(n for n in nodes if n["@type"] == "BreadcrumbList")
    items = sorted(crumbs["itemListElement"], key=lambda i: i["position"])
    assert [i["position"] for i in items] == list(range(1, len(items) + 1))
    return [(i["name"], i["item"]) for i in items]


def breadcrumb_problems(root: Path) -> list[str]:
    base = site.DEFAULT_BASE_URL
    problems = []
    for water in snap_of(root)["waterbodies"]:
        page = root / "water" / water["id"] / "index.html"
        visible, ld = visible_trail(page), ld_trail(page)
        if visible != ld:
            problems.append(f"{water['id']}: visible {visible} != JSON-LD {ld}")
        names = [n for n, _ in visible]
        if water["counties"]:
            county = water["counties"][0]
            want = [
                ("Home", base),
                (f"{county} County", f"{base}county/{site.slugify(county)}/"),
                (water["name"], f"{base}water/{water['id']}/"),
            ]
            if visible != want:
                problems.append(f"{water['id']}: trail {visible} != {want}")
        elif names != ["Home", water["name"]]:
            problems.append(f"{water['id']}: no-county trail changed: {names}")
        for _, url in visible:
            rel = url[len(base) :] if url.startswith(base) else None
            if rel is None or not (root / rel / "index.html").exists():
                problems.append(f"{water['id']}: crumb links to a missing page {url}")
    return problems


def test_water_breadcrumbs_name_the_county(sample: Path, traps: Path) -> None:
    for root in (sample, traps):
        assert breadcrumb_problems(root) == []
        snap = snap_of(root)
        assert any(w["counties"] for w in snap["waterbodies"])


def test_waters_without_a_county_keep_the_short_trail(
    sample: Path, traps: Path
) -> None:
    seen = 0
    for root in (sample, traps):
        for w in snap_of(root)["waterbodies"]:
            if not w["counties"]:
                seen += 1
                page = root / "water" / w["id"] / "index.html"
                assert [n for n, _ in visible_trail(page)] == ["Home", w["name"]]
    assert seen, "fixtures carry no water without a county"


def test_404_and_noindex_pages_keep_their_rules(sample: Path) -> None:
    assert "Breadcrumb" not in (sample / "404.html").read_text()
    assert 'name="robots" content="noindex"' in (sample / "404.html").read_text()
    staged = 0
    for w in snap_of(sample)["waterbodies"]:
        raw = (sample / "water" / w["id"] / "index.html").read_text()
        if 'content="noindex,follow"' in raw:
            staged += 1
            assert 'rel="canonical"' not in raw
            assert visible_trail(sample / "water" / w["id"] / "index.html")
    assert staged


def _copy_water_page(sample: Path, tmp_path: Path) -> tuple[Path, str]:
    snap = snap_of(sample)
    water = next(w for w in snap["waterbodies"] if w["counties"])
    root = tmp_path / "bc"
    (root / "snapshot").mkdir(parents=True)
    (root / "snapshot" / "v1.json").write_text(
        json.dumps({**snap, "waterbodies": [water]})
    )
    page = root / "water" / water["id"] / "index.html"
    page.parent.mkdir(parents=True)
    page.write_text((sample / "water" / water["id"] / "index.html").read_text())
    county = site.slugify(water["counties"][0])
    target = root / "county" / county
    target.mkdir(parents=True)
    (target / "index.html").write_text("x")
    for rel in ("",):
        (root / rel).mkdir(exist_ok=True)
        (root / rel / "index.html").write_text("x")
    return page, county


def test_negative_control_visible_disagrees_with_json_ld(
    sample: Path, tmp_path: Path
) -> None:
    page, _ = _copy_water_page(sample, tmp_path)
    root = page.parents[2]
    assert breadcrumb_problems(root) == []
    raw = page.read_text()
    nav = found(_NAV.search(raw)).group(0)
    sabotaged = raw.replace(
        nav, re.sub(r"<li>.*?</li>\s*", "", nav, count=1, flags=re.S)
    )
    assert sabotaged != raw
    assert len(visible_trail_text(sabotaged)) < len(visible_trail_text(raw))
    page.write_text(sabotaged)
    assert any("JSON-LD" in p for p in breadcrumb_problems(root))


def visible_trail_text(raw: str) -> list[str]:
    return _LINK.findall(found(_NAV.search(raw)).group(0))


def test_negative_control_link_to_a_missing_county_page(
    sample: Path, tmp_path: Path
) -> None:
    page, county = _copy_water_page(sample, tmp_path)
    root = page.parents[2]
    assert breadcrumb_problems(root) == []
    (root / "county" / county / "index.html").unlink()
    assert not (root / "county" / county / "index.html").exists()
    assert any("missing page" in p for p in breadcrumb_problems(root))
