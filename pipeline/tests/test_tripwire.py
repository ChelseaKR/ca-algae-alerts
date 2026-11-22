"""A well-formed file that changes too many statuses at once is refused
(docs/DECISIONS.md 0044).

These run on the committed history.json, like test_ca_short_file.py. Each
sabotaged file keeps every record id, so nothing is withdrawn and nothing
is quarantined: the older guards (0027) pass it, which each test shows
first, and only the tripwire refuses it. Each limit is tested at its
boundary, and the unchanged file passes.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
from collections import Counter
from collections.abc import Callable
from pathlib import Path

import pytest

from caalgae import cli, fetch, missouri, normalize, snapshot, tripwire
from caalgae import history as hist
from caalgae import status as st
from caalgae.sources import CA_SWRCB_FHAB, MO_DNR_HAB

HISTORY = Path(__file__).resolve().parents[1] / "data" / "history.json"
CA = CA_SWRCB_FHAB.id
MO = MO_DNR_HAB.id


@pytest.fixture(scope="module")
def real() -> hist.History:
    return hist.load(HISTORY)


@pytest.fixture(scope="module")
def run_date(real: hist.History) -> dt.date:
    """The day after the committed file, so the tests follow the data."""
    last = real.last_file_date(CA)
    assert last is not None
    return last + dt.timedelta(days=1)


def _active(h: hist.History, source: str) -> list[normalize.Record]:
    return [
        e.record for e in h.entries.values() if e.active and e.record.source == source
    ]


def _info(source: str, run_date: dt.date) -> dict[str, object]:
    return {"file_date": run_date.isoformat(), "source": source}


def _merge(
    h: hist.History, records: list[normalize.Record], source: str, run_date: dt.date
) -> hist.History:
    """The merge as a California run does it, every 0027 limit on."""
    strict = source == CA
    return hist.merge(
        h,
        records,
        run_date=run_date,
        file_info=_info(source, run_date),
        max_removed=hist.MAX_REMOVED_RECORDS if strict else None,
        protect_advisories=strict,
    )


def _waters(h: hist.History, source: str, run_date: dt.date) -> dict[str, list[str]]:
    """Water id -> the keys of the waters under an advisory, by record
    water_key, so a test can edit one water's records."""
    out: dict[str, list[str]] = {}
    built = snapshot.build_waterbodies(
        (e for e in h.entries.values() if e.record.source == source), run_date
    )
    by_id = {str(w["id"]): w for w in built}
    for e in h.entries.values():
        r = e.record
        if r.source != source:
            continue
        water = snapshot.water_id(r.state, r.county_text, r.water_name)
        if water in by_id and by_id[water]["status"]["kind"] == st.ADVISORY:
            out.setdefault(water, [])
            if r.water_key not in out[water]:
                out[water].append(r.water_key)
    return out


def _none(record: normalize.Record) -> normalize.Record:
    """The same record, id and all, saying no advisory is recommended."""
    return dataclasses.replace(
        record, level="None", tier="no_advisory", explicit_no_advisory=True
    )


def _edit_waters(
    records: list[normalize.Record],
    keys: set[str],
    edit: Callable[[normalize.Record], normalize.Record],
) -> list[normalize.Record]:
    return [edit(r) if r.water_key in keys and r.is_advisory else r for r in records]


def _keys(under: dict[str, list[str]], count: int) -> set[str]:
    """The record water_keys of ``count`` waters that are each one key."""
    single = [keys[0] for keys in under.values() if len(keys) == 1]
    assert len(single) >= count
    return set(single[:count])


# -- the unchanged file ------------------------------------------------------


def test_the_real_file_unchanged_is_no_change(
    real: hist.History, run_date: dt.date
) -> None:
    """Negative control: today's data merged again changes no status."""
    for source, label in ((CA, "California's file"), (MO, "Missouri's layer")):
        merged = _merge(real, _active(real, source), source, run_date)
        change = tripwire.check(
            real, merged, source=source, label=label, run_date=run_date
        )
        assert change.dropped == ()
        assert change.before == change.after > 0


def test_the_limits_today(real: hist.History, run_date: dt.date) -> None:
    """The limits are a share with a floor; this pins what they come to on
    the committed data, where 0044 shows the arithmetic."""
    ca = tripwire.measure(real, real, source=CA, run_date=run_date)
    mo = tripwire.measure(real, real, source=MO, run_date=run_date)
    assert ca.drop_limit == int(0.05 * ca.before)
    assert ca.count_limit == int(0.10 * ca.before)
    assert ca.drop_limit > tripwire.MIN_DROP_WATERS, "California is past the floor"
    assert mo.drop_limit == tripwire.MIN_DROP_WATERS == 5
    assert mo.count_limit == tripwire.MIN_COUNT_WATERS == 25


# -- every level changed in place ---------------------------------------------


def test_every_advisory_edited_to_none_in_place_is_refused(
    real: hist.History, run_date: dt.date
) -> None:
    records = [_none(r) if r.is_advisory else r for r in _active(real, CA)]
    # The sabotage applies, and the older guards pass it: every id is still
    # there, so nothing is withdrawn.
    merged = _merge(real, records, CA, run_date)
    assert len(merged.active_records()) == len(real.active_records())
    change = tripwire.measure(real, merged, source=CA, run_date=run_date)
    assert change.before > change.drop_limit
    assert change.after == 0
    assert len(change.left) == change.before
    with pytest.raises(tripwire.MassChange) as refused:
        tripwire.check(
            real, merged, source=CA, label="California's file", run_date=run_date
        )
    message = str(refused.value)
    assert f"would take {change.before} of {change.before} waters out of an" in message
    assert f"the limit is {change.drop_limit}" in message
    assert "The last good data stays published" in message
    assert "accept_status_change" in message
    assert change.left[0] in message


def test_a_newer_none_for_every_report_is_refused(
    real: hist.History, run_date: dt.date
) -> None:
    """The other shape of the same file: nothing edited, one new "None"
    record after each report's current advisory."""
    live = hist._current_advisories(real.entries, CA)
    records = _active(real, CA)
    file_date = run_date - dt.timedelta(days=1)
    added = [
        dataclasses.replace(
            _none(r),
            id=str(90_000_000 + i),
            date=file_date,
            end_date=None,
            stamp=None,
        )
        for i, r in enumerate(r for r in records if r.id in live)
    ]
    merged = _merge(real, [*records, *added], CA, run_date)
    assert len(merged.active_records()) == len(real.active_records()) + len(added)
    with pytest.raises(tripwire.MassChange, match="out of an advisory"):
        tripwire.check(
            real, merged, source=CA, label="California's file", run_date=run_date
        )


# -- the drop limit, at its boundary ------------------------------------------


def test_waters_leaving_an_advisory_are_refused_one_past_the_limit(
    real: hist.History, run_date: dt.date
) -> None:
    under = _waters(real, CA, run_date)
    limit = tripwire.measure(real, real, source=CA, run_date=run_date).drop_limit
    records = _active(real, CA)

    def after(count: int) -> hist.History:
        edited = _edit_waters(records, _keys(under, count), _none)
        assert edited != records  # the sabotage applied
        return _merge(real, edited, CA, run_date)

    at = tripwire.check(
        real, after(limit), source=CA, label="California's file", run_date=run_date
    )
    assert len(at.left) == limit
    assert at.after == at.before - limit
    with pytest.raises(tripwire.MassChange, match=f"{limit + 1} in all"):
        tripwire.check(
            real,
            after(limit + 1),
            source=CA,
            label="California's file",
            run_date=run_date,
        )


def test_a_lowered_level_counts_as_a_drop(
    real: hist.History, run_date: dt.date
) -> None:
    """Danger, Warning and Caution rewritten as the lowest advisory level:
    every water still has an advisory, so the count does not move, and the
    run is still refused."""
    records = _active(real, CA)

    def lowest(r: normalize.Record) -> normalize.Record:
        return dataclasses.replace(r, level="General Awareness", tier="other_advisory")

    edited = [
        lowest(r) if r.tier in ("danger", "warning", "caution") else r for r in records
    ]
    merged = _merge(real, edited, CA, run_date)
    change = tripwire.measure(real, merged, source=CA, run_date=run_date)
    assert change.after == change.before, "no water left an advisory"
    assert change.left == ()
    assert len(change.lowered) > change.drop_limit
    with pytest.raises(tripwire.MassChange, match=r"out of an advisory and lower \d+"):
        tripwire.check(
            real, merged, source=CA, label="California's file", run_date=run_date
        )


# -- the count limit, at its boundary -----------------------------------------


def test_new_advisories_are_refused_one_past_the_count_limit(
    real: hist.History, run_date: dt.date
) -> None:
    under = _waters(real, CA, run_date)
    under_keys = {k for keys in under.values() for k in keys}
    limit = tripwire.measure(real, real, source=CA, run_date=run_date).count_limit
    records = _active(real, CA)
    # One existing record from each of enough waters with no advisory, to
    # copy as a new Danger posted on the file's date.
    seeds: dict[str, normalize.Record] = {}
    for r in records:
        if r.water_key not in under_keys:
            seeds.setdefault(r.water_key, r)
    assert len(seeds) > limit + 1

    def after(count: int) -> hist.History:
        added = [
            dataclasses.replace(
                r,
                id=str(91_000_000 + i),
                level="Danger",
                tier="danger",
                explicit_no_advisory=False,
                date=run_date - dt.timedelta(days=1),
                end_date=None,
                stamp=None,
            )
            for i, r in enumerate(list(seeds.values())[:count])
        ]
        return _merge(real, [*records, *added], CA, run_date)

    at = tripwire.check(
        real, after(limit), source=CA, label="California's file", run_date=run_date
    )
    assert at.after == at.before + limit
    assert at.dropped == ()
    with pytest.raises(tripwire.MassChange) as refused:
        tripwire.check(
            real,
            after(limit + 1),
            source=CA,
            label="California's file",
            run_date=run_date,
        )
    assert f"from {at.before} to {at.before + limit + 1}" in str(refused.value)
    assert f"the limit is {limit}" in str(refused.value)


# -- what is not a change, and the override ------------------------------------


def test_the_override_and_a_first_read_pass(
    real: hist.History, run_date: dt.date
) -> None:
    records = [_none(r) if r.is_advisory else r for r in _active(real, CA)]
    merged = _merge(real, records, CA, run_date)
    change = tripwire.check(
        real,
        merged,
        source=CA,
        label="California's file",
        run_date=run_date,
        accept=True,
    )
    assert change.after == 0, "the override lets the measured change through"
    # A source never read before has nothing to protect.
    first = hist.merge(
        hist.empty(),
        _active(real, CA),
        run_date=run_date,
        file_info=_info(CA, run_date),
    )
    tripwire.check(
        hist.empty(), first, source=CA, label="California's file", run_date=run_date
    )


def test_a_planned_end_date_passing_is_not_a_change(run_date: dt.date) -> None:
    """Both sides are read on the run date, so an advisory that ended by its
    own end date overnight is not something the file did."""
    posted = run_date - dt.timedelta(days=30)

    def record(n: int) -> normalize.Record:
        return normalize.Record(
            id=str(n),
            source=CA,
            state="CA",
            site_id=f"site-{n}",
            water_key=f"alameda|lake {n}",
            water_name=f"Lake {n}",
            county_text="Alameda",
            landmark="",
            lat=None,
            lon=None,
            date=posted,
            level="Caution",
            tier="caution",
            explicit_no_advisory=False,
            end_date=run_date - dt.timedelta(days=1),
            detail="",
            stamp=None,
        )

    records = [record(n) for n in range(1, 41)]
    before = hist.merge(
        hist.empty(), records, run_date=posted, file_info=_info(CA, posted)
    )
    after = hist.merge(
        before, records, run_date=run_date, file_info=_info(CA, run_date)
    )
    change = tripwire.check(
        before, after, source=CA, label="California's file", run_date=run_date
    )
    assert (change.before, change.after, change.dropped) == (0, 0, ())
    # The control: read the day before, all 40 were advisories, and the same
    # 40 edited to "None" in a file is a change and is refused.
    eve = run_date - dt.timedelta(days=2)
    assert tripwire.measure(before, before, source=CA, run_date=eve).before == 40
    flipped = hist.merge(
        before, [_none(r) for r in records], run_date=eve, file_info=_info(CA, eve)
    )
    with pytest.raises(tripwire.MassChange):
        tripwire.check(
            before, flipped, source=CA, label="California's file", run_date=eve
        )


# -- wired into the run --------------------------------------------------------


def _ca_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    real: hist.History,
    run_date: dt.date,
    records: list[normalize.Record],
) -> tuple[list[str], Path, Path]:
    """A run of the real CLI on a copy of the committed history, with the
    download and the CSV read replaced by ``records``. Missouri is left out."""
    history = tmp_path / "history.json"
    history.write_bytes(HISTORY.read_bytes())
    last = real.last_file(CA)
    assert last is not None
    source = fetch.SourceFile(
        url="https://example.invalid/f.csv", resource_id="r", file_date=run_date
    )
    download = fetch.Download(
        source,
        b"",
        dt.datetime(run_date.year, run_date.month, run_date.day, 15, tzinfo=dt.UTC),
    )
    monkeypatch.setattr(cli, "_download", lambda args, previous: download)
    monkeypatch.setattr(
        normalize,
        "normalize_csv",
        lambda body, file_date: normalize.Normalized(
            records=records,
            quarantine=Counter({"kept": int(last["quarantined"])}),
            rows_read=len(records),
        ),
    )
    monkeypatch.setattr(
        cli,
        "_missouri",
        lambda args, history, run_date, now: (history, Counter(), None),
    )
    out = tmp_path / "snapshot.json"
    argv = [
        "--history",
        str(history),
        "--snapshot-out",
        str(out),
        "--run-today",
        run_date.isoformat(),
        "--cyan-refresh",
        "never",
        "--cyan-cache",
        str(tmp_path / "no-cyan.json"),
    ]
    return argv, history, out


def test_the_run_is_refused_and_nothing_is_written(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    real: hist.History,
    run_date: dt.date,
) -> None:
    records = [_none(r) if r.is_advisory else r for r in _active(real, CA)]
    argv, history, out = _ca_run(tmp_path, monkeypatch, real, run_date, records)
    github_output = tmp_path / "github-output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(github_output))
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    assert cli.main(argv) == 2
    err = capsys.readouterr()
    assert (
        "caalgae: run refused -- nothing published: California's file would take"
        in err.err
    )
    assert "accept_status_change" in err.err
    # The last good data is untouched and nothing new was written.
    assert history.read_bytes() == HISTORY.read_bytes()
    assert not out.exists()
    # The reason reaches the workflow run and the job that opens the issue,
    # on one line.
    assert "::error title=Publish refused::California's file would take" in err.out
    reason = github_output.read_text(encoding="utf-8")
    assert reason.startswith("reason=California's file would take")
    assert reason.count("\n") == 1
    # The owner's override, after reading the file, lets the same file through.
    assert cli.main([*argv, "--accept-status-change"]) == 0
    assert out.exists()
    assert history.read_bytes() != HISTORY.read_bytes()


def test_the_real_file_runs_clean_through_the_cli(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    real: hist.History,
    run_date: dt.date,
) -> None:
    """Negative control for the wiring: the same harness, the data unchanged."""
    argv, _history, out = _ca_run(
        tmp_path, monkeypatch, real, run_date, _active(real, CA)
    )
    assert cli.main(argv) == 0
    assert out.exists()


def test_another_refusal_does_not_write_the_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only the tripwire's own message, which holds no text from a source,
    goes to the workflow's outputs."""
    github_output = tmp_path / "github-output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(github_output))
    assert cli.main(["--fixture-page", str(tmp_path / "missing.html")]) == 2
    assert not github_output.exists()


def _mo_record(n: int, day: dt.date) -> normalize.Record:
    return normalize.Record(
        id=f"mo-{n}",
        source=MO,
        state="MO",
        site_id=f"mo-{n}",
        water_key=f"mo||lake {n}",
        water_name=f"Lake {n}",
        county_text="",
        landmark=f"Lake {n}",
        lat=None,
        lon=None,
        date=day,
        level="Notice (notice)",
        tier="other_advisory",
        explicit_no_advisory=False,
        end_date=None,
        detail="",
        stamp=None,
        end_kind="dissipated",
    )


def test_missouri_past_the_limit_is_unavailable_and_california_goes_on(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    run_date: dt.date,
) -> None:
    """A Missouri answer over the limit never stops the run (0010): it is
    not merged, and Missouri reads "data unavailable" (0024)."""
    assert MO_DNR_HAB.enabled
    eve = run_date - dt.timedelta(days=1)
    records = [_mo_record(n, eve) for n in range(1, 13)]
    before = hist.merge(
        hist.empty(),
        records,
        run_date=eve,
        file_info={**_info(MO, eve), "fetched_at": f"{eve.isoformat()}T15:00:00Z"},
    )
    limit = tripwire.measure(before, before, source=MO, run_date=run_date).drop_limit
    assert limit == tripwire.MIN_DROP_WATERS < len(records) - 1

    def answer(count: int) -> normalize.Normalized:
        edited = [
            dataclasses.replace(
                r, level="Dissipated", tier="no_advisory", explicit_no_advisory=True
            )
            for r in records[:count]
        ] + records[count:]
        assert edited != records  # the sabotage applied
        return normalize.Normalized(
            records=edited, quarantine=Counter(), rows_read=len(edited)
        )

    fixture = tmp_path / "mo.json"
    fixture.write_bytes(b"{}")
    args = argparse.Namespace(
        mo_fixture=fixture,
        mo_viewer_fixture=None,
        fixture_page=None,
        accept_status_change=False,
    )
    now = dt.datetime(run_date.year, run_date.month, run_date.day, 15, tzinfo=dt.UTC)
    monkeypatch.setattr(missouri, "check_fresh", lambda records, run_date: None)

    monkeypatch.setattr(missouri, "normalize", lambda body, day: answer(limit))
    merged, _, mode = cli._missouri(args, before, run_date, now)
    assert mode is not None and mode.mode == snapshot.LIVE, "at the limit: merged"

    monkeypatch.setattr(missouri, "normalize", lambda body, day: answer(limit + 1))
    merged, _, mode = cli._missouri(args, before, run_date, now)
    assert mode is not None and mode.mode == snapshot.UNAVAILABLE
    assert mode.reason is not None
    assert mode.reason.startswith("suspect: Missouri's layer would take 6 of 12 waters")
    assert "accept_status_change" not in mode.reason, "the snapshot gets the count only"
    assert merged.entries == before.entries, "the answer was not merged"
    assert merged.outages[MO]["since"] == run_date.isoformat()
    warning = capsys.readouterr().err
    assert "Missouri not merged: Missouri's layer would take 6 of 12 waters" in warning
    assert "accept_status_change" in warning, "the run log says how to accept it"

    args.accept_status_change = True
    merged, _, mode = cli._missouri(args, before, run_date, now)
    assert mode is not None and mode.mode == snapshot.LIVE
    assert merged.entries != before.entries
