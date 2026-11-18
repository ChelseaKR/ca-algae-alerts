"""The site icon as files a search engine can show (docs/DESIGN.md, Mark).

Google Search shows a site's icon only from a crawlable file in a raster
format, square, at a multiple of 48 px. The SVG mark alone does not
qualify, so the same mark ships as PNG at 48, 96 and 192 px, linked from
every page, plus /favicon.ico for clients that ask for it unprompted.

Pages are read with html.parser, never a regular expression over markup.
Each check has a control that proves it can fail.
"""

from __future__ import annotations

import struct
from html.parser import HTMLParser
from pathlib import Path
from urllib.robotparser import RobotFileParser

import pytest
from paths import PAGE, SAMPLE
from pngfile import png_pixels, png_size

from caalgae import cli, site

TEMPLATES = Path(__file__).resolve().parents[1] / "src/caalgae/templates"
# The mark's own colors (templates/mark.svg), and where each one sits on its
# 32-unit grid: the square, the board's paper, the band across its top.
SQUARE = (0x26, 0x2A, 0x6B)
PAPER = (0xFB, 0xFA, 0xF6)
BAND = (0x8F, 0x95, 0xE8)
SPOTS = {(3.0, 20.0): SQUARE, (24.0, 10.5): PAPER, (16.0, 6.0): BAND}


@pytest.fixture(scope="module")
def site_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    tmp = tmp_path_factory.mktemp("icons")
    out = tmp / "site"
    assert (
        cli.main(
            [
                "--fixture-page", str(PAGE),
                "--fixture-csv", str(SAMPLE),
                "--run-today", "2026-10-12",
                "--history", str(tmp / "history.json"),
                "--site-out", str(out),
            ]
        )
        == 0
    )  # fmt: skip
    return out


class _Icons(HTMLParser):
    """Every <link rel="icon"> in a page, as its attributes."""

    def __init__(self) -> None:
        super().__init__()
        self.icons: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        found = {name: value or "" for name, value in attrs}
        if tag == "link" and found.get("rel") == "icon":
            self.icons.append(found)


def icons_of(html: str) -> list[dict[str, str]]:
    parser = _Icons()
    parser.feed(html)
    return parser.icons


def icon_problems(page: Path, root: Path) -> list[str]:
    """What is wrong with one built page's icon links; empty when nothing."""
    problems = []
    icons = icons_of(page.read_text(encoding="utf-8"))
    pngs = {i.get("sizes", ""): i for i in icons if i.get("type") == "image/png"}
    for size in site.ICON_PNG_SIZES:
        link = pngs.get(f"{size}x{size}")
        if link is None:
            problems.append(f"no {size} px PNG icon link")
            continue
        href = link["href"]
        if href.startswith("https://"):  # the 404 page links absolutely
            target = root / href.removeprefix(site.DEFAULT_BASE_URL)
        else:
            target = (page.parent / href).resolve()
        if not target.is_file():
            problems.append(f"{href} is not a file in the build")
        elif png_size(target.read_bytes()) != (size, size):
            problems.append(f"{href} is not {size} px square")
    if not any(i.get("type") == "image/svg+xml" for i in icons):
        problems.append("the SVG icon link is gone")
    return problems


def test_the_png_icons_are_square_multiples_of_48_and_ship_unchanged(
    site_root: Path,
) -> None:
    assert site.ICON_PNG_SIZES == (48, 96, 192)
    for size in site.ICON_PNG_SIZES:
        assert size % 48 == 0
        packaged = (TEMPLATES / f"icon-{size}.png").read_bytes()
        assert png_size(packaged) == (size, size)
        built = site_root / "assets" / f"icon-{size}.png"
        assert built.read_bytes() == packaged, "the build must copy, not redraw"


@pytest.mark.parametrize("size", site.ICON_PNG_SIZES)
def test_each_icon_is_the_mark_in_its_own_colors(size: int) -> None:
    pixels = png_pixels((TEMPLATES / f"icon-{size}.png").read_bytes())
    scale = size / 32
    for (x, y), color in SPOTS.items():
        assert pixels[int(y * scale)][int(x * scale)] == (*color, 255), (x, y)
    # The square's corners are rounded, so the very corner is clear.
    assert pixels[0][0][3] == 0
    # The mark's own file still has those colors: the icons were made from it.
    mark = (TEMPLATES / "mark.svg").read_text(encoding="utf-8")
    for color in (SQUARE, PAPER, BAND):
        assert "#{:02x}{:02x}{:02x}".format(*color) in mark


def test_every_page_links_the_three_png_icons_and_each_file_exists(
    site_root: Path,
) -> None:
    pages = sorted(site_root.rglob("*.html"))
    assert len(pages) > 10
    for page in pages:
        assert icon_problems(page, site_root) == [], page


def test_favicon_ico_sits_at_the_site_root_with_the_mark_at_16_32_and_48(
    site_root: Path,
) -> None:
    data = (site_root / "favicon.ico").read_bytes()
    assert data == (TEMPLATES / "favicon.ico").read_bytes()
    reserved, kind, count = struct.unpack("<HHH", data[:6])
    assert (reserved, kind, count) == (0, 1, 3)
    sizes = []
    for n in range(count):
        entry = data[6 + 16 * n : 22 + 16 * n]
        width, height, _, _, _, bits, length, offset = struct.unpack("<BBBBHHII", entry)
        image = data[offset : offset + length]
        assert png_size(image) == (width, height)
        assert bits == 32
        sizes.append(width)
    assert sizes == [16, 32, 48]


def test_robots_txt_lets_an_image_crawler_fetch_the_icons(site_root: Path) -> None:
    robots = RobotFileParser()
    robots.parse((site_root / "robots.txt").read_text(encoding="utf-8").splitlines())
    for path in ("favicon.ico", *(f"assets/icon-{s}.png" for s in site.ICON_PNG_SIZES)):
        for agent in ("Googlebot-Image", "Googlebot", "bingbot"):
            assert robots.can_fetch(agent, site.DEFAULT_BASE_URL + path), (agent, path)


def test_the_link_tags_add_no_word_a_reader_sees(site_root: Path) -> None:
    for icon in icons_of((site_root / "index.html").read_text(encoding="utf-8")):
        assert set(icon) <= {"rel", "href", "type", "sizes"}, icon


# -- controls: each check can fail -----------------------------------------


def test_control_a_page_without_the_png_links_is_reported(
    site_root: Path, tmp_path: Path
) -> None:
    home = (site_root / "index.html").read_text(encoding="utf-8")
    kept = [
        line
        for line in home.splitlines()
        if not ('rel="icon"' in line and "image/png" in line)
    ]
    assert len(kept) == len(home.splitlines()) - 3  # the sabotage applied
    page = tmp_path / "index.html"
    page.write_text("\n".join(kept), encoding="utf-8")
    assert icon_problems(page, site_root) == [
        "no 48 px PNG icon link",
        "no 96 px PNG icon link",
        "no 192 px PNG icon link",
    ]


def test_control_a_link_to_a_missing_or_wrong_sized_file_is_reported(
    site_root: Path, tmp_path: Path
) -> None:
    copy = tmp_path / "site"
    (copy / "assets").mkdir(parents=True)
    (copy / "index.html").write_text(
        (site_root / "index.html").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (copy / "assets" / "icon-48.png").write_bytes(
        (site_root / "assets" / "icon-96.png").read_bytes()
    )
    (copy / "assets" / "icon-96.png").write_bytes(
        (site_root / "assets" / "icon-96.png").read_bytes()
    )
    assert icon_problems(copy / "index.html", copy) == [
        "./assets/icon-48.png is not 48 px square",
        "./assets/icon-192.png is not a file in the build",
    ]


def test_control_a_recolored_icon_is_not_the_mark() -> None:
    pixels = png_pixels((TEMPLATES / "icon-48.png").read_bytes())
    assert pixels[30][4] == (*SQUARE, 255)
    assert pixels[30][4] != (*PAPER, 255)


def test_control_a_robots_file_that_blocks_assets_fails_the_crawl_check() -> None:
    robots = RobotFileParser()
    robots.parse(["User-agent: *", "Disallow: /assets/"])
    assert not robots.can_fetch(
        "Googlebot-Image", site.DEFAULT_BASE_URL + "assets/icon-48.png"
    )
