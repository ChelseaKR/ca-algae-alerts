"""The support page's app section says only what is true today: the iPhone
app is not released (DECISIONS 0031). Nothing on the page may read as if the
app can be downloaded, bought, restored or relied on for alerts yet."""

from __future__ import annotations

import html
import re

import pytest
from paths import PAGE, TRAPS

from caalgae import cli

_TAG = re.compile(r"<[^>]+>")

# Phrases that would only be true once the app is on sale.
_NOT_YET_TRUE = (
    "app store",
    "download the app",
    "get the app",
    "restore purchases",
    "reportaproblem",
    "within about a day",
    "when do app alerts arrive",
    "background app refresh",
)


@pytest.fixture(scope="module")
def support(tmp_path_factory: pytest.TempPathFactory) -> str:
    tmp = tmp_path_factory.mktemp("support")
    out = tmp / "site"
    assert (
        cli.main(
            [
                "--fixture-page", str(PAGE),
                "--fixture-csv", str(TRAPS),
                "--run-today", "2026-10-12",
                "--history", str(tmp / "history.json"),
                "--site-out", str(out),
            ]
        )
        == 0
    )  # fmt: skip
    return (out / "support" / "index.html").read_text(encoding="utf-8")


def text_of(raw: str) -> str:
    raw = re.sub(r"<script\b.*?</script>", " ", raw, flags=re.S)
    return html.unescape(re.sub(r"\s+", " ", _TAG.sub(" ", raw)))


def test_the_app_section_says_it_is_not_released(support: str) -> None:
    assert '<h2 id="iphone-app">The iPhone app</h2>' in support
    assert "The Lake Notice iPhone app is not released yet." in text_of(support)


def test_nothing_reads_as_if_the_app_were_on_sale(support: str) -> None:
    lower = text_of(support).lower()
    found = [p for p in _NOT_YET_TRUE if p in lower]
    assert found == []


def test_the_page_description_does_not_offer_help_with_an_unreleased_app(
    support: str,
) -> None:
    description = re.search(r'<meta name="description" content="([^"]*)"', support)
    assert description is not None
    assert "not released yet" in description.group(1)
