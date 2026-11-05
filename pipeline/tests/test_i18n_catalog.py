"""The Spanish catalog and its review gate (DECISIONS 0025): the shape and
parity checks that always run, the review checks that run once Spanish is
on, the Spanish copy guard and the Spanish date formatter."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

import pytest

from caalgae import i18n, sources, wording


def green() -> i18n.Catalog:
    """The real catalog as it would look after review: every draft marked
    reviewed and every sign placeholder replaced by a pasted quote with its
    hash. The sabotage tests start here, so each one shows the gate can pass
    and that the one change turns it red."""
    cat = i18n.catalog()
    es = dict(cat.es)
    status: dict[str, dict[str, Any]] = {}
    for n, (key, meta) in enumerate(cat.status.items()):
        new = dict(meta)
        if i18n.PLACEHOLDER in es[key]:
            es[key] = f"«No se meta al agua.» Texto de prueba del letrero {n}."
            new.update(
                status="state",
                url="https://example.org/letrero.pdf",
                read_on="2026-11-05",
                sha256=i18n.sha256(es[key]),
            )
        elif new["status"] == "draft":
            new.update(status="reviewed", reviewer="XX", reviewed_on="2026-11-05")
        status[key] = new
    return i18n.Catalog(en=cat.en, es=es, status=status)


def with_changes(
    cat: i18n.Catalog,
    es: dict[str, str] | None = None,
    status: dict[str, dict[str, Any]] | None = None,
) -> i18n.Catalog:
    new_status = {k: dict(v) for k, v in cat.status.items()}
    for key, fields in (status or {}).items():
        new_status[key] = {**new_status[key], **fields}
    return i18n.Catalog(en=cat.en, es={**cat.es, **(es or {})}, status=new_status)


# -- main as committed ------------------------------------------------------


def test_spanish_is_off_on_main() -> None:
    assert i18n.ES_ENABLED is False
    assert i18n.LEVELS_ENABLED is False


def test_committed_catalog_passes_the_always_on_checks() -> None:
    assert i18n.check_catalog(i18n.catalog(), enabled=False) == []


def test_every_safety_string_on_main_is_still_a_draft() -> None:
    # No reviewer has signed off and no sign text has been pasted, so nothing
    # on main may claim otherwise.
    cat = i18n.catalog()
    safety = {k: m for k, m in cat.status.items() if m.get("safety")}
    assert len(safety) == 22
    assert {m["status"] for m in safety.values()} == {"draft"}
    assert all(m["status"] in ("draft", "same") for m in cat.status.values())


def test_sign_wording_is_left_as_marked_placeholders() -> None:
    cat = i18n.catalog()
    for tier in i18n.SIGNED_TIERS:
        key = f"level.{tier}.sign"
        assert cat.es[key].startswith(i18n.PLACEHOLDER)
        assert cat.status[key]["paste_from"].startswith(
            "https://mywaterquality.ca.gov/"
        )


def test_turning_spanish_on_today_fails_on_every_draft_and_placeholder() -> None:
    problems = i18n.check_catalog(i18n.catalog(), enabled=True)
    assert sum("safety string is still a draft" in p for p in problems) == 22
    assert sum("has not been pasted in" in p for p in problems) == 4


def test_the_reviewed_catalog_passes_with_spanish_on() -> None:
    assert i18n.check_catalog(green(), enabled=True) == []


def test_english_catalog_reads_the_published_wording() -> None:
    # English output is unchanged: the catalog points at wording.py.
    for tier in i18n.TIERS:
        assert i18n.EN[f"level.{tier}.guidance"] == wording.LEVEL_GUIDANCE[tier]
    assert i18n.EN["levels.human_advice"] == wording.HUMAN_ADVICE
    assert i18n.EN["footer.not_medical_advice"] == wording.NOT_MEDICAL_ADVICE
    for source in sources.SOURCES.values():
        assert i18n.EN[f"footer.attribution.{source.id}"] == source.attribution


# -- the four sabotages: each turns the gate red ------------------------------


def test_sabotage_english_value_in_a_safety_key() -> None:
    base = green()
    english = base.en["levels.human_advice"]
    bad = with_changes(base, es={"levels.human_advice": english})
    assert bad.es["levels.human_advice"] != base.es["levels.human_advice"]
    problems = i18n.check_catalog(bad, enabled=True)
    assert problems == [
        "levels.human_advice: Spanish is identical to English but marked reviewed"
    ]


def test_sabotage_one_word_of_a_state_quote() -> None:
    base = green()
    key = "level.danger.sign"
    edited = base.es[key].replace("meta", "mete", 1)
    assert edited != base.es[key]
    problems = i18n.check_catalog(with_changes(base, es={key: edited}), enabled=True)
    assert problems == [f"{key}: text differs from the state quote it was pasted as"]


def test_sabotage_a_draft_safety_string() -> None:
    bad = with_changes(green(), status={"level.warning.guidance": {"status": "draft"}})
    problems = i18n.check_catalog(bad, enabled=True)
    assert problems == ["level.warning.guidance: safety string is still a draft"]
    # Off, a draft is allowed: that is what main carries.
    assert i18n.check_catalog(bad, enabled=False) == []


def test_sabotage_a_safety_claim_in_spanish() -> None:
    bad = with_changes(green(), es={"levels.end": "El agua es segura para nadar."})
    problems = i18n.check_catalog(bad, enabled=True)
    assert problems == ["levels.end: copy guard: 'segura'"]


# -- shape rules ----------------------------------------------------------------


def test_a_missing_spanish_string_fails() -> None:
    cat = green()
    es = dict(cat.es)
    del es["levels.h1"]
    problems = i18n.check_catalog(i18n.Catalog(cat.en, es, cat.status), enabled=False)
    assert "levels.h1: missing from es.json" in problems
    assert "levels.h1: status for a key with no string" in problems


def test_extra_keys_and_missing_status_fail() -> None:
    cat = green()
    es = {**cat.es, "levels.extra": "Texto"}
    status = {k: v for k, v in cat.status.items() if k != "levels.h1"}
    problems = i18n.check_catalog(i18n.Catalog(cat.en, es, status), enabled=False)
    assert "levels.extra: in es.json, not in English" in problems
    assert "levels.h1: no status" in problems


def test_placeholder_parity() -> None:
    bad = with_changes(green(), es={"footer.independent": "Independiente."})
    assert i18n.check_catalog(bad, enabled=False) == [
        "footer.independent: placeholders differ from English (['site_name'])"
    ]


def test_same_marker_must_not_be_stale_or_on_safety_text() -> None:
    stale = with_changes(green(), es={"state.CA": "Califas"})
    assert i18n.check_catalog(stale, enabled=False) == [
        "state.CA: marked same but no longer matches English (stale)"
    ]
    english = green().en["levels.not_a_finding"]
    bad = with_changes(
        green(),
        es={"levels.not_a_finding": english},
        status={"levels.not_a_finding": {"status": "same"}},
    )
    assert i18n.check_catalog(bad, enabled=False) == [
        "levels.not_a_finding: a safety string cannot be marked same"
    ]


def test_status_fields_are_required() -> None:
    cat = green()
    bad = with_changes(
        cat,
        status={
            "levels.h1": {"status": "approved"},
            "levels.lede": {"reviewer": ""},
            "level.caution.sign": {"url": ""},
        },
    )
    problems = i18n.check_catalog(bad, enabled=False)
    assert "levels.h1: status must be one of state, reviewed, same, draft, not 'approved'" in problems  # fmt: skip
    assert (
        "levels.lede: a reviewed string needs reviewer initials and a date" in problems
    )
    assert "level.caution.sign: a state string needs url" in problems


def test_a_placeholder_cannot_be_marked_reviewed() -> None:
    cat = i18n.catalog()
    bad = with_changes(
        cat,
        status={"level.caution.sign": {"status": "reviewed", "reviewer": "XX", "reviewed_on": "2026-11-05"}},
    )  # fmt: skip
    assert i18n.check_catalog(bad, enabled=False) == [
        "level.caution.sign: still holds a paste placeholder but is marked reviewed"
    ]


# -- the Spanish copy guard ------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "El lago es seguro.",
        "Aguas seguras para todos.",
        "Ya está sin peligro.",
        "El río está apto para nadar.",
        "El agua está limpia.",
        "Libre de toxinas desde ayer.",
        "Es peligroso nadar.",
        "Hay peligro hoy.",
    ],
)
def test_spanish_guard_catches(text: str) -> None:
    assert i18n.spanish_safety_claims(text, ["Peligro"]) != []


def test_spanish_guard_allows_the_level_label() -> None:
    assert i18n.spanish_safety_claims("Aviso de Peligro, publicado.", ["Peligro"]) == []


# -- dates -------------------------------------------------------------------------


def test_es_date() -> None:
    assert i18n.es_date(dt.date(2026, 10, 9)) == "9 de octubre de 2026"
    assert i18n.es_date("2027-01-31") == "31 de enero de 2027"
    with pytest.raises(ValueError, match="needs a date"):
        i18n.es_date(None)


def test_catalog_files_are_valid_json_with_one_status_each() -> None:
    root = Path(i18n.__file__).parent / "locales"
    es = json.loads((root / "es.json").read_text(encoding="utf-8"))
    status = json.loads((root / "es.status.json").read_text(encoding="utf-8"))
    assert set(es) == set(status) == set(i18n.EN)
    assert all(m["status"] in i18n.STATUSES for m in status.values())


# -- the script -------------------------------------------------------------------


def test_gate_passes_on_main_and_fails_when_switched_on(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert i18n.main([]) == 0
    out = capsys.readouterr().out
    assert "58 Spanish strings (0 state, 0 reviewed, 1 same, 57 draft)" in out
    assert "22 safety drafts; Spanish off; 0 problems" in out
    assert i18n.main(["--enabled"]) == 1
    assert "26 problems" in capsys.readouterr().out


def test_gate_prints_a_hash(capsys: pytest.CaptureFixture[str]) -> None:
    assert i18n.main(["--hash", "levels.h1"]) == 0
    assert capsys.readouterr().out.strip() == i18n.sha256(
        i18n.catalog().es["levels.h1"]
    )
