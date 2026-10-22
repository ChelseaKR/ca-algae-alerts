"""docs/MISSOURI-READINGS.md lists the Missouri readings the owner confirms.

The table in that file must say what missouri.py does. The checker builds one
case per row, runs it through the real normalizer and compares the tier and
the label; a sabotaged copy of the table must be reported (after asserting the
sabotage applied).
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

from caalgae import missouri

DOC = Path(__file__).resolve().parents[2] / "docs" / "MISSOURI-READINGS.md"
RUN = dt.date(2026, 10, 12)
OBSERVED_MS = 1791046800000  # 2026-10-03, as test_missouri.py uses
DISSIPATED_MS = OBSERVED_MS + 3 * 86_400_000
TIER_BY_TEXT = {
    "`other_advisory`": "other_advisory",
    "`no_advisory`": "no_advisory",
    "`not_classified`": "not_classified",
    "`unknown`": "unknown",
}


def table_rows(text: str) -> list[tuple[str, str, str, str]]:
    rows = []
    in_table = False
    for line in text.splitlines():
        if line.startswith("| Code |"):
            in_table = True
            continue
        if not in_table:
            continue
        if not line.startswith("|"):
            break
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells[0].startswith("---"):
            continue
        rows.append((cells[0], cells[1], cells[2], cells[3]))
    return rows


def case(code: str, *, dissipated: bool) -> dict[str, Any]:
    attrs = {
        "objectid": 7, "WBName": "Test Lake", "HABODat": OBSERVED_MS,
        "BloomStat": code, "CaseStatus": "Closed",
        "DissDat": DISSIPATED_MS if dissipated else None,
    }  # fmt: skip
    return {"attributes": attrs, "geometry": {"x": -94.2, "y": 39.0}}


def problems(text: str) -> list[str]:
    found: list[str] = []
    rows = table_rows(text)
    if len(rows) != 9:
        found.append(f"expected 9 rows, found {len(rows)}")
    for cell, label, treated, record in rows:
        dissipated = "with a dissipation date" in cell
        code = "" if cell == "blank" else cell.split("`")[1] if "`" in cell else "other"
        if cell == "any other code":
            code = "zzzzzz"
        result = missouri._record(case(code, dissipated=dissipated), RUN)
        if isinstance(result, str):
            found.append(f"{cell}: quarantined ({result})")
            continue
        want_tier = next(v for k, v in TIER_BY_TEXT.items() if record.startswith(k))
        if result.tier != want_tier:
            found.append(f"{cell}: doc says {want_tier}, code gives {result.tier}")
        if code in missouri.LABELS and label != missouri.level_label(code):
            found.append(
                f"{cell}: doc label {label!r}, code {missouri.level_label(code)!r}"
            )
        if ("an advisory" in treated) != (code in missouri.ADVISORY_CODES):
            found.append(f"{cell}: advisory reading disagrees with ADVISORY_CODES")
    return found


def test_the_doc_matches_the_code() -> None:
    text = DOC.read_text(encoding="utf-8")
    assert problems(text) == []
    assert "closed-case rule" in text.casefold()
    assert "not** an" in text  # a closed case is not an end


def test_a_wrong_reading_is_caught() -> None:
    text = DOC.read_text(encoding="utf-8")
    sabotaged = text.replace(
        "| `notthr` | Below threshold (notthr) | decides nothing | `not_classified` |",
        "| `notthr` | Below threshold (notthr) | an advisory | `other_advisory` |",
    )
    assert sabotaged != text  # the sabotage applied
    found = problems(sabotaged)
    assert any(p.startswith("`notthr`") for p in found), found
