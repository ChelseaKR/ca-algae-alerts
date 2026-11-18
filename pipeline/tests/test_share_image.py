"""The share image: the picture a link preview shows (docs/DESIGN.md).

One image for every page: the sign-board mark and the site's name, and
nothing else. It never shows a level, a lake or a status, because a preview
is read without the page and its dates. Its alt text is the site's name.

Pages are read with html.parser, never a regular expression over markup.
Each check has a control that proves it can fail.
"""

from __future__ import annotations

from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.robotparser import RobotFileParser

import pytest
from paths import PAGE, SAMPLE
from pngfile import Pixel, png_pixels, png_size

from caalgae import cli, site

TEMPLATES = Path(__file__).resolve().parents[1] / "src/caalgae/templates"
IMAGE_URL = site.DEFAULT_BASE_URL + "assets/og-image.png"
# The mark's colors (templates/mark.svg) and the page's paper (style.css).
SQUARE = (0x26, 0x2A, 0x6B)
PAPER = (0xFB, 0xFA, 0xF6)
BAND = (0x8F, 0x95, 0xE8)
# What every page must say about the image, tag by tag.
EXPECTED = {
    "og:image": IMAGE_URL,
    "og:image:type": "image/png",
    "og:image:width": "1200",
    "og:image:height": "630",
    "og:image:alt": "Lake Notice",
    "twitter:card": "summary_large_image",
    "twitter:image": IMAGE_URL,
    "twitter:image:alt": "Lake Notice",
}


@pytest.fixture(scope="module")
def site_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    tmp = tmp_path_factory.mktemp("share")
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


@pytest.fixture(scope="module")
def pixels() -> list[list[Pixel]]:
    return png_pixels((TEMPLATES / site.SHARE_IMAGE_FILE).read_bytes())


class _Meta(HTMLParser):
    """Every <meta> with a property or a name, as (key, content) pairs."""

    def __init__(self) -> None:
        super().__init__()
        self.found: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "meta":
            return
        got = {name: value or "" for name, value in attrs}
        key = got.get("property") or got.get("name")
        if key:
            self.found.append((key, got.get("content", "")))


def share_tags(html: str) -> list[tuple[str, str]]:
    parser = _Meta()
    parser.feed(html)
    return [
        (key, value)
        for key, value in parser.found
        if key.startswith(("og:image", "twitter:image")) or key == "twitter:card"
    ]


def tag_problems(html: str) -> list[str]:
    """What is wrong with one page's share-image tags; empty when nothing."""
    tags = share_tags(html)
    problems = [
        f"{key} appears {n} times"
        for key, n in Counter(k for k, _ in tags).items()
        if n > 1
    ]
    found = dict(tags)
    for key, value in EXPECTED.items():
        if found.get(key) != value:
            problems.append(f"{key} is {found.get(key)!r}, not {value!r}")
    problems += [f"unexpected tag {key}" for key in found if key not in EXPECTED]
    return problems


def is_cool(pixel: Pixel) -> bool:
    """True for paper, indigo, the band's periwinkle and any blend of them:
    red and green never run ahead of blue. A posted sign's yellow, orange or
    red, and any green, fail this."""
    r, g, b, _ = pixel
    return r - b <= 8 and g - b <= 8


def test_the_image_is_1200_by_630_and_ships_unchanged(site_root: Path) -> None:
    packaged = (TEMPLATES / site.SHARE_IMAGE_FILE).read_bytes()
    assert png_size(packaged) == (1200, 630) == site.SHARE_IMAGE_SIZE
    assert (site_root / "assets" / site.SHARE_IMAGE_FILE).read_bytes() == packaged


def test_every_page_names_the_image_its_size_and_only_the_sites_name(
    site_root: Path,
) -> None:
    pages = sorted(site_root.rglob("*.html"))
    assert len(pages) > 10
    for page in pages:
        assert tag_problems(page.read_text(encoding="utf-8")) == [], page


def test_the_alt_text_is_the_sites_name_and_nothing_else() -> None:
    assert EXPECTED["og:image:alt"] == site.SITE_NAME == EXPECTED["twitter:image:alt"]


def test_the_image_is_paper_with_the_mark_in_the_middle(
    pixels: list[list[Pixel]],
) -> None:
    for x, y in ((0, 0), (1199, 0), (0, 629), (1199, 629), (100, 315), (1100, 315)):
        assert pixels[y][x][:3] == PAPER, (x, y)
    # The mark sits at (470, 96), 260 px square, on the same 32-unit grid as
    # mark.svg: its square, the board's paper and the band across its top.
    scale = 260 / 32
    for (gx, gy), color in {
        (3.0, 20.0): SQUARE,
        (24.0, 10.5): PAPER,
        (16.0, 6.0): BAND,
    }.items():
        assert pixels[int(96 + gy * scale)][int(470 + gx * scale)][:3] == color, (
            gx,
            gy,
        )


def test_the_name_is_set_in_the_brand_indigo_under_the_mark(
    pixels: list[list[Pixel]],
) -> None:
    band = [pixel[:3] for row in pixels[420:510] for pixel in row]
    ink = sum(1 for pixel in band if pixel == SQUARE)
    assert 0.08 < ink / len(band) < 0.35, "letters, not a block and not blank"
    # Nothing is written above the mark, beside it or under the name.
    for rows in (pixels[:90], pixels[540:]):
        assert all(pixel[:3] == PAPER for row in rows for pixel in row)


def test_no_pixel_is_a_sign_color_or_green(pixels: list[list[Pixel]]) -> None:
    assert all(is_cool(pixel) for row in pixels for pixel in row)


def test_robots_txt_lets_a_crawler_fetch_the_image(site_root: Path) -> None:
    robots = RobotFileParser()
    robots.parse((site_root / "robots.txt").read_text(encoding="utf-8").splitlines())
    for agent in ("Googlebot-Image", "facebookexternalhit", "Twitterbot"):
        assert robots.can_fetch(agent, IMAGE_URL), agent


# -- controls: each check can fail -----------------------------------------


def test_control_the_old_small_card_and_a_wordy_alt_are_reported(
    site_root: Path,
) -> None:
    home = (site_root / "index.html").read_text(encoding="utf-8")
    small = home.replace("summary_large_image", "summary")
    assert small != home
    assert tag_problems(small) == [
        "twitter:card is 'summary', not 'summary_large_image'"
    ]
    wordy = home.replace(
        '<meta property="og:image:alt" content="Lake Notice">',
        '<meta property="og:image:alt" content="Lake Notice: toxic algae advisories">',
    )
    assert wordy != home
    assert tag_problems(wordy) == [
        "og:image:alt is 'Lake Notice: toxic algae advisories', not 'Lake Notice'"
    ]


def test_control_a_page_with_no_image_tags_is_reported() -> None:
    assert len(tag_problems("<html><head><title>x</title></head></html>")) == len(
        EXPECTED
    )


def test_control_the_sign_colors_and_green_fail_the_color_check() -> None:
    for sign in (
        (0xF6, 0xC8, 0x00),
        (0xE6, 0x6A, 0x00),
        (0xB5, 0x12, 0x1B),
        (0x1F, 0x8A, 0x3B),
    ):
        assert not is_cool((*sign, 255)), sign
    for own in (SQUARE, PAPER, BAND):
        assert is_cool((*own, 255))
