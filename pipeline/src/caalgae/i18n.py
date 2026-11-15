"""The Spanish catalog, its review gate, and the rendered-page check
(DECISIONS 0025).

Nothing here publishes while the flags are off. ``LEVELS_ENABLED`` builds the
English /levels/ page; ``ES_ENABLED`` builds its Spanish twin, /es/niveles/.
Both are False on main.

The rules, from growth/spanish-pages-plan-tt-ln-2026-11-05.md section 4:

- The state's Spanish wins. A ``state`` string is the state's own words,
  pasted by a person from a browser, with its URL, the date read and a
  SHA-256 of the text, so an edit to "verbatim" text fails the gate.
- No safety string ships until a person has reviewed it. An agent may draft
  one, labeled ``draft``; with ``ES_ENABLED`` a draft safety string, or any
  string still holding a paste placeholder, fails the build.
- A missing string fails the build. There is no English fallback.
- A Spanish value identical to English must be declared ``same`` (or still be
  ``draft``), the convention Family Greenhouse's
  ``check-i18n-catalogs.mjs`` uses (``intentionallyEqual`` and ``todo``).
- A built /es/ page is checked after rendering, so English cannot slip in
  through a template literal.

The English strings are not moved out of ``wording.py``: the English catalog
below reads them from it, so English output stays byte-for-byte the same and
the existing wording tests keep pinning it.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import html
import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

from caalgae import newyork, sources, wording

# Off on main. Turning on ES_ENABLED needs every safety string reviewed or
# pasted from the state (the gate below fails the build otherwise) and waits
# for hreflang, which waits for the ~2026-11-25 read of the dated titles.
LEVELS_ENABLED = False
ES_ENABLED = False

STATUSES = ("state", "reviewed", "same", "draft")
# A value still waiting for Chelsea's paste from the state's sign. Never
# built into a published page.
PLACEHOLDER = "⟦PEGAR"

# The state's posted-sign page, the source of the English sign quotes below
# (wording.py's comment block; quotes checked by Chelsea Kelly-Reif in a
# browser on 2026-11-05) and of the Spanish sign text still to be pasted.
# This host's robots.txt allows only Googlebot, so it is read by hand, never
# by the pipeline or an agent.
SIGN_URL = "https://mywaterquality.ca.gov/habs/resources/signage.html"
MAT_SIGN_URL = "https://mywaterquality.ca.gov/habs/docs/toxic-algal-mat-signs.pdf"
EN_SIGN_READ_ON = dt.date(2026, 11, 5)

TIERS = ("caution", "warning", "danger", "algal_mat", "other_advisory")
SIGNED_TIERS = ("caution", "warning", "danger", "algal_mat")

_FISH_SIGN = (
    '"For fish caught here, throw away guts and clean fillets with tap water '
    'or bottled water before cooking." "Do not eat shellfish from this water."'
)
_NO_BOIL = (
    '"Do not use this water for drinking or cooking. Boiling or filtering will '
    'not make the water safe."'
)

EN: dict[str, str] = {
    # page chrome (_base_i18n.html.jinja); English values match base.html.jinja
    "chrome.skip": "Skip to main content",
    "chrome.tagline": "Lake & river toxic algae advisories",
    "chrome.other_language": "En español",
    "nav.label": "Primary",
    "nav.breadcrumb": "Breadcrumb",
    "nav.home": "Home",
    "nav.latest": "Latest",
    "nav.advisories": "All advisories",
    "nav.county": "By county",
    "nav.missouri": "Missouri",
    "nav.ny_history": "New York history",
    "nav.dogs": "Dogs",
    "nav.about": "About",
    "state.CA": "California",
    "state.MO": "Missouri",
    "footer.attribution.ca-swrcb-fhab": sources.CA_SWRCB_FHAB.attribution,
    "footer.attribution.mo-dnr-hab": sources.MO_DNR_HAB.attribution,
    "footer.attribution.epa-cyan": sources.EPA_CYAN.attribution,
    "footer.attribution.ny": newyork.ATTRIBUTION,
    "footer.ny_source": "Source and terms",
    "footer.not_medical_advice": wording.NOT_MEDICAL_ADVICE,
    "footer.independent": (
        "{site_name} is independent and is not affiliated with or endorsed by "
        "any state or federal agency."
    ),
    "footer.disclaimer_link": "{state} data disclaimer",
    "footer.file": "California data file {file_name}, read {date}. Official map:",
    "footer.dataset": "Dataset on data.ca.gov",
    "footer.about": "about the data",
    "footer.privacy": "privacy",
    "footer.terms": "terms",
    "footer.support": "support",
    "footer.analytics_opt_out": "Opt out of analytics",
    # the levels page
    "levels.title": "What Caution, Warning and Danger mean",
    "levels.description": (
        "What each California toxic algae advisory level asks of people, "
        "children and pets, with the words on the state's sign."
    ),
    "levels.h1": "What the advisory levels mean",
    "levels.lede": (
        "California posts toxic algae advisories at lakes and rivers at three "
        "levels: Caution, Warning and Danger. Each level below gives the words "
        "on the state's sign and a plain summary. The sign posted at the water "
        "and the state's own guidance govern."
    ),
    "levels.sign_heading": "The state's sign",
    "levels.summary_heading": "In short",
    "levels.sign_source": "From the state's posted-sign wording, read {date}:",
    "levels.contact_heading": "After contact",
    "levels.human_advice": wording.HUMAN_ADVICE,
    "levels.dogs_heading": "Dogs",
    "levels.dog_advice": wording.DOG_ADVICE,
    "levels.end_heading": "When an advisory ends",
    "levels.end": (
        'A water page says "No all-clear recorded" until the state records an '
        "end to the advisory, however old the posting is. When the state's "
        "latest record recommends no advisory, that is what the state knew on "
        "that date."
    ),
    "levels.not_a_finding": wording.NOT_A_FINDING,
    "levels.links_advisories": "See every water with an advisory on file",
    "levels.links_county": "find a lake by county",
    "levels.links_dogs": "Dogs and algae",
    **{f"level.{tier}.name": name for tier, name in wording.TIER_LABEL.items()},
    "level.algal_mat.name": "Algal mat signs",
    "level.other_advisory.name": "Other signs",
    **{f"level.{tier}.guidance": wording.LEVEL_GUIDANCE[tier] for tier in TIERS},
    # The state's English sign wording, verbatim from wording.py's sources.
    "level.caution.sign": (
        '"Do not let pets and other animals go into or drink the water, or eat '
        'scum on the shore." "Keep children away from algae in the water and on '
        'the shore." "Do not drink the water or use it for cooking." '
        f"{_FISH_SIGN}"
    ),
    "level.warning.sign": (
        '"No swimming." "Do not let pets and other animals go into or drink the '
        'water, or eat scum on the shore." "Stay away from scum, and cloudy or '
        f'discolored water." {_NO_BOIL} {_FISH_SIGN}'
    ),
    "level.danger.sign": (
        '"Stay out of the water until further notice." "Do not let pets and '
        'other animals drink or go into the water, or go near the scum." "Do '
        f'not eat fish or shellfish from this water." {_NO_BOIL}'
    ),
    "level.algal_mat.sign": (
        '"Mats can be attached to the bottom, detached and floating, or washed '
        'up on shore." "Do NOT let children or adults touch, eat, or swallow '
        'any algal mats." "Do NOT let dogs eat algal mats or drink from the '
        'water." "Call your doctor or veterinarian if you or your pet get sick '
        'after contacting or ingesting algae."'
    ),
    # "Swimming at <water>" on an indexed water page (DECISIONS 0033)
    "swim.heading": wording.SWIM_HEADING,
    "swim.cannot_say": wording.SWIM_CANNOT_SAY,
    "swim.advisory": wording.SWIM_ADVISORY,
    **{f"swim.guidance.{key}": line for key, line in wording.SWIM_GUIDANCE.items()},
    "swim.generic": wording.SWIM_GENERIC,
    "swim.not_advisory": wording.SWIM_NOT_ADVISORY,
    "swim.unknown_level": wording.SWIM_UNKNOWN_LEVEL,
    "swim.unclassified": wording.SWIM_UNCLASSIFIED,
    "swim.check": wording.SWIM_CHECK,
    "swim.own_page": wording.SWIM_OWN_PAGE,
    "swim.covers": wording.SWIM_COVERS,
}

SIGN_URLS = {tier: SIGN_URL for tier in SIGNED_TIERS} | {"algal_mat": MAT_SIGN_URL}

_MONTHS_ES = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)


def es_date(day: dt.date | str | None) -> str:
    """``9 de octubre de 2026``, written from a month table so no locale or
    new dependency is needed. Like ``wording.date_label``, never called
    without a date."""
    if day is None:
        raise ValueError("a date label needs a date")
    if isinstance(day, str):
        day = dt.date.fromisoformat(day)
    return f"{day.day} de {_MONTHS_ES[day.month - 1]} de {day.year}"


DATE_LABEL = {"en": wording.date_label, "es": es_date}


def _locale_text(name: str) -> str:
    return resources.files("caalgae").joinpath(f"locales/{name}").read_text("utf-8")


def load_es() -> dict[str, str]:
    loaded: dict[str, str] = json.loads(_locale_text("es.json"))
    return loaded


def load_status() -> dict[str, dict[str, Any]]:
    loaded: dict[str, dict[str, Any]] = json.loads(_locale_text("es.status.json"))
    return loaded


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


_PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")


def placeholders(value: str) -> list[str]:
    return sorted(_PLACEHOLDER_RE.findall(value))


# -- the Spanish copy guard (plan section 4.5) ------------------------------

_ES_FORBIDDEN = re.compile(
    r"\b(?:segur[oa]s?|sin peligro|apt[oa]s? para nadar|limpi[oa]s?|"
    r"libre de toxinas)\b",
    re.I,
)
_PELIGRO = re.compile(r"\bpeligros[oa]s?\b|\bpeligro\b", re.I)


def spanish_safety_claims(text: str, level_labels: Iterable[str] = ()) -> list[str]:
    """Words the Spanish copy may never use about water: "seguro" and its
    forms, "sin peligro", "apta para nadar", "limpia", "libre de toxinas".
    "Peligro" is allowed only as the level's own label, so each label is
    removed before the check."""
    for label in sorted(set(level_labels), key=len, reverse=True):
        text = text.replace(label, " ")
    found = [m.group(0) for m in _ES_FORBIDDEN.finditer(text)]
    found += [m.group(0) for m in _PELIGRO.finditer(text)]
    return found


# -- the catalog gate ---------------------------------------------------------


@dataclass(frozen=True)
class Catalog:
    en: Mapping[str, str]
    es: Mapping[str, str]
    status: Mapping[str, Mapping[str, Any]]

    def level_labels(self) -> list[str]:
        return [
            self.es[f"level.{t}.name"] for t in TIERS if f"level.{t}.name" in self.es
        ]


def catalog() -> Catalog:
    return Catalog(en=EN, es=load_es(), status=load_status())


def _check_provenance(key: str, es: str, meta: Mapping[str, Any]) -> list[str]:
    """A ``state`` string's source and hash; a ``reviewed`` string's sign-off."""
    status = meta["status"]
    out = []
    if status == "state":
        out += [
            f"{key}: a state string needs {field}"
            for field in ("url", "read_on", "sha256")
            if not meta.get(field)
        ]
        if meta.get("sha256") and meta["sha256"] != sha256(es):
            out.append(f"{key}: text differs from the state quote it was pasted as")
    if status == "reviewed" and not (meta.get("reviewer") and meta.get("reviewed_on")):
        out.append(f"{key}: a reviewed string needs reviewer initials and a date")
    if PLACEHOLDER in es and status != "draft":
        out.append(f"{key}: still holds a paste placeholder but is marked {status}")
    return out


def _check_entry(key: str, en: str, es: str, meta: Mapping[str, Any]) -> list[str]:
    status = meta.get("status")
    if status not in STATUSES:
        return [f"{key}: status must be one of {', '.join(STATUSES)}, not {status!r}"]
    out = []
    if placeholders(en) != placeholders(es):
        out.append(f"{key}: placeholders differ from English ({placeholders(en)})")
    if es == en and status not in ("same", "draft"):
        out.append(f"{key}: Spanish is identical to English but marked {status}")
    if status == "same" and es != en:
        out.append(f"{key}: marked same but no longer matches English (stale)")
    if status == "same" and meta.get("safety"):
        out.append(f"{key}: a safety string cannot be marked same")
    return out + _check_provenance(key, es, meta)


def check_catalog(cat: Catalog, *, enabled: bool) -> list[str]:
    """Every problem with the catalog. Shape, parity, the equal-means-declared
    rule and state-quote hashes always apply; with ``enabled`` a draft safety
    string, any placeholder and the Spanish copy guard fail too."""
    problems = [f"{k}: missing from es.json" for k in sorted(set(cat.en) - set(cat.es))]
    problems += [
        f"{k}: in es.json, not in English" for k in sorted(set(cat.es) - set(cat.en))
    ]
    problems += [f"{k}: no status" for k in sorted(set(cat.es) - set(cat.status))]
    problems += [f"{k}: status for a key with no string" for k in sorted(set(cat.status) - set(cat.es))]  # fmt: skip
    for key in sorted(set(cat.en) & set(cat.es) & set(cat.status)):
        meta = cat.status[key]
        es = cat.es[key]
        problems += _check_entry(key, cat.en[key], es, meta)
        if not enabled:
            continue
        if meta.get("safety") and meta.get("status") == "draft":
            problems.append(f"{key}: safety string is still a draft")
        if PLACEHOLDER in es:
            problems.append(f"{key}: the state's wording has not been pasted in")
        if not key.startswith("level.") or not key.endswith(".name"):
            problems += [
                f"{key}: copy guard: {word!r}"
                for word in spanish_safety_claims(es, cat.level_labels())
            ]
    return problems


class GateError(RuntimeError):
    """The Spanish catalog or a built Spanish page failed the gate."""


def require(problems: list[str]) -> None:
    if problems:
        raise GateError("Spanish gate failed:\n" + "\n".join(problems))


# -- the rendered-page check (plan section 6.5) -------------------------------

_SCRIPT = re.compile(r"<script\b[^>]*>(.*?)</script>", re.S | re.I)
_STYLE = re.compile(r"<style\b.*?</style>", re.S | re.I)
_TITLE = re.compile(r"<title>(.*?)</title>", re.S)
_ATTR = re.compile(
    r'\b(?:alt|aria-label|title)="([^"]*)"|<meta name="description" content="([^"]*)"'
)
_TAG = re.compile(r"<[^>]+>")
_JS_STRING = re.compile(r'"([^"\\]{12,})"')
_URLISH = re.compile(r"\b(?:https?://\S+|[\w.-]+@[\w.-]+|[\w-]+\.(?:gov|com|org)\S*)")
_WORD = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+(?:'[a-z]+)?")
_LANG = re.compile(r'<html\b[^>]*\blang="([^"]*)"')

# Common English words that are not Spanish words. "no", "a", "es" and
# "con" are left out on purpose: they are Spanish too.
EN_STOPWORDS = frozenset(
    [
        "the",
        "and",
        "of",
        "to",
        "is",
        "are",
        "with",
        "for",
        "this",
        "that",
        "your",
        "you",
        "it",
        "from",
        "on",
        "or",
        "be",
        "at",
        "by",
        "not",
        "do",
        "does",
        "if",
        "was",
        "were",
        "has",
        "have",
        "water",
        "advisory",
        "advisories",
        "posted",
        "lake",
        "lakes",
        "river",
        "rivers",
        "sign",
        "signs",
        "dog",
        "dogs",
        "record",
        "records",
        "state's",
    ]
)
STOPWORD_SHARE = 0.03
ENGLISH_RUN = 4


def _visible_texts(page: str) -> list[str]:
    texts = [html.unescape(t) for t in _TITLE.findall(page)]
    for alt, desc in _ATTR.findall(page):
        texts.append(html.unescape(alt or desc))
    scripts = _SCRIPT.findall(page)
    # String literals a script can put on the page (GA4's opt-out messages).
    for body in scripts:
        texts += [s for s in _JS_STRING.findall(body) if " " in s]
    body = _SCRIPT.sub(" ", page)
    body = _STYLE.sub(" ", body)
    body = re.sub(r"<head\b.*?</head>", " ", body, flags=re.S)
    texts.append(html.unescape(_TAG.sub("\n", body)))
    return texts


# Words of the English catalog that are Spanish words too, so a Spanish
# sentence may use them. Fixed here, never read from es.json: an English
# sentence pasted into the Spanish catalog must not teach the check its words.
SHARED_WORDS = frozenset({"a", "no", "en", "federal", "control", "california"})


def english_vocabulary(cat: Catalog) -> frozenset[str]:
    """The words of the English catalog, its placeholders left out, plus the
    stopwords, less ``SHARED_WORDS``."""
    words = {
        w.casefold()
        for v in cat.en.values()
        for w in _WORD.findall(_PLACEHOLDER_RE.sub(" ", v))
    }
    return frozenset((words | EN_STOPWORDS) - SHARED_WORDS)


def english_leftovers(
    page: str, *, allow: Iterable[str], vocabulary: frozenset[str]
) -> list[str]:
    """English left on a Spanish page: any run of ``ENGLISH_RUN`` or more
    English words in a row, or an English stopword share above
    ``STOPWORD_SHARE``. ``allow`` (proper nouns from the snapshot and the
    catalog's ``same`` values) is removed first, longest first."""
    problems = []
    allowed = sorted({a for a in allow if a.strip()}, key=len, reverse=True)
    words_total = 0
    stop_total = 0
    for text in _visible_texts(page):
        for phrase in allowed:
            text = text.replace(phrase, "\n")
        text = _URLISH.sub("\n", text)
        for chunk in re.split(r"[\n.;:!?()\"“”«»]+", text):
            words = _WORD.findall(chunk)
            words_total += len(words)
            stop_total += sum(w.casefold() in EN_STOPWORDS for w in words)
            run: list[str] = []
            for word in [*words, ""]:
                if word and word.casefold() in vocabulary:
                    run.append(word)
                    continue
                if len(run) >= ENGLISH_RUN:
                    problems.append("English words: " + " ".join(run))
                run = []
    if words_total and stop_total / words_total > STOPWORD_SHARE:
        problems.append(
            f"English stopwords are {stop_total} of {words_total} words "
            f"(over {STOPWORD_SHARE:.0%})"
        )
    return problems


def snapshot_proper_nouns(snap: Mapping[str, Any]) -> set[str]:
    """Names that stay as the state wrote them: waters, counties, sites,
    agencies and programs, all read from the snapshot, never kept by hand."""
    names: set[str] = {"Lake Notice", "Poison Control", "CyAN", "Copernicus Sentinel-3"}
    for water in snap.get("waterbodies", []):
        names.add(str(water.get("name", "")))
        names.add(str(water.get("source_name", "")))
        names.update(str(c) for c in water.get("counties", []))
        for spot in water.get("sites", []):
            names.add(str(spot.get("name", "")))
    for source in snap.get("sources", []):
        names.add(str(source.get("agency", "")))
        names.add(str(source.get("program", "")))
    source_file = snap.get("source_file") or {}
    names.add(str(source_file.get("file_name", "")))
    return {n for n in names if n}


def check_rendered(root: Path, snap: Mapping[str, Any], cat: Catalog) -> list[str]:
    """Every /es/ page under ``root``: ``lang="es"``, no English left in its
    visible text, title, alt, aria-label, title attributes, description or
    script strings, and the Spanish copy guard. Every other page keeps
    ``lang="en"``."""
    allow = snapshot_proper_nouns(snap) | {
        cat.es[k]
        for k, m in cat.status.items()
        if m.get("status") == "same" and k in cat.es
    }
    vocabulary = english_vocabulary(cat)
    problems = []
    for page in sorted(root.rglob("*.html")):
        rel = page.relative_to(root).as_posix()
        text = page.read_text(encoding="utf-8")
        lang = _LANG.search(text)
        want = "es" if rel.startswith("es/") else "en"
        if not lang or lang.group(1) != want:
            problems.append(f"{rel}: lang is not {want!r}")
        if want != "es":
            continue
        problems += [
            f"{rel}: {p}"
            for p in english_leftovers(text, allow=allow, vocabulary=vocabulary)
        ]
        visible = " ".join(_visible_texts(text))
        problems += [
            f"{rel}: copy guard: {word!r}"
            for word in spanish_safety_claims(visible, cat.level_labels())
        ]
    return problems


def main(argv: list[str] | None = None) -> int:
    """``make i18n``: the catalog gate. ``--enabled`` checks as if Spanish
    were on, to show what turning it on needs; ``--hash KEY`` prints the
    SHA-256 of a Spanish string, for the ``sha256`` field after pasting the
    state's wording."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(prog="python -m caalgae.i18n")
    parser.add_argument("--enabled", action="store_true", help="check as if ES_ENABLED")
    parser.add_argument("--hash", metavar="KEY", help="print the SHA-256 of KEY")
    args = parser.parse_args(argv)
    cat = catalog()
    if args.hash:
        print(sha256(cat.es[args.hash]))
        return 0
    enabled = bool(args.enabled or ES_ENABLED)
    problems = check_catalog(cat, enabled=enabled)
    for problem in problems:
        print(problem, file=sys.stderr)
    counts = dict.fromkeys(STATUSES, 0)
    for meta in cat.status.values():
        counts[str(meta.get("status"))] = counts.get(str(meta.get("status")), 0) + 1
    drafts = sum(
        1 for m in cat.status.values() if m.get("safety") and m.get("status") == "draft"
    )
    by_status = ", ".join(f"{n} {s}" for s, n in counts.items())
    print(
        f"i18n: {len(cat.es)} Spanish strings ({by_status}); {drafts} safety "
        f"drafts; Spanish {'on' if enabled else 'off'}; {len(problems)} problems"
    )
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
