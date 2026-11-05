"""IndexNow on the real fixture build and in the publish workflow.

The key file ships only in a lakenotice.com build, every URL the sitemap lists
is announceable (own host, built, indexable), robots.txt lets Bingbot in and
names the sitemap, and the workflow selects before the deploy and submits only
in a job after it, never with continue-on-error (the standards ban it)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from paths import PAGE, TRAPS

from caalgae import cli, site
from caalgae import indexnow as ix

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "publish.yml"
DOMAIN_URL = f"https://{site.SITE_DOMAIN}"


def _build(root: Path, *extra: str) -> Path:
    out = root / "site"
    assert (
        cli.main(
            [
                "--fixture-page", str(PAGE),
                "--fixture-csv", str(TRAPS),
                "--run-today", "2026-10-12",
                "--history", str(root / "history.json"),
                "--site-out", str(out),
                *extra,
            ]
        )
        == 0
    )  # fmt: skip
    return out


@pytest.fixture(scope="module")
def domain_site(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return _build(tmp_path_factory.mktemp("ixdomain"), "--base-url", DOMAIN_URL)


def test_the_domain_build_carries_exactly_one_matching_key_file(
    domain_site: Path,
) -> None:
    key = ix.find_key(domain_site)
    assert (domain_site / f"{key}.txt").read_text(encoding="utf-8").strip() == key
    assert re.fullmatch(r"[0-9a-f]{32}", key)


def test_a_build_for_another_host_has_no_key_file(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    other = _build(
        tmp_path_factory.mktemp("ixother"), "--base-url", "https://example.org/x"
    )
    assert not [p for p in other.iterdir() if ix.KEY_FILE_RE.match(p.name)]


def test_robots_allows_bingbot_and_lists_the_sitemap(domain_site: Path) -> None:
    robots = (domain_site / "robots.txt").read_text(encoding="utf-8")
    assert ix.check_robots(robots, DOMAIN_URL) == []


def test_every_sitemap_url_is_announceable(domain_site: Path) -> None:
    entries = ix.parse_sitemap(
        (domain_site / "sitemap.xml").read_text(encoding="utf-8")
    )
    assert len(entries) > 5
    kept, notes = ix.filter_submittable(
        sorted(entries), base_url=DOMAIN_URL, site_dir=domain_site
    )
    assert notes == []
    assert kept == sorted(entries)


def test_selection_on_the_real_sitemap_finds_exactly_the_edits(
    domain_site: Path,
) -> None:
    cur = ix.parse_sitemap((domain_site / "sitemap.xml").read_text(encoding="utf-8"))
    urls = sorted(cur)
    prev = dict(cur)
    removed, bumped = urls[1], urls[3]
    del prev[removed]
    prev[bumped] = "2000-01-01"
    assert prev != cur  # the sabotage applied
    assert ix.select_changed(prev, cur) == sorted([removed, bumped])
    assert ix.select_changed(cur, cur) == []


def _block(text: str, start: str, end: str) -> str:
    i = text.index(start)
    return text[i : text.index(end, i + len(start))]


def test_workflow_selects_before_the_deploy_and_submits_in_a_job_after_it() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    build = _block(text, "\n  build:\n", "\n  deploy:\n")
    select = build.index("- name: pick the pages to announce to IndexNow")
    keep = build.index("- name: keep the IndexNow list")
    pages = build.index("- name: upload the site as a Pages artifact")
    assert select < keep < pages
    job = _block(text, "\n  indexnow:\n", "\n  alert-on-failure:\n")
    assert "    needs: deploy\n" in job
    assert "indexnow.py submit" in job
    assert "indexnow.py submit" not in build
    # The standards ban continue-on-error; indexnow.py exits 0 instead.
    code = [ln for ln in text.splitlines() if not ln.strip().startswith("#")]
    assert not [ln for ln in code if "continue-on-error" in ln]
    assert "secrets." not in job
    # A refused ping never opens the publish-failure issue.
    assert "needs: [build, deploy]" in text
    # Only the publish workflow calls it, never pull-request CI.
    ci = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "indexnow" not in ci
