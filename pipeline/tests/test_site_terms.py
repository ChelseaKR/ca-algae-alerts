"""The terms of use page: built, linked from every footer, in the sitemap,
and never a safety claim (DECISIONS 0002)."""

from __future__ import annotations

from pathlib import Path

import pytest
from test_site import affirmative_safety_claims, build, pages, text_of


@pytest.fixture(scope="module")
def site_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build(tmp_path_factory.mktemp("terms"))


def test_terms_page_names_the_operator_and_says_it_is_not_a_determination(
    site_dir: Path,
) -> None:
    text = text_of(site_dir / "terms" / "index.html")
    assert "Chelsea Kelly-Reif" in text
    assert "chelsea@chelseakr.com" in text
    assert "This site is not a safety determination." in text
    assert "follow posted signs" in text
    assert "can be wrong or late" in text
    assert "laws of the State of California" in text
    assert affirmative_safety_claims(text) == []
    # No affiliate section while the Associates tag is empty (DECISIONS 0013).
    assert "Amazon" not in text


def test_every_footer_links_the_terms_page(site_dir: Path) -> None:
    built = [p for p in pages(site_dir) if p.name != "404.html"]
    assert built
    for page in built:
        assert 'terms/">terms</a>' in page.read_text(encoding="utf-8"), page


def test_terms_page_is_in_the_sitemap(site_dir: Path) -> None:
    sitemap = (site_dir / "sitemap.xml").read_text(encoding="utf-8")
    assert "/terms/</loc>" in sitemap


def test_terms_page_discloses_affiliate_links_once_the_tag_is_set(
    tmp_path: Path,
) -> None:
    from test_site_affiliate import DISCLOSURE, TAG, build

    text = text_of(build(tmp_path, TAG) / "terms" / "index.html")
    assert DISCLOSURE in text
    assert affirmative_safety_claims(text) == []
