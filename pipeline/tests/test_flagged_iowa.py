"""The Iowa reader, built behind a flag that is off (DECISIONS 0038).

The two CSV fixtures under fixtures/states-invented/ are written by hand in
AQuIA's download format with invented beaches, site ids and results; no DNR
data is committed.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from test_flagged_states import ALL_FLAGS, INVENTED, RUN, build, build_args

from caalgae import cli, fetch, flagged, iowa, sources

IA_PAGES = [INVENTED / "ia-state.csv", INVENTED / "ia-countycity.csv"]
FLAG = "LN_ENABLE_IOWA"


@pytest.fixture(autouse=True)
def _flags_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    for flag in ALL_FLAGS:
        monkeypatch.delenv(flag, raising=False)


def pages() -> list[bytes]:
    return [p.read_bytes() for p in IA_PAGES]


def ia_records() -> dict[str, iowa.Record]:
    return {r.id: r for r in iowa.normalize(pages(), RUN).records}


def _csv(header: str, *rows: str) -> bytes:
    return ("\n".join((header, *rows)) + "\n").encode()


HEADER = IA_PAGES[1].read_text(encoding="utf-8").splitlines()[0]


# ---- the flag and the source -----------------------------------------------


@pytest.mark.parametrize("value", ["", "0"])
def test_unset_empty_and_zero_leave_iowa_off(value: str) -> None:
    assert flagged.enabled({FLAG: value}) == []


@pytest.mark.parametrize("value", ["yes", "true", " 1", "2"])
def test_any_other_iowa_value_refuses(value: str) -> None:
    with pytest.raises(flagged.FlagError, match=FLAG):
        flagged.enabled({FLAG: value})


def test_the_iowa_flag_turns_on_iowa_and_nothing_else() -> None:
    assert [r.state for r in flagged.enabled({FLAG: "1"})] == ["IA"]


def test_the_iowa_source_is_off_unlisted_and_its_license_unknown() -> None:
    source = flagged.READERS["IA"].source
    assert source is sources.IA_DNR_BEACHES
    assert source.enabled is False
    assert source.license.startswith("unknown")
    assert source.attribution == ""
    assert source.id not in sources.SOURCES
    assert source not in sources.enabled_sources()
    assert sources.FLAGGED_SOURCES[source.id] is source


# ---- a default build ---------------------------------------------------------


def test_a_default_build_is_byte_identical_with_or_without_the_iowa_reader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    with_iowa, printed = build(tmp_path / "with", capsys)
    assert "snapshot.json" in with_iowa
    monkeypatch.delitem(flagged.READERS, "IA")
    without, printed_without = build(tmp_path / "without", capsys)
    assert with_iowa == without
    assert printed == printed_without


def test_the_iowa_flag_set_to_zero_builds_the_same_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    default, _ = build(tmp_path / "default", capsys)
    monkeypatch.setenv(FLAG, "0")
    zero, _ = build(
        tmp_path / "zero", capsys, "--state-review-out", str(tmp_path / "r")
    )
    assert zero == default
    assert not (tmp_path / "r").exists()


def test_a_default_run_never_reaches_iowa(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def refuse(_client: object) -> list[bytes]:
        raise AssertionError("Iowa was fetched with its flag off")

    reader = flagged.READERS["IA"]
    monkeypatch.setitem(
        flagged.READERS,
        "IA",
        flagged.Reader(
            reader.state, reader.flag, reader.source, refuse, iowa.normalize
        ),
    )
    build(tmp_path, capsys)


def test_an_iowa_fixture_never_turns_iowa_on(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = cli.main(build_args(tmp_path, "--state-fixture", f"IA={IA_PAGES[0]}"))
    assert code == 2
    assert "its flag is off" in capsys.readouterr().err
    assert not (tmp_path / "history.json").exists()


def test_iowa_on_writes_a_review_file_and_publishes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    default, _ = build(tmp_path / "default", capsys)
    monkeypatch.setenv(FLAG, "1")
    review = tmp_path / "review"
    on, printed = build(
        tmp_path / "on",
        capsys,
        "--state-fixture",
        f"IA={IA_PAGES[0]}",
        "--state-fixture",
        f"IA={IA_PAGES[1]}",
        "--state-review-out",
        str(review),
    )
    assert on == default
    assert "IA review only, not published: 13 records from 18 rows" in printed
    doc = json.loads((review / "ia-review.json").read_text(encoding="utf-8"))
    assert doc["not_published"].startswith("Review only.")
    assert doc["flag"] == FLAG
    assert doc["source"]["license"].startswith("unknown")
    assert len(doc["records"]) == 13
    for name in on:
        assert "review" not in name


# ---- the reading: the sign alone never makes an algae advisory --------------


def test_a_not_recommended_sign_with_microcystin_over_8_is_an_advisory() -> None:
    records = ia_records()
    first = records["ia-99000001-2026-06-12-swimming-is-not-recommended"]
    assert (first.level, first.tier, first.state) == (
        "Swimming is Not Recommended",
        "other_advisory",
        "IA",
    )
    assert first.site_id == "ia-99000001"
    assert first.water_name == "Invented Lake Beach"
    assert (first.lat, first.lon) == (None, None)
    assert first.detail == "Microcystin 12.5 ug/L."
    second = records["ia-99000001-2026-06-19-swimming-is-not-recommended"]
    assert second.detail == (
        "Microcystin 9.1 ug/L. Algae toxin over the advisory threshold."
    )
    city = records["ia-99100001-2026-07-03-swimming-not-recommended"]
    assert (city.level, city.tier) == ("Swimming Not Recommended", "other_advisory")


@pytest.mark.parametrize(
    "record_id",
    [
        "ia-99000002-2026-07-10-swimming-is-not-recommended",  # bacteria, 0.4
        "ia-99000002-2026-07-17-swimming-is-not-recommended",  # no result
        "ia-99000003-2026-07-24-swimming-is-not-recommended",  # exactly 8
    ],
)
def test_a_not_recommended_sign_without_toxin_over_8_decides_nothing(
    record_id: str,
) -> None:
    record = ia_records()[record_id]
    assert record.tier == "not_classified"
    assert not record.is_advisory
    assert not record.explicit_no_advisory


def test_a_watch_sign_with_a_low_result_is_an_explicit_end() -> None:
    records = ia_records()
    for record_id in (
        "ia-99000001-2026-06-26-watch-general-information",
        "ia-99100001-2026-07-10-ok-for-swimming",
    ):
        end = records[record_id]
        assert (end.tier, end.explicit_no_advisory, end.end_kind) == (
            "no_advisory",
            True,
            "below_threshold",
        )


def test_a_watch_sign_without_a_low_result_never_ends_anything() -> None:
    records = ia_records()
    disagree = records["ia-99000003-2026-07-31-watch-general-information"]
    assert (disagree.tier, disagree.is_unrecognized) == ("unknown", True)
    unsampled = records["ia-99000004-2026-08-07-watch-general-information"]
    assert unsampled.tier == "not_classified"
    limit_too_high = records["ia-99100002-2026-07-10-ok-for-swimming"]
    assert limit_too_high.tier == "not_classified"


def test_other_statuses_decide_nothing_or_stay_undetermined() -> None:
    records = ia_records()
    closed = records["ia-99000004-2026-08-14-beach-closed"]
    assert closed.tier == "not_classified"
    assert closed.detail == "Microcystin ND ug/L. Closed for repairs."
    new = records["ia-99000005-2026-08-21-swimming-advisory"]
    assert (new.level, new.tier, new.is_unrecognized) == (
        "Swimming Advisory",
        "unknown",
        True,
    )


def test_every_iowa_advisory_rests_on_a_toxin_result_over_8() -> None:
    for record in ia_records().values():
        if record.is_advisory:
            assert record.level in iowa.NOT_RECOMMENDED
            result = record.detail.split()[1]
            assert float(result) > iowa.THRESHOLD_UG_L
        if record.explicit_no_advisory:
            assert record.level in iowa.NO_ADVISORY_SIGN


def test_iowa_never_invents_a_level() -> None:
    raw = {
        line.split(",")[-2]
        for path in IA_PAGES
        for line in path.read_text(encoding="utf-8").splitlines()[1:]
    }
    assert {r.level for r in ia_records().values()} <= raw


def test_iowa_quarantines_what_it_cannot_place() -> None:
    result = iowa.normalize(pages(), RUN)
    assert result.rows_read == 18
    assert dict(result.quarantine) == {
        "missing site id": 1,
        "missing beach name": 1,
        "missing sample date": 1,
        "sample date outside 2000 to the run date": 1,
        "the same status on the same beach and day twice": 1,
    }
    assert len(result.records) == 13


@pytest.mark.parametrize(
    ("text", "side"),
    [
        ("12.5", "over"),
        ("8.01", "over"),
        ("8", "at"),
        ("8.0", "at"),
        ("7.99", "under"),
        ("0", "under"),
        ("<0.3", "under"),
        ("< 8", "under"),
        ("<10", "unread"),
        ("", "unread"),
        ("ND", "unread"),
        ("-1", "unread"),
        ("pending", "unread"),
    ],
)
def test_microcystin_side(text: str, side: str) -> None:
    assert iowa.microcystin_side(text) == side


# ---- refusals ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("bodies", "match"),
    [
        ([b"x"], "2 downloads, not 1"),
        ([_csv(HEADER), _csv(HEADER)], "no rows"),
        ([_csv("siteID,name,status"), _csv(HEADER)], "no longer has the columns"),
        ([b"<!DOCTYPE html><html>", _csv(HEADER)], "web page"),
        ([b"\xff\xfe\x00", _csv(HEADER)], "not UTF-8"),
        (
            [
                _csv(
                    HEADER, ",Invented,x,6/1/2026,1,1,1,1,Watch / General Information,"
                ),
                _csv(HEADER),
            ],
            "no row this pipeline can place",
        ),
    ],
)
def test_iowa_refuses_a_changed_or_empty_read_whole(
    bodies: list[bytes], match: str
) -> None:
    with pytest.raises(iowa.IowaRefused, match=match):
        iowa.normalize(bodies, RUN)


def test_a_byte_order_mark_is_read() -> None:
    body = b"\xef\xbb\xbf" + IA_PAGES[1].read_bytes()
    assert len(iowa.normalize([body, _csv(HEADER)], RUN).records) == 3


# ---- the fetch ---------------------------------------------------------------


def test_iowa_fetch_reads_robots_then_both_downloads_politely() -> None:
    seen: list[str] = []
    bodies = pages()

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        assert request.headers["User-Agent"] == fetch.USER_AGENT
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        which = request.url.path.rsplit("/", 1)[-1]
        return httpx.Response(200, content=bodies[iowa.DOWNLOADS.index(which)])

    slept: list[float] = []
    client = httpx.Client(
        transport=httpx.MockTransport(handler), headers={"User-Agent": fetch.USER_AGENT}
    )
    assert iowa.fetch_pages(client, sleep=slept.append) == bodies
    assert seen == [
        "/robots.txt",
        "/aquia/Programs/DownloadBeachResults/State",
        "/aquia/Programs/DownloadBeachResults/CountyCity",
    ]
    assert slept == [iowa.POLITE_DELAY_SECONDS]


@pytest.mark.parametrize("robots", ["403", "disallow"])
def test_iowa_fetch_stops_at_robots_and_requests_nothing_else(robots: str) -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        if robots == "403":
            return httpx.Response(403)
        return httpx.Response(200, text="User-agent: *\nDisallow: /aquia/\n")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(fetch.RobotsOffLimits):
        iowa.fetch_pages(client, sleep=lambda _s: None)
    assert seen == ["/robots.txt"]


def test_iowa_fetch_refuses_an_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(503)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(fetch.FetchError, match="State download returned HTTP 503"):
        iowa.fetch_pages(client, sleep=lambda _s: None)


def test_iowa_on_without_a_fixture_reads_through_the_reader(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(iowa, "POLITE_DELAY_SECONDS", 0.0)
    bodies = pages()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        which = request.url.path.rsplit("/", 1)[-1]
        return httpx.Response(200, content=bodies[iowa.DOWNLOADS.index(which)])

    def client() -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(handler))

    flagged.review(
        run_date=RUN,
        fixtures={},
        out_dir=None,
        site_out=None,
        environ={FLAG: "1"},
        client_factory=client,
    )
    assert "IA review only" in capsys.readouterr().out


# ---- the copy rules ----------------------------------------------------------


def test_no_iowa_record_says_safe_or_clear() -> None:
    for record in ia_records().values():
        for text in (record.level, record.detail, record.landmark):
            lowered = text.lower()
            assert "safe" not in lowered
            assert "all clear" not in lowered
            assert "all-clear" not in lowered
