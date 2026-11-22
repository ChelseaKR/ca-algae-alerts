"""Refuse a file that changes more statuses in one run than a real file does
(docs/DECISIONS.md 0044).

The other guards look at the file's shape: columns, dates, withdrawn records,
quarantined rows. A file can pass all of them and still be wrong, with every
record in place and its level changed. So this compares what the site would
say before and after the merge, water by water, on the same run date:

- a water's status **drops** when it leaves an advisory (to "no advisory
  recorded" or to undetermined) or stays in one at a lower level;
- the **count** is the number of waters under an advisory.

A run is refused when more waters drop than ``MAX_DROP_SHARE`` of the waters
under an advisory before it (never fewer than ``MIN_DROP_WATERS``), or when
the count moves, up or down, by more than ``MAX_COUNT_SHARE`` of what it was
(never fewer than ``MIN_COUNT_WATERS``). The figures come from this
repository's own record of real changes; the arithmetic is in 0044.

Both sides are read on the same run date, so an advisory whose planned end
date passes overnight is not a change: no file made it. A source read for the
first time has nothing to compare with and is not checked.

This is a publishing gate only. It decides whether a run is published, and
it writes no word of any page.
"""

from __future__ import annotations

import dataclasses
import datetime as dt

from caalgae import history as hist
from caalgae import snapshot
from caalgae import status as st
from caalgae.normalize import TIER_RANK

# More waters dropping than this share of the waters under an advisory
# refuses the run. California, 2016 to 2026: the most on one record date is
# 6 (2.2%), in any 7 days 13 (4.6%), in any 14 days 18 (4.1%).
MAX_DROP_SHARE = 0.05
# A small source: 5% of Missouri's 47 is 2, and one busy day could reach it.
MIN_DROP_WATERS = 5
# The count of waters under an advisory moving by more than this share,
# either way, refuses the run. New advisories on one record date: at most 13;
# in any 14 days, 23.
MAX_COUNT_SHARE = 0.10
MIN_COUNT_WATERS = 25

_EXAMPLES = 5


class MassChange(RuntimeError):
    """The file would change too many statuses at once. Nothing is written.

    ``summary`` is what was measured; the full message adds what happens
    next and the owner's override. Both are built from counts and this
    pipeline's own water ids, never from the source's text."""

    def __init__(self, summary: str, flag: str) -> None:
        self.summary = summary
        super().__init__(
            f"{summary} A change that size looks like a wrong file. The last "
            "good data stays published. If the agency really did change this "
            f"much, read its file, then run the publish workflow with {flag}."
        )


@dataclasses.dataclass(frozen=True)
class Change:
    """One source's statuses before and after a merge."""

    before: int
    after: int
    left: tuple[str, ...]
    lowered: tuple[str, ...]

    @property
    def dropped(self) -> tuple[str, ...]:
        return (*self.left, *self.lowered)

    @property
    def drop_limit(self) -> int:
        return max(MIN_DROP_WATERS, int(MAX_DROP_SHARE * self.before))

    @property
    def count_limit(self) -> int:
        return max(MIN_COUNT_WATERS, int(MAX_COUNT_SHARE * self.before))


def _statuses(
    history: hist.History, source: str, run_date: dt.date
) -> dict[str, tuple[str, int]]:
    """Each water's status kind and level rank, as the snapshot builds it."""
    waters = snapshot.build_waterbodies(
        (e for e in history.entries.values() if e.record.source == source), run_date
    )
    return {
        str(w["id"]): (
            str(w["status"]["kind"]),
            TIER_RANK.get(str(w["status"]["tier"]), 0),
        )
        for w in waters
    }


def measure(
    before: hist.History, after: hist.History, *, source: str, run_date: dt.date
) -> Change:
    was = _statuses(before, source, run_date)
    now = _statuses(after, source, run_date)
    left: list[str] = []
    lowered: list[str] = []
    for water, (kind, rank) in sorted(was.items()):
        if kind != st.ADVISORY:
            continue
        kind_now, rank_now = now.get(water, (st.UNDETERMINED, 0))
        if kind_now != st.ADVISORY:
            left.append(water)
        elif rank_now < rank:
            lowered.append(water)
    return Change(
        before=sum(1 for kind, _ in was.values() if kind == st.ADVISORY),
        after=sum(1 for kind, _ in now.values() if kind == st.ADVISORY),
        left=tuple(left),
        lowered=tuple(lowered),
    )


def check(
    before: hist.History,
    after: hist.History,
    *,
    source: str,
    label: str,
    run_date: dt.date,
    accept: bool = False,
    flag: str = "accept_status_change",
) -> Change:
    """The change this merge makes, or ``MassChange`` when it is past a limit.

    ``label`` names the source in the message ("California's file").
    ``accept`` is the owner's override, after reading the file."""
    change = measure(before, after, source=source, run_date=run_date)
    if accept or before.last_file(source) is None:
        return change
    if len(change.dropped) > change.drop_limit:
        examples = ", ".join(change.dropped[:_EXAMPLES])
        raise MassChange(
            f"{label} would take {len(change.left)} of {change.before} waters "
            f"out of an advisory and lower {len(change.lowered)} more in one "
            f"run ({len(change.dropped)} in all; the limit is "
            f"{change.drop_limit}), starting with {examples}.",
            flag,
        )
    moved = change.after - change.before
    if abs(moved) > change.count_limit:
        raise MassChange(
            f"{label} would move the number of waters under an advisory from "
            f"{change.before} to {change.after} in one run (a change of "
            f"{abs(moved)}; the limit is {change.count_limit}).",
            flag,
        )
    return change
