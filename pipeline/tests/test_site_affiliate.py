"""The dog-gear affiliate block (docs/DECISIONS.md 0013, narrowed by 0029).

Off while AMAZON_ASSOCIATE_TAG is empty: no block, no Amazon URL, no privacy
paragraph. On, the Dogs and algae page, and no other page, carries three to
five plain Amazon search links with the exact rel, the tag, Amazon's sentence
and a non-endorsement sentence naming both agencies; lake pages carry no
Amazon link at all; no wording anywhere offers a home toxin test kit or says a
product makes water safe. HTML is read with html.parser, never a regex. Each
guard has a negative control that first asserts its sabotage applied.
"""

from __future__ import annotations

import html
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


def dogs_page(root: Path) -> Path:
    return root / "dogs" / "index.html"


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
    # Empty means no links; set, it is a US Associates id. The shipped id is
    # Lake Notice's own, never Trout Truck's.
    tag = site.AMAZON_ASSOCIATE_TAG
    assert tag == "lakenotice-20"
    assert tag != "trouttruck-20"
    assert (site.gear_links() == []) == (tag == "")
    assert tag.endswith("-20")
    assert 3 <= len(site.GEAR_CATEGORIES) <= 5
    for link in site.gear_links():
        assert parse_qs(urlsplit(link["url"]).query)["tag"] == [tag]


def test_empty_tag_renders_nothing(off_site: Path) -> None:
    assert lake_pages(off_site), "the fixture build has no lake pages"
    assert dogs_page(off_site).exists()
    assert off_problems(off_site) == []


def test_off_guard_is_not_vacuous(on_site: Path) -> None:
    # Negative control: the same checker, run on a build whose tag was set,
    # must report the block (so "absent when empty" cannot pass by accident).
    assert parse(dogs_page(on_site)).has_section
    problems = off_problems(on_site)
    assert any("gear block present" in p for p in problems)
    assert any("Amazon URL present" in p for p in problems)
    assert any("privacy page" in p for p in problems)


def test_tagged_block_on_the_dogs_page(on_site: Path) -> None:
    page = dogs_page(on_site)
    g = parse(page)
    assert g.has_section
    amazon = [(h, r) for h, r in g.links if "amazon." in h]
    assert len(amazon) == len(site.GEAR_CATEGORIES)
    assert 3 <= len(amazon) <= 5
    # The one other link in the block is the privacy policy, without rel.
    assert [h for h, _ in g.links if "amazon." not in h] == ["../privacy/#affiliate"]
    for href, rel in amazon:
        assert rel == REL, rel  # the exact rel, no more, no less
        parts = urlsplit(href)
        assert (parts.scheme, parts.netloc, parts.path) == (
            "https", "www.amazon.com", "/s"
        ), href  # fmt: skip
        query = parse_qs(parts.query)
        assert sorted(query) == ["k", "tag"], href
        assert query["tag"] == [TAG], href
    assert [h for h, _ in amazon] == g.amazon_hrefs  # no Amazon link outside it
    text = block_text(g)
    assert DISCLOSURE in text
    assert site.gear_endorsement() in text
    # The disclosure comes before the first link, as on Trout Truck.
    raw = page.read_text(encoding="utf-8")
    assert raw.index(DISCLOSURE) < raw.index("https://www.amazon.com/s")
    # Each item says which piece of the page's advice it goes with.
    for _label, _terms, why in site.GEAR_CATEGORIES:
        assert why in text, why


def test_no_amazon_link_on_any_lake_page(on_site: Path) -> None:
    pages = lake_pages(on_site)
    assert len(pages) >= 2
    for page in pages:
        g = parse(page)
        assert not g.has_section, page
        assert g.amazon_hrefs == [], page
        assert "amazon." not in page.read_text(encoding="utf-8").casefold(), page


def test_lake_page_guard_is_not_vacuous(on_site: Path) -> None:
    # Negative control: put a tagged link into a lake page's HTML and the same
    # parser must find it, after asserting the sabotage applied.
    raw = lake_pages(on_site)[0].read_text(encoding="utf-8")
    link = site.amazon_search_url("dog life jacket")
    sabotaged = raw.replace("</main>", f'<a href="{link}">x</a></main>', 1)
    assert sabotaged != raw  # the sabotage applied
    g = Gear()
    g.feed(sabotaged)
    assert g.amazon_hrefs == [link]
    assert "amazon." in sabotaged.casefold()


def test_block_only_on_the_dogs_page_and_nowhere_in_data(on_site: Path) -> None:
    dogs = dogs_page(on_site)
    privacy = on_site / "privacy" / "index.html"
    for page in all_pages(on_site):
        if page == dogs:
            continue
        g = parse(page)
        assert not g.has_section, page
        assert g.amazon_hrefs == [], page
        if page != privacy:  # privacy names Amazon.com in prose, never a link
            assert "amazon." not in page.read_text(encoding="utf-8").casefold(), page
    for rel in ("sitemap.xml", "robots.txt", "snapshot/v1.json"):
        assert "amazon." not in (on_site / rel).read_text(encoding="utf-8").casefold()
    # JSON-LD blocks (script elements) on the dogs page carry no Amazon URL.
    assert dogs.read_text(encoding="utf-8").count("amazon.com") == len(
        site.GEAR_CATEGORIES
    )


def test_no_amazon_script_image_or_price(on_site: Path) -> None:
    raw = dogs_page(on_site).read_text(encoding="utf-8")
    for tag in ("<script", "<img", "<iframe", "<link"):
        for chunk in raw.split(tag)[1:]:
            assert "amazon" not in chunk.split(">", 1)[0].casefold(), tag
    text = block_text(parse(dogs_page(on_site)))
    assert "$" not in text
    assert "price" not in text.casefold()


def test_privacy_paragraph_only_when_set(on_site: Path) -> None:
    privacy = (on_site / "privacy" / "index.html").read_text(encoding="utf-8")
    assert 'id="affiliate"' in privacy
    flat = " ".join(html.unescape(privacy).split())
    assert DISCLOSURE in flat
    assert site.gear_endorsement() in flat
    assert "Amazon Services LLC Associates Program" in flat
    assert "Dogs and algae</a> page, and no other page" in flat
    assert "lake page" not in flat


def test_no_test_kit_or_safety_wording_anywhere(on_site: Path) -> None:
    labels = " ".join(" ".join(c) for c in site.GEAR_CATEGORIES)
    for needle in FORBIDDEN:
        assert needle not in labels.casefold(), needle
    text = block_text(parse(dogs_page(on_site)))
    for needle in FORBIDDEN:
        assert needle not in text.casefold(), needle
    assert affirmative_safety_claims(text) == []
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
    # Negative control: put a test kit and a safety claim into the categories
    # and the same scans must flag them, after asserting the sabotage applied.
    original = site.GEAR_CATEGORIES
    sabotaged = (
        *original,
        ("Home toxin test kit", "algae toxin test kit", "Keeps your dog safe."),
    )
    monkeypatch.setattr(site, "GEAR_CATEGORIES", sabotaged)
    assert original != site.GEAR_CATEGORIES  # the sabotage applied
    out = build(tmp_path, TAG)
    text = block_text(parse(dogs_page(out)))
    assert "home toxin test kit" in text.casefold()
    assert [n for n in FORBIDDEN if n in text.casefold()], "the scan missed it"
    assert affirmative_safety_claims(text) != []
    labels = " ".join(" ".join(c) for c in site.GEAR_CATEGORIES)
    assert [n for n in FORBIDDEN if n in labels.casefold()]


def test_a_changed_tag_leaves_no_trace_of_the_old_one(tmp_path: Path) -> None:
    out = build(tmp_path, "other-20")
    for page in all_pages(out):
        assert TAG not in page.read_text(encoding="utf-8")
    assert "tag=other-20" in dogs_page(out).read_text(encoding="utf-8")


def test_ios_sources_carry_no_amazon_link() -> None:
    root = Path(__file__).resolve().parents[2] / "ios"
    swift = [
        p for p in root.rglob("*.swift") if "amazon" in p.read_text("utf-8").casefold()
    ]
    assert swift == []
