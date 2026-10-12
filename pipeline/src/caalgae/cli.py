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
import sys
from collections.abc import Sequence
from pathlib import Path

from caalgae import fetch, normalize, site, snapshot
from caalgae import history as hist
from caalgae.sources import CA_SWRCB_FHAB

DEFAULT_HISTORY = Path(__file__).resolve().parents[2] / "data" / "history.json"
STALE_AFTER_DAYS = 7


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


def run(args: argparse.Namespace) -> int:
    run_date = (
        dt.date.fromisoformat(args.run_today)
        if args.run_today
        else dt.datetime.now(dt.UTC).date()
    )
    history = hist.load(args.history)
    download = _download(args, history.last_file_date)
    source = download.source
    if source.file_date > run_date + dt.timedelta(days=1):
        raise RunRefused(f"{source.file_name} is dated after the run date {run_date}")
    age = (run_date - source.file_date).days
    if age > STALE_AFTER_DAYS:
        print(
            f"caalgae: WARNING the state's newest file is {age} days old "
            f"({source.file_name}); the site says so",
            file=sys.stderr,
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
    }
    merged = hist.merge(
        history, normalized.records, run_date=run_date, file_info=file_info
    )
    snap = snapshot.build(
        merged,
        run_date=run_date,
        generated_at=download.fetched_at,
        quarantine=normalized.quarantine,
        rows_read=normalized.rows_read,
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
    for reason, count in sorted(normalized.quarantine.items()):
        print(f"caalgae: quarantined {count} row(s): {reason}")
    print(
        f"caalgae: {source.file_name}: {normalized.rows_read} rows, "
        f"{len(normalized.records)} records, "
        f"{len(snap['waterbodies'])} waterbodies"
    )
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
