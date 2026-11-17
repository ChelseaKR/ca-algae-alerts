"""The footer's Ko-fi tip link (docs/DECISIONS.md 0043).

On, every built HTML page that has the site footer carries one tip line in
that footer, and nowhere else on the page: not in <main>, not next to an
advisory level, never on a lake, county or state page's body. It is a plain
link with target="_blank" rel="noopener": no Ko-fi script, image, frame or
widget, and no click tracking. Nothing reaches the snapshot the iOS app
reads, and the iOS sources never name Ko-fi. Off (``KOFI_URL = ""``), no page
has it. The words make no safety or dog claim. HTML is read with
html.parser, never a regex; each guard has a negative control that first
asserts its sabotage applied.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

import pytest
from paths import CYAN_CACHE, MO_POINTS, PAGE, TRAPS

from caalgae import cli, site

REPO = Path(__file__).resolve().parents[2]
# From the constant, so swapping in the real page changes nothing here.
URL = site.KOFI_URL
LEAD = "Lake Notice is made by one person."
LINK_TEXT = "You can leave a tip on Ko-fi."
LINE = (
    f'<p class="tip-line">{LEAD} '
    f'<a href="{URL}" target="_blank" rel="noopener">{LINK_TEXT}</a></p>'
)
# Never in the tip's words: nothing about safety, dogs, a lake's status or
# what a visitor decided, and never "no tracking".
BANNED = (
    "safe", "dog", "health", "advisor", "algae", "bloom", "toxic", "swim",
    "helped", "decide", "protect", "track", "guarantee", "kept",
)  # fmt: skip


def build(tmp_path: Path, url: str) -> Path:
    """Build the CA plus Missouri fixture site with ``site.KOFI_URL`` ``url``."""
    out = tmp_path / "site"
    original = site.KOFI_URL
    site.KOFI_URL = url
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
        site.KOFI_URL = original
    return out


class Where(HTMLParser):
    """Where Ko-fi appears in a page: each link's enclosing landmark and its
    attributes, and any script, image, frame or link element naming it."""

    def __init__(self) -> None:
        super().__init__()
        self.stack: list[str] = []
        self.links: list[tuple[str, dict[str, str | None]]] = []
        self.embeds: list[str] = []
        self.has_footer = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        if tag in ("main", "footer", "header", "nav"):
            self.stack.append(tag)
            if tag == "footer":
                self.has_footer = True
        named = any("ko-fi" in (v or "").lower() for v in a.values())
        if tag == "a" and named:
            self.links.append((self.stack[-1] if self.stack else "body", a))
        elif named:
            self.embeds.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag in ("main", "footer", "header", "nav") and self.stack:
            self.stack.pop()

    def handle_data(self, data: str) -> None:
        if "ko-fi" in data.lower() and self.stack and self.stack[-1] != "footer":
            self.embeds.append(f"text in <{self.stack[-1]}>")


def _link_problems(rel: Path, w: Where, text: str) -> list[str]:
    """A page with a footer, the line on: one link, in the footer, exactly
    as drafted, with no hook."""
    if len(w.links) != 1:
        return [f"{rel}: {len(w.links)} Ko-fi links, not one"]
    found = []
    landmark, attrs = w.links[0]
    if landmark != "footer":
        found.append(f"{rel}: the link is in <{landmark}>, not the footer")
    if attrs.get("target") != "_blank" or attrs.get("rel") != "noopener":
        found.append(f"{rel}: target or rel is not exactly _blank, noopener")
    if any(k.startswith(("data-", "on")) for k in attrs):
        found.append(f"{rel}: the link carries a tracking or script hook")
    if text.count(LINE) != 1:
        found.append(f"{rel}: the footer line's words or markup differ")
    return found


def _page_problems(rel: Path, text: str, *, on: bool) -> tuple[list[str], bool]:
    w = Where()
    w.feed(text)
    found = []
    if w.embeds:
        found.append(f"{rel}: Ko-fi outside a footer link: {w.embeds}")
    if not on:
        if w.links or "tip-line" in text:
            found.append(f"{rel}: a tip line while it is off")
    elif w.has_footer:
        found += _link_problems(rel, w, text)
    elif w.links:
        found.append(f"{rel}: a tip link on a page with no footer")
    return found, w.has_footer


def problems(out: Path, *, on: bool) -> list[str]:
    found: list[str] = []
    pages = sorted(out.rglob("*.html"))
    if not pages:
        found.append("no pages built")
    footers = 0
    for path in pages:
        page, has_footer = _page_problems(
            path.relative_to(out), path.read_text(encoding="utf-8"), on=on
        )
        found += page
        footers += has_footer
    if on and not footers:
        found.append("no page has a footer")
    data = (
        p
        for p in out.rglob("*")
        if p.is_file() and p.suffix in {".json", ".xml", ".txt", ".js"}
    )
    for path in data:
        if "ko-fi" in path.read_text(encoding="utf-8", errors="ignore").lower():
            found.append(f"{path.relative_to(out)}: Ko-fi in a data file")
    return found


@pytest.fixture(scope="module")
def built_on(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build(tmp_path_factory.mktemp("tip-on"), URL)


def test_the_constant_is_one_well_formed_ko_fi_address():
    """KOFI_URL is a plain https Ko-fi page address, and never the
    placeholder the branch carried before the owner sent her page."""
    assert re.fullmatch(r"https://ko-fi\.com/[A-Za-z0-9_]+", site.KOFI_URL)
    assert "placeholder" not in site.KOFI_URL.lower()
    assert site.TIP_LEAD == LEAD and site.TIP_LINK_TEXT == LINK_TEXT


def test_the_words_make_no_claim():
    for text in (site.TIP_LEAD, site.TIP_LINK_TEXT):
        low = text.lower()
        assert not [w for w in BANNED if w in low], text


def test_every_footer_and_only_the_footer_has_the_line(built_on: Path):
    assert problems(built_on, on=True) == []
    # The pages that matter are covered: home, a lake, the dogs page.
    for page in ("index.html", "dogs/index.html", "advisories/index.html"):
        assert LINE in (built_on / page).read_text(encoding="utf-8"), page
    lakes = sorted(built_on.glob("lake/*/index.html")) or sorted(
        built_on.glob("water/*/index.html")
    )
    assert lakes and LINE in lakes[0].read_text(encoding="utf-8")


def test_the_snapshot_the_app_reads_never_carries_it(built_on: Path):
    snaps = list(built_on.rglob("snapshot/*.json"))
    assert snaps
    for snap in snaps:
        assert "ko-fi" not in snap.read_text(encoding="utf-8").lower()


def test_off_no_page_has_it(tmp_path: Path):
    out = build(tmp_path, "")
    assert problems(out, on=False) == []


def test_negative_controls(tmp_path: Path):
    out = build(tmp_path, URL)
    assert problems(out, on=True) == []
    home = out / "index.html"
    dogs = out / "dogs" / "index.html"
    adv = out / "advisories" / "index.html"

    def sabotage(path: Path, old: str, new: str) -> None:
        text = path.read_text(encoding="utf-8")
        changed = text.replace(old, new, 1)
        assert changed != text
        path.write_text(changed, encoding="utf-8")

    # Moved out of the footer into the page body.
    sabotage(home, LINE, "")
    sabotage(home, "</main>", LINE + "</main>")
    # A tracking hook on the link.
    sabotage(dogs, 'rel="noopener"', 'rel="noopener" data-ga-event="tip"')
    # A Ko-fi widget script.
    widget = '<script src="https://storage.ko-fi.com/w.js"></script></body>'
    sabotage(adv, "</body>", widget)
    found = "\n".join(problems(out, on=True))
    assert "index.html: the link is in <main>, not the footer" in found
    assert "dogs/index.html: the link carries a tracking or script hook" in found
    assert "advisories/index.html: Ko-fi outside a footer link" in found


def test_the_ios_sources_never_name_ko_fi():
    """The iOS app (not yet submitted) reads snapshot/v1.json and opens the
    site in the system browser; it has no web view. A Ko-fi string in its
    sources would be a tip inside the app (App Store guideline 3.1.1)."""
    hits = []
    for path in (REPO / "ios").rglob("*"):
        if not path.is_file() or path.stat().st_size > 2_000_000:
            continue
        if path.suffix in {".png", ".jpg", ".car"}:
            continue
        text = path.read_bytes().decode("utf-8", errors="ignore").lower()
        if "ko-fi" in text or "kofi" in text:
            hits.append(str(path.relative_to(REPO)))
    assert hits == []
