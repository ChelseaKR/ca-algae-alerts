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

import datetime as dt
import json
import shutil
from collections import defaultdict
from importlib import resources
from pathlib import Path
from typing import Any

import jinja2

from caalgae import wording
from caalgae.normalize import CA_COUNTIES, TIER_RANK
from caalgae.snapshot import slugify

SITE_NAME = "Algae Alerts (working title)"
DEFAULT_BASE_URL = "https://chelseakr.github.io/ca-algae-alerts/"
# Empty until the owner creates a GA4 property for this site
# (docs/OWNER-STEPS in the hand-off). Set, every page carries the tag and the
# privacy page describes it; empty, the privacy page says nothing is collected.
GA4_MEASUREMENT_ID = ""
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
        dog_advice=wording.DOG_ADVICE,
    )
    return env


def _advisory_sort(water: dict[str, Any]) -> tuple[str, int, str]:
    s = water["status"]
    return (s["posted"] or "", TIER_RANK.get(s["tier"] or "", 0), water["name"])


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
        source = snap["sources"][0]
        self.common: dict[str, Any] = {
            "site_name": SITE_NAME,
            "support_email": support_email,
            "app_store_url": app_store_url,
            "ga4_measurement_id": ga4_measurement_id,
            "ga4_denied_regions": GA4_DENIED_REGIONS,
            "source": source,
            "source_file": snap["source_file"],
            "run_date": self.run_date,
            "quarantine": snap["quarantine"],
        }
        self.waters = snap["waterbodies"]
        self.by_county: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.no_county: list[dict[str, Any]] = []
        for water in self.waters:
            for county in water["counties"]:
                self.by_county[county].append(water)
            if not water["counties"]:
                self.no_county.append(water)

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
        html = self.env.get_template(template).render(
            **self.common,
            root=root or "./",
            canonical_url=canonical,
            breadcrumb=context.pop("breadcrumb", None),
            structured_data=context.pop("structured_data", None),
            noindex=context.pop("noindex", False),
            **context,
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")
        if canonical:
            self.urls.append(canonical)

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
            title=f"California lake toxic algae advisories, by date | {SITE_NAME}",
            description=(
                "Toxic algae (harmful algal bloom) advisories at California lakes "
                "and rivers, newest first, with each lake's history since 2016. "
                "For swimmers, families, paddlers, anglers and dog owners."
            ),
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
            title=f"Every California algae advisory with no all-clear recorded | {SITE_NAME}",
            description=(
                "Every California waterbody whose latest state record is an "
                "algae advisory, newest posting first, including old advisories "
                "the state never recorded an end for."
            ),
            waters=self.open_advisories(),
            breadcrumb=crumbs,
            structured_data={
                "@context": "https://schema.org",
                **self._breadcrumb_data(crumbs),
            },
        )

    def water_page(self, water: dict[str, Any]) -> None:
        rel = f"water/{water['id']}/"
        crumbs = self._crumbs((water["name"], self.base_url + rel))
        sites = {s["id"]: s for s in water["sites"]}
        county = (
            f"{' and '.join(water['counties'])} County"
            if water["counties"]
            else (water["county_text"] or "County not recorded")
        )
        about: dict[str, Any] = {"@type": "BodyOfWater", "name": water["name"]}
        if water["center"]:
            about["geo"] = {
                "@type": "GeoCoordinates",
                "latitude": water["center"]["lat"],
                "longitude": water["center"]["lon"],
            }
        self._write(
            rel,
            "water.html.jinja",
            title=(
                f"{water['name']} toxic algae advisories and history "
                f"(swimming, kids, dogs) | {SITE_NAME}"
            ),
            description=(
                f"{water['name']}, {county}: {wording.headline(water['status'])} "
                "Every state advisory record since 2016, with what each level "
                "means for people, children and dogs."
            ),
            water=water,
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
                        "isBasedOn": self.common["source"]["dataset_url"],
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
                title=f"{county} County lake toxic algae advisories | {SITE_NAME}",
                description=(
                    f"Toxic algae advisory status and history for {len(waters)} "
                    f"lakes and rivers in {county} County, California."
                ),
                county=county,
                waters=ordered,
                breadcrumb=crumbs_c,
                structured_data={
                    "@context": "https://schema.org",
                    **self._breadcrumb_data(crumbs_c),
                },
            )

    def static_pages(self) -> None:
        pages = [
            ("dogs/", "dogs.html.jinja", "Is this lake safe for my dog? Reading California algae advisories",
             "How to read California toxic algae advisories before taking your dog to a lake: what each level means, why no advisory is not an all-clear, and signs to watch for."),
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
                counties_known=len(CA_COUNTIES),
                tiers=["caution", "warning", "danger", "other_advisory"],
            )
        self._write("404.html", "404.html.jinja", title=f"Page not found | {SITE_NAME}",
                    description="Page not found.", noindex=True)  # fmt: skip

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
            urls=sorted(self.urls), lastmod=self.snap["run_date"]
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
        self.static_pages()
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
