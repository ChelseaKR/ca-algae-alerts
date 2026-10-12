"""The append-only record of every advisory action ever read.

The state's file carries history back to 2016 today, but it is re-created
from time to time (the dataset says "Created September 30, 2026") and rows
can be edited or withdrawn. So the pipeline keeps its own copy, keyed by the
state's ``Response_Action_ID``:

- a record seen for the first time is added with ``first_seen``;
- a record that changes is updated in place and its ``revised_on`` set;
- a record missing from a later file is never deleted. It gets
  ``removed_from_source`` and stops counting toward any status (the state
  withdrew it), but stays in the waterbody's history, labeled.

A failed or refused run never reaches this module, so a bad fetch cannot
mark the whole file as removed (decision 0005 in Trout Truck's terms: a
failed fetch is never a "nothing happened" fact). A run that would mark
more than ``MAX_REMOVED_FRACTION`` of the active records removed is refused
as a truncated file.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
from pathlib import Path
from typing import Any

from caalgae.normalize import Record

HISTORY_VERSION = 1
MAX_REMOVED_FRACTION = 0.05


class HistoryError(RuntimeError):
    """The merge would damage history. Nothing is written."""


_RECORD_FIELDS = (
    "source",
    "state",
    "site_id",
    "water_key",
    "water_name",
    "county_text",
    "landmark",
    "lat",
    "lon",
    "level",
    "tier",
    "explicit_no_advisory",
    "detail",
)


def record_to_json(record: Record) -> dict[str, Any]:
    out: dict[str, Any] = {name: getattr(record, name) for name in _RECORD_FIELDS}
    out["date"] = record.date.isoformat()
    out["end_date"] = record.end_date.isoformat() if record.end_date else None
    out["stamp"] = record.stamp.isoformat() if record.stamp else None
    return out


def record_from_json(record_id: str, data: dict[str, Any]) -> Record:
    fields = {name: data[name] for name in _RECORD_FIELDS}
    return Record(
        id=record_id,
        date=dt.date.fromisoformat(data["date"]),
        end_date=dt.date.fromisoformat(data["end_date"]) if data["end_date"] else None,
        stamp=dt.datetime.fromisoformat(data["stamp"]) if data["stamp"] else None,
        **fields,
    )


@dataclasses.dataclass
class HistoryEntry:
    record: Record
    first_seen: str
    last_seen: str
    revised_on: str | None = None
    removed_from_source: str | None = None

    @property
    def active(self) -> bool:
        return self.removed_from_source is None


@dataclasses.dataclass
class History:
    entries: dict[str, HistoryEntry]
    files: list[dict[str, Any]]

    @property
    def last_file_date(self) -> dt.date | None:
        if not self.files:
            return None
        return dt.date.fromisoformat(self.files[-1]["file_date"])

    def active_records(self) -> list[Record]:
        return [e.record for e in self.entries.values() if e.active]


def empty() -> History:
    return History(entries={}, files=[])


def load(path: Path) -> History:
    if not path.exists():
        return empty()
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("version") != HISTORY_VERSION:
        raise HistoryError(f"{path}: unknown history version {data.get('version')}")
    entries = {
        record_id: HistoryEntry(
            record=record_from_json(record_id, item["record"]),
            first_seen=item["first_seen"],
            last_seen=item["last_seen"],
            revised_on=item.get("revised_on"),
            removed_from_source=item.get("removed_from_source"),
        )
        for record_id, item in data["records"].items()
    }
    return History(entries=entries, files=list(data["files"]))


def save(history: History, path: Path) -> None:
    def sort_id(record_id: str) -> tuple[int, str]:
        return (int(record_id) if record_id.isdigit() else -1, record_id)

    records = {}
    for record_id in sorted(history.entries, key=sort_id):
        entry = history.entries[record_id]
        item: dict[str, Any] = {
            "record": record_to_json(entry.record),
            "first_seen": entry.first_seen,
            "last_seen": entry.last_seen,
        }
        if entry.revised_on:
            item["revised_on"] = entry.revised_on
        if entry.removed_from_source:
            item["removed_from_source"] = entry.removed_from_source
        records[record_id] = item
    payload = {"version": HISTORY_VERSION, "files": history.files, "records": records}
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=1, sort_keys=False, ensure_ascii=False)
    path.write_text(text + "\n", encoding="utf-8")


def merge(
    history: History,
    records: list[Record],
    *,
    run_date: dt.date,
    file_info: dict[str, Any],
) -> History:
    """A new History with this file's records merged in."""
    today = run_date.isoformat()
    current = {r.id: r for r in records}
    entries = dict(history.entries)
    previously_active = [rid for rid, e in entries.items() if e.active]
    newly_removed = [rid for rid in previously_active if rid not in current]
    if previously_active and (
        len(newly_removed) > MAX_REMOVED_FRACTION * len(previously_active)
    ):
        raise HistoryError(
            f"this file would withdraw {len(newly_removed)} of "
            f"{len(previously_active)} records on file; that looks like a "
            "truncated file, not the state's edits"
        )
    for record_id, record in current.items():
        old = entries.get(record_id)
        if old is None:
            entries[record_id] = HistoryEntry(record, first_seen=today, last_seen=today)
            continue
        revised = old.revised_on
        if old.record != record:
            revised = today
        entries[record_id] = HistoryEntry(
            record, first_seen=old.first_seen, last_seen=today, revised_on=revised
        )
    for record_id in newly_removed:
        old = entries[record_id]
        entries[record_id] = dataclasses.replace(old, removed_from_source=today)
    files = [*history.files, file_info]
    return History(entries=entries, files=files)
