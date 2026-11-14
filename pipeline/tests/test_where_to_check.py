"""The "where to check" page: a dated, factual table of sources. Each checker
has a negative control that first asserts the sabotage changed the page, then
asserts the checker fails."""

from __future__ import annotations

import datetime as dt
import html
import re
from pathlib import Path

import pytest
from paths import SAMPLE, TRAPS
from test_site import build, meta_problems, pages, text_of

from caalgae import site, where_to_check

REL = "where-to-check/index.html"
_ROW = re.compile(r"<tr id=\"[^\"]+\">(.*?)</tr>", re.S)
_MAIN = re.compile(r"<main\b.*?</main>", re.S)
_BANNED = re.compile(r"\b(?:safe|safety|endorsed|endorse|endorsement|official)\b", re.I)
# The two operators whose pages the research found differing from the state
# record. The page names neither, by any of their names or addresses.
_UNNAMED = ("big bear", "bbmwd", "rocky mountain", "rockymountainrec")


@pytest.fixture(scope="module")
def sample_site(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build(tmp_path_factory.mktemp("wtc-sample"), SAMPLE)


@pytest.fixture(scope="module")
def traps_site(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build(tmp_path_factory.mktemp("wtc-traps"), TRAPS)


def main_text(page: Path) -> str:
    return text_of_main(page.read_text(encoding="utf-8"))


def text_of_main(raw: str) -> str:
    main = _MAIN.search(raw)
    assert main
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", main.group(0))))


# -- the page and its data ----------------------------------------------------


def test_every_source_has_a_link_a_read_date_and_both_sides() -> None:
    assert len(where_to_check.SOURCES) >= 10
    for s in where_to_check.SOURCES:
        assert s.url == "" or s.url.startswith("https://"), s.name
        assert isinstance(s.read_on, dt.date), s.name
        assert s.covers.strip() and s.does_not_cover.strip(), s.name
        if s.also_url:
            assert s.also_url.startswith("https://") and s.also_label
    assert sum(s.url == "" for s in where_to_check.SOURCES) == 1  # Lake Notice


def test_as_of_is_the_newest_read_date() -> None:
    assert max(s.read_on for s in where_to_check.SOURCES) == where_to_check.AS_OF
    assert dt.date(2026, 10, 23) == where_to_check.AS_OF


def row_problems(raw: str) -> list[str]:
    """Rows of the sources table with no link or no read date."""
    problems = []
    for i, row in enumerate(_ROW.findall(raw)):
        if '<a href="' not in row:
            problems.append(f"row {i}: no link")
        if not re.search(r'<time datetime="\d{4}-\d{2}-\d{2}">[^<]+</time>', row):
            problems.append(f"row {i}: no read date")
    return problems


def test_page_has_one_row_per_source_with_link_and_read_date(sample_site: Path) -> None:
    raw = (sample_site / REL).read_text(encoding="utf-8")
    assert len(_ROW.findall(raw)) == len(where_to_check.SOURCES)
    assert row_problems(raw) == []
    for s in where_to_check.SOURCES:
        if s.url:
            assert f'<a href="{s.url}">' in raw


def test_row_checker_catches_a_row_with_no_read_date(sample_site: Path) -> None:
    raw = (sample_site / REL).read_text(encoding="utf-8")
    broken = re.sub(r"<time datetime=[^>]*>[^<]*</time>", "", raw, count=1)
    assert broken != raw  # the sabotage applied
    assert row_problems(broken) == ["row 0: no read date"]
    unlinked = re.sub(r"<a href=\"[^\"]*\">[^<]*</a>", "x", raw, count=0)
    assert unlinked != raw
    assert any("no link" in p for p in row_problems(unlinked))


def test_metadata_fits_and_is_unique(sample_site: Path) -> None:
    assert meta_problems(sample_site) == []
    raw = (sample_site / REL).read_text(encoding="utf-8")
    title = re.search(r"<title>(.*?)</title>", raw, re.S)
    desc = re.search(r'<meta name="description" content="(.*?)"', raw)
    assert title and desc
    assert len(title.group(1)) <= 60 and len(desc.group(1)) <= 155
    assert raw.count("<h1>") == 1
    assert (
        f'<link rel="canonical" href="{site.DEFAULT_BASE_URL}where-to-check/">' in raw
    )
    assert 'name="robots"' not in raw


def test_title_checker_catches_a_title_over_60(
    sample_site: Path, tmp_path: Path
) -> None:
    root = tmp_path / "copy"
    import shutil

    shutil.copytree(sample_site, root)
    page = root / REL
    raw = page.read_text(encoding="utf-8")
    long_title = raw.replace(
        "<title>",
        "<title>Where to check a California algae advisory and everything "
        "else you might want to know ",
        1,
    )
    assert long_title != raw
    page.write_text(long_title, encoding="utf-8")
    assert any("title is" in p for p in meta_problems(root))
    dup = root / "about" / "index.html"
    about = dup.read_text(encoding="utf-8")
    page.write_text(raw, encoding="utf-8")
    title = re.search(r"<title>(.*?)</title>", raw, re.S)
    assert title
    swapped = re.sub(
        r"<title>.*?</title>", f"<title>{title.group(1)}</title>", about, flags=re.S
    )
    assert swapped != about
    dup.write_text(swapped, encoding="utf-8")
    assert any("title shared" in p for p in meta_problems(root))


# -- not an orphan ------------------------------------------------------------


def inbound(root: Path, rel_dir: str) -> list[str]:
    """Pages that link to ``rel_dir`` (a directory such as ``where-to-check/``)."""
    found = []
    for page in pages(root):
        if page == root / rel_dir / "index.html":
            continue
        for href in re.findall(r'href="([^"#]+)', page.read_text(encoding="utf-8")):
            if href.startswith("http"):
                continue
            target = (page.parent / href).resolve()
            if target == (root / rel_dir).resolve():
                found.append(str(page.relative_to(root)))
                break
    return found


def test_linked_from_home_and_about(sample_site: Path) -> None:
    links = inbound(sample_site, "where-to-check")
    assert "index.html" in links and "about/index.html" in links


def test_orphan_check_catches_an_unlinked_page(
    sample_site: Path, tmp_path: Path
) -> None:
    import shutil

    root = tmp_path / "copy"
    shutil.copytree(sample_site, root)
    # Home, about, and any water page whose swimming section names a
    # where-to-check source (DECISIONS 0033).
    linking = inbound(sample_site, "where-to-check")
    assert {"index.html", "about/index.html"} <= set(linking)
    for rel in linking:
        page = root / rel
        raw = page.read_text(encoding="utf-8")
        stripped = raw.replace("where-to-check/", "gone/")
        assert stripped != raw  # the sabotage applied
        page.write_text(stripped, encoding="utf-8")
    assert inbound(root, "where-to-check") == []


# -- sitemap ------------------------------------------------------------------


_ENTRY = re.compile(r"<url><loc>([^<]+)</loc>(?:<lastmod>([^<]+)</lastmod>)?</url>")


@pytest.mark.parametrize("which", ["sample_site", "traps_site"])
def test_sitemap_lists_the_page_with_its_own_data_date(
    which: str, request: pytest.FixtureRequest
) -> None:
    root: Path = request.getfixturevalue(which)
    got = dict(_ENTRY.findall((root / "sitemap.xml").read_text()))
    # The fixtures' run date is 2026-10-12; the page's date is its own.
    assert got[site.DEFAULT_BASE_URL + "where-to-check/"] == "2026-10-23"


def test_lastmod_is_independent_of_the_run_date_and_the_clock(tmp_path: Path) -> None:
    out = tmp_path / "a"
    snap = __import__("json").loads(
        (build(tmp_path / "src", SAMPLE) / "snapshot" / "v1.json").read_text()
    )
    snap["run_date"] = "2027-03-01"
    site.build_site(snap, out)
    got = dict(_ENTRY.findall((out / "sitemap.xml").read_text()))
    assert got[site.DEFAULT_BASE_URL + "where-to-check/"] == "2026-10-23"


# -- wording ------------------------------------------------------------------


def banned(raw: str) -> list[str]:
    return _BANNED.findall(text_of_main(raw))


def test_page_never_says_safe_or_endorsed(sample_site: Path) -> None:
    raw = (sample_site / REL).read_text(encoding="utf-8")
    assert banned(raw) == []
    assert "a water not listed may still have an advisory" in text_of_main(raw)


def test_banned_phrase_check_catches_safe_and_endorsed(sample_site: Path) -> None:
    raw = (sample_site / REL).read_text(encoding="utf-8")
    for word in ("safe", "endorsed"):
        sabotaged = raw.replace(
            '<h2 id="more">', f'<p>This lake is {word}.</p><h2 id="more">', 1
        )
        assert sabotaged != raw
        assert banned(sabotaged) == [word]


def test_page_says_it_is_a_dated_snapshot_and_sources_change(sample_site: Path) -> None:
    text = main_text(sample_site / REL)
    assert "dated snapshot" in text
    assert "pages change" in text
    assert "Oct 23, 2026" in text


def conflicting_names(raw: str) -> list[str]:
    low = raw.lower()
    return [n for n in _UNNAMED if n in low]


def test_page_names_neither_conflicting_operator(sample_site: Path) -> None:
    raw = (sample_site / REL).read_text(encoding="utf-8")
    assert conflicting_names(raw) == []


def test_operator_check_catches_a_named_operator(sample_site: Path) -> None:
    raw = (sample_site / REL).read_text(encoding="utf-8")
    sabotaged = raw.replace(
        '<h2 id="more">', '<p>Big Bear Municipal Water District</p><h2 id="more">', 1
    )
    assert sabotaged != raw
    assert conflicting_names(sabotaged) == ["big bear"]
    sabotaged = raw.replace(
        '<h2 id="more">', '<p>rockymountainrec.com</p><h2 id="more">', 1
    )
    assert sabotaged != raw
    assert "rockymountainrec" in conflicting_names(sabotaged)


def test_no_sponsor_affiliate_or_agency_marks(sample_site: Path) -> None:
    raw = (sample_site / REL).read_text(encoding="utf-8").lower()
    main = _MAIN.search(raw)
    assert main
    for needle in ("amazon", "sponsor", 'rel="sponsored', "<img", "seal"):
        assert needle not in main.group(0), needle


def test_every_source_url_is_in_the_research_log() -> None:
    # Guard against a stray URL: the hosts the research checked.
    # mywaterquality.ca.gov's robots.txt allows only Googlebot, so it is read
    # by hand in a browser, never by the pipeline or an agent.
    hosts = {
        "www.waterboards.ca.gov", "mywaterquality.ca.gov", "data.ca.gov",
        "emd.saccounty.gov", "ehs.sbcounty.gov", "www.ebparks.org",
        "www.bvrancheria.com", "mywatersheds.com", "www.epa.gov",
        "www.theswimguide.org",
    }  # fmt: skip
    for s in where_to_check.SOURCES:
        for url in (s.url, s.also_url):
            if url:
                assert url.split("/")[2] in hosts, url


# -- the headline note ----------------------------------------------------------


def test_headline_note_appears_only_with_several_advisory_spots(
    sample_site: Path,
) -> None:
    import json

    snap = json.loads((sample_site / "snapshot" / "v1.json").read_text())
    many = [
        w for w in snap["waterbodies"] if w["status"].get("sites_with_advisory", 0) > 1
    ]
    one = [
        w for w in snap["waterbodies"]
        if w["status"]["kind"] == "advisory" and w["status"].get("sites_with_advisory") == 1
    ]  # fmt: skip
    assert many and one
    note = (
        "The headline shows the highest level posted in the 12 months before "
        "the state's data, or the newest posting if none was."
    )
    for w in many:
        assert note in text_of(sample_site / "water" / w["id"] / "index.html")
    for w in one:
        assert note not in text_of(sample_site / "water" / w["id"] / "index.html")
    assert "the level shown is the highest posted in the 12 months" in text_of(
        sample_site / "advisories" / "index.html"
    )
