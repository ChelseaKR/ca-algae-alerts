"""Build the free static site from a validated snapshot.

One page per waterbody (its status, its sites, every record since 2016),
county pages, a page of every open advisory, a page for dog owners, an
about page that states the data's limits, privacy and support pages, a
sitemap, robots.txt and the snapshot itself at ``snapshot/v1.json``.

Every page is plain HTML with relative links, so the build works on any
host and from a local folder. Google Analytics 4 is added only when
``GA4_MEASUREMENT_ID`` is set, and never loads for a browser that sends
Global Privacy Control or Do Not Track (``_ga4.html.jinja``).
"""

from __future__ import annotations

import calendar
import datetime as dt
import json
import math
import re
import shutil
from collections import Counter, defaultdict
from collections.abc import Iterable
from importlib import resources
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlsplit

import jinja2

from caalgae import i18n, indexnow, levels, where_to_check, wording
from caalgae.normalize import CA_COUNTIES, TIER_RANK
from caalgae.snapshot import slugify
from caalgae.water_names import display_water

# The product name, the domain and the site's default base URL live here and
# nowhere else in code; tests/test_naming.py checks every other place that
# carries the name (the two Info.plist display names, README, the style sheet
# header, the listing draft) against SITE_NAME.
SITE_NAME = "Lake Notice"
SITE_DOMAIN = "lakenotice.com"
STATE_NAMES = {"CA": "California", "MO": "Missouri"}
STATE_SOURCE = {"CA": "ca-swrcb-fhab", "MO": "mo-dnr-hab"}
DEFAULT_BASE_URL = f"https://{SITE_DOMAIN}/"
# Sitemap staging (owner decision, 2026-10-23). A water page is listed in the
# sitemap and indexable only when the state recorded an advisory for it within
# this many months of the build's data date (``run_date``, never the wall
# clock). Every other water page is still built and linked, with
# ``noindex,follow`` and no canonical, and its body is identical. Most waters
# have one or two state records, so unstaged they are near-copies of each other
# (growth/lake-notice-page-audit-2026-10-23.md). To undo: set this to a number
# that reaches back past 2016, such as 1200, and every water is indexable
# again; the sitemap and the robots tags both follow this one value.
INDEX_WINDOW_MONTHS = 24
# A water outside that window is still indexable when the state has published
# at least this many records for it (DECISIONS 0016). The audit's thin pages
# were the ones with one or two records, 85 to 92% template; a page with five
# or more has its own history table. On the 2026-11-03 snapshot this adds 118
# waters (Salton Sea, Trinity Lake, Lake Merced, Lake Natoma and others) to
# the 308 the window keeps. To undo: set it to a number no water reaches,
# such as 100000.
INDEX_MIN_RECORDS = 5


# Search results show about 60 characters of a title and 155 of a
# description; longer ones are cut mid-phrase. Every page is held to both.
TITLE_MAX = 60
DESCRIPTION_MAX = 155


def fit(candidates: list[str], limit: int) -> str:
    """The first candidate within ``limit``; failing that, the last one cut at
    a word boundary with an ellipsis, so a very long name still fits."""
    for candidate in candidates:
        if len(candidate) <= limit:
            return candidate
    last = candidates[-1]
    return last[: limit - 1].rsplit(" ", 1)[0].rstrip(" ,:;|-") + "\u2026"


def water_title(
    name: str, county: str | None, status: dict[str, Any] | None = None
) -> str:
    """A waterbody page title of at most TITLE_MAX characters. ``county`` is
    passed only when another water in the same state has the same name, so two
    "Bear Creek" pages never share a title.

    A water with an advisory leads with its name, then the headline's level
    and its last posted date (``wording.title_status``), because that is what
    a search for "<water> algae" asks (DECISIONS 0018). "last posted" is
    dropped before the word "algae" or the date is. Any other status gets
    no status in the title: "recommends no advisory" needs its not-a-finding
    sentence next to it (0002), and a title has no room for one. A name too
    long for the status falls back to the plain title, never a cut date."""
    where = f"{name}, {county} County" if county else name
    short = f"{name}, {county}" if county else name
    tail = f" | {SITE_NAME}"
    plain = [
        f"{where} toxic algae advisories{tail}",
        f"{where} algae advisories{tail}",
        f"{short} algae advisories{tail}",
        f"{short}{tail}",
        f"{name}{tail}",
    ]
    if status and wording.title_status(status):
        posted = wording.title_status(status)
        dated = wording.title_status(status, short=True)
        candidates = [
            f"{where} toxic algae: {posted}",
            f"{where} algae: {posted}",
            f"{where} algae: {dated}",
            f"{where}: {dated}",
            f"{short}: {dated}",
        ]
        for candidate in candidates:
            if len(candidate) <= TITLE_MAX:
                return candidate
    return fit(plain, TITLE_MAX)


def water_description(
    name: str,
    place: str | None,
    headline: str,
    file_date: str | None = None,
    advisory: bool = True,
) -> str:
    """A waterbody page description of at most DESCRIPTION_MAX characters.
    The status and its date come first and are never the part that is cut.

    A status that is not an advisory carries the same not-a-finding sentence
    as the page's first line (0002), in every candidate: a search snippet is
    quoted on its own. The date of the state's file follows when it fits
    (0018); without one, nothing is put in its place."""
    # A place the name already carries ("Lake Havasu (Arizona)") is not repeated.
    if place and f"({place})" in name:
        place = None
    lead = f"{name}, {place}: " if place else f"{name}: "
    answer = headline if advisory else f"{headline} {wording.NOT_A_FINDING}"
    dated = (
        [f"From the state's data dated {wording.date_label(file_date)}."]
        if file_date
        else []
    )
    extras = [
        " ".join(["", *dated, "Every state advisory record since 2016."]),
        " ".join(["", *dated, "State records since 2016."]),
        " ".join(["", *dated]),
        " Every state advisory record since 2016.",
        "",
    ]
    return fit(
        [*(f"{lead}{answer}{extra}" for extra in extras), f"{name}: {answer}", answer],
        DESCRIPTION_MAX,
    )


def _waters(count: int) -> str:
    return f"{count} water" if count == 1 else f"{count} waters"


def county_title(county: str, with_advisory: int, total: int) -> str:
    """A county page title of at most TITLE_MAX characters.

    A county where some water's latest record is an advisory says how many,
    out of the waters on record, because a county search ("<county> county
    lake algae") is asking whether anything is posted there. It is the same
    count as the county index's "Latest record is an advisory" column and the
    page's first line. A county with none keeps the plain title: "0 of 2
    waters" in a title, without the not-a-finding sentence beside it, would
    read as an all-clear (DECISIONS 0002)."""
    tail = f" | {SITE_NAME}"
    plain = [
        f"{county} County lake toxic algae advisories{tail}",
        f"{county} County algae advisories{tail}",
    ]
    if with_advisory > 0:
        share = f"{with_advisory} of {_waters(total)}"
        for candidate in (
            f"{county} County lake algae advisories: {share}",
            f"{county} County algae advisories: {share}",
        ):
            if len(candidate) <= TITLE_MAX:
                return candidate
    return fit(plain, TITLE_MAX)


def county_count_line(
    county: str, with_advisory: int, total: int, file_date: str | None
) -> str:
    """The county page's count sentence, which its description also leads
    with. Nothing is said about a county with no advisory on record beyond
    the table itself."""
    if with_advisory <= 0:
        return ""
    lead = (
        f"{with_advisory} of the {_waters(total)} in {county} County "
        + (
            "has an advisory as its"
            if with_advisory == 1
            else "have an advisory as their"
        )
        + " latest state record"
        if total != 1
        else f"The one water in {county} County has an advisory as its latest "
        "state record"
    )
    when = (
        f", in the state's data dated {wording.date_label(file_date)}"
        if file_date
        else ""
    )
    return f"{lead}{when}."


def county_description(
    county: str, with_advisory: int, total: int, file_date: str | None
) -> str:
    """A county page description of at most DESCRIPTION_MAX characters."""
    plain = (
        f"Toxic algae advisory status and history for {total} "
        f"lakes and rivers in {county} County, California."
    )
    line = county_count_line(county, with_advisory, total, file_date)
    if not line:
        return plain
    return fit(
        [
            f"{line} An advisory stays listed until the state records an end.",
            line,
            plain,
        ],
        DESCRIPTION_MAX,
    )


def advisories_description(waters: list[dict[str, Any]]) -> str:
    """The advisory list's description: how many waters it lists, by state,
    the same waters the page's table lists. Missouri waters are on the page,
    so the description names them rather than calling the list California's."""
    counts = Counter(w["state"] for w in waters)
    parts = [
        f"{counts[state]} {name}"
        for state, name in STATE_NAMES.items()
        if counts[state]
    ]
    if not parts:
        return (
            "Lakes and rivers whose latest state record is a toxic algae "
            "advisory, with its level and date."
        )
    lead = " and ".join(parts)
    return fit(
        [
            f"{lead} lakes and rivers whose latest state record is a toxic algae "
            "advisory, with its level and date, including old ones with no "
            "recorded end.",
            f"{lead} lakes and rivers whose latest state record is a toxic algae "
            "advisory, with its level and date.",
        ],
        DESCRIPTION_MAX,
    )


def state_list(states: Iterable[str]) -> str:
    """State codes as names in STATE_NAMES order: "California",
    "California and Missouri", "California, Missouri and ..."."""
    present = set(states)
    names = [name for code, name in STATE_NAMES.items() if code in present]
    if len(names) <= 1:
        return "".join(names)
    return f"{', '.join(names[:-1])} and {names[-1]}"


def home_title(states: Iterable[str]) -> str:
    """The home page title, naming every state whose data is live in this
    build (DECISIONS 0032). California alone keeps the title it has had
    since launch; a state is named only while its waters are in the
    snapshot, so an empty or dropped Missouri source drops the name too."""
    where = state_list(states) or "California"
    return fit(
        [
            f"{where} lake toxic algae advisories by date | {SITE_NAME}",
            f"{where} toxic algae advisories by date",
            f"{where} algae advisories by date",
        ],
        TITLE_MAX,
    )


def home_description(states: Iterable[str]) -> str:
    """The home page description, naming the same states as its title.
    "Since 2016" is California's span only, so a build with another state
    says "history" without a year."""
    where = state_list(states) or "California"
    span = " since 2016" if where == "California" else ""
    return fit(
        [
            f"Toxic algae (harmful algal bloom) advisories at {where} lakes "
            f"and rivers, newest first, with each lake's history{span} for "
            "swimmers and dogs.",
            f"Toxic algae advisories at {where} lakes and rivers, newest "
            f"first, with each lake's history{span}.",
        ],
        DESCRIPTION_MAX,
    )


def advisories_title(waters: list[dict[str, Any]]) -> str:
    """The advisory list's title, naming the states its table lists, the
    same states its description counts (DECISIONS 0032)."""
    where = state_list(w["state"] for w in waters) or "California"
    return fit(
        [
            f"All {where} toxic algae advisories on file | {SITE_NAME}",
            f"All {where} toxic algae advisories on file",
            f"{where} toxic algae advisories on file",
        ],
        TITLE_MAX,
    )


# Lake Notice's own GA4 web stream (property 561648146, "Lake Notice", created
# 2026-10-31 in the ChelseaKR account; DECISIONS 0007). Set, every page carries
# the tag and the privacy page describes it; empty, no page loads any script
# and the privacy page says nothing is collected. Never copy another
# product's id here: it would mix this site's visits into that property
# (tests/test_site.py checks this one against the portfolio's other ids).
GA4_MEASUREMENT_ID = "G-75YLGQKDHG"
# Amazon Associates dog-gear links (docs/DECISIONS.md 0013, narrowed by 0029).
# Website only, and only on the Dogs and algae page (/dogs/): never on a lake,
# county, state or any other page, and never in the iOS app, which has no web
# view. The one config value is the tracking id below: Lake Notice's own
# Associates id, lakenotice-20, never Trout Truck's. Empty, the gear block and
# the privacy paragraph render nothing and no Amazon URL is built anywhere.
# Never a home toxin test kit: a negative strip is not safety, and nothing here
# may imply that gear makes algae exposure any less of a risk
# (tests/test_site_affiliate.py fails on test-kit or safety wording in the
# categories or in a built page).
AMAZON_ASSOCIATE_TAG = "lakenotice-20"
AMAZON_SEARCH_URL = "https://www.amazon.com/s"
# Amazon's required wording, byte for byte: do not paraphrase it.
AMAZON_ASSOCIATE_DISCLOSURE = "As an Amazon Associate I earn from qualifying purchases."
AFFILIATE_LINK_REL = "sponsored nofollow noopener"
# Label, the search terms, then the line tying the item to the dogs page's own
# advice (DOG_ADVICE and "At the water"). Generic searches, not products, so
# nothing goes stale and the page states no price, rating or "best" claim.
GEAR_CATEGORIES: tuple[tuple[str, str, str], ...] = (
    ("Portable dog water bottle", "portable dog water bottle",
     "Bring fresh drinking water so your dog does not drink from the lake."),
    ("Collapsible dog water bowl", "collapsible dog water bowl",
     "Something to pour that fresh water into, away from the shore."),
    ("Long dog leash", "long dog leash",
     "Keep your dog out of the water and away from scum on the shore where "
     "an advisory is on file or the water looks green, blue-green or scummy."),
    ("Portable dog rinse bottle", "portable dog rinse shower bottle",
     "If your dog does go in, rinse it off with fresh water you brought."),
    ("Dog drying towel", "dog drying towel",
     "Dry its coat after the rinse, and do not let it lick its coat."),
)  # fmt: skip
# How each state's agency is named in the non-endorsement sentence.
AGENCY_GEAR_NAME = {"CA": "the Water Board", "MO": "Missouri DNR"}


def amazon_search_url(terms: str) -> str:
    """An Amazon search URL for ``terms`` carrying the associate tag."""
    return f"{AMAZON_SEARCH_URL}?{urlencode({'k': terms, 'tag': AMAZON_ASSOCIATE_TAG})}"


def gear_links() -> list[dict[str, str]]:
    """The gear block's links; none at all while the tag is empty."""
    if not AMAZON_ASSOCIATE_TAG:
        return []
    return [
        {"label": label, "url": amazon_search_url(terms), "why": why}
        for label, terms, why in GEAR_CATEGORIES
    ]


def gear_endorsement(state: str | None = None) -> str:
    """The sentence that keeps a commercial link from implying that the agency
    whose data the page shows endorses it. With no state, it names both."""
    if state is None:
        return (
            f"The links are {SITE_NAME}'s, not the Water Board's or Missouri "
            "DNR's, and neither agency endorses them or Amazon."
        )
    agency = AGENCY_GEAR_NAME[state]
    return (
        f"The links are {SITE_NAME}'s, not {agency}'s, and {agency} does not "
        "endorse them or Amazon."
    )


GA4_DENIED_REGIONS = [
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR",
    "HU", "IS", "IE", "IT", "LV", "LI", "LT", "LU", "MT", "NL", "NO", "PL",
    "PT", "RO", "SK", "SI", "ES", "SE", "GB", "CH",
]  # fmt: skip


def _env() -> jinja2.Environment:
    env = jinja2.Environment(
        loader=jinja2.PackageLoader("caalgae", "templates"),
        autoescape=jinja2.select_autoescape(["html", "jinja", "xml"]),
        undefined=jinja2.StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["date"] = wording.date_label
    env.globals.update(
        headline=wording.headline,
        caveat=wording.caveat,
        level_name=wording.level_name,
        newer_posting=wording.newer_posting,
        older_higher=wording.older_higher,
        dog_answer=wording.dog_answer,
        list_row=wording.list_row,
        list_caveat=wording.LIST_CAVEAT,
        guidance=wording.LEVEL_GUIDANCE,
        guidance_for=wording.guidance_for,
        cells_label=wording.cells_label,
        satellite_explainer=wording.SATELLITE_EXPLAINER,
        dog_advice=wording.DOG_ADVICE,
        human_advice=wording.HUMAN_ADVICE,
        not_medical_advice=wording.NOT_MEDICAL_ADVICE,
    )
    return env


def _advisory_sort(water: dict[str, Any]) -> tuple[str, int, str]:
    s = water["status"]
    newest = wording.newest_posted(water) or ""
    return (newest, TIER_RANK.get(s["tier"] or "", 0), water["name"])


def months_before(day: dt.date, months: int) -> dt.date:
    """``day`` minus ``months`` calendar months, the day clamped to the month."""
    index = day.year * 12 + (day.month - 1) - months
    year, month = divmod(index, 12)
    last = calendar.monthrange(year, month + 1)[1]
    return dt.date(year, month + 1, min(day.day, last))


def is_indexable(
    water: dict[str, Any],
    run_date: dt.date,
    months: int,
    min_records: int | None = None,
) -> bool:
    """True when the state's last advisory for this water falls within
    ``months`` months before ``run_date``, or when the state has published at
    least ``min_records`` records for it (INDEX_MIN_RECORDS by default)."""
    floor = INDEX_MIN_RECORDS if min_records is None else min_records
    if len(water.get("records", [])) >= floor:
        return True
    last = water["status"].get("last_advisory")
    if not last:
        return False
    return dt.date.fromisoformat(last) >= months_before(run_date, months)


def water_lastmod(water: dict[str, Any]) -> dt.date | None:
    """The newest date this water's page shows: its records (the history
    table), its status's last-posted date and its last advisory. None when the
    water has no dated record. Never the wall clock or the build date."""
    days = [r["date"] for r in water["records"]]
    for key in ("posted", "last_advisory"):
        if water["status"].get(key):
            days.append(water["status"][key])
    return max(map(dt.date.fromisoformat, days), default=None)


# Matching names nearby. The state's file sometimes lists one water as two or
# more entries: under two counties (Lake Tulloch), with a stray suffix ("Big
# bear lake ca") or with the words swapped ("Lake Crowley"). Identity stays
# as DECISIONS 0009 defines it; a water page only links to entries whose names
# match its own and whose centers lie within this distance, with each entry's
# own status, so a visitor who lands on one entry sees the others. Names that
# start "Unnamed" never match. On the 2026-10-29 snapshot this puts the
# section on 56 water pages (Big Bear Lake, Lake Tulloch, Crowley Lake, Clear
# Lake, Lake Havasu and others); the page says "may be the same water", never
# that it is.
SAME_NAME_NEARBY_MILES = 6
_NAME_WORD = re.compile(r"[a-z0-9]+")
_STATE_SUFFIXES = {"ca", "california", "mo", "missouri"}
_EARTH_RADIUS_MILES = 3958.8


def name_key(name: str) -> tuple[str, ...]:
    """A water's name as a sorted tuple of words, without a trailing state
    word, so "Lake Crowley" matches "Crowley Lake" and "Big bear lake ca"
    matches "Big Bear Lake". Empty for a name that cannot be matched."""
    words = _NAME_WORD.findall(name.casefold())
    while words and words[-1] in _STATE_SUFFIXES:
        words.pop()
    if not words or words[0] == "unnamed":
        return ()
    return tuple(sorted(words))


def miles_between(a: dict[str, float], b: dict[str, float]) -> float:
    """Great-circle distance between two ``{"lat", "lon"}`` points, in miles."""
    lat1, lon1, lat2, lon2 = map(math.radians, (a["lat"], a["lon"], b["lat"], b["lon"]))
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * _EARTH_RADIUS_MILES * math.asin(math.sqrt(h))


def same_name_nearby(waters: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """For each water id, the other waters in the same state whose names match
    (``name_key``) and whose centers are within SAME_NAME_NEARBY_MILES. A water
    with no center is never matched."""
    groups: dict[tuple[str, tuple[str, ...]], list[dict[str, Any]]] = defaultdict(list)
    for water in waters:
        key = name_key(water["name"])
        if key and water.get("center"):
            groups[(water["state"], key)].append(water)
    nearby: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for group in groups.values():
        for i, a in enumerate(group):
            for b in group[i + 1 :]:
                if miles_between(a["center"], b["center"]) <= SAME_NAME_NEARBY_MILES:
                    nearby[a["id"]].append(b)
                    nearby[b["id"]].append(a)
    return {
        wid: sorted(others, key=lambda w: (w["name"].casefold(), w["id"]))
        for wid, others in nearby.items()
    }


# Trout Truck links (DECISIONS 0026). A CA water page links to the same water's
# page on Trout Truck, Chelsea's other free site, only when a reviewed pair in
# pipeline/data/trout_truck_pairs.json names it; there is no fuzzy match at
# build time, and no footer or sitewide link. The page links Trout Truck's page
# and nothing else: no planting week, date or count is copied here, because
# those go stale on Trout Truck's schedule, not this one. A pair is dropped
# when its Lake Notice id is gone from the snapshot or its Trout Truck path is
# gone from trout_truck_pages.json (read from Trout Truck's committed
# snapshot by scripts/trout_truck_pages.py), so the site never links a dead
# page. Plain links: no tag, no tracking parameter, no rel="sponsored"
# (nothing is paid); GA4's enhanced measurement already counts outbound clicks.
TROUT_TRUCK_URL = "https://trouttruck.com"
_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
TROUT_TRUCK_PAIRS_FILE = _DATA_DIR / "trout_truck_pairs.json"
TROUT_TRUCK_PAGES_FILE = _DATA_DIR / "trout_truck_pages.json"
TROUT_TRUCK_KINDS = frozenset({"lake", "stream"})
_TT_PATH = re.compile(r"/water/[a-z0-9]+(?:-[a-z0-9]+)*/")


def trout_truck_links(
    pairs: list[dict[str, Any]],
    tt_paths: Iterable[str],
    water_ids: Iterable[str],
) -> dict[str, dict[str, str]]:
    """Each Lake Notice water id with a live pair, mapped to its Trout Truck
    page (``url``, ``name``, ``kind``). A row whose Lake Notice id or Trout
    Truck path is gone is dropped; a malformed row or a water paired twice is
    an error, because the file is hand-reviewed and a typo must not ship."""
    live_tt = set(tt_paths)
    live_ln = set(water_ids)
    links: dict[str, dict[str, str]] = {}
    for row in pairs:
        ln_id, path, name, kind = (
            row["ln_id"],
            row["tt_path"],
            row["tt_name"],
            row["kind"],
        )
        if kind not in TROUT_TRUCK_KINDS or not _TT_PATH.fullmatch(path) or not name:
            raise ValueError(f"trout_truck_pairs.json: bad row {row!r}")
        if ln_id in links:
            raise ValueError(f"trout_truck_pairs.json: {ln_id} is paired twice")
        if ln_id in live_ln and path in live_tt:
            links[ln_id] = {"url": TROUT_TRUCK_URL + path, "name": name, "kind": kind}
    return links


def load_trout_truck_links(water_ids: Iterable[str]) -> dict[str, dict[str, str]]:
    pairs = json.loads(TROUT_TRUCK_PAIRS_FILE.read_text("utf-8"))["pairs"]
    pages = json.loads(TROUT_TRUCK_PAGES_FILE.read_text("utf-8"))["paths"]
    return trout_truck_links(pairs, pages, water_ids)


def newest(days: Iterable[dt.date | None]) -> dt.date | None:
    present = [d for d in days if d is not None]
    return max(present) if present else None


class SiteBuilder:
    def __init__(
        self,
        snap: dict[str, Any],
        out: Path,
        *,
        base_url: str,
        support_email: str,
        app_store_url: str,
        ga4_measurement_id: str,
    ) -> None:
        self.snap = snap
        self.out = out
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/") + "/"
        self.env = _env()
        self.run_date = dt.date.fromisoformat(snap["run_date"])
        self.urls: list[str] = []
        self.lastmods: dict[str, str] = {}
        self.sources = {s["id"]: s for s in snap["sources"]}
        source = self.sources["ca-swrcb-fhab"]
        self.common: dict[str, Any] = {
            "site_name": SITE_NAME,
            "support_email": support_email,
            "app_store_url": app_store_url,
            "ga4_measurement_id": ga4_measurement_id,
            "ga4_denied_regions": GA4_DENIED_REGIONS,
            "affiliate_enabled": bool(AMAZON_ASSOCIATE_TAG),
            "amazon_disclosure": AMAZON_ASSOCIATE_DISCLOSURE,
            "gear_endorsement_all": gear_endorsement(),
            "source": source,
            "source_file": snap["source_file"],
            "source_files": snap["source_files"],
            "all_sources": snap["sources"],
            "state_names": STATE_NAMES,
            "run_date": self.run_date,
            "quarantine": snap["quarantine"],
        }
        self.waters = [display_water(w) for w in snap["waterbodies"]]
        # Titles add the county when the source's name is shared (0009), so a
        # display name (0009, "Display names") never adds or drops one.
        self._name_counts = Counter(
            (w["state"], w["source_name"].casefold()) for w in self.waters
        )
        self._same_name_nearby = same_name_nearby(self.waters)
        self._trout_truck = load_trout_truck_links(w["id"] for w in self.waters)
        self.common["states_present"] = sorted({w["state"] for w in self.waters})
        # States whose data is live in this build: waters in the snapshot and
        # the state's source listed, the same test state_pages uses.
        self.live_states = [
            state
            for state in STATE_NAMES
            if state in self.common["states_present"]
            and STATE_SOURCE[state] in self.sources
        ]
        self.by_county: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.no_county: list[dict[str, Any]] = []
        for water in self.waters:
            for county in water["counties"]:
                self.by_county[county].append(water)
            if not water["counties"]:
                self.no_county.append(water)
        # A date after the snapshot's run_date cannot be real: that water gets
        # no lastmod and does not move its county, state or the site-wide date.
        self.water_dates: dict[str, dt.date] = {}
        for water in self.waters:
            day = water_lastmod(water)
            if day is not None and day <= self.run_date:
                self.water_dates[water["id"]] = day
        self.site_date = newest(self.water_dates.values())

    # -- helpers --------------------------------------------------------

    def _write(self, rel: str, template: str, **context: Any) -> None:
        """Write ``rel`` (a directory path ending in / or a file name)."""
        is_page = rel == "" or rel.endswith("/")
        path = self.out / (rel + "index.html" if is_page else rel)
        # A 404 page is served at whatever path was asked for, so its links
        # are absolute; every other page links relatively.
        root = "../" * rel.count("/") or "./"
        if rel == "404.html":
            root = self.base_url
        canonical = None if context.get("noindex") else self.base_url + rel
        lastmod: dt.date | None = context.pop("lastmod", None)
        html = self.env.get_template(template).render(
            **self.common,
            root=root or "./",
            canonical_url=canonical,
            breadcrumb=context.pop("breadcrumb", None),
            structured_data=context.pop("structured_data", None),
            noindex=context.pop("noindex", False),
            robots=context.pop("robots", "noindex"),
            **context,
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")
        if canonical:
            self.urls.append(canonical)
            if lastmod is not None and lastmod <= self.run_date:
                self.lastmods[canonical] = lastmod.isoformat()

    def _newest_of(self, waters: Iterable[dict[str, Any]]) -> dt.date | None:
        return newest(self.water_dates.get(w["id"]) for w in waters)

    def _crumbs(self, *trail: tuple[str, str]) -> list[tuple[str, str]]:
        return [("Home", self.base_url), *trail]

    def _breadcrumb_data(self, crumbs: list[tuple[str, str]]) -> dict[str, Any]:
        return {
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": i, "name": name, "item": url}
                for i, (name, url) in enumerate(crumbs, start=1)
            ],
        }

    # -- pages ----------------------------------------------------------

    def open_advisories(self) -> list[dict[str, Any]]:
        open_ = [w for w in self.waters if w["status"]["kind"] == "advisory"]
        return sorted(open_, key=_advisory_sort, reverse=True)

    def home(self) -> None:
        open_ = self.open_advisories()
        recent = [w for w in open_ if wording.is_recent_water(w, self.run_date)]
        self._write(
            "",
            "index.html.jinja",
            title=home_title(self.live_states),
            description=home_description(self.live_states),
            lastmod=self.site_date,
            recent=recent,
            older_count=len(open_) - len(recent),
            water_count=len(self.waters),
            recent_days=wording.RECENT_DAYS,
            structured_data={
                "@context": "https://schema.org",
                "@type": "WebSite",
                "name": SITE_NAME,
                "url": self.base_url,
            },
        )

    def advisories(self) -> None:
        crumbs = self._crumbs(("Every open advisory", self.base_url + "advisories/"))
        waters = self.open_advisories()
        self._write(
            "advisories/",
            "advisories.html.jinja",
            title=advisories_title(waters),
            description=advisories_description(waters),
            lastmod=self.site_date,
            waters=waters,
            breadcrumb=crumbs,
            structured_data={
                "@context": "https://schema.org",
                **self._breadcrumb_data(crumbs),
            },
        )

    def _name_is_shared(self, water: dict[str, Any]) -> bool:
        """True when another water in the same state has this source name."""
        key = (water["state"], water["source_name"].casefold())
        return self._name_counts[key] > 1

    @staticmethod
    def _county_label(water: dict[str, Any]) -> str | None:
        """The county to name in a title, or None when there is none."""
        if water["counties"]:
            return " and ".join(water["counties"])
        return None

    @staticmethod
    def _place(water: dict[str, Any]) -> str:
        """Where a water is, as its page's lede says it."""
        if water["counties"]:
            return f"{' and '.join(water['counties'])} County"
        # Missouri's layer names no county; California's rows sometimes omit it.
        return str(
            water["county_text"]
            or (
                "County not recorded"
                if water["state"] == "CA"
                else STATE_NAMES[water["state"]]
            )
        )

    def _file_date(self, state: str) -> str | None:
        """The date of the state's data file, or None when it has none."""
        return next(
            (
                f.get("file_date")
                for f in self.snap["source_files"]
                if f["source"] == STATE_SOURCE[state]
            ),
            None,
        )

    def water_page(self, water: dict[str, Any]) -> None:
        rel = f"water/{water['id']}/"
        trail = [(water["name"], self.base_url + rel)]
        if water["counties"]:
            first = water["counties"][0]
            trail.insert(
                0, (f"{first} County", self.base_url + f"county/{slugify(first)}/")
            )
        crumbs = self._crumbs(*trail)
        sites = {s["id"]: s for s in water["sites"]}
        county = self._place(water)
        about: dict[str, Any] = {"@type": "BodyOfWater", "name": water["name"]}
        if water["center"]:
            about["geo"] = {
                "@type": "GeoCoordinates",
                "latitude": water["center"]["lat"],
                "longitude": water["center"]["lon"],
            }
        water_source = self.sources[STATE_SOURCE[water["state"]]]
        indexable = is_indexable(water, self.run_date, INDEX_WINDOW_MONTHS)
        file_date = self._file_date(water["state"])
        satellite_source = self.sources.get("epa-cyan")
        self._write(
            rel,
            "water.html.jinja",
            title=water_title(
                water["name"],
                self._county_label(water) if self._name_is_shared(water) else None,
                water["status"],
            ),
            description=water_description(
                water["name"],
                None if county == "County not recorded" else county,
                wording.headline(water["status"]),
                file_date,
                advisory=water["status"]["kind"] == "advisory",
            ),
            noindex=not indexable,
            robots="noindex,follow",
            lastmod=self.water_dates.get(water["id"]),
            water=water,
            water_source=water_source,
            satellite_source=satellite_source,
            county=county,
            summary=wording.summary(water["name"], county, water["status"], file_date),
            status_notes=[
                note
                for note in (
                    wording.newer_posting(water),
                    wording.older_higher(water),
                    wording.age_note(water, file_date),
                )
                if note
            ],
            sites=sites,
            county_links=[(c, slugify(c)) for c in water["counties"]],
            same_name_nearby=[
                {
                    "id": other["id"],
                    "name": other["name"],
                    "place": self._place(other),
                    "headline": wording.headline(other["status"]),
                }
                for other in self._same_name_nearby.get(water["id"], [])
            ],
            same_name_miles=SAME_NAME_NEARBY_MILES,
            trout_truck=self._trout_truck.get(water["id"]),
            breadcrumb=crumbs,
            structured_data={
                "@context": "https://schema.org",
                "@graph": [
                    self._breadcrumb_data(crumbs),
                    {
                        "@type": "WebPage",
                        "name": f"{water['name']} toxic algae advisories",
                        "url": self.base_url + rel,
                        "about": about,
                        "isBasedOn": water_source["dataset_url"],
                    },
                ],
            },
        )

    def counties(self) -> None:
        crumbs = self._crumbs(("By county", self.base_url + "county/"))
        rows = [
            (c, slugify(c), len(self.by_county[c]),
             sum(w["status"]["kind"] == "advisory" for w in self.by_county[c]))
            for c in sorted(self.by_county)
        ]  # fmt: skip
        self._write(
            "county/",
            "counties.html.jinja",
            title=f"California algae advisories by county | {SITE_NAME}",
            description="Lakes and rivers with California toxic algae advisory records, by county.",
            rows=rows,
            lastmod=self._newest_of(w for ws in self.by_county.values() for w in ws),
            no_county=self.no_county,
            breadcrumb=crumbs,
            structured_data={
                "@context": "https://schema.org",
                **self._breadcrumb_data(crumbs),
            },
        )
        # County pages are California's: Missouri's layer names no county.
        ca_file_date = self._file_date("CA")
        for county, waters in self.by_county.items():
            rel = f"county/{slugify(county)}/"
            crumbs_c = [*crumbs, (f"{county} County", self.base_url + rel)]
            ordered = sorted(waters, key=wording.list_sort_key)
            with_advisory = sum(w["status"]["kind"] == "advisory" for w in waters)
            self._write(
                rel,
                "county.html.jinja",
                title=county_title(county, with_advisory, len(waters)),
                description=county_description(
                    county, with_advisory, len(waters), ca_file_date
                ),
                count_line=county_count_line(
                    county, with_advisory, len(waters), ca_file_date
                ),
                county=county,
                file_date=ca_file_date,
                lastmod=self._newest_of(waters),
                waters=ordered,
                breadcrumb=crumbs_c,
                structured_data={
                    "@context": "https://schema.org",
                    **self._breadcrumb_data(crumbs_c),
                },
            )

    def state_pages(self) -> None:
        for state, name in STATE_NAMES.items():
            waters = [w for w in self.waters if w["state"] == state]
            if not waters or STATE_SOURCE[state] not in self.sources:
                continue
            rel = f"state/{state.lower()}/"
            crumbs = self._crumbs((name, self.base_url + rel))
            ordered = sorted(waters, key=wording.list_sort_key)
            self._write(
                rel,
                "state.html.jinja",
                title=f"{name} lake algae advisories | {SITE_NAME}",
                description=(
                    f"Toxic algae advisory status and history for {len(waters)} "
                    f"lakes and rivers in {name}, from the state's own records."
                ),
                state=state,
                file_date=self._file_date(state),
                lastmod=self._newest_of(waters),
                state_name=name,
                waters=ordered,
                state_source=self.sources[STATE_SOURCE[state]],
                breadcrumb=crumbs,
                structured_data={
                    "@context": "https://schema.org",
                    **self._breadcrumb_data(crumbs),
                },
            )

    def static_pages(self) -> None:
        pages = [
            ("dogs/", "dogs.html.jinja", "Is this lake safe for my dog? Algae advisories",
             "How to read California algae advisories before a lake trip with your dog: what each level means, why no advisory is not an all-clear, and signs to watch."),
            ("about/", "about.html.jinja", "About the data and its limits",
             "Where the advisories come from, how a status is decided, and what the data cannot tell you."),
            ("privacy/", "privacy.html.jinja", "Privacy policy",
             "What the website and the iPhone app collect."),
            ("support/", "support.html.jinja", "Support",
             "Help with the website and the iPhone app."),
            ("terms/", "terms.html.jinja", "Terms of use",
             "Who runs Lake Notice, what it is and is not, and why it is never a determination about a water."),
        ]  # fmt: skip
        for rel, template, title, description in pages:
            name = title.split("?")[0] if rel == "dogs/" else title
            crumbs = self._crumbs(
                (name if rel != "dogs/" else "Dogs and algae", self.base_url + rel)
            )
            self._write(
                rel,
                template,
                title=f"{title} | {SITE_NAME}",
                description=description,
                breadcrumb=crumbs,
                structured_data={
                    "@context": "https://schema.org",
                    **self._breadcrumb_data(crumbs),
                },
                # Only the dogs page shows record data; about, privacy,
                # support and terms have no content date in the repo, so no lastmod.
                lastmod=self.site_date if rel == "dogs/" else None,
                counties_known=len(CA_COUNTIES),
                tiers=["caution", "warning", "danger", "other_advisory"],
                # The gear block is on the dogs page and nowhere else
                # (DECISIONS 0029); every other page gets no links.
                gear_links=gear_links() if rel == "dogs/" else [],
                affiliate_rel=AFFILIATE_LINK_REL,
                gear_endorsement=gear_endorsement(),
            )
        self._write("404.html", "404.html.jinja", title=f"Page not found | {SITE_NAME}",
                    description="Page not found.", noindex=True)  # fmt: skip

    def where_to_check_page(self) -> None:
        """The dated "where to check" page. Its lastmod is the page's own data
        date (the newest read date in ``where_to_check.SOURCES``), set directly:
        it is a fixed fact about the page, not a record date, so the run-date
        ceiling that guards record dates does not apply."""
        rel = "where-to-check/"
        crumbs = self._crumbs((where_to_check.TITLE, self.base_url + rel))
        self._write(
            rel,
            "where_to_check.html.jinja",
            title=f"{where_to_check.TITLE} | {SITE_NAME}",
            description=where_to_check.DESCRIPTION,
            page_title=where_to_check.TITLE,
            sources=[
                {**vars(src), "slug": slugify(src.name)}
                for src in where_to_check.SOURCES
            ],
            county_counts=where_to_check.COUNTY_COUNTS,
            unread=where_to_check.UNREAD_COUNTIES,
            as_of=where_to_check.AS_OF,
            breadcrumb=crumbs,
            structured_data={
                "@context": "https://schema.org",
                **self._breadcrumb_data(crumbs),
            },
        )
        self.lastmods[self.base_url + rel] = where_to_check.AS_OF.isoformat()

    def extras(self) -> None:
        assets = self.out / "assets"
        assets.mkdir(parents=True, exist_ok=True)
        css = (
            resources.files("caalgae")
            .joinpath("templates/style.css")
            .read_text("utf-8")
        )
        (assets / "style.css").write_text(css, encoding="utf-8")
        snap_dir = self.out / "snapshot"
        snap_dir.mkdir(parents=True, exist_ok=True)
        (snap_dir / "v1.json").write_text(
            json.dumps(self.snap, separators=(",", ":"), ensure_ascii=False),
            encoding="utf-8",
        )
        sitemap = self.env.get_template("sitemap.xml.jinja").render(
            entries=[(u, self.lastmods.get(u)) for u in sorted(self.urls)]
        )
        (self.out / "sitemap.xml").write_text(sitemap, encoding="utf-8")
        (self.out / "robots.txt").write_text(
            f"User-agent: *\nAllow: /\nSitemap: {self.base_url}sitemap.xml\n",
            encoding="utf-8",
        )
        (self.out / ".nojekyll").write_text("", encoding="utf-8")
        # The IndexNow ownership file (indexnow.py), served from the domain's
        # root. Public by design. Only a build for lakenotice.com carries it,
        # because the key proves ownership of that one host; find_key reads the
        # templates directory, which holds exactly one such file.
        if urlsplit(self.base_url).hostname == SITE_DOMAIN:
            indexnow.copy_key_file(Path(__file__).parent / "templates", self.out)

    def build(self) -> None:
        if self.out.exists():
            shutil.rmtree(self.out)
        self.out.mkdir(parents=True)
        self.home()
        self.advisories()
        for water in self.waters:
            self.water_page(water)
        self.counties()
        self.state_pages()
        self.static_pages()
        self.where_to_check_page()
        # /levels/ and /es/niveles/, both off on main (DECISIONS 0025).
        levels.build(self, levels=i18n.LEVELS_ENABLED, es=i18n.ES_ENABLED)
        self.extras()


def build_site(
    snap: dict[str, Any],
    out: Path,
    *,
    base_url: str = "",
    support_email: str = "",
    app_store_url: str = "",
    ga4_measurement_id: str | None = None,
) -> None:
    SiteBuilder(
        snap,
        out,
        base_url=base_url,
        support_email=support_email,
        app_store_url=app_store_url,
        ga4_measurement_id=GA4_MEASUREMENT_ID
        if ga4_measurement_id is None
        else ga4_measurement_id,
    ).build()
