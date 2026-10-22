"""publish.yml: the daily schedule is present and Pages is still gated.

The workflow is read as text (the project carries no YAML parser). The
schedule must exist and be at 14:41 UTC; nothing may deploy, and no scheduled
run may start, while the PAGES_ENABLED variable is unset; and the workflow
itself must never set that variable. Each sabotage test first asserts the edit
changed the copy.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/publish.yml"
CRON = '- cron: "41 14 * * *"'
GATE = "vars.PAGES_ENABLED == 'true'"
SCHEDULE_GUARD = f"if: github.event_name != 'schedule' || {GATE}"


def code_lines(text: str) -> list[str]:
    """The workflow's lines with comments and blank lines removed."""
    out = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            out.append(stripped)
    return out


def problems(text: str) -> list[str]:
    lines = code_lines(text)
    found: list[str] = []
    if "schedule:" not in lines or CRON not in lines:
        found.append("the daily 14:41 UTC schedule line is missing")
    if "workflow_dispatch: {}" not in lines:
        found.append("manual dispatch is missing")
    if SCHEDULE_GUARD not in lines:
        found.append("a scheduled run is not gated on PAGES_ENABLED")
    # The Pages artifact and the deploy job stay behind the variable.
    for needle in (
        "if: vars.PAGES_ENABLED == 'true'",
        "if: vars.PAGES_ENABLED != 'true'",
    ):
        if needle not in lines:
            found.append(f"missing the Pages gate {needle!r}")
    if sum(1 for line in lines if line == "if: vars.PAGES_ENABLED == 'true'") != 2:
        found.append("the Pages artifact and the deploy job must both be gated")
    for line in lines:
        if line.startswith("PAGES_ENABLED:") or "gh variable set" in line:
            found.append(f"the workflow sets the Pages variable: {line}")
    return found


def test_schedule_is_present_and_pages_still_gated() -> None:
    assert problems(WORKFLOW.read_text(encoding="utf-8")) == []


def test_header_documents_the_daylight_saving_shift() -> None:
    header = "\n".join(
        line for line in WORKFLOW.read_text(encoding="utf-8").splitlines()
        if line.startswith("#")
    )  # fmt: skip
    assert "07:41 PDT" in header
    assert "06:41 PST" in header
    assert "2026-11-01" in header


def test_missing_schedule_is_caught() -> None:
    before = WORKFLOW.read_text(encoding="utf-8")
    after = before.replace(CRON, '- cron: "0 0 1 1 *"')
    assert after != before  # the sabotage applied
    assert "the daily 14:41 UTC schedule line is missing" in problems(after)


def test_ungated_schedule_is_caught() -> None:
    before = WORKFLOW.read_text(encoding="utf-8")
    after = before.replace(SCHEDULE_GUARD, "if: true")
    assert after != before  # the sabotage applied
    assert "a scheduled run is not gated on PAGES_ENABLED" in problems(after)


def test_ungated_deploy_is_caught() -> None:
    before = WORKFLOW.read_text(encoding="utf-8")
    marker = "    needs: build\n    if: vars.PAGES_ENABLED == 'true'\n"
    assert marker in before
    after = before.replace(marker, "    needs: build\n")
    assert after != before  # the sabotage applied
    assert any("both be gated" in p for p in problems(after)), problems(after)


def test_workflow_that_sets_the_variable_is_caught() -> None:
    before = WORKFLOW.read_text(encoding="utf-8")
    after = before + "      PAGES_ENABLED: true\n"
    assert after != before  # the sabotage applied
    assert any("sets the Pages variable" in p for p in problems(after))
