"""The "Also listed under <county>" (DECISIONS 0034): mutual links between the
state's entries for what may be one water listed once per county, detected
from names, county borders and distance, never from a list of names."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from test_site import affirmative_safety_claims, build, text_of

from caalgae import county_adjacency, site
from caalgae.normalize import CA_COUNTIES

# About 1 mile of latitude, in degrees.
MILE = 1 / 69.0


def water(
    wid: str, name: str, counties: list[str], lat: float, state: str = "CA"
) -> dict[str, Any]:
    return {
        "id": wid,
        "name": name,
        "state": state,
        "counties": counties,
        "center": {"lat": lat, "lon": -120.0},
    }


def links(waters: list[dict[str, Any]]) -> dict[str, list[str]]:
    found = site.also_listed(waters, site.same_name_nearby(waters))
    return {wid: [o["id"] for o in others] for wid, others in found.items()}


def test_adjacency_covers_every_county_and_is_symmetric() -> None:
    assert set(county_adjacency.CA_NEIGHBORS) == set(CA_COUNTIES)
    for county, neighbors in county_adjacency.CA_NEIGHBORS.items():
        assert county not in neighbors
        for other in neighbors:
            assert county in county_adjacency.CA_NEIGHBORS[other]
    assert len(county_adjacency.CA_ADJACENT_PAIRS) == 144
    assert county_adjacency.touching(["El Dorado"], ["Placer"])
    assert county_adjacency.touching(["Imperial", "Riverside"], ["Imperial"])
    # Alameda and Solano do not touch: the two Lake Chabots are different waters.
    assert not county_adjacency.touching(["Alameda"], ["Solano"])


def test_a_lake_split_across_two_bordering_counties_links_both_ways() -> None:
    got = links(
        [
            water("ca-el-dorado-lake-tahoe", "Lake Tahoe", ["El Dorado"], 39.0),
            water("ca-placer-lake-tahoe", "Lake Tahoe", ["Placer"], 39.0 + 18 * MILE),
        ]
    )
    assert got == {
        "ca-el-dorado-lake-tahoe": ["ca-placer-lake-tahoe"],
        "ca-placer-lake-tahoe": ["ca-el-dorado-lake-tahoe"],
    }


@pytest.mark.parametrize(
    ("a", "b"),
    [
        # Counties that do not touch.
        (("Lake Chabot", ["Alameda"], 0), ("Lake Chabot", ["Solano"], 25)),
        # Bordering counties, but a lake too far away to be the same one.
        (
            ("Horseshoe Lake", ["Los Angeles"], 0),
            ("Horseshoe Lake", ["San Bernardino"], 67),
        ),
        (("Rock Creek", ["Mono"], 0), ("Rock Creek", ["Tuolumne"], 80)),
        # Different names.
        (("Eel River", ["Humboldt"], 0), ("South Fork Eel River", ["Mendocino"], 9)),
        # The same county list is not "another county".
        (("Lake X", ["Placer"], 0), ("Lake X", ["Placer"], 10)),
    ],
)
def test_pairs_that_are_not_linked(
    a: tuple[str, list[str], float], b: tuple[str, list[str], float]
) -> None:
    waters = [
        water("ca-a", a[0], a[1], 38.0 + a[2] * MILE),
        water("ca-b", b[0], b[1], 38.0 + b[2] * MILE),
    ]
    assert links(waters) == {}


def test_a_river_reaches_farther_than_a_lake() -> None:
    river = [
        water("ca-humboldt-eel-river", "Eel River", ["Humboldt"], 40.0),
        water("ca-mendocino-eel-river", "Eel River", ["Mendocino"], 40.0 - 100 * MILE),
    ]
    assert links(river)["ca-humboldt-eel-river"] == ["ca-mendocino-eel-river"]
    lake = [
        water("ca-a", "Lake Y", ["Humboldt"], 40.0),
        water("ca-b", "Lake Y", ["Mendocino"], 40.0 - 40 * MILE),
    ]
    assert links(lake) == {}


def test_matching_names_nearby_keeps_its_own_pairs() -> None:
    # Within SAME_NAME_NEARBY_MILES: the existing section links them, not this one.
    waters = [
        water("ca-calaveras-lake-tulloch", "Lake Tulloch", ["Calaveras"], 37.9),
        water(
            "ca-tuolumne-lake-tulloch", "Lake Tulloch", ["Tuolumne"], 37.9 + 2 * MILE
        ),
    ]
    assert site.same_name_nearby(waters)
    assert links(waters) == {}


def test_waters_without_a_county_or_center_are_never_linked() -> None:
    no_county = water("mo-a", "Lake Z", [], 38.0, state="MO")
    other = water("mo-b", "Lake Z", [], 38.0 + 10 * MILE, state="MO")
    assert links([no_county, other]) == {}
    no_center = water("ca-a", "Lake Tahoe", ["Placer"], 39.0)
    no_center["center"] = None
    assert links([no_center, water("ca-b", "Lake Tahoe", ["El Dorado"], 39.0)]) == {}


@pytest.fixture(scope="module")
def split_site(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, str, str]:
    """The traps build's snapshot plus a copy of one California water listed
    under a bordering county 15 miles away, built again."""
    tmp = tmp_path_factory.mktemp("split")
    built = build(tmp)
    snap = json.loads((built / "snapshot" / "v1.json").read_text("utf-8"))
    original = next(
        w
        for w in snap["waterbodies"]
        if w["state"] == "CA" and w["counties"] and w["center"]
    )
    county = original["counties"][0]
    neighbor = sorted(county_adjacency.CA_NEIGHBORS[county])[0]
    twin = copy.deepcopy(original)
    twin["id"] = f"{original['id']}-twin"
    twin["counties"] = [neighbor]
    twin["center"]["lat"] += 15 * MILE
    snap["waterbodies"].append(twin)
    out = tmp / "split-site"
    site.build_site(snap, out)
    return out, original["id"], twin["id"]


def test_built_pages_link_each_other(split_site: tuple[Path, str, str]) -> None:
    out, a, b = split_site
    page_a = (out / "water" / a / "index.html").read_text("utf-8")
    page_b = (out / "water" / b / "index.html").read_text("utf-8")
    assert f'href="../../water/{b}/">Also listed under ' in page_a
    assert f'href="../../water/{a}/">Also listed under ' in page_b
    for page in (out / "water" / a / "index.html", out / "water" / b / "index.html"):
        text = text_of(page)
        assert "may be the same water, listed once per county" in text
        assert affirmative_safety_claims(text) == []


def test_unpaired_pages_have_no_section(split_site: tuple[Path, str, str]) -> None:
    out, a, b = split_site
    others = [
        p for p in (out / "water").glob("*/index.html") if p.parent.name not in (a, b)
    ]
    assert others
    for page in others:
        assert 'id="also-listed"' not in page.read_text("utf-8"), page
