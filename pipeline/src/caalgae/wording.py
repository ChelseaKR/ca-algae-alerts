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
# An advisory whose level was last posted longer ago than this, measured
# against the state's file date, gets a sentence saying how old it is
# (decision 0017).
STALE_DAYS = 90
_TIER_ORDER = {"danger": 4, "warning": 3, "caution": 2, "other_advisory": 1}

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


# What a person should do after contact, paraphrased from the CDC ("If you
# or your animal go in water with an algal bloom, rinse off with tap water
# right after"; "contact a healthcare provider or the Poison Control hotline
# at 1-800-222-1222") and the California Water Boards' posted advisory signs
# ("Call your doctor or veterinarian if you or your pet get sick after going
# into the water") and HABs Portal infographic ("Shower immediately"). It
# adds no medical claim of its own.
HUMAN_ADVICE = (
    "If you or a child go in water that may have toxic algae, shower or rinse "
    "off with tap water right away. If anyone gets sick afterward, call a "
    "doctor or Poison Control at 1-800-222-1222."
)

NOT_MEDICAL_ADVICE = (
    "Lake Notice republishes state records for information only. It is not "
    "medical advice, and records can be late or wrong. In an emergency, call "
    "911. For a possible poisoning, call Poison Control at 1-800-222-1222."
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


# The sentence every status that is not an advisory carries (0002).
NOT_A_FINDING = "That is not a finding that the water is safe now."


def title_status(status: dict[str, Any], short: bool = False) -> str | None:
    """The headline's level and last posted date for a page title, such as
    "Danger advisory, last posted Nov 3, 2026": the headline's first
    sentence, so a title says nothing the status box does not. ``short``
    leaves out "last posted" ("Danger advisory, Nov 3, 2026") for a title
    that would not fit otherwise; the date is never left out. None for any
    status that is not an advisory (decision 0018). Website only, like
    ``summary``."""
    if status["kind"] != "advisory":
        return None
    when = date_label(status["posted"])
    return f"{level_name(status)}, {when if short else 'last posted ' + when}"


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
    # A place the name already carries ("Lake Havasu (Arizona)") is not repeated.
    where = f"{name} ({place})" if place and f"({place})" not in name else name
    if file_date:
        line = (
            f"As of the state's data dated {date_label(file_date)}, "
            f"the records for {where} show: {headline(status)}"
        )
    else:
        line = f"The state's records for {where} show: {headline(status)}"
    if status["kind"] != "advisory":
        line += f" {NOT_A_FINDING}"
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


def newest_posted(water: dict[str, Any]) -> str | None:
    """The newest date any of a water's spots had an advisory posted, with
    no all-clear since. It can be newer than the headline's date, which
    belongs to the highest level (decision 0017)."""
    dates = [
        str(site["status"]["posted"])
        for site in water.get("sites", [])
        if site["status"]["kind"] == "advisory" and site["status"]["posted"]
    ]
    return max(dates, default=water["status"].get("posted"))


def is_recent_water(water: dict[str, Any], run_date: dt.date) -> bool:
    """Any advisory at the water posted within ``RECENT_DAYS``, whatever its
    level, so a new lower posting is not hidden behind an older higher one."""
    return is_recent({"posted": newest_posted(water)}, run_date)


def newer_posting(water: dict[str, Any]) -> str | None:
    """The sentence for a newer posting at a lower level than the headline,
    or None when the headline's posting is the newest. Website only."""
    status = water["status"]
    if status["kind"] != "advisory":
        return None
    newest = newest_posted(water)
    if not newest or newest == status.get("posted"):
        return None
    at = [
        site["status"]
        for site in water["sites"]
        if site["status"]["kind"] == "advisory" and site["status"]["posted"] == newest
    ]
    top = max(at, key=lambda st: _TIER_ORDER.get(st.get("tier") or "", 0))
    spots = "1 reported spot" if len(at) == 1 else f"{len(at)} reported spots"
    return (
        f"The newest advisory posting here is lower: {level_name(top)}, "
        f"posted {date_label(newest)} at {spots}. No all-clear recorded."
    )


def older_higher(water: dict[str, Any]) -> str | None:
    """The sentence for an advisory at a higher level than the headline's,
    posted before the 12-month headline window and never lifted, or None.
    It stays on file and in view (0002); it no longer leads (0017).
    Website only."""
    status = water["status"]
    if status["kind"] != "advisory":
        return None
    rank = _TIER_ORDER.get(status.get("tier") or "", 0)
    higher = [
        site["status"]
        for site in water["sites"]
        if site["status"]["kind"] == "advisory"
        and site["status"]["posted"]
        and _TIER_ORDER.get(site["status"].get("tier") or "", 0) > rank
    ]
    if not higher:
        return None
    top_rank = max(_TIER_ORDER.get(st.get("tier") or "", 0) for st in higher)
    at_top = [
        st for st in higher if _TIER_ORDER.get(st.get("tier") or "", 0) == top_rank
    ]
    latest = max(str(st["posted"]) for st in at_top)
    spots = "1 reported spot" if len(at_top) == 1 else f"{len(at_top)} reported spots"
    return (
        f"An older, higher advisory is also on file: {level_name(at_top[0])}, "
        f"last posted {date_label(latest)} at {spots}. No all-clear recorded."
    )


def _age(days: int) -> str:
    if days >= 730:
        return f"more than {days // 365} years"
    if days >= 365:
        return "more than a year"
    return f"{days // 30} months"


def age_note(water: dict[str, Any], file_date: str | None) -> str | None:
    """How old the headline's posting is, when it is older than
    ``STALE_DAYS`` before the state's file date, and the date of the state's
    newest record of any kind for the water when that is newer. Silence
    still ends nothing (0002): this says how old the record is, never that
    the advisory has ended. Website only."""
    status = water["status"]
    if status["kind"] != "advisory" or not file_date or not status.get("posted"):
        return None
    posted = dt.date.fromisoformat(status["posted"])
    filed = dt.date.fromisoformat(file_date)
    days = (filed - posted).days
    if days <= STALE_DAYS:
        return None
    line = (
        f"That level was last posted {date_label(posted)}, {_age(days)} before "
        f"the state's data dated {date_label(filed)}, and the state has not "
        "recorded an end to it."
    )
    dates = [
        r["date"] for r in water.get("records", []) if not r.get("removed_from_source")
    ]
    newest = max(dates, default=None)
    if newest and newest > status["posted"]:
        line += (
            f" The state's newest record of any kind for {water['name']} is from "
            f"{date_label(newest)}."
        )
    return line
