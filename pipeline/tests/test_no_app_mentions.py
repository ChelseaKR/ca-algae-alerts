"""No generated file mentions an app (DECISIONS 0046, 2026-11-21).

The owner dropped the iPhone app on 2026-11-17: Lake Notice is a website
only. The about page's "A paid iPhone app is in development", the support
page's "The Lake Notice iPhone app is not released yet", the privacy page's
app section and app sentences, and the App Store switch's water-page and
llms.txt lines are gone. The about and support pages answer "Is there an
app?" in the approved words, and the privacy page covers the website only,
with a new date.

Two builds are read, every text file in each (pages, sitemaps, robots.txt,
llms.txt, the snapshot): one as production builds (analytics and gear links
on, Missouri, CyAN and New York in, no support address so the fallback lede
shows), and one with analytics and gear links off and an address set, so the
other privacy and support branches are read too. Each negative control
asserts that its sabotage changed the input before it asserts the check
caught it.
"""

from __future__ import annotations

import html
import json
import re
import shutil
from pathlib import Path
from typing import Any

import pytest
from paths import CYAN_CACHE, FIXTURES, MO_POINTS, PAGE, TRAPS

from caalgae import cli, site

# Words only an app page would use. Word bounded and case-insensitive, read
# over raw files (so ids, meta descriptions and JSON-LD count) with their
# whitespace flattened (so a phrase broken across template lines counts).
MENTIONS = {
    "iPhone": r"\biphone\b",
    "iOS app": r"\bios app\b",
    "App Store": r"\bapp store\b",
    "the app": r"\bthe app\b",
    "in-app": r"\bin-app\b",
    "in development": r"\bin development\b",
    "not released yet": r"\bnot released yet\b",
    # The owner's rule for every privacy sentence: never "no tracking".
    "no tracking": r"\bno tracking\b",
}
_MENTION = re.compile("|".join(f"(?:{p})" for p in MENTIONS.values()), re.I)
_TAG = re.compile(r"<[^>]+>")
_SCRIPT = re.compile(r"<script\b.*?</script>", re.S)

# The approved words (FOR-APPROVAL-app-mentions.md, recommended column).
ABOUT_HEADING = '<h2 id="app">Is there an app?</h2>'
ABOUT_TEXT = (
    "No. Lake Notice is a website. To follow a lake, bookmark its page. The "
    "pages are rebuilt from the states' data once a day, and every status "
    "shows its date."
)
SUPPORT_HEADING = '<h2 id="app">Is there an app?</h2>'
SUPPORT_TEXT = (
    "No. Lake Notice is a website, and everything on it is free, so there is "
    "nothing to install, restore or refund. To follow a lake, bookmark its page."
)
SUPPORT_LEDE_NO_ADDRESS = "A support address will be listed here."
SUPPORT_DESCRIPTION = "Help with the website."
PRIVACY_DESCRIPTION = "What the website collects."
PRIVACY_UPDATED = "Last updated 2026-11-21. Covers this website."
PRIVACY_LEDE_GA_END = "or you opt out. It has no account and no advertising."
PRIVACY_LEDE_NO_GA = (
    "The Lake Notice website does not collect personal data. It has no "
    "account, no analytics, no advertising and no third-party script."
)
PRIVACY_DATA_FILE = (
    "The advisory data file ( snapshot/v1.json ) is a plain file with no analytics."
)
PRIVACY_GEAR = (
    "They are ordinary links. Nothing loads from Amazon when a page opens, "
    "and this site adds no script or pixel for them."
)
PRIVACY_CHILDREN_GA = (
    "The website's analytics are the same for every visitor, children "
    "included, and never ask for a name, age or contact details."
)

# What the pages said before 2026-11-21, for the negative controls.
OLD = {
    "about/index.html": (
        "<p>A paid iPhone app is in development. Browsing and every lake's "
        "history will be free.</p>"
    ),
    "support/index.html": (
        "<p>The Lake Notice iPhone app is not released yet. It cannot be "
        "downloaded or bought today.</p>"
    ),
    "privacy/index.html": (
        "<li><strong>No analytics:</strong> the app has no analytics, no "
        "tracking and\n      no third-party SDK.</li>"
    ),
    "llms.txt": "- [iPhone app](https://apps.apple.com/x): favorites, alerts",
}


def _cli_build(root: Path) -> Path:
    out = root / "site"
    assert (
        cli.main(
            [
                "--fixture-page", str(PAGE),
                "--fixture-csv", str(TRAPS),
                "--mo-fixture", str(MO_POINTS),
                "--cyan-cache", str(CYAN_CACHE),
                "--cyan-refresh", "never",
                "--ny-history", "on",
                "--ny-cache", str(FIXTURES / "ny"),
                "--run-today", "2026-10-12",
                "--history", str(root / "history.json"),
                "--site-out", str(out),
            ]
        )
        == 0
    )  # fmt: skip
    return out


@pytest.fixture(scope="module")
def live(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """As production builds: analytics and gear links on, no address."""
    out = _cli_build(tmp_path_factory.mktemp("no-app-live"))
    assert site.GA4_MEASUREMENT_ID and site.AMAZON_ASSOCIATE_TAG
    return out


@pytest.fixture(scope="module")
def bare(live: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Analytics and gear links off, a support address set."""
    snap: dict[str, Any] = json.loads((live / "snapshot" / "v1.json").read_text())
    out = tmp_path_factory.mktemp("no-app-bare") / "site"
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(site, "AMAZON_ASSOCIATE_TAG", "")
        site.build_site(
            snap, out, ga4_measurement_id="", support_email="help@example.invalid"
        )
    return out


def _texts(out: Path) -> dict[str, str]:
    """Every text file the build wrote, by path, whitespace flattened."""
    texts: dict[str, str] = {}
    for f in sorted(out.rglob("*")):
        if not f.is_file():
            continue
        try:
            raw = f.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue  # an image or another binary file
        texts[str(f.relative_to(out))] = " ".join(raw.split())
    return texts


def _mentions(out: Path) -> list[tuple[str, str]]:
    return [
        (name, m.group(0).lower())
        for name, text in _texts(out).items()
        for m in _MENTION.finditer(text)
    ]


def _visible(page: Path) -> str:
    raw = _SCRIPT.sub(" ", page.read_text(encoding="utf-8"))
    raw = re.sub(r"<title>.*?</title>|<meta[^>]*>", " ", raw, flags=re.S)
    return html.unescape(re.sub(r"\s+", " ", _TAG.sub(" ", raw)))


def _description(page: Path) -> str:
    found = re.search(r'<meta name="description" content="([^"]*)"', page.read_text())
    assert found is not None, page
    return html.unescape(found.group(1))


# ---- no file mentions an app, in either build


@pytest.mark.parametrize("build", ["live", "bare"])
def test_no_generated_file_mentions_an_app(build: str, request: pytest.FixtureRequest):
    out: Path = request.getfixturevalue(build)
    texts = _texts(out)
    # The pages the app was on were built, so the check is not empty.
    for name in ("about/index.html", "support/index.html", "privacy/index.html",
                 "index.html", "llms.txt", "sitemap.xml", "snapshot/v1.json"):  # fmt: skip
        assert name in texts, name
    assert sum(n.startswith("water/") for n in texts) > 10
    assert any(n.startswith("state/ny/") for n in texts) or build == "bare"
    assert _mentions(out) == []


def test_about_answers_is_there_an_app(live: Path):
    page = live / "about" / "index.html"
    assert ABOUT_HEADING in page.read_text(encoding="utf-8")
    assert f"Is there an app? {ABOUT_TEXT}" in _visible(page)


def test_support_answers_is_there_an_app(live: Path, bare: Path):
    for out in (live, bare):
        page = out / "support" / "index.html"
        assert SUPPORT_HEADING in page.read_text(encoding="utf-8")
        assert f"Is there an app? {SUPPORT_TEXT}" in _visible(page)
        assert _description(page) == SUPPORT_DESCRIPTION
    assert SUPPORT_LEDE_NO_ADDRESS in _visible(live / "support" / "index.html")
    assert "help@example.invalid" in _visible(bare / "support" / "index.html")


def test_privacy_covers_the_website_only_with_the_new_date(live: Path, bare: Path):
    for out in (live, bare):
        page = out / "privacy" / "index.html"
        text = _visible(page)
        assert PRIVACY_UPDATED in text
        assert 'id="app"' not in page.read_text(encoding="utf-8")
        assert _description(page) == PRIVACY_DESCRIPTION
    on = _visible(live / "privacy" / "index.html")
    assert PRIVACY_LEDE_GA_END in on
    assert PRIVACY_DATA_FILE in on
    assert PRIVACY_GEAR in on
    assert PRIVACY_CHILDREN_GA in on
    off = _visible(bare / "privacy" / "index.html")
    assert PRIVACY_LEDE_NO_GA in off
    assert "Nothing is collected from anyone, including children." in off
    assert "Gear links" not in off


def test_llms_txt_calls_lake_notice_a_free_website(live: Path):
    text = (live / "llms.txt").read_text(encoding="utf-8")
    assert "Lake Notice is a free website that mirrors state" in text


def test_the_app_store_switch_is_gone():
    # The parser only: nothing is built or fetched.
    with pytest.raises(SystemExit):
        cli._parse_args(["--app-store-url", "https://apps.apple.com/x"])
    assert "app_store_url" not in vars(cli._parse_args([]))


# ---- negative controls


def _copy(src: Path, dst: Path) -> Path:
    shutil.copytree(src, dst)
    return dst


@pytest.mark.parametrize("name", sorted(OLD))
def test_negative_control_each_old_passage_is_caught(
    name: str, live: Path, tmp_path: Path
):
    out = _copy(live, tmp_path / "site")
    target = out / name
    before = target.read_text(encoding="utf-8")
    anchor = "</main>" if name.endswith(".html") else "## Sources"
    doctored = before.replace(anchor, f"{OLD[name]}\n{anchor}", 1)
    assert doctored != before  # the sabotage landed
    target.write_text(doctored, encoding="utf-8")
    found = _mentions(out)
    assert found and {n for n, _ in found} == {name}


def test_negative_control_the_old_meta_description_is_caught(
    live: Path, tmp_path: Path
):
    out = _copy(live, tmp_path / "site")
    page = out / "support" / "index.html"
    before = page.read_text(encoding="utf-8")
    doctored = before.replace(
        f'content="{SUPPORT_DESCRIPTION}"',
        'content="Help with the website. The iPhone app is not released yet."',
    )
    assert doctored != before
    page.write_text(doctored, encoding="utf-8")
    assert ("support/index.html", "not released yet") in _mentions(out)


def test_negative_control_a_phrase_broken_across_lines_is_caught(
    live: Path, tmp_path: Path
):
    out = _copy(live, tmp_path / "site")
    home = out / "index.html"
    before = home.read_text(encoding="utf-8")
    doctored = before.replace(
        "</main>", "<p>An app is in\n  development.</p>\n</main>", 1
    )
    assert doctored != before
    home.write_text(doctored, encoding="utf-8")
    assert _mentions(out) == [("index.html", "in development")]
