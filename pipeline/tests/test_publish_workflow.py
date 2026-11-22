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
    if "workflow_dispatch: {}" not in lines and "workflow_dispatch:" not in lines:
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


GUARD = "uv run python -m caalgae.publish_guard --site-dir ../site \\"


def guard_problems(text: str) -> list[str]:
    """The publish guard (DECISIONS 0024) runs before anything is committed
    or uploaded, and its override reaches it."""
    lines = code_lines(text)
    found: list[str] = []
    if GUARD not in lines:
        return ["the publish guard step is missing"]
    at = lines.index(GUARD)
    for later in (
        "- name: commit updated history, if any",
        "uses: actions/upload-pages-artifact@56afc609e74202658d3ffba0e8f6dda462b719fa # v3.0.1",
    ):
        if later not in lines or lines.index(later) < at:
            found.append(f"the guard does not run before {later!r}")
    if "ALLOW_PAGE_DROP: ${{ inputs.allow_page_drop }}" not in lines:
        found.append("the allow_page_drop override does not reach the guard")
    return found


def test_the_publish_guard_runs_before_commit_and_upload() -> None:
    assert guard_problems(WORKFLOW.read_text(encoding="utf-8")) == []


def test_a_guard_moved_after_the_upload_is_caught() -> None:
    before = WORKFLOW.read_text(encoding="utf-8")
    after = before.replace(GUARD, "true")
    assert after != before  # the sabotage applied
    assert guard_problems(after) == ["the publish guard step is missing"]
    moved = before.replace(GUARD, "true") + "\n" + GUARD + "\n"
    assert any("does not run before" in p for p in guard_problems(moved))


def tripwire_problems(text: str) -> list[str]:
    """The tripwire's override reaches the pipeline, and its refusal reaches
    the publish-failure issue (DECISIONS 0044)."""
    lines = code_lines(text)
    found: list[str] = []
    for needle, what in (
        ("accept_status_change:", "the accept_status_change input is missing"),
        (
            "ACCEPT_STATUS_CHANGE: ${{ inputs.accept_status_change == true }}",
            "the accept_status_change input does not reach the pipeline step",
        ),
        (
            'if [ "$ACCEPT_STATUS_CHANGE" = "true" ]; then '
            'accept_change="--accept-status-change"; fi',
            "the override is not turned into --accept-status-change",
        ),
        ('${accept_change:+"$accept_change"}', "the flag is not passed to caalgae"),
        (
            "pipeline_reason: ${{ steps.pipeline.outputs.reason }}",
            "the refusal's reason is not a job output",
        ),
        (
            "PIPELINE_REASON: ${{ needs.build.outputs.pipeline_reason }}",
            "the refusal's reason does not reach the publish-failure issue",
        ),
    ):
        if needle not in lines:
            found.append(what)
    name = "- name: run the pipeline (live fetch -> history -> snapshot -> site)"
    if name not in lines or lines[lines.index(name) + 1] != "id: pipeline":
        found.append("the pipeline step has no id for its reason output")
    # Off unless the owner turns it on for one manual run.
    at = (
        lines.index("accept_status_change:") if "accept_status_change:" in lines else -1
    )
    if at >= 0 and lines[at + 1 : at + 4][-1] != "default: false":
        found.append("accept_status_change is not off by default")
    return found


def test_the_tripwire_override_and_reason_are_wired() -> None:
    assert tripwire_problems(WORKFLOW.read_text(encoding="utf-8")) == []


def test_an_unwired_tripwire_override_is_caught() -> None:
    before = WORKFLOW.read_text(encoding="utf-8")
    for old, new, expected in (
        (
            '${accept_change:+"$accept_change"}',
            "",
            "the flag is not passed to caalgae",
        ),
        (
            "        id: pipeline\n",
            "",
            "the pipeline step has no id for its reason output",
        ),
        (
            "ACCEPT_STATUS_CHANGE: ${{ inputs.accept_status_change == true }}",
            "ACCEPT_STATUS_CHANGE: true",
            "the accept_status_change input does not reach the pipeline step",
        ),
    ):
        after = before.replace(old, new)
        assert after != before  # the sabotage applied
        assert expected in tripwire_problems(after)
