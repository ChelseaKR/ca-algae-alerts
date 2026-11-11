"""Oregon and Kansas readers, built behind flags that are off (DECISIONS 0037).

Every fixture under fixtures/states-invented/ is written by hand in the
agency's format with invented waters and values; no agency data is committed.
"""

from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
from pathlib import Path

import httpx
import pytest
from paths import CYAN_CACHE, FIXTURES, MO_POINTS, PAGE, TRAPS

from caalgae import cli, fetch, flagged, kansas, oregon, sources

INVENTED = FIXTURES / "states-invented"
KS_PAGES = [INVENTED / "ks-page-1.json", INVENTED / "ks-page-2.json"]
OR_LIST = INVENTED / "or-list.json"
RUN = dt.date(2026, 10, 12)
ROOT = Path(__file__).resolve().parents[2]
FLAGS = ("LN_ENABLE_OREGON", "LN_ENABLE_KANSAS")
# Every registered flag, Iowa's included (DECISIONS 0038; test_flagged_iowa.py).
ALL_FLAGS = (*FLAGS, "LN_ENABLE_IOWA")
ADVISORY_WORDS = {
    "OR": oregon.ADVISORY_STATUSES | oregon.END_STATUSES,
    "KS": kansas.ADVISORY_STATUSES | {kansas.END_STATUS} | kansas.UNREAD_STATUSES,
}


@pytest.fixture(autouse=True)
def _flags_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    for flag in ALL_FLAGS:
        monkeypatch.delenv(flag, raising=False)


@pytest.fixture
def small_kansas(monkeypatch: pytest.MonkeyPatch) -> None:
    # The real layer has thousands of rows; the invented one has sixteen.
    monkeypatch.setattr(kansas, "MIN_ROWS", 10)


def ks_records() -> dict[str, kansas.Record]:
    pages = [p.read_bytes() for p in KS_PAGES]
    return {r.id: r for r in kansas.normalize(pages, RUN).records}


def or_records() -> dict[str, oregon.Record]:
    return {r.id: r for r in oregon.normalize([OR_LIST.read_bytes()], RUN).records}


# ---- the flags ----------------------------------------------------------


@pytest.mark.parametrize("value", ["", "0"])
def test_unset_empty_and_zero_are_off(value: str) -> None:
    assert flagged.enabled({}) == []
    assert flagged.enabled(dict.fromkeys(FLAGS, value)) == []


@pytest.mark.parametrize("value", ["yes", "true", "on", " 1", "1 ", "2", "01"])
def test_any_other_value_refuses(value: str) -> None:
    for flag in FLAGS:
        with pytest.raises(flagged.FlagError, match=flag):
            flagged.enabled({flag: value})


def test_each_flag_turns_on_its_own_state_and_nothing_else() -> None:
    assert [r.state for r in flagged.enabled({"LN_ENABLE_OREGON": "1"})] == ["OR"]
    assert [r.state for r in flagged.enabled({"LN_ENABLE_KANSAS": "1"})] == ["KS"]
    both = flagged.enabled(dict.fromkeys(FLAGS, "1"))
    assert sorted(r.state for r in both) == ["KS", "OR"]


def test_the_flags_are_distinct_and_the_sources_are_off_and_unlisted() -> None:
    assert sorted(r.flag for r in flagged.READERS.values()) == sorted(ALL_FLAGS)
    for reader in flagged.READERS.values():
        assert reader.source.enabled is False
        assert reader.source.license.startswith("unknown")
        assert reader.source.attribution == ""
        assert reader.source.id not in sources.SOURCES
        assert reader.source not in sources.enabled_sources()
        assert reader.source.state == reader.state
    assert set(sources.FLAGGED_SOURCES) == {
        "or-oha-hab",
        "ks-kdhe-hab",
        "ia-dnr-beaches",
    }


def test_no_workflow_mentions_a_flag_or_the_review_options() -> None:
    workflows = sorted((ROOT / ".github" / "workflows").glob("*.y*ml"))
    assert workflows, "the workflows were not found"
    for path in workflows:
        text = path.read_text(encoding="utf-8")
        for word in (*ALL_FLAGS, "--state-fixture", "--state-review-out"):
            assert word not in text, f"{path.name} mentions {word}"


# ---- a default build ----------------------------------------------------


def build_args(out: Path, *extra: str) -> list[str]:
    return [
        "--fixture-page",
        str(PAGE),
        "--fixture-csv",
        str(TRAPS),
        "--mo-fixture",
        str(MO_POINTS),
        "--cyan-cache",
        str(CYAN_CACHE),
        "--cyan-refresh",
        "never",
        "--run-today",
        RUN.isoformat(),
        "--history",
        str(out / "history.json"),
        "--snapshot-out",
        str(out / "snapshot.json"),
        "--site-out",
        str(out / "site"),
        *extra,
    ]


def tree_hashes(out: Path) -> dict[str, str]:
    return {
        str(p.relative_to(out)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(out.rglob("*"))
        if p.is_file()
    }


def build(
    out: Path, capsys: pytest.CaptureFixture[str], *extra: str
) -> tuple[dict[str, str], str]:
    assert cli.main(build_args(out, *extra)) == 0
    printed = capsys.readouterr().out
    return tree_hashes(out), printed


def test_a_default_build_is_byte_identical_whether_or_not_they_are_registered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    with_readers, printed = build(tmp_path / "with", capsys)
    assert any(name.startswith("site/") for name in with_readers)
    assert "snapshot.json" in with_readers
    assert "history.json" in with_readers
    monkeypatch.setattr(flagged, "READERS", {})
    without, printed_without = build(tmp_path / "without", capsys)
    assert with_readers == without
    assert printed == printed_without
    for name in with_readers:
        assert "-review" not in name


def test_flags_set_to_zero_build_the_same_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    default, _ = build(tmp_path / "default", capsys)
    for flag in ALL_FLAGS:
        monkeypatch.setenv(flag, "0")
    zero, _ = build(
        tmp_path / "zero", capsys, "--state-review-out", str(tmp_path / "r")
    )
    assert zero == default
    assert not (tmp_path / "r").exists()


def test_a_default_run_never_reaches_the_network_for_them(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def refuse(_client: object) -> list[bytes]:
        raise AssertionError("a flagged state was fetched with its flag off")

    for state, reader in flagged.READERS.items():
        monkeypatch.setitem(
            flagged.READERS,
            state,
            flagged.Reader(
                reader.state, reader.flag, reader.source, refuse, reader.normalize
            ),
        )
    build(tmp_path, capsys)


def test_a_fixture_never_turns_a_state_on(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = cli.main(build_args(tmp_path, "--state-fixture", f"OR={OR_LIST}"))
    assert code == 2
    assert "its flag is off" in capsys.readouterr().err
    assert not (tmp_path / "history.json").exists()
    assert not (tmp_path / "site").exists()


def test_a_bad_flag_refuses_the_run_before_anything_is_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("LN_ENABLE_KANSAS", "true")
    assert cli.main(build_args(tmp_path)) == 2
    assert "LN_ENABLE_KANSAS" in capsys.readouterr().err
    assert not (tmp_path / "history.json").exists()


@pytest.mark.parametrize("value", ["OR", "=x", "TX=x", "OR="])
def test_a_malformed_fixture_option_refuses(value: str) -> None:
    with pytest.raises(flagged.FlagError):
        flagged.parse_fixtures([value])


# ---- on, with a fixture: review only, never published ---------------------


def test_flag_on_writes_review_files_and_publishes_nothing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    small_kansas: None,
) -> None:
    default, _ = build(tmp_path / "default", capsys)
    for flag in FLAGS:
        monkeypatch.setenv(flag, "1")
    review = tmp_path / "review"
    on, printed = build(
        tmp_path / "on",
        capsys,
        "--state-fixture",
        f"OR={OR_LIST}",
        "--state-fixture",
        f"KS={KS_PAGES[0]}",
        "--state-fixture",
        f"KS={KS_PAGES[1]}",
        "--state-review-out",
        str(review),
    )
    # The published outputs are the default build's, byte for byte.
    assert on == default
    assert "OR review only, not published" in printed
    assert "KS review only, not published" in printed
    for state in ("or", "ks"):
        doc = json.loads((review / f"{state}-review.json").read_text(encoding="utf-8"))
        assert doc["not_published"].startswith("Review only.")
        assert doc["source"]["license"].startswith("unknown")
        assert doc["records"]
        assert {r["level"] for r in doc["records"]} <= ADVISORY_WORDS[doc["state"]] | {
            "",
            "Closed for Season",
            "Boil water notice",
        }
    for name in on:
        assert "review" not in name


def test_the_review_directory_may_not_be_inside_the_site(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("LN_ENABLE_OREGON", "1")
    code = cli.main(
        build_args(
            tmp_path,
            "--state-fixture",
            f"OR={OR_LIST}",
            "--state-review-out",
            str(tmp_path / "site" / "review"),
        )
    )
    assert code == 2
    assert "must not be inside" in capsys.readouterr().err
    assert not (tmp_path / "site").exists()


def test_flag_on_without_a_review_directory_only_prints(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    flagged.review(
        run_date=RUN,
        fixtures={"OR": [OR_LIST]},
        out_dir=None,
        site_out=None,
        environ={"LN_ENABLE_OREGON": "1"},
    )
    assert "OR review only" in capsys.readouterr().out
    assert list(tmp_path.iterdir()) == []


def test_flag_on_without_a_fixture_reads_through_the_reader(
    capsys: pytest.CaptureFixture[str],
) -> None:
    body = OR_LIST.read_bytes()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(200, content=body)

    def client() -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(handler))

    flagged.review(
        run_date=RUN,
        fixtures={},
        out_dir=None,
        site_out=None,
        environ={"LN_ENABLE_OREGON": "1"},
        client_factory=client,
    )
    assert "OR review only" in capsys.readouterr().out


# ---- Kansas ---------------------------------------------------------------


def test_kansas_keeps_kdhe_s_words_and_reads_lifted_as_an_explicit_end(
    small_kansas: None,
) -> None:
    records = ks_records()
    watch = records["ks-LM9001-2026-06-05-watch"]
    assert (watch.level, watch.tier, watch.state) == ("Watch", "other_advisory", "KS")
    assert watch.date == dt.date(2026, 6, 5)  # Central midnight, not UTC
    assert watch.end_date is None
    assert (watch.lat, watch.lon) == (38.5, -97.5)
    assert watch.site_id == "ks-LM9001"
    assert watch.water_name == "INVENTED LAKE A"
    assert records["ks-LM9001-2026-06-19-warning"].level == "Warning"
    lifted = records["ks-LM9001-2026-08-14-lifted"]
    assert lifted.tier == "no_advisory"
    assert lifted.explicit_no_advisory is True
    assert lifted.end_kind == "lifted"
    assert records["ks-LM9002-2026-07-03-lake-hazard"].tier == "other_advisory"
    assert records["ks-LM9002-2025-07-11-advisory"].tier == "other_advisory"


def test_kansas_statuses_without_a_reading_decide_nothing_or_stay_undetermined(
    small_kansas: None,
) -> None:
    records = ks_records()
    assert records["ks-LM9003-2019-08-02-historical-pending"].tier == "not_classified"
    assert records["ks-LM9003-2020-09-04-mixed"].tier == "not_classified"
    assert records["ks-LM9005-2026-05-01-blank"].tier == "not_classified"
    new = records["ks-LM9004-2026-09-25-closed-for-season"]
    assert (new.level, new.tier, new.is_unrecognized) == (
        "Closed for Season",
        "unknown",
        True,
    )
    for record in records.values():
        assert not record.explicit_no_advisory or record.level == "Lifted"


def test_kansas_never_invents_a_level_or_a_coordinate(small_kansas: None) -> None:
    records = ks_records()
    raw = {
        f["attributes"]["status"]
        for p in KS_PAGES
        for f in json.loads(p.read_bytes())["features"]
    }
    assert {r.level for r in records.values()} <= raw
    outside = records["ks-LM9006-2026-07-17-watch"]
    assert (outside.lat, outside.lon) == (None, None)


def test_kansas_quarantines_what_it_cannot_place(small_kansas: None) -> None:
    pages = [p.read_bytes() for p in KS_PAGES]
    result = kansas.normalize(pages, RUN)
    assert result.rows_read == 16
    assert dict(result.quarantine) == {
        "missing water id": 1,
        "missing water name": 1,
        "missing status date": 1,
        "status date outside 2010 to the run date": 2,
        "the same status on the same water and day twice": 1,
    }
    assert len(result.records) == 10


def _ks_variant(change: str) -> list[bytes]:
    pages = [json.loads(p.read_bytes()) for p in KS_PAGES]
    original = copy.deepcopy(pages)
    if change == "field":
        pages[1]["fields"] = [f for f in pages[1]["fields"] if f["name"] != "status"]
    elif change == "error":
        pages[0] = {"error": {"code": 400}}
    elif change == "early":
        pages = pages[:1]
    elif change == "rows":
        pages[1]["features"] = []
    elif change == "features":
        del pages[0]["features"]
    assert pages != original, f"the {change} control did not change anything"
    return [json.dumps(p).encode() for p in pages]


@pytest.mark.parametrize(
    ("change", "match"),
    [
        ("field", "no longer has the fields"),
        ("error", "answered an error"),
        ("early", "stopped before"),
        ("rows", "returned 7 rows"),
        ("features", "no feature list"),
    ],
)
def test_kansas_refuses_a_changed_layer_whole(
    change: str, match: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(kansas, "MIN_ROWS", 10)
    with pytest.raises(kansas.KansasRefused, match=match):
        kansas.normalize(_ks_variant(change), RUN)


@pytest.mark.parametrize(
    ("pages", "match"),
    [([], "no pages"), ([b"<html>"], "not JSON"), ([b"[]"], "not a JSON object")],
)
def test_kansas_refuses_an_answer_that_is_not_a_layer(
    pages: list[bytes], match: str
) -> None:
    with pytest.raises(kansas.KansasRefused, match=match):
        kansas.normalize(pages, RUN)


def test_kansas_refuses_a_layer_with_nothing_it_can_place(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(kansas, "MIN_ROWS", 1)
    page = json.loads(KS_PAGES[1].read_bytes())
    page["features"] = [
        f for f in page["features"] if not f["attributes"]["waterbody_id"]
    ]
    page["features"].append("not a row")
    with pytest.raises(kansas.KansasRefused, match="no status"):
        kansas.normalize([json.dumps(page).encode()], RUN)


def test_kansas_fetch_reads_robots_then_pages_politely() -> None:
    seen: list[str] = []
    bodies = [p.read_bytes() for p in KS_PAGES]

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        assert request.headers["User-Agent"] == fetch.USER_AGENT
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        offset = int(request.url.params["resultOffset"])
        return httpx.Response(200, content=bodies[offset // kansas.PAGE_SIZE])

    slept: list[float] = []
    client = httpx.Client(
        transport=httpx.MockTransport(handler), headers={"User-Agent": fetch.USER_AGENT}
    )
    pages = kansas.fetch_pages(client, sleep=slept.append)
    assert pages == bodies
    assert seen[0] == "https://maps.kdhe.ks.gov/robots.txt"
    assert len(seen) == 3
    assert slept == [kansas.POLITE_DELAY_SECONDS]
    params = httpx.URL(seen[1]).params
    assert params["outFields"] == ",".join(kansas.FIELDS)
    assert params["returnGeometry"] == "false"


def test_kansas_fetch_stops_at_a_robots_file_it_cannot_read() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        return httpx.Response(403)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(fetch.RobotsOffLimits):
        kansas.fetch_pages(client, sleep=lambda _s: None)
    assert seen == ["/robots.txt"]


@pytest.mark.parametrize(
    ("body", "status", "error"),
    [
        (b"{}", 500, fetch.FetchError),
        (
            json.dumps({"features": [], "exceededTransferLimit": True}).encode(),
            200,
            kansas.KansasRefused,
        ),
    ],
)
def test_kansas_fetch_refuses_an_error_or_a_layer_that_never_ends(
    body: bytes, status: int, error: type[Exception]
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(status, content=body)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(error):
        kansas.fetch_pages(client, sleep=lambda _s: None)


def test_kansas_fetch_hands_a_non_json_page_to_normalize() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(200, content=b"<html>")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    pages = kansas.fetch_pages(client, sleep=lambda _s: None)
    with pytest.raises(kansas.KansasRefused, match="not JSON"):
        kansas.normalize(pages, RUN)


# ---- Oregon ---------------------------------------------------------------


def test_oregon_keeps_oha_s_words_and_strips_its_markup() -> None:
    records = or_records()
    advisory = records["or-901-2026-07-10-advisory-in-effect"]
    assert (advisory.level, advisory.tier, advisory.state) == (
        "Advisory in effect",
        "other_advisory",
        "OR",
    )
    assert advisory.date == dt.date(2026, 7, 10)  # Pacific midnight
    assert advisory.water_name == "Invented Lake"
    assert advisory.county_text == "Lane"
    assert advisory.landmark == "Invented Lake (north arm to the dam)"
    assert advisory.detail == "Visible bloom. Microcystin 9.9 ug/L."
    assert (advisory.lat, advisory.lon) == (None, None)
    assert advisory.water_key == "or|lane|invented lake"
    river = records["or-903-2026-08-21-precaution-in-effect"]
    assert (river.tier, river.landmark, river.detail) == (
        "other_advisory",
        "Invented River",
        "",
    )
    assert records["or-904-2020-06-01-permanent-advisory"].detail == "Ongoing toxins."


def test_oregon_reads_has_been_lifted_as_an_explicit_end_and_nothing_else() -> None:
    records = or_records()
    lifted = records["or-902-2026-09-30-precaution-has-been-lifted"]
    assert (lifted.tier, lifted.explicit_no_advisory, lifted.end_kind) == (
        "no_advisory",
        True,
        "lifted",
    )
    unknown = records["or-905-2026-08-01-boil-water-notice"]
    assert (unknown.tier, unknown.is_unrecognized) == ("unknown", True)
    for record in records.values():
        assert record.explicit_no_advisory == (record.level in oregon.END_STATUSES)


def test_oregon_quarantines_what_it_cannot_place() -> None:
    result = oregon.normalize([OR_LIST.read_bytes()], RUN)
    assert result.rows_read == 10
    assert dict(result.quarantine) == {
        "not shown on OHA's page": 1,
        "status is not exactly one value": 1,
        "missing date": 1,
        "missing water name": 1,
        "date outside 2007 to the run date": 1,
    }
    assert len(result.records) == 5


def _or_variant(change: str) -> bytes:
    data = json.loads(OR_LIST.read_bytes())
    original = copy.deepcopy(data)
    if change == "field":
        del data["value"][2]["County"]
    elif change == "next":
        data["odata.nextLink"] = "https://www.oregon.gov/next"
    elif change == "empty":
        data["value"] = []
    elif change == "shape":
        data = {"d": data["value"]}
    elif change == "none":
        data["value"] = [data["value"][5]]
    elif change == "duplicate":
        data["value"].append(data["value"][0])
    assert data != original, f"the {change} control did not change anything"
    return json.dumps(data).encode()


@pytest.mark.parametrize(
    ("change", "match"),
    [
        ("field", "no longer has the fields"),
        ("next", "more items than one answer"),
        ("empty", "no items"),
        ("shape", "no item list"),
        ("none", "no item this pipeline can place"),
    ],
)
def test_oregon_refuses_a_changed_list_whole(change: str, match: str) -> None:
    with pytest.raises(oregon.OregonRefused, match=match):
        oregon.normalize([_or_variant(change)], RUN)


def test_oregon_counts_a_repeated_item_once() -> None:
    result = oregon.normalize([_or_variant("duplicate")], RUN)
    assert result.quarantine["the same list item twice"] == 1


@pytest.mark.parametrize(
    ("pages", "match"), [([], "not 0"), ([b"x", b"y"], "not 2"), ([b"<"], "not JSON")]
)
def test_oregon_refuses_an_answer_that_is_not_one_list(
    pages: list[bytes], match: str
) -> None:
    with pytest.raises(oregon.OregonRefused, match=match):
        oregon.normalize(pages, RUN)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, ""),
        (3, ""),
        ("<div>​A&#160;B<br>C</div>", "A B C"),
        ("plain", "plain"),
    ],
)
def test_oregon_text_of(value: object, expected: str) -> None:
    assert oregon.text_of(value) == expected


@pytest.mark.parametrize("value", [None, "not a date", "2026-07-10T07:00:00", 5])
def test_oregon_an_unreadable_date_is_missing(value: object) -> None:
    assert oregon._date(value) is None


def test_oregon_an_item_without_an_integer_id_is_quarantined() -> None:
    data = json.loads(OR_LIST.read_bytes())
    data["value"][0]["ID"] = "901"
    result = oregon.normalize([json.dumps(data).encode()], RUN)
    assert result.quarantine["missing list item id"] == 1


def test_oregon_fetch_reads_robots_then_one_request_for_named_fields() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/robots.txt":
            return httpx.Response(
                200,
                text="User-agent: *\nDisallow: /_layouts\n",
                headers={"content-type": "text/plain"},
            )
        return httpx.Response(200, content=OR_LIST.read_bytes())

    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert oregon.fetch_pages(client) == [OR_LIST.read_bytes()]
    assert seen[0].url.path == "/robots.txt"
    assert len(seen) == 2
    assert seen[1].headers["Accept"] == oregon.ACCEPT
    assert seen[1].url.params["$select"] == ",".join(oregon.FIELDS)
    assert "Author" not in str(seen[1].url)


@pytest.mark.parametrize("robots", ["403", "disallow"])
def test_oregon_fetch_stops_at_robots_and_requests_nothing_else(robots: str) -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        if robots == "403":
            return httpx.Response(403)
        return httpx.Response(200, text="User-agent: *\nDisallow: /oha/\n")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(fetch.RobotsOffLimits):
        oregon.fetch_pages(client)
    assert seen == ["/robots.txt"]


def test_oregon_fetch_refuses_an_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(503)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(fetch.FetchError, match="HTTP 503"):
        oregon.fetch_pages(client)


# ---- the copy rules -------------------------------------------------------


def test_no_record_says_safe_or_clear(small_kansas: None) -> None:
    for record in [*ks_records().values(), *or_records().values()]:
        for text in (record.level, record.detail, record.landmark):
            lowered = text.lower()
            assert "safe" not in lowered
            assert "all clear" not in lowered
            assert "all-clear" not in lowered
