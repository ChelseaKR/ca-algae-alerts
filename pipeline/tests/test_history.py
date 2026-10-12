from __future__ import annotations

import dataclasses
import datetime as dt
from pathlib import Path

import pytest

from caalgae import history as hist
from caalgae import normalize

INFO = {"file_date": "2026-10-09", "source": "ca-swrcb-fhab"}


def test_first_merge_adds_everything(traps: normalize.Normalized) -> None:
    h = hist.merge(
        hist.empty(), traps.records, run_date=dt.date(2026, 10, 12), file_info=INFO
    )
    assert len(h.entries) == len(traps.records)
    assert all(e.first_seen == "2026-10-12" and e.active for e in h.entries.values())
    assert h.last_file_date == dt.date(2026, 10, 9)


def test_round_trip(tmp_path: Path, traps: normalize.Normalized) -> None:
    h = hist.merge(
        hist.empty(), traps.records, run_date=dt.date(2026, 10, 12), file_info=INFO
    )
    path = tmp_path / "h.json"
    hist.save(h, path)
    again = hist.load(path)
    assert again.entries == h.entries
    assert again.files == h.files
    assert hist.load(tmp_path / "missing.json").entries == {}


def test_withdrawn_record_is_kept_and_labeled(
    traps: normalize.Normalized, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(hist, "MAX_REMOVED_FRACTION", 0.5)
    h = hist.merge(
        hist.empty(), traps.records, run_date=dt.date(2026, 10, 12), file_info=INFO
    )
    gone = traps.records[0].id
    later = hist.merge(
        h, traps.records[1:], run_date=dt.date(2026, 10, 13), file_info=INFO
    )
    assert later.entries[gone].removed_from_source == "2026-10-13"
    assert gone not in {r.id for r in later.active_records()}
    assert len(later.entries) == len(traps.records)


def test_revised_record_is_updated_in_place(traps: normalize.Normalized) -> None:
    h = hist.merge(
        hist.empty(), traps.records, run_date=dt.date(2026, 10, 12), file_info=INFO
    )
    changed = [
        dataclasses.replace(traps.records[0], detail="edited"),
        *traps.records[1:],
    ]
    later = hist.merge(h, changed, run_date=dt.date(2026, 10, 13), file_info=INFO)
    entry = later.entries[traps.records[0].id]
    assert entry.record.detail == "edited"
    assert entry.revised_on == "2026-10-13"
    assert entry.first_seen == "2026-10-12"


def test_truncated_file_is_refused(traps: normalize.Normalized) -> None:
    h = hist.merge(
        hist.empty(), traps.records, run_date=dt.date(2026, 10, 12), file_info=INFO
    )
    with pytest.raises(hist.HistoryError, match="truncated"):
        hist.merge(h, traps.records[:3], run_date=dt.date(2026, 10, 13), file_info=INFO)


def test_unknown_version_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "h.json"
    path.write_text('{"version": 99, "files": [], "records": {}}')
    with pytest.raises(hist.HistoryError, match="version"):
        hist.load(path)
