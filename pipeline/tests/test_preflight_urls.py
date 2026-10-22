"""The app's snapshot URL and the site URL are keyed to SITE_DOMAIN.

The iOS code, the docs a shipped build depends on and the pipeline's
published path must agree, because an installed build keeps the URL it was
built with (docs/DECISIONS.md 0013). `url_problems` reads each place and
returns what disagrees; a sabotaged copy must be caught, and each sabotage
test first asserts the edit changed the copy.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from paths import PAGE, SAMPLE

from caalgae import cli, site

ROOT = Path(__file__).resolve().parents[2]
SWIFT = "ios/AlgaeCore/Sources/AlgaeCore/SnapshotStore.swift"
# Files that may not point a reader or the app at the old github.io host.
NO_GITHUB_IO = [
    SWIFT,
    "ios/README.md",
    "docs/app-store/README.md",
    "docs/DOMAIN.md",
    "SECURITY.md",
    "pipeline/src/caalgae/site.py",
]
OLD_HOST = "chelseakr.github.io/ca-algae-alerts"
SNAPSHOT_PATH = "snapshot/v1.json"
_URL_LINE = re.compile(r'static let (url|siteURL) = URL\(string: "([^"]+)"\)!')


def url_problems(root: Path) -> list[str]:
    found: list[str] = []
    swift = (root / SWIFT).read_text(encoding="utf-8")
    urls = dict(_URL_LINE.findall(swift))
    if urls.get("url") != f"https://{site.SITE_DOMAIN}/{SNAPSHOT_PATH}":
        found.append(f"{SWIFT}: SnapshotEndpoint.url is {urls.get('url')!r}")
    if urls.get("siteURL") != f"https://{site.SITE_DOMAIN}/":
        found.append(f"{SWIFT}: SnapshotEndpoint.siteURL is {urls.get('siteURL')!r}")
    for rel in NO_GITHUB_IO:
        if OLD_HOST in (root / rel).read_text(encoding="utf-8"):
            found.append(f"{rel}: still points at the old github.io project URL")
    return found


def test_real_tree_is_keyed_to_the_domain() -> None:
    assert url_problems(ROOT) == []


def test_the_pipeline_publishes_the_path_the_app_fetches(tmp_path: Path) -> None:
    out = tmp_path / "site"
    assert (
        cli.main(
            [
                "--fixture-page", str(PAGE),
                "--fixture-csv", str(SAMPLE),
                "--run-today", "2026-10-12",
                "--history", str(tmp_path / "history.json"),
                "--site-out", str(out),
            ]
        )
        == 0
    )  # fmt: skip
    assert (out / SNAPSHOT_PATH).is_file()
    sitemap = (out / "sitemap.xml").read_text(encoding="utf-8")
    assert f"https://{site.SITE_DOMAIN}/" in sitemap


def test_sabotage_is_caught(tmp_path: Path) -> None:
    for rel in NO_GITHUB_IO:
        dest = tmp_path / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, dest)
    assert url_problems(tmp_path) == []  # the copy starts clean
    swift = tmp_path / SWIFT
    before = swift.read_text(encoding="utf-8")
    swift.write_text(
        before.replace(site.SITE_DOMAIN, "chelseakr.github.io/ca-algae-alerts"),
        encoding="utf-8",
    )
    assert swift.read_text(encoding="utf-8") != before  # the sabotage applied
    problems = url_problems(tmp_path)
    assert any("SnapshotEndpoint.url" in p for p in problems), problems
    assert any("SnapshotEndpoint.siteURL" in p for p in problems), problems
    assert any("old github.io" in p for p in problems), problems
