"""Decision 0023: Missouri pages quote the department's own public note
(PubInfo) verbatim, credited, and the status box says when the department
closed the headline's case without a dissipation date (batch LN-C).

The notes are the department's, read from its HAB layer on 2026-11-05
(Hagen Lake, objectid 37535, and Briars pond, 37943, both "advise" and
"Closed" with no dissipation date).
"""

from __future__ import annotations

import datetime as dt
import html
import json
from pathlib import Path
from typing import Any

import pytest
from paths import CYAN_CACHE, MO_POINTS, PAGE, TRAPS
from test_site import text_of

from caalgae import cli, missouri, snapshot
from caalgae import history as hist
from caalgae import status as st

RUN = dt.date(2026, 11, 5)
HAGEN = (
    "Cyanobacteria present. People and animals should avoid contact with the "
    "water for at least 14 days after the bloom has dissipated. "
)
BRIARS = (
    "Cyanobacteria confirmed. People and pets should avoid contact for at "
    "least 14 days after the bloom has dissipated. "
)


def feature(**attrs: Any) -> dict[str, Any]:
    base = {"objectid": 37535, "WBName": "Hagen Lake", "HABODat": 1790442000000,
            "BloomStat": "advise", "CaseStatus": "Closed", "DissDat": None,
            "WBType": "lakepond", "PubInfo": HAGEN}  # fmt: skip
    return {
        "attributes": {**base, **attrs},
        "geometry": {"x": -92.25499220002386, "y": 38.96778369957761},
    }


def test_pubinfo_is_read_verbatim_with_its_spacing_trimmed() -> None:
    r = missouri._record(feature(), RUN)
    assert not isinstance(r, str)
    assert r.public_info == HAGEN.strip()
    assert r.detail == "Case closed."


def test_a_note_decides_nothing() -> None:
    """Negative control: a note that says the bloom dissipated does not end
    the advisory. Only a dissipation date does (0010)."""
    r = missouri._record(feature(PubInfo="Bloom has dissipated."), RUN)
    assert not isinstance(r, str)
    assert r.public_info == "Bloom has dissipated."
    assert st.site_status([r], RUN).kind == st.ADVISORY


@pytest.mark.parametrize("blank", [None, "", "   "])
def test_a_blank_note_is_blank(blank: str | None) -> None:
    r = missouri._record(feature(PubInfo=blank), RUN)
    assert not isinstance(r, str)
    assert r.public_info == ""


def test_a_layer_without_pubinfo_still_reads() -> None:
    """The 2026-10-12 fixture predates the field. Losing a note is not the
    layer changing shape, so Missouri is not hidden (0019)."""
    data = json.loads(MO_POINTS.read_bytes())
    assert "PubInfo" not in {f["name"] for f in data["fields"]}
    result = missouri.normalize(MO_POINTS.read_bytes(), dt.date(2026, 10, 12))
    assert result.rows_read == 278
    assert {r.public_info for r in result.records} == {""}


def test_history_keeps_the_note_and_old_histories_default_to_none() -> None:
    r = missouri._record(feature(), RUN)
    assert not isinstance(r, str)
    data = hist.record_to_json(r)
    assert data["public_info"] == HAGEN.strip()
    assert hist.record_from_json(r.id, data) == r
    del data["public_info"]
    assert hist.record_from_json(r.id, data).public_info == ""


def _water(*features: dict[str, Any]) -> dict[str, Any]:
    records = []
    for f in features:
        r = missouri._record(f, RUN)
        assert not isinstance(r, str)
        records.append(r)
    entries = [
        hist.HistoryEntry(record=r, first_seen="2026-11-05", last_seen="2026-11-05")
        for r in records
    ]
    (only,) = snapshot.build_waterbodies(entries, RUN)
    return only


def test_snapshot_carries_the_note_only_when_there_is_one() -> None:
    w = _water(feature(), feature(objectid=1, PubInfo=None, HABODat=1780000000000))
    by_id = {r["id"]: r for r in w["records"]}
    assert by_id["mo-37535"]["public_info"] == HAGEN.strip()
    assert "public_info" not in by_id["mo-1"]


def test_closed_note_for_one_closed_case() -> None:
    w = _water(feature())
    assert w["status"]["kind"] == "advisory"
    assert missouri.closed_note(w) == (
        "The department marked this case closed without a dissipation date."
    )


def test_no_closed_note_for_an_active_case() -> None:
    assert missouri.closed_note(_water(feature(CaseStatus="Active"))) is None


def test_no_closed_note_when_the_bloom_dissipated_on_a_date() -> None:
    w = _water(feature(BloomStat="dissap", DissDat=1791651600000))
    assert w["status"]["kind"] == "no_advisory_recorded"
    assert missouri.closed_note(w) is None


def test_closed_note_counts_cases_on_the_headline_date() -> None:
    a = feature(objectid=1, WBName="Twin Lake")
    b = feature(objectid=2, WBName="Twin Lake", CaseStatus="Active")
    c = feature(objectid=3, WBName="Twin Lake")
    assert missouri.closed_note(_water(a, b)) == (
        "The department marked 1 of these 2 cases closed without a dissipation date."
    )
    assert missouri.closed_note(_water(a, c)) == (
        "The department marked these 2 cases closed without a dissipation date."
    )


def test_closed_note_is_missouri_only() -> None:
    w = _water(feature())
    assert missouri.closed_note({**w, "state": "CA"}) is None
    assert missouri.department_notes({**w, "state": "CA"}) == []


def test_department_notes_skip_the_placeholder_and_blanks() -> None:
    w = _water(
        feature(objectid=1),
        feature(objectid=2, PubInfo="No additional information", HABODat=1780000000000),
        feature(
            objectid=3, PubInfo="No additional information.", HABODat=1770000000000
        ),
        feature(objectid=4, PubInfo=None, HABODat=1760000000000),
    )
    assert missouri.department_notes(w) == [
        {"date": "2026-09-26", "level": "Advisory (advise)", "text": HAGEN.strip()}
    ]


# -- the built site ----------------------------------------------------------


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The real 2026-10-12 layer, with PubInfo added to two of its cases:
    Blind Pony Lake (closed "advise", no dissipation date) and Eagles Parkway
    Trail Project (active "advise"). The Briars pond note is borrowed for the
    second, and markup in a note must come out as text."""
    tmp = tmp_path_factory.mktemp("pubinfo")
    data = json.loads(MO_POINTS.read_bytes())
    data["fields"].append({"name": "PubInfo", "type": "esriFieldTypeString"})
    notes = {37466: HAGEN, 37949: BRIARS + "<b>Signs</b> posted."}
    for f in data["features"]:
        f["attributes"]["PubInfo"] = notes.get(f["attributes"]["objectid"])
    layer = tmp / "mo.json"
    layer.write_text(json.dumps(data))
    assert cli.main([
        "--fixture-page", str(PAGE), "--fixture-csv", str(TRAPS), "--run-today", "2026-10-12",
        "--history", str(tmp / "h.json"), "--site-out", str(tmp / "site"),
        "--snapshot-out", str(tmp / "s.json"),
        "--mo-fixture", str(layer), "--cyan-cache", str(CYAN_CACHE),
    ]) == 0  # fmt: skip
    return tmp


def _page(built: Path, name: str) -> tuple[dict[str, Any], str, str]:
    snap = json.loads((built / "s.json").read_text())
    w = next(w for w in snap["waterbodies"] if w["name"] == name)
    path = built / "site" / "water" / w["id"] / "index.html"
    return w, path.read_text(encoding="utf-8"), text_of(path)


def test_the_page_quotes_the_note_and_credits_the_department(built: Path) -> None:
    w, raw, text = _page(built, "Blind Pony Lake")
    assert w["status"]["kind"] == "advisory"
    assert "In the department's words" in text
    assert f"“{HAGEN.strip()}”" in text
    assert "Quoted as the Missouri Department of Natural Resources published it" in text
    assert (
        'href="https://dnr.mo.gov/water/alerts-hazards/harmful-algal-bloom-hab-reports-map"'
        in raw
    )
    assert "A note does not change the status above." in text


def test_the_status_box_says_the_case_was_closed(built: Path) -> None:
    _, raw, _ = _page(built, "Blind Pony Lake")
    box = raw[raw.index('<div class="status') :]
    box = box[: box.index("</div>")]
    assert "The department marked this case closed without a dissipation date." in box


def test_an_active_case_gets_its_note_but_no_closed_line(built: Path) -> None:
    _, raw, text = _page(built, "Eagles Parkway Trail Project")
    assert BRIARS.strip() in text
    assert "closed without a dissipation date" not in text
    # Markup in the department's text is escaped, never rendered.
    assert "<b>Signs</b>" not in raw
    assert html.escape("<b>Signs</b>") in raw


def test_negative_control_a_page_without_a_note_has_no_section(built: Path) -> None:
    snap = json.loads((built / "s.json").read_text())
    quiet = [
        w
        for w in snap["waterbodies"]
        if w["state"] == "MO" and not any(r.get("public_info") for r in w["records"])
    ]
    assert quiet
    for w in quiet[:20]:
        page = built / "site" / "water" / w["id"] / "index.html"
        assert "In the department's words" not in text_of(page), w["id"]
