"""The built site: every page, every link, the sitemap, the structured
data, and the copy rules (never "safe", always a date)."""

from __future__ import annotations

import datetime as dt
import html
import json
import re
from pathlib import Path
from typing import Any

import pytest
from paths import PAGE, SAMPLE, TRAPS

from caalgae import cli, site, wording

_TAG = re.compile(r"<[^>]+>")
_SCRIPT = re.compile(r"<script\b.*?</script>", re.S)
_HREF = re.compile(r'href="([^"]+)"')


def build(tmp_path: Path, csv: Path = TRAPS, *extra: str) -> Path:
    out = tmp_path / "site"
    assert (
        cli.main(
            [
                "--fixture-page", str(PAGE),
                "--fixture-csv", str(csv),
                "--run-today", "2026-10-12",
                "--history", str(tmp_path / "history.json"),
                "--site-out", str(out),
                *extra,
            ]
        )
        == 0
    )  # fmt: skip
    return out


@pytest.fixture(scope="module")
def traps_site(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build(tmp_path_factory.mktemp("traps"))


@pytest.fixture(scope="module")
def sample_site(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build(tmp_path_factory.mktemp("sample"), SAMPLE)


def text_of(page: Path) -> str:
    raw = _SCRIPT.sub(" ", page.read_text(encoding="utf-8"))
    raw = re.sub(r"<title>.*?</title>|<meta[^>]*>", " ", raw, flags=re.S)
    return html.unescape(re.sub(r"\s+", " ", _TAG.sub(" ", raw)))


def pages(root: Path) -> list[Path]:
    return sorted(root.rglob("*.html"))


def snapshot_of(root: Path) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads((root / "snapshot" / "v1.json").read_text())
    return loaded


def test_expected_pages_exist(traps_site: Path) -> None:
    for rel in ["index.html", "advisories/index.html", "county/index.html",
                "county/alameda/index.html", "dogs/index.html", "about/index.html",
                "privacy/index.html", "support/index.html", "404.html",
                "sitemap.xml", "robots.txt", "snapshot/v1.json", "assets/style.css"]:  # fmt: skip
        assert (traps_site / rel).exists(), rel
    for water in snapshot_of(traps_site)["waterbodies"]:
        assert (traps_site / "water" / water["id"] / "index.html").exists()


def test_every_relative_link_resolves(sample_site: Path) -> None:
    for page in pages(sample_site):
        if page.name == "404.html":
            continue
        for href in _HREF.findall(page.read_text(encoding="utf-8")):
            if href.startswith(("http", "mailto:", "#")):
                continue
            target = (page.parent / href.split("#")[0]).resolve()
            if target.is_dir():
                target = target / "index.html"
            assert target.exists(), f"{page}: {href}"


def test_sitemap_lists_every_indexable_page(sample_site: Path) -> None:
    sitemap = (sample_site / "sitemap.xml").read_text()
    locs = re.findall(r"<loc>([^<]+)</loc>", sitemap)
    # All but the 404 and the waters staged out of the sitemap.
    staged = len(staging_problems_inputs(sample_site)[1])
    assert len(locs) == len(pages(sample_site)) - 1 - staged
    assert all(loc.startswith(site.DEFAULT_BASE_URL) for loc in locs)
    assert "404" not in sitemap


def test_home_lists_recent_advisories_newest_first_with_dates(traps_site: Path) -> None:
    text = text_of(traps_site / "index.html")
    assert "Delta Lake" in text and "Lake Alpha" in text
    assert text.index("Delta Lake") < text.index("Lake Alpha")  # Sep 25 before Sep 20
    assert "Sep 25, 2026" in text
    # Zeta Lake's 2019 advisory is not "recent" but is still counted.
    assert "Zeta Lake" not in text
    assert (
        "including 4 older" in text
    )  # Gamma, Eta, Iota (over 30 days) and Zeta (2019)
    assert "Zeta Lake" in text_of(traps_site / "advisories" / "index.html")


def test_old_unlifted_advisory_reads_as_last_posted_with_no_all_clear(
    traps_site: Path,
) -> None:
    text = text_of(traps_site / "water" / "ca-nevada-state-zeta-lake" / "index.html")
    assert "Caution advisory, last posted Jul 15, 2019. No all-clear recorded." in text


def test_blank_end_date_never_renders_as_ended(traps_site: Path) -> None:
    text = text_of(traps_site / "water" / "ca-alameda-lake-alpha" / "index.html")
    assert "No all-clear recorded" in text
    assert "End date recorded" not in text
    assert not re.search(r"\bended\b", text, re.I)


def test_lift_reads_as_the_states_record_with_its_date(traps_site: Path) -> None:
    text = text_of(traps_site / "water" / "ca-lake-beta-reservoir" / "index.html")
    assert (
        "The state's latest record, from Sep 1, 2026, recommends no advisory." in text
    )
    assert "not a finding that the water is safe" in text
    assert "Last advisory on file: Jul 1, 2026." in text


def test_undetermined_is_not_presented_as_clear(traps_site: Path) -> None:
    text = text_of(traps_site / "water" / "ca-marin-theta-lake" / "index.html")
    assert "no advisory level the state has classified" in text
    assert "recommends no advisory" not in text


def test_lake_pages_speak_to_everyone_and_label_the_dog_section(
    traps_site: Path,
) -> None:
    page = (traps_site / "water" / "ca-alameda-lake-alpha" / "index.html").read_text()
    assert '<h2 id="dogs">Dogs at Lake Alpha</h2>' in page
    assert "people, children and pets" in text_of(
        traps_site / "water" / "ca-alameda-lake-alpha" / "index.html"
    )


# -- the copy guard -------------------------------------------------------

_SPLIT = re.compile(r"(?<=[.!?])\s+")
_SAFETY = re.compile(r"\b(?:safe|safety|all[- ]clear)\b", re.I)
_NEGATION = re.compile(r"\b(?:not|never|no|cannot|isn't|doesn't)\b|n't\b", re.I)


def affirmative_safety_claims(text: str) -> list[str]:
    """Sentences that mention safety or an all-clear without negating it or
    asking it. "No all-clear recorded" and "does not mean safe" pass; "safe
    to swim" does not."""
    out = []
    for sentence in _SPLIT.split(text):
        sentence = sentence.strip()
        if not _SAFETY.search(sentence):
            continue
        if sentence.endswith("?") or _NEGATION.search(sentence):
            continue
        out.append(sentence)
    return out


def test_guard_catches_an_affirmative_claim() -> None:
    # Negative control: the guard is not vacuous.
    assert affirmative_safety_claims("Lake Alpha is safe for swimming.") == [
        "Lake Alpha is safe for swimming."
    ]
    assert affirmative_safety_claims("All-clear recorded on Sep 1.") != []
    assert affirmative_safety_claims("No all-clear recorded. Is it safe?") == []


@pytest.mark.parametrize("which", ["traps_site", "sample_site"])
def test_no_page_claims_a_water_is_safe(
    which: str, request: pytest.FixtureRequest
) -> None:
    root: Path = request.getfixturevalue(which)
    problems = []
    for page in pages(root):
        problems += [
            f"{page.relative_to(root)}: {s}"
            for s in affirmative_safety_claims(text_of(page))
        ]
        title = re.search(r"<title>(.*?)</title>", page.read_text(), re.S)
        assert title
        problems += [
            f"{page.relative_to(root)} title: {s}"
            for s in affirmative_safety_claims(html.unescape(title.group(1)))
        ]
    assert problems == []


def test_wording_module_never_says_safe_affirmatively() -> None:
    statuses = [
        {
            "kind": "advisory",
            "tier": "caution",
            "level": "Caution",
            "posted": "2026-09-01",
        },
        {
            "kind": "advisory",
            "tier": "other_advisory",
            "level": "Algal mat alert sign",
            "posted": "2026-09-01",
        },
        {
            "kind": "no_advisory_recorded",
            "lift_kind": "no_advisory_record",
            "lift_date": "2026-09-01",
        },
        {
            "kind": "no_advisory_recorded",
            "lift_kind": "end_date",
            "lift_date": "2026-09-01",
        },
        {"kind": "undetermined"},
    ]
    for s in statuses:
        for line in (
            wording.headline(s),
            wording.caveat(s),
            wording.dog_answer("X", s),
        ):
            assert affirmative_safety_claims(line) == [], line
    for line in [*wording.LEVEL_GUIDANCE.values(), wording.DOG_ADVICE]:
        assert affirmative_safety_claims(line) == [], line


def test_date_label_refuses_a_missing_date() -> None:
    assert wording.date_label(dt.date(2026, 10, 9)) == "Oct 9, 2026"
    with pytest.raises(ValueError):
        wording.date_label(None)


# -- structured data ------------------------------------------------------


def structured(page: Path) -> dict[str, Any]:
    match = re.search(
        r'<script type="application/ld\+json">(.*?)</script>', page.read_text(), re.S
    )
    assert match
    loaded: dict[str, Any] = json.loads(match.group(1))
    return loaded


def test_structured_data_matches_what_the_page_shows(sample_site: Path) -> None:
    for water in snapshot_of(sample_site)["waterbodies"]:
        page = sample_site / "water" / water["id"] / "index.html"
        data = structured(page)
        webpage = data["@graph"][1]
        assert webpage["about"]["name"] == water["name"]
        assert (
            f"<h1>{html.escape(water['name'], quote=False)}: toxic algae advisories</h1>"
            in page.read_text()
        )
        assert "safe" not in json.dumps(data).lower()
        assert webpage["isBasedOn"].startswith("https://data.ca.gov/")
        crumbs = data["@graph"][0]["itemListElement"]
        assert crumbs[-1]["name"] == water["name"]


def test_home_structured_data_is_a_website(traps_site: Path) -> None:
    data = structured(traps_site / "index.html")
    assert data["@type"] == "WebSite"


# -- analytics -------------------------------------------------------------


def test_no_analytics_by_default_and_privacy_says_so(traps_site: Path) -> None:
    for page in pages(traps_site):
        assert "googletagmanager" not in page.read_text()
    assert "nothing" in text_of(
        traps_site / "privacy" / "index.html"
    ).lower() or "No cookies" in text_of(traps_site / "privacy" / "index.html")


def test_ga4_when_configured_honors_gpc_before_loading(
    tmp_path: Path, traps_site: Path
) -> None:
    snap = snapshot_of(traps_site)
    out = tmp_path / "ga"
    site.build_site(snap, out, ga4_measurement_id="G-TEST123")
    page = (out / "index.html").read_text()
    gpc = page.index("navigator")
    assert page.index("globalPrivacyControl === true) return") < page.index(
        "createElement"
    )
    assert gpc < page.index("googletagmanager")
    assert "allow_google_signals: false" in page
    assert "ca-algae-alerts:analytics-opt-out" in page
    assert "Google Analytics 4" in text_of(out / "privacy" / "index.html")


def test_404_uses_absolute_links_and_is_noindex(traps_site: Path) -> None:
    page = (traps_site / "404.html").read_text()
    assert 'name="robots" content="noindex"' in page
    assert f'href="{site.DEFAULT_BASE_URL}assets/style.css"' in page


def test_base_url_and_support_email(tmp_path: Path) -> None:
    out = build(
        tmp_path,
        TRAPS,
        "--base-url",
        "https://example.org/x",
        "--support-email",
        "help@example.org",
    )
    assert (
        '<link rel="canonical" href="https://example.org/x/">'
        in (out / "index.html").read_text()
    )
    assert "help@example.org" in (out / "support" / "index.html").read_text()


# -- sitemap staging: only waters with a recent advisory are indexable ----------

_ROBOTS = re.compile(r'<meta name="robots" content="([^"]*)"')


def staging_problems_inputs(root: Path) -> tuple[list[str], list[str]]:
    """(water ids with an indexable page, water ids staged out) as the
    snapshot and the constant say they should be."""
    snap = snapshot_of(root)
    run = dt.date.fromisoformat(snap["run_date"])
    keep, out = [], []
    for w in snap["waterbodies"]:
        (keep if site.is_indexable(w, run, site.INDEX_WINDOW_MONTHS) else out).append(
            w["id"]
        )
    return keep, out


def staging_problems(root: Path) -> list[str]:
    """Disagreements between the snapshot's rule, each water page's robots
    tag and the sitemap, and a check that the counts add up."""
    keep, out = staging_problems_inputs(root)
    locs = set(re.findall(r"<loc>([^<]+)</loc>", (root / "sitemap.xml").read_text()))
    problems = []
    listed = noindex = 0
    for wid in keep + out:
        raw = (root / "water" / wid / "index.html").read_text(encoding="utf-8")
        robots = _ROBOTS.search(raw)
        url = f"{site.DEFAULT_BASE_URL}water/{wid}/"
        in_map = url in locs
        listed += in_map
        noindex += bool(robots)
        if wid in keep and (robots or not in_map):
            problems.append(f"{wid}: recent but noindex or missing from the sitemap")
        if wid in out and (not robots or in_map):
            problems.append(f"{wid}: stale but indexable or in the sitemap")
        if robots and robots.group(1) != "noindex,follow":
            problems.append(f"{wid}: robots is {robots.group(1)}")
        if bool(robots) == in_map:
            problems.append(f"{wid}: sitemap and robots disagree")
    if listed + noindex != len(keep) + len(out):
        problems.append(f"counts do not add up: {listed} + {noindex}")
    return problems


@pytest.mark.parametrize("which", ["traps_site", "sample_site"])
def test_sitemap_and_robots_follow_the_recent_advisory_rule(
    which: str, request: pytest.FixtureRequest
) -> None:
    root: Path = request.getfixturevalue(which)
    keep, out = staging_problems_inputs(root)
    assert keep and out  # the fixtures exercise both sides of the rule
    assert staging_problems(root) == []


def test_months_before_clamps_the_day() -> None:
    assert site.months_before(dt.date(2026, 10, 22), 24) == dt.date(2024, 10, 22)
    assert site.months_before(dt.date(2026, 3, 31), 1) == dt.date(2026, 2, 28)
    assert site.months_before(dt.date(2026, 1, 15), 1) == dt.date(2025, 12, 15)
    water = {"status": {"last_advisory": "2024-10-22"}}
    assert site.is_indexable(water, dt.date(2026, 10, 22), 24)
    assert not site.is_indexable(water, dt.date(2026, 10, 23), 24)
    assert not site.is_indexable(
        {"status": {"last_advisory": None}}, dt.date(2026, 1, 1), 24
    )


def test_other_pages_stay_indexable(traps_site: Path) -> None:
    for rel in ["index.html", "advisories/index.html", "dogs/index.html",
                "county/index.html", "county/alameda/index.html"]:  # fmt: skip
        assert _ROBOTS.search((traps_site / rel).read_text()) is None, rel


def test_staging_changes_only_the_head_of_a_water_page(
    tmp_path: Path, traps_site: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(site, "INDEX_WINDOW_MONTHS", 1200)
    everything = build(tmp_path)
    _, out = staging_problems_inputs(traps_site)
    assert out

    def body(path: Path) -> str:
        return re.sub(r"<head>.*?</head>", "", path.read_text(), flags=re.S)

    for wid in out:
        rel = Path("water") / wid / "index.html"
        assert body(traps_site / rel) == body(everything / rel)


@pytest.mark.parametrize("sabotage", ["stale_in_sitemap", "recent_noindex", "disagree"])
def test_staging_guard_catches_each_sabotage(sabotage: str, tmp_path: Path) -> None:
    # Negative controls: break a built copy, assert the break applied, then
    # assert the guard reports it.
    root = build(tmp_path)
    keep, out = staging_problems_inputs(root)
    assert staging_problems(root) == []
    sitemap = root / "sitemap.xml"
    before = sitemap.read_text()
    if sabotage == "stale_in_sitemap":
        url = f"{site.DEFAULT_BASE_URL}water/{out[0]}/"
        sitemap.write_text(
            before.replace("</urlset>", f"<url><loc>{url}</loc></url></urlset>")
        )
        assert sitemap.read_text() != before
    elif sabotage == "recent_noindex":
        page = root / "water" / keep[0] / "index.html"
        raw = page.read_text()
        page.write_text(
            raw.replace(
                "<title>", '<meta name="robots" content="noindex,follow"><title>', 1
            )
        )
        assert page.read_text() != raw
    else:
        url = f"{site.DEFAULT_BASE_URL}water/{keep[0]}/"
        assert f"<loc>{url}</loc>" in before
        sitemap.write_text(before.replace(f"<loc>{url}</loc>", "<loc>x</loc>"))
        assert sitemap.read_text() != before
    assert staging_problems(root) != []
