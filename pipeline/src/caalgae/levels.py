"""The levels page: /levels/ in English and its Spanish twin, /es/niveles/
(DECISIONS 0025). Both are off on main (``i18n.LEVELS_ENABLED`` and
``i18n.ES_ENABLED``), so a build today writes neither page.

With Spanish on, the build fails, and nothing is written for publishing, if
the catalog fails the gate (a draft safety string, a state quote that
drifted, a placeholder not yet pasted) or if the built Spanish page has
English left on it. ``allow_draft`` skips only the review checks, for tests
and a local preview; the rendered-page check always runs.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, Any

from caalgae import i18n

if TYPE_CHECKING:
    from caalgae.site import SiteBuilder

EN_PATH = "levels/"
ES_PATH = "es/niveles/"


def translator(strings: Mapping[str, str]) -> Callable[..., str]:
    """``t(key, **values)``. A missing key raises, so a page with a missing
    string never builds; there is no English fallback."""

    def t(key: str, **values: Any) -> str:
        value = strings[key]
        return value.format(**values) if values else value

    return t


def sign_sources(lang: str, cat: i18n.Catalog) -> dict[str, dict[str, Any]]:
    """Where each level's sign quote comes from. A Spanish quote has a read
    date only once it is a ``state`` string; a placeholder has none, and no
    date is shown for it."""
    if lang == "en":
        return {
            tier: {"url": i18n.SIGN_URLS[tier], "read_on": i18n.EN_SIGN_READ_ON}
            for tier in i18n.SIGNED_TIERS
        }
    out = {}
    for tier in i18n.SIGNED_TIERS:
        meta = cat.status.get(f"level.{tier}.sign", {})
        if meta.get("status") == "state":
            out[tier] = {"url": meta["url"], "read_on": meta["read_on"]}
        else:
            out[tier] = {"url": meta.get("paste_from", i18n.SIGN_URLS[tier]), "read_on": None}  # fmt: skip
    return out


def _page(builder: SiteBuilder, lang: str, cat: i18n.Catalog, *, twin: bool) -> None:
    from caalgae.site import SITE_NAME, TITLE_MAX, fit

    rel, other_rel = (EN_PATH, ES_PATH) if lang == "en" else (ES_PATH, EN_PATH)
    t = translator(cat.en if lang == "en" else cat.es)
    crumbs = [
        (t("nav.home"), builder.base_url),
        (t("levels.h1"), builder.base_url + rel),
    ]
    builder._write(
        rel,
        "levels.html.jinja",
        title=fit([f"{t('levels.title')} | {SITE_NAME}", t("levels.title")], TITLE_MAX),
        description=t("levels.description"),
        breadcrumb=crumbs,
        structured_data={
            "@context": "https://schema.org",
            **builder._breadcrumb_data(crumbs),
        },
        lang=lang,
        t=t,
        local_date=i18n.DATE_LABEL[lang],
        tiers=i18n.TIERS,
        signs=sign_sources(lang, cat),
        other_language_url=("../" * rel.count("/")) + other_rel if twin else None,
        other_lang="es" if lang == "en" else "en",
    )


def build(
    builder: SiteBuilder,
    *,
    levels: bool,
    es: bool,
    allow_draft: bool = False,
    cat: i18n.Catalog | None = None,
) -> None:
    """Write the levels pages the flags ask for. With ``es``, the catalog is
    gated first and the built Spanish page is checked after."""
    if es and not levels:
        raise i18n.GateError("the Spanish levels page needs its English twin")
    cat = cat or i18n.catalog()
    if es:
        i18n.require(i18n.check_catalog(cat, enabled=not allow_draft))
    if levels:
        _page(builder, "en", cat, twin=es)
    if es:
        _page(builder, "es", cat, twin=True)
        i18n.require(i18n.check_rendered(builder.out, builder.snap, cat))
