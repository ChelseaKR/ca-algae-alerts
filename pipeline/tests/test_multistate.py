"""California, Missouri and the satellite layer together: the site and the
snapshot keep them apart and say what each source requires."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from paths import CYAN_CACHE, MO_POINTS, PAGE, TRAPS
from test_site import affirmative_safety_claims, pages, text_of

from caalgae import cli
from caalgae.sources import MO_REQUIRED_DISCLAIMER, MO_REVOCATION_CLAUSE


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    tmp = tmp_path_factory.mktemp("multi")
    assert cli.main([
        "--fixture-page", str(PAGE), "--fixture-csv", str(TRAPS), "--run-today", "2026-10-12",
        "--history", str(tmp / "h.json"), "--site-out", str(tmp / "site"),
        "--snapshot-out", str(tmp / "s.json"),
        "--mo-fixture", str(MO_POINTS), "--cyan-cache", str(CYAN_CACHE),
    ]) == 0  # fmt: skip
    return tmp


def snap(built: Path) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads((built / "s.json").read_text())
    return loaded


def test_both_states_and_every_source_file(built: Path) -> None:
    s = snap(built)
    assert {w["state"] for w in s["waterbodies"]} == {"CA", "MO"}
    assert [f["source"] for f in s["source_files"]] == ["ca-swrcb-fhab", "mo-dnr-hab"]
    kinds = {
        src["id"]: (src["record_kind"], src["lift_semantics"]) for src in s["sources"]
    }
    assert kinds == {
        "ca-swrcb-fhab": ("official_advisory", "explicit_record"),
        "mo-dnr-hab": ("official_advisory", "explicit_field"),
        "epa-cyan": ("satellite_estimate", "none_recorded"),
    }


def test_satellite_never_decides_a_status(built: Path) -> None:
    s = snap(built)
    alpha = next(w for w in s["waterbodies"] if w["name"] == "Lake Alpha")
    assert alpha["satellite"]["record_kind"] == "satellite_estimate"
    assert all(
        r["record_kind"] == "official_advisory"
        for w in s["waterbodies"]
        for r in w["records"]
    )
    # Beta Reservoir has an explicit end; its satellite block (no readings)
    # leaves that alone, and a high estimate elsewhere does not create one.
    beta = next(w for w in s["waterbodies"] if w["name"] == "Beta Reservoir")
    assert beta["status"]["kind"] == "no_advisory_recorded"
    assert beta["satellite"]["readings"] == []


def test_lake_page_labels_the_satellite_section(built: Path) -> None:
    text = text_of(built / "site" / "water" / "ca-alameda-lake-alpha" / "index.html")
    assert "Satellite estimate (not an advisory)" in text
    assert "about 550,000 cells/mL" in text
    assert "not whether toxins are present" in text
    assert "small ponds" in text
    beta = text_of(built / "site" / "water" / "ca-lake-beta-reservoir" / "index.html")
    assert "No satellite reading on file" in beta and "not a reading" in beta


def test_missouri_pages_carry_the_required_disclaimer_verbatim(built: Path) -> None:
    mo_pages = sorted((built / "site" / "water").glob("mo-*/index.html"))
    assert mo_pages
    for page in [
        *mo_pages,
        built / "site" / "state" / "mo" / "index.html",
        built / "site" / "about" / "index.html",
    ]:
        assert MO_REQUIRED_DISCLAIMER in text_of(page), page
    about = text_of(built / "site" / "about" / "index.html")
    assert MO_REVOCATION_CLAUSE in about
    ca = text_of(built / "site" / "water" / "ca-alameda-lake-alpha" / "index.html")
    assert MO_REQUIRED_DISCLAIMER not in ca
    assert "Missouri data disclaimer" in ca  # the footer links it from every page


def test_missouri_dissipated_reads_as_the_states_record(built: Path) -> None:
    s = snap(built)
    w = next(
        w
        for w in s["waterbodies"]
        if w["state"] == "MO" and w["status"]["lift_kind"] == "dissipated"
    )
    text = text_of(built / "site" / "water" / w["id"] / "index.html")
    assert re.search(
        r"The state recorded the bloom as dissipated on \w{3} \d{1,2}, \d{4}\.", text
    )


def test_no_page_in_the_multistate_build_claims_safety(built: Path) -> None:
    problems = []
    for page in pages(built / "site"):
        problems += [
            f"{page.name}: {x}" for x in affirmative_safety_claims(text_of(page))
        ]
    assert problems == []
