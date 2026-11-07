"""States whose readers are built but switched off (DECISIONS 0037).

Each state has its own flag, an environment variable read like Trout
Truck's: exactly ``1`` is on; unset, empty and ``0`` are off; anything else
refuses the run, so a typo never turns a state on or silently leaves it off.

Off is the default and means the run is byte-identical to one without these
readers: nothing is fetched, nothing is printed, nothing is written.

On does not publish. A state whose flag is on is read (or a fixture is), its
records are normalized in the agency's own words, and a review file is
written to ``--state-review-out`` when given. Its records never enter the
history, the snapshot, the site or the app. Wiring a state into those is a
later change, made only after the agency's written yes.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
import os
from collections.abc import Callable, Mapping
from pathlib import Path

import httpx

from caalgae import fetch, kansas, oregon
from caalgae.history import record_to_json
from caalgae.normalize import Normalized
from caalgae.sources import KS_KDHE_HAB, OR_OHA_HAB, Source


class FlagError(ValueError):
    """A flag holds something other than unset, empty, ``0`` or ``1``."""


@dataclasses.dataclass(frozen=True)
class Reader:
    state: str
    flag: str
    source: Source
    fetch_pages: Callable[[httpx.Client], list[bytes]]
    normalize: Callable[[list[bytes], dt.date], Normalized]


READERS: dict[str, Reader] = {
    "OR": Reader(
        "OR", "LN_ENABLE_OREGON", OR_OHA_HAB, oregon.fetch_pages, oregon.normalize
    ),
    "KS": Reader(
        "KS", "LN_ENABLE_KANSAS", KS_KDHE_HAB, kansas.fetch_pages, kansas.normalize
    ),
}


def is_on(reader: Reader, environ: Mapping[str, str]) -> bool:
    value = environ.get(reader.flag, "")
    if value in {"", "0"}:
        return False
    if value == "1":
        return True
    raise FlagError(f"{reader.flag} must be unset, empty, 0 or 1, not {value!r}")


def enabled(environ: Mapping[str, str] | None = None) -> list[Reader]:
    env = os.environ if environ is None else environ
    return [r for r in READERS.values() if is_on(r, env)]


def parse_fixtures(values: list[str]) -> dict[str, list[Path]]:
    """``--state-fixture OR=path`` (repeatable; a state's pages in order)."""
    out: dict[str, list[Path]] = {}
    for value in values:
        state, sep, path = value.partition("=")
        if not sep or state not in READERS or not path:
            raise FlagError(
                f"--state-fixture takes STATE=PATH with STATE one of "
                f"{sorted(READERS)}, not {value!r}"
            )
        out.setdefault(state, []).append(Path(path))
    return out


def review_document(
    reader: Reader, normalized: Normalized, run_date: dt.date
) -> dict[str, object]:
    return {
        "not_published": (
            "Review only. This state's agency has not agreed to reuse; nothing "
            "here is published (DECISIONS 0037)."
        ),
        "state": reader.state,
        "flag": reader.flag,
        "source": reader.source.as_json(),
        "run_date": run_date.isoformat(),
        "rows_read": normalized.rows_read,
        "quarantine": dict(sorted(normalized.quarantine.items())),
        "records": [
            {"id": r.id, **record_to_json(r)}
            for r in sorted(normalized.records, key=lambda r: r.id)
        ],
    }


def review(
    *,
    run_date: dt.date,
    fixtures: Mapping[str, list[Path]],
    out_dir: Path | None,
    site_out: Path | None,
    environ: Mapping[str, str] | None = None,
    client_factory: Callable[[], httpx.Client] = fetch.make_client,
) -> None:
    """Read each state whose flag is on. With every flag off, return at once."""
    on = enabled(environ)
    stray = sorted(set(fixtures) - {r.state for r in on})
    if stray:
        raise FlagError(
            f"--state-fixture given for {stray} but its flag is off; "
            "a fixture never turns a state on"
        )
    if not on:
        return
    if out_dir is not None and site_out is not None:
        site = site_out.resolve()
        target = out_dir.resolve()
        if target == site or site in target.parents:
            raise FlagError("--state-review-out must not be inside --site-out")
    for reader in on:
        if reader.state in fixtures:
            pages = [p.read_bytes() for p in fixtures[reader.state]]
        else:
            with client_factory() as client:
                pages = reader.fetch_pages(client)
        normalized = reader.normalize(pages, run_date)
        print(
            f"caalgae: {reader.state} review only, not published: "
            f"{len(normalized.records)} records from {normalized.rows_read} rows"
        )
        if out_dir is not None:
            out_dir.mkdir(parents=True, exist_ok=True)
            path = out_dir / f"{reader.state.lower()}-review.json"
            body = review_document(reader, normalized, run_date)
            path.write_text(
                json.dumps(body, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
