from __future__ import annotations

import datetime as dt
import json
from collections import Counter
from pathlib import Path
from typing import Any

import pytest
from paths import RUN_DATE

from caalgae import history as hist
from caalgae import normalize, snapshot

ROOT = Path(__file__).resolve().parents[2]
INFO = {
    "source": "ca-swrcb-fhab",
    "url": "https://publish.data.ca.gov/x/hab-responses_2026-10-09.csv",
    "file_name": "hab-responses_2026-10-09.csv",
    "file_date": "2026-10-09",
    "fetched_at": "2026-10-12T13:00:00Z",
    "rows_read": 17,
    "quarantined": 3,
}


def build(traps: normalize.Normalized) -> dict[str, Any]:
    h = hist.merge(hist.empty(), traps.records, run_date=RUN_DATE, file_info=INFO)
    return snapshot.build(
        h,
        run_date=RUN_DATE,
        generated_at=dt.datetime(2026, 10, 12, 13, tzinfo=dt.UTC),
        quarantine=traps.quarantine,
        rows_read=traps.rows_read,
    )


def by_name(snap: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {w["name"]: w for w in snap["waterbodies"]}


def test_snapshot_validates_and_counts(traps: normalize.Normalized) -> None:
    snap = build(traps)
    snapshot.validate(snap)
    assert snap["quarantine"]["total"] == 3
    assert snap["source_file"]["newest_record_date"] == "2026-09-25"
    assert len(snap["waterbodies"]) == 9


def test_every_record_carries_its_source_and_every_water_its_state(
    traps: normalize.Normalized,
) -> None:
    snap = build(traps)
    assert {s["id"] for s in snap["sources"]} == {"ca-swrcb-fhab"}
    assert snap["sources"][0]["license"] == "Other (Public Domain)"
    for water in snap["waterbodies"]:
        assert water["state"] == "CA"
        assert water["id"].startswith("ca-")
        assert {r["source"] for r in water["records"]} == {"ca-swrcb-fhab"}


def test_statuses_in_the_snapshot(traps: normalize.Normalized) -> None:
    w = by_name(build(traps))
    assert w["Lake Alpha"]["status"]["kind"] == "advisory"
    assert w["Lake Alpha"]["status"]["posted"] == "2026-09-20"
    assert w["Beta Reservoir"]["status"]["kind"] == "no_advisory_recorded"
    assert w["Delta Lake"]["status"]["tier"] == "other_advisory"
    assert len(w["Delta Lake"]["sites"]) == 2
    assert w["Zeta Lake"]["counties"] == []
    assert w["Epsilon Creek"]["counties"] == ["Calaveras", "Tuolumne"]
    assert w["Theta Lake"]["status"]["kind"] == "undetermined"
    assert w["Delta Lake"]["center"] == {"lat": 33.8, "lon": -117.1}


def test_records_are_newest_first(traps: normalize.Normalized) -> None:
    alpha = by_name(build(traps))["Lake Alpha"]
    dates = [r["date"] for r in alpha["records"]]
    assert dates == sorted(dates, reverse=True)


def test_schema_rejects_an_advisory_without_a_posted_date(
    traps: normalize.Normalized,
) -> None:
    snap = build(traps)
    snap["waterbodies"][0]["status"] = {
        **snap["waterbodies"][0]["status"],
        "kind": "advisory",
        "posted": None,
        "tier": "caution",
    }
    with pytest.raises(snapshot.SnapshotError):
        snapshot.validate(snap)


def test_schema_rejects_a_lift_without_a_date(traps: normalize.Normalized) -> None:
    snap = build(traps)
    beta = next(w for w in snap["waterbodies"] if w["name"] == "Beta Reservoir")
    beta["status"]["lift_date"] = None
    with pytest.raises(snapshot.SnapshotError):
        snapshot.validate(snap)


def test_duplicate_ids_refused() -> None:
    with pytest.raises(snapshot.SnapshotError, match="share an id"):
        snapshot._assert_unique_ids([{"id": "ca-x"}, {"id": "ca-x"}])


def test_build_needs_a_file() -> None:
    with pytest.raises(snapshot.SnapshotError):
        snapshot.build(
            hist.empty(),
            run_date=RUN_DATE,
            generated_at=dt.datetime.now(dt.UTC),
            quarantine=Counter(),
            rows_read=1,
        )


def test_write_is_compact_and_valid(
    tmp_path: Path, traps: normalize.Normalized
) -> None:
    path = tmp_path / "v1.json"
    snapshot.write(build(traps), path)
    assert json.loads(path.read_text())["schema_version"] == 1


def test_packaged_schema_matches_the_published_one() -> None:
    published = json.loads((ROOT / "schema" / "snapshot.v1.json").read_text())
    assert snapshot.load_schema() == published


def test_slugs() -> None:
    assert snapshot.slugify("Lake Élsinore (north)") == "lake-elsinore-north"
    assert snapshot.slugify("!!!") == "unnamed"
    assert snapshot.water_id("CA", "", "X") == "ca-county-not-recorded-x"
