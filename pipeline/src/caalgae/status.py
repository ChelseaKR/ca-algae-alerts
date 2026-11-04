"""What the records say about each reported site and each waterbody.

The one rule (docs/DECISIONS.md 0002): an advisory stands until the state
records an explicit end. Silence never ends one.

For a site (one bloom report: one reported location), the records are
ordered by advisory date, then the state's timestamp, then id. Only two
kinds of record decide anything:

- an advisory (Caution, Warning, Danger, or one of the state's other
  advisory types), and
- the state's explicit "None" (no advisory recommended), or Missouri's
  dissipated case with its date; ``lift_kind`` names which.

"NA - refer to Report Details" and a blank level decide nothing, so they
can neither raise nor end an advisory. The latest deciding record wins.
An advisory record that carries an end date on or before the run date is
also an explicit end (``lift_kind = "end_date"``); a blank end date is
unknown and changes nothing.

A waterbody shows an advisory if any of its sites does. Its level is the
highest among those sites, and its posted date is the date that level was
last posted, never another site's date: a 2020 Danger at one spot and a 2026
Caution at another is "Danger, last posted 2020", not "Danger, posted 2026"
(decision 0017). The newer, lower posting is shown beside it by the site.

A "site" here is a reported spot, which ``snapshot`` identifies by the
state's coordinates (decision 0017): the state files the same monitoring
spot under a new bloom report each season, so a later "None" at the same
coordinates is an explicit record at the same spot.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
from collections.abc import Iterable

from caalgae.normalize import TIER_RANK, Record

ADVISORY = "advisory"
NO_ADVISORY_RECORDED = "no_advisory_recorded"
UNDETERMINED = "undetermined"


@dataclasses.dataclass(frozen=True)
class Status:
    kind: str
    tier: str | None = None
    level: str | None = None
    posted: dt.date | None = None
    planned_end: dt.date | None = None
    lift_kind: str | None = None
    lift_date: dt.date | None = None
    last_advisory: dt.date | None = None
    sites_with_advisory: int = 0


def _deciding(record: Record) -> bool:
    return record.is_advisory or record.explicit_no_advisory


def site_status(records: Iterable[Record], run_date: dt.date) -> Status:
    ordered = sorted(records, key=Record.sort_key)
    advisories = [r for r in ordered if r.is_advisory]
    last_advisory = advisories[-1].date if advisories else None
    deciding = [r for r in ordered if _deciding(r)]
    if not deciding:
        return Status(kind=UNDETERMINED, last_advisory=last_advisory)
    latest = deciding[-1]
    if latest.explicit_no_advisory:
        return Status(
            kind=NO_ADVISORY_RECORDED,
            lift_kind=latest.end_kind,
            lift_date=latest.date,
            last_advisory=last_advisory,
        )
    if latest.end_date is not None and latest.end_date <= run_date:
        return Status(
            kind=NO_ADVISORY_RECORDED,
            lift_kind="end_date",
            lift_date=latest.end_date,
            last_advisory=last_advisory,
        )
    return Status(
        kind=ADVISORY,
        tier=latest.tier,
        level=latest.level,
        posted=latest.date,
        planned_end=latest.end_date,
        last_advisory=last_advisory,
        sites_with_advisory=1,
    )


def water_status(site_statuses: Iterable[Status]) -> Status:
    statuses = list(site_statuses)
    last_advisory = max(
        (s.last_advisory for s in statuses if s.last_advisory), default=None
    )
    advisories = [s for s in statuses if s.kind == ADVISORY]
    if advisories:
        # The highest level, and of the sites at that level the one posted
        # last. Its date goes with its level: another site's newer posting
        # at a lower level never dates this one.
        top = max(
            advisories,
            key=lambda s: (TIER_RANK[s.tier or ""], s.posted or dt.date.min),
        )
        return Status(
            kind=ADVISORY,
            tier=top.tier,
            level=top.level,
            posted=top.posted,
            planned_end=top.planned_end,
            last_advisory=last_advisory,
            sites_with_advisory=len(advisories),
        )
    lifted = [s for s in statuses if s.kind == NO_ADVISORY_RECORDED]
    if lifted:
        latest = max(lifted, key=lambda s: s.lift_date or dt.date.min)
        return Status(
            kind=NO_ADVISORY_RECORDED,
            lift_kind=latest.lift_kind,
            lift_date=latest.lift_date,
            last_advisory=last_advisory,
        )
    return Status(kind=UNDETERMINED, last_advisory=last_advisory)
