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
    w = st.water_status([lifted, open_])
    assert w.kind == st.ADVISORY and w.tier == "other_advisory"
    assert w.sites_with_advisory == 1
    danger = dataclasses.replace(open_, tier="danger", posted=dt.date(2026, 1, 1))
    top = st.water_status([open_, danger])
    assert top.tier == "danger"
    assert top.posted == dt.date(2026, 9, 25)  # newest posting across sites


def test_water_lifted_only_when_no_site_is_open(traps: normalize.Normalized) -> None:
    w = st.water_status([st.site_status(_site(traps, "201"), RUN_DATE)])
    assert w.kind == st.NO_ADVISORY_RECORDED
    assert st.water_status([st.Status(kind=st.UNDETERMINED)]).kind == st.UNDETERMINED


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
