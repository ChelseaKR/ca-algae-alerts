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
import shutil
from collections import Counter, defaultdict
from collections.abc import Iterable
from importlib import resources
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import jinja2

from caalgae import where_to_check, wording
from caalgae.normalize import CA_COUNTIES, TIER_RANK
from caalgae.snapshot import slugify

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


def water_title(name: str, county: str | None) -> str:
    """A waterbody page title of at most TITLE_MAX characters. ``county`` is
    passed only when another water in the same state has the same name, so two
    "Bear Creek" pages never share a title."""
    where = f"{name}, {county} County" if county else name
    short = f"{name}, {county}" if county else name
    tail = f" | {SITE_NAME}"
    return fit(
        [
            f"{where} toxic algae advisories{tail}",
            f"{where} algae advisories{tail}",
            f"{short} algae advisories{tail}",
            f"{short}{tail}",
            f"{name}{tail}",
        ],
        TITLE_MAX,
    )


def water_description(name: str, place: str | None, headline: str) -> str:
    """A waterbody page description of at most DESCRIPTION_MAX characters.
    The status and its date come first and are never the part that is cut."""
    lead = f"{name}, {place}: " if place else f"{name}: "
    return fit(
        [
            f"{lead}{headline} Every state advisory record since 2016.",
            f"{lead}{headline} State records since 2016.",
            f"{lead}{headline}",
            f"{name}: {headline}",
        ],
        DESCRIPTION_MAX,
    )


# PLACEHOLDER, deliberately empty: the owner has not created a GA4 property
# for Lake Notice yet (docs/DOMAIN.md, "After the site is live"). When she
# does, the change is this one line, a measurement id of the form "G-XXXXXXXXXX".
# Set, every page carries the tag and the privacy page describes it; empty,
# no page loads any script and the privacy page says nothing is collected.
# Never copy another product's id here: it would mix this site's visits into
# that property.
GA4_MEASUREMENT_ID = ""
# Amazon Associates dog-gear links (docs/DECISIONS.md 0013, narrowed by 0015).
# Website only, and only on the Dogs and algae page (/dogs/): never on a lake,
# county, state or any other page, and never in the iOS app, which has no web
# view. The one config value is the tracking id below. It defaults to the
# owner's existing Associates id, trouttruck-20, which needs lakenotice.com on
# that account's website list before this ships; a Lake Notice id of its own
# is a one-line change here. Empty, the gear block and the privacy paragraph
# render nothing and no Amazon URL is built anywhere. Never a home toxin test
# kit: a negative strip is not safety, and nothing here may imply that gear
# makes algae exposure any less of a risk (tests/test_site_affiliate.py fails on
# test-kit or safety wording in the categories or in a built page).
AMAZON_ASSOCIATE_TAG = "trouttruck-20"
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
        dog_answer=wording.dog_answer,
        guidance=wording.LEVEL_GUIDANCE,
        guidance_for=wording.guidance_for,
        cells_label=wording.cells_label,
        satellite_explainer=wording.SATELLITE_EXPLAINER,
        dog_advice=wording.DOG_ADVICE,
    )
    return env


def _advisory_sort(water: dict[str, Any]) -> tuple[str, int, str]:
    s = water["status"]
    return (s["posted"] or "", TIER_RANK.get(s["tier"] or "", 0), water["name"])


def months_before(day: dt.date, months: int) -> dt.date:
    """``day`` minus ``months`` calendar months, the day clamped to the month."""
    index = day.year * 12 + (day.month - 1) - months
    year, month = divmod(index, 12)
    last = calendar.monthrange(year, month + 1)[1]
    return dt.date(year, month + 1, min(day.day, last))


def is_indexable(water: dict[str, Any], run_date: dt.date, months: int) -> bool:
    """True when the state's last advisory for this water falls within
    ``months`` months before ``run_date``."""
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
        self.waters = snap["waterbodies"]
        self._name_counts = Counter(
            (w["state"], w["name"].casefold()) for w in self.waters
        )
        self.common["states_present"] = sorted({w["state"] for w in self.waters})
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
        recent = [w for w in open_ if wording.is_recent(w["status"], self.run_date)]
        self._write(
            "",
            "index.html.jinja",
            title=f"California lake toxic algae advisories by date | {SITE_NAME}",
            description=(
                "Toxic algae (harmful algal bloom) advisories at California lakes "
                "and rivers, newest first, with each lake's history since 2016 "
                "for swimmers and dogs."
            ),
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
        self._write(
            "advisories/",
            "advisories.html.jinja",
            title=f"California algae advisories with no all-clear | {SITE_NAME}",
            description=(
                "Every California waterbody whose latest state record is an "
                "algae advisory, newest first, including old ones the state "
                "never recorded an end for."
            ),
            lastmod=self.site_date,
            waters=self.open_advisories(),
            breadcrumb=crumbs,
            structured_data={
                "@context": "https://schema.org",
                **self._breadcrumb_data(crumbs),
            },
        )

    def _name_is_shared(self, water: dict[str, Any]) -> bool:
        """True when another water in the same state has this name."""
        return self._name_counts[(water["state"], water["name"].casefold())] > 1

    @staticmethod
    def _county_label(water: dict[str, Any]) -> str | None:
        """The county to name in a title, or None when there is none."""
        if water["counties"]:
            return " and ".join(water["counties"])
        return None

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
        county = (
            f"{' and '.join(water['counties'])} County"
            if water["counties"]
            else (
                water["county_text"]
                # Missouri's layer names no county; California's rows sometimes omit it.
                or (
                    "County not recorded"
                    if water["state"] == "CA"
                    else STATE_NAMES[water["state"]]
                )
            )
        )
        about: dict[str, Any] = {"@type": "BodyOfWater", "name": water["name"]}
        if water["center"]:
            about["geo"] = {
                "@type": "GeoCoordinates",
                "latitude": water["center"]["lat"],
                "longitude": water["center"]["lon"],
            }
        water_source = self.sources[STATE_SOURCE[water["state"]]]
        indexable = is_indexable(water, self.run_date, INDEX_WINDOW_MONTHS)
        satellite_source = self.sources.get("epa-cyan")
        self._write(
            rel,
            "water.html.jinja",
            title=water_title(
                water["name"],
                self._county_label(water) if self._name_is_shared(water) else None,
            ),
            description=water_description(
                water["name"],
                None if county == "County not recorded" else county,
                wording.headline(water["status"]),
            ),
            noindex=not indexable,
            robots="noindex,follow",
            lastmod=self.water_dates.get(water["id"]),
            water=water,
            water_source=water_source,
            satellite_source=satellite_source,
            county=county,
            sites=sites,
            county_links=[(c, slugify(c)) for c in water["counties"]],
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
        for county, waters in self.by_county.items():
            rel = f"county/{slugify(county)}/"
            crumbs_c = [*crumbs, (f"{county} County", self.base_url + rel)]
            ordered = sorted(
                waters,
                key=lambda w: (w["status"]["kind"] != "advisory", w["name"].casefold()),
            )
            self._write(
                rel,
                "county.html.jinja",
                title=fit(
                    [
                        f"{county} County lake toxic algae advisories | {SITE_NAME}",
                        f"{county} County algae advisories | {SITE_NAME}",
                    ],
                    TITLE_MAX,
                ),
                description=(
                    f"Toxic algae advisory status and history for {len(waters)} "
                    f"lakes and rivers in {county} County, California."
                ),
                county=county,
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
            ordered = sorted(
                waters,
                key=lambda w: (w["status"]["kind"] != "advisory", w["name"].casefold()),
            )
            self._write(
                rel,
                "state.html.jinja",
                title=f"{name} lake algae advisories | {SITE_NAME}",
                description=(
                    f"Toxic algae advisory status and history for {len(waters)} "
                    f"lakes and rivers in {name}, from the state's own records."
                ),
                state=state,
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
                # Only the dogs page shows record data; about, privacy and
                # support have no content date in the repo, so no lastmod.
                lastmod=self.site_date if rel == "dogs/" else None,
                counties_known=len(CA_COUNTIES),
                tiers=["caution", "warning", "danger", "other_advisory"],
                # The gear block is on the dogs page and nowhere else
                # (DECISIONS 0015); every other page gets no links.
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
