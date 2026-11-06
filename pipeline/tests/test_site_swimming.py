"""The "Swimming at <water>" section on indexed water pages (DECISIONS 0033) answers
the swimming question from the water's own posted status and that level's
sign only, never calls a water safe, and carries the not-a-finding sentence
for every status that is not an advisory."""

from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any

import pytest
from test_site import affirmative_safety_claims, build, pages, text_of

from caalgae import i18n, where_to_check, wording

_SECTION = re.compile(r'<h2 id="swimming">(.*?)</h2>(.*?)<h2 ', re.S)
_TAG = re.compile(r"<[^>]+>")


@pytest.fixture(scope="module")
def traps_site(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build(tmp_path_factory.mktemp("swim"))


def water(state: str = "CA", **status: Any) -> dict[str, Any]:
    return {"id": "ca-x-lake-x", "name": "Lake X", "state": state, "status": status}


def advisory(tier: str, level: str = "", state: str = "CA") -> dict[str, Any]:
    return water(state, kind="advisory", tier=tier, level=level, posted="2026-10-02")


def text(lines: list[str]) -> str:
    return " ".join(lines)


@pytest.mark.parametrize(
    ("tier", "level", "expected"),
    [
        ("caution", "Caution", "Caution sign asks people to keep children away"),
        ("warning", "Warning", "Warning sign says “No swimming.”"),
        ("danger", "Danger", "stay out of the water until further notice"),
        (
            "other_advisory",
            "Algal mat alert sign",
            "touch, eat or swallow any algal mats",
        ),
        ("other_advisory", "General awareness", "Read the sign posted at the water"),
    ],
)
def test_an_advisory_gets_its_posting_and_its_signs_swim_line(
    tier: str, level: str, expected: str
) -> None:
    lines = wording.swim_answer(advisory(tier, level))
    assert lines[0].startswith(
        "The state's records cannot say if it is safe to swim at Lake X today."
    )
    assert "The latest posting: Caution advisory" in lines[0] or tier != "caution"
    assert "last posted Oct 2, 2026. No all-clear recorded." in lines[0]
    assert expected in lines[1]
    assert affirmative_safety_claims(text(lines)) == []


def test_missouri_gets_the_generic_line_not_californias_levels() -> None:
    lines = wording.swim_answer(advisory("other_advisory", state="MO"))
    assert lines[1] == wording.SWIM_GENERIC
    assert "Caution" not in text(lines) and "Warning" not in text(lines)


def test_no_advisory_carries_the_not_a_finding_sentence() -> None:
    lines = wording.swim_answer(
        water(
            kind="no_advisory_recorded",
            lift_kind="no_advisory_record",
            lift_date="2026-09-01",
        )
    )
    joined = text(lines)
    assert "recommends no advisory." in joined
    assert wording.NOT_A_FINDING in joined
    assert "all-clear" not in joined.replace("no all-clear", "")
    assert affirmative_safety_claims(joined) == []


def test_an_unread_level_and_no_level_never_answer_the_question() -> None:
    unread = text(
        wording.swim_answer(water(kind="undetermined", level="Danger - Closure"))
    )
    assert "a level this site does not recognize" in unread
    assert "stay out of the water at Lake X" in unread
    blank = text(wording.swim_answer(water(kind="undetermined", level=None)))
    assert "cannot answer the swimming question" in blank
    for line in (unread, blank):
        assert affirmative_safety_claims(line) == []


def test_heading_is_a_statement_not_a_question() -> None:
    assert wording.SWIM_HEADING.format(name="Lake X") == "Swimming at Lake X"
    assert "?" not in wording.SWIM_HEADING


def test_every_swim_string_is_in_the_spanish_catalog_as_a_draft() -> None:
    cat = i18n.catalog()
    keys = [k for k in cat.en if k.startswith("swim.")]
    assert len(keys) == 15
    for key in keys:
        assert cat.status[key]["status"] == "draft", key
    safety = [k for k in keys if cat.status[k].get("safety")]
    assert set(keys) - set(safety) == {"swim.heading", "swim.own_page", "swim.covers"}
    assert i18n.check_catalog(cat, enabled=False) == []


def section(page: Path) -> str | None:
    found = _SECTION.search(page.read_text(encoding="utf-8"))
    if not found:
        return None
    return html.unescape(_TAG.sub(" ", found.group(1) + " " + found.group(2)))


def test_indexed_pages_have_the_section_and_noindex_pages_do_not(
    traps_site: Path,
) -> None:
    indexed = noindexed = 0
    for page in (traps_site / "water").glob("*/index.html"):
        raw = page.read_text(encoding="utf-8")
        body = section(page)
        if 'content="noindex' in raw:
            noindexed += 1
            assert body is None, page
        else:
            indexed += 1
            assert body is not None, page
            assert "cannot say if it is safe to swim" in body
            assert "check the state's official algae page" in body
    # The negative control is real: the fixture has pages of both kinds.
    assert indexed and noindexed


def test_no_page_claims_safety_with_the_section_on(traps_site: Path) -> None:
    claims = [
        f"{page.name}: {s}"
        for page in pages(traps_site)
        for s in affirmative_safety_claims(text_of(page))
    ]
    assert claims == []


def test_only_one_waters_sources_are_linked() -> None:
    elsinore = where_to_check.sources_for("ca-riverside-lake-elsinore")
    assert [s.name for s in elsinore] == [
        "Lake Elsinore and San Jacinto Watersheds Authority: lake conditions"
    ]
    assert len(where_to_check.sources_for("ca-lake-clear-lake")) == 1
    assert where_to_check.sources_for("ca-alameda-lake-chabot") == []
    # Every id a source names is a California water id.
    for src in where_to_check.SOURCES:
        assert all(w.startswith("ca-") for w in src.waters)
