"""``caalgae``: one run, end to end.

dataset page -> discover the dated Responses CSV -> download -> normalize ->
merge into history -> snapshot (schema-validated) -> site.

Every refusal is one ``caalgae: run refused -- nothing published:`` line and
a non-zero exit, before anything is written. History is written only after
the snapshot passes its schema, so a run that fails late leaves no trace.

Offline runs (tests, ``make smoke``, screenshots) pass ``--fixture-page`` and
``--fixture-csv`` and make no network request at all.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import os
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import httpx

from caalgae import cyan, fetch, flagged, missouri, newyork, normalize, site, snapshot
from caalgae import history as hist
from caalgae.sources import CA_SWRCB_FHAB, EPA_CYAN, MO_DNR_HAB

DEFAULT_HISTORY = Path(__file__).resolve().parents[2] / "data" / "history.json"
DEFAULT_CYAN = Path(__file__).resolve().parents[2] / "data" / "cyan.json"
STALE_AFTER_DAYS = 7
# Missouri after a passing failure: shown with its read date for this many
# days after the last good read, then hidden (docs/DECISIONS.md 0019).
MO_STALE_AFTER_DAYS = 2
# California's quarantine may grow by at most this many rows in one run
# (DECISIONS 0027). It held at exactly 249 for 15 runs; a date-format change
# would quarantine every new posting without any other check noticing.
MAX_QUARANTINE_GROWTH = 25


class RunRefused(RuntimeError):
    pass


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="caalgae", description=__doc__)
    p.add_argument("--history", type=Path, default=DEFAULT_HISTORY)
    p.add_argument("--snapshot-out", type=Path, default=None)
    p.add_argument("--site-out", type=Path, default=None)
    p.add_argument("--fixture-page", type=Path, default=None)
    p.add_argument("--fixture-csv", type=Path, default=None)
    p.add_argument("--fixture-fetched-at", default=None)
    p.add_argument("--run-today", default=None, help="YYYY-MM-DD (tests only)")
    p.add_argument("--base-url", default="")
    p.add_argument("--support-email", default="")
    p.add_argument("--app-store-url", default="")
    p.add_argument("--mo-fixture", type=Path, default=None)
    p.add_argument("--mo-viewer-fixture", type=Path, default=None)
    p.add_argument("--cyan-cache", type=Path, default=None)
    p.add_argument("--cyan-refresh", choices=("auto", "never", "force"), default="auto")
    p.add_argument(
        "--ny-history",
        choices=("config", "on", "off"),
        default="config",
        help="New York bloom history section; 'config' follows site.NY_HISTORY_ENABLED",
    )
    p.add_argument(
        "--ny-cache",
        type=Path,
        default=None,
        help="a New York cache directory other than the pinned one (tests, previews)",
    )
    p.add_argument(
        "--accept-ca-edits",
        action="store_true",
        help=(
            "accept a California file that withdraws current advisories, more "
            f"than {hist.MAX_REMOVED_RECORDS} records, or grows the quarantine by "
            f"more than {MAX_QUARANTINE_GROWTH} rows; only after reading the "
            "file (docs/DECISIONS.md 0027)"
        ),
    )
    p.add_argument(
        "--state-fixture",
        action="append",
        default=[],
        metavar="STATE=PATH",
        help=(
            "a flagged state's fixture page (repeatable, in order); only with "
            "that state's flag on (docs/DECISIONS.md 0037)"
        ),
    )
    p.add_argument(
        "--state-review-out",
        type=Path,
        default=None,
        help="directory for flagged states' review files; never published",
    )
    return p.parse_args(argv)


def _download(args: argparse.Namespace, previous: dt.date | None) -> fetch.Download:
    if (args.fixture_page is None) != (args.fixture_csv is None):
        raise RunRefused("--fixture-page and --fixture-csv go together")
    if args.fixture_page is not None:
        page = args.fixture_page.read_text(encoding="utf-8")
        source = fetch.discover_responses_file(page)
        fetch.assert_not_regressed(source, previous)
        fetched_at = dt.datetime.fromisoformat(
            (args.fixture_fetched_at or f"{source.file_date}T12:00:00Z").replace(
                "Z", "+00:00"
            )
        )
        return fetch.Download(source, args.fixture_csv.read_bytes(), fetched_at)
    with fetch.make_client() as client:
        source = fetch.discover_responses_file(fetch.fetch_dataset_page(client))
        fetch.assert_not_regressed(source, previous)
        return fetch.fetch_csv(client, source, dt.datetime.now(dt.UTC))


def _warn(message: str) -> None:
    print(f"caalgae: WARNING {message}", file=sys.stderr)
    if os.environ.get("GITHUB_ACTIONS") == "true":
        print(f"::warning::{message}")


def _california(
    args: argparse.Namespace, history: hist.History, run_date: dt.date
) -> tuple[hist.History, Counter[str], fetch.Download]:
    download = _download(args, history.last_file_date(CA_SWRCB_FHAB.id))
    source = download.source
    if source.file_date > run_date + dt.timedelta(days=1):
        raise RunRefused(f"{source.file_name} is dated after the run date {run_date}")
    age = (run_date - source.file_date).days
    if age > STALE_AFTER_DAYS:
        _warn(
            f"the state's newest file is {age} days old ({source.file_name}); the site says so"
        )
    normalized = normalize.normalize_csv(download.body, source.file_date)
    _check_quarantine(history, normalized, accept=args.accept_ca_edits)
    unread = Counter(r.level for r in normalized.records if r.is_unrecognized)
    if unread:
        _warn(
            f"{sum(unread.values())} California record(s) carry a level this "
            f"pipeline does not recognize ({', '.join(sorted(unread))}); their "
            "spots read as undetermined until the level is mapped"
        )
    file_info = {
        "source": CA_SWRCB_FHAB.id,
        "url": source.url,
        "file_name": source.file_name,
        "file_date": source.file_date.isoformat(),
        "fetched_at": download.fetched_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "rows_read": normalized.rows_read,
        "quarantined": sum(normalized.quarantine.values()),
        "quarantined_by_reason": dict(sorted(normalized.quarantine.items())),
    }
    merged = hist.merge(
        history,
        normalized.records,
        run_date=run_date,
        file_info=file_info,
        max_removed=None if args.accept_ca_edits else hist.MAX_REMOVED_RECORDS,
        protect_advisories=not args.accept_ca_edits,
    )
    print(
        f"caalgae: {source.file_name}: {normalized.rows_read} rows, "
        f"{len(normalized.records)} records"
    )
    return merged, normalized.quarantine, download


def _check_quarantine(
    history: hist.History, normalized: normalize.Normalized, *, accept: bool
) -> None:
    """Refuse a California file whose quarantine jumped (DECISIONS 0027)."""
    last = history.last_file(CA_SWRCB_FHAB.id)
    if last is None or accept:
        return
    before = int(last.get("quarantined", 0))
    now = sum(normalized.quarantine.values())
    if now - before > MAX_QUARANTINE_GROWTH:
        raise RunRefused(
            f"the state's file quarantines {now} rows, up from {before} last run; "
            "a jump that size looks like a changed format, so nothing is published "
            "until the file is checked"
        )


def _missouri_last_read(history: hist.History) -> dt.date | None:
    last = history.last_file(MO_DNR_HAB.id)
    return dt.date.fromisoformat(str(last["fetched_at"])[:10]) if last else None


def _missouri_recent(history: hist.History, run_date: dt.date) -> bool:
    """Whether Missouri's last good read is recent enough to show, dated."""
    last = _missouri_last_read(history)
    return last is not None and (run_date - last).days <= MO_STALE_AFTER_DAYS


def _unavailable(
    history: hist.History, run_date: dt.date, reason: str
) -> tuple[hist.History, snapshot.SourceMode]:
    """Missouri in its "data unavailable" mode (DECISIONS 0024). The first
    run that finds it so sets ``since``; later runs keep that date and
    update the reason. Its pages stay up; the snapshot says why."""
    previous = history.outages.get(MO_DNR_HAB.id)
    since = previous["since"] if previous else run_date.isoformat()
    outages = {**history.outages, MO_DNR_HAB.id: {"since": since, "reason": reason}}
    if previous is None:
        _warn(f"Missouri data unavailable from {since}: {reason}")
    else:
        _warn(f"Missouri data still unavailable (since {since}): {reason}")
    last = _missouri_last_read(history)
    return dataclasses.replace(history, outages=outages), snapshot.SourceMode(
        source=MO_DNR_HAB.id,
        mode=snapshot.UNAVAILABLE,
        since=dt.date.fromisoformat(since),
        reason=reason,
        last_read=last,
    )


def _missouri_read(args: argparse.Namespace) -> tuple[bytes, bytes | None]:
    """The layer's answer and, when read, the department's viewer
    definition. A failed viewer read is never a reason to hide anything."""
    if args.mo_fixture is not None:
        viewer = args.mo_viewer_fixture.read_bytes() if args.mo_viewer_fixture else None
        return args.mo_fixture.read_bytes(), viewer
    if args.fixture_page is not None:
        # An offline run without a Missouri fixture reads nothing.
        raise fetch.FetchError("offline run: Missouri not read")
    with fetch.make_client() as client:
        body = missouri.fetch_cases(client)
        try:
            return body, missouri.fetch_viewer(client)
        except (fetch.FetchError, httpx.HTTPError) as error:
            _warn(f"Missouri viewer not checked: {error}")
            return body, None


def _missouri_merge(
    history: hist.History,
    body: bytes,
    viewer: bytes | None,
    run_date: dt.date,
    now: dt.datetime,
) -> tuple[hist.History, normalize.Normalized]:
    """A good read merged into history, or ``missouri.LayerUnavailable``."""
    normalized = missouri.normalize(body, run_date)
    missouri.check_fresh(normalized.records, run_date)
    if viewer is not None:
        try:
            missouri.check_viewer(viewer)
        except missouri.LayerUnavailable:
            raise
        except fetch.FetchError as error:  # an unreadable viewer proves no move
            _warn(f"Missouri viewer not checked: {error}")
    file_info = {
        "source": MO_DNR_HAB.id,
        "url": MO_DNR_HAB.dataset_url,
        "file_name": "HAB_SUBMIT_POINTS layer 6 (public water bodies)",
        "file_date": run_date.isoformat(),
        "fetched_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "rows_read": normalized.rows_read,
        "quarantined": sum(normalized.quarantine.values()),
        "quarantined_by_reason": dict(sorted(normalized.quarantine.items())),
    }
    try:
        merged = hist.merge(
            history, normalized.records, run_date=run_date, file_info=file_info
        )
    except hist.HistoryError as error:
        # A partial answer must not stop California (source-outage audit,
        # 2026-11-05, finding 8).
        raise missouri.LayerUnavailable(str(error), kind="partial") from error
    if MO_DNR_HAB.id in merged.outages:
        print(
            "caalgae: Missouri data available again; outage since "
            f"{merged.outages[MO_DNR_HAB.id]['since']} cleared"
        )
        merged = dataclasses.replace(
            merged,
            outages={k: v for k, v in merged.outages.items() if k != MO_DNR_HAB.id},
        )
    return merged, normalized


def _missouri_passing_failure(
    history: hist.History, run_date: dt.date, error: Exception
) -> tuple[hist.History, snapshot.SourceMode | None]:
    last = _missouri_last_read(history)
    if last is None:
        _warn(f"Missouri not shown: never read: {error}")
        return history, None
    ongoing = history.outages.get(MO_DNR_HAB.id)
    if ongoing is not None:
        # A passing failure during an outage never brings old data back.
        return _unavailable(history, run_date, ongoing["reason"])
    if _missouri_recent(history, run_date):
        _warn(f"Missouri not refreshed: {error}")
        return history, snapshot.SourceMode(
            source=MO_DNR_HAB.id, mode=snapshot.STALE_DATED, last_read=last
        )
    return _unavailable(
        history, run_date, f"not refreshed since {last.isoformat()}: {error}"
    )


def _missouri(
    args: argparse.Namespace, history: hist.History, run_date: dt.date, now: dt.datetime
) -> tuple[hist.History, Counter[str], snapshot.SourceMode | None]:
    """The second state. A failure here never stops California
    (docs/DECISIONS.md 0010). The third value is Missouri's mode, or None
    when it is not shown at all.

    - Switched off (``MO_DNR_HAB.enabled = False``, the State's revocation):
      not shown; no Missouri page is built (0019).
    - A good read: ``live``.
    - A passing failure (network, server error, robots.txt unreadable):
      ``stale_dated``, with its read date, while the last good read is at
      most ``MO_STALE_AFTER_DAYS`` old; ``unavailable`` after that.
    - The layer gone, changed, frozen or superseded
      (``missouri.LayerUnavailable``), or an answer that would damage
      history: ``unavailable`` at once (0024). Its history is kept for when
      a good read returns, and a good read clears the outage.
    """
    if not MO_DNR_HAB.enabled:
        return history, Counter(), None
    try:
        body, viewer = _missouri_read(args)
        merged, normalized = _missouri_merge(history, body, viewer, run_date, now)
    except missouri.LayerUnavailable as error:
        if _missouri_last_read(history) is None:
            # Nothing was ever read, so there is no page to keep up.
            _warn(f"Missouri data unavailable and never read: {error}")
            return history, Counter(), None
        merged, mode = _unavailable(history, run_date, f"{error.kind}: {error}")
        return merged, Counter(), mode
    except (fetch.FetchError, httpx.HTTPError) as error:
        merged, maybe = _missouri_passing_failure(history, run_date, error)
        return merged, Counter(), maybe
    print(
        f"caalgae: Missouri: {normalized.rows_read} cases, {len(normalized.records)} records"
    )
    return (
        merged,
        Counter({f"Missouri: {k}": v for k, v in normalized.quarantine.items()}),
        snapshot.SourceMode(
            source=MO_DNR_HAB.id, mode=snapshot.LIVE, last_read=now.date()
        ),
    )


def _cyan(
    args: argparse.Namespace, history: hist.History, run_date: dt.date, now: dt.datetime
) -> dict[str, Any] | None:
    """The satellite layer's cache, refreshed weekly on a live run. A failed
    refresh warns and keeps the cache; every reading carries its week."""
    offline = args.fixture_page is not None
    path = args.cyan_cache or (None if offline else DEFAULT_CYAN)
    if path is None or not EPA_CYAN.enabled:
        return None
    cache = cyan.load_cache(path)
    if offline or args.cyan_refresh == "never":
        return cache
    if args.cyan_refresh == "auto" and not cyan.is_due(cache, now):
        return cache
    waters = snapshot.build_waterbodies(history.entries.values(), run_date)
    try:
        with fetch.make_client() as client:
            cache = cyan.refresh(client, cache, waters, now)
    except (fetch.FetchError, httpx.HTTPError, ValueError) as error:
        _warn(f"CyAN not refreshed: {error}")
        return cache
    cyan.save_cache(cache, path)
    print(f"caalgae: CyAN: {len(cache['series'])} lakes refreshed")
    return cache


def _new_york(args: argparse.Namespace) -> newyork.History | None:
    """The New York history section, history only (docs/DECISIONS.md 0020).
    Built from the cache in the repository, never fetched by this run. When
    the section is on, a missing, altered or malformed cache refuses the
    run, so /state/ny/ pages never vanish from a green publish."""
    wanted = args.ny_history == "on" or (
        args.ny_history == "config" and site.NY_HISTORY_ENABLED
    )
    if not wanted:
        return None
    try:
        if args.ny_cache is not None:
            return newyork.load(args.ny_cache, pinned=None)
        return newyork.load()
    except newyork.NYDataError as error:
        raise RunRefused(f"New York history is on but not built: {error}") from error


def run(args: argparse.Namespace) -> int:
    run_date = (
        dt.date.fromisoformat(args.run_today)
        if args.run_today
        else dt.datetime.now(dt.UTC).date()
    )
    # Flagged states first (DECISIONS 0037): with every flag off this does
    # nothing at all; with one on, a failed read refuses the run before
    # anything is written. Their records never reach the history or site.
    flagged.review(
        run_date=run_date,
        fixtures=flagged.parse_fixtures(args.state_fixture),
        out_dir=args.state_review_out,
        site_out=args.site_out,
    )
    # Read first, so a bad New York cache refuses the run before anything
    # is written.
    ny_history = _new_york(args) if args.site_out is not None else None
    history = hist.load(args.history)
    merged, quarantine, download = _california(args, history, run_date)
    now = download.fetched_at
    merged, mo_quarantine, mo_mode = _missouri(args, merged, run_date, now)
    cyan_cache = _cyan(args, merged, run_date, now)
    snap = snapshot.build(
        merged,
        run_date=run_date,
        generated_at=now,
        quarantine=quarantine + mo_quarantine,
        cyan_cache=cyan_cache,
        hidden_sources=frozenset() if mo_mode else frozenset({MO_DNR_HAB.id}),
        modes=[mo_mode] if mo_mode else [],
    )
    snapshot.validate(snap)
    if args.snapshot_out is not None:
        snapshot.write(snap, args.snapshot_out)
    if args.site_out is not None:
        site.build_site(
            snap,
            args.site_out,
            base_url=args.base_url,
            support_email=args.support_email,
            app_store_url=args.app_store_url,
            ny_history=ny_history,
        )
    hist.save(merged, args.history)
    for reason, count in sorted((quarantine + mo_quarantine).items()):
        print(f"caalgae: quarantined {count} row(s): {reason}")
    print(f"caalgae: {len(snap['waterbodies'])} waterbodies")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        return run(args)
    except (
        RunRefused,
        fetch.FetchError,
        normalize.SourceShapeError,
        hist.HistoryError,
        snapshot.SnapshotError,
        flagged.FlagError,
    ) as error:
        print(f"caalgae: run refused -- nothing published: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
