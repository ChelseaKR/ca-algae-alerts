"""Find and download the current FHAB "Responses" CSV from data.ca.gov.

The rules this module enforces (docs/LICENSES-AND-ATTRIBUTION.md):

- **Never call the CKAN API.** ``https://data.ca.gov/robots.txt`` and
  ``https://publish.data.ca.gov/robots.txt`` both disallow ``/api/``. The
  file's name carries its date (``hab-responses_2026-10-09.csv``), so the
  download URL changes; it is discovered by reading the dataset's HTML page,
  which robots.txt allows.
- **Never touch the state's map site.** ``mywaterquality.ca.gov`` allows
  only Googlebot. ``guard_url`` refuses that host outright.
- One dataset page and one file per run, with an identifying User-Agent.

A failed or suspicious fetch stops the run. It never becomes "no
advisories": see ``assert_not_regressed`` and ``cli.run``.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import re
import urllib.parse
import urllib.robotparser

import httpx

from caalgae import __version__

DATASET_PAGE_URL = (
    "https://data.ca.gov/dataset/surface-water-freshwater-harmful-algal-blooms"
)
USER_AGENT = (
    f"ca-algae-alerts/{__version__} (+https://github.com/ChelseaKR/ca-algae-alerts)"
)
# The dataset this program publishes under. The page also lists files of
# related datasets (Safe to Swim, drinking water), so the match is pinned to
# this dataset's id and to the Responses file name, never "the first CSV".
FHAB_DATASET_ID = "ab672540-aecd-42f1-9b05-9aad326f97ec"
_RESPONSES_LINK = re.compile(
    r"https://publish\.data\.ca\.gov/dataset/(?P<dataset>[0-9a-f-]{36})"
    r"/resource/(?P<resource>[0-9a-f-]{36})"
    r"/download/hab-responses_(?P<date>\d{4}-\d{2}-\d{2})\.csv"
)
# Paths robots.txt disallows on the two data.ca.gov hosts, read 2026-10-12,
# and the API prefixes data.ny.gov's robots.txt disallows, read 2026-11-02
# (its other rules cover browse and catalog pages this pipeline never asks for).
_DISALLOWED_PREFIXES = {
    "data.ca.gov": ("/api/", "/datastore/", "/search?"),
    "publish.data.ca.gov": ("/api/",),
    "data.ny.gov": ("/api/odata/", "/OData.svc/", "/api/collocate", "/tiles/"),
}
_FORBIDDEN_HOSTS = frozenset({"mywaterquality.ca.gov", "www.mywaterquality.ca.gov"})
# 7.1 MB on 2026-10-09; growth is ~1 MB a year. A file far above this is not
# the file we expect.
MAX_CSV_BYTES = 64 * 1024 * 1024
TIMEOUT = httpx.Timeout(60.0, connect=20.0)


class FetchError(RuntimeError):
    """The source could not be read safely. The run must stop."""


@dataclasses.dataclass(frozen=True)
class SourceFile:
    url: str
    resource_id: str
    file_date: dt.date

    @property
    def file_name(self) -> str:
        return f"hab-responses_{self.file_date.isoformat()}.csv"


@dataclasses.dataclass(frozen=True)
class Download:
    source: SourceFile
    body: bytes
    fetched_at: dt.datetime


def guard_url(url: str) -> None:
    """Refuse a URL this pipeline must never request."""
    parts = urllib.parse.urlsplit(url)
    host = (parts.hostname or "").lower()
    if parts.scheme != "https":
        raise FetchError(f"refusing non-HTTPS URL: {url}")
    if host in _FORBIDDEN_HOSTS:
        raise FetchError(f"refusing {host}: its robots.txt allows only Googlebot")
    target = parts.path + (f"?{parts.query}" if parts.query else "")
    for prefix in _DISALLOWED_PREFIXES.get(host, ()):
        if target.startswith(prefix):
            raise FetchError(f"refusing {url}: robots.txt disallows {prefix}")


def discover_responses_file(html: str) -> SourceFile:
    """Pick the Responses CSV link out of the dataset page.

    Exactly one distinct Responses file of this dataset must be linked. Two
    different dates on one page means the page is mid-update or reshaped,
    and guessing would risk publishing an older file as current.
    """
    found: dict[str, SourceFile] = {}
    for match in _RESPONSES_LINK.finditer(html):
        if match.group("dataset") != FHAB_DATASET_ID:
            continue
        file_date = dt.date.fromisoformat(match.group("date"))
        found[match.group(0)] = SourceFile(
            url=match.group(0),
            resource_id=match.group("resource"),
            file_date=file_date,
        )
    if not found:
        raise FetchError(
            "the dataset page links no hab-responses_<date>.csv for the FHAB "
            "dataset; the page may have changed shape"
        )
    if len(found) > 1:
        names = ", ".join(sorted(f.file_name for f in found.values()))
        raise FetchError(
            f"the dataset page links more than one Responses file: {names}"
        )
    return next(iter(found.values()))


def assert_not_regressed(
    source: SourceFile, previous_file_date: dt.date | None
) -> None:
    """Refuse a file older than the one the last published run used."""
    if previous_file_date is not None and source.file_date < previous_file_date:
        raise FetchError(
            f"the dataset page now links {source.file_name}, older than "
            f"{previous_file_date.isoformat()} which the last run used"
        )


def _get(client: httpx.Client, url: str) -> httpx.Response:
    guard_url(url)
    try:
        response = client.get(url)
    except httpx.HTTPError as error:
        raise FetchError(f"GET {url} failed: {error}") from error
    if response.status_code != 200:
        raise FetchError(f"GET {url} returned HTTP {response.status_code}")
    return response


def fetch_dataset_page(client: httpx.Client) -> str:
    return _get(client, DATASET_PAGE_URL).text


def fetch_csv(client: httpx.Client, source: SourceFile, now: dt.datetime) -> Download:
    """Download the file. The redirect to a short-lived signed storage URL
    is followed; only the first hop is ours to choose and guard."""
    response = _get(client, source.url)
    body = response.content
    if len(body) > MAX_CSV_BYTES:
        raise FetchError(f"{source.file_name} is {len(body)} bytes, over the cap")
    if not body:
        raise FetchError(f"{source.file_name} is empty")
    return Download(source=source, body=body, fetched_at=now)


def make_client() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": USER_AGENT},
        timeout=TIMEOUT,
        follow_redirects=True,
    )


class RobotsOffLimits(FetchError):
    """The host's robots.txt could not be read, or disallows the path."""


def robots_allows(
    client: httpx.Client, url: str
) -> urllib.robotparser.RobotFileParser | None:
    """Read the host's robots.txt before touching it (docs/DECISIONS.md 0011).

    Returns the parsed file, so a caller can check further paths on the same
    host and honor its crawl delay, or None when the host has no robots.txt.

    - 200: parsed and enforced for our User-Agent.
    - 404 (no robots.txt): no rules. The owner's ruling of 2026-10-12.
    - A redirect to anything but a robots.txt, 403, 5xx (ArcGIS's 403
      "Invalid URL"), any other status, or no answer: the host is
      off-limits and nothing is fetched from it. Same ruling.
    """
    parts = urllib.parse.urlsplit(url)
    robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
    try:
        response = client.get(robots_url)
    except httpx.HTTPError as error:
        raise RobotsOffLimits(f"{robots_url} did not answer: {error}") from error
    final_path = urllib.parse.urlsplit(str(response.url)).path
    if response.history and final_path != "/robots.txt":
        raise RobotsOffLimits(
            f"{robots_url} redirected to {response.url}, not a robots file; "
            "the host is off-limits"
        )
    if response.status_code == 404:
        return None
    if response.status_code != 200:
        raise RobotsOffLimits(
            f"{robots_url} returned HTTP {response.status_code}; the host is off-limits"
        )
    parser = urllib.robotparser.RobotFileParser()
    parser.parse(response.text.splitlines())
    if not parser.can_fetch(USER_AGENT, url):
        raise RobotsOffLimits(f"{robots_url} disallows {parts.path}")
    return parser
