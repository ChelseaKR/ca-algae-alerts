"""Build the versioned snapshot: every waterbody, its sites, its records and
its status, validated against ``schema/snapshot.v1.json`` before it is
written. The app and the site are both built from this one object.
"""

from __future__ import annotations

import dataclasses
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

from caalgae import cyan
from caalgae import history as hist
from caalgae import status as st
from caalgae.normalize import counties_of
from caalgae.sources import CA_SWRCB_FHAB, SOURCES, enabled_sources

SCHEMA_VERSION = 1

# A state's data mode (DECISIONS 0024), carried in ``state_status``.
LIVE = "live"
STALE_DATED = "stale_dated"
UNAVAILABLE = "unavailable"
# An unavailable state's pages stay indexed this many days after ``since``,
# then carry noindex (still built, still 200).
UNAVAILABLE_INDEX_DAYS = 30


@dataclasses.dataclass(frozen=True)
class SourceMode:
    """How current one state's data is this run.

    - ``live``: read this run.
    - ``stale_dated``: a passing failure; shown with its read date.
    - ``unavailable``: the source is gone, changed, frozen or superseded, or
      a passing failure outlasted ``MO_STALE_AFTER_DAYS``. Its pages stay up
      with a dated notice, no status headline and the history labeled as
      records read before ``last_read``; the app shows no status for it and
      sends no alert.
    """

    source: str
    mode: str
    last_read: dt.date | None = None
    since: dt.date | None = None
    reason: str | None = None


class SnapshotError(RuntimeError):
    """The snapshot failed its own contract. Nothing is published."""


def slugify(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", folded.lower()).strip("-") or "unnamed"


def water_id(state: str, county_text: str, name: str) -> str:
    """``ca-alameda-lake-temescal``; ``mo-truman-lake`` where the source
    names no county."""
    if not county_text:
        return f"{state.lower()}-{slugify(name)}"
    return f"{state.lower()}-{slugify(county_text)}-{slugify(name)}"


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


def _record_json(entry: hist.HistoryEntry, spot: str) -> dict[str, Any]:
    r = entry.record
    return {
        "id": r.id,
        "site": spot,
        "date": r.date.isoformat(),
        "level": r.level,
        "tier": r.tier,
        "explicit_no_advisory": r.explicit_no_advisory,
        "end_date": _iso(r.end_date),
        "detail": r.detail,
        "source": r.source,
        "record_kind": r.record_kind,
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


# Sources whose reports are matched to a spot by the state's coordinates
# (decision 0017). California files the same monitoring spot under a new
# bloom report each season, with the same coordinates to six decimals
# (measured 2026-11-03: 280 such spots; where landmarks differ they are
# spellings of one station, "Oaks Arm (DWR site CL-4)" and "(CL-04)").
# Missouri's readings are owner-confirmed per case (0013), so it is not
# matched.
SPOT_BY_COORDINATES = frozenset({CA_SWRCB_FHAB.id})


def spot_ids(group: Iterable[hist.HistoryEntry]) -> dict[str, str]:
    """Each bloom report's spot, as a report id.

    Reports of a coordinate-matched source that share their latest
    coordinates are one spot, named by the report with the newest record, so
    a later "None" at those coordinates is an explicit record at the same
    spot (0002) and ends an older advisory there. A report without
    coordinates, or from another source, is its own spot. Nothing is matched
    by name or by distance: two points a meter apart stay two spots.
    """
    entries = sorted(group, key=lambda e: e.record.sort_key())
    coords: dict[str, tuple[float, float]] = {}
    newest: dict[str, tuple[dt.date, dt.datetime, int]] = {}
    for entry in entries:
        r = entry.record
        newest[r.site_id] = r.sort_key()
        if r.source in SPOT_BY_COORDINATES and r.lat is not None and r.lon is not None:
            coords[r.site_id] = (r.lat, r.lon)
    at: dict[tuple[float, float], list[str]] = defaultdict(list)
    for report, point in coords.items():
        at[point].append(report)
    spot = {report: report for report in newest}
    for reports in at.values():
        name = max(reports, key=lambda rep: newest[rep])
        for report in reports:
            spot[report] = name
    return spot


def _center(sites: list[dict[str, Any]]) -> dict[str, float] | None:
    points = [(s["lat"], s["lon"]) for s in sites if s["lat"] is not None]
    if not points:
        return None
    return {
        "lat": round(statistics.median(p[0] for p in points), 5),
        "lon": round(statistics.median(p[1] for p in points), 5),
    }


def build_waterbodies(
    entries: Iterable[hist.HistoryEntry],
    run_date: dt.date,
    file_dates: dict[str, dt.date] | None = None,
) -> list[dict[str, Any]]:
    """``file_dates`` is each source's file date, the day a water's
    12-month headline window is measured back from (decision 0017); a
    source without one is measured from ``run_date``."""
    dates = file_dates or {}
    by_water: dict[str, list[hist.HistoryEntry]] = defaultdict(list)
    for entry in entries:
        by_water[entry.record.water_key].append(entry)
    out: list[dict[str, Any]] = []
    for group in by_water.values():
        first = group[0].record
        names = Counter(e.record.water_name for e in group)
        name = _display_name(names)
        spot = spot_ids(group)
        by_site: dict[str, list[hist.HistoryEntry]] = defaultdict(list)
        for entry in group:
            by_site[spot[entry.record.site_id]].append(entry)
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
                "status": status_json(
                    st.water_status(statuses, dates.get(first.source, run_date))
                ),
                "sites": sites,
                "records": [_record_json(e, spot[e.record.site_id]) for e in records],
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


def _file_json(history: hist.History, source: str) -> dict[str, Any] | None:
    last = history.last_file(source)
    if last is None:
        return None
    dates = [
        e.record.date
        for e in history.entries.values()
        if e.active and e.record.source == source
    ]
    return {
        "source": last["source"],
        "url": last["url"],
        "file_name": last["file_name"],
        "file_date": last["file_date"],
        "fetched_at": last["fetched_at"],
        "rows_read": last["rows_read"],
        "newest_record_date": _iso(max(dates, default=None)),
    }


def _mode_json(mode: SourceMode, history: hist.History) -> dict[str, Any]:
    source = SOURCES[mode.source]
    last_read = mode.last_read
    if last_read is None and (last := history.last_file(source.id)) is not None:
        last_read = dt.date.fromisoformat(str(last["fetched_at"])[:10])
    unavailable = mode.mode == UNAVAILABLE
    return {
        "state": source.state,
        "source": source.id,
        "mode": mode.mode,
        "last_read": _iso(last_read),
        "since": _iso(mode.since) if unavailable else None,
        "reason": mode.reason if unavailable else None,
        "map_url": source.current_map_url,
    }


def build(
    history: hist.History,
    *,
    run_date: dt.date,
    generated_at: dt.datetime,
    quarantine: Counter[str],
    cyan_cache: dict[str, Any] | None = None,
    hidden_sources: frozenset[str] = frozenset(),
    modes: Iterable[SourceMode] = (),
) -> dict[str, Any]:
    """The snapshot. Each waterbody's ``satellite`` block comes from the
    EPA CyAN cache (``cyan.py``) and never touches its status.

    A source in ``hidden_sources`` is left out entirely: its waters, its
    file and its entry in ``sources`` (docs/DECISIONS.md 0019). Its history
    is untouched."""
    if CA_SWRCB_FHAB.id in hidden_sources:
        raise SnapshotError("California cannot be hidden; a run without it is refused")
    shown = [s for s in enabled_sources() if s.id not in hidden_sources]
    primary = _file_json(history, CA_SWRCB_FHAB.id)
    if primary is None:
        raise SnapshotError("no California source file on record")
    files = [f for f in (_file_json(history, s.id) for s in shown) if f is not None]
    file_dates = {
        s.id: day for s in shown if (day := history.last_file_date(s.id)) is not None
    }
    waters = build_waterbodies(
        (e for e in history.entries.values() if e.record.source not in hidden_sources),
        run_date,
        file_dates,
    )
    by_source = {m.source: m for m in modes}
    state_status = [
        _mode_json(by_source.get(s.id) or SourceMode(source=s.id, mode=LIVE), history)
        for s in shown
        if s.record_kind == "official_advisory"
    ]
    satellite = cyan.blocks(cyan_cache, waters) if cyan_cache else {}
    for water in waters:
        water["satellite"] = satellite.get(water["id"])
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "run_date": run_date.isoformat(),
        "sources": [s.as_json() for s in shown],
        "source_file": primary,
        "source_files": files,
        "state_status": state_status,
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
