"""scripts/check_publish_health.py and .github/workflows/publish-health.yml.

No network: the fetch is a function the tests replace. The clock is a fixed
instant, and the snapshot is built here, never read from the daily-rewritten
data files. Each negative control asserts its sabotage changed the input
before it asserts the check noticed. The workflow is read as text (the
project carries no YAML parser).
"""

from __future__ import annotations

import copy
import datetime as dt
import importlib.util
import json
import re
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any

import httpx
import pytest

from caalgae import cli

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "check_publish_health.py"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "publish-health.yml"
PUBLISH = REPO_ROOT / ".github" / "workflows" / "publish.yml"
SCHEMA = REPO_ROOT / "schema" / "snapshot.v1.json"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_publish_health", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


ph = _load()
# 19:23 UTC, the scheduled check, on a day whose 14:41 publish deployed.
NOW = dt.datetime(2026, 11, 19, 19, 23, tzinfo=dt.UTC)


def _iso(when: dt.datetime) -> str:
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


def healthy() -> dict[str, Any]:
    """The live snapshot's shape on 2026-11-19, cut to what the check reads."""
    return {
        "generated_at": "2026-11-19T14:44:52Z",
        "run_date": "2026-11-19",
        "state_status": [
            {
                "state": "CA",
                "source": "ca-swrcb-fhab",
                "mode": "live",
                "last_read": "2026-11-19",
                "since": None,
                "reason": None,
            },
            {
                "state": "MO",
                "source": "mo-dnr-hab",
                "mode": "live",
                "last_read": "2026-11-19",
                "since": None,
                "reason": None,
            },
        ],
        "source_files": [
            {"source": "ca-swrcb-fhab", "file_date": "2026-11-18"},
            {"source": "mo-dnr-hab", "file_date": "2026-11-19"},
        ],
    }


def keys(snapshot: object) -> set[str]:
    return {f.key for f in ph.evaluate(snapshot, NOW)}


def mo(snapshot: dict[str, Any]) -> dict[str, Any]:
    entry: dict[str, Any] = snapshot["state_status"][1]
    return entry


def test_a_healthy_snapshot_has_no_findings() -> None:
    assert ph.evaluate(healthy(), NOW) == []
    assert ph.state_key([]) == ""


def test_the_thresholds_are_the_documented_constants() -> None:
    assert ph.STALE_PUBLISH_HOURS == 24
    assert ph.STATE_STALE_DAYS == 2
    assert ph.CA_FILE_MAX_AGE_DAYS == 7


def test_the_thresholds_follow_the_pipelines_own_rules() -> None:
    # A state is shown dated for MO_STALE_AFTER_DAYS, then goes unavailable;
    # the site starts saying California's file is old after STALE_AFTER_DAYS.
    assert ph.STATE_STALE_DAYS == cli.MO_STALE_AFTER_DAYS
    assert ph.CA_FILE_MAX_AGE_DAYS == cli.STALE_AFTER_DAYS


def test_publish_age_boundary() -> None:
    snap = healthy()
    snap["generated_at"] = _iso(NOW - dt.timedelta(hours=ph.STALE_PUBLISH_HOURS))
    assert keys(snap) == set()
    snap["generated_at"] = _iso(
        NOW - dt.timedelta(hours=ph.STALE_PUBLISH_HOURS, minutes=1)
    )
    assert keys(snap) == {"publish-stale"}


def test_one_missed_daily_run_is_caught_the_same_day() -> None:
    # The 14:41 run on the 19th never deployed; the last good one was the 18th.
    snap = healthy()
    snap["generated_at"] = "2026-11-18T14:44:20Z"
    stale = NOW - dt.datetime(2026, 11, 18, 14, 44, 20, tzinfo=dt.UTC)
    assert stale > dt.timedelta(hours=ph.STALE_PUBLISH_HOURS)
    # The states were read on the day the snapshot was built, so only the
    # publish itself is a finding, not every state with it.
    snap["state_status"][0]["last_read"] = "2026-11-18"
    mo(snap)["last_read"] = "2026-11-18"
    snap["source_files"][0]["file_date"] = "2026-11-17"
    found = ph.evaluate(snap, NOW)
    assert [f.key for f in found] == ["publish-stale"]
    assert "29 hours old" in found[0].text


def test_a_lagging_late_start_is_not_a_finding() -> None:
    # The scheduled publish started 3 hours late and deployed before 19:23.
    snap = healthy()
    snap["generated_at"] = "2026-11-19T17:48:00Z"
    assert keys(snap) == set()


def test_an_unavailable_state_is_a_finding() -> None:
    snap = healthy()
    mo(snap).update(
        mode="unavailable",
        since="2026-11-17",
        last_read="2026-11-14",
        reason="gone: HTTP 404 <script>",
    )
    found = ph.evaluate(snap, NOW)
    assert [f.key for f in found] == ["MO-unavailable"]
    assert "since 2026-11-17 (last read 2026-11-14)" in found[0].text
    assert "script" not in found[0].text


def test_a_passing_failure_inside_the_pipelines_window_is_not_a_finding() -> None:
    snap = healthy()
    mo(snap).update(mode="stale_dated", last_read="2026-11-17")
    assert keys(snap) == set()


def test_a_state_past_the_window_but_not_marked_unavailable_is_a_finding() -> None:
    snap = healthy()
    mo(snap).update(mode="stale_dated", last_read="2026-11-16")
    found = ph.evaluate(snap, NOW)
    assert [f.key for f in found] == ["MO-stale"]
    assert "3 days before" in found[0].text
    # The same age on a state labelled live is caught the same way.
    mo(snap).update(mode="live")
    assert keys(snap) == {"MO-stale"}


def test_ca_file_age_boundary() -> None:
    snap = healthy()
    built = dt.date(2026, 11, 19)
    snap["source_files"][0]["file_date"] = (
        built - dt.timedelta(days=ph.CA_FILE_MAX_AGE_DAYS)
    ).isoformat()
    assert keys(snap) == set()
    snap["source_files"][0]["file_date"] = (
        built - dt.timedelta(days=ph.CA_FILE_MAX_AGE_DAYS + 1)
    ).isoformat()
    assert keys(snap) == {"ca-file-old"}


Mutation = Callable[[dict[str, Any]], object]


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (lambda s: s.pop("generated_at"), "generated-missing"),
        (lambda s: s.update(generated_at="yesterday"), "generated-missing"),
        (lambda s: s.update(generated_at="2026-11-19T14:44:52"), "generated-missing"),
        (lambda s: s.pop("state_status"), "states-missing"),
        (lambda s: s.update(state_status=[]), "states-missing"),
        (lambda s: s["state_status"].pop(0), "ca-missing"),
        (lambda s: s["state_status"][0].update(state="ca"), "state-code"),
        (lambda s: s["state_status"].append("MO"), "state-code"),
        (lambda s: s["state_status"][1].update(mode="frozen"), "MO-mode"),
        (lambda s: s["state_status"][1].pop("mode"), "MO-mode"),
        (lambda s: s["state_status"][1].update(last_read=None), "MO-last-read"),
        (lambda s: s["state_status"][1].update(last_read="11/19"), "MO-last-read"),
        (lambda s: s.pop("source_files"), "ca-file-missing"),
        (lambda s: s["source_files"].pop(0), "ca-file-missing"),
        (lambda s: s["source_files"][0].pop("file_date"), "ca-file-date"),
    ],
)
def test_absence_is_a_finding_never_a_pass(mutate: Mutation, expected: str) -> None:
    snap = healthy()
    before = copy.deepcopy(snap)
    mutate(snap)
    assert snap != before, "the sabotage did not apply"
    assert expected in keys(snap)


def test_an_unavailable_state_with_unreadable_dates_is_still_named() -> None:
    snap = healthy()
    mo(snap).update(mode="unavailable", since=None, last_read=None)
    found = ph.evaluate(snap, NOW)
    assert [f.key for f in found] == ["MO-unavailable"]
    assert "an unreadable date" in found[0].text


@pytest.mark.parametrize("bad", [None, [], "x", 3])
def test_a_snapshot_that_is_not_an_object_is_a_finding(bad: object) -> None:
    assert keys(bad) == {"snapshot-shape"}


def test_fetch_retries_then_reports_the_site_down() -> None:
    calls: list[str] = []

    def down(url: str) -> bytes:
        calls.append(url)
        raise httpx.ConnectError("refused")

    found = ph.check("https://example.test/snapshot/v1.json", NOW, down)
    assert [f.key for f in found] == ["fetch"]
    assert len(calls) == ph.FETCH_ATTEMPTS


def test_fetch_recovers_on_a_later_attempt() -> None:
    answers: list[Exception | bytes] = [
        httpx.ConnectError("blip"),
        json.dumps(healthy()).encode(),
    ]

    def flaky(url: str) -> bytes:
        item = answers.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    assert ph.check("https://example.test/s.json", NOW, flaky) == []


def test_a_body_that_is_not_json_is_a_finding() -> None:
    found = ph.check("https://example.test/s.json", NOW, lambda u: b"<html>")
    assert [f.key for f in found] == ["snapshot-json"]


def test_a_stale_body_through_the_whole_path() -> None:
    snap = healthy()
    snap["generated_at"] = "2026-11-01T00:00:00Z"
    found = ph.check("https://e.test/s.json", NOW, lambda u: json.dumps(snap).encode())
    assert [f.key for f in found] == ["publish-stale"]


def test_http_fetch_sends_an_identifying_user_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["ua"] = request.headers["User-Agent"]
        return httpx.Response(200, content=b"{}")

    real = httpx.Client

    def client(**kwargs: Any) -> httpx.Client:
        return real(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(ph.httpx, "Client", client)
    assert ph.http_fetch("https://e.test/snapshot/v1.json") == b"{}"
    assert seen["ua"] == ph.USER_AGENT
    assert "lakenotice" in ph.USER_AGENT


def test_snapshot_url_accepts_https_only_and_defaults() -> None:
    assert ph.snapshot_url("") == "https://lakenotice.com/snapshot/v1.json"
    assert (
        ph.snapshot_url("https://lakenotice.com/")
        == "https://lakenotice.com/snapshot/v1.json"
    )
    for bad in (
        "http://lakenotice.com",
        "https://user:pw@lakenotice.com",
        "https://lakenotice.com/?a=1",
        "file:///etc/passwd",
        "lakenotice.com",
    ):
        with pytest.raises(ValueError):
            ph.snapshot_url(bad)


def test_the_report_holds_only_fixed_text_and_numbers() -> None:
    snap = healthy()
    mo(snap).update(
        mode="unavailable",
        since="2026-11-17",
        last_read="2026-11-14",
        reason="<script>alert(1)</script> @everyone",
        source="@everyone",
    )
    text = ph.report(ph.evaluate(snap, NOW), "https://e.test/s.json", NOW)
    assert "script" not in text and "@everyone" not in text
    assert "MO's data is unavailable since 2026-11-17" in text


def test_the_state_key_is_sorted_unique_and_in_the_report() -> None:
    findings = [
        ph.Finding("publish-stale", "a"),
        ph.Finding("MO-unavailable", "b"),
        ph.Finding("publish-stale", "c"),
    ]
    assert ph.state_key(findings) == "MO-unavailable,publish-stale"
    text = ph.report(findings, "https://e.test/s.json", NOW)
    assert "<!-- publish-health-state: MO-unavailable,publish-stale -->" in text


def test_the_state_key_ignores_numbers_that_grow_each_day() -> None:
    # A snapshot one day staler is the same state: no new comment.
    day_one, day_two = healthy(), healthy()
    day_one["generated_at"] = "2026-11-18T14:44:20Z"
    day_two["generated_at"] = "2026-11-17T14:44:20Z"
    one, two = ph.evaluate(day_one, NOW), ph.evaluate(day_two, NOW)
    assert one[0].text != two[0].text
    assert ph.state_key(one) == ph.state_key(two)


def test_main_exit_codes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out, state = tmp_path / "r.md", tmp_path / "state"
    argv = ["--out", str(out), "--state-out", str(state)]
    monkeypatch.setattr(ph, "check", lambda url, now: [])
    assert ph.main(argv) == 0
    assert not out.exists()
    assert state.read_text(encoding="utf-8") == "\n"
    monkeypatch.setattr(ph, "check", lambda url, now: [ph.Finding("k", "Something.")])
    assert ph.main(argv) == 1
    assert "Something." in out.read_text(encoding="utf-8")
    assert state.read_text(encoding="utf-8") == "k\n"
    assert ph.main(["--base-url", "http://x", *argv]) == 2


def test_the_fields_read_are_in_the_data_contract() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    props = schema["properties"]
    assert "generated_at" in schema["required"]
    entry = props["state_status"]["items"]["properties"]
    assert {"state", "mode", "last_read", "since"} <= set(entry)
    assert tuple(entry["mode"]["enum"]) == ph.MODES
    file_ref = props["source_files"]["items"]["$ref"].rsplit("/", 1)[-1]
    assert {"source", "file_date"} <= set(schema["$defs"][file_ref]["properties"])


# ---- the workflow's shape ------------------------------------------------


def _wf() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def _uses_lines(text: str) -> list[str]:
    return [m.group(0) for m in re.finditer(r"uses: \S+", text)]


def _run_bodies(text: str) -> list[str]:
    return re.findall(r"run: \|\n((?:          .*\n|\n)+)", text)


def test_every_action_is_pinned_to_a_full_sha() -> None:
    uses = _uses_lines(_wf())
    assert uses
    for line in uses:
        assert re.fullmatch(r"uses: [\w./-]+@[0-9a-f]{40}", line), line


def test_pin_check_catches_a_tag() -> None:
    sabotaged = _wf().replace("@93cb6efe18208431cddfb8368fd83d5badbf9bfd", "@v5")
    assert sabotaged != _wf()
    assert any(
        not re.fullmatch(r"uses: [\w./-]+@[0-9a-f]{40}", u)
        for u in _uses_lines(sabotaged)
    )


def test_permissions_are_least_privilege() -> None:
    text = _wf()
    top = text[: text.index("jobs:")]
    assert "permissions:\n  contents: read\n" in top
    job = text[text.index("jobs:") :]
    assert "issues: write" in job
    for forbidden in ("contents: write", "actions:", "pull-requests:", "id-token"):
        assert forbidden not in text


def test_no_expression_is_interpolated_into_a_run_script() -> None:
    bodies = _run_bodies(_wf())
    assert len(bodies) == 2
    for body in bodies:
        assert "${{" not in body


def test_interpolation_check_catches_an_expression() -> None:
    text = _wf().replace('"$SITE_BASE_URL"', '"${{ vars.SITE_BASE_URL }}"')
    assert text != _wf()
    assert any("${{" in b for b in _run_bodies(text))


def test_one_fixed_title_one_label_and_a_body_file() -> None:
    text = _wf()
    assert text.count("ISSUE_TITLE:") == 1
    assert "--label bug" in text
    assert "--body-file" in text and "--body " not in text
    assert text.count("gh issue create") == 1


def _issue_step() -> str:
    bodies = _run_bodies(_wf())
    return next(b for b in bodies if "gh issue" in b)


def test_the_workflow_reads_back_the_marker_the_script_writes() -> None:
    step = _issue_step()
    prefix = ph.STATE_MARKER.split("{}")[0]
    assert prefix in step
    # The capture accepts every character a finding key can hold.
    assert "(?<s>[A-Za-z0-9,-]*)" in step
    broken = healthy()
    broken.pop("generated_at")
    broken["state_status"].append({"state": "x"})
    mo(broken).update(mode="unavailable")
    broken["source_files"][0].pop("file_date")
    found = ph.evaluate(broken, NOW)
    assert len(found) == 4
    assert re.fullmatch(r"[A-Za-z0-9,-]+", ph.state_key(found))


def comment_problems(step: str) -> list[str]:
    """What breaks 'comment only when the state changes'."""
    found: list[str] = []
    lines = [line.strip() for line in step.splitlines()]
    try:
        guard = lines.index('if [ "$previous" = "$current" ]; then')
    except ValueError:
        return ["the unchanged-state guard is missing"]
    after = lines[guard:]
    if "exit 0" not in after[: after.index("fi")]:
        found.append("an unchanged state does not stop before commenting")
    comments = [i for i, line in enumerate(lines) if "gh issue comment" in line]
    healthy_end = lines.index("exit 0")
    late = [i for i in comments if i > healthy_end]
    if not late or min(late) < guard:
        found.append("an unhealthy comment is posted before the guard")
    return found


def test_an_unchanged_unhealthy_state_gets_no_comment() -> None:
    assert comment_problems(_issue_step()) == []


def test_a_comment_before_the_guard_is_caught() -> None:
    step = _issue_step()
    sabotaged = step.replace(
        '          if [ -z "$existing" ]; then\n',
        '          gh issue comment "$existing" --body-file "$report"\n'
        '          if [ -z "$existing" ]; then\n',
        1,
    )
    assert sabotaged != step
    assert "an unhealthy comment is posted before the guard" in comment_problems(
        sabotaged
    )


def test_a_missing_guard_is_caught() -> None:
    step = _issue_step()
    sabotaged = step.replace('if [ "$previous" = "$current" ]; then', "if false; then")
    assert sabotaged != step
    assert comment_problems(sabotaged) == ["the unchanged-state guard is missing"]


def test_recovery_comments_and_closes() -> None:
    step = _issue_step()
    assert 'gh issue close "$existing"' in step
    assert step.index('if [ "$HEALTHY" = "true" ]') < step.index("gh issue close")


def test_the_open_issue_is_found_by_listing_not_search() -> None:
    step = _issue_step()
    assert "gh issue list --state open" in step
    assert "--search" not in step


def test_schedule_runs_after_the_publish_and_is_not_on_the_hour() -> None:
    cron = re.search(r'cron: "(\d+) (\d+) \* \* \*"', _wf())
    assert cron
    minute, hour = int(cron.group(1)), int(cron.group(2))
    publish = re.search(r'cron: "(\d+) (\d+) \* \* \*"', PUBLISH.read_text())
    assert publish
    gap = (hour * 60 + minute) - (int(publish.group(2)) * 60 + int(publish.group(1)))
    # Long enough for the publish to deploy; short enough that a healthy
    # snapshot is far under the limit at check time.
    assert 2 * 60 <= gap <= (ph.STALE_PUBLISH_HOURS - 12) * 60
    assert minute not in (0, 30)
