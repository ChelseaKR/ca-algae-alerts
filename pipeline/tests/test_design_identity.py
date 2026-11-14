"""The visual identity's safety rules (docs/DESIGN.md).

Advisory levels must stay unmistakable in color and in words, in light and
dark, and color must never be the only signal. Nothing that is not an
advisory may take a sign color, and no color on the site may be green, so
no color ever reads as "safe". Each check has a negative control that
proves it can fail.
"""

from __future__ import annotations

import colorsys
import re
from pathlib import Path

import pytest
from paths import PAGE, SAMPLE

from caalgae import cli

CSS_PATH = Path(__file__).resolve().parents[1] / "src/caalgae/templates/style.css"
CSS = CSS_PATH.read_text(encoding="utf-8")

TIERS = ("caution", "warning", "danger", "other_advisory")
RANKS = {"caution": 1, "warning": 2, "danger": 3}
# The CSS token name for each tier's band and band text.
TOKEN = {
    "caution": "caution",
    "warning": "warning",
    "danger": "danger",
    "other_advisory": "other",
}
# The fixture waters, one per kind of record (responses-sample_2026-10-09.csv).
PAGES = {
    "danger": "ca-alameda-lake-temescal",
    "warning": "ca-los-angeles-pyramid-lake",
    "caution": "ca-napa-lake-berryessa",
    "no_advisory_recorded": "ca-contra-costa-lake-anza",
    "undetermined": "ca-el-dorado-folsom-lake",
}
_STATUS = re.compile(
    r'<div class="status (status-[a-z_]+)([^"]*)">(.*?)<div class="sign-body">', re.S
)
_VAR = re.compile(r"(--[a-z0-9-]+):\s*(#[0-9a-fA-F]{6})\s*;")


@pytest.fixture(scope="module")
def site_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    tmp = tmp_path_factory.mktemp("design")
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


def status_box(root: Path, water_id: str) -> tuple[str, str, str]:
    page = (root / "water" / water_id / "index.html").read_text(encoding="utf-8")
    m = _STATUS.search(page)
    assert m, water_id
    return m.group(1), m.group(2).strip(), m.group(3)


# --- Colors ------------------------------------------------------------


def palettes(css: str) -> dict[str, dict[str, str]]:
    """The light tokens (the first :root) and the dark ones (the :root inside
    the prefers-color-scheme: dark block)."""
    light_block = css.split("@media (prefers-color-scheme: dark)")[0]
    dark_block = css.split("@media (prefers-color-scheme: dark)")[1].split("\n}\n")[0]
    return {
        "light": dict(_VAR.findall(light_block)),
        "dark": dict(_VAR.findall(dark_block)),
    }


def luminance(hex_color: str) -> float:
    def ch(c: int) -> float:
        s = c / 255
        return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4

    r, g, b = (int(hex_color[i : i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a: str, b: str) -> float:
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def is_green(hex_color: str) -> bool:
    r, g, b = (int(hex_color[i : i + 2], 16) / 255 for i in (1, 3, 5))
    hue, light, sat = colorsys.rgb_to_hls(r, g, b)
    return 75 <= hue * 360 <= 170 and sat > 0.2 and 0.1 < light < 0.95


def level_failures(scheme: str, v: dict[str, str]) -> list[str]:
    found = [
        f"{scheme} {t}: band text {r:.2f}:1"
        for t in TIERS
        if (r := contrast(v[f"--{TOKEN[t]}-ink"], v[f"--{TOKEN[t]}-band"])) < 4.5
    ]
    bands = [v[f"--{t}-band"] for t in ("caution", "warning", "danger")]
    if len(set(bands)) != 3:
        found.append(f"{scheme}: the three levels share a band color")
    # Caution and danger must be far apart even in grayscale.
    if contrast(v["--caution-band"], v["--danger-band"]) < 3:
        found.append(f"{scheme}: caution and danger too close in lightness")
    if v["--record-band"] in bands or v["--other-band"] in bands:
        found.append(f"{scheme}: a non-level record shares a level's color")
    return found


def text_failures(scheme: str, v: dict[str, str]) -> list[str]:
    found = [
        f"{scheme} {fg} on {bg}: {r:.2f}:1"
        for fg in ("--ink", "--muted", "--link", "--link-visited")
        for bg in ("--paper", "--surface", "--wash", "--row-alt")
        if (r := contrast(v[fg], v[bg])) < 4.5
    ]
    if contrast(v["--focus"], v["--paper"]) < 3:
        found.append(f"{scheme}: focus ring under 3:1")
    return found


def color_failures(css: str) -> list[str]:
    found: list[str] = []
    for scheme, v in palettes(css).items():
        found += level_failures(scheme, v) + text_failures(scheme, v)
        found += [f"{scheme} {n} is green ({c})" for n, c in v.items() if is_green(c)]
    return found


def test_level_colors_are_distinct_readable_and_never_green() -> None:
    assert palettes(CSS)["light"] and palettes(CSS)["dark"]
    assert color_failures(CSS) == []


def test_color_check_can_fail() -> None:
    """Negative controls: each sabotage must be caught."""
    low = CSS.replace("--danger-ink: #ffffff;", "--danger-ink: #c03030;", 1)
    assert any("danger: band text" in f for f in color_failures(low))
    same = CSS.replace("--warning-band: #e66a00;", "--warning-band: #b5121b;", 1)
    assert any("share a band color" in f for f in color_failures(same))
    green = CSS.replace("--brand: #262a6b;", "--brand: #1f7a3a;", 1)
    assert any("is green" in f for f in color_failures(green))
    dim = CSS.replace("--muted: #4a4e66;", "--muted: #a0a0a0;", 1)
    assert any("--muted on" in f for f in color_failures(dim))


def test_every_level_rule_exists_for_band_and_table_chip() -> None:
    for t in TIERS:
        assert f".tier-{t} .sign-band {{ background: var(--{TOKEN[t]}-band)" in CSS
        assert f".level.tier-{t}::before {{ background: var(--{TOKEN[t]}-band)" in CSS


def test_no_stylesheet_asks_another_server() -> None:
    assert "http://" not in CSS.replace("http://www.w3.org/2000/svg", "")
    assert "https://" not in CSS
    assert "@import" not in CSS and "@font-face" not in CSS


# --- Words and marks ---------------------------------------------------


@pytest.mark.parametrize("tier", ["caution", "warning", "danger"])
def test_advisory_band_carries_the_level_in_words_and_marks(
    site_root: Path, tier: str
) -> None:
    kind, classes, band = status_box(site_root, PAGES[tier])
    assert kind == "status-advisory"
    assert classes == f"tier-{tier}"
    assert 'aria-hidden="true"' in band
    word = re.search(r'<span class="sign-word">([^<]+)</span>', band)
    assert word and word.group(1) == f"{tier.capitalize()} advisory"
    assert band.count('class="on"') == RANKS[tier]
    assert len(re.findall(r'<span( class="on")?></span>', band)) == 3


@pytest.mark.parametrize("kind", ["no_advisory_recorded", "undetermined"])
def test_a_record_that_is_not_an_advisory_gets_no_level_look(
    site_root: Path, kind: str
) -> None:
    got_kind, classes, band = status_box(site_root, PAGES[kind])
    assert got_kind == f"status-{kind}"
    assert classes == ""
    word = re.search(r'<span class="sign-word">([^<]+)</span>', band)
    assert word and word.group(1) == "Latest state record"
    assert "sign-pips" not in band
    lowered = band.lower()
    for never in ("safe", "clear", "open", "ok"):
        assert never not in re.sub(r"<[^>]+>", " ", lowered).split(), never


def test_table_rows_carry_the_level_class(site_root: Path) -> None:
    page = (site_root / "advisories" / "index.html").read_text(encoding="utf-8")
    cells = re.findall(r'<td class="level([^"]*)">([^<]+)', page)
    assert cells
    for classes, text in cells:
        tier = classes.strip().removeprefix("tier-")
        if tier in RANKS:
            assert text.startswith(f"{tier.capitalize()} advisory")


def test_every_page_has_the_mark_and_the_favicon_ships(site_root: Path) -> None:
    assert (
        (site_root / "assets" / "mark.svg")
        .read_text(encoding="utf-8")
        .startswith("<svg")
    )
    for page in sorted(site_root.rglob("*.html")):
        text = page.read_text(encoding="utf-8")
        assert 'assets/mark.svg" type="image/svg+xml"' in text, page
        assert '<svg class="mark" viewBox="0 0 32 32" aria-hidden="true"' in text, page
        assert '<span class="wordmark">Lake Notice</span>' in text, page
