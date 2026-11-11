"""/llms.txt: built at the site root from the snapshot, served as text/plain,
and free of placeholders and of any "safe" claim."""

from __future__ import annotations

import json
import mimetypes
import re
from pathlib import Path

import pytest
from test_site import build


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build(tmp_path_factory.mktemp("llms"))


def test_llms_txt_is_built_at_the_root(built: Path) -> None:
    assert (built / "llms.txt").is_file()
    # GitHub Pages picks the Content-Type from the extension.
    assert mimetypes.guess_type("llms.txt")[0] == "text/plain"


def test_llms_txt_follows_the_format(built: Path) -> None:
    text = (built / "llms.txt").read_text(encoding="utf-8")
    assert text.startswith("# Lake Notice\n\n> ")
    assert "## Pages" in text and "## Sources" in text
    assert "no all-clear" in text
    assert "Caution" in text and "Warning" in text and "Danger" in text
    assert "14:41 UTC" in text


def test_llms_txt_reads_the_snapshot(built: Path) -> None:
    text = (built / "llms.txt").read_text(encoding="utf-8")
    snap = json.loads((built / "snapshot" / "v1.json").read_text())
    assert f"data date is {snap['run_date']}" in text
    for source in snap["sources"]:
        assert source["agency"] in text
        assert source["dataset_url"] in text
    assert "/state/ca/" in text


def test_llms_txt_has_no_placeholder_and_no_safe_claim(built: Path) -> None:
    text = (built / "llms.txt").read_text(encoding="utf-8")
    for bad in ("TO" + "DO", "T" + "BD", "lorem", "{", "}", "None", "X" * 3):
        assert bad not in text, bad
    # "safe" appears only inside a denial.
    for line in text.splitlines():
        if re.search(r"\bsafe\b", line):
            assert re.search(r"never|not|\"safe\"", line), line
