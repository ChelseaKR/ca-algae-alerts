"""The iPhone app says what the website says (decision 0017).

The app cannot run this package, so its tests read a fixture built here:
Lake Elsinore's real records from ``test_spots_and_age`` (the state's file
dated 2026-11-03), each case's snapshot as the pipeline builds it, and the
website's sentences for it. ``AdvisoryParityTests.swift`` decodes every
snapshot with the app's strict decoder and checks the app's sentences
against these, word for word.

This test fails when the committed fixture no longer matches what the
pipeline builds, so the two cannot drift. To rebuild it after a deliberate
wording or status change, run

    CAALGAE_WRITE_IOS_FIXTURE=1 uv run --frozen pytest tests/test_ios_parity_fixture.py

and commit the file with the Swift change that matches it.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from test_spots_and_age import FILE_DATE, RUN, TMDL, build, elsinore, history_only

from caalgae import wording
from caalgae.normalize import Record

FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "ios/AlgaeCore/Tests/AlgaeCoreTests/Fixtures/elsinore-parity.json"
)
RECENT_ON = dt.date(2026, 10, 1)


def _fresh_danger() -> list[Record]:
    return [
        dataclasses.replace(r, level="Danger", tier="danger") if r.id == "15344" else r
        for r in elsinore()
    ]


def _newer_lower() -> list[Record]:
    return [
        dataclasses.replace(r, date=dt.date(2026, 3, 10)) if r.id == "714" else r
        for r in elsinore()
    ]


def _none_a_meter_away() -> list[Record]:
    return [
        dataclasses.replace(r, lat=TMDL[0] + 0.000001) if r.id == "13297" else r
        for r in elsinore()
    ]


CASES: dict[str, Callable[[], list[Record]]] = {
    "elsinore": elsinore,
    "history_only": history_only,
    "fresh_danger": _fresh_danger,
    "newer_lower": _newer_lower,
    "none_a_meter_away": _none_a_meter_away,
    "single_fresh": lambda: [elsinore()[-1]],
}


def fixture() -> dict[str, Any]:
    cases = []
    for name, records in CASES.items():
        snap = build(records())
        (water,) = snap["waterbodies"]
        cases.append(
            {
                "name": name,
                "snapshot": snap,
                "expected": {
                    "headline": wording.headline(water["status"]),
                    "newer_posting": wording.newer_posting(water),
                    "older_higher": wording.older_higher(water),
                    "age_note": wording.age_note(water, FILE_DATE),
                    "newest_posted": wording.newest_posted(water),
                    "recent_on": RECENT_ON.isoformat(),
                    "is_recent_on": wording.is_recent_water(water, RECENT_ON),
                    "is_recent_on_run_date": wording.is_recent_water(water, RUN),
                    "sites_with_advisory": water["status"]["sites_with_advisory"],
                    "site_ids": sorted(s["id"] for s in water["sites"]),
                },
            }
        )
    return {
        "about": (
            "Built by pipeline/tests/test_ios_parity_fixture.py from Lake "
            "Elsinore's records in the state's file dated 2026-11-03. Do not "
            "edit by hand."
        ),
        "file_date": FILE_DATE,
        "cases": cases,
    }


def render() -> str:
    return json.dumps(fixture(), indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def test_the_app_fixture_matches_what_the_pipeline_builds() -> None:
    text = render()
    if os.environ.get("CAALGAE_WRITE_IOS_FIXTURE") == "1":
        FIXTURE.write_text(text, encoding="utf-8")
    assert FIXTURE.read_text(encoding="utf-8") == text, (
        "ios fixture is stale; rebuild it (see this module's docstring)"
    )


def test_the_fixture_covers_every_line_the_app_must_match() -> None:
    """Each sentence the app mirrors appears in at least one case, and is
    absent in at least one, so the Swift tests cannot pass on empty input."""
    expected = [c["expected"] for c in fixture()["cases"]]
    for key in ("newer_posting", "older_higher", "age_note"):
        assert any(e[key] for e in expected), key
        assert any(e[key] is None for e in expected), key
    assert {e["is_recent_on"] for e in expected} == {True, False}
    by_name = {c["name"]: c["expected"] for c in fixture()["cases"]}
    assert by_name["elsinore"]["headline"] == (
        "Caution advisory, last posted Sep 24, 2026. No all-clear recorded."
    )


def test_negative_control_an_edited_fixture_is_reported() -> None:
    """A fixture with one sentence changed must not compare equal."""
    data = json.loads(render())
    data["cases"][0]["expected"]["headline"] = (
        "Danger advisory, last posted Sep 24, 2026. No all-clear recorded."
    )
    edited = json.dumps(data, indent=1, sort_keys=True, ensure_ascii=False) + "\n"
    assert edited != render()
