from __future__ import annotations

import json
from pathlib import Path

import pytest
from paths import PAGE, SAMPLE, TRAPS

from caalgae import cli


def args(tmp_path: Path, csv: Path = TRAPS, *extra: str) -> list[str]:
    return [
        "--fixture-page",
        str(PAGE),
        "--fixture-csv",
        str(csv),
        "--run-today",
        "2026-10-12",
        "--history",
        str(tmp_path / "history.json"),
        "--snapshot-out",
        str(tmp_path / "snapshot.json"),
        *extra,
    ]


def test_offline_run_writes_history_and_snapshot(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(args(tmp_path)) == 0
    snap = json.loads((tmp_path / "snapshot.json").read_text())
    assert snap["source_file"]["file_name"] == "hab-responses_2026-10-09.csv"
    history = json.loads((tmp_path / "history.json").read_text())
    assert len(history["records"]) == 14
    out = capsys.readouterr().out
    assert "quarantined 1 row(s): missing water body name" in out


def test_second_run_is_idempotent(tmp_path: Path) -> None:
    assert cli.main(args(tmp_path)) == 0
    first = (tmp_path / "snapshot.json").read_text()
    assert cli.main(args(tmp_path)) == 0
    assert (tmp_path / "snapshot.json").read_text() == first


def test_real_sample_runs(tmp_path: Path) -> None:
    assert cli.main(args(tmp_path, SAMPLE)) == 0
    snap = json.loads((tmp_path / "snapshot.json").read_text())
    names = {w["name"] for w in snap["waterbodies"]}
    assert "Lake Temescal" in names


def test_older_file_than_last_run_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(args(tmp_path)) == 0
    history = json.loads((tmp_path / "history.json").read_text())
    history["files"][-1]["file_date"] = "2026-10-10"
    (tmp_path / "history.json").write_text(json.dumps(history))
    (tmp_path / "snapshot.json").unlink()
    assert cli.main(args(tmp_path)) == 2
    assert "run refused -- nothing published" in capsys.readouterr().err
    assert not (tmp_path / "snapshot.json").exists()


def test_file_dated_in_the_future_is_refused(tmp_path: Path) -> None:
    a = args(tmp_path)
    a[a.index("--run-today") + 1] = "2026-10-01"
    assert cli.main(a) == 2
    assert not (tmp_path / "history.json").exists()


def test_stale_file_warns_but_publishes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    a = args(tmp_path)
    a[a.index("--run-today") + 1] = "2026-11-30"
    assert cli.main(a) == 0
    assert "WARNING" in capsys.readouterr().err


def test_fixture_flags_go_together(tmp_path: Path) -> None:
    assert (
        cli.main(["--fixture-page", str(PAGE), "--history", str(tmp_path / "h.json")])
        == 2
    )


def test_shape_error_is_a_refusal(tmp_path: Path) -> None:
    bad = tmp_path / "bad.csv"
    bad.write_text("a,b\n1,2\n")
    assert cli.main(args(tmp_path, bad)) == 2
    assert not (tmp_path / "history.json").exists()
