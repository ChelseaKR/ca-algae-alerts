"""Build the versioned snapshot: every waterbody, its sites, its records and
its status, validated against ``schema/snapshot.v1.json`` before it is
written. The app and the site are both built from this one object.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import statistics
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Iterable
from importlib import resources
from pathlib import Path
from typing import Any

import jsonschema

from caalgae import history as hist
from caalgae import status as st
from caalgae.normalize import counties_of
from caalgae.sources import SOURCES

SCHEMA_VERSION = 1


class SnapshotError(RuntimeError):
    """The snapshot failed its own contract. Nothing is published."""


def slugify(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", folded.lower()).strip("-") or "unnamed"


def water_id(state: str, county_text: str, name: str) -> str:
    county = slugify(county_text) if county_text else "county-not-recorded"
    return f"{state.lower()}-{county}-{slugify(name)}"


def _display_name(variants: Counter[str]) -> str:
    """The most-used spelling; ties go to the one with more capitals."""
    return max(
        variants.items(), key=lambda kv: (kv[1], sum(c.isupper() for c in kv[0]), kv[0])
    )[0]


def _iso(day: dt.date | None) -> str | None:
    return day.isoformat() if day else None


def status_json(status: st.Status) -> dict[str, Any]:
    return {
        "kind": status.kind,
        "tier": status.tier,
        "level": status.level,
        "posted": _iso(status.posted),
        "planned_end": _iso(status.planned_end),
        "lift_kind": status.lift_kind,
        "lift_date": _iso(status.lift_date),
        "last_advisory": _iso(status.last_advisory),
        "sites_with_advisory": status.sites_with_advisory,
    }


def _record_json(entry: hist.HistoryEntry) -> dict[str, Any]:
    r = entry.record
    return {
        "id": r.id,
        "site": r.site_id,
        "date": r.date.isoformat(),
        "level": r.level,
        "tier": r.tier,
        "explicit_no_advisory": r.explicit_no_advisory,
        "end_date": _iso(r.end_date),
        "detail": r.detail,
        "source": r.source,
        "removed_from_source": entry.removed_from_source,
    }


def _site_json(
    site_id: str, entries: list[hist.HistoryEntry], run_date: dt.date
) -> tuple[dict[str, Any], st.Status]:
    latest = max(entries, key=lambda e: e.record.sort_key()).record
    status = st.site_status((e.record for e in entries if e.active), run_date)
    coords = [(e.record.lat, e.record.lon) for e in entries if e.record.lat is not None]
    lat, lon = coords[-1] if coords else (None, None)
    return (
        {
            "id": site_id,
            "landmark": latest.landmark,
            "lat": lat,
            "lon": lon,
            "status": status_json(status),
        },
        status,
    )


def _center(sites: list[dict[str, Any]]) -> dict[str, float] | None:
    points = [(s["lat"], s["lon"]) for s in sites if s["lat"] is not None]
    if not points:
        return None
    return {
        "lat": round(statistics.median(p[0] for p in points), 5),
        "lon": round(statistics.median(p[1] for p in points), 5),
    }


def build_waterbodies(
    entries: Iterable[hist.HistoryEntry], run_date: dt.date
) -> list[dict[str, Any]]:
    by_water: dict[str, list[hist.HistoryEntry]] = defaultdict(list)
    for entry in entries:
        by_water[entry.record.water_key].append(entry)
    out: list[dict[str, Any]] = []
    for group in by_water.values():
        first = group[0].record
        names = Counter(e.record.water_name for e in group)
        name = _display_name(names)
        by_site: dict[str, list[hist.HistoryEntry]] = defaultdict(list)
        for entry in group:
            by_site[entry.record.site_id].append(entry)
        sites, statuses = [], []
        # Newest activity first, so a lake's page leads with what changed last.
        newest = {
            site_id: max(e.record.sort_key() for e in site_entries)
            for site_id, site_entries in by_site.items()
        }
        for site_id in sorted(by_site, key=lambda s: newest[s], reverse=True):
            site, site_status = _site_json(site_id, by_site[site_id], run_date)
            sites.append(site)
            statuses.append(site_status)
        records = sorted(group, key=lambda e: e.record.sort_key(), reverse=True)
        out.append(
            {
                "id": water_id(first.state, first.county_text, name),
                "state": first.state,
                "name": name,
                "county_text": first.county_text,
                "counties": counties_of(first.county_text),
                "center": _center(sites),
                "status": status_json(st.water_status(statuses)),
                "sites": sites,
                "records": [_record_json(e) for e in records],
            }
        )
    _assert_unique_ids(out)
    out.sort(key=lambda w: (str(w["name"]).casefold(), str(w["id"])))
    return out


def _assert_unique_ids(waters: list[dict[str, Any]]) -> None:
    ids = Counter(w["id"] for w in waters)
    clashes = [i for i, n in ids.items() if n > 1]
    if clashes:
        raise SnapshotError(f"two waterbodies share an id: {clashes[:5]}")


def build(
    history: hist.History,
    *,
    run_date: dt.date,
    generated_at: dt.datetime,
    quarantine: Counter[str],
    rows_read: int,
) -> dict[str, Any]:
    if not history.files:
        raise SnapshotError("no source file on record")
    current = history.files[-1]
    waters = build_waterbodies(history.entries.values(), run_date)
    active = history.active_records()
    newest = max((r.date for r in active), default=None)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "run_date": run_date.isoformat(),
        "sources": [s.as_json() for s in SOURCES.values()],
        "source_file": {
            "source": current["source"],
            "url": current["url"],
            "file_name": current["file_name"],
            "file_date": current["file_date"],
            "fetched_at": current["fetched_at"],
            "rows_read": rows_read,
            "newest_record_date": _iso(newest),
        },
        "quarantine": {
            "total": sum(quarantine.values()),
            "by_reason": dict(sorted(quarantine.items())),
        },
        "waterbodies": waters,
    }


def load_schema() -> dict[str, Any]:
    text = resources.files("caalgae").joinpath("snapshot.v1.json").read_text("utf-8")
    loaded: dict[str, Any] = json.loads(text)
    return loaded


def validate(snapshot: dict[str, Any]) -> None:
    try:
        jsonschema.validate(snapshot, load_schema())
    except jsonschema.ValidationError as error:
        raise SnapshotError(f"snapshot fails its schema: {error.message}") from error


def write(snapshot: dict[str, Any], path: Path) -> None:
    validate(snapshot)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(snapshot, separators=(",", ":"), ensure_ascii=False)
    path.write_text(text, encoding="utf-8")
