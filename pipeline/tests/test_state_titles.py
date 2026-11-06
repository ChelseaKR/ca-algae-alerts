"""The home and /advisories/ titles name every state whose data is live in
the build, and only those (DECISIONS 0032). Water page titles are not
touched here: they are under the dated-title read until about 2026-11-25."""

from __future__ import annotations

import html
import re
from pathlib import Path

import pytest
from paths import CYAN_CACHE, MO_POINTS, PAGE, TRAPS
from test_site import build

from caalgae import cli, site

_TITLE = re.compile(r"<title>(.*?)</title>", re.S)
_DESCRIPTION = re.compile(r'<meta name="description" content="([^"]*)"')


def title_of(page: Path) -> str:
    found = _TITLE.search(page.read_text(encoding="utf-8"))
    assert found
    return html.unescape(found.group(1)).strip()


def description_of(page: Path) -> str:
    found = _DESCRIPTION.search(page.read_text(encoding="utf-8"))
    assert found
    return html.unescape(found.group(1))


@pytest.fixture(scope="module")
def ca_only(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build(tmp_path_factory.mktemp("ca_only"))


@pytest.fixture(scope="module")
def both(tmp_path_factory: pytest.TempPathFactory) -> Path:
    tmp = tmp_path_factory.mktemp("both")
    assert cli.main([
        "--fixture-page", str(PAGE), "--fixture-csv", str(TRAPS), "--run-today", "2026-10-12",
        "--history", str(tmp / "h.json"), "--site-out", str(tmp / "site"),
        "--snapshot-out", str(tmp / "s.json"),
        "--mo-fixture", str(MO_POINTS), "--cyan-cache", str(CYAN_CACHE),
    ]) == 0  # fmt: skip
    return tmp / "site"


def test_state_list_follows_state_names_order() -> None:
    assert site.state_list([]) == ""
    assert site.state_list(["CA"]) == "California"
    assert site.state_list(["MO", "CA"]) == "California and Missouri"
    assert site.state_list(["MO"]) == "Missouri"


def test_california_only_keeps_the_launch_titles() -> None:
    assert site.home_title(["CA"]) == (
        "California lake toxic algae advisories by date | Lake Notice"
    )
    assert site.advisories_title([{"state": "CA"}]) == (
        "All California toxic algae advisories on file | Lake Notice"
    )
    assert "since 2016" in site.home_description(["CA"])


def test_missouri_is_named_while_its_data_is_live() -> None:
    assert site.home_title(["CA", "MO"]) == (
        "California and Missouri toxic algae advisories by date"
    )
    assert site.advisories_title([{"state": "CA"}, {"state": "MO"}]) == (
        "All California and Missouri toxic algae advisories on file"
    )
    description = site.home_description(["CA", "MO"])
    assert "California and Missouri lakes and rivers" in description
    # 2016 is California's span; Missouri's records do not reach back to it.
    assert "2016" not in description


def test_every_candidate_fits() -> None:
    for states in (["CA"], ["CA", "MO"], ["MO"], []):
        assert len(site.home_title(states)) <= site.TITLE_MAX
        assert len(site.home_description(states)) <= site.DESCRIPTION_MAX
        waters = [{"state": s} for s in states]
        assert len(site.advisories_title(waters)) <= site.TITLE_MAX


def test_built_titles_without_missouri(ca_only: Path) -> None:
    assert title_of(ca_only / "index.html") == (
        "California lake toxic algae advisories by date | Lake Notice"
    )
    assert title_of(ca_only / "advisories" / "index.html") == (
        "All California toxic algae advisories on file | Lake Notice"
    )
    assert "Missouri" not in description_of(ca_only / "index.html")


def test_built_titles_with_missouri(both: Path) -> None:
    assert title_of(both / "index.html") == (
        "California and Missouri toxic algae advisories by date"
    )
    assert "California and Missouri" in description_of(both / "index.html")
    advisories = both / "advisories" / "index.html"
    # The fixture's Missouri points include an open advisory, so the list
    # names Missouri; its description already counts Missouri's rows.
    assert "Missouri" in description_of(advisories)
    assert title_of(advisories) == (
        "All California and Missouri toxic algae advisories on file"
    )


def test_advisories_title_follows_the_listed_waters_not_the_build() -> None:
    # Missouri live but with no open advisory: the list names California only.
    assert site.advisories_title([{"state": "CA"}]).startswith("All California toxic")


def test_water_titles_are_untouched(both: Path) -> None:
    # No water page title names a state it did not name before this change.
    for page in (both / "water").glob("*/index.html"):
        assert "California and Missouri" not in title_of(page), page
