#!/usr/bin/env python3
"""Is the live snapshot fresh, and is every state's source still being read?

The publish workflow opens an issue when a run fails (publish.yml,
``alert-on-failure``), but that job runs inside the run it reports on: on 3
of the 5 failed runs from 2026-10-28 to 2026-11-12 GitHub blocked the alert
job together with the build, and nothing else looked. This check, run once a
day by .github/workflows/publish-health.yml, reads what the site actually
serves (``snapshot/v1.json``) and so sees:

- the daily run never happened or never deployed (a blocked or disabled
  schedule, a Pages outage, a deploy that did not land), so the snapshot is
  old;
- a state whose data stopped (DECISIONS 0024): ``unavailable``, or a last
  read older than the pipeline itself allows;
- California's newest file is older than the week after which the site
  starts saying so (``cli.STALE_AFTER_DAYS``);
- the site is not answering, or answers something that is not a snapshot.

Absence is a finding, never a pass: a missing field, a date that does not
parse or a fetch that fails each say so and make the check fail.

Exit status: 0 healthy, 1 unhealthy (the report is in --out), 2 usage error.
--state-out always gets the sorted finding keys (empty when healthy); the
workflow compares them with the ones recorded in the open issue and comments
only when they change. The report holds only fixed text, state codes (two
capital letters), finding keys, and dates and numbers computed here; nothing
a remote server sent is copied into it, so it is safe to post as an issue
body.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx

# Thresholds, each justified against publish.yml (one run a day at 14:41
# UTC, deployed by about 14:55) and publish-health.yml (19:23 UTC, so a
# healthy snapshot is about 4.7 hours old when this runs).
#
# A missed day makes the snapshot about 28.7 hours old at check time, so 24
# hours flags it the same day, with about 19 hours of margin for a late
# scheduled start or a slow run. One missed day is worth hearing about: the
# app's alerts and the site's statuses come only from this file.
STALE_PUBLISH_HOURS = 24
# The pipeline shows a state that failed to read, dated, while its last good
# read is at most this many days old, then switches it to "unavailable"
# (cli.MO_STALE_AFTER_DAYS). A last read older than that, measured from the
# day the snapshot was built, means the pipeline's own rule did not fire.
STATE_STALE_DAYS = 2
# The pipeline warns, and the site says so, once California's newest file is
# more than this many days old (cli.STALE_AFTER_DAYS).
CA_FILE_MAX_AGE_DAYS = 7

SNAPSHOT_PATH = "snapshot/v1.json"
DEFAULT_BASE_URL = "https://lakenotice.com"
CA_SOURCE = "ca-swrcb-fhab"
USER_AGENT = "lakenotice-publish-health (+https://lakenotice.com)"
FETCH_ATTEMPTS = 3
FETCH_TIMEOUT_SECONDS = 30.0
# The live snapshot was 5.4 MB on 2026-11-19.
MAX_SNAPSHOT_BYTES = 25_000_000
MODES = ("live", "stale_dated", "unavailable")
# The workflow reads this line back from the open issue's body.
STATE_MARKER = "<!-- publish-health-state: {} -->"
_STATE_CODE = re.compile(r"^[A-Z]{2}$")

Fetch = Callable[[str], bytes]


class Finding:
    """One thing wrong, as a fixed sentence."""

    def __init__(self, key: str, text: str) -> None:
        self.key = key
        self.text = text

    def __repr__(self) -> str:
        return f"Finding({self.key!r})"


def _parse_time(value: object) -> dt.datetime | None:
    if not isinstance(value, str):
        return None
    try:
        when = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if when.tzinfo is None:
        return None
    return when


def _parse_date(value: object) -> dt.date | None:
    if not isinstance(value, str):
        return None
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        return None


def evaluate(snapshot: object, now: dt.datetime) -> list[Finding]:
    """Findings for one parsed snapshot. Empty means healthy."""
    if not isinstance(snapshot, dict):
        return [Finding("snapshot-shape", "The snapshot is not a JSON object.")]
    findings: list[Finding] = []

    generated = _parse_time(snapshot.get("generated_at"))
    if generated is None:
        findings.append(
            Finding("generated-missing", "The snapshot has no readable generated_at.")
        )
        # Per-source ages are measured from the build; without one, from now.
        built_on = now.date()
    else:
        built_on = generated.astimezone(dt.UTC).date()
        hours = (now - generated).total_seconds() / 3600
        if hours > STALE_PUBLISH_HOURS:
            findings.append(
                Finding(
                    "publish-stale",
                    f"The live snapshot is {hours:.0f} hours old "
                    f"(limit {STALE_PUBLISH_HOURS}). The daily publish did "
                    "not deploy.",
                )
            )
    findings.extend(_check_states(snapshot.get("state_status"), built_on))
    findings.extend(_check_ca_file(snapshot.get("source_files"), built_on))
    return findings


def _check_states(entries: object, built_on: dt.date) -> list[Finding]:
    if not isinstance(entries, list) or not entries:
        return [Finding("states-missing", "The snapshot has no state_status list.")]
    findings: list[Finding] = []
    seen_ca = False
    for entry in entries:
        code = entry.get("state") if isinstance(entry, dict) else None
        if (
            not isinstance(entry, dict)
            or not isinstance(code, str)
            or not _STATE_CODE.match(code)
        ):
            findings.append(
                Finding("state-code", "A state entry has no valid two-letter code.")
            )
            continue
        seen_ca = seen_ca or code == "CA"
        findings.extend(_check_state(code, entry, built_on))
    if not seen_ca:
        findings.append(Finding("ca-missing", "California is not in state_status."))
    return findings


def _check_state(code: str, entry: dict[str, Any], built_on: dt.date) -> list[Finding]:
    mode = entry.get("mode")
    if mode not in MODES:
        return [Finding(f"{code}-mode", f"{code} has no readable mode.")]
    last_read = _parse_date(entry.get("last_read"))
    shown = last_read.isoformat() if last_read else "an unreadable date"
    if mode == "unavailable":
        since = _parse_date(entry.get("since"))
        return [
            Finding(
                f"{code}-unavailable",
                f"{code}'s data is unavailable since "
                f"{since.isoformat() if since else 'an unreadable date'} "
                f"(last read {shown}). Its pages and the app show no current "
                "status for it.",
            )
        ]
    if last_read is None:
        return [Finding(f"{code}-last-read", f"{code} has no readable last_read.")]
    days = (built_on - last_read).days
    if days > STATE_STALE_DAYS:
        return [
            Finding(
                f"{code}-stale",
                f"{code} was last read on {shown}, {days} days before the "
                f"snapshot was built (limit {STATE_STALE_DAYS}), yet it is "
                "not marked unavailable.",
            )
        ]
    return []


def _check_ca_file(files: object, built_on: dt.date) -> list[Finding]:
    if not isinstance(files, list):
        return [Finding("ca-file-missing", "The snapshot has no source_files list.")]
    ca = [f for f in files if isinstance(f, dict) and f.get("source") == CA_SOURCE]
    if not ca:
        return [Finding("ca-file-missing", "California's file is not in source_files.")]
    file_date = _parse_date(ca[0].get("file_date"))
    if file_date is None:
        return [Finding("ca-file-date", "California's file has no readable file_date.")]
    days = (built_on - file_date).days
    if days > CA_FILE_MAX_AGE_DAYS:
        return [
            Finding(
                "ca-file-old",
                f"California's newest file is dated {file_date.isoformat()}, "
                f"{days} days before the snapshot was built (limit "
                f"{CA_FILE_MAX_AGE_DAYS}). The site already says so; the "
                "state may have stopped posting.",
            )
        ]
    return []


def state_key(findings: list[Finding]) -> str:
    """The sorted, de-duplicated finding keys: what the issue records."""
    return ",".join(sorted({f.key for f in findings}))


def snapshot_url(base_url: str) -> str:
    """The snapshot URL for a base, https only, no credentials or query."""
    base = base_url.strip() or DEFAULT_BASE_URL
    parts = urlsplit(base)
    if (
        parts.scheme != "https"
        or not parts.hostname
        or parts.username
        or parts.password
        or parts.query
        or parts.fragment
    ):
        raise ValueError("the base URL must be plain https://host[/path]")
    return base.rstrip("/") + "/" + SNAPSHOT_PATH


def http_fetch(url: str) -> bytes:
    """One GET; raises on a network error or a non-200 answer."""
    with httpx.Client(follow_redirects=True, timeout=FETCH_TIMEOUT_SECONDS) as client:
        response = client.get(url, headers={"User-Agent": USER_AGENT})
    response.raise_for_status()
    if len(response.content) > MAX_SNAPSHOT_BYTES:
        raise ValueError("snapshot is larger than expected")
    return response.content


def check(url: str, now: dt.datetime, fetch: Fetch = http_fetch) -> list[Finding]:
    """Fetch the snapshot (with retries) and evaluate it."""
    body = b""
    for attempt in range(FETCH_ATTEMPTS):
        try:
            body = fetch(url)
            break
        except (httpx.HTTPError, ValueError, OSError):
            if attempt == FETCH_ATTEMPTS - 1:
                return [
                    Finding(
                        "fetch",
                        f"The site did not serve {SNAPSHOT_PATH} in "
                        f"{FETCH_ATTEMPTS} attempts.",
                    )
                ]
    try:
        snapshot = json.loads(body)
    except ValueError:
        return [Finding("snapshot-json", f"{SNAPSHOT_PATH} is not valid JSON.")]
    return evaluate(snapshot, now)


def report(findings: list[Finding], url: str, now: dt.datetime) -> str:
    lines = [
        "The daily health check read the live snapshot and found:",
        "",
        *(f"- {f.text}" for f in findings),
        "",
        f"Checked {now.strftime('%Y-%m-%d %H:%MZ')} against {url}.",
        "This issue closes itself on the first healthy check. It gets a new "
        "comment only when what the check finds changes, not every day.",
        "",
        STATE_MARKER.format(state_key(findings)),
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument(
        "--base-url", default="", help="site root; default lakenotice.com"
    )
    parser.add_argument("--out", type=Path, required=True, help="report file")
    parser.add_argument(
        "--state-out", type=Path, required=True, help="finding keys file"
    )
    args = parser.parse_args(argv)
    try:
        url = snapshot_url(args.base_url)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    now = dt.datetime.now(dt.UTC)
    findings = check(url, now)
    args.state_out.write_text(state_key(findings) + "\n", encoding="utf-8")
    if not findings:
        print(f"healthy: {url}")
        return 0
    args.out.write_text(report(findings, url, now), encoding="utf-8")
    for f in findings:
        print(f"UNHEALTHY: {f.text}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
