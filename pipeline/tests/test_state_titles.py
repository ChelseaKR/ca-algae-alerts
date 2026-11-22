"""The home and /advisories/ titles name every state whose data is live in
the build, and only those (DECISIONS 0032). With two states listed, the
/advisories/ title counts the waters and its description carries the
states' data date (0032, 2026-11-15). Water page titles are not touched
here: they are under the dated-title read until about 2026-11-25."""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

import pytest
from paths import CYAN_CACHE, MO_POINTS, PAGE, TRAPS
from test_site import build

from caalgae import cli, site, wording

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
        "Toxic algae advisories: 2 California and Missouri waters"
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
    rows = re.findall(
        r'href="\.\./water/([a-z]{2})-', advisories.read_text(encoding="utf-8")
    )
    assert title_of(advisories) == (
        f"Toxic algae advisories: {len(rows)} California and Missouri waters"
    )


# The wording Chelsea approved on 2026-11-15 for the 2026-11-15 data.
APPROVED_TITLE = "Toxic algae advisories: 524 California and Missouri waters"
APPROVED_DESCRIPTION = (
    "477 California and 47 Missouri lakes and rivers whose latest state record "
    "is a toxic algae advisory, from the states' data dated Nov 13, 2026."
)
TODAY = [{"state": "CA"}] * 477 + [{"state": "MO"}] * 47
# Missouri's layer has no file date of its own, so its date is the run date.
TODAY_FILES: dict[str, str | None] = {"CA": "2026-11-13", "MO": "2026-11-15"}


def test_the_approved_wording_comes_from_the_counts_and_dates() -> None:
    assert site.advisories_title(TODAY) == APPROVED_TITLE
    assert site.advisories_description(TODAY, TODAY_FILES) == APPROVED_DESCRIPTION
    # The oldest listed state's date, whichever state it is.
    flipped = {"CA": "2026-11-15", "MO": "2026-11-13"}
    assert site.advisories_description(TODAY, flipped) == APPROVED_DESCRIPTION


def test_the_counted_forms_fit_any_realistic_count() -> None:
    big = [{"state": "CA"}] * 9998 + [{"state": "MO"}] * 1
    title = site.advisories_title(big)
    assert title == "Toxic algae advisories: 9999 California and Missouri waters"
    assert len(title) <= site.TITLE_MAX
    files = {"CA": "2026-09-30", "MO": "2026-09-30"}
    description = site.advisories_description(big, files)
    assert "from the states' data dated Sep 30, 2026." in description
    assert len(description) <= site.DESCRIPTION_MAX


def test_one_state_listed_keeps_the_earlier_wording() -> None:
    # Missouri live with no open advisory (or dropped): no count of zero, and
    # no "states'" for one state. The title and description are the ones the
    # page had before the counted form.
    ca = [{"state": "CA"}] * 477
    assert site.advisories_title(ca) == (
        "All California toxic algae advisories on file | Lake Notice"
    )
    assert site.advisories_description(ca, TODAY_FILES) == (
        "477 California lakes and rivers whose latest state record is a toxic "
        "algae advisory, with its level and date, including old ones with no "
        "recorded end."
    )
    mo = [{"state": "MO"}] * 47
    assert site.advisories_title(mo) == (
        "All Missouri toxic algae advisories on file | Lake Notice"
    )
    assert "dated" not in site.advisories_description(mo, TODAY_FILES)


def test_a_missing_file_date_keeps_the_earlier_description() -> None:
    for files in ({"CA": "2026-11-13", "MO": None}, {"CA": "2026-11-13"}, {}):
        description = site.advisories_description(TODAY, files)
        assert description.startswith("477 California and 47 Missouri lakes")
        assert "dated" not in description, files
    assert "dated" not in site.advisories_description(TODAY)
    # The title has no date, so it keeps its count.
    assert site.advisories_title(TODAY) == APPROVED_TITLE


def test_a_listed_water_from_an_unnamed_state_drops_the_count() -> None:
    # The count must be the table's length; a water no state name covers
    # would make it short, so the earlier wording stays.
    odd = [*TODAY, {"state": "NY"}]
    assert site.advisories_title(odd) == (
        "All California and Missouri toxic algae advisories on file"
    )
    assert "dated" not in site.advisories_description(odd, TODAY_FILES)


def test_built_description_carries_the_oldest_file_date(both: Path) -> None:
    snap = json.loads((both.parent / "s.json").read_text(encoding="utf-8"))
    dates = [
        f["file_date"]
        for f in snap["source_files"]
        if f["source"] in site.STATE_SOURCE.values()
    ]
    assert len(dates) == 2 and all(dates)
    description = description_of(both / "advisories" / "index.html")
    assert description.endswith(
        f"from the states' data dated {wording.date_label(min(dates))}."
    ), description


def test_advisories_title_follows_the_listed_waters_not_the_build() -> None:
    # Missouri live but with no open advisory: the list names California only.
    assert site.advisories_title([{"state": "CA"}]).startswith("All California toxic")


def test_water_titles_are_untouched(both: Path) -> None:
    # No water page title names a state it did not name before this change.
    for page in (both / "water").glob("*/index.html"):
        assert "California and Missouri" not in title_of(page), page
