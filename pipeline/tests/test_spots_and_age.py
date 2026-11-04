"""Decision 0017: a reported spot is the state's coordinates, a water's
headline date belongs to its level, and an old advisory says how old it is.

The records are Lake Elsinore's, from the state's file dated 2026-11-03
(Response_Action_IDs, report ids, dates, levels and coordinates as
published). On 2026-11-03 Lake Notice showed "Danger advisory, last posted
Sep 24, 2026" for it, though every record posted that day was a Caution.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import html
from collections import Counter
from pathlib import Path
from typing import Any

from caalgae import history as hist
from caalgae import site as site_mod
from caalgae import snapshot, wording
from caalgae.normalize import Record, water_key
from caalgae.sources import CA_SWRCB_FHAB

RUN = dt.date(2026, 11, 3)
FILE_DATE = "2026-11-03"
INFO = {
    "source": "ca-swrcb-fhab",
    "url": "https://publish.data.ca.gov/x/hab-responses_2026-11-03.csv",
    "file_name": "hab-responses_2026-11-03.csv",
    "file_date": FILE_DATE,
    "fetched_at": "2026-11-03T14:00:00Z",
    "rows_read": 6,
    "quarantined": 0,
}


def rec(
    rid: str,
    report: str,
    day: str,
    level: str,
    lat: float | None,
    lon: float | None,
    landmark: str,
) -> Record:
    tier = {"Danger": "danger", "Caution": "caution", "None": "no_advisory"}[level]
    return Record(
        id=rid,
        source=CA_SWRCB_FHAB.id,
        state="CA",
        site_id=report,
        water_key=water_key("Lake Elsinore", "Riverside"),
        water_name="Lake Elsinore",
        county_text="Riverside",
        landmark=landmark,
        lat=lat,
        lon=lon,
        date=dt.date.fromisoformat(day),
        level=level,
        tier=tier,
        explicit_no_advisory=tier == "no_advisory",
        end_date=None,
        detail="",
        stamp=None,
    )


TMDL = (33.662428, -117.3555)
INLET = (33.656111, -117.30444)
ELM_GROVE = (33.66581, -117.33548)


def elsinore() -> list[Record]:
    return [
        rec("9001", "2431", "2020-09-03", "Danger", *INLET, "Inlet Channel"),
        rec(
            "9002",
            "3289",
            "2022-12-08",
            "Danger",
            *TMDL,
            "In open water near TMDL LE02",
        ),
        rec(
            "13297", "3927", "2026-01-05", "None", *TMDL, "In open water near TMDL LE02"
        ),
        rec("15342", "4056", "2026-09-24", "Caution", *ELM_GROVE, "Elm Grove Beach"),
    ]


def build(records: list[Record]) -> dict[str, Any]:
    h = hist.merge(hist.empty(), records, run_date=RUN, file_info=INFO)
    snap = snapshot.build(
        h,
        run_date=RUN,
        generated_at=dt.datetime(2026, 11, 3, 14, tzinfo=dt.UTC),
        quarantine=Counter(),
    )
    snapshot.validate(snap)
    return snap


def water(records: list[Record]) -> dict[str, Any]:
    (only,) = build(records)["waterbodies"]
    return only


# -- spots are the state's coordinates ----------------------------------------


def test_a_none_at_the_same_coordinates_under_a_new_report_ends_the_old_one() -> None:
    w = water(elsinore())
    sites = {s["id"]: s for s in w["sites"]}
    # 3289 and 3927 are one spot, named by the newer report.
    assert "3289" not in sites
    assert sites["3927"]["status"]["kind"] == "no_advisory_recorded"
    assert sites["3927"]["status"]["lift_date"] == "2026-01-05"
    # Every record still points at a listed spot.
    assert {r["site"] for r in w["records"]} <= set(sites)
    assert w["status"]["sites_with_advisory"] == 2


def test_negative_control_a_meter_apart_is_another_spot() -> None:
    """Move the None one millionth of a degree. It is no longer the same
    reported spot, so the 2022 Danger stands: nothing is matched by
    distance, and the test above fails if the matching is switched off."""
    moved = [
        dataclasses.replace(r, lat=TMDL[0] + 0.000001) if r.id == "13297" else r
        for r in elsinore()
    ]
    assert next(r for r in moved if r.id == "13297").lat != TMDL[0]  # it applied
    w = water(moved)
    sites = {s["id"]: s for s in w["sites"]}
    assert sites["3289"]["status"]["kind"] == "advisory"
    assert sites["3289"]["status"]["posted"] == "2022-12-08"
    assert w["status"]["sites_with_advisory"] == 3


def test_reports_without_coordinates_are_never_merged() -> None:
    a = rec("1", "10", "2024-06-01", "Danger", None, None, "beach")
    b = rec("2", "11", "2025-06-01", "None", None, None, "beach")
    w = water([a, b])
    assert {s["id"] for s in w["sites"]} == {"10", "11"}
    assert w["status"]["kind"] == "advisory"


def test_other_sources_are_not_matched_by_coordinates() -> None:
    a = dataclasses.replace(elsinore()[1], source="mo-dnr-hab")
    b = dataclasses.replace(elsinore()[2], source="mo-dnr-hab")
    assert snapshot.spot_ids(
        [
            hist.HistoryEntry(record=a, first_seen=FILE_DATE, last_seen=FILE_DATE),
            hist.HistoryEntry(record=b, first_seen=FILE_DATE, last_seen=FILE_DATE),
        ]
    ) == {"3289": "3289", "3927": "3927"}


# -- the headline's date belongs to its level ---------------------------------


def test_elsinore_reads_danger_with_the_dangers_own_date() -> None:
    w = water(elsinore())
    assert wording.headline(w["status"]) == (
        "Danger advisory, last posted Sep 3, 2020. No all-clear recorded."
    )
    assert wording.newer_posting(w) == (
        "The newest advisory posting here is lower: Caution advisory, posted "
        "Sep 24, 2026 at 1 reported spot. No all-clear recorded."
    )


def test_age_note_says_how_old_and_when_the_state_last_wrote() -> None:
    w = water(elsinore())
    assert wording.age_note(w, FILE_DATE) == (
        "That level was last posted Sep 3, 2020, more than 6 years before the "
        "state's data dated Nov 3, 2026, and the state has not recorded an end "
        "to it. The state's newest record of any kind for Lake Elsinore is from "
        "Sep 24, 2026."
    )


def test_no_age_note_or_newer_line_for_a_fresh_single_posting() -> None:
    w = water([elsinore()[3]])
    assert wording.age_note(w, FILE_DATE) is None
    assert wording.newer_posting(w) is None
    assert wording.age_note(w, None) is None
    assert wording._age(400) == "more than a year"
    assert wording._age(100) == "3 months"


def test_a_new_lower_posting_keeps_the_water_on_the_recent_list() -> None:
    w = water(elsinore())
    assert not wording.is_recent(w["status"], dt.date(2026, 10, 1))
    assert wording.is_recent_water(w, dt.date(2026, 10, 1))
    assert not wording.is_recent_water(w, RUN)


def test_the_water_page_shows_all_three_sentences(tmp_path: Path) -> None:
    snap = build(elsinore())
    site_mod.build_site(snap, tmp_path, ga4_measurement_id="")
    page = html.unescape(
        (tmp_path / "water" / "ca-riverside-lake-elsinore" / "index.html").read_text()
    )
    assert "Danger advisory, last posted Sep 3, 2020. No all-clear recorded." in page
    assert "Danger advisory, last posted Sep 24, 2026" not in page
    assert "The newest advisory posting here is lower: Caution advisory" in page
    assert "more than 6 years before the state's data dated Nov 3, 2026" in page
    listing = html.unescape((tmp_path / "advisories" / "index.html").read_text())
    assert "Danger advisory. The newest advisory posting here is lower" in listing
