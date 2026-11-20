"""Accessibility rules the axe and pa11y gates cannot see (the ACR,
docs/accessibility/ACR.md).

Tables: every table on every built page sits in a scroll region that a
keyboard can focus and that is named by the table's own caption, and no
stylesheet rule turns a table into a block. Below 40rem the stylesheet used
to set ``table { display: block; overflow-x: auto }``: that drops the row and
column semantics in some screen readers (SC 1.3.1), and a scrolling table
with no link in it, such as a water's history, could not be scrolled from a
keyboard in a browser that does not focus scroll containers (SC 2.1.1).
axe scans at 1280px, where nothing scrolls, so it never saw either.

HTML is read with html.parser, never a regex; each guard has a negative
control that first asserts its sabotage applied.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

import pytest
from paths import CYAN_CACHE, FIXTURES, MO_POINTS, PAGE, TRAPS

from caalgae import cli

STYLE = Path(cli.__file__).parent / "templates" / "style.css"


def build(tmp_path: Path) -> Path:
    """California, Missouri, CyAN and New York history: every template that
    draws a table."""
    out = tmp_path / "site"
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
                "--ny-history", "on",
                "--ny-cache", str(FIXTURES / "ny"),
            ]
        )
        == 0
    )  # fmt: skip
    return out


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build(tmp_path_factory.mktemp("a11y"))


class _Tables(HTMLParser):
    """Each table's nearest enclosing element, and each caption's id."""

    def __init__(self) -> None:
        super().__init__()
        self.stack: list[dict[str, str | None]] = []
        self.tables: list[tuple[dict[str, str | None], str | None]] = []
        self.ids: list[str] = []
        self._in_table = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        if a.get("id"):
            self.ids.append(str(a["id"]))
        if tag == "table":
            parent = self.stack[-1] if self.stack else {}
            self.tables.append((parent, None))
        if tag == "caption" and self.tables:
            parent, _ = self.tables[-1]
            self.tables[-1] = (parent, a.get("id"))
        if tag not in {"br", "meta", "link", "img", "input", "hr"}:
            self.stack.append({"tag": tag, **a})

    def handle_endtag(self, tag: str) -> None:
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i]["tag"] == tag:
                del self.stack[i:]
                break


def table_region_problems(page: str) -> list[str]:
    parser = _Tables()
    parser.feed(page)
    problems: list[str] = []
    for n, (parent, caption_id) in enumerate(parser.tables, 1):
        where = f"table {n}"
        if parent.get("tag") != "div" or "table-scroll" not in (
            parent.get("class") or ""
        ):
            problems.append(f"{where} is not inside a div.table-scroll")
            continue
        if parent.get("role") != "region":
            problems.append(f"{where}: its scroll box is not a named region")
        if parent.get("tabindex") != "0":
            problems.append(f"{where}: its scroll box cannot take keyboard focus")
        if not caption_id:
            problems.append(f"{where}: its caption has no id")
        elif parent.get("aria-labelledby") != caption_id:
            problems.append(
                f"{where}: region named by {parent.get('aria-labelledby')}, not its caption"
            )
        elif parser.ids.count(caption_id) != 1:
            problems.append(
                f"{where}: caption id {caption_id} is not unique on the page"
            )
    return problems


def test_every_table_is_in_a_named_focusable_scroll_region(built: Path) -> None:
    seen = 0
    for page in sorted(built.rglob("*.html")):
        text = page.read_text(encoding="utf-8")
        seen += text.count("<table")
        assert table_region_problems(text) == [], page.relative_to(built)
    # Home, advisories, county list, a county, the states, every water page
    # and New York history all draw tables, so a build with few is broken.
    assert seen > 50


def test_each_template_with_a_table_was_built(built: Path) -> None:
    for rel in [
        "index.html", "advisories/index.html", "county/index.html",
        "county/alameda/index.html", "state/ca/index.html", "state/mo/index.html",
        "state/ny/index.html", "where-to-check/index.html",
    ]:  # fmt: skip
        assert "<table" in (built / rel).read_text(encoding="utf-8"), rel
    ny_water = next(p for p in (built / "state" / "ny").glob("*/index.html"))
    assert "<table" in ny_water.read_text(encoding="utf-8")
    assert any("satellite-table-caption" in p.read_text(encoding="utf-8")
               for p in (built / "water").glob("*/index.html"))  # fmt: skip


@pytest.mark.parametrize(
    ("old", "new", "expect"),
    [
        ('<div class="table-scroll" role="region"', '<div class="other" role="region"', "not inside"),
        ('role="region" aria-labelledby', 'aria-labelledby', "not a named region"),
        (' tabindex="0">', ">", "cannot take keyboard focus"),
        ('<caption id="history-table-caption"', '<caption id="spots-table-caption"', "not its caption"),
    ],
)  # fmt: skip
def test_table_guard_catches_each_sabotage(
    built: Path, old: str, new: str, expect: str
) -> None:
    page = next(
        p.read_text(encoding="utf-8")
        for p in sorted((built / "water").glob("*/index.html"))
        if "history-table-caption" in p.read_text(encoding="utf-8")
    )
    broken = page.replace(old, new, 1)
    assert broken != page, "the sabotage did not apply"
    assert any(expect in p for p in table_region_problems(broken))


def _rules(css: str) -> list[tuple[str, str]]:
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    return [
        (sel.strip(), body) for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css)
    ]


def stylesheet_problems(css: str) -> list[str]:
    problems: list[str] = []
    for selector, body in _rules(css):
        names = [s.strip() for s in selector.split(",")]
        if "table" in names and re.search(r"display\s*:\s*block", body):
            problems.append("a rule turns tables into blocks")
    scroll = [b for s, b in _rules(css) if s == ".table-scroll"]
    if not scroll or not re.search(r"overflow-x\s*:\s*auto", scroll[0]):
        problems.append(".table-scroll does not scroll sideways")
    focus = [b for s, b in _rules(css) if ".table-scroll:focus-visible" in s]
    if not focus or not re.search(r"outline\s*:\s*[2-9]px solid", focus[0]):
        problems.append("a focused table region draws no outline")
    return problems


def test_stylesheet_keeps_tables_as_tables_and_shows_region_focus() -> None:
    assert stylesheet_problems(STYLE.read_text(encoding="utf-8")) == []


def test_stylesheet_guard_catches_a_block_table() -> None:
    css = STYLE.read_text(encoding="utf-8")
    broken = (
        css
        + "\n@media (max-width: 40rem) { table { display: block; overflow-x: auto; } }\n"
    )
    assert "a rule turns tables into blocks" in stylesheet_problems(broken)
    unfocused = css.replace(".table-scroll:focus-visible", ".nothing:focus-visible")
    assert unfocused != css, "the sabotage did not apply"
    assert "a focused table region draws no outline" in stylesheet_problems(unfocused)
