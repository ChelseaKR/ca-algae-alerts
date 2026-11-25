"""Missouri water pages under the sitemap staging rule (DECISIONS 0016, 0040).

The site tests read California-only builds, so the rule had no test on a
build with Missouri in it. This one builds California and Missouri from the
fixtures and checks the rule there, then the three Chesterfield waters by
name: the two with an advisory inside the window are indexable, and the park
lake, whose one record carries no level the state has classified, stays out.
Table Rock Lake, Briars Pond and Hagen Lake, the Missouri pages the search
read of 2026-11-12 names (0041), are checked the same way.
"""

from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any

import pytest
from paths import CYAN_CACHE, MO_POINTS, PAGE, TRAPS
from test_site import lede_of, snapshot_of, staging_problems, staging_problems_inputs

from caalgae import cli, site, wording

_ROBOTS = re.compile(r'<meta name="robots" content="([^"]*)"')
_CANONICAL = re.compile(r'<link rel="canonical" href="([^"]*)"')

# Indexable: one "Advisory (advise)" record each, posted in July 2026.
CHESTERFIELD_INDEXED = [
    "mo-lake-chesterfield-and-tributary",
    "mo-harbors-at-lake-chesterfield",
]
# Held back: one record, "Dissipated (dissap)", Aug 17, 2024.
CHESTERFIELD_HELD = "mo-chesterfield-central-park-lake"
# The Missouri waters the 2026-11-12 search read names as getting
# impressions (DECISIONS 0041): each has an advisory inside the window.
SEARCH_READ_NAMED = ["mo-table-rock-lake", "mo-briars-pond", "mo-hagen-lake"]


def build_both(tmp: Path) -> Path:
    assert cli.main([
        "--fixture-page", str(PAGE), "--fixture-csv", str(TRAPS), "--run-today", "2026-10-12",
        "--history", str(tmp / "h.json"), "--site-out", str(tmp / "site"),
        "--mo-fixture", str(MO_POINTS), "--cyan-cache", str(CYAN_CACHE),
        "--ny-history", "off",
    ]) == 0  # fmt: skip
    return tmp / "site"


@pytest.fixture(scope="module")
def both(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build_both(tmp_path_factory.mktemp("both"))


def water_of(root: Path, wid: str) -> dict[str, Any]:
    found: dict[str, Any] = next(
        w for w in snapshot_of(root)["waterbodies"] if w["id"] == wid
    )
    return found


def head_of(root: Path, wid: str) -> tuple[str | None, str | None, bool]:
    """A water page's robots tag, its canonical, and whether the sitemap
    lists it."""
    raw = (root / "water" / wid / "index.html").read_text(encoding="utf-8")
    robots, canonical = _ROBOTS.search(raw), _CANONICAL.search(raw)
    url = f"{site.DEFAULT_BASE_URL}water/{wid}/"
    locs = re.findall(r"<loc>([^<]+)</loc>", (root / "sitemap.xml").read_text())
    return (
        robots.group(1) if robots else None,
        html.unescape(canonical.group(1)) if canonical else None,
        url in locs,
    )


def test_missouri_pages_follow_the_staging_rule(both: Path) -> None:
    keep, out = staging_problems_inputs(both)
    # The build exercises both sides of the rule with Missouri waters.
    assert any(wid.startswith("mo-") for wid in keep)
    assert any(wid.startswith("mo-") for wid in out)
    assert staging_problems(both) == []


@pytest.mark.parametrize("wid", [*CHESTERFIELD_INDEXED, *SEARCH_READ_NAMED])
def test_missouri_lakes_with_an_advisory_in_the_window_are_indexable(
    both: Path, wid: str
) -> None:
    water = water_of(both, wid)
    assert water["status"]["kind"] == "advisory"
    robots, canonical, in_sitemap = head_of(both, wid)
    assert robots is None
    assert canonical == f"{site.DEFAULT_BASE_URL}water/{wid}/"
    assert in_sitemap


def test_chesterfield_park_lake_with_no_classified_level_stays_out(
    both: Path,
) -> None:
    water = water_of(both, CHESTERFIELD_HELD)
    # Thin by the rule: under the record floor, and nothing in it is an
    # advisory, so the page's only status line is "no advisory level".
    assert len(water["records"]) < site.INDEX_MIN_RECORDS
    assert water["status"]["kind"] != "advisory"
    assert water["status"].get("last_advisory") is None
    assert head_of(both, CHESTERFIELD_HELD) == ("noindex,follow", None, False)
    # Held back, not hidden: the page is built, says what the record cannot
    # show, and the state page still links it.
    page = both / "water" / CHESTERFIELD_HELD / "index.html"
    assert wording.NOT_A_FINDING in lede_of(page)
    state_page = (both / "state" / "mo" / "index.html").read_text(encoding="utf-8")
    assert f'water/{CHESTERFIELD_HELD}/"' in state_page


def test_only_the_record_floor_holds_the_park_lake_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Negative control: with the floor at one record the same page is
    # indexable, so the checks above can fail and name what would flip them.
    monkeypatch.setattr(site, "INDEX_MIN_RECORDS", 1)
    root = build_both(tmp_path)
    robots, canonical, in_sitemap = head_of(root, CHESTERFIELD_HELD)
    assert robots is None
    assert canonical == f"{site.DEFAULT_BASE_URL}water/{CHESTERFIELD_HELD}/"
    assert in_sitemap
