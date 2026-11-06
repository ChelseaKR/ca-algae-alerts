"""Decision 0022: a California report whose landmark is the same as
another's, once a trailing "(CODE)", case and spacing are set aside, and
whose latest coordinates are within 25 m of the other's, is the same spot.

The records are the state's, from the file dated 2026-11-03
(Response_Action_IDs, report ids, dates, levels, coordinates and landmarks
as published). Each pair was two spots under 0017's exact-coordinate rule,
so an old advisory stayed open beside a newer "None" a few meters away.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
from collections import Counter
from typing import Any

import pytest

from caalgae import history as hist
from caalgae import snapshot
from caalgae.normalize import Record, water_key
from caalgae.sources import CA_SWRCB_FHAB

RUN = dt.date(2026, 11, 3)
INFO = {
    "source": "ca-swrcb-fhab",
    "url": "https://publish.data.ca.gov/x/hab-responses_2026-11-03.csv",
    "file_name": "hab-responses_2026-11-03.csv",
    "file_date": "2026-11-03",
    "fetched_at": "2026-11-03T14:00:00Z",
    "rows_read": 10,
    "quarantined": 0,
}
TIERS = {"Danger": "danger", "Caution": "caution", "None": "no_advisory"}


def rec(
    water: tuple[str, str],
    rid: str,
    report: str,
    day: str,
    level: str,
    lat: float,
    lon: float,
    landmark: str,
) -> Record:
    name, county = water
    tier = TIERS[level]
    return Record(
        id=rid,
        source=CA_SWRCB_FHAB.id,
        state="CA",
        site_id=report,
        water_key=water_key(name, county),
        water_name=name,
        county_text=county,
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


HAVASU = ("Lake Havasu", "San Bernardino")
ANTELOPE = ("Antelope Creek", "Tehama")
FOUR_ISLAND = ("Four Island Lake", "Kern")
MCLEOD = ("McLeod Lake", "San Joaquin")


def havasu() -> list[Record]:
    return [
        rec(HAVASU, "5139", "3818", "2022-12-09", "Danger", 34.428813, -114.31938,
            "Skiers Island"),
        rec(HAVASU, "13602", "4788", "2026-04-16", "None", 34.428813, -114.31936,
            "Skiers Island (714SKIERS)"),
    ]  # fmt: skip


def antelope() -> list[Record]:
    return [
        rec(ANTELOPE, "1144", "3025", "2021-09-09", "Caution", 40.26488, -121.76809,
            "MF ~0.4mi above Ponderosa Way"),
        rec(ANTELOPE, "14183", "5158", "2026-06-24", "None", 40.2649, -121.76808,
            "MF ~0.4mi above Ponderosa Way (509PS0170)"),
    ]  # fmt: skip


def four_island() -> list[Record]:
    return [
        rec(FOUR_ISLAND, "3250", "3462", "2022-08-08", "Caution", 35.162126,
            -118.65771, "Bear Valley Springs"),
        rec(FOUR_ISLAND, "13400", "5023", "2026-02-04", "None", 35.16216,
            -118.65792, "Bear valley springs"),
    ]  # fmt: skip


def water(records: list[Record]) -> dict[str, Any]:
    h = hist.merge(hist.empty(), records, run_date=RUN, file_info=INFO)
    snap = snapshot.build(
        h,
        run_date=RUN,
        generated_at=dt.datetime(2026, 11, 3, 14, tzinfo=dt.UTC),
        quarantine=Counter(),
    )
    snapshot.validate(snap)
    (only,) = snap["waterbodies"]
    return only


@pytest.mark.parametrize(
    ("landmark", "key"),
    [
        ("Skiers Island (714SKIERS)", "skiers island"),
        ("Skiers Island", "skiers island"),
        ("  Bear   valley Springs ", "bear valley springs"),
        ("Oaks Arm (DWR site CL-4)", "oaks arm"),
        ("Morelli Park Boat Launch", "morelli park boat launch"),
        ("Morelli Park (MP)", "morelli park"),
        ("(MP)", ""),
        ("Inlet (north) channel", "inlet (north) channel"),
    ],
)
def test_landmark_key_drops_only_a_trailing_code(landmark: str, key: str) -> None:
    assert snapshot.landmark_key(landmark) == key


def test_meters_apart_measures_the_audit_cases() -> None:
    a, b = havasu()
    assert snapshot.meters_apart((a.lat, a.lon), (b.lat, b.lon)) == pytest.approx(
        1.84, abs=0.05
    )
    c, d = four_island()
    assert snapshot.meters_apart((c.lat, c.lon), (d.lat, d.lon)) == pytest.approx(
        19.5, abs=0.5
    )


@pytest.mark.parametrize(
    ("records", "spot", "lift"),
    [
        (havasu, "4788", "2026-04-16"),
        (antelope, "5158", "2026-06-24"),
        (four_island, "5023", "2026-02-04"),
    ],
)
def test_a_renamed_spot_nearby_ends_the_old_advisory(
    records: Any, spot: str, lift: str
) -> None:
    w = water(records())
    assert [s["id"] for s in w["sites"]] == [spot]
    (site,) = w["sites"]
    assert site["status"]["kind"] == "no_advisory_recorded"
    assert site["status"]["lift_date"] == lift
    assert w["status"]["kind"] == "no_advisory_recorded"
    assert {r["site"] for r in w["records"]} == {spot}


def test_negative_control_a_different_name_meters_away_stays_open() -> None:
    """McLeod Lake: "Morelli Park Boat Launch" (Danger, 2020) is about 4 m
    from "Morelli Park (MP)" (None, 2026). The names differ after the code
    is dropped, so they stay two spots and the Danger stands."""
    records = [
        rec(MCLEOD, "799", "2330", "2020-09-04", "Danger", 37.95305, -121.30648,
            "Morelli Park Boat Launch"),
        rec(MCLEOD, "15407", "3266", "2026-10-01", "None", 37.95301, -121.30646,
            "Morelli Park (MP)"),
    ]  # fmt: skip
    a, b = records
    assert snapshot.meters_apart((a.lat, a.lon), (b.lat, b.lon)) < 25  # it applies
    w = water(records)
    sites = {s["id"]: s for s in w["sites"]}
    assert set(sites) == {"2330", "3266"}
    assert sites["2330"]["status"]["kind"] == "advisory"
    assert w["status"]["kind"] == "advisory"


def test_negative_control_the_same_name_past_25_m_stays_open() -> None:
    """Move Havasu's None 0.0003 degrees of latitude (about 33 m). The rule
    no longer applies, so the 2022 Danger stands, and the test above fails
    if the distance check is switched off."""
    moved = [
        dataclasses.replace(r, lat=r.lat + 0.0003) if r.id == "13602" else r
        for r in havasu()
    ]
    a, b = moved
    assert snapshot.meters_apart((a.lat, a.lon), (b.lat, b.lon)) > 25  # it applied
    w = water(moved)
    sites = {s["id"]: s for s in w["sites"]}
    assert set(sites) == {"3818", "4788"}
    assert sites["3818"]["status"]["kind"] == "advisory"
    assert w["status"]["kind"] == "advisory"


def test_an_empty_name_is_never_matched() -> None:
    a, b = (dataclasses.replace(r, landmark="(SKI)") for r in havasu())
    w = water([a, b])
    assert {s["id"] for s in w["sites"]} == {"3818", "4788"}


def test_other_sources_are_not_matched_by_name() -> None:
    a, b = (dataclasses.replace(r, source="mo-dnr-hab") for r in havasu())
    assert snapshot.spot_ids(
        [
            hist.HistoryEntry(record=r, first_seen="2026-11-03", last_seen="2026-11-03")
            for r in (a, b)
        ]
    ) == {"3818": "3818", "4788": "4788"}


@pytest.mark.parametrize(
    ("landmark", "code"),
    [
        ("Nuwuvi Park (714NVWVVI-01)", "714nvwvvi-01"),
        ("Oaks Arm (DWR site  CL-4)", "dwr site cl-4"),
        ("Skiers Island", None),
        ("(MP)", "mp"),
    ],
)
def test_landmark_code_is_the_trailing_parenthetical(
    landmark: str, code: str | None
) -> None:
    assert snapshot.landmark_code(landmark) == code


# Lake Havasu's two Nuwuvi Park stations, at the state's shared point. The
# levels and the moves below are constructed: on the 2026-11-03 file the two
# stations share coordinates, so they are one spot by 0017 already. The
# tests ask what happens if the state moves one of them a few meters.
NUWUVI = (34.49911, -114.39853)
NORTH_20_M = 0.00018  # degrees of latitude, about 20 m


def nuwuvi(station: str, rid: str, report: str, day: str, level: str, north: float,
           landmark: str | None = None) -> Record:  # fmt: skip
    return rec(HAVASU, rid, report, day, level, NUWUVI[0] + north, NUWUVI[1],
               landmark or f"Nuwuvi Park (714NVWVVI-{station})")  # fmt: skip


def test_negative_control_two_station_codes_nearby_stay_two_spots() -> None:
    """A Danger at -01 and a later None at -02, 20 m away. The names match
    once the codes are dropped, but the codes differ, so the None is at
    another station and the Danger stands (a false all-clear otherwise)."""
    records = [
        nuwuvi("01", "1", "4846", "2026-05-18", "Danger", 0.0),
        nuwuvi("02", "2", "4847", "2026-06-29", "None", NORTH_20_M),
    ]
    a, b = records
    assert snapshot.meters_apart((a.lat, a.lon), (b.lat, b.lon)) < 25  # it applies
    w = water(records)
    sites = {s["id"]: s for s in w["sites"]}
    assert set(sites) == {"4846", "4847"}
    assert sites["4846"]["status"]["kind"] == "advisory"
    assert w["status"]["kind"] == "advisory"


def test_the_same_station_code_nearby_is_still_one_spot() -> None:
    """The control for the test above: give -02 the code -01 and the two
    reports join, so the None ends the Danger. Only the code differs."""
    records = [
        nuwuvi("01", "1", "4846", "2026-05-18", "Danger", 0.0),
        nuwuvi("01", "2", "4847", "2026-06-29", "None", NORTH_20_M),
    ]
    w = water(records)
    assert [s["id"] for s in w["sites"]] == ["4847"]
    assert w["status"]["kind"] == "no_advisory_recorded"


def test_an_uncoded_name_between_two_codes_joins_only_the_nearer() -> None:
    """A plain "Nuwuvi Park", 7 m from -01 and 13 m from -02, matches both
    by name. It joins -01, its nearest, and -02 stays its own spot, so -02's
    None cannot end the Caution at -01 through it."""
    records = [
        nuwuvi("01", "1", "4846", "2025-06-05", "Danger", 0.0),
        nuwuvi("", "2", "5000", "2026-01-22", "Caution", 0.000063,
               landmark="Nuwuvi Park"),
        nuwuvi("02", "3", "4847", "2026-06-29", "None", NORTH_20_M),
    ]  # fmt: skip
    w = water(records)
    spot = {r["id"]: r["site"] for r in w["records"]}
    assert spot["1"] == spot["2"] == "5000"
    assert spot["3"] == "4847"
    sites = {s["id"]: s for s in w["sites"]}
    assert sites["5000"]["status"]["kind"] == "advisory"
    assert w["status"]["kind"] == "advisory"


def test_shared_coordinates_still_join_two_codes() -> None:
    """0017 is unchanged: "Oaks Arm (DWR site CL-4)" and "(CL-04)" at the
    same point are one spot, whatever their codes."""
    records = [
        nuwuvi("01", "1", "4846", "2026-05-18", "Danger", 0.0,
               landmark="Oaks Arm (DWR site CL-4)"),
        nuwuvi("02", "2", "4847", "2026-06-29", "None", 0.0,
               landmark="Oaks Arm (DWR site CL-04)"),
    ]  # fmt: skip
    w = water(records)
    assert [s["id"] for s in w["sites"]] == ["4847"]
