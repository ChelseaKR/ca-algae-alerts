"""A short or reshaped California file must not flip live advisories
(docs/DECISIONS.md 0025).

The source-outage audit of 2026-11-05 dropped the newest 5% of advisory rows
from the real history and watched 10 waters flip from a current advisory to
"recommends no advisory". These tests run that cut on the committed
history.json, show the old 5% guard lets it through (the sabotage applies),
and show the new limits refuse it. Each limit is tested at its boundary.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from caalgae import cli, missouri, normalize, wording
from caalgae import history as hist
from caalgae import status as st
from caalgae.snapshot import status_json
from caalgae.sources import CA_SWRCB_FHAB

HISTORY = Path(__file__).resolve().parents[1] / "data" / "history.json"
RUN = dt.date(2026, 11, 6)
INFO = {"file_date": "2026-11-05", "source": CA_SWRCB_FHAB.id}


@pytest.fixture(scope="module")
def real() -> hist.History:
    return hist.load(HISTORY)


def _ca_active(h: hist.History) -> list[normalize.Record]:
    return [
        e.record
        for e in h.entries.values()
        if e.active and e.record.source == CA_SWRCB_FHAB.id
    ]


def _strict(h: hist.History, records: list[normalize.Record]) -> hist.History:
    return hist.merge(
        h,
        records,
        run_date=RUN,
        file_info=INFO,
        max_removed=hist.MAX_REMOVED_RECORDS,
        protect_advisories=True,
    )


def test_real_history_is_accepted_as_is(real: hist.History) -> None:
    """Negative control: today's file, unchanged, passes every limit."""
    merged = _strict(real, _ca_active(real))
    assert len(merged.active_records()) == len(real.active_records())


def test_a_four_percent_newest_cut_is_refused(real: hist.History) -> None:
    records = _ca_active(real)
    advisories = sorted(
        (r for r in records if r.is_advisory), key=normalize.Record.sort_key
    )
    cut = {r.id for r in advisories[-int(len(advisories) * 0.04) :]}
    short = [r for r in records if r.id not in cut]
    # The sabotage applies: the cut is under the old 5% limit, so the old
    # guard alone lets it through, and it does withdraw live advisories.
    assert len(cut) < hist.MAX_REMOVED_FRACTION * len(records)
    hist.merge(real, short, run_date=RUN, file_info=INFO)
    live = hist._current_advisories(real.entries, CA_SWRCB_FHAB.id)
    assert cut & live
    with pytest.raises(hist.HistoryError, match="withdraw"):
        _strict(real, short)


def _not_deciding(records: list[normalize.Record]) -> list[normalize.Record]:
    return [r for r in records if r.tier == "not_classified"]


def test_the_absolute_cap_is_exact(real: hist.History) -> None:
    records = _ca_active(real)
    spare = _not_deciding(records)
    assert len(spare) > hist.MAX_REMOVED_RECORDS
    at_cap = {r.id for r in spare[: hist.MAX_REMOVED_RECORDS]}
    over = {r.id for r in spare[: hist.MAX_REMOVED_RECORDS + 1]}
    merged = _strict(real, [r for r in records if r.id not in at_cap])
    assert sum(1 for e in merged.entries.values() if e.removed_from_source) - sum(
        1 for e in real.entries.values() if e.removed_from_source
    ) == len(at_cap)
    with pytest.raises(hist.HistoryError, match="more than the 25"):
        _strict(real, [r for r in records if r.id not in over])


def test_one_current_advisory_withdrawn_is_refused(real: hist.History) -> None:
    records = _ca_active(real)
    live = sorted(hist._current_advisories(real.entries, CA_SWRCB_FHAB.id))
    assert live
    without = [r for r in records if r.id != live[0]]
    with pytest.raises(hist.HistoryError, match="1 current advisory"):
        _strict(real, without)
    # The owner's override, after reading the file, lets it through.
    merged = hist.merge(real, without, run_date=RUN, file_info=INFO)
    assert merged.entries[live[0]].removed_from_source == RUN.isoformat()


def test_a_superseded_advisory_may_be_withdrawn(real: hist.History) -> None:
    """Negative control: an advisory that a later record already decided is
    not current, so its withdrawal changes no status and passes."""
    records = _ca_active(real)
    live = hist._current_advisories(real.entries, CA_SWRCB_FHAB.id)
    old = next(r for r in records if r.is_advisory and r.id not in live)
    _strict(real, [r for r in records if r.id != old.id])


# -- an unrecognized level ---------------------------------------------------


def _rec(rid: str, day: int, level: str, site: str = "s1") -> normalize.Record:
    tier = normalize.tier_of(level)
    return normalize.Record(
        id=rid,
        source=CA_SWRCB_FHAB.id,
        state="CA",
        site_id=site,
        water_key="ca|alameda|lake temescal",
        water_name="Lake Temescal",
        county_text="Alameda",
        landmark="",
        lat=None,
        lon=None,
        date=dt.date(2026, 10, day),
        level=level,
        tier=tier,
        explicit_no_advisory=tier == "no_advisory",
        end_date=None,
        detail="",
        stamp=None,
    )


def test_a_new_level_after_none_reads_unknown_not_no_advisory() -> None:
    records = [
        _rec("1", 1, "Danger"),
        _rec("2", 10, "None"),
        _rec("3", 20, "Danger - Closure"),
    ]
    s = st.site_status(records, RUN)
    assert s.kind == st.UNDETERMINED
    assert s.level == "Danger - Closure"
    line = wording.headline(status_json(s))
    assert "recommends no advisory" not in line
    assert "Danger - Closure" in line
    # Negative control: the same row with a blank level decides nothing, and
    # the "None" still speaks, so the rule above is what changed the answer.
    blank = [*records[:2], dataclasses.replace(records[2], level="", tier="unknown")]
    assert st.site_status(blank, RUN).kind == st.NO_ADVISORY_RECORDED


def test_an_unrecognized_spot_outranks_another_spots_none() -> None:
    lifted = st.site_status([_rec("1", 1, "Danger"), _rec("2", 10, "None")], RUN)
    unread = st.site_status([_rec("3", 20, "Danger - Closure", site="s2")], RUN)
    water = st.water_status([lifted, unread], RUN)
    assert water.kind == st.UNDETERMINED
    assert water.level == "Danger - Closure"
    # An advisory anywhere still leads.
    open_ = st.site_status([_rec("4", 21, "Caution", site="s3")], RUN)
    assert st.water_status([lifted, unread, open_], RUN).kind == st.ADVISORY
    # Without the unrecognized spot the water reads as lifted (control).
    assert st.water_status([lifted], RUN).kind == st.NO_ADVISORY_RECORDED


def test_a_later_none_still_ends_an_unrecognized_level() -> None:
    s = st.site_status([_rec("1", 1, "Danger - Closure"), _rec("2", 10, "None")], RUN)
    assert s.kind == st.NO_ADVISORY_RECORDED


def test_unrecognized_dog_answer_never_clears() -> None:
    s = status_json(st.site_status([_rec("3", 20, "Danger - Closure")], RUN))
    answer = wording.dog_answer("Lake Temescal", s)
    assert "keep your dog out" in answer


def test_missouri_unlisted_code_is_unrecognized_but_blank_is_not() -> None:
    def feature(code: str) -> dict[str, object]:
        return {
            "attributes": {
                "objectid": 9,
                "WBName": "Truman Lake",
                "HABODat": 1791046800000,
                "BloomStat": code,
                "CaseStatus": "Open",
                "DissDat": None,
            },
            "geometry": {"x": -93.4, "y": 38.2},
        }

    new = missouri._record(feature("closure"), dt.date(2026, 10, 12))
    blank = missouri._record(feature(""), dt.date(2026, 10, 12))
    listed = missouri._record(feature("notthr"), dt.date(2026, 10, 12))
    assert isinstance(new, normalize.Record) and new.is_unrecognized
    assert isinstance(blank, normalize.Record) and not blank.is_unrecognized
    assert isinstance(listed, normalize.Record) and not listed.is_unrecognized


# -- the quarantine ceiling --------------------------------------------------


def _with_quarantine(count: int) -> hist.History:
    return hist.History(
        entries={}, files=[{"source": CA_SWRCB_FHAB.id, "quarantined": count}]
    )


def _normalized(quarantined: int) -> normalize.Normalized:
    return normalize.Normalized(
        records=[],
        quarantine=Counter({"missing or unreadable advisory date": quarantined}),
        rows_read=quarantined,
    )


def test_a_quarantine_jump_is_refused_at_its_boundary() -> None:
    h = _with_quarantine(249)
    cli._check_quarantine(h, _normalized(249 + cli.MAX_QUARANTINE_GROWTH), accept=False)
    with pytest.raises(cli.RunRefused, match="quarantines 275 rows, up from 249"):
        cli._check_quarantine(
            h, _normalized(249 + cli.MAX_QUARANTINE_GROWTH + 1), accept=False
        )
    # The override, and a first run with nothing to compare, pass.
    cli._check_quarantine(h, _normalized(5000), accept=True)
    cli._check_quarantine(hist.empty(), _normalized(5000), accept=False)


def test_the_cli_applies_the_limits_and_the_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The flag is wired: without it the California merge gets both limits;
    with it, neither. Missouri's merge never gets them."""
    from paths import PAGE, TRAPS

    seen: list[tuple[str, object, object]] = []
    real_merge = hist.merge

    def spy(*a: Any, **k: Any) -> hist.History:
        info = k["file_info"]
        seen.append((info["source"], k.get("max_removed"), k.get("protect_advisories")))
        return real_merge(*a, **k)

    monkeypatch.setattr(hist, "merge", spy)
    base = [
        "--fixture-page",
        str(PAGE),
        "--fixture-csv",
        str(TRAPS),
        "--run-today",
        "2026-10-12",
        "--history",
        str(tmp_path / "h.json"),
    ]
    assert cli.main(base) == 0
    assert seen[-1] == (CA_SWRCB_FHAB.id, hist.MAX_REMOVED_RECORDS, True)
    assert cli.main([*base, "--accept-ca-edits"]) == 0
    assert seen[-1] == (CA_SWRCB_FHAB.id, None, False)
