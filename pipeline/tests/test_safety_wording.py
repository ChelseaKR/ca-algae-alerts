"""The guidance, absence and list-age wording from the 2026-11-05 audit.

- Every California level keeps pets out of the water, not only from
  drinking it, and says boiling or filtering does not make it safe.
- Toxic algal mat signs get the mat sign's own guidance for dogs and children.
- No page says a water that is not listed has no advisory.
- County and state list rows say how old a record is, current ones first,
  with a caveat under each list.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from test_site import affirmative_safety_claims, build, pages, text_of

from caalgae import wording


@pytest.fixture(scope="module")
def traps_site(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build(tmp_path_factory.mktemp("safety"))


def _water(kind: str, day: str | None, **status: Any) -> dict[str, Any]:
    st: dict[str, Any] = {"kind": kind, **status}
    if kind == "advisory":
        st.setdefault("tier", "danger")
        st["posted"] = day
    elif kind == "no_advisory_recorded":
        st.setdefault("lift_kind", "no_advisory_record")
        st["lift_date"] = day
    return {"name": f"W {kind} {day}", "status": st, "sites": [], "records": []}


@pytest.mark.parametrize("tier", ["caution", "warning", "danger"])
def test_every_level_keeps_pets_out_and_says_boiling_does_not_help(
    tier: str,
) -> None:
    text = wording.LEVEL_GUIDANCE[tier]
    assert "go into or drink the water" in text
    assert "boiling or filtering does not make it safe" in text
    assert "do not let pets drink" not in text.casefold()
    assert affirmative_safety_claims(text) == []


def test_fish_lines_follow_the_state_signs() -> None:
    for tier in ("caution", "warning"):
        assert "throw away the guts" in wording.LEVEL_GUIDANCE[tier]
    assert "Do not eat fish or shellfish" in wording.LEVEL_GUIDANCE["danger"]


@pytest.mark.parametrize(
    "level", ["Algal mat alert sign", "Algal mat general awareness sign"]
)
def test_algal_mat_waters_get_dog_and_child_guidance(level: str) -> None:
    water = {
        "state": "CA",
        "status": {"kind": "advisory", "tier": "other_advisory", "level": level},
    }
    text = wording.guidance_for(water)
    assert text == wording.LEVEL_GUIDANCE["algal_mat"]
    assert "Do not let dogs eat algal mats or drink from the water" in text
    assert "children or adults touch, eat or swallow" in text


def test_other_non_standard_levels_keep_the_read_the_sign_text() -> None:
    water = {
        "state": "CA",
        "status": {
            "kind": "advisory",
            "tier": "other_advisory",
            "level": "General awareness",
        },
    }
    assert wording.guidance_for(water) == wording.LEVEL_GUIDANCE["other_advisory"]


def test_missouri_guidance_quotes_the_department() -> None:
    water = {"state": "MO", "status": {"kind": "advisory", "tier": "other_advisory"}}
    text = wording.guidance_for(water)
    assert text == wording.STATE_GUIDANCE["MO"]
    assert "Do not let pets drink or play in the water" in text
    assert affirmative_safety_claims(text) == []


def test_no_page_says_a_missing_water_has_no_advisory(traps_site: Path) -> None:
    for page in pages(traps_site):
        text = text_of(page)
        assert "not listed has no advisory" not in text, page
        assert "has no advisory record at all" not in text, page
    home = text_of(traps_site / "index.html")
    assert "a water not listed may still have an advisory" in home
    dogs = text_of(traps_site / "dogs" / "index.html")
    assert "may still have an advisory" in dogs
    assert "Algal mat signs" in dogs


def test_list_row_says_how_old_a_record_is() -> None:
    old = _water("advisory", "2021-07-09")
    assert wording.list_row(old, "2026-11-03") == (
        "Danger advisory, last posted Jul 9, 2021. No all-clear recorded. "
        "This record is more than 5 years old."
    )
    recent = _water("advisory", "2026-10-23")
    assert wording.list_row(recent, "2026-11-03").endswith("No all-clear recorded.")
    lifted = _water("no_advisory_recorded", "2018-12-04")
    assert wording.list_row(lifted, "2026-11-03").endswith(
        "recommends no advisory. This record is more than 7 years old."
    )
    # Without a file date nothing is computed, never guessed.
    assert "old" not in wording.list_row(old, None)


def test_undetermined_row_carries_its_newest_record_date() -> None:
    w = _water("undetermined", None)
    w["records"] = [
        {"date": "2019-06-01"},
        {"date": "2024-08-02", "removed_from_source": True},
    ]
    assert wording.list_row(w, "2026-11-03") == (
        "Reports on file, with no advisory level the state has classified. "
        "Newest record Jun 1, 2019. This record is more than 7 years old."
    )


def test_list_order_puts_current_records_first() -> None:
    waters = [
        _water("advisory", "2021-07-09"),
        _water("no_advisory_recorded", "2018-12-04"),
        _water("advisory", "2026-10-23"),
        _water("no_advisory_recorded", "2026-09-01"),
        _water("advisory", "2020-05-01"),
    ]
    got = [w["name"] for w in sorted(waters, key=wording.list_sort_key)]
    assert got == [
        "W advisory 2026-10-23",
        "W advisory 2021-07-09",
        "W advisory 2020-05-01",
        "W no_advisory_recorded 2026-09-01",
        "W no_advisory_recorded 2018-12-04",
    ]


def test_county_and_state_lists_carry_the_caveat(traps_site: Path) -> None:
    lists = [
        p
        for p in pages(traps_site)
        if p.parent.parent.name == "county" or p.parent.parent.name == "state"
    ]
    assert lists
    for page in lists:
        text = text_of(page)
        assert "Older records are not current conditions." in text, page
        assert affirmative_safety_claims(text) == [], page
