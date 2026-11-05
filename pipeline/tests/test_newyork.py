"""New York's yearly bloom history (docs/DECISIONS.md 0020): the pinned cache,
how rows become waters, the thin-page threshold and its negative control, the
rollout switch, the copy rules (history only: never an advisory, a current
status or an end) and the yearly refresh's manners toward data.ny.gov."""

from __future__ import annotations

import datetime as dt
import html
import json
import re
import shutil
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from paths import MO_POINTS, PAGE, SAMPLE

from caalgae import cli, fetch, newyork, site

NY_FIXTURE = Path(__file__).parent / "fixtures" / "ny"
_TAG = re.compile(r"<[^>]+>")
_MAIN = re.compile(r"<main\b.*?</main>", re.S)
_HREF = re.compile(r'href="([^"]+)"')

# Fixture waters (every row for eight real waters, read 2026-11-02).
DEEP = "seneca-lake"  # 7 years, 732 reports
BELOW = "adirondack-lake"  # 1 year, 4 reports: one report short of the threshold
BELOW_TOO = "jefferson-greenwood-lake"  # 1 year, 1 report
BY_REPORTS = "lower-esopus-creek"  # 1 year, 9 reports
BY_YEARS = "big-fresh-pond"  # 2 years, 2 reports


def build(tmp_path: Path, *extra: str) -> Path:
    out = tmp_path / "site"
    assert (
        cli.main(
            [
                "--fixture-page", str(PAGE),
                "--fixture-csv", str(SAMPLE),
                "--mo-fixture", str(MO_POINTS),
                "--run-today", "2026-10-12",
                "--history", str(tmp_path / "history.json"),
                "--site-out", str(out),
                *extra,
            ]
        )
        == 0
    )  # fmt: skip
    return out


def build_ny(tmp_path: Path, limit: int | None = None) -> Path:
    out = tmp_path / "site"
    history = newyork.load(NY_FIXTURE, pinned=None)
    snap = json.loads((build(tmp_path) / "snapshot" / "v1.json").read_text())
    site.build_site(snap, out, ny_history=history, ny_index_limit=limit)
    return out


@pytest.fixture(scope="module")
def ny_site(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build_ny(tmp_path_factory.mktemp("ny"))


def ny_pages(root: Path) -> list[Path]:
    return sorted((root / "state" / "ny").rglob("index.html"))


def main_text(page: Path) -> str:
    match = _MAIN.search(page.read_text(encoding="utf-8"))
    assert match, page
    return html.unescape(re.sub(r"\s+", " ", _TAG.sub(" ", match.group(0)))).strip()


def sitemap_urls(root: Path) -> list[str]:
    return re.findall(r"<loc>([^<]+)</loc>", (root / "sitemap.xml").read_text())


def is_indexed(root: Path, slug: str) -> bool:
    """Listed in the sitemap, or carrying a canonical link, or lacking a
    robots noindex: any one of these means search engines may list it."""
    page = (root / "state" / "ny" / slug / "index.html").read_text(encoding="utf-8")
    url = f"{site.DEFAULT_BASE_URL}state/ny/{slug}/"
    return (
        url in sitemap_urls(root)
        or 'rel="canonical"' in page
        or 'name="robots" content="noindex' not in page
    )


# -- the pinned cache ------------------------------------------------------------


def test_committed_cache_matches_its_pin_and_sidecar() -> None:
    body = (newyork.DATA_DIR / newyork.ROWS_FILE).read_bytes()
    meta = json.loads((newyork.DATA_DIR / newyork.META_FILE).read_text())
    assert newyork.sha256(body) == newyork.PINNED_SHA256 == meta["sha256"]
    assert meta["dataset"] == "95my-wijm"
    assert meta["fields"] == list(newyork.FIELDS)
    assert meta["rows_updated_at"] == "2026-01-14T17:36:47Z"


def test_committed_cache_reads_as_measured_on_2026_11_02() -> None:
    history = newyork.load()
    assert history.rows_read == 1371
    assert history.unnamed_rows == 102
    assert history.quarantine == {}
    assert len(history.waters) == 477
    assert (history.first_year, history.last_year) == (2019, 2025)
    eligible = [w for w in history.waters if newyork.meets_threshold(w)]
    assert len(eligible) == 284
    assert len(newyork.indexed_ids(history.waters, 50)) == 50
    seneca = next(w for w in history.waters if w.id == "ny-seneca-lake")
    # Seven rows under four spellings of its counties are one water.
    assert seneca.counties == ("Ontario", "Schuyler", "Seneca", "Yates")
    assert (seneca.year_count, seneca.report_count) == (7, 732)


def test_an_altered_cache_is_refused(tmp_path: Path) -> None:
    shutil.copytree(NY_FIXTURE, tmp_path / "ny")
    rows = tmp_path / "ny" / newyork.ROWS_FILE
    rows.write_bytes(rows.read_bytes().replace(b'"732"', b'"733"', 1) + b" ")
    with pytest.raises(newyork.NYDataError, match="does not match the hash"):
        newyork.load(tmp_path / "ny", pinned=None)


def test_a_cache_that_is_not_the_pinned_file_is_refused() -> None:
    with pytest.raises(newyork.NYDataError, match="not the pinned file"):
        newyork.load(NY_FIXTURE)


def test_a_missing_cache_is_refused(tmp_path: Path) -> None:
    with pytest.raises(newyork.NYDataError, match="cannot be read"):
        newyork.load(tmp_path)


# -- rows to waters ----------------------------------------------------------------


def row(**overrides: Any) -> dict[str, Any]:
    base = {
        "waterbody_name": "Test Pond",
        "county": "Albany",
        "year": "2024",
        "bloom_type": "confirmed",
        "date_first_report": "2024-08-01T00:00:00.000",
        "date_last_report": "2024-08-20T00:00:00.000",
        "number_of_reports": "3",
        "latitude": "42.6",
        "longitude": "-73.8",
    }
    return {**base, **overrides}


def parse(*rows: Any) -> tuple[list[newyork.Water], int, int, dict[str, int]]:
    return newyork.parse(json.dumps(list(rows)).encode())


@pytest.mark.parametrize(
    ("bad", "reason"),
    [
        ({"bloom_type": "suspicious"}, "bloom type other than confirmed"),
        ({"bloom_type": None}, "bloom type other than confirmed"),
        ({"date_first_report": ""}, "missing or malformed date"),
        ({"date_last_report": "08/20/2024"}, "missing or malformed date"),
        (
            {"date_first_report": "2023-12-30T00:00:00.000"},
            "report date outside the row's year",
        ),
        (
            {"date_last_report": "2024-07-01T00:00:00.000"},
            "last report before first report",
        ),
        ({"number_of_reports": "0"}, "report count is not a positive whole number"),
        ({"number_of_reports": "2.5"}, "report count is not a positive whole number"),
        ({"number_of_reports": None}, "report count is not a positive whole number"),
        ({"latitude": "34.1"}, "point outside New York"),
        ({"longitude": "nan"}, "point outside New York"),
        ({"year": "twenty"}, "missing or malformed year"),
        ({"county": " , "}, "no county"),
        ({"waterbody_name": "  "}, "no water name"),
    ],
)
def test_a_row_that_cannot_be_shown_honestly_is_held_back_and_counted(
    bad: dict[str, Any], reason: str
) -> None:
    waters, read, unnamed, quarantine = parse(
        row(), row(year="2023", **_dates(2023)), row(**bad)
    )
    assert quarantine == {reason: 1}
    assert read == 3 and unnamed == 0
    assert [w.year_count for w in waters] == [2]


def _dates(year: int) -> dict[str, str]:
    return {
        "date_first_report": f"{year}-08-01T00:00:00.000",
        "date_last_report": f"{year}-08-20T00:00:00.000",
    }


def test_a_row_that_is_not_an_object_is_held_back() -> None:
    _, _, _, quarantine = parse(row(), "not a row")
    assert quarantine == {"bloom type other than confirmed": 1}


@pytest.mark.parametrize("body", [b"not json", b"[]", b'{"rows": []}'])
def test_a_file_that_is_not_a_list_of_rows_is_refused(body: bytes) -> None:
    with pytest.raises(newyork.NYDataError):
        newyork.parse(body)


def test_unnamed_waters_get_no_page_and_are_counted() -> None:
    waters, _, unnamed, _ = parse(
        row(),
        row(waterbody_name="Unnamed Water"),
        row(waterbody_name="Unnamed Tributary T3"),
    )
    assert unnamed == 2
    assert [w.name for w in waters] == ["Test Pond"]


def test_one_point_under_several_county_spellings_is_one_water() -> None:
    waters, *_ = parse(
        row(county="Steuben, Yates"),
        row(county="Yates, Steuben", year="2023", **_dates(2023)),
    )
    assert len(waters) == 1
    assert waters[0].counties == ("Steuben", "Yates")
    assert waters[0].place == "Steuben and Yates counties"
    assert waters[0].id == "ny-test-pond"


def test_waters_that_share_a_name_get_their_own_page_and_id() -> None:
    waters, *_ = parse(
        row(county="Suffolk", latitude="40.935", longitude="-72.323"),
        row(county="Suffolk", latitude="40.975", longitude="-72.291"),
        row(county="Orange", latitude="41.3", longitude="-74.3"),
    )
    assert sorted(w.id for w in waters) == [
        "ny-orange-test-pond",
        "ny-suffolk-test-pond-40-935-72-323",
        "ny-suffolk-test-pond-40-975-72-291",
    ]


def test_a_second_row_for_one_water_in_one_year_is_held_back() -> None:
    waters, _, _, quarantine = parse(row(), row(number_of_reports="7"))
    assert quarantine == {"a second row for one water in one year": 1}
    assert waters[0].report_count in (3, 7)


# -- the thin-page threshold and the staged rollout ---------------------------------


def water(years: int, reports: int, name: str = "w") -> newyork.Water:
    per_year = [
        reports // years + (1 if i < reports % years else 0) for i in range(years)
    ]
    return newyork.Water(
        id=f"ny-{name}",
        slug=name,
        name=name,
        counties=("Albany",),
        lat=42.6,
        lon=-73.8,
        years=tuple(
            newyork.BloomYear(
                2025 - i, dt.date(2025 - i, 8, 1), dt.date(2025 - i, 8, 2), n, "x"
            )
            for i, n in enumerate(per_year)
        ),
    )


@pytest.mark.parametrize(
    ("years", "reports", "expected"),
    [(1, 1, False), (1, 4, False), (1, 5, True), (2, 2, True), (7, 732, True)],
)
def test_threshold_is_two_years_or_five_reports(
    years: int, reports: int, expected: bool
) -> None:
    assert newyork.meets_threshold(water(years, reports)) is expected


def test_the_staged_limit_takes_the_deepest_histories_first() -> None:
    waters = [
        water(1, 4, "thin"),
        water(2, 2, "two"),
        water(1, 9, "nine"),
        water(7, 99, "deep"),
    ]
    assert newyork.indexed_ids(waters, None) == {"ny-two", "ny-nine", "ny-deep"}
    assert newyork.indexed_ids(waters, 2) == {"ny-deep", "ny-nine"}
    assert newyork.indexed_ids(waters, 0) == set()


# -- the rollout switch: off by default ------------------------------------------------


def test_the_section_is_off_by_default() -> None:
    assert site.NY_HISTORY_ENABLED is False
    assert site.NY_INDEX_LIMIT == 50


def test_default_build_has_no_new_york_page_link_or_url(tmp_path: Path) -> None:
    out = build(tmp_path)
    assert not (out / "state" / "ny").exists()
    assert not any("/state/ny/" in u for u in sitemap_urls(out))
    for page in out.rglob("*.html"):
        text = page.read_text(encoding="utf-8")
        assert "New York" not in text, page
        assert "state/ny/" not in text, page
    snapshot = json.loads((out / "snapshot" / "v1.json").read_text())
    assert {w["state"] for w in snapshot["waterbodies"]} <= {"CA", "MO"}


def test_turned_on_from_the_command_line_with_a_cache(tmp_path: Path) -> None:
    out = build(tmp_path, "--ny-history", "on", "--ny-cache", str(NY_FIXTURE))
    assert (out / "state" / "ny" / DEEP / "index.html").exists()
    # New York never reaches the snapshot the app reads, so it never alerts.
    snapshot = json.loads((out / "snapshot" / "v1.json").read_text())
    assert {w["state"] for w in snapshot["waterbodies"]} <= {"CA", "MO"}
    assert "New York" not in json.dumps(snapshot)


def refused(tmp_path: Path, *extra: str) -> None:
    """Run the build expecting a refusal, and return its message. Nothing
    is written: no site, no snapshot and no history."""
    out = tmp_path / "site"
    code = cli.main(
        [
            "--fixture-page", str(PAGE),
            "--fixture-csv", str(SAMPLE),
            "--mo-fixture", str(MO_POINTS),
            "--run-today", "2026-10-12",
            "--history", str(tmp_path / "history.json"),
            "--site-out", str(out),
            *extra,
        ]
    )  # fmt: skip
    assert code == 2
    assert not out.exists()
    assert not (tmp_path / "history.json").exists()


def altered_cache(tmp_path: Path) -> Path:
    cache = tmp_path / "ny-cache"
    shutil.copytree(NY_FIXTURE, cache)
    return cache


def test_a_missing_cache_refuses_the_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    refused(tmp_path, "--ny-history", "on", "--ny-cache", str(tmp_path / "missing"))
    err = capsys.readouterr().err
    assert "run refused -- nothing published" in err
    assert "New York history is on but not built" in err


def test_rows_that_do_not_match_their_hash_refuse_the_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cache = altered_cache(tmp_path)
    rows = cache / newyork.ROWS_FILE
    rows.write_bytes(rows.read_bytes() + b"\n")
    refused(tmp_path, "--ny-history", "on", "--ny-cache", str(cache))
    assert "does not match the hash" in capsys.readouterr().err


def test_a_sidecar_without_its_dates_refuses_the_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cache = altered_cache(tmp_path)
    meta_path = cache / newyork.META_FILE
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    del meta["fetched_at"]
    meta_path.write_text(json.dumps(meta), encoding="utf-8")
    refused(tmp_path, "--ny-history", "on", "--ny-cache", str(cache))
    assert "missing its hash or dates" in capsys.readouterr().err


def test_config_on_with_an_unpinned_cache_refuses_the_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Someone refreshes the New York rows and forgets PINNED_SHA256: the
    publish run fails instead of dropping every /state/ny/ page."""
    monkeypatch.setattr(site, "NY_HISTORY_ENABLED", True)
    # load()'s default pin is bound when it is defined, so move it there.
    monkeypatch.setitem(newyork.load.__kwdefaults__, "pinned", "0" * 64)
    refused(tmp_path)
    assert "is not the pinned file" in capsys.readouterr().err


def test_off_never_reads_the_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The control for the refusals above: with the section off, the same
    unpinned cache is never read and the build goes ahead without New York."""
    monkeypatch.setattr(site, "NY_HISTORY_ENABLED", False)
    monkeypatch.setitem(newyork.load.__kwdefaults__, "pinned", "0" * 64)
    out = build(tmp_path)
    assert (out / "index.html").exists()
    assert not (out / "state" / "ny").exists()


def test_config_on_reads_the_pinned_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(site, "NY_HISTORY_ENABLED", True)
    out = build(tmp_path)
    assert len(ny_pages(out)) == 478  # the state page and 477 waters
    ny_urls = [u for u in sitemap_urls(out) if "/state/ny/" in u]
    assert len(ny_urls) == 51  # the state page and the first 50 waters


# -- indexing: only waters over the threshold, never one below it -----------------------


def test_waters_over_the_threshold_are_indexed(ny_site: Path) -> None:
    for slug in (DEEP, BY_REPORTS, BY_YEARS):
        assert is_indexed(ny_site, slug), slug
    assert f"{site.DEFAULT_BASE_URL}state/ny/" in sitemap_urls(ny_site)


def test_a_water_below_the_threshold_is_never_indexed(ny_site: Path) -> None:
    for slug in (BELOW, BELOW_TOO):
        page = (ny_site / "state" / "ny" / slug / "index.html").read_text(
            encoding="utf-8"
        )
        assert '<meta name="robots" content="noindex,follow">' in page
        assert 'rel="canonical"' not in page
        assert not any(slug in u for u in sitemap_urls(ny_site))
        assert not is_indexed(ny_site, slug)


def test_negative_control_the_index_check_sees_a_lowered_threshold(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sabotage the threshold and the same check must flip, so the test above
    cannot pass by never looking."""
    monkeypatch.setattr(newyork, "MIN_YEARS", 1)
    out = build_ny(tmp_path)
    assert is_indexed(out, BELOW)
    assert f"{site.DEFAULT_BASE_URL}state/ny/{BELOW}/" in sitemap_urls(out)


def test_the_staged_limit_keeps_the_rest_out_of_the_sitemap(tmp_path: Path) -> None:
    out = build_ny(tmp_path, limit=1)
    assert is_indexed(out, DEEP)
    for slug in (BY_REPORTS, BY_YEARS, BELOW):
        assert not is_indexed(out, slug), slug


def test_lastmod_is_the_newest_report_on_the_page(ny_site: Path) -> None:
    sitemap = (ny_site / "sitemap.xml").read_text()
    assert (
        f"<loc>{site.DEFAULT_BASE_URL}state/ny/{DEEP}/</loc><lastmod>2025-10-28</lastmod>"
        in sitemap
    )


# -- what each page says ---------------------------------------------------------------


_NEGATION = re.compile(r"\b(?:not|no|never|nothing|without)\b", re.I)
_FORBIDDEN = re.compile(
    r"\b(?:advisor(?:y|ies)|current(?:ly)?|now|ended|ends|lifted|over|clean|clear|"
    r"all[- ]clear|safe|safety|resolved|gone)\b",
    re.I,
)


def unnegated_status_words(text: str) -> list[str]:
    """Sentences that call a row an advisory, a current status or an end, or
    call a water safe or clear, without negating it."""
    sentences = re.split(r"(?<=[.!?:])\s+", text)
    return [s for s in sentences if _FORBIDDEN.search(s) and not _NEGATION.search(s)]


def test_copy_guard_catches_status_and_end_wording() -> None:
    assert unnegated_status_words("The advisory at Seneca Lake ended Oct 28, 2025.")
    assert unnegated_status_words("Current status: bloom.")
    assert unnegated_status_words("Seneca Lake is clear now.")
    assert (
        unnegated_status_words("It is not an advisory and not a current status.") == []
    )


def test_new_york_pages_never_call_a_row_an_advisory_a_status_or_an_end(
    ny_site: Path,
) -> None:
    pages = ny_pages(ny_site)
    assert len(pages) == 9
    for page in pages:
        assert unnegated_status_words(main_text(page)) == [], page
        head = page.read_text(encoding="utf-8").split("</head>")[0]
        title = re.search(r"<title>(.*?)</title>", head)
        description = re.search(r'name="description" content="([^"]*)"', head)
        assert title and description
        for line in (
            html.unescape(title.group(1)),
            html.unescape(description.group(1)),
        ):
            assert unnegated_status_words(line) == [], line


def test_every_new_york_page_says_what_the_data_is_and_is_not(ny_site: Path) -> None:
    for page in ny_pages(ny_site):
        text = main_text(page)
        assert "It is history." in text
        assert "It is not an advisory and not a current status." in text
        assert "A last report date is not an end date." in text
        assert "does not send alerts for New York waters" in text
        assert newyork.NO_VOUCH_CLAUSE in text
        assert newyork.NOTIFICATIONS_URL in page.read_text(encoding="utf-8")


def test_each_water_page_shows_its_years_and_record_count(ny_site: Path) -> None:
    text = main_text(ny_site / "state" / "ny" / DEEP / "index.html")
    assert "in 7 years (2019 to 2025), with 732 reports in all" in text
    assert "7 years and 732 reports on record" in text
    assert "2025 Confirmed bloom Jul 22, 2025 Oct 28, 2025 158" in text
    one = main_text(ny_site / "state" / "ny" / BELOW_TOO / "index.html")
    year = re.search(r"in 1 year \((\d{4})\), with 1 report in all", one)
    assert year, one
    assert f"{year.group(1)} Confirmed bloom" in one


def test_attribution_is_on_every_page_when_the_section_is_on(ny_site: Path) -> None:
    for page in ny_site.rglob("*.html"):
        text = html.unescape(page.read_text(encoding="utf-8"))
        assert newyork.ATTRIBUTION in text, page


def test_new_york_pages_differ_from_advisory_pages(ny_site: Path) -> None:
    page = (ny_site / "state" / "ny" / DEEP / "index.html").read_text(encoding="utf-8")
    assert "algae bloom history" in page
    for advisory_copy in (
        "What the state's records say",
        "no all-clear recorded",
        "Dogs at",
    ):
        assert advisory_copy not in page


def test_titles_fit_and_differ_for_waters_that_share_a_name(ny_site: Path) -> None:
    titles: dict[str, Path] = {}
    for page in ny_pages(ny_site):
        head = page.read_text(encoding="utf-8")
        found_title = re.search(r"<title>(.*?)</title>", head)
        found_description = re.search(r'name="description" content="([^"]*)"', head)
        assert found_title and found_description
        title = html.unescape(found_title.group(1))
        description = html.unescape(found_description.group(1))
        assert len(title) <= site.TITLE_MAX, title
        assert len(description) <= site.DESCRIPTION_MAX, description
        assert title not in titles, (title, page, titles.get(title))
        titles[title] = page


def test_every_link_on_a_new_york_page_resolves(ny_site: Path) -> None:
    for page in ny_pages(ny_site):
        for href in _HREF.findall(page.read_text(encoding="utf-8")):
            if href.startswith(("http://", "https://", "mailto:", "#")):
                continue
            target = (page.parent / href.split("#")[0]).resolve()
            if target.is_dir() or href.endswith("/"):
                target = target / "index.html"
            assert target.exists(), (page, href)


def test_tables_are_labeled_for_screen_readers(ny_site: Path) -> None:
    for page in ny_pages(ny_site):
        raw = page.read_text(encoding="utf-8")
        assert raw.count("<table>") == raw.count("<caption") >= 1
        assert '<th scope="col">' in raw
        assert raw.count("<h1>") == 1


# -- the yearly refresh ------------------------------------------------------------


ROBOTS = "User-agent: *\nCrawl-delay: 1\nDisallow: /api/odata/\n"
META = {"name": newyork.DATASET_NAME, "rowsUpdatedAt": 1768412207}
NOW = dt.datetime(2027, 1, 20, 12, 0, tzinfo=dt.UTC)


@respx.mock
def test_refresh_reads_robots_first_waits_and_writes_a_pinnable_cache(
    tmp_path: Path,
) -> None:
    body = (NY_FIXTURE / newyork.ROWS_FILE).read_bytes()
    robots = respx.get("https://data.ny.gov/robots.txt").mock(
        return_value=httpx.Response(200, text=ROBOTS)
    )
    meta = respx.get(newyork.META_URL).mock(return_value=httpx.Response(200, json=META))
    rows = respx.get(url__startswith=newyork.ROWS_URL).mock(
        return_value=httpx.Response(200, content=body)
    )
    slept: list[float] = []
    with fetch.make_client() as client:
        digest = newyork.refresh(client, tmp_path, NOW, sleep=slept.append)
    assert robots.call_count == meta.call_count == rows.call_count == 1
    assert slept == [2.0, 2.0]
    request = rows.calls.last.request
    assert request.url.params["$select"] == ",".join(newyork.FIELDS)
    assert request.headers["User-Agent"] == fetch.USER_AGENT
    sidecar = json.loads((tmp_path / newyork.META_FILE).read_text())
    assert sidecar["sha256"] == digest == newyork.sha256(body)
    assert sidecar["rows_updated_at"] == "2026-01-14T17:36:47Z"
    assert sidecar["fetched_at"] == "2027-01-20T12:00:00Z"
    assert newyork.load(tmp_path, pinned=None).rows_read == 20


@respx.mock
def test_refresh_honors_a_longer_crawl_delay(tmp_path: Path) -> None:
    respx.get("https://data.ny.gov/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nCrawl-delay: 9\n")
    )
    respx.get(newyork.META_URL).mock(return_value=httpx.Response(200, json=META))
    respx.get(url__startswith=newyork.ROWS_URL).mock(
        return_value=httpx.Response(
            200, content=(NY_FIXTURE / newyork.ROWS_FILE).read_bytes()
        )
    )
    slept: list[float] = []
    with fetch.make_client() as client:
        newyork.refresh(client, tmp_path, NOW, sleep=slept.append)
    assert slept == [9.0, 9.0]


@pytest.mark.parametrize(
    "robots",
    [
        httpx.Response(403),
        httpx.Response(503),
        httpx.Response(200, text="User-agent: *\nDisallow: /resource/\n"),
        httpx.Response(200, text="User-agent: *\nDisallow: /\n"),
    ],
)
@respx.mock
def test_refresh_stops_when_robots_says_no(
    tmp_path: Path, robots: httpx.Response
) -> None:
    respx.get("https://data.ny.gov/robots.txt").mock(return_value=robots)
    meta = respx.get(newyork.META_URL).mock(return_value=httpx.Response(200, json=META))
    rows = respx.get(url__startswith=newyork.ROWS_URL).mock(
        return_value=httpx.Response(200)
    )
    with fetch.make_client() as client, pytest.raises(fetch.RobotsOffLimits):
        newyork.refresh(client, tmp_path, NOW, sleep=lambda _: None)
    assert meta.call_count == rows.call_count == 0
    assert not (tmp_path / newyork.ROWS_FILE).exists()


@respx.mock
def test_refresh_keeps_the_cache_when_the_rows_fail(tmp_path: Path) -> None:
    respx.get("https://data.ny.gov/robots.txt").mock(return_value=httpx.Response(404))
    respx.get(newyork.META_URL).mock(return_value=httpx.Response(200, json=META))
    respx.get(url__startswith=newyork.ROWS_URL).mock(return_value=httpx.Response(500))
    with (
        fetch.make_client() as client,
        pytest.raises(fetch.FetchError, match="HTTP 500"),
    ):
        newyork.refresh(client, tmp_path, NOW, sleep=lambda _: None)
    assert not (tmp_path / newyork.ROWS_FILE).exists()


@respx.mock
def test_refresh_refuses_rows_that_would_not_load(tmp_path: Path) -> None:
    respx.get("https://data.ny.gov/robots.txt").mock(return_value=httpx.Response(404))
    respx.get(newyork.META_URL).mock(return_value=httpx.Response(200, json=META))
    respx.get(url__startswith=newyork.ROWS_URL).mock(
        return_value=httpx.Response(200, content=b"[]")
    )
    with fetch.make_client() as client, pytest.raises(newyork.NYDataError):
        newyork.refresh(client, tmp_path, NOW, sleep=lambda _: None)
    assert not (tmp_path / newyork.ROWS_FILE).exists()


def test_page_changes_lists_removed_and_added_ids() -> None:
    assert newyork.page_changes(
        [water(1, 1, "a"), water(1, 1, "b")], [water(1, 1, "b"), water(2, 2, "c")]
    ) == (
        ["ny-a"],
        ["ny-c"],
    )


@pytest.mark.parametrize(
    "url",
    [
        "https://data.ny.gov/api/odata/v4/95my-wijm",
        "https://data.ny.gov/OData.svc/95my-wijm",
        "https://data.ny.gov/api/collocate/x",
        "https://data.ny.gov/tiles/95my-wijm",
    ],
)
def test_the_disallowed_data_ny_gov_prefixes_are_refused(url: str) -> None:
    with pytest.raises(fetch.FetchError, match=r"robots\.txt disallows"):
        fetch.guard_url(url)
