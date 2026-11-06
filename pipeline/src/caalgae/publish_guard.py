"""Refuse a deploy that silently drops a state's pages (DECISIONS 0024).

Run by publish.yml after the build and before anything is committed or
deployed. It compares the built ``sitemap.xml`` with the live one, state by
state (``water/<st>-...`` and ``state/<st>/`` pages; ``county/`` pages are
California's), and refuses the run when a state that had indexable pages
loses all of them, or more than ``MAX_DROP_FRACTION`` of them, unless:

- the state's source is switched off (``enabled=False``: the State revoked
  permission, decision 0019), or
- the owner names the state in the workflow's ``allow_page_drop`` input, or
- the state is in its "data unavailable" mode past its 30 indexed days, so
  its pages carry noindex on purpose. Even then every dropped URL must still
  be a built page, so it keeps answering 200.

A refused run fails before the history commit and the Pages upload, so
yesterday's site stays live and the publish-failure issue opens. A state
in its "data unavailable" mode is reported (``unavailable`` output) so the
workflow can open an issue the same day; that never fails the run.

No live sitemap (the first deploy, a 404) or a failed read of it is not a
reason to refuse: there is then nothing live to protect, and the run says so.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx

from caalgae.site import STATE_NAMES
from caalgae.snapshot import UNAVAILABLE_INDEX_DAYS
from caalgae.sources import SOURCES

MAX_DROP_FRACTION = 0.20
USER_AGENT = (
    "ca-algae-alerts-publish-guard (+https://github.com/ChelseaKR/ca-algae-alerts)"
)
_LOC = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>")
_ALLOW = re.compile(r"^[A-Z]{2}(,[A-Z]{2})*$")
_WATER = re.compile(r"^water/([a-z]{2})-")
_STATE = re.compile(r"^state/([a-z]{2})/")


class GuardInputError(ValueError):
    pass


def sitemap_urls(xml: str) -> set[str]:
    return set(_LOC.findall(xml))


def state_of(url: str, base_url: str) -> str | None:
    path = url[len(base_url) :] if url.startswith(base_url) else urlsplit(url).path
    path = path.lstrip("/")
    if m := _WATER.match(path) or _STATE.match(path):
        return m.group(1).upper()
    if path.startswith("county/"):
        return "CA"
    return None


def by_state(urls: set[str], base_url: str) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for url in urls:
        state = state_of(url, base_url)
        if state:
            out.setdefault(state, set()).add(url)
    return out


def _disabled_states() -> set[str]:
    return {s.state for s in SOURCES.values() if not s.enabled}


def _built(site_dir: Path, url: str, base_url: str) -> bool:
    rel = url[len(base_url) :] if url.startswith(base_url) else urlsplit(url).path
    rel = rel.lstrip("/")
    page = (
        site_dir / rel / "index.html"
        if rel == "" or rel.endswith("/")
        else site_dir / rel
    )
    return page.is_file()


def check(
    *,
    live: set[str] | None,
    built: set[str],
    snapshot: dict[str, Any],
    site_dir: Path,
    base_url: str,
    allow: set[str],
) -> tuple[list[str], list[str], list[str]]:
    """(refusals, notes, unavailable notices)."""
    refusals: list[str] = []
    notes: list[str] = []
    run_date = dt.date.fromisoformat(snapshot["run_date"])
    unavailable = {
        m["state"]: m
        for m in snapshot.get("state_status", [])
        if m["mode"] == "unavailable"
    }
    notices = [
        f"{STATE_NAMES.get(st, st)} data unavailable since {m['since']}: {m['reason']}"
        for st, m in sorted(unavailable.items())
    ]
    if live is None:
        notes.append("no live sitemap to compare with; nothing live to protect")
        return refusals, notes, notices
    before = by_state(live, base_url)
    after = by_state(built, base_url)
    disabled = _disabled_states()
    for state, urls in sorted(before.items()):
        lost = urls - after.get(state, set())
        if not lost:
            continue
        kept = len(urls) - len(lost)
        line = f"{state}: {len(urls)} sitemap URLs live, {kept} in this build ({len(lost)} dropped)"
        if not (kept == 0 or len(lost) > MAX_DROP_FRACTION * len(urls)):
            notes.append(line + "; within the limit")
            continue
        if state in allow:
            notes.append(line + "; allowed by the owner's allow_page_drop")
            continue
        if state in disabled:
            notes.append(line + "; the source is switched off")
            continue
        outage = unavailable.get(state)
        if outage is not None:
            days = (run_date - dt.date.fromisoformat(outage["since"])).days
            gone = sorted(u for u in lost if not _built(site_dir, u, base_url))
            if days >= UNAVAILABLE_INDEX_DAYS and not gone:
                notes.append(
                    line
                    + f"; data unavailable for {days} days, pages kept with noindex"
                )
                continue
            if gone:
                refusals.append(
                    line + f"; {len(gone)} would stop answering, e.g. {gone[0]}"
                )
                continue
        refusals.append(
            line + "; the source is not switched off and no override was given"
        )
    return refusals, notes, notices


def fetch_live(base_url: str) -> tuple[set[str] | None, str | None]:
    """The live sitemap's URLs, or None with the reason it was not read."""
    if urlsplit(base_url).scheme != "https":
        return None, f"base URL is not https: {base_url}"
    try:
        response = httpx.get(
            base_url + "sitemap.xml",
            headers={"User-Agent": USER_AGENT},
            timeout=30,
            follow_redirects=True,
        )
    except httpx.HTTPError as error:
        return None, f"live sitemap not read: {error}"
    if response.status_code != 200:
        return None, f"live sitemap answered HTTP {response.status_code}"
    return sitemap_urls(response.text), None


def _parse_allow(text: str) -> set[str]:
    text = text.strip().upper().replace(" ", "")
    if not text:
        return set()
    if not _ALLOW.match(text):
        raise GuardInputError(
            f"allow_page_drop must be state codes like MO or CA,MO: {text!r}"
        )
    return set(text.split(","))


def _output(name: str, value: str) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(f"{name}={value.replace(chr(10), ' ')}\n")


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="publish_guard", description=__doc__)
    p.add_argument("--site-dir", type=Path, required=True)
    p.add_argument("--base-url", required=True)
    p.add_argument("--allow", default="")
    p.add_argument("--live-sitemap-file", type=Path, default=None, help="tests only")
    args = p.parse_args(argv)
    base_url = args.base_url.rstrip("/") + "/"
    try:
        allow = _parse_allow(args.allow)
    except GuardInputError as error:
        print(f"publish guard: {error}", file=sys.stderr)
        _output("reason", str(error))
        return 2
    built = sitemap_urls((args.site_dir / "sitemap.xml").read_text(encoding="utf-8"))
    snapshot = json.loads(
        (args.site_dir / "snapshot" / "v1.json").read_text(encoding="utf-8")
    )
    if args.live_sitemap_file is not None:
        live: set[str] | None = (
            sitemap_urls(args.live_sitemap_file.read_text(encoding="utf-8"))
            if args.live_sitemap_file.exists()
            else None
        )
        problem = None if live is not None else "no live sitemap file"
    else:
        live, problem = fetch_live(base_url)
    if problem:
        print(f"publish guard: {problem}")
    refusals, notes, notices = check(
        live=live,
        built=built,
        snapshot=snapshot,
        site_dir=args.site_dir,
        base_url=base_url,
        allow=allow,
    )
    for line in notes:
        print(f"publish guard: {line}")
    for line in notices:
        print(f"publish guard: NOTICE {line}")
    _output("unavailable", "; ".join(notices))
    if refusals:
        reason = "; ".join(refusals)
        print(f"publish guard: REFUSED -- nothing deployed: {reason}", file=sys.stderr)
        if os.environ.get("GITHUB_ACTIONS") == "true":
            print(f"::error::publish guard refused the deploy: {reason}")
        _output("reason", reason)
        return 1
    print("publish guard: no state lost its pages")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
