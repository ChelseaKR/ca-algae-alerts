"""The product name appears in many places; every one must match SITE_NAME.

`name_problems` reads each place that carries the name and returns what
disagrees. The real tree must report nothing; a copy with one place
sabotaged must report that place (and the test first asserts the sabotage
changed the copy, so a no-op edit cannot read as a pass).
"""

from __future__ import annotations

import json
import plistlib
import re
import shutil
from html.parser import HTMLParser
from pathlib import Path

from paths import PAGE, SAMPLE

from caalgae import cli, site

ROOT = Path(__file__).resolve().parents[2]
OLD_NAME = "Algae Alerts"

PLISTS = [
    "ios/AlgaeAlerts/Resources/Info.plist",
    "ios/AlgaeAlertsWidgets/Info.plist",
]
TEXT_FILES = [
    "README.md",
    "pipeline/src/caalgae/templates/style.css",
    "docs/app-store/LISTING.md",
    *PLISTS,
]
# Where the retired name must not survive. DECISIONS.md and CHANGELOG.md
# record the rename, so they are not scanned.
SCANNED_FOR_OLD_NAME = [
    *TEXT_FILES,
    "pipeline/src/caalgae/site.py",
    "pipeline/src/caalgae/wording.py",
]


class _Meta(HTMLParser):
    """Collects og:site_name, the <title> text and JSON-LD script bodies."""

    def __init__(self) -> None:
        super().__init__()
        self.og_site_name: str | None = None
        self.title = ""
        self.ld: list[str] = []
        self._in_title = False
        self._in_ld = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        if tag == "meta" and a.get("property") == "og:site_name":
            self.og_site_name = a.get("content")
        elif tag == "title":
            self._in_title = True
        elif tag == "script" and a.get("type") == "application/ld+json":
            self._in_ld = True
            self.ld.append("")

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        elif tag == "script":
            self._in_ld = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
        elif self._in_ld:
            self.ld[-1] += data


def name_problems(root: Path) -> list[str]:
    """Every place under `root` whose product name is not SITE_NAME."""
    found: list[str] = []
    for rel in PLISTS:
        shown = plistlib.loads((root / rel).read_bytes()).get("CFBundleDisplayName")
        if shown != site.SITE_NAME:
            found.append(f"{rel}: CFBundleDisplayName is {shown!r}")
    readme = (root / "README.md").read_text(encoding="utf-8").splitlines()[0]
    if readme != f"# {site.SITE_NAME}":
        found.append(f"README.md: title line is {readme!r}")
    css = (root / "pipeline/src/caalgae/templates/style.css").read_text(
        encoding="utf-8"
    )
    if not css.startswith(f"/* {site.SITE_NAME} --"):
        found.append("style.css: header comment does not carry the name")
    listing = (root / "docs/app-store/LISTING.md").read_text(encoding="utf-8")
    if f"`{site.SITE_NAME}` (" not in listing:
        found.append("LISTING.md: the Name section does not carry the name")
    for rel in SCANNED_FOR_OLD_NAME:
        text = (root / rel).read_text(encoding="utf-8")
        if OLD_NAME in text or "working title" in text.casefold():
            found.append(f"{rel}: still carries the retired name or 'working title'")
    return found


def test_every_place_carries_the_one_constant() -> None:
    assert name_problems(ROOT) == []


def test_name_and_domain_rules() -> None:
    lowered = site.SITE_NAME.casefold()
    assert site.SITE_NAME == "Lake Notice"
    assert "bloom" not in lowered  # hard rule: no "bloom" in the name
    assert "safe" not in lowered  # nothing here may imply safe water
    assert site.SITE_DOMAIN == "lakenotice.com"
    assert site.DEFAULT_BASE_URL == "https://lakenotice.com/"


def test_sabotage_is_caught(tmp_path: Path) -> None:
    for rel in [
        *TEXT_FILES,
        "pipeline/src/caalgae/site.py",
        "pipeline/src/caalgae/wording.py",
    ]:
        dest = tmp_path / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, dest)
    assert name_problems(tmp_path) == []  # the copy starts clean
    victim = tmp_path / PLISTS[1]
    before = victim.read_text(encoding="utf-8")
    victim.write_text(before.replace(site.SITE_NAME, OLD_NAME), encoding="utf-8")
    assert victim.read_text(encoding="utf-8") != before  # the sabotage applied
    problems = name_problems(tmp_path)
    assert any(PLISTS[1] in p for p in problems), problems


def test_built_site_carries_the_name_and_not_the_old_one(tmp_path: Path) -> None:
    out = tmp_path / "site"
    assert (
        cli.main(
            [
                "--fixture-page", str(PAGE),
                "--fixture-csv", str(SAMPLE),
                "--run-today", "2026-10-12",
                "--history", str(tmp_path / "history.json"),
                "--site-out", str(out),
            ]
        )
        == 0
    )  # fmt: skip
    pages = sorted(out.rglob("*.html"))
    assert pages
    for page in pages:
        text = page.read_text(encoding="utf-8")
        assert OLD_NAME not in text and "working title" not in text.casefold(), page
        meta = _Meta()
        meta.feed(text)
        assert meta.og_site_name == site.SITE_NAME, page
        # A water page whose title carries its advisory and date gives the
        # room to the date (DECISIONS 0018); og:site_name, checked above,
        # still names the site.
        dated = page.parent.parent.name == "water" and re.search(
            r"[A-Z][a-z]{2} \d{1,2}, \d{4}$", meta.title.strip()
        )
        # A county title that counts its waters under an advisory gives the
        # room to the count the same way (0018, 2026-11-04 addendum).
        counted = page.parent.parent.name == "county" and re.search(
            r"\d+ of \d+ waters?$", meta.title.strip()
        )
        # A New York water title that carries its bloom years does the same
        # (DECISIONS 0021).
        # A name too long to fit beside the site name is the whole title.
        dated = dated or (
            page.parent.parent.name == "ny"
            and (
                re.search(r", NY(?: algae)?: .* \d{4}$", meta.title.strip())
                or len(f"{meta.title.strip()} | {site.SITE_NAME}") > site.TITLE_MAX
            )
        )
        if page.name != "404.html" and not dated and not counted:
            assert meta.title.strip().endswith(site.SITE_NAME), (page, meta.title)
    home = _Meta()
    home.feed((out / "index.html").read_text(encoding="utf-8"))
    names = [json.loads(block).get("name") for block in home.ld]
    assert site.SITE_NAME in names
    sitemap = (out / "sitemap.xml").read_text(encoding="utf-8")
    assert f"<loc>https://{site.SITE_DOMAIN}/" in sitemap
    assert "github.io" not in sitemap
    assert (
        f"Sitemap: https://{site.SITE_DOMAIN}/sitemap.xml"
        in (out / "robots.txt").read_text()
    )
    privacy = (out / "privacy" / "index.html").read_text(encoding="utf-8")
    assert f"this website and the {site.SITE_NAME} iPhone app" in " ".join(
        privacy.split()
    )
