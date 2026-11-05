"""How a water's name and place are shown on the site (DECISIONS 0009, "Display names").

The state files type names by hand: "Big bear lake ca", "Briars pond",
"crystal pool". Those spellings stay in the history and the snapshot exactly
as the state published them (the app and the snapshot's readers get the
source), and a water's id still comes from the source name (0009). The site
shows a display name built by three steps, in order:

1. **A reviewed override**, keyed by water id *and* the exact source name, for
   the few names no rule can fix. If the state ever retypes the name, the
   override stops applying and the rules take over, so an override can never
   rename a different spelling.
2. **A trailing state suffix is dropped**, only when it is the water's own
   state: " ca" after a water word for California ("Big bear lake ca"), and
   ", MO" or ", Missouri" after a comma for Missouri ("Corby Pond St. Joseph,
   MO"). Missouri's " CA" means a conservation area ("Little Prairie CA") and
   is kept, and so is a name that is a state word ("Lake California").
3. **Casing**: a name that starts with a lowercase letter gets a capital.
   A proper name typed partly in lowercase ("Diamond valley lake", "Lake
   herman", "Central Park lake") is capitalized when its lowercase words are
   one run at the end and a water word ("lake", "pond", "creek" ...) is its
   first or last word. Descriptions ("Unnamed pond", "Private pond",
   "Neighborhood detention pond"), names with a comma, and words such as "of"
   and "du" are left as typed. Words are never removed, so "Fee fee creek"
   becomes "Fee Fee Creek", its real name, not "Fee Creek".

A place is the county, or for a water with none, what the source says in its
place. California's "Nevada State" and "Arizona State" are other states, so
they show as "Nevada" and "Arizona", the way a Missouri water shows
"Missouri". Any other text that names no California county shows nothing: a
county is never guessed.
"""

from __future__ import annotations

import re
from typing import Any

# Words that make a name a water's proper name when they lead or end it.
WATER_WORDS = frozenset(
    {
        "area", "basin", "bay", "canal", "channel", "creek", "dam", "lac",
        "lagoon", "lake", "lakes", "marsh", "park", "pond", "ponds", "pool",
        "reservoir", "river", "shoals", "slough", "spring", "springs",
    }
)  # fmt: skip
# Kept lowercase inside a name, and never a reason to capitalize one.
CONNECTORS = frozenset(
    {"a", "adj", "and", "at", "by", "de", "del", "du", "for", "in", "near",
     "of", "on", "the", "to"}
)  # fmt: skip
# A name that starts with one of these describes a water rather than naming
# it ("Unnamed pond", "Private pond"); only its first letter is capitalized.
DESCRIPTIVE_STARTS = frozenset(
    {"former", "neighborhood", "plumbing", "private", "small", "unknown", "unnamed"}
)

# Reviewed one-off display names: (water id, exact source name) -> display.
# Each is a casing fix a rule cannot make safely. Reviewed 2026-11-04 against
# the snapshot of that date.
OVERRIDES: dict[tuple[str, str], str] = {
    # "fish grotto" ends in no water word; it is a pond's proper name.
    ("ca-san-diego-anthonys-fish-grotto", "Anthony\u2019s fish grotto"): (
        "Anthony\u2019s Fish Grotto"
    ),
    # The name ends "no. 1" before its parenthesis.
    (
        "mo-cameron-reservoir-no-1-century-lake",
        "Cameron reservoir no. 1 (Century Lake)",
    ): "Cameron Reservoir No. 1 (Century Lake)",
    # The river and its county run together; the comma is display only.
    ("mo-james-river-christian-county", "James river Christian county"): (
        "James River, Christian County"
    ),
}

_CA_SUFFIX = re.compile(r"^(?P<head>.*\S)[ ,]+ca$", re.IGNORECASE)
_MO_SUFFIX = re.compile(r"^(?P<head>.*\S),\s*(?:mo|missouri)$", re.IGNORECASE)
_OTHER_STATE = re.compile(r"^(?P<state>Arizona|Nevada|Oregon) State$")


def _last_word(text: str) -> str:
    words = text.split()
    return words[-1].casefold().strip(".,") if words else ""


def strip_state_suffix(name: str, state: str) -> str:
    """``name`` without a trailing suffix naming the water's own state."""
    if state == "CA":
        found = _CA_SUFFIX.match(name)
        if found and _last_word(found["head"]) in WATER_WORDS:
            return found["head"]
    elif state == "MO":
        found = _MO_SUFFIX.match(name)
        if found:
            return found["head"]
    return name


def _capitalize(word: str) -> str:
    return word[:1].upper() + word[1:]


def _is_lower(word: str) -> bool:
    return word[:1].isalpha() and word[:1].islower()


def fix_casing(name: str) -> str:
    """``name`` with the casing rule applied; see the module docstring."""
    if not name:
        return name
    head, sep, tail = name.partition(" (")
    words = head.split(" ")
    first = words[0].casefold()
    if first in DESCRIPTIVE_STARTS or "," in head:
        return _capitalize(name)
    lower = [i for i, w in enumerate(words) if _is_lower(w) and w not in CONNECTORS]
    anchored = first in WATER_WORDS or words[-1].casefold() in WATER_WORDS
    if not lower or not anchored or words[-1] in CONNECTORS:
        return _capitalize(name)
    start = lower[0]
    run = words[start:]
    if any(not (_is_lower(w) or w in CONNECTORS) for w in run):
        return _capitalize(name)
    fixed = [
        w if i < start or w in CONNECTORS else _capitalize(w)
        for i, w in enumerate(words)
    ]
    return _capitalize(" ".join(fixed)) + sep + tail


def display_name(water_id: str, source_name: str, state: str) -> str:
    """The name the site shows for a water; the source name is unchanged."""
    override = OVERRIDES.get((water_id, source_name))
    if override is not None:
        return override
    return fix_casing(strip_state_suffix(source_name, state))


def display_place_text(county_text: str, counties: list[str]) -> str:
    """What the site shows where a water's county would be, from the
    source's county text. A county the source names is shown as before
    (the caller adds "County"). "Nevada State" shows as "Nevada". Any other
    text that names no California county shows as "": nothing is guessed."""
    if counties or not county_text:
        return county_text
    other = _OTHER_STATE.match(county_text)
    return other["state"] if other else ""


def display_water(water: dict[str, Any]) -> dict[str, Any]:
    """A shallow copy of a snapshot water with its display name and place,
    and the source's spelling as ``source_name``. The snapshot's own dict is
    not changed, so ``snapshot/v1.json`` still carries the source's spelling."""
    return {
        **water,
        "source_name": water["name"],
        "name": display_name(water["id"], water["name"], water["state"]),
        "county_text": display_place_text(water["county_text"], water["counties"]),
    }
