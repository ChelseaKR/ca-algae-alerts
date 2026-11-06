"""The levels pages, /levels/ and /es/niveles/ (DECISIONS 0025): off on main,
gated when on, and checked after rendering so English cannot reach a Spanish
page through a template literal."""

from __future__ import annotations

import html
import json
import re
import shutil
from pathlib import Path
from typing import Any

import jinja2
import pytest
from paths import PAGE, TRAPS
from test_i18n_catalog import green, with_changes

from caalgae import cli, i18n, levels, newyork, site, wording

ENGLISH_SENTENCE = "<p>Keep your dog out of the water today.</p>"


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    tmp = tmp_path_factory.mktemp("es")
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
    return out


def snap_of(root: Path) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads((root / "snapshot" / "v1.json").read_text())
    return loaded


def builder_for(root: Path, tmp_path: Path, ga4: str = "") -> site.SiteBuilder:
    out = tmp_path / "site"
    shutil.copytree(root, out)
    # The fixture site follows site.NY_HISTORY_ENABLED, as a publish does, so
    # this builder carries the same New York section and the same nav.
    return site.SiteBuilder(
        snap_of(root),
        out,
        base_url="",
        support_email="",
        app_store_url="",
        ga4_measurement_id=ga4,
        ny_history=newyork.load() if site.NY_HISTORY_ENABLED else None,
    )


def es_page(builder: site.SiteBuilder) -> str:
    return (builder.out / levels.ES_PATH / "index.html").read_text(encoding="utf-8")


def visible(page: str) -> str:
    page = re.sub(r"<script\b.*?</script>|<head\b.*?</head>", " ", page, flags=re.S)
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", page)))


def sabotaged_template() -> jinja2.DictLoader:
    source = (
        Path(site.__file__).parent / "templates" / "levels.html.jinja"
    ).read_text()
    edited = source.replace("{% endblock %}", ENGLISH_SENTENCE + "\n{% endblock %}")
    assert edited != source
    return jinja2.DictLoader({"levels.html.jinja": edited})


# -- off on main ----------------------------------------------------------------


def test_main_builds_neither_page(built: Path) -> None:
    assert not (built / "levels").exists()
    assert not (built / "es").exists()
    sitemap = (built / "sitemap.xml").read_text()
    assert "/levels/" not in sitemap and "/es/" not in sitemap


def test_no_page_on_main_carries_hreflang(built: Path) -> None:
    assert not [p for p in built.rglob("*.html") if "hreflang" in p.read_text()]


def test_spanish_needs_its_english_twin(built: Path, tmp_path: Path) -> None:
    with pytest.raises(i18n.GateError, match="English twin"):
        levels.build(builder_for(built, tmp_path), levels=False, es=True)


def test_turning_spanish_on_today_fails_the_build(built: Path, tmp_path: Path) -> None:
    builder = builder_for(built, tmp_path)
    with pytest.raises(i18n.GateError, match="safety string is still a draft"):
        levels.build(builder, levels=True, es=True)
    assert not (builder.out / "es").exists()


# -- the English page ---------------------------------------------------------------


def test_english_page_only(built: Path, tmp_path: Path) -> None:
    builder = builder_for(built, tmp_path)
    levels.build(builder, levels=True, es=False)
    page = (builder.out / levels.EN_PATH / "index.html").read_text()
    assert '<html lang="en">' in page
    assert "En español" not in page  # no link to a twin that was not built
    text = visible(page)
    for tier in i18n.TIERS:
        assert wording.LEVEL_GUIDANCE[tier] in text
    assert wording.NOT_A_FINDING in text
    assert builder.base_url + levels.EN_PATH in builder.urls
    assert len(re.search(r"<title>(.*?)</title>", page).group(1)) <= site.TITLE_MAX


def test_english_chrome_matches_every_other_page(built: Path, tmp_path: Path) -> None:
    # The fixture site was built with the live GA4 setting; so is this page.
    builder = builder_for(built, tmp_path, ga4=site.GA4_MEASUREMENT_ID)
    levels.build(builder, levels=True, es=False)
    page = (builder.out / levels.EN_PATH / "index.html").read_text()
    dogs = (builder.out / "dogs" / "index.html").read_text()
    for part in ("header", "footer"):
        pattern = rf"<{part}\b.*?</{part}>"
        mine = re.search(pattern, page, re.S)
        theirs = re.search(pattern, dogs, re.S)
        assert mine and theirs
        assert re.sub(r"\s+", " ", mine.group(0)) == re.sub(
            r"\s+", " ", theirs.group(0)
        )


# -- the Spanish page, previewed with drafts and once reviewed -------------------------


def test_draft_preview_renders_clean_spanish(built: Path, tmp_path: Path) -> None:
    # The committed drafts already pass the rendered-page check, so review
    # is the only step left between them and a build.
    builder = builder_for(built, tmp_path)
    levels.build(builder, levels=True, es=True, allow_draft=True)
    page = es_page(builder)
    assert '<html lang="es">' in page
    assert i18n.check_rendered(builder.out, builder.snap, i18n.catalog()) == []
    assert "⟦PEGAR" in page  # placeholders show in a preview, never in a build


def test_reviewed_catalog_builds_both_twins(built: Path, tmp_path: Path) -> None:
    builder = builder_for(built, tmp_path)
    levels.build(builder, levels=True, es=True, cat=green())
    page = es_page(builder)
    en = (builder.out / levels.EN_PATH / "index.html").read_text()
    assert '<a href="../../levels/" lang="en">In English</a>' in page
    assert '<a href="../es/niveles/" lang="es">En español</a>' in en
    assert "hreflang" not in page + en  # waits until after ~2026-11-25
    assert "leído el 5 de noviembre de 2026" in page
    # Too long with the site name, so the title drops it (site.fit).
    assert "<title>Qué significan Precaución, Advertencia y Peligro</title>" in page
    assert "<title>What Caution, Warning and Danger mean | Lake Notice</title>" in en
    for text in (page, en):
        desc = re.search(r'<meta name="description" content="([^"]*)"', text)
        assert desc and len(html.unescape(desc.group(1))) <= site.DESCRIPTION_MAX
    assert "⟦PEGAR" not in page


# -- the rendered-page sabotages --------------------------------------------------------


def test_sabotage_hard_coded_english_in_the_spanish_template(
    built: Path, tmp_path: Path
) -> None:
    clean = builder_for(built, tmp_path / "clean")
    levels.build(clean, levels=True, es=True, cat=green())
    builder = builder_for(built, tmp_path / "bad")
    builder.env.loader = jinja2.ChoiceLoader([sabotaged_template(), builder.env.loader])
    with pytest.raises(
        i18n.GateError, match="English words: Keep your dog out of the water"
    ):
        levels.build(builder, levels=True, es=True, cat=green())
    assert es_page(builder) != es_page(clean)  # the sabotage applied
    assert ENGLISH_SENTENCE in es_page(builder)


def test_sabotage_english_in_a_safety_key_is_caught_after_rendering(
    built: Path, tmp_path: Path
) -> None:
    # Marked draft, the English value passes the catalog's equal-means-declared
    # rule in a preview; the rendered-page check still stops it.
    bad = with_changes(
        i18n.catalog(),
        es={"levels.human_advice": wording.HUMAN_ADVICE},
    )
    builder = builder_for(built, tmp_path)
    with pytest.raises(i18n.GateError, match="English words"):
        levels.build(builder, levels=True, es=True, allow_draft=True, cat=bad)
    assert wording.HUMAN_ADVICE in visible(es_page(builder))


def test_rendered_check_catches_a_safety_claim_and_a_wrong_lang(
    built: Path, tmp_path: Path
) -> None:
    builder = builder_for(built, tmp_path)
    levels.build(builder, levels=True, es=True, cat=green())
    path = builder.out / levels.ES_PATH / "index.html"
    path.write_text(
        es_page(builder)
        .replace('<html lang="es">', '<html lang="en">')
        .replace("</main>", "<p>El agua está limpia.</p></main>")
    )
    problems = i18n.check_rendered(builder.out, builder.snap, green())
    assert "es/niveles/index.html: lang is not 'es'" in problems
    assert "es/niveles/index.html: copy guard: 'limpia'" in problems


def test_stopword_share_and_proper_nouns(built: Path) -> None:
    vocab = i18n.english_vocabulary(i18n.catalog())
    # Names from the snapshot stay as the state wrote them.
    names = i18n.snapshot_proper_nouns(snap_of(built))
    assert names
    name = sorted(names, key=len)[-1]
    page = f"<html lang='es'><body><p>Aviso en {name}, del estado.</p></body></html>"
    assert i18n.english_leftovers(page, allow=names, vocabulary=vocab) == []
    # Short English fragments add up.
    page = "<body>" + " ".join(["palabra"] * 30) + " the water is. </body>"
    assert i18n.english_leftovers(page, allow=(), vocabulary=frozenset()) == [
        "English stopwords are 3 of 33 words (over 3%)"
    ]


def test_ga4_messages_are_english_and_block_turning_spanish_on(
    built: Path, tmp_path: Path
) -> None:
    # A known blocker, written down rather than hidden: _ga4.html.jinja's
    # opt-out messages are English, so with GA4 on the Spanish page fails.
    builder = builder_for(built, tmp_path, ga4="G-TEST000000")
    with pytest.raises(i18n.GateError, match="Analytics is off"):
        levels.build(builder, levels=True, es=True, cat=green())


def test_a_missing_string_fails_the_render() -> None:
    t = levels.translator({"a": "uno {n}"})
    assert t("a", n=1) == "uno 1"
    with pytest.raises(KeyError):
        t("b")
