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
as a truncated file. California is held tighter (decision 0027): at most
``MAX_REMOVED_RECORDS`` withdrawals, and none of a report's current advisory.
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
# California's stricter limits (DECISIONS 0027). 5% of 14,270 active records
# is 713, enough for a short file to flip live advisories to an older "None";
# in 15 runs the state withdrew 0 records. A run over either limit is
# refused unless the owner passes ``accept_edits`` after reading the file.
MAX_REMOVED_RECORDS = 25


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
# Added with the second source (2026-10-12). A history written before then
# has neither; both default to California's meaning.
_OPTIONAL_FIELDS = {
    "record_kind": "official_advisory",
    "end_kind": "no_advisory_record",
}


def record_to_json(record: Record) -> dict[str, Any]:
    out: dict[str, Any] = {name: getattr(record, name) for name in _RECORD_FIELDS}
    for name in _OPTIONAL_FIELDS:
        out[name] = getattr(record, name)
    out["date"] = record.date.isoformat()
    out["end_date"] = record.end_date.isoformat() if record.end_date else None
    out["stamp"] = record.stamp.isoformat() if record.stamp else None
    return out


def record_from_json(record_id: str, data: dict[str, Any]) -> Record:
    fields: dict[str, Any] = {name: data[name] for name in _RECORD_FIELDS}
    for name, default in _OPTIONAL_FIELDS.items():
        fields[name] = data.get(name, default)
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
    # A source in its "data unavailable" mode (DECISIONS 0024), by source id:
    # ``{"since": "YYYY-MM-DD", "reason": str}``. ``since`` is the first run
    # that found it unavailable and is kept until a good read clears it.
    outages: dict[str, dict[str, str]] = dataclasses.field(default_factory=dict)

    def last_file(self, source: str) -> dict[str, Any] | None:
        mine = [f for f in self.files if f.get("source") == source]
        return mine[-1] if mine else None

    def last_file_date(self, source: str) -> dt.date | None:
        last = self.last_file(source)
        return dt.date.fromisoformat(last["file_date"]) if last else None

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
    return History(
        entries=entries,
        files=list(data["files"]),
        outages=dict(data.get("outages", {})),
    )


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
    payload: dict[str, Any] = {"version": HISTORY_VERSION, "files": history.files}
    if history.outages:
        payload["outages"] = dict(sorted(history.outages.items()))
    payload["records"] = records
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=1, sort_keys=False, ensure_ascii=False)
    path.write_text(text + "\n", encoding="utf-8")


def _current_advisories(entries: dict[str, HistoryEntry], source: str) -> set[str]:
    """The ids of each report's latest deciding record, where that record is
    an advisory: the records whose withdrawal would change a status shown
    as an advisory today."""
    by_site: dict[str, list[Record]] = {}
    for entry in entries.values():
        r = entry.record
        deciding = r.is_advisory or r.explicit_no_advisory or r.is_unrecognized
        if entry.active and r.source == source and deciding:
            by_site.setdefault(r.site_id, []).append(r)
    out: set[str] = set()
    for site in by_site.values():
        latest = max(site, key=Record.sort_key)
        if latest.is_advisory:
            out.add(latest.id)
    return out


def merge(
    history: History,
    records: list[Record],
    *,
    run_date: dt.date,
    file_info: dict[str, Any],
    max_removed: int | None = None,
    protect_advisories: bool = False,
) -> History:
    """A new History with this file's records merged in.

    Only records of this file's source are compared, so one source's file
    can never withdraw another source's records. Record ids are prefixed by
    source where they could collide (Missouri's are ``mo-<objectid>``).

    ``max_removed`` refuses a file that would withdraw more than that many
    records, whatever the fraction. ``protect_advisories`` refuses a file
    that would withdraw any report's current advisory: the record that,
    gone, would let an older "None" or nothing at all speak for that spot
    (DECISIONS 0027).
    """
    today = run_date.isoformat()
    source = file_info["source"]
    current = {r.id: r for r in records}
    if any(r.source != source for r in records):
        raise HistoryError(f"a {source} file carried another source's records")
    entries = dict(history.entries)
    previously_active = [
        rid for rid, e in entries.items() if e.active and e.record.source == source
    ]
    newly_removed = [rid for rid in previously_active if rid not in current]
    if previously_active and (
        len(newly_removed) > MAX_REMOVED_FRACTION * len(previously_active)
    ):
        raise HistoryError(
            f"this file would withdraw {len(newly_removed)} of "
            f"{len(previously_active)} records on file; that looks like a "
            "truncated file, not the state's edits"
        )
    if max_removed is not None and len(newly_removed) > max_removed:
        raise HistoryError(
            f"this file would withdraw {len(newly_removed)} records, more than "
            f"the {max_removed} allowed in one run; that looks like a truncated "
            "file, not the state's edits"
        )
    if protect_advisories and newly_removed:
        live = _current_advisories(entries, source)
        lost = sorted(rid for rid in newly_removed if rid in live)
        if lost:
            raise HistoryError(
                f"this file would withdraw {len(lost)} current advisor"
                f"{'y' if len(lost) == 1 else 'ies'} (records {', '.join(lost[:10])}); "
                "the page would fall back to an older record, so the run is "
                "refused until the file is checked"
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
    return History(entries=entries, files=files, outages=dict(history.outages))
