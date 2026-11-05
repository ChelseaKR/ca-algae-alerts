"""Winter records (DECISIONS 0028): a water page's "Winter records at
<water>" section, its winter line in "Dogs at <water>", and the /dogs/
"In winter" line.

A quiet winter is not an all-clear. Every count comes from the state's own
records in the snapshot. A water with no winter record gets the
not-a-finding sentence with the state's month counts, never a level, a zero
or "no advisory". Each negative control checks that its sabotage applied.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import html
import re
from collections import Counter
from pathlib import Path
from typing import Any

from test_site import affirmative_safety_claims
from test_spots_and_age import INFO, elsinore, history_only

from caalgae import history as hist
from caalgae import site as site_mod
from caalgae import snapshot, wording
from caalgae.normalize import Record, water_key
from caalgae.sources import CA_SWRCB_FHAB

RUN = dt.date(2026, 11, 3)
TIERS = {
    "Danger": "danger",
    "Warning": "warning",
    "Caution": "caution",
    "None": "no_advisory",
}
LEVEL_WORDS = re.compile(r"\b(Caution|Warning|Danger)\b")
_TAG = re.compile(r"<[^>]+>")


def rec(rid: str, name: str, county: str, day: str, level: str, n: int = 0) -> Record:
    tier = TIERS[level]
    return Record(
        id=rid,
        source=CA_SWRCB_FHAB.id,
        state="CA",
        site_id=f"r{rid}",
        water_key=water_key(name, county),
        water_name=name,
        county_text=county,
        landmark="Boat ramp",
        lat=34.0 + n * 0.01,
        lon=-118.0,
        date=dt.date.fromisoformat(day),
        level=level,
        tier=tier,
        explicit_no_advisory=tier == "no_advisory",
        end_date=None,
        detail="",
        stamp=None,
    )


def summer_lake() -> list[Record]:
    """Five records, all in summer, from 2019: indexed (five or more), and
    its records cover every winter since 2019-20."""
    return [
        rec(f"9{i}", "Summer Lake", "Kern", day, level, i)
        for i, (day, level) in enumerate(
            [
                ("2019-07-10", "Caution"),
                ("2020-08-12", "Warning"),
                ("2021-06-01", "Danger"),
                ("2023-09-15", "Caution"),
                ("2024-10-03", "None"),
            ]
        )
    ]


def castaic() -> list[Record]:
    """Winter advisories in two winters, last winter's latest on Feb 19."""
    return [
        rec(f"8{i}", "Castaic Lake", "Los Angeles", day, level, i)
        for i, (day, level) in enumerate(
            [
                ("2024-12-02", "Caution"),
                ("2025-11-10", "Warning"),
                ("2025-12-15", "Danger"),
                ("2026-02-19", "Caution"),
                ("2026-06-01", "Danger"),
                ("2026-09-01", "None"),
            ]
        )
    ]


def snap_of(records: list[Record], run: dt.date = RUN) -> dict[str, Any]:
    h = hist.merge(hist.empty(), records, run_date=run, file_info=INFO)
    snap = snapshot.build(
        h,
        run_date=run,
        generated_at=dt.datetime(run.year, run.month, run.day, 14, tzinfo=dt.UTC),
        quarantine=Counter(),
    )
    snapshot.validate(snap)
    return snap


def water_named(snap: dict[str, Any], name: str) -> dict[str, Any]:
    (w,) = [w for w in snap["waterbodies"] if w["name"] == name]
    return w


def months_of(snap: dict[str, Any]) -> dict[str, Any] | None:
    return site_mod.state_months(snap["waterbodies"], advisories_only=False)


def page_text(root: Path, water: dict[str, Any]) -> str:
    raw = (root / "water" / water["id"] / "index.html").read_text(encoding="utf-8")
    return html.unescape(re.sub(r"\s+", " ", _TAG.sub(" ", raw)))


def winter_section(root: Path, water: dict[str, Any]) -> str | None:
    raw = (root / "water" / water["id"] / "index.html").read_text(encoding="utf-8")
    m = re.search(r'<section class="winter-records".*?</section>', raw, re.S)
    if not m:
        return None
    return html.unescape(re.sub(r"\s+", " ", _TAG.sub(" ", m.group(0)))).strip()


def dogs_section(root: Path, water: dict[str, Any]) -> str:
    raw = (root / "water" / water["id"] / "index.html").read_text(encoding="utf-8")
    m = re.search(r'<h2 id="dogs">.*?(?=<h2 |<section )', raw, re.S)
    assert m
    return html.unescape(re.sub(r"\s+", " ", _TAG.sub(" ", m.group(0)))).strip()


# -- the counts -----------------------------------------------------------------


def test_winter_of_and_the_last_whole_winter() -> None:
    assert site_mod.winter_of(dt.date(2025, 11, 1)) == 2025
    assert site_mod.winter_of(dt.date(2026, 2, 28)) == 2025
    assert site_mod.winter_of(dt.date(2026, 3, 1)) is None
    assert site_mod.winter_of(dt.date(2025, 10, 31)) is None
    assert site_mod.last_whole_winter(dt.date(2026, 11, 3)) == 2025
    assert site_mod.last_whole_winter(dt.date(2027, 2, 27)) == 2025
    assert site_mod.last_whole_winter(dt.date(2027, 3, 1)) == 2026


def test_castaic_counts_its_own_winter_advisories_by_winter() -> None:
    snap = snap_of(castaic())
    w = water_named(snap, "Castaic Lake")
    got = site_mod.winter_record(w, RUN, months_of(snap))
    assert got is not None and got["kind"] == "advisories"
    assert got["count"] == 4
    assert got["latest"] == {"date": "2026-02-19", "tier": "caution", "level": "Caution"}
    assert got["last_winter"] == {
        "label": "November 2025 through February 2026",
        "count": 3,
        "last_date": "2026-02-19",
    }
    assert got["winters"] == [
        {
            "label": "November 2025 through February 2026",
            "count": 3,
            "highest": "Danger advisory",
            "last_date": "2026-02-19",
        },
        {
            "label": "November 2024 through February 2025",
            "count": 1,
            "highest": "Caution advisory",
            "last_date": "2024-12-02",
        },
    ]
    lines = wording.winter_lines(w["name"], got)
    assert lines == [
        "In past winters (November through February), the state posted 4 "
        "advisory records for Castaic Lake.",
        "The latest winter posting was on Feb 19, 2026: Caution advisory.",
        "Last winter (November 2025 through February 2026) it posted 3 advisory "
        "records, the last on Feb 19, 2026.",
        wording.WINTER_ENDS,
    ]


def test_elsinore_winter_counts_match_the_states_records() -> None:
    """Elsinore's real records (file dated 2026-11-03): one winter advisory,
    Danger on 2022-12-08. The 2026-01-05 "None" is a winter record but not an
    advisory, so last winter has no advisory and no last-winter sentence."""
    snap = snap_of(elsinore())
    w = snap["waterbodies"][0]
    winter_days = [
        r["date"]
        for r in w["records"]
        if site_mod.winter_of(dt.date.fromisoformat(r["date"])) is not None
    ]
    assert sorted(winter_days) == ["2022-12-08", "2026-01-05"]
    got = site_mod.winter_record(w, RUN, months_of(snap))
    assert got is not None and got["kind"] == "advisories"
    assert got["count"] == 1
    assert got["latest"]["date"] == "2022-12-08"
    assert got["last_winter"] is None


def test_negative_control_a_winter_none_is_not_counted_as_an_advisory() -> None:
    """Sabotage: the 2026-01-05 "None" made a Danger. The count and last
    winter must change, or the test above proves nothing."""
    sabotaged = [
        dataclasses.replace(r, level="Danger", tier="danger", explicit_no_advisory=False)
        if r.id == "13297"
        else r
        for r in elsinore()
    ]
    assert any(r.id == "13297" and r.tier == "danger" for r in sabotaged)
    snap = snap_of(sabotaged)
    got = site_mod.winter_record(snap["waterbodies"][0], RUN, months_of(snap))
    assert got is not None
    assert got["count"] == 2
    assert got["last_winter"] is not None and got["last_winter"]["count"] == 1


def test_withdrawn_records_are_not_counted() -> None:
    snap = snap_of(castaic())
    w = water_named(snap, "Castaic Lake")
    withdrawn = {
        **w,
        "records": [
            {**r, "removed_from_source": "2026-03-01"} if r["date"] == "2024-12-02" else r
            for r in w["records"]
        ],
    }
    got = site_mod.winter_record(withdrawn, RUN, months_of(snap))
    assert got is not None and got["count"] == 3
    assert [row["label"] for row in got["winters"]] == [
        "November 2025 through February 2026"
    ]


def test_state_months_come_from_the_file() -> None:
    snap = snap_of(castaic() + summer_lake())
    months = months_of(snap)
    assert months is not None
    # Castaic: Nov 1, Dec 2, Feb 1, Jun 1, Sep 1; Summer Lake: Jul, Aug, Jun, Sep, Oct.
    assert (months["november"], months["december"], months["january"]) == (1, 2, 0)
    assert months["february"] == 1
    # A tie for the peak goes to the earliest month: June, September and
    # December each have 2.
    assert (months["peak"], months["peak_month"]) == (2, "June")
    adv = site_mod.state_months(snap["waterbodies"], advisories_only=True)
    assert adv is not None
    # The two "None" records (Sep and Oct) drop out.
    assert adv["months_with"] == months["months_with"] - 1
    # Control: one more December record must move the count, so it is not
    # a number written into the code.
    more = snap_of([*castaic(), rec("77", "Castaic Lake", "Los Angeles", "2023-12-01", "Caution", 9)])
    again = months_of(more)
    assert again is not None and again["december"] == 3


def test_a_water_with_no_winter_record_gets_the_not_a_finding_sentence() -> None:
    snap = snap_of(castaic() + summer_lake())
    w = water_named(snap, "Summer Lake")
    got = site_mod.winter_record(w, RUN, months_of(snap))
    assert got is not None and got["kind"] == "absent"
    (line,) = wording.winter_lines(w["name"], got)
    assert line == (
        "None of the state's records for Summer Lake, which begin on Jul 10, "
        "2019, were posted in November through February. That is not a finding "
        "that the water is free of toxic algae: across the state's file, 2 "
        "records were posted in all Decembers on file, against 2 in all "
        "Junes."
    )
    assert not LEVEL_WORDS.search(line)
    assert "no advisory" not in line.casefold()
    assert affirmative_safety_claims(line) == []


def test_a_record_that_starts_after_last_winter_cannot_say() -> None:
    late = [
        rec(f"6{i}", "New Pond", "Kern", day, "Caution", i)
        for i, day in enumerate(
            ["2026-04-01", "2026-05-01", "2026-06-01", "2026-07-01", "2026-08-01"]
        )
    ]
    snap = snap_of(late)
    got = site_mod.winter_record(snap["waterbodies"][0], RUN, months_of(snap))
    assert got == {"kind": "uncovered", "first": "2026-04-01"}
    (line,) = wording.winter_lines("New Pond", got)
    assert "cannot say" in line and "None of the state's records" not in line


def test_winter_records_with_no_advisory_level() -> None:
    days = ["2023-12-01", "2024-07-01", "2024-08-01", "2025-07-01", "2025-08-01"]
    records = [
        rec(f"5{i}", "Quiet Lake", "Kern", day, "None" if i == 0 else "Caution", i)
        for i, day in enumerate(days)
    ]
    snap = snap_of(records)
    got = site_mod.winter_record(snap["waterbodies"][0], RUN, months_of(snap))
    assert got == {"kind": "no_advisory_level", "any_count": 1}
    (line,) = wording.winter_lines("Quiet Lake", got)
    assert line.startswith("The state posted 1 record for Quiet Lake")
    assert "not a finding" in line


def test_every_winter_line_passes_the_never_safe_guard() -> None:
    for line in [
        wording.WINTER_TOTAL,
        wording.WINTER_LATEST,
        wording.WINTER_LAST,
        wording.WINTER_ENDS,
        wording.WINTER_NO_LEVEL,
        wording.WINTER_ABSENT,
        wording.WINTER_UNCOVERED,
        wording.DOGS_WINTER_POSTED,
        wording.DOGS_WINTER_NO_LEVEL,
        wording.DOGS_WINTER_ABSENT,
        wording.DOGS_PAGE_WINTER,
    ]:
        assert affirmative_safety_claims(line) == [], line
        assert "all clear" not in line.casefold()
        assert "all-clear" not in line.casefold()


# -- the built pages ------------------------------------------------------------


def test_built_pages_show_each_waters_winter_record(tmp_path: Path) -> None:
    snap = snap_of(castaic() + summer_lake())
    site_mod.build_site(snap, tmp_path, ga4_measurement_id="")
    castaic_w = water_named(snap, "Castaic Lake")
    summer_w = water_named(snap, "Summer Lake")

    c = winter_section(tmp_path, castaic_w)
    assert c is not None
    assert c.startswith("Winter records at Castaic Lake")
    assert "the state posted 4 advisory records for Castaic Lake" in c
    assert "November 2024 through February 2025 1 Caution advisory Dec 2, 2024" in c
    assert "winter does not end it" in c
    assert "That is not a finding that the water is free of toxic algae:" not in c

    s = winter_section(tmp_path, summer_w)
    assert s is not None
    assert "That is not a finding that the water is free of toxic algae:" in s
    # The negative control's check: a winter-free water renders no level, no
    # count of zero and no "no advisory" in its winter section or its dogs line.
    assert not LEVEL_WORDS.search(s), s
    assert "no advisory" not in s.casefold()
    assert not re.search(r"\b0\b", s), s
    assert "<table" not in (tmp_path / "water" / summer_w["id"] / "index.html").read_text().split('class="winter-records"')[1].split("</section>")[0]

    # Run date Nov 3 is in winter: each dogs section carries its winter line.
    assert wording.DOGS_WINTER_POSTED in dogs_section(tmp_path, castaic_w)
    summer_dogs = dogs_section(tmp_path, summer_w)
    assert wording.DOGS_WINTER_ABSENT in summer_dogs
    assert wording.DOGS_WINTER_POSTED not in summer_dogs


def test_negative_control_the_absence_sentence_needs_a_winter_free_record(
    tmp_path: Path,
) -> None:
    """Sabotage: Castaic's winter records moved to October. The absence
    sentence must then appear on its page, so the check that it is missing
    above can see it."""
    moved = [
        dataclasses.replace(r, date=dt.date(r.date.year, 10, 15))
        if r.date.month in (11, 12, 1, 2)
        else r
        for r in castaic()
    ]
    assert not any(r.date.month in (11, 12, 1, 2) for r in moved)
    snap = snap_of(moved + summer_lake())
    site_mod.build_site(snap, tmp_path, ga4_measurement_id="")
    c = winter_section(tmp_path, water_named(snap, "Castaic Lake"))
    assert c is not None
    assert "That is not a finding that the water is free of toxic algae:" in c


def test_no_dogs_winter_line_outside_winter(tmp_path: Path) -> None:
    run = dt.date(2026, 10, 15)
    snap = snap_of(castaic(), run)
    site_mod.build_site(snap, tmp_path, ga4_measurement_id="")
    w = water_named(snap, "Castaic Lake")
    assert wording.DOGS_WINTER_POSTED not in dogs_section(tmp_path, w)
    # The section itself stays: last winter's record does not expire in March.
    assert winter_section(tmp_path, w) is not None


def test_a_page_that_is_not_indexed_gets_no_winter_section(tmp_path: Path) -> None:
    thin = [rec("41", "Thin Pond", "Kern", "2019-12-01", "Caution")]
    snap = snap_of(castaic() + thin)
    site_mod.build_site(snap, tmp_path, ga4_measurement_id="")
    w = water_named(snap, "Thin Pond")
    assert not site_mod.is_indexable(w, RUN, site_mod.INDEX_WINDOW_MONTHS)
    assert winter_section(tmp_path, w) is None
    assert "Winter records" not in page_text(tmp_path, w)


def test_the_dogs_page_gives_the_states_winter_counts(tmp_path: Path) -> None:
    snap = snap_of(castaic() + summer_lake())
    site_mod.build_site(snap, tmp_path, ga4_measurement_id="")
    raw = (tmp_path / "dogs" / "index.html").read_text(encoding="utf-8")
    text = html.unescape(re.sub(r"\s+", " ", _TAG.sub(" ", raw)))
    adv = site_mod.state_months(snap["waterbodies"], advisories_only=True)
    assert adv is not None
    line = wording.dogs_page_winter(adv)
    assert line is not None
    assert f"In winter , {line}" in text or f"In winter, {line}" in text
    assert f"{adv['december']} from Decembers" in line
    assert affirmative_safety_claims(line) == []


def test_the_dogs_page_says_nothing_of_winter_without_a_winter_advisory(
    tmp_path: Path,
) -> None:
    snap = snap_of(summer_lake())
    site_mod.build_site(snap, tmp_path, ga4_measurement_id="")
    raw = (tmp_path / "dogs" / "index.html").read_text(encoding="utf-8")
    assert "In winter" not in raw
    # Control: with Castaic's winter advisories the line is there.
    with_winter = tmp_path / "with"
    site_mod.build_site(snap_of(summer_lake() + castaic()), with_winter, ga4_measurement_id="")
    assert "In winter" in (with_winter / "dogs" / "index.html").read_text(encoding="utf-8")


def test_history_only_elsinore_is_unchanged_by_the_section_order(tmp_path: Path) -> None:
    """The section follows "Advisory history" and precedes "Source"."""
    snap = snap_of(history_only())
    site_mod.build_site(snap, tmp_path, ga4_measurement_id="")
    raw = (tmp_path / "water" / snap["waterbodies"][0]["id"] / "index.html").read_text()
    assert raw.index('id="history"') < raw.index('id="winter"') < raw.index('id="source"')
