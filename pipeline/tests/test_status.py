"""The status rule, its traps, and negative controls that prove the trap
tests can fail."""

from __future__ import annotations

import dataclasses
import datetime as dt

import pytest
from paths import RUN_DATE

from caalgae import normalize
from caalgae import status as st


def _site(traps: normalize.Normalized, site_id: str) -> list[normalize.Record]:
    return [r for r in traps.records if r.site_id == site_id]


def test_blank_end_date_trap_advisory_stands(traps: normalize.Normalized) -> None:
    s = st.site_status(_site(traps, "101"), RUN_DATE)
    assert s.kind == st.ADVISORY
    assert s.tier == "caution"
    assert s.posted == dt.date(2026, 9, 20)
    assert s.lift_date is None


def test_explicit_none_lifts(traps: normalize.Normalized) -> None:
    s = st.site_status(_site(traps, "201"), RUN_DATE)
    assert s.kind == st.NO_ADVISORY_RECORDED
    assert s.lift_kind == "no_advisory_record"
    assert s.lift_date == dt.date(2026, 9, 1)
    assert s.last_advisory == dt.date(2026, 7, 1)


def test_na_record_does_not_lift(traps: normalize.Normalized) -> None:
    s = st.site_status(_site(traps, "301"), RUN_DATE)
    assert s.kind == st.ADVISORY and s.tier == "warning"


def test_recorded_past_end_date_lifts(traps: normalize.Normalized) -> None:
    s = st.site_status(_site(traps, "401"), RUN_DATE)
    assert s.kind == st.NO_ADVISORY_RECORDED
    assert s.lift_kind == "end_date"
    assert s.lift_date == dt.date(2025, 9, 30)


def test_future_end_date_does_not_lift_yet(traps: normalize.Normalized) -> None:
    s = st.site_status(_site(traps, "801"), RUN_DATE)
    assert s.kind == st.ADVISORY
    assert s.planned_end == dt.date(2026, 12, 31)
    after = st.site_status(_site(traps, "801"), dt.date(2027, 1, 1))
    assert after.kind == st.NO_ADVISORY_RECORDED


def test_old_advisory_with_no_lift_is_still_an_advisory(
    traps: normalize.Normalized,
) -> None:
    s = st.site_status(_site(traps, "601"), RUN_DATE)
    assert s.kind == st.ADVISORY
    assert s.posted == dt.date(2019, 7, 15)


def test_blank_level_only_is_undetermined_not_clear(
    traps: normalize.Normalized,
) -> None:
    s = st.site_status(_site(traps, "901"), RUN_DATE)
    assert s.kind == st.UNDETERMINED
    assert st.site_status([], RUN_DATE).kind == st.UNDETERMINED


def test_same_day_records_order_by_the_states_timestamp(
    traps: normalize.Normalized,
) -> None:
    s = st.site_status(_site(traps, "1001"), RUN_DATE)
    assert s.kind == st.ADVISORY


def test_water_takes_any_open_advisory_and_the_highest_tier(
    traps: normalize.Normalized,
) -> None:
    lifted = st.site_status(_site(traps, "401"), RUN_DATE)
    open_ = st.site_status(_site(traps, "402"), RUN_DATE)
    w = st.water_status([lifted, open_], RUN_DATE)
    assert w.kind == st.ADVISORY and w.tier == "other_advisory"
    assert w.sites_with_advisory == 1
    danger = dataclasses.replace(open_, tier="danger", posted=dt.date(2026, 1, 1))
    top = st.water_status([open_, danger], RUN_DATE)
    assert top.tier == "danger"
    # The date is the Danger's own, not the newer lower posting's (0017).
    assert open_.posted == dt.date(2026, 9, 25)
    assert top.posted == dt.date(2026, 1, 1)


def test_water_headline_date_belongs_to_its_level() -> None:
    """Lake Elsinore, 2026-11-03: a Danger last posted 2020-09-03 at one spot
    and Cautions posted 2026-09-24 at others read "Danger, posted Sep 24,
    2026". The headline's level and date must come from the same posting."""
    old_danger = st.Status(
        kind=st.ADVISORY,
        tier="danger",
        level="Danger",
        posted=dt.date(2020, 9, 3),
        sites_with_advisory=1,
    )
    new_caution = st.Status(
        kind=st.ADVISORY,
        tier="caution",
        level="Caution",
        posted=dt.date(2026, 9, 24),
        sites_with_advisory=1,
    )
    newer_danger = dataclasses.replace(old_danger, posted=dt.date(2026, 3, 10))
    w = st.water_status([new_caution, old_danger, newer_danger], dt.date(2026, 11, 3))
    assert (w.tier, w.level, w.posted) == ("danger", "Danger", dt.date(2026, 3, 10))
    assert w.sites_with_advisory == 3
    # Negative control: the old rule (newest date across every site) gives
    # the false pairing, so this test can fail.
    mixed = max(s.posted for s in (new_caution, old_danger, newer_danger) if s.posted)
    assert (w.tier, mixed) == ("danger", dt.date(2026, 9, 24))
    assert w.posted != mixed


def test_water_lifted_only_when_no_site_is_open(traps: normalize.Normalized) -> None:
    w = st.water_status([st.site_status(_site(traps, "201"), RUN_DATE)], RUN_DATE)
    assert w.kind == st.NO_ADVISORY_RECORDED
    assert (
        st.water_status([st.Status(kind=st.UNDETERMINED)], RUN_DATE).kind
        == st.UNDETERMINED
    )


# --- negative controls -----------------------------------------------------


def test_negative_control_removing_the_none_record_reopens_the_advisory(
    traps: normalize.Normalized,
) -> None:
    records = _site(traps, "201")
    without_none = [r for r in records if not r.explicit_no_advisory]
    assert len(without_none) == len(records) - 1  # the mutation landed
    assert st.site_status(without_none, RUN_DATE).kind == st.ADVISORY


def test_negative_control_a_blank_end_treated_as_ended_would_be_caught(
    traps: normalize.Normalized, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sabotage the rule the way the bug class does ("no end date" read as
    "ended"), check the sabotage applied, and check the trap test's own
    assertion would then fail."""
    records = _site(traps, "101")
    sabotaged = [dataclasses.replace(r, end_date=r.end_date or r.date) for r in records]
    assert all(r.end_date is not None for r in sabotaged)  # the mutation landed
    s = st.site_status(sabotaged, RUN_DATE)
    assert s.kind != st.ADVISORY  # so test_blank_end_date_trap would go red


def test_negative_control_na_counted_as_deciding_would_be_caught(
    traps: normalize.Normalized, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = st._deciding
    monkeypatch.setattr(
        st, "_deciding", lambda r: original(r) or r.tier == "not_classified"
    )
    assert st._deciding is not original  # the mutation landed
    s = st.site_status(_site(traps, "301"), RUN_DATE)
    # With NA deciding, the Warning is no longer what the site reports, so
    # test_na_record_does_not_lift would go red.
    assert s.tier != "warning"


# --- the 12-month headline rule (owner, 0017) ------------------------------


def _adv(tier: str, day: str) -> st.Status:
    return st.Status(
        kind=st.ADVISORY,
        tier=tier,
        level=tier.capitalize(),
        posted=dt.date.fromisoformat(day),
        sites_with_advisory=1,
    )


def test_window_start_is_twelve_calendar_months_back() -> None:
    assert st.window_start(dt.date(2026, 11, 3)) == dt.date(2025, 11, 3)
    assert st.window_start(dt.date(2028, 2, 29)) == dt.date(2027, 2, 28)


def test_highest_level_inside_the_window_leads() -> None:
    w = st.water_status(
        [_adv("caution", "2026-09-24"), _adv("warning", "2025-11-03")],
        dt.date(2026, 11, 3),
    )
    assert (w.tier, w.posted) == ("warning", dt.date(2025, 11, 3))  # on the edge
    w = st.water_status(
        [_adv("caution", "2026-09-24"), _adv("warning", "2025-11-02")],
        dt.date(2026, 11, 3),
    )
    assert (w.tier, w.posted) == ("caution", dt.date(2026, 9, 24))  # a day out


def test_nothing_in_the_window_leads_with_the_newest_posting() -> None:
    w = st.water_status(
        [_adv("danger", "2017-07-28"), _adv("caution", "2021-06-30")],
        dt.date(2026, 11, 3),
    )
    assert (w.tier, w.posted) == ("caution", dt.date(2021, 6, 30))
    assert w.sites_with_advisory == 2
    tie = st.water_status(
        [_adv("caution", "2021-06-30"), _adv("danger", "2021-06-30")],
        dt.date(2026, 11, 3),
    )
    assert tie.tier == "danger"
