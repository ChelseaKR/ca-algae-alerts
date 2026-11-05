"""Trout Truck links (DECISIONS 0026): a water page links the same water's
Trout Truck page only when a reviewed pair names it, says plainly that it is
Chelsea's other site, copies none of Trout Truck's planting data, and drops
the link when either page is gone."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from paths import PAGE, TRAPS

from caalgae import cli, site

ROOT = Path(__file__).resolve().parents[2]
LN_SNAPSHOT = ROOT / "ios" / "AlgaeAlerts" / "Resources" / "snapshot.json"
LABEL = "Trout Truck, another free site by Chelsea Kelly-Reif, who makes Lake Notice"
LAKE = "ca-alameda-lake-alpha"
CREEK = "ca-calaveras-tuolumne-epsilon-creek"
_SECTION = re.compile(r'<h2 id="trout-plantings">.*?(?=<h2 )', re.S)
_TAG = re.compile(r"<[^>]+>")


def _pairs() -> list[dict[str, object]]:
    return [
        {"ln_id": LAKE, "tt_path": "/water/alpha-lake/", "tt_name": "Alpha Lake",
         "kind": "lake", "tier": "A", "miles_apart": 0.2},
        {"ln_id": CREEK, "tt_path": "/water/epsilon-creek/", "tt_name": "Epsilon Creek",
         "kind": "stream", "tier": "A", "miles_apart": 1.0},
    ]  # fmt: skip


def build(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    pairs: list[dict[str, object]],
    tt_paths: list[str],
) -> Path:
    pairs_file = tmp_path / "pairs.json"
    pages_file = tmp_path / "pages.json"
    pairs_file.write_text(json.dumps({"pairs": pairs}), encoding="utf-8")
    pages_file.write_text(json.dumps({"paths": tt_paths}), encoding="utf-8")
    monkeypatch.setattr(site, "TROUT_TRUCK_PAIRS_FILE", pairs_file)
    monkeypatch.setattr(site, "TROUT_TRUCK_PAGES_FILE", pages_file)
    out = tmp_path / "site"
    assert (
        cli.main(
            [
                "--fixture-page", str(PAGE),
                "--fixture-csv", str(TRAPS),
                "--run-today", "2026-10-12",
                "--history", str(tmp_path / "history.json"),
                "--site-out", str(out),
            ]
        )
        == 0
    )  # fmt: skip
    return out


def water_html(out: Path, water_id: str) -> str:
    return (out / "water" / water_id / "index.html").read_text(encoding="utf-8")


def section_text(page: str) -> str:
    match = _SECTION.search(page)
    assert match, "no Trout Truck section"
    return re.sub(r"\s+", " ", _TAG.sub(" ", match.group(0)))


def test_paired_water_links_trout_truck_with_plain_label(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = build(
        tmp_path, monkeypatch, _pairs(), ["/water/alpha-lake/", "/water/epsilon-creek/"]
    )
    page = water_html(out, LAKE)
    assert '<a href="https://trouttruck.com/water/alpha-lake/">' in page
    text = section_text(page)
    assert LABEL in text
    assert "Alpha Lake trout planting schedule on Trout Truck" in text
    # Section sits after "Matching names nearby" and before the dogs section.
    assert page.index('id="trout-plantings"') < page.index('id="dogs"')
    # A plain link: no tag, no tracking parameter, no sponsored rel.
    anchor = re.search(r'<a href="https://trouttruck\.com[^>]*>', page)
    assert anchor and "?" not in anchor.group(0) and "rel=" not in anchor.group(0)


def test_section_copies_no_status_or_date(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = build(
        tmp_path, monkeypatch, _pairs(), ["/water/alpha-lake/", "/water/epsilon-creek/"]
    )
    for water_id in (LAKE, CREEK):
        text = section_text(water_html(out, water_id)).casefold()
        assert not re.search(r"\d", text), text
        for word in ("advisory", "caution", "warning", "danger", "safe", "week of",
                     "planted on", "last planted", "this week", "stocked"):  # fmt: skip
            assert word not in text, (word, text)


def test_stream_pair_says_reports_may_be_another_stretch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = build(
        tmp_path, monkeypatch, _pairs(), ["/water/alpha-lake/", "/water/epsilon-creek/"]
    )
    stretch = "which may be on a different stretch"
    assert stretch in section_text(water_html(out, CREEK))
    assert stretch not in section_text(water_html(out, LAKE))


def test_unpaired_pages_and_sitewide_pages_have_no_trout_truck_link(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = build(
        tmp_path, monkeypatch, _pairs(), ["/water/alpha-lake/", "/water/epsilon-creek/"]
    )
    with_link = {
        p.parent.name
        for p in out.rglob("*.html")
        if "trouttruck.com" in p.read_text(encoding="utf-8")
    }
    # Only the two paired water pages: no footer, home, county or about link.
    assert with_link == {LAKE, CREEK}
    assert "Trout Truck" not in water_html(out, "ca-kern-gamma-pond")


def test_removed_trout_truck_page_drops_the_link(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Negative control: the same build with Epsilon Creek gone from Trout
    # Truck's page list. The lake keeps its link, so the removal applied to
    # one row and did not just turn the feature off.
    out = build(tmp_path, monkeypatch, _pairs(), ["/water/alpha-lake/"])
    assert "trouttruck.com" in water_html(out, LAKE)
    creek = water_html(out, CREEK)
    assert "trouttruck.com" not in creek
    assert 'id="trout-plantings"' not in creek


def test_missing_lake_notice_id_drops_the_row() -> None:
    pairs = [*_pairs(), {"ln_id": "ca-gone-lake", "tt_path": "/water/gone-lake/",
                         "tt_name": "Gone Lake", "kind": "lake"}]  # fmt: skip
    links = site.trout_truck_links(
        pairs,
        ["/water/alpha-lake/", "/water/epsilon-creek/", "/water/gone-lake/"],
        [LAKE, CREEK],
    )
    assert set(links) == {LAKE, CREEK}


@pytest.mark.parametrize(
    "bad",
    [
        {"kind": "river"},
        {"tt_path": "water/alpha-lake"},
        {"tt_path": "https://trouttruck.com/water/alpha-lake/"},
        {"tt_name": ""},
    ],
)
def test_malformed_row_is_an_error(bad: dict[str, str]) -> None:
    row = {**_pairs()[0], **bad}
    with pytest.raises(ValueError, match="bad row"):
        site.trout_truck_links([row], ["/water/alpha-lake/"], [LAKE])


def test_water_paired_twice_is_an_error() -> None:
    row = _pairs()[0]
    with pytest.raises(ValueError, match="paired twice"):
        site.trout_truck_links([row, row], ["/water/alpha-lake/"], [LAKE])


def test_committed_pairs_match_both_snapshots() -> None:
    data = json.loads(site.TROUT_TRUCK_PAIRS_FILE.read_text("utf-8"))
    pages = set(json.loads(site.TROUT_TRUCK_PAGES_FILE.read_text("utf-8"))["paths"])
    pairs = data["pairs"]
    assert len(pairs) == 66
    assert len({p["tt_path"] for p in pairs}) == 60
    assert {p["tier"] for p in pairs} <= {"A", "B", "reviewed"}
    ln_ids = {
        w["id"] for w in json.loads(LN_SNAPSHOT.read_text("utf-8"))["waterbodies"]
    }
    links = site.load_trout_truck_links(ln_ids)
    # Every committed pair is live against both committed snapshots.
    assert len(links) == 66
    assert (
        links["ca-mono-crowley-lake"]["url"]
        == "https://trouttruck.com/water/crowley-lake/"
    )
    assert links["ca-plumas-spanish-creek"]["kind"] == "stream"
    # The needs-review rows are listed for a person and never rendered.
    review = {r["ln_id"] for r in data["needs_review"]}
    assert len(review) == 13
    assert "ca-lassen-eagle-lake" in review
    assert not review & set(links)
    assert review <= ln_ids
    assert {r["tt_path"] for r in [*pairs, *data["needs_review"]]} <= pages
