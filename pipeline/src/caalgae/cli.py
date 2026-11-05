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
import datetime as dt
import os
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import httpx

from caalgae import cyan, fetch, missouri, normalize, site, snapshot
from caalgae import history as hist
from caalgae.sources import CA_SWRCB_FHAB, EPA_CYAN, MO_DNR_HAB

DEFAULT_HISTORY = Path(__file__).resolve().parents[2] / "data" / "history.json"
DEFAULT_CYAN = Path(__file__).resolve().parents[2] / "data" / "cyan.json"
STALE_AFTER_DAYS = 7
# Missouri after a passing failure: shown with its read date for this many
# days after the last good read, then hidden (docs/DECISIONS.md 0019).
MO_STALE_AFTER_DAYS = 2


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
    p.add_argument("--cyan-cache", type=Path, default=None)
    p.add_argument("--cyan-refresh", choices=("auto", "never", "force"), default="auto")
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
        history, normalized.records, run_date=run_date, file_info=file_info
    )
    print(
        f"caalgae: {source.file_name}: {normalized.rows_read} rows, "
        f"{len(normalized.records)} records"
    )
    return merged, normalized.quarantine, download


def _missouri_recent(history: hist.History, run_date: dt.date) -> bool:
    """Whether Missouri's last good read is recent enough to show, dated."""
    last = history.last_file(MO_DNR_HAB.id)
    if last is None:
        return False
    fetched = dt.date.fromisoformat(str(last["fetched_at"])[:10])
    return (run_date - fetched).days <= MO_STALE_AFTER_DAYS


def _missouri(
    args: argparse.Namespace, history: hist.History, run_date: dt.date, now: dt.datetime
) -> tuple[hist.History, Counter[str], bool]:
    """The second state. A failure here never stops California
    (docs/DECISIONS.md 0010), and it fails closed (0019): the third value
    says whether Missouri is shown at all.

    - A good read: shown.
    - The layer gone or changed (``missouri.LayerUnavailable``): hidden at
      once. Its history is kept for when a good read returns.
    - A passing failure (network, server error, robots.txt unreadable):
      shown, with its read date, only while the last good read is at most
      ``MO_STALE_AFTER_DAYS`` old; hidden after that.
    """
    if not MO_DNR_HAB.enabled:
        return history, Counter(), False
    try:
        if args.mo_fixture is not None:
            body = args.mo_fixture.read_bytes()
        elif args.fixture_page is not None:
            # An offline run without a Missouri fixture reads nothing.
            return history, Counter(), _missouri_recent(history, run_date)
        else:
            with fetch.make_client() as client:
                body = missouri.fetch_cases(client)
        normalized = missouri.normalize(body, run_date)
    except missouri.LayerUnavailable as error:
        _warn(f"Missouri hidden: the layer is gone or changed: {error}")
        return history, Counter(), False
    except (fetch.FetchError, httpx.HTTPError) as error:
        shown = _missouri_recent(history, run_date)
        _warn(
            f"Missouri not refreshed: {error}"
            + (
                ""
                if shown
                else f"; hidden, last good read over {MO_STALE_AFTER_DAYS} days old"
            )
        )
        return history, Counter(), shown
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
    merged = hist.merge(
        history, normalized.records, run_date=run_date, file_info=file_info
    )
    print(
        f"caalgae: Missouri: {normalized.rows_read} cases, {len(normalized.records)} records"
    )
    return (
        merged,
        Counter({f"Missouri: {k}": v for k, v in normalized.quarantine.items()}),
        True,
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


def run(args: argparse.Namespace) -> int:
    run_date = (
        dt.date.fromisoformat(args.run_today)
        if args.run_today
        else dt.datetime.now(dt.UTC).date()
    )
    history = hist.load(args.history)
    merged, quarantine, download = _california(args, history, run_date)
    now = download.fetched_at
    merged, mo_quarantine, mo_shown = _missouri(args, merged, run_date, now)
    cyan_cache = _cyan(args, merged, run_date, now)
    snap = snapshot.build(
        merged,
        run_date=run_date,
        generated_at=now,
        quarantine=quarantine + mo_quarantine,
        cyan_cache=cyan_cache,
        hidden_sources=frozenset() if mo_shown else frozenset({MO_DNR_HAB.id}),
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
    ) as error:
        print(f"caalgae: run refused -- nothing published: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
