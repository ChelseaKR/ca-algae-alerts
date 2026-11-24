"""/state/mo/ counts the waters whose latest record is an advisory in its
title, its description and its first line (DECISIONS 0041), the way county
pages do (0018).

/state/ca/ keeps its launch title and description. A state with no advisory
on record states no count, because "0 of 225 waters" would read as an
all-clear (0002). A state whose data is unavailable keeps the outage wording
of 0024 and states no count anywhere.
"""

from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any

import pytest
from paths import CYAN_CACHE, MO_POINTS, PAGE, TRAPS
from test_site import affirmative_safety_claims, build, lede_of, snapshot_of

from caalgae import cli, site, wording

_TITLE = re.compile(r"<title>(.*?)</title>", re.S)
_DESCRIPTION = re.compile(r'<meta name="description" content="([^"]*)"')
_COUNT = re.compile(r"(\d+) of (?:the )?(\d+) waters?\b")

CA_TITLE = "California lake algae advisories | Lake Notice"


def run(tmp: Path, run_today: str, *extra: str) -> Path:
    assert cli.main([
        "--fixture-page", str(PAGE), "--fixture-csv", str(TRAPS), "--run-today", run_today,
        "--history", str(tmp / "h.json"), "--site-out", str(tmp / "site"),
        "--cyan-cache", str(CYAN_CACHE), "--ny-history", "off", *extra,
    ]) == 0  # fmt: skip
    return tmp / "site"


@pytest.fixture(scope="module")
def both(tmp_path_factory: pytest.TempPathFactory) -> Path:
    tmp = tmp_path_factory.mktemp("both")
    return run(tmp, "2026-10-12", "--mo-fixture", str(MO_POINTS))


def texts_of(page: Path) -> dict[str, str]:
    raw = page.read_text(encoding="utf-8")
    title, description = _TITLE.search(raw), _DESCRIPTION.search(raw)
    assert title and description
    return {
        "title": html.unescape(title.group(1)).strip(),
        "description": html.unescape(description.group(1)),
        "lede": lede_of(page),
    }


def expected_state_counts(snap: dict[str, Any]) -> dict[str, tuple[int, int]]:
    """Per state, from the snapshot: waters with an advisory, all waters."""
    expected: dict[str, tuple[int, int]] = {}
    for w in snap["waterbodies"]:
        adv, total = expected.get(w["state"], (0, 0))
        expected[w["state"]] = (adv + (w["status"]["kind"] == "advisory"), total + 1)
    return expected


def state_snippet_problems(root: Path) -> list[str]:
    """State pages whose title, description or first line disagree with the
    snapshot about how many waters have an advisory as their latest record,
    or that state a count where none belongs: a state outside
    ``site.STATE_COUNTED``, or one with no advisory on record."""
    snap = snapshot_of(root)
    problems = []
    for state, (adv, total) in sorted(expected_state_counts(snap).items()):
        texts = texts_of(root / "state" / state.lower() / "index.html")
        problems += [
            f"{state}: {claim}"
            for text in texts.values()
            for claim in affirmative_safety_claims(text)
        ]
        if state not in site.STATE_COUNTED or adv == 0:
            problems += [
                f"{state}: {where} states a count"
                for where, text in texts.items()
                if _COUNT.search(text)
            ]
            continue
        for where, text in texts.items():
            found = _COUNT.search(text)
            if not found or found.groups() != (str(adv), str(total)):
                problems.append(f"{state}: {where} count is not {adv} of {total}")
        file_date = next(
            f["file_date"]
            for f in snap["source_files"]
            if f["source"] == site.STATE_SOURCE[state]
        )
        if wording.date_label(file_date) not in texts["description"]:
            problems.append(f"{state}: description lacks the state's file date")
    return problems


def test_title_keeps_the_launch_words_and_adds_the_count() -> None:
    assert site.state_title("Missouri", 47, 225) == (
        "Missouri lake algae advisories: 47 of 225 waters"
    )
    assert site.state_title("Missouri", 1, 1).endswith("1 of 1 water")
    # No advisory on record: the launch title, and never "0 of".
    assert site.state_title("Missouri", 0, 225) == (
        "Missouri lake algae advisories | Lake Notice"
    )
    assert site.state_title("California", 0, 905) == CA_TITLE


def test_count_line_and_description_say_the_same_count_with_its_date() -> None:
    line = site.state_count_line("Missouri", 47, 225, "2026-11-13")
    assert line == (
        "47 of the 225 waters in Missouri have a toxic algae advisory as their "
        "latest state record, in the state's data dated Nov 13, 2026."
    )
    assert site.state_description("Missouri", 47, 225, "2026-11-13") == (
        "47 of the 225 waters in Missouri have a toxic algae (harmful algal "
        "bloom) advisory as their latest state record, in the state's data "
        "dated Nov 13, 2026."
    )
    assert site.state_count_line("Missouri", 1, 225, None) == (
        "1 of the 225 waters in Missouri has a toxic algae advisory as its "
        "latest state record."
    )
    assert site.state_count_line("Missouri", 1, 1, None) == (
        "The one water in Missouri has a toxic algae advisory as its latest "
        "state record."
    )


def test_no_advisory_on_record_states_no_count() -> None:
    assert site.state_count_line("Missouri", 0, 225, "2026-11-13") == ""
    description = site.state_description("Missouri", 0, 225, "2026-11-13")
    assert description == (
        "Toxic algae advisory status and history for 225 lakes and rivers in "
        "Missouri, from the state's own records."
    )
    assert "0 of" not in description


def test_every_candidate_fits_and_a_long_name_drops_the_extra_words() -> None:
    for name, adv, total in [("Missouri", 47, 225), ("California", 477, 905),
                             ("New Hampshire", 1234, 5678), ("Missouri", 0, 225),
                             ("Extraordinarily Long Named Imaginary State", 3, 9)]:  # fmt: skip
        title = site.state_title(name, adv, total)
        description = site.state_description(name, adv, total, "2026-09-30")
        assert len(title) <= site.TITLE_MAX, title
        assert len(description) <= site.DESCRIPTION_MAX, description
    # Too long with "(harmful algal bloom)": the count sentence alone.
    shorter = site.state_description("New Hampshire", 1234, 5678, "2026-09-30")
    assert shorter == site.state_count_line("New Hampshire", 1234, 5678, "2026-09-30")
    assert "harmful algal bloom" not in shorter


def test_missouri_page_counts_what_the_snapshot_holds(both: Path) -> None:
    adv, total = expected_state_counts(snapshot_of(both))["MO"]
    assert adv > 0  # the fixture has Missouri advisories to count
    texts = texts_of(both / "state" / "mo" / "index.html")
    assert texts["title"] == f"Missouri lake algae advisories: {adv} of {total} waters"
    assert texts["description"].startswith(f"{adv} of the {total} waters in Missouri")
    # Missouri's file date is its read date, the run date of this build.
    assert "in the state's data dated Oct 12, 2026." in texts["description"]
    assert site.state_count_line("Missouri", adv, total, "2026-10-12") in texts["lede"]
    assert state_snippet_problems(both) == []


def test_california_page_is_unchanged(both: Path) -> None:
    texts = texts_of(both / "state" / "ca" / "index.html")
    total = expected_state_counts(snapshot_of(both))["CA"][1]
    assert texts["title"] == CA_TITLE
    assert texts["description"] == (
        f"Toxic algae advisory status and history for {total} lakes and rivers "
        "in California, from the state's own records."
    )
    assert texts["lede"] == (
        f"{total} waters appear in the records of the California State Water "
        "Resources Control Board. Waters whose latest record is an advisory "
        "come first, newest first."
    )


def test_the_check_catches_a_wrong_count_and_a_count_where_none_belongs(
    tmp_path: Path,
) -> None:
    # Negative control: each sabotage must apply and must be reported.
    root = run(tmp_path, "2026-10-12", "--mo-fixture", str(MO_POINTS))
    assert state_snippet_problems(root) == []
    page = root / "state" / "mo" / "index.html"
    raw = page.read_text(encoding="utf-8")
    changed = _TITLE.sub(
        lambda m: _COUNT.sub("999 of 999 waters", m.group(0)), raw, count=1
    )
    assert changed != raw
    page.write_text(changed, encoding="utf-8")
    page = root / "state" / "ca" / "index.html"
    raw = page.read_text(encoding="utf-8")
    changed = _TITLE.sub("<title>California algae: 0 of 2 waters</title>", raw)
    assert changed != raw
    page.write_text(changed, encoding="utf-8")
    problems = state_snippet_problems(root)
    assert any(p.startswith("MO: title count is not") for p in problems)
    assert "CA: title states a count" in problems


def test_unavailable_missouri_keeps_the_outage_wording_and_states_no_count(
    tmp_path: Path,
) -> None:
    run(tmp_path, "2026-10-11", "--mo-fixture", str(MO_POINTS))
    gone = tmp_path / "mo.json"
    gone.write_bytes(b'{"error": {"code": 404}}')
    root = run(tmp_path, "2026-10-12", "--mo-fixture", str(gone))
    texts = texts_of(root / "state" / "mo" / "index.html")
    assert texts["title"] == "Missouri lake algae: data unavailable since Oct 12, 2026"
    assert texts["description"] == site.unavailable_description(
        "Missouri lakes", "Missouri", "2026-10-12", scope="their"
    )
    for where, text in texts.items():
        assert not _COUNT.search(text), (where, text)
        assert "latest state record" not in text, (where, text)


def test_a_passing_failure_dates_the_count_by_the_last_good_read(
    tmp_path: Path,
) -> None:
    # Missouri read on Oct 11 and not read on Oct 12 (an offline run without
    # its fixture is a passing failure): shown, dated by the read (0024).
    run(tmp_path, "2026-10-11", "--mo-fixture", str(MO_POINTS),
        "--fixture-fetched-at", "2026-10-11T12:00:00Z")  # fmt: skip
    root = run(tmp_path, "2026-10-12")
    mode = next(m for m in snapshot_of(root)["state_status"] if m["state"] == "MO")
    assert mode["mode"] == "stale_dated"
    texts = texts_of(root / "state" / "mo" / "index.html")
    assert "in the state's data dated Oct 11, 2026." in texts["description"]
    assert "Oct 12" not in texts["description"]
    assert state_snippet_problems(root) == []


def test_the_constant_is_the_only_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Widening is one edit: with California in STATE_COUNTED its page counts
    # too, and the same check passes against the snapshot.
    monkeypatch.setattr(site, "STATE_COUNTED", frozenset({"CA", "MO"}))
    root = build(tmp_path)
    adv, total = expected_state_counts(snapshot_of(root))["CA"]
    assert adv > 0
    assert texts_of(root / "state" / "ca" / "index.html")["title"] == (
        f"California lake algae advisories: {adv} of {total} waters"
    )
    assert state_snippet_problems(root) == []
