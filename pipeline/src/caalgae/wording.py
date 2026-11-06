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

# Who each level asks to take care, paraphrased from the state's own
# posted-sign wording. The sign at the water and the state's own guidance
# govern; the about page says so. Sources, read 2026-11-05:
#
# California HAB program, "Posting Signs" (posted-sign levels of the
# California Voluntary Guidance),
# https://mywaterquality.ca.gov/habs/resources/signage.html
#   CAUTION: "Do not let pets and other animals go into or drink the water,
#     or eat scum on the shore." "Keep children away from algae in the water
#     and on the shore." "Do not drink the water or use it for cooking."
#     "For fish caught here, throw away guts and clean fillets with tap water
#     or bottled water before cooking." "Do not eat shellfish from this water."
#   WARNING: "No swimming." "Do not let pets and other animals go into or
#     drink the water, or eat scum on the shore." "Stay away from scum, and
#     cloudy or discolored water." "Do not use this water for drinking or
#     cooking. Boiling or filtering will not make the water safe." (and the
#     same fish and shellfish lines as CAUTION)
#   DANGER: "Stay out of the water until further notice." "Do not let pets
#     and other animals drink or go into the water, or go near the scum."
#     "Do not eat fish or shellfish from this water." "Do not use this water
#     for drinking or cooking. Boiling or filtering will not make the water
#     safe."
#
# California HAB program, toxic algal mat signs,
# https://mywaterquality.ca.gov/habs/docs/toxic-algal-mat-signs.pdf
#   "Mats can be attached to the bottom, detached and floating, or washed up
#   on shore." "Do NOT let children or adults touch, eat, or swallow any
#   algal mats." "Do NOT let dogs eat algal mats or drink from the water."
#   "Call your doctor or veterinarian if you or your pet get sick after
#   contacting or ingesting algae."
#
# The drinking and cooking sentence is on every level, not only Warning and
# Danger: no level of advisory makes the water fit to drink.
WATER_USE = (
    "Do not drink this water or cook with it; boiling or filtering does not "
    "make it safe."
)
_FISH = (
    "For fish caught here, throw away the guts and clean fillets with tap or "
    "bottled water before cooking. Do not eat shellfish from this water."
)

LEVEL_GUIDANCE = {
    "caution": (
        "Algae that can make toxins may be present. Keep people, children "
        "and pets away from algae and scum in the water and on the shore. Do "
        "not let pets or other animals go into or drink the water, or eat "
        f"scum on the shore. {WATER_USE} {_FISH}"
    ),
    "warning": (
        "Toxins may be at levels that can harm people and animals. Do not "
        "swim or let children in the water, and stay away from scum and "
        "cloudy or discolored water. Do not let pets or other animals go into "
        f"or drink the water, or eat scum on the shore. {WATER_USE} {_FISH}"
    ),
    "danger": (
        "Toxins may be at levels that can seriously harm people and animals. "
        "Stay out of the water and keep children away from the water and the "
        "shore. Do not let pets or other animals go into or drink the water, "
        f"or go near the scum. {WATER_USE} Do not eat fish or shellfish from "
        "this water."
    ),
    "algal_mat": (
        "Toxic algal mats may be present. Mats can be attached to the bottom, "
        "floating, or washed up on shore. Do not let dogs eat algal mats or "
        "drink from the water, and do not let children or adults touch, eat "
        f"or swallow any algal mats. {WATER_USE} Call a doctor or "
        "veterinarian if you or your pet get sick after contact with algae."
    ),
    "other_advisory": (
        "The state recorded an advisory of a type outside the Caution, "
        "Warning and Danger levels. Read the sign posted at the water. "
        f"{WATER_USE}"
    ),
}


def is_algal_mat(level: str | None) -> bool:
    """The state's two toxic algal mat signs ("Algal mat alert sign",
    "Algal mat general awareness sign") share one tier with other
    non-standard levels; their guidance comes from the mat signs."""
    return "algal mat" in (level or "").casefold()


# For a state whose advisory levels are not California's Caution, Warning
# and Danger: no level-by-level summary is invented for them.
GENERIC_GUIDANCE = (
    "The state recorded an advisory here. Read the state's notice and any sign "
    "posted at the water, and keep people, children and pets out of discolored "
    "or scummy water."
)

# Missouri's advisories have no levels, so one summary of the Department of
# Natural Resources' own guidance, read 2026-11-05:
# https://dnr.mo.gov/water/hows-water/pollutants-sources/harmful-algal-blooms-habs/animal-health
#   "Do not let pets drink or play in the water or roll in or eat the algae,
#   even if dried."
# https://dnr.mo.gov/water/hows-water/pollutants-sources/harmful-algal-blooms-habs/human-health
#   "we recommend you do not eat fish from affected areas for two weeks after
#   the bloom visually dissipates." "remove all fat, skin and organs before
#   cooking" "Always cook fish thoroughly."
# The department's pages do not mention boiling or filtering; the WATER_USE
# sentence is California's wording and holds for the same toxins.
STATE_GUIDANCE = {
    "MO": (
        f"{GENERIC_GUIDANCE} Do not let pets drink or play in the water or roll "
        f"in or eat the algae, even if dried. {WATER_USE} The department advises "
        "not eating fish from the area for two weeks after the bloom visually "
        "dissipates; if you do, remove all fat, skin and organs and cook the "
        "fish thoroughly."
    ),
}

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
    if status.get("level"):
        return (
            f"The state's latest record says \u201c{status['level']}\u201d, a level "
            "this site does not recognize, so it cannot say what applies. Check "
            "the official map."
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
    if status.get("level"):
        return (
            f"{headline(status)} Until it is read, keep your dog out of the "
            f"water at {name} and away from scum on the shore."
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
        if tier == "other_advisory" and is_algal_mat(water["status"].get("level")):
            return LEVEL_GUIDANCE["algal_mat"]
        return LEVEL_GUIDANCE[tier]
    return STATE_GUIDANCE.get(water["state"], GENERIC_GUIDANCE)


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


# A list row older than this, against the state's file date, says how old
# it is: county and state lists put years-old records beside current ones.
LIST_STALE_DAYS = 365

LIST_CAVEAT = (
    "Older records are not current conditions. A record says what the state "
    "knew on its date, not that a water is safe now: check posted signs and "
    "the state's map before you go."
)


def row_date(water: dict[str, Any]) -> str | None:
    """The date a list row's status rests on: the headline's posting or
    lift date, or for a status with neither, the newest record on file."""
    status = water["status"]
    day = status.get("posted") if status["kind"] == "advisory" else None
    day = day or status.get("lift_date")
    if day:
        return str(day)
    dates = [
        r["date"] for r in water.get("records", []) if not r.get("removed_from_source")
    ]
    return max(dates, default=None)


def list_row(water: dict[str, Any], file_date: str | None) -> str:
    """A county or state list row: the headline, the newest record's date
    when the headline carries none, and how old the record is when it is
    more than ``LIST_STALE_DAYS`` before the state's file date. Website only."""
    line = headline(water["status"])
    day = row_date(water)
    if day and water["status"]["kind"] == "undetermined":
        line += f" Newest record {date_label(day)}."
    if day and file_date:
        days = (dt.date.fromisoformat(file_date) - dt.date.fromisoformat(day)).days
        if days > LIST_STALE_DAYS:
            line += f" This record is {_age(days)} old."
    return line


def list_sort_key(water: dict[str, Any]) -> tuple[bool, int, str]:
    """Advisories first, then newest first within each group, so current
    records lead and years-old ones sink."""
    status = water["status"]
    day = (newest_posted(water) if status["kind"] == "advisory" else None) or row_date(
        water
    )
    ordinal = dt.date.fromisoformat(day).toordinal() if day else 0
    return (status["kind"] != "advisory", -ordinal, water["name"].casefold())


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


# -- winter records (DECISIONS 0028) ------------------------------------------
#
# A quiet winter is not an all-clear. "Winter" is November through February,
# calendar months, not a state term. Every number comes from the state's own
# records at build time; none is written here. These are templates so the
# Spanish catalog (i18n.EN) reads the same words. Website only for now: the
# app's StatusWording.swift follows in its own change (#23).

WINTER_MONTHS = (11, 12, 1, 2)

WINTER_HEADING = "Winter records at {name}"
WINTER_TOTAL = (
    "In past winters (November through February), the state posted {records} "
    "for {name}."
)
WINTER_LATEST = "The latest winter posting was on {date}: {level}."
WINTER_LAST = "Last winter ({season}) it posted {records}, the last on {date}."
WINTER_ENDS = (
    "An advisory stays in effect until the state records an end; winter does "
    "not end it."
)
WINTER_NO_LEVEL = (
    "The state posted {records} for {name} in November through February, none "
    "of them at an advisory level. That is not a finding that the water is "
    "free of toxic algae in winter."
)
WINTER_ABSENT = (
    "None of the state's records for {name}, which begin on {first}, were "
    "posted in November through February. That is not a finding that the "
    "water is free of toxic algae: across the state's file, {december} were "
    "posted in all Decembers on file, against {peak} in all {peak_month}s."
)
WINTER_UNCOVERED = (
    "The state's records for {name} begin on {first}, after the start of the "
    "last whole winter, so they cannot say whether advisories are posted here "
    "in winter."
)
WINTER_TABLE_CAPTION = "Advisory records at {name} by winter, newest first"
WINTER_ADVISORY_ONE = "1 advisory record"
WINTER_ADVISORY_MANY = "{count} advisory records"
WINTER_RECORD_ONE = "1 record"
WINTER_RECORD_MANY = "{count} records"

DOGS_WINTER_POSTED = (
    "Algae advisories here have been posted in winter too: see Winter records."
)
DOGS_WINTER_NO_LEVEL = (
    "None of the state's winter records here is at an advisory level. That is "
    "not a finding that the water is free of toxic algae in winter."
)
DOGS_WINTER_ABSENT = (
    "None of the state's records here were posted in November through "
    "February. That is not a finding that the water is free of toxic algae in "
    "winter: look at the water before your dog goes in."
)

DOGS_PAGE_WINTER = (
    "the state still posts algae advisories. Its California file holds "
    "advisory records from {months}: {november} from Novembers, {december} "
    "from Decembers, {january} from Januaries and {february} from Februaries, "
    "against {peak} from {peak_month}s. Most lakes are never tested in any "
    "month. A winter visit gets the same check as a summer one: the lake's "
    "page, the state's map and the signs at the water."
)
DOGS_PAGE_EVERY_MONTH = "every month of the year"
DOGS_PAGE_SOME_MONTHS = "{count} of the 12 months"


def _count(n: int, one: str, many: str) -> str:
    return one if n == 1 else many.format(count=f"{n:,}")


def advisory_records(n: int) -> str:
    return _count(n, WINTER_ADVISORY_ONE, WINTER_ADVISORY_MANY)


def any_records(n: int) -> str:
    return _count(n, WINTER_RECORD_ONE, WINTER_RECORD_MANY)


def winter_lines(name: str, winter: dict[str, Any]) -> list[str]:
    """The sentences of a water page's "Winter records" section, from
    ``site.winter_record``. Never "safe", never "no advisory": a water with
    no winter record gets the not-a-finding sentence with the state's month
    counts, and a record too short to cover a winter says so."""
    kind = winter["kind"]
    if kind == "advisories":
        lines = [
            WINTER_TOTAL.format(records=advisory_records(winter["count"]), name=name),
            WINTER_LATEST.format(
                date=date_label(winter["latest"]["date"]),
                level=level_name(winter["latest"]),
            ),
        ]
        last = winter.get("last_winter")
        if last:
            lines.append(
                WINTER_LAST.format(
                    season=last["label"],
                    records=advisory_records(last["count"]),
                    date=date_label(last["last_date"]),
                )
            )
        return [*lines, WINTER_ENDS]
    if kind == "no_advisory_level":
        return [
            WINTER_NO_LEVEL.format(records=any_records(winter["any_count"]), name=name)
        ]
    if kind == "absent":
        months = winter["state_months"]
        return [
            WINTER_ABSENT.format(
                name=name,
                first=date_label(winter["first"]),
                december=any_records(months["december"]),
                peak=f"{months['peak']:,}",
                peak_month=months["peak_month"],
            )
        ]
    return [WINTER_UNCOVERED.format(name=name, first=date_label(winter["first"]))]


def dogs_winter_line(winter: dict[str, Any] | None, run_date: dt.date) -> str | None:
    """The one winter sentence the "Dogs at" section adds from November
    through February (by the snapshot's run date), or None."""
    if winter is None or run_date.month not in WINTER_MONTHS:
        return None
    return {
        "advisories": DOGS_WINTER_POSTED,
        "no_advisory_level": DOGS_WINTER_NO_LEVEL,
        "absent": DOGS_WINTER_ABSENT,
    }.get(winter["kind"])


def dogs_page_winter(months: dict[str, Any] | None) -> str | None:
    """The /dogs/ "In winter" sentence from the state's advisory counts per
    calendar month, or None when the file has no winter advisory at all
    (then the page claims nothing about winter)."""
    if not months or not any(
        months[m] for m in ("november", "december", "january", "february")
    ):
        return None
    span = (
        DOGS_PAGE_EVERY_MONTH
        if months["months_with"] == 12
        else DOGS_PAGE_SOME_MONTHS.format(count=months["months_with"])
    )
    return DOGS_PAGE_WINTER.format(
        months=span,
        **{
            k: f"{months[k]:,}"
            for k in ("november", "december", "january", "february", "peak")
        },
        peak_month=months["peak_month"],
    )
