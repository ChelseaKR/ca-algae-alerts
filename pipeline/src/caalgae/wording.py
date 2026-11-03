"""Every sentence the site uses to describe a status, in one place.

The rules (docs/DECISIONS.md 0002 and 0005):

- Never say a water is safe. The most the data supports is "the state's
  latest record recommended no advisory", with its date.
- An advisory reads "last posted <date>, no all-clear recorded" until the
  state records an explicit end.
- A date is always shown with a status. Nothing is "current" without one.
- Speak to everyone who uses the water: people, children and pets. Dogs get
  their own clearly labeled section, not the whole framing.
- Plain, calm words. No fear-led copy.

``ios/AlgaeCore/Sources/AlgaeCore/StatusWording.swift`` mirrors these
strings; a test on each side pins them.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

RECENT_DAYS = 30

TIER_LABEL = {
    "danger": "Danger",
    "warning": "Warning",
    "caution": "Caution",
}

# Who each level asks to take care, summarized from the posted-sign levels
# of the California Voluntary Guidance. The sign at the water and the
# state's own guidance govern; the about page says so.
LEVEL_GUIDANCE = {
    "caution": (
        "Algae that can make toxins may be present. Keep people, children "
        "and pets away from algae and scum, and do not let pets drink the water."
    ),
    "warning": (
        "Toxins may be at levels that can harm people and animals. Do not "
        "swim or let children or pets in the water, and stay away from scum."
    ),
    "danger": (
        "Toxins may be at levels that can seriously harm people and animals. "
        "Stay out of the water and keep children and pets away from the "
        "water and the shore."
    ),
    "other_advisory": (
        "The state recorded an advisory of a type outside the Caution, "
        "Warning and Danger levels. Read the sign posted at the water."
    ),
}

# For a state whose advisory levels are not California's Caution, Warning
# and Danger: no level-by-level summary is invented for them.
GENERIC_GUIDANCE = (
    "The state recorded an advisory here. Read the state's notice and any sign "
    "posted at the water, and keep people, children and pets out of discolored "
    "or scummy water."
)

SATELLITE_EXPLAINER = (
    "This is a satellite estimate from the U.S. EPA's Cyanobacteria Assessment "
    "Network, not an advisory. It estimates how much cyanobacteria is in the "
    "water near the lake's center, not whether toxins are present: a high "
    "number does not mean toxins, and a low one does not mean there are none. "
    "It covers lakes of about 1 square kilometer and larger, so small ponds, "
    "dog parks and most rivers are not covered, and clouds can hide a lake for "
    "weeks. It never changes the advisory status above."
)

DOG_ADVICE = (
    "Dogs are more exposed than people: they swim through scum, drink the "
    "water and lick algae off their fur. Where an advisory is on file, keep "
    "your dog out of the water and away from scum on the shore. If your dog "
    "does go in, rinse it with clean water and do not let it lick its coat. "
    "Call a veterinarian at once if your dog vomits, drools, stumbles or has "
    "a seizure after being near the water."
)


def date_label(day: dt.date | str | None) -> str:
    """``Oct 9, 2026``. Never called without a date: a missing date is a
    different sentence, not a blank."""
    if day is None:
        raise ValueError("a status sentence needs a date")
    if isinstance(day, str):
        day = dt.date.fromisoformat(day)
    return f"{day:%b} {day.day}, {day.year}"


def level_name(status: dict[str, Any]) -> str:
    """The state's own word for the level, with our label for the three
    standard levels."""
    tier = status.get("tier")
    if tier in TIER_LABEL:
        return f"{TIER_LABEL[tier]} advisory"
    return str(status.get("level") or "Advisory")


def headline(status: dict[str, Any]) -> str:
    """One line for a list row or a page's status box."""
    kind = status["kind"]
    if kind == "advisory":
        return (
            f"{level_name(status)}, last posted {date_label(status['posted'])}. "
            "No all-clear recorded."
        )
    if kind == "no_advisory_recorded":
        if status["lift_kind"] == "end_date":
            return (
                f"The state recorded an end date of {date_label(status['lift_date'])}."
            )
        if status["lift_kind"] == "dissipated":
            return (
                "The state recorded the bloom as dissipated on "
                f"{date_label(status['lift_date'])}."
            )
        return (
            "The state's latest record, from "
            f"{date_label(status['lift_date'])}, recommends no advisory."
        )
    return "Reports on file, with no advisory level the state has classified."


def summary(
    name: str, place: str | None, status: dict[str, Any], file_date: str | None
) -> str:
    """The first sentence of a water page: the answer to "is there an algae
    advisory at <name>?", with the date of the state's data it comes from,
    so it still reads correctly when quoted on its own (a search snippet, an
    assistant's answer). Built from ``headline``, so it says nothing the
    status box does not. Without a file date there is no "as of" clause: a
    missing date is left out, never filled in. A status that is not an
    advisory carries the not-safe sentence in the same paragraph. Website
    only: the app shows the status box, so StatusWording.swift has no copy."""
    where = f"{name} ({place})" if place else name
    if file_date:
        line = (
            f"As of the state's data dated {date_label(file_date)}, "
            f"the records for {where} show: {headline(status)}"
        )
    else:
        line = f"The state's records for {where} show: {headline(status)}"
    if status["kind"] != "advisory":
        line += " That is not a finding that the water is safe now."
    return line


def caveat(status: dict[str, Any]) -> str:
    """The sentence that keeps a status from reading as a promise."""
    if status["kind"] == "advisory":
        return (
            "Reporting is voluntary, so the state may not have recorded an end "
            "even if conditions changed. Check posted signs and the official map."
        )
    return (
        "That reflects what the state knew on that date. It is not a finding "
        "that the water is safe now: blooms can return within days, and many "
        "are never reported."
    )


def dog_answer(name: str, status: dict[str, Any]) -> str:
    """The honest answer to "is this lake safe for my dog?" for one water."""
    kind = status["kind"]
    if kind == "advisory":
        return (
            f"The state has an advisory on file for {name} ({level_name(status)}), "
            f"last posted {date_label(status['posted'])}, and no all-clear "
            "recorded. Keep your dog out of the water and away from scum on "
            "the shore until the state records an end."
        )
    if kind == "no_advisory_recorded":
        return (
            f"{headline(status)} For {name}, that is not the same as an "
            "all-clear for today. Look at the water "
            "before your dog goes in: keep it out of green, blue-green or "
            "scummy water and away from mats on the shore."
        )
    return (
        f"The state has reports on file for {name} but has not classified an "
        "advisory level, so the records cannot answer this. Keep your dog out "
        "of discolored or scummy water."
    )


def guidance_for(water: dict[str, Any]) -> str | None:
    tier = water["status"].get("tier")
    if not tier:
        return None
    if water["state"] == "CA":
        return LEVEL_GUIDANCE[tier]
    return GENERIC_GUIDANCE


def cells_label(cells: int) -> str:
    """``about 550,000 cells/mL``: estimates are rounded to two significant
    figures, because the satellite does not measure to the cell."""
    if cells <= 0:
        # A valid reading of zero is the satellite seeing the lake and finding
        # less than it can detect; a week it could not see has no entry.
        return "below what the satellite can detect"
    rounded = int(float(f"{cells:.2g}"))
    return f"about {rounded:,} cells/mL"


def is_recent(status: dict[str, Any], run_date: dt.date) -> bool:
    posted = status.get("posted")
    if not posted:
        return False
    return (run_date - dt.date.fromisoformat(posted)).days <= RECENT_DAYS
