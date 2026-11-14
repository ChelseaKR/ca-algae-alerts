"""Tide Hours links (DECISIONS 0042): a tidal water page links its nearest
Tide Hours station only when a reviewed row names it, says plainly that it is
Chelsea's other site, copies no tide time or height, and drops the link when
the water is gone. Each negative control checks that its sabotage changed the
input before it checks that the guard noticed."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from paths import PAGE, TRAPS

from caalgae import cli, site

LABEL = "Tide Hours, another free site by Chelsea Kelly-Reif, who makes Lake Notice"
LAKE = "ca-alameda-lake-alpha"
OTHER = "ca-calaveras-tuolumne-epsilon-creek"
_PARA = re.compile(r'<p id="tide-hours">.*?</p>', re.S)
_TAG = re.compile(r"<[^>]+>")


def _rows() -> list[dict[str, object]]:
    return [
        {"ln_id": LAKE, "ln_name": "Lake Alpha", "station_id": "9414750",
         "station_name": "Alameda", "miles": 0.5},
        {"ln_id": "ca-nowhere-gone-lake", "ln_name": "Gone Lake",
         "station_id": "9414290", "station_name": "San Francisco (Golden Gate)",
         "miles": 0.6},
    ]  # fmt: skip


def build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, rows: list[dict[str, object]]
) -> Path:
    stations = tmp_path / "stations.json"
    stations.write_text(json.dumps({"stations": rows}), encoding="utf-8")
    monkeypatch.setattr(site, "TIDE_HOURS_STATIONS_FILE", stations)
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


def test_listed_water_links_its_station_with_plain_label(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = build(tmp_path, monkeypatch, _rows())
    page = water_html(out, LAKE)
    match = _PARA.search(page)
    assert match, "no Tide Hours sentence"
    text = re.sub(r"\s+", " ", _TAG.sub(" ", match.group(0)))
    assert LABEL in text
    assert "nearest NOAA tide station, Alameda (0.5 mi away)" in text
    assert '<a href="https://tidehours.com/stations/9414750/">' in page
    # A plain link: no tag, no tracking parameter, no sponsored rel.
    anchor = re.search(r'<a href="https://tidehours\.com[^>]*>', page)
    assert anchor and "?" not in anchor.group(0) and "rel=" not in anchor.group(0)
    # It sits after the status and before the after-contact advice.
    assert page.index('id="status"') < page.index('id="tide-hours"')
    assert page.index('id="tide-hours"') < page.index('id="after-contact"')
    # No tide time or height is copied onto the page.
    assert not re.search(r"\d+:\d\d\s*(?:a\.?m\.?|p\.?m\.?)|\bft\b", text, re.I)


def test_unlisted_and_gone_waters_get_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = build(tmp_path, monkeypatch, _rows())
    assert 'id="tide-hours"' not in water_html(out, OTHER)
    assert not (out / "water" / "ca-nowhere-gone-lake").exists()
    assert "tidehours.com" not in "".join(
        p.read_text(encoding="utf-8") for p in out.rglob("*.html") if LAKE not in str(p)
    )


def test_empty_file_builds_the_site_as_before(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = build(tmp_path, monkeypatch, [])
    assert "tidehours.com" not in water_html(out, LAKE)


@pytest.mark.parametrize(
    ("field", "bad"),
    [
        ("ln_id", "mo-alameda-lake-alpha"),
        ("station_id", "941475"),
        ("station_id", "../9414750"),
        ("station_name", "  "),
        ("miles", 1.4),
        ("miles", 0),
        ("miles", "0.5"),
    ],
)
def test_a_malformed_row_is_an_error(field: str, bad: object) -> None:
    rows = _rows()
    assert rows[0][field] != bad
    rows[0][field] = bad
    assert rows[0][field] == bad
    with pytest.raises(ValueError, match="bad row"):
        site.tide_hours_links(rows, [LAKE])


def test_a_water_listed_twice_is_an_error() -> None:
    rows = _rows()
    rows[1]["ln_id"] = LAKE
    assert rows[0]["ln_id"] == rows[1]["ln_id"]
    with pytest.raises(ValueError, match="listed twice"):
        site.tide_hours_links(rows, [LAKE])


def test_the_committed_file_is_valid_and_reviewed() -> None:
    doc = json.loads(site.TIDE_HOURS_STATIONS_FILE.read_text("utf-8"))
    rows = doc["stations"]
    ids = [r["ln_id"] for r in rows]
    links = site.tide_hours_links(rows, ids)
    assert len(links) == len(rows) == 35
    assert doc["reviewed_on"] == "2026-11-13"
    # Nothing excluded as not tidal comes back as a row.
    assert not set(ids) & set(doc["excluded_not_tidal"])
    assert all(r["ln_id"].startswith("ca-") for r in rows)
