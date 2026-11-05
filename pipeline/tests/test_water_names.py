"""Display names (DECISIONS 0009, "Display names").

The cases are the state's own spellings from the 2026-11-04 snapshot, each
with the name the site should show. The ones that must not change are as
important as the fixes: Missouri's "CA" means a conservation area, "Lake
California" is a name, and "Unnamed pond" is a description, not a name.
"""

from __future__ import annotations

import copy
import html
import json
import re
from pathlib import Path
from typing import Any

import pytest
from paths import PAGE, TRAPS

from caalgae import cli, site, water_names

CHANGED = [
    # Casing: a proper name typed partly or wholly in lowercase.
    ("ca-calaveras-salt-spring-valley-reservoir", "salt spring valley reservoir",
     "CA", "Salt Spring Valley Reservoir"),
    ("ca-placer-combie-lake", "Combie lake", "CA", "Combie Lake"),
    ("ca-riverside-diamond-valley-lake", "Diamond valley lake", "CA",
     "Diamond Valley Lake"),
    ("ca-solano-lake-herman", "Lake herman", "CA", "Lake Herman"),
    ("ca-merced-volta-state-wildlife-area", "Volta State Wildlife area", "CA",
     "Volta State Wildlife Area"),
    ("mo-briars-pond", "Briars pond", "MO", "Briars Pond"),
    ("mo-crystal-pool", "crystal pool", "MO", "Crystal Pool"),
    ("mo-central-park-lake", "Central Park lake", "MO", "Central Park Lake"),
    ("mo-mike-s-creek", "Mike's creek", "MO", "Mike's Creek"),
    ("mo-pointe-royale-lower-lake", "Pointe Royale lower lake", "MO",
     "Pointe Royale Lower Lake"),
    ("mo-lac-michel-terre-du-lac", "Lac Michel terre du lac", "MO",
     "Lac Michel Terre du Lac"),
    ("mo-fort-zumwalt-park-pond-lake-whetsel",
     "Fort zumwalt park pond (Lake Whetsel)", "MO",
     "Fort Zumwalt Park Pond (Lake Whetsel)"),
    # A repeated word is the real name, so no word is dropped.
    ("mo-fee-fee-creek", "Fee fee creek", "MO", "Fee Fee Creek"),
    # A description only gets its first capital.
    ("mo-small-pond-in-golf-course-adj-to-cosmopolotin-park-columbia",
     "small pond in golf course adj to Cosmopolotin Park, Columbia", "MO",
     "Small pond in golf course adj to Cosmopolotin Park, Columbia"),
    # The water's own state as a suffix.
    ("ca-san-bernardino-big-bear-lake-ca", "Big bear lake ca", "CA",
     "Big Bear Lake"),
    ("mo-corby-pond-st-joseph-mo", "Corby Pond St. Joseph, MO", "MO",
     "Corby Pond St. Joseph"),
    ("mo-westside-park-lake-fenton-missouri",
     "Westside Park Lake - Fenton, Missouri", "MO", "Westside Park Lake - Fenton"),
    # Reviewed overrides.
    ("ca-san-diego-anthonys-fish-grotto", "Anthony\u2019s fish grotto", "CA",
     "Anthony\u2019s Fish Grotto"),
    ("mo-cameron-reservoir-no-1-century-lake",
     "Cameron reservoir no. 1 (Century Lake)", "MO",
     "Cameron Reservoir No. 1 (Century Lake)"),
    ("mo-james-river-christian-county", "James river Christian county", "MO",
     "James River, Christian County"),
]  # fmt: skip

UNCHANGED = [
    ("ca-tehama-lake-california", "Lake California", "CA"),
    ("mo-turtle-pond-at-caldwell-memorial-ca", "Turtle Pond at Caldwell Memorial CA",
     "MO"),
    ("mo-william-towell-lake-little-prairie-ca",
     "William Towell Lake - Little Prairie CA", "MO"),
    ("ca-sacramento-unnamed-pond", "Unnamed pond", "CA"),
    ("ca-san-diego-private-pond", "Private pond", "CA"),
    ("mo-neighborhood-detention-pond", "Neighborhood detention pond", "MO"),
    ("mo-plumbing-issue-in-my-apartment-complex",
     "Plumbing issue in my apartment complex", "MO"),
    ("mo-unknown-off-clark-trail", "Unknown - off Clark Trail", "MO"),
    ("mo-pierce-city-city-park-recreational-pond",
     "Pierce City City Park Recreational Pond", "MO"),
    ("mo-walden-pond-also-called-hermit-hollow-lake",
     "Walden Pond, also called Hermit Hollow Lake", "MO"),
    ("mo-queeny-park-back-pond-large-fishing-pond",
     "Queeny Park, back pond (large fishing pond)", "MO"),
    ("ca-san-diego-san-luis-rey-river-estuary", "San Luis Rey River estuary", "CA"),
    ("mo-lake-of-the-ozarks-flw-rec-area", "Lake of the Ozarks - FLW rec Area", "MO"),
    ("ca-x-lake-of-the-woods", "Lake of the Woods", "CA"),
    ("ca-x-castaic-lake", "Castaic Lake", "CA"),
]  # fmt: skip

_WORD = re.compile(r"[a-z0-9]+")
_STATE_WORDS = {"ca", "mo", "missouri"}


def words(name: str) -> list[str]:
    return _WORD.findall(name.casefold())


@pytest.mark.parametrize(("wid", "source", "state", "shown"), CHANGED)
def test_display_name_fixes_the_states_spelling(
    wid: str, source: str, state: str, shown: str
) -> None:
    assert water_names.display_name(wid, source, state) == shown


@pytest.mark.parametrize(("wid", "source", "state"), UNCHANGED)
def test_display_name_leaves_good_and_descriptive_names_alone(
    wid: str, source: str, state: str
) -> None:
    assert water_names.display_name(wid, source, state) == source


@pytest.mark.parametrize(("wid", "source", "state", "shown"), CHANGED)
def test_display_name_never_adds_or_drops_a_word_but_a_state_suffix(
    wid: str, source: str, state: str, shown: str
) -> None:
    before, after = words(source), words(shown)
    if before != after:
        assert before[-1] in _STATE_WORDS
        assert before[:-1] == after


def test_every_override_is_needed_and_keeps_the_words() -> None:
    for (wid, source), shown in water_names.OVERRIDES.items():
        assert water_names.fix_casing(source) != shown, wid
        assert words(source) == words(shown), wid


def test_an_override_stops_when_the_state_retypes_the_name() -> None:
    """Keyed by id and exact spelling: another spelling under the same id
    gets the rules, never the override's text."""
    wid = "mo-james-river-christian-county"
    assert water_names.display_name(wid, "James River Christian County", "MO") == (
        "James River Christian County"
    )
    assert (
        water_names.display_name("mo-other-id", "James river Christian county", "MO")
        != "James River, Christian County"
    )


@pytest.mark.parametrize(
    ("county_text", "counties", "shown"),
    [
        ("San Bernardino", ["San Bernardino"], "San Bernardino"),
        ("Calaveras; Tuolumne", ["Calaveras", "Tuolumne"], "Calaveras; Tuolumne"),
        ("Nevada State", [], "Nevada"),
        ("Arizona State", [], "Arizona"),
        # Text that names no county and no state shows nothing, never a guess.
        ("Lower Basin", [], ""),
        ("Mexico", [], ""),
        ("", [], ""),
    ],
)
def test_display_place_text(county_text: str, counties: list[str], shown: str) -> None:
    assert water_names.display_place_text(county_text, counties) == shown


def test_display_water_copies_and_keeps_the_source() -> None:
    water = {
        "id": "ca-san-bernardino-big-bear-lake-ca",
        "state": "CA",
        "name": "Big bear lake ca",
        "county_text": "San Bernardino",
        "counties": ["San Bernardino"],
    }
    before = copy.deepcopy(water)
    shown = water_names.display_water(water)
    assert water == before
    assert shown["name"] == "Big Bear Lake"
    assert shown["source_name"] == "Big bear lake ca"
    assert shown["id"] == water["id"]


# -- the built site -------------------------------------------------------

_TITLE = re.compile(r"<title>(.*?)</title>", re.S)
_H1 = re.compile(r"<h1>(.*?)</h1>", re.S)
_DESCRIPTION = re.compile(r'<meta name="description" content="(.*?)"', re.S)
_LEDE = re.compile(r'<p class="lede">(.*?)</p>', re.S)
_RAW = ("gamma pond ca", "Nevada State")


@pytest.fixture(scope="module")
def traps_snapshot(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    tmp = tmp_path_factory.mktemp("names")
    out = tmp / "site"
    assert (
        cli.main(
            [
                "--fixture-page", str(PAGE),
                "--fixture-csv", str(TRAPS),
                "--run-today", "2026-10-12",
                "--history", str(tmp / "history.json"),
                "--site-out", str(out),
            ]
        )
        == 0
    )  # fmt: skip
    loaded: dict[str, Any] = json.loads((out / "snapshot" / "v1.json").read_text())
    return loaded


def misspelled_snapshot(snap: dict[str, Any]) -> dict[str, Any]:
    """The traps snapshot with Gamma Pond split the way the state splits Big
    Bear Lake: the clean name in two counties (so its titles add the county)
    and a third entry typed "gamma pond ca" in the first county."""
    snap = copy.deepcopy(snap)
    waters = snap["waterbodies"]
    gamma = next(w for w in waters if w["name"] == "Gamma Pond")
    other = copy.deepcopy(gamma)
    other.update(id="ca-inyo-gamma-pond", county_text="Inyo", counties=["Inyo"])
    typed = copy.deepcopy(gamma)
    typed.update(id=gamma["id"] + "-ca", name="gamma pond ca")
    waters += [other, typed]
    return snap


def raw_name_problems(root: Path) -> list[str]:
    """Pages (not the snapshot) whose title, h1, description or lede shows a
    source spelling the display rules replace."""
    found = []
    for page in sorted(root.rglob("*.html")):
        raw = page.read_text(encoding="utf-8")
        for pattern in (_TITLE, _H1, _DESCRIPTION, _LEDE):
            match = pattern.search(raw)
            text = html.unescape(match.group(1)) if match else ""
            found += [
                f"{page.relative_to(root)}: {spelling!r}"
                for spelling in _RAW
                if spelling in text
            ]
    return found


def test_site_shows_display_names_and_the_snapshot_keeps_the_source(
    traps_snapshot: dict[str, Any], tmp_path: Path
) -> None:
    snap = misspelled_snapshot(traps_snapshot)
    out = tmp_path / "site"
    site.build_site(snap, out, ga4_measurement_id="")
    assert raw_name_problems(out) == []
    twin = next(w for w in snap["waterbodies"] if w["name"] == "gamma pond ca")
    page = (out / "water" / twin["id"] / "index.html").read_text(encoding="utf-8")
    h1 = _H1.search(page)
    assert h1 and h1.group(1).startswith("Gamma Pond:")
    zeta = next(w for w in snap["waterbodies"] if w["name"] == "Zeta Lake")
    lede = _LEDE.search(
        (out / "water" / zeta["id"] / "index.html").read_text(encoding="utf-8")
    )
    assert lede and "Zeta Lake (Nevada)" in html.unescape(lede.group(1))
    # The published snapshot is the source, byte for byte, ids included.
    published = json.loads((out / "snapshot" / "v1.json").read_text())
    assert published == snap
    titles = [
        _TITLE.search(p.read_text(encoding="utf-8"))
        for p in sorted((out / "water").rglob("index.html"))
    ]
    texts = [t.group(1) for t in titles if t]
    assert len(texts) == len(set(texts)), "two water pages share a title"
    # The county stays where the source's name is shared, and only there.
    title_of = {
        w["id"]: _TITLE.search(
            (out / "water" / w["id"] / "index.html").read_text(encoding="utf-8")
        )
        for w in snap["waterbodies"]
        if w["name"].casefold().startswith("gamma pond")
    }
    shown = {wid: m.group(1) for wid, m in title_of.items() if m}
    assert "Kern" in shown[twin["id"].removesuffix("-ca")]
    assert "Inyo" in shown["ca-inyo-gamma-pond"]
    assert (
        shown[twin["id"]].startswith("Gamma Pond") and "Kern" not in shown[twin["id"]]
    )


def test_raw_name_check_reports_the_source_spelling(
    traps_snapshot: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Negative control: with the display rules off, the same build shows the
    source spellings, and the check reports both."""
    monkeypatch.setattr(
        site, "display_water", lambda w: {**w, "source_name": w["name"]}
    )
    out = tmp_path / "site"
    site.build_site(misspelled_snapshot(traps_snapshot), out, ga4_measurement_id="")
    problems = raw_name_problems(out)
    assert any("gamma pond ca" in p for p in problems)
    assert any("Nevada State" in p for p in problems)
