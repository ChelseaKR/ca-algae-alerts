from __future__ import annotations

import datetime as dt

import pytest
from paths import FILE_DATE, SAMPLE

from caalgae import normalize


def test_traps_fixture_quarantines_exactly_the_bad_rows(
    traps: normalize.Normalized,
) -> None:
    assert traps.rows_read == 17
    assert dict(traps.quarantine) == {
        "advisory date outside 2016 to the file's date": 1,
        "missing water body name": 1,
        "missing or unreadable advisory date": 1,
    }
    assert len(traps.records) == 14


def test_source_vocabulary_is_kept_and_mapped(traps: normalize.Normalized) -> None:
    by_level = {r.level: r.tier for r in traps.records}
    assert by_level["Caution"] == "caution"
    assert by_level["Danger"] == "danger"
    assert by_level["Warning"] == "warning"
    assert by_level["Algal mat alert sign"] == "other_advisory"
    assert by_level["None"] == "no_advisory"
    assert by_level["NA - refer to Report Details"] == "not_classified"
    assert by_level[""] == "unknown"


def test_only_the_states_none_is_an_explicit_no_advisory(
    traps: normalize.Normalized,
) -> None:
    flagged = {r.level for r in traps.records if r.explicit_no_advisory}
    assert flagged == {"None"}


def test_blank_end_date_stays_unknown(traps: normalize.Normalized) -> None:
    alpha = [r for r in traps.records if r.water_name == "Lake Alpha"]
    assert alpha and all(r.end_date is None for r in alpha)


def test_casing_variants_share_a_water_key(traps: normalize.Normalized) -> None:
    keys = {r.water_key for r in traps.records if r.water_name.lower() == "delta lake"}
    assert keys == {"riverside|delta lake"}


def test_coordinates_outside_california_or_blank_are_dropped() -> None:
    assert normalize.parse_coordinate("37.8", "-122.2") == (37.8, -122.2)
    assert normalize.parse_coordinate("", "") == (None, None)
    assert normalize.parse_coordinate("0", "0") == (None, None)
    assert normalize.parse_coordinate("x", "-122") == (None, None)


def test_counties_ignore_other_states() -> None:
    assert normalize.counties_of("Calaveras; Tuolumne") == ["Calaveras", "Tuolumne"]
    assert normalize.counties_of("Nevada State") == []
    assert normalize.counties_of("Nevada") == ["Nevada"]
    assert len(normalize.CA_COUNTIES) == 58


def test_date_formats() -> None:
    assert normalize.parse_date("10/9/2026 12:00:00 AM") == dt.date(2026, 10, 9)
    assert normalize.parse_date("2026-10-09") == dt.date(2026, 10, 9)
    assert normalize.parse_date("") is None
    assert normalize.parse_date("soon") is None
    assert normalize.parse_stamp("10/9/2026 3:59:09 PM") == dt.datetime(
        2026, 10, 9, 15, 59, 9
    )
    assert normalize.parse_stamp("") is None


def test_missing_column_is_a_shape_error() -> None:
    with pytest.raises(normalize.SourceShapeError, match="missing columns"):
        normalize.normalize_csv(b"Response_Action_ID,County\n1,Lake\n", FILE_DATE)


def test_header_only_file_is_a_shape_error() -> None:
    header = ",".join(normalize.REQUIRED_COLUMNS).encode()
    with pytest.raises(normalize.SourceShapeError, match="no rows"):
        normalize.normalize_csv(header + b"\n", FILE_DATE)


def test_duplicate_ids_are_a_shape_error() -> None:
    body = SAMPLE.read_bytes()
    lines = body.splitlines(keepends=True)
    with pytest.raises(normalize.SourceShapeError, match="appears twice"):
        normalize.normalize_csv(b"".join([*lines, lines[1]]), FILE_DATE)


def test_real_sample_reads_cleanly() -> None:
    result = normalize.normalize_csv(SAMPLE.read_bytes(), FILE_DATE)
    assert result.rows_read == 1890
    assert len(result.records) + sum(result.quarantine.values()) == 1890
    assert {r.state for r in result.records} == {"CA"}
    assert {r.source for r in result.records} == {"ca-swrcb-fhab"}
