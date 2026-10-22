"""The dog-gear affiliate block (docs/DECISIONS.md 0013).

Off while AMAZON_ASSOCIATE_TAG is empty: no block, no Amazon URL, no privacy
paragraph. On, every lake page carries three plain Amazon search links with
the exact rel, Amazon's sentence and a non-endorsement sentence naming the
agency; no other page does; no wording anywhere offers a home toxin test kit
or says a product makes water safe. HTML is read with html.parser, never a
regex. Each guard has a negative control that first asserts its sabotage
applied.
"""

from __future__ import annotations

import html
import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from paths import CYAN_CACHE, MO_POINTS, PAGE, TRAPS
from test_site import affirmative_safety_claims

from caalgae import cli, site

TAG = "lakenotice-test-20"
REL = "sponsored nofollow noopener"
DISCLOSURE = "As an Amazon Associate I earn from qualifying purchases."
# Wording that must never appear in a built page or in a gear category: a home
# toxin test kit, or a claim that a product makes water safe.
FORBIDDEN = (
    "test kit", "testing kit", "toxin test", "test strip", "water test",
    "cyanotoxin test", "purif", "filter your", "makes the water", "guarantee",
    "safe", "clean water",
)  # fmt: skip


def build(tmp_path: Path, tag: str) -> Path:
    """Build a CA plus Missouri site with ``site.AMAZON_ASSOCIATE_TAG`` ``tag``."""
    out = tmp_path / "site"
    original = site.AMAZON_ASSOCIATE_TAG
    site.AMAZON_ASSOCIATE_TAG = tag
    try:
        assert (
            cli.main(
                [
                    "--fixture-page", str(PAGE),
                    "--fixture-csv", str(TRAPS),
                    "--run-today", "2026-10-12",
                    "--history", str(tmp_path / "history.json"),
                    "--site-out", str(out),
                    "--mo-fixture", str(MO_POINTS),
                    "--cyan-cache", str(CYAN_CACHE),
                ]
            )
            == 0
        )  # fmt: skip
    finally:
        site.AMAZON_ASSOCIATE_TAG = original
    return out


class Gear(HTMLParser):
    """Collects the gear section's text, its links and its rel values."""

    def __init__(self) -> None:
        super().__init__()
        self.depth = 0
        self.inside = False
        self.text: list[str] = []
        self.links: list[tuple[str, str | None]] = []
        self.amazon_hrefs: list[str] = []
        self.has_section = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        href = a.get("href") or ""
        if "amazon." in href:
            self.amazon_hrefs.append(href)
        if tag == "section" and "gear" in (a.get("class") or "").split():
            self.inside = True
            self.has_section = True
            self.depth = 0
        if self.inside:
            if tag == "section":
                self.depth += 1
            if tag == "a":
                self.links.append((href, a.get("rel")))

    def handle_endtag(self, tag: str) -> None:
        if self.inside and tag == "section":
            self.depth -= 1
            if self.depth == 0:
                self.inside = False

    def handle_data(self, data: str) -> None:
        if self.inside:
            self.text.append(data)


def parse(page: Path) -> Gear:
    g = Gear()
    g.feed(page.read_text(encoding="utf-8"))
    return g


def block_text(g: Gear) -> str:
    return " ".join(" ".join(g.text).split())


def all_pages(root: Path) -> list[Path]:
    return sorted(root.rglob("*.html"))


def lake_pages(root: Path) -> list[Path]:
    """The pages that carry a water's own status: water/<id>/index.html."""
    return sorted((root / "water").glob("*/index.html"))


@pytest.fixture(scope="module")
def off_site(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build(tmp_path_factory.mktemp("off"), "")


@pytest.fixture(scope="module")
def on_site(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build(tmp_path_factory.mktemp("on"), TAG)


def off_problems(root: Path) -> list[str]:
    """What is wrong with a build that should carry no affiliate surface."""
    found: list[str] = []
    for page in all_pages(root):
        text = page.read_text(encoding="utf-8")
        g = parse(page)
        if g.has_section or "gear-heading" in text:
            found.append(f"{page}: gear block present")
        if g.amazon_hrefs or "amazon.com" in text.casefold():
            found.append(f"{page}: Amazon URL present")
    privacy = (root / "privacy" / "index.html").read_text(encoding="utf-8")
    if 'id="affiliate"' in privacy or DISCLOSURE in privacy:
        found.append("privacy page carries the affiliate paragraph")
    return found


def test_the_constant_and_the_links_agree() -> None:
    # Empty (the shipped state until the owner creates the id) means no links;
    # set, it is a US Associates id of its own, never Trout Truck's.
    tag = site.AMAZON_ASSOCIATE_TAG
    assert (site.gear_links() == []) == (tag == "")
    if tag:
        assert tag.endswith("-20") and tag != "trouttruck-20"


def test_empty_tag_renders_nothing(off_site: Path) -> None:
    assert lake_pages(off_site), "the fixture build has no lake pages"
    assert off_problems(off_site) == []


def test_off_guard_is_not_vacuous(on_site: Path) -> None:
    # Negative control: the same checker, run on a build whose tag was set,
    # must report the block (so "absent when empty" cannot pass by accident).
    assert parse(lake_pages(on_site)[0]).has_section
    problems = off_problems(on_site)
    assert any("gear block present" in p for p in problems)
    assert any("Amazon URL present" in p for p in problems)
    assert any("privacy page" in p for p in problems)


def test_tagged_block_on_every_lake_page(on_site: Path) -> None:
    pages = lake_pages(on_site)
    assert len(pages) >= 2
    states = set()
    for page in pages:
        g = parse(page)
        assert g.has_section, page
        amazon = [(h, r) for h, r in g.links if "amazon." in h]
        assert len(amazon) == len(site.GEAR_CATEGORIES) == 3, page
        # The one other link in the block is the privacy policy, without rel.
        assert [h for h, _ in g.links if "amazon." not in h] == [
            "../../privacy/#affiliate"
        ]
        for href, rel in amazon:
            assert rel == REL, (page, rel)  # the exact rel, no more, no less
            parts = urlsplit(href)
            assert (parts.scheme, parts.netloc, parts.path) == (
                "https", "www.amazon.com", "/s"
            ), href  # fmt: skip
            query = parse_qs(parts.query)
            assert sorted(query) == ["k", "tag"], href
            assert query["tag"] == [TAG], href
        assert [h for h, _ in amazon] == g.amazon_hrefs, (
            page
        )  # no Amazon link outside the block
        text = block_text(g)
        assert DISCLOSURE in text, page
        if "Missouri" in page.read_text(encoding="utf-8")[:4000]:
            states.add("MO")
        for agency in ("the Water Board", "Missouri DNR"):
            if f"not {agency}'s, and {agency} does not endorse them or Amazon." in text:
                states.add(agency)
    assert "the Water Board" in states, "no California page names the Water Board"
    assert "Missouri DNR" in states, "no Missouri page names Missouri DNR"


def test_california_pages_name_the_water_board_and_missouri_pages_name_dnr(
    on_site: Path,
) -> None:
    snap_waters = json.loads((on_site / "snapshot" / "v1.json").read_text())[
        "waterbodies"
    ]
    by_state = {"CA": 0, "MO": 0}
    for w in snap_waters:
        page = on_site / "water" / w["id"] / "index.html"
        if not page.exists():
            continue
        text = block_text(parse(page))
        want = site.gear_endorsement(w["state"])
        assert want in text, (w["name"], text)
        other = "MO" if w["state"] == "CA" else "CA"
        assert site.gear_endorsement(other) not in text
        by_state[w["state"]] += 1
    assert by_state["CA"] and by_state["MO"], by_state


def test_block_only_on_lake_pages_and_nowhere_in_data(on_site: Path) -> None:
    lakes = set(lake_pages(on_site))
    for page in all_pages(on_site):
        text = page.read_text(encoding="utf-8")
        if page in lakes:
            continue
        assert not parse(page).has_section, page
        if page != on_site / "privacy" / "index.html":
            assert "amazon." not in text.casefold(), page
    for rel in ("sitemap.xml", "robots.txt", "snapshot/v1.json"):
        assert "amazon." not in (on_site / rel).read_text(encoding="utf-8").casefold()
    # JSON-LD blocks (script elements) on lake pages carry no Amazon URL either.
    for page in lakes:
        assert page.read_text(encoding="utf-8").count("amazon.com") == len(
            site.GEAR_CATEGORIES
        ), page


def test_privacy_paragraph_only_when_set(on_site: Path) -> None:
    privacy = (on_site / "privacy" / "index.html").read_text(encoding="utf-8")
    assert 'id="affiliate"' in privacy
    flat = " ".join(html.unescape(privacy).split())
    assert DISCLOSURE in flat
    assert site.gear_endorsement() in flat
    assert "Amazon Services LLC Associates Program" in flat


def test_no_test_kit_or_safety_wording_anywhere(on_site: Path) -> None:
    labels = " ".join(f"{label} {terms}" for label, terms in site.GEAR_CATEGORIES)
    for needle in FORBIDDEN:
        assert needle not in labels.casefold(), needle
    for page in lake_pages(on_site):
        text = block_text(parse(page)).casefold()
        for needle in FORBIDDEN:
            assert needle not in text, (page, needle)
        assert affirmative_safety_claims(block_text(parse(page))) == []
    privacy = " ".join(
        (on_site / "privacy" / "index.html").read_text(encoding="utf-8").split()
    ).casefold()
    for needle in FORBIDDEN:
        if needle == "safe":
            continue  # the privacy page's other sections predate this block
        assert needle not in privacy, needle


def test_forbidden_wording_guard_is_not_vacuous(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Negative control: put a test kit into the categories and the same
    # scans must flag it, after asserting the sabotage applied.
    original = site.GEAR_CATEGORIES
    sabotaged = (*original, ("Home toxin test kit", "algae toxin test kit"))
    monkeypatch.setattr(site, "GEAR_CATEGORIES", sabotaged)
    assert original != site.GEAR_CATEGORIES  # the sabotage applied
    out = build(tmp_path, TAG)
    page = lake_pages(out)[0]
    text = block_text(parse(page)).casefold()
    assert "home toxin test kit" in text
    assert [n for n in FORBIDDEN if n in text], "the scan did not flag a test kit"
    labels = " ".join(f"{label} {terms}" for label, terms in site.GEAR_CATEGORIES)
    assert [n for n in FORBIDDEN if n in labels.casefold()]


def test_a_changed_tag_leaves_no_trace_of_the_old_one(tmp_path: Path) -> None:
    out = build(tmp_path, "other-20")
    for page in all_pages(out):
        text = page.read_text(encoding="utf-8")
        assert TAG not in text
    assert "tag=other-20" in lake_pages(out)[0].read_text(encoding="utf-8")


def test_ios_sources_carry_no_amazon_link() -> None:
    root = Path(__file__).resolve().parents[2] / "ios"
    swift = [
        p for p in root.rglob("*.swift") if "amazon" in p.read_text("utf-8").casefold()
    ]
    assert swift == []
