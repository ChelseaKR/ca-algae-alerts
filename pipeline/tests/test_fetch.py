from __future__ import annotations

import datetime as dt

import httpx
import pytest
import respx

from caalgae import fetch

URL = (
    "https://publish.data.ca.gov/dataset/ab672540-aecd-42f1-9b05-9aad326f97ec"
    "/resource/4283c060-c22f-48f5-a75c-8bccf0c54a99/download/hab-responses_2026-10-09.csv"
)


def test_discovers_the_dated_responses_file_from_the_real_page(page_html: str) -> None:
    found = fetch.discover_responses_file(page_html)
    assert found.url == URL
    assert found.file_date == dt.date(2026, 10, 9)
    assert found.file_name == "hab-responses_2026-10-09.csv"


def test_ignores_other_datasets_and_files_on_the_page(page_html: str) -> None:
    # The real page also links Safe to Swim and drinking-water CSVs, and the
    # FHAB cases/results/bloom-report files. Only one link qualifies.
    assert page_html.count("safetoswim") > 0
    assert page_html.count("hab-cases_2026-10-09.csv") > 0
    assert fetch.discover_responses_file(page_html).resource_id.startswith("4283c060")


def test_refuses_a_page_with_no_responses_link() -> None:
    with pytest.raises(fetch.FetchError, match="links no"):
        fetch.discover_responses_file("<html>nothing here</html>")


def test_refuses_a_page_with_two_different_responses_files(page_html: str) -> None:
    older = URL.replace("2026-10-09", "2026-10-08")
    with pytest.raises(fetch.FetchError, match="more than one"):
        fetch.discover_responses_file(page_html + f'<a href="{older}">')


def test_a_responses_file_from_another_dataset_is_not_picked() -> None:
    other = URL.replace(
        "ab672540-aecd-42f1-9b05-9aad326f97ec", "0" * 8 + "-0000-0000-0000-" + "0" * 12
    )
    with pytest.raises(fetch.FetchError):
        fetch.discover_responses_file(f'<a href="{other}">')


@pytest.mark.parametrize(
    "url",
    [
        "https://data.ca.gov/api/3/action/package_search?q=hab",
        "https://publish.data.ca.gov/api/3/action/package_show",
        "https://data.ca.gov/datastore/dump/abc",
        "https://data.ca.gov/search?q=algae",
        "https://mywaterquality.ca.gov/habs/",
        "http://data.ca.gov/dataset/x",
    ],
)
def test_guard_refuses_paths_robots_disallows_and_the_map_site(url: str) -> None:
    with pytest.raises(fetch.FetchError):
        fetch.guard_url(url)


def test_guard_allows_the_dataset_page_and_download() -> None:
    fetch.guard_url(fetch.DATASET_PAGE_URL)
    fetch.guard_url(URL)


def test_refuses_a_file_older_than_the_last_run() -> None:
    source = fetch.SourceFile(URL, "r", dt.date(2026, 10, 9))
    fetch.assert_not_regressed(source, None)
    fetch.assert_not_regressed(source, dt.date(2026, 10, 9))
    with pytest.raises(fetch.FetchError, match="older"):
        fetch.assert_not_regressed(source, dt.date(2026, 10, 10))


@respx.mock
def test_live_path_follows_the_storage_redirect_and_sends_the_user_agent(
    page_html: str,
) -> None:
    respx.get(fetch.DATASET_PAGE_URL).mock(
        return_value=httpx.Response(200, text=page_html)
    )
    signed = "https://example.r2.cloudflarestorage.com/x.csv?sig=1"
    respx.get(URL).mock(return_value=httpx.Response(302, headers={"location": signed}))
    stored = respx.get(signed).mock(
        return_value=httpx.Response(200, content=b"a,b\n1,2\n")
    )
    now = dt.datetime(2026, 10, 12, 13, 0, tzinfo=dt.UTC)
    with fetch.make_client() as client:
        source = fetch.discover_responses_file(fetch.fetch_dataset_page(client))
        download = fetch.fetch_csv(client, source, now)
    assert download.body == b"a,b\n1,2\n"
    assert stored.calls.last.request.headers["user-agent"].startswith(
        "ca-algae-alerts/"
    )


@respx.mock
def test_http_errors_and_empty_bodies_stop_the_run() -> None:
    respx.get(fetch.DATASET_PAGE_URL).mock(return_value=httpx.Response(503))
    source = fetch.SourceFile(URL, "r", dt.date(2026, 10, 9))
    respx.get(URL).mock(return_value=httpx.Response(200, content=b""))
    now = dt.datetime(2026, 10, 12, tzinfo=dt.UTC)
    with fetch.make_client() as client:
        with pytest.raises(fetch.FetchError, match="503"):
            fetch.fetch_dataset_page(client)
        with pytest.raises(fetch.FetchError, match="empty"):
            fetch.fetch_csv(client, source, now)


@respx.mock
def test_network_failure_is_a_fetch_error() -> None:
    respx.get(fetch.DATASET_PAGE_URL).mock(side_effect=httpx.ConnectError("down"))
    with fetch.make_client() as client, pytest.raises(fetch.FetchError, match="failed"):
        fetch.fetch_dataset_page(client)


@respx.mock
def test_oversized_file_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fetch, "MAX_CSV_BYTES", 4)
    respx.get(URL).mock(return_value=httpx.Response(200, content=b"12345"))
    source = fetch.SourceFile(URL, "r", dt.date(2026, 10, 9))
    with (
        fetch.make_client() as client,
        pytest.raises(fetch.FetchError, match="over the cap"),
    ):
        fetch.fetch_csv(client, source, dt.datetime(2026, 10, 12, tzinfo=dt.UTC))
