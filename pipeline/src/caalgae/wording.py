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
        return (
            "The state's latest record, from "
            f"{date_label(status['lift_date'])}, recommends no advisory."
        )
    return "Reports on file, with no advisory level the state has classified."


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
            f"The state has a {level_name(status).lower()} on file for {name}, "
            f"last posted {date_label(status['posted'])}, and no all-clear "
            "recorded. Keep your dog out of the water and away from scum on "
            "the shore until the state records an end."
        )
    if kind == "no_advisory_recorded":
        return (
            f"The state's latest record for {name} recommends no advisory, but "
            "that is not the same as an all-clear for today. Look at the water "
            "before your dog goes in: keep it out of green, blue-green or "
            "scummy water and away from mats on the shore."
        )
    return (
        f"The state has reports on file for {name} but has not classified an "
        "advisory level, so the records cannot answer this. Keep your dog out "
        "of discolored or scummy water."
    )


def is_recent(status: dict[str, Any], run_date: dt.date) -> bool:
    posted = status.get("posted")
    if not posted:
        return False
    return (run_date - dt.date.fromisoformat(posted)).days <= RECENT_DAYS
