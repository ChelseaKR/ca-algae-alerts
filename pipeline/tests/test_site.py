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

from caalgae import cli, site, water_names, wording

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


def lede_of(page: Path) -> str:
    match = re.search(r'<p class="lede">(.*?)</p>', page.read_text(), re.S)
    assert match
    return html.unescape(re.sub(r"\s+", " ", _TAG.sub(" ", match.group(1)))).strip()


def test_water_page_opens_with_a_dated_answer(traps_site: Path) -> None:
    # The first sentence after the h1 names the water, its county, the date
    # of the state's file and the status, so it reads correctly when quoted
    # on its own. It is the status box's headline, never a new claim.
    water = traps_site / "water"
    assert lede_of(water / "ca-alameda-lake-alpha" / "index.html").startswith(
        "As of the state's data dated Oct 9, 2026, the records for Lake Alpha "
        "(Alameda County) show: Caution advisory, last posted Sep 20, 2026. "
        "No all-clear recorded."
    )
    beta = lede_of(water / "ca-lake-beta-reservoir" / "index.html")
    assert (
        "show: The state's latest record, from Sep 1, 2026, recommends no "
        "advisory. That is not a finding that the water is safe now." in beta
    )
    theta = lede_of(water / "ca-marin-theta-lake" / "index.html")
    assert "no advisory level the state has classified" in theta
    assert "not a finding that the water is safe now" in theta


def test_summary_leaves_out_a_missing_date_and_never_says_safe() -> None:
    advisory = {"kind": "advisory", "tier": "danger", "posted": "2026-10-16"}
    line = wording.summary("Lake X", "Alameda County", advisory, None)
    assert line == (
        "The state's records for Lake X (Alameda County) show: Danger advisory, "
        "last posted Oct 16, 2026. No all-clear recorded."
    )
    assert "As of" not in line and "safe" not in line
    none = {"kind": "no_advisory_recorded", "lift_kind": "no_advisory_record",
            "lift_date": "2026-09-01"}  # fmt: skip
    line = wording.summary("Lake X", None, none, "2026-10-30")
    assert line.startswith(
        "As of the state's data dated Oct 30, 2026, the records for Lake X show:"
    )
    assert affirmative_safety_claims(line) == []
    assert line.endswith("That is not a finding that the water is safe now.")


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


# -- what a person should do after contact ---------------------------------


def test_human_exposure_and_medical_lines_say_what_the_sources_say() -> None:
    # Pinned to the CDC and California Water Boards wording they paraphrase:
    # rinse off with tap water, and a doctor or Poison Control if sick.
    assert "rinse off with tap water right away" in wording.HUMAN_ADVICE
    poison = "call a doctor or Poison Control at 1-800-222-1222"
    assert poison in wording.HUMAN_ADVICE
    assert wording.NOT_MEDICAL_ADVICE.startswith(site.SITE_NAME + " ")
    assert "It is not medical advice" in wording.NOT_MEDICAL_ADVICE
    assert "Poison Control at 1-800-222-1222" in wording.NOT_MEDICAL_ADVICE


@pytest.mark.parametrize("which", ["traps_site", "sample_site"])
def test_every_page_says_it_is_not_medical_advice(
    which: str, request: pytest.FixtureRequest
) -> None:
    root: Path = request.getfixturevalue(which)
    built = pages(root)
    assert built
    missing = [
        str(p.relative_to(root))
        for p in built
        if wording.NOT_MEDICAL_ADVICE not in text_of(p)
    ]
    assert missing == []


def test_people_get_after_contact_steps_where_dogs_do(traps_site: Path) -> None:
    water_pages = sorted((traps_site / "water").glob("*/index.html"))
    assert water_pages
    for page in water_pages:
        assert 'id="after-contact"' in page.read_text(encoding="utf-8"), page
        assert wording.HUMAN_ADVICE in text_of(page), page
    for path in ("dogs/index.html", "about/index.html"):
        assert wording.HUMAN_ADVICE in text_of(traps_site / path), path


def test_after_contact_check_is_not_vacuous(traps_site: Path) -> None:
    # Negative control: a page without the line fails the same check.
    page = traps_site / "water" / "ca-alameda-lake-alpha" / "index.html"
    stripped = page.read_text(encoding="utf-8").replace(
        html.escape(wording.HUMAN_ADVICE, quote=False), ""
    )
    assert stripped != page.read_text(encoding="utf-8")  # the sabotage applied
    stripped_text = html.unescape(re.sub(r"\s+", " ", _TAG.sub(" ", stripped)))
    assert wording.HUMAN_ADVICE not in stripped_text


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
            wording.summary("X", "Y County", s, "2026-09-01"),
            wording.summary("X", None, s, None),
        ):
            assert affirmative_safety_claims(line) == [], line
    for line in [
        *wording.LEVEL_GUIDANCE.values(),
        wording.DOG_ADVICE,
        wording.HUMAN_ADVICE,
        wording.NOT_MEDICAL_ADVICE,
    ]:
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


# Every other GA4 web stream in the portfolio's account (2026-10-31). Lake
# Notice's id must never be one of them, or its visits land in another
# product's reports.
OTHER_PRODUCTS_GA4_IDS = {
    "G-ZYL3RMXCZF",  # Trout Truck
    "G-L2JN3PQ75P",  # Family Greenhouse
    "G-45H8Q9H93F",  # GTFS Scorecard
    "G-YKGPZ76LVE",  # Next Home Game
    "G-6RWDSWTRR7",  # chelseakr.com
}


def test_default_build_carries_lake_notices_own_ga4_id(traps_site: Path) -> None:
    measurement_id = site.GA4_MEASUREMENT_ID
    assert re.fullmatch(r"G-[A-Z0-9]{10}", measurement_id)
    assert measurement_id not in OTHER_PRODUCTS_GA4_IDS
    for page in pages(traps_site):
        if page.suffix == ".html":
            assert f'var id = "{measurement_id}";' in page.read_text(), page
    privacy = text_of(traps_site / "privacy" / "index.html")
    assert "Google Analytics 4" in privacy
    assert "Last updated 2026-10-31" in privacy
    assert "Global Privacy Control" in privacy


def test_no_analytics_without_an_id_and_privacy_says_so(
    tmp_path: Path, traps_site: Path
) -> None:
    out = tmp_path / "no-ga"
    site.build_site(snapshot_of(traps_site), out, ga4_measurement_id="")
    for page in pages(out):
        assert "googletagmanager" not in page.read_text()
    privacy = text_of(out / "privacy" / "index.html")
    assert "no analytics" in privacy
    assert "Google Analytics" not in privacy


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


# -- search-result metadata: length and uniqueness -----------------------------

_TITLE = re.compile(r"<title>(.*?)</title>", re.S)
_DESCRIPTION = re.compile(r'<meta name="description" content="(.*?)"', re.S)


def meta_problems(root: Path) -> list[str]:
    """Pages whose title or description is cut off in search results (over
    60 and 155 characters), missing, or shared with another page."""
    problems = []
    seen: dict[str, str] = {}
    for page in pages(root):
        rel = str(page.relative_to(root))
        raw = page.read_text(encoding="utf-8")
        title, description = _TITLE.search(raw), _DESCRIPTION.search(raw)
        if not title or not description:
            problems.append(f"{rel}: missing title or description")
            continue
        t, d = html.unescape(title.group(1)), html.unescape(description.group(1))
        if len(t) > site.TITLE_MAX:
            problems.append(f"{rel}: title is {len(t)} characters: {t}")
        if len(d) > site.DESCRIPTION_MAX:
            problems.append(f"{rel}: description is {len(d)} characters: {d}")
        if t in seen:
            problems.append(f"{rel}: title shared with {seen[t]}: {t}")
        seen[t] = rel
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


def test_enough_records_make_a_stale_water_indexable() -> None:
    old = {"status": {"last_advisory": "2019-07-15"}}
    run = dt.date(2026, 11, 3)
    assert not site.is_indexable({**old, "records": [{}] * 4}, run, 24, 5)
    assert site.is_indexable({**old, "records": [{}] * 5}, run, 24, 5)
    # A water with no advisory ever is indexable on its records alone.
    never = {"status": {"last_advisory": None}, "records": [{}] * 5}
    assert site.is_indexable(never, run, 24, 5)
    assert not site.is_indexable({**never, "records": [{}] * 4}, run, 24, 5)
    # The default floor is the module constant, read at call time.
    assert site.INDEX_MIN_RECORDS == 5
    assert not site.is_indexable({**old, "records": [{}] * 4}, run, 24)


def test_record_floor_reaches_the_sitemap_and_robots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The fixtures' stale waters have one record each; a floor of 1 must list
    # them all, and the sitemap and robots tags must still agree.
    root = build(tmp_path)
    _, before = staging_problems_inputs(root)
    assert "ca-nevada-state-zeta-lake" in before
    monkeypatch.setattr(site, "INDEX_MIN_RECORDS", 1)
    root = build(tmp_path / "floor")
    keep, out = staging_problems_inputs(root)
    assert "ca-nevada-state-zeta-lake" in keep and out == []
    assert staging_problems(root) == []


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


@pytest.mark.parametrize("which", ["traps_site", "sample_site"])
def test_titles_and_descriptions_fit_search_results(
    which: str, request: pytest.FixtureRequest
) -> None:
    assert meta_problems(request.getfixturevalue(which)) == []


def test_meta_guard_catches_a_long_title_and_a_shared_title(tmp_path: Path) -> None:
    # Negative control: sabotage a built copy and assert the sabotage applied
    # before asserting the guard noticed it.
    root = build(tmp_path)
    first, second = pages(root)[:2]
    before = first.read_text(encoding="utf-8")
    first.write_text(
        _TITLE.sub("<title>" + "long " * 20 + "</title>", before, count=1),
        encoding="utf-8",
    )
    assert first.read_text(encoding="utf-8") != before  # sabotage applied
    other = second.read_text(encoding="utf-8")
    title = _TITLE.search(other)
    assert title
    second.write_text(
        _TITLE.sub("<title>Same</title>", other, count=1), encoding="utf-8"
    )
    third = pages(root)[2]
    third.write_text(
        _TITLE.sub("<title>Same</title>", third.read_text(encoding="utf-8"), count=1),
        encoding="utf-8",
    )
    problems = meta_problems(root)
    assert any("title is" in p for p in problems)
    assert any("title shared with" in p for p in problems)


def test_water_title_and_description_fit_for_any_name() -> None:
    long_name = (
        "Tributary to Some Extraordinarily Long Named Creek near the Old Mill " * 2
    )
    headline = wording.headline(
        {
            "kind": "advisory",
            "tier": "danger",
            "level": "Danger",
            "posted": "2026-10-16",
        }
    )
    for name in ["Clear Lake", long_name.strip()]:
        assert len(site.water_title(name, None)) <= site.TITLE_MAX
        assert len(site.water_title(name, "Alameda and Contra Costa")) <= site.TITLE_MAX
        assert len(site.water_description(name, "Alameda County", headline)) <= (
            site.DESCRIPTION_MAX
        )
    # The status and its date are never the part cut.
    assert headline in site.water_description("Clear Lake", "Lake County", headline)
    assert site.water_title("Bear Creek", "Mono").startswith("Bear Creek, Mono County")
    assert site.water_title("Clear Lake", None).startswith("Clear Lake toxic algae")


_TITLE_DATE = re.compile(r"[A-Z][a-z]{2} \d{1,2}, \d{4}")


def snippet_problems(root: Path) -> list[str]:
    """Water pages whose search title or description says more than the page
    (DECISIONS 0002 and 0018): a sentence that claims safety, a title date
    the page's first line does not carry, or a status that is not an
    advisory without its not-a-finding sentence."""
    problems = []
    for page in sorted((root / "water").glob("*/index.html")):
        rel = str(page.relative_to(root))
        raw = page.read_text(encoding="utf-8")
        title, description = _TITLE.search(raw), _DESCRIPTION.search(raw)
        assert title and description
        t, d = html.unescape(title.group(1)), html.unescape(description.group(1))
        lede = lede_of(page)
        for text in (t, d):
            problems += [f"{rel}: {s}" for s in affirmative_safety_claims(text)]
        for day in _TITLE_DATE.findall(t):
            if day not in lede:
                problems.append(f"{rel}: title date {day} is not in the first line")
        if wording.NOT_A_FINDING in lede and wording.NOT_A_FINDING not in d:
            problems.append(f"{rel}: description drops the not-a-finding sentence")
    return problems


@pytest.mark.parametrize("which", ["traps_site", "sample_site"])
def test_search_snippets_say_only_what_the_page_says(
    which: str, request: pytest.FixtureRequest
) -> None:
    assert snippet_problems(request.getfixturevalue(which)) == []


def test_advisory_titles_lead_with_the_level_and_its_date(traps_site: Path) -> None:
    water = traps_site / "water"

    def title(wid: str) -> str:
        found = _TITLE.search((water / wid / "index.html").read_text())
        assert found
        return html.unescape(found.group(1))

    assert title("ca-alameda-lake-alpha") == (
        "Lake Alpha algae: Caution advisory, last posted Sep 20, 2026"
    )
    assert title("ca-nevada-state-zeta-lake").endswith("Jul 15, 2019")
    # No status in the title unless it is an advisory: "recommends no
    # advisory" needs its not-a-finding sentence, which a title cannot hold.
    assert title("ca-lake-beta-reservoir").endswith("algae advisories | Lake Notice")
    assert title("ca-marin-theta-lake").endswith("algae advisories | Lake Notice")
    beta = _DESCRIPTION.search(
        (water / "ca-lake-beta-reservoir" / "index.html").read_text()
    )
    assert beta and wording.NOT_A_FINDING in html.unescape(beta.group(1))
    alpha = _DESCRIPTION.search(
        (water / "ca-alameda-lake-alpha" / "index.html").read_text()
    )
    assert alpha and html.unescape(alpha.group(1)).startswith(
        "Lake Alpha, Alameda County: Caution advisory, last posted Sep 20, 2026. "
        "No all-clear recorded. From the state's data dated Oct 9, 2026."
    )


def test_title_status_drops_last_posted_before_the_date() -> None:
    danger = {"kind": "advisory", "tier": "danger", "posted": "2026-10-19"}
    nov = {**danger, "posted": "2026-11-03"}
    assert site.water_title("Castaic Lake", None, nov) == (
        "Castaic Lake algae: Danger advisory, last posted Nov 3, 2026"
    )
    assert site.water_title("Castaic Lake", None, danger) == (
        "Castaic Lake algae: Danger advisory, Oct 19, 2026"
    )
    assert site.water_title("San Luis Reservoir", None, danger) == (
        "San Luis Reservoir algae: Danger advisory, Oct 19, 2026"
    )
    long_name = "Pierce City City Park Recreational Pond"
    assert site.water_title(long_name, None, danger) == f"{long_name} | Lake Notice"
    none = {"kind": "no_advisory_recorded", "lift_kind": "no_advisory_record",
            "lift_date": "2026-09-01"}  # fmt: skip
    assert wording.title_status(none) is None
    assert site.water_title("Mission Bay", None, none) == (
        "Mission Bay toxic algae advisories | Lake Notice"
    )
    line = site.water_description("Mission Bay", "San Diego County",
                                  wording.headline(none), "2026-11-03",
                                  advisory=False)  # fmt: skip
    assert line.endswith(wording.NOT_A_FINDING)
    assert len(line) <= site.DESCRIPTION_MAX


def test_snippet_check_catches_a_title_or_description_that_says_more(
    tmp_path: Path,
) -> None:
    # Negative control: each sabotage must be applied and must be reported.
    root = build(tmp_path)
    alpha = root / "water" / "ca-alameda-lake-alpha" / "index.html"
    beta = root / "water" / "ca-lake-beta-reservoir" / "index.html"
    raw = alpha.read_text(encoding="utf-8")
    changed = raw.replace(
        "last posted Sep 20, 2026</title>", "last posted Oct 1, 2026</title>"
    )
    assert changed != raw
    alpha.write_text(changed, encoding="utf-8")
    raw = beta.read_text(encoding="utf-8")
    changed = re.sub(r'(<meta name="description" content=")[^"]*"',
                     r'\1Beta Reservoir is safe to swim."', raw, count=1)  # fmt: skip
    assert changed != raw
    beta.write_text(changed, encoding="utf-8")
    problems = snippet_problems(root)
    assert any("title date Oct 1, 2026" in p for p in problems)
    assert any("safe to swim" in p for p in problems)
    assert any("drops the not-a-finding sentence" in p for p in problems)


def test_water_pages_that_share_a_name_get_different_titles() -> None:
    def w(i: str, county: str) -> dict[str, Any]:
        return {"state": "CA", "name": "Bear Creek", "id": i, "counties": [county]}

    waters = [w("ca-a-bear-creek", "Mono"), w("ca-b-bear-creek", "Inyo")]
    titles = {
        site.water_title(x["name"], site.SiteBuilder._county_label(x)) for x in waters
    }
    assert len(titles) == 2


# -- matching names nearby ---------------------------------------------------


def _water(
    wid: str, name: str, lat: float, lon: float, state: str = "CA"
) -> dict[str, Any]:
    return {"id": wid, "name": name, "state": state, "center": {"lat": lat, "lon": lon}}


def test_name_key_ignores_case_word_order_and_a_trailing_state() -> None:
    assert site.name_key("Big bear lake ca") == site.name_key("Big Bear Lake")
    assert site.name_key("Lake Crowley") == site.name_key("Crowley Lake")
    assert site.name_key("Bear Creek") != site.name_key("Bear Lake")
    assert site.name_key("Unnamed pond") == ()
    assert site.name_key("CA") == ()


def test_same_name_nearby_needs_a_match_a_center_and_distance() -> None:
    waters = [
        _water("a", "Big Bear Lake", 34.24, -116.91),
        _water("b", "Big bear lake ca", 34.243, -116.912),
        _water("far", "Big Bear Lake", 38.0, -120.0),
        _water("other-state", "Big Bear Lake", 34.24, -116.91, state="MO"),
        _water("unnamed-1", "Unnamed pond", 34.24, -116.91),
        _water("unnamed-2", "Unnamed pond", 34.24, -116.91),
        {"id": "nocenter", "name": "Big Bear Lake", "state": "CA", "center": None},
    ]
    nearby = site.same_name_nearby(waters)
    assert {k: [w["id"] for w in v] for k, v in nearby.items()} == {
        "a": ["b"],
        "b": ["a"],
    }
    assert site.miles_between(waters[0]["center"], waters[2]["center"]) > (
        site.SAME_NAME_NEARBY_MILES
    )


def test_water_page_links_matching_names_nearby_with_their_own_status(
    tmp_path: Path, traps_site: Path
) -> None:
    snap = snapshot_of(traps_site)
    original = next(w for w in snap["waterbodies"] if w["center"])
    twin = json.loads(json.dumps(original))
    twin["id"] = original["id"] + "-ca"
    twin["name"] = original["name"].lower() + " ca"
    snap["waterbodies"].append(twin)
    out = tmp_path / "twins"
    site.build_site(snap, out)
    page = text_of(out / "water" / original["id"] / "index.html")
    assert "Matching names nearby" in page
    assert "may be the same water" in page
    # The twin is listed by its display name, never the state's "... ca".
    assert water_names.display_name(twin["id"], twin["name"], "CA") in page
    assert twin["name"] not in page
    assert wording.headline(twin["status"]) in page
    raw = (out / "water" / original["id"] / "index.html").read_text()
    assert f'href="../../water/{twin["id"]}/"' in raw
    lone = next(
        w for w in snap["waterbodies"]
        if site.name_key(w["name"]) != site.name_key(original["name"])
    )  # fmt: skip
    assert "Matching names nearby" not in text_of(
        out / "water" / lone["id"] / "index.html"
    )


_COUNT = re.compile(r"(\d+) of (?:the )?(\d+) waters?\b")


def expected_county_counts(snap: dict[str, Any]) -> dict[str, tuple[int, int]]:
    """Per county, from the snapshot: waters with an advisory, all waters."""
    expected: dict[str, tuple[int, int]] = {}
    for w in snap["waterbodies"]:
        for county in w["counties"]:
            adv, total = expected.get(county, (0, 0))
            expected[county] = (adv + (w["status"]["kind"] == "advisory"), total + 1)
    return expected


def _says_count(text: str, adv: int, total: int) -> bool:
    if total == 1:
        return "The one water in" in text and "has an advisory as its" in text
    found = _COUNT.search(text)
    return found is not None and found.groups() == (str(adv), str(total))


def _one_county_problems(
    page: Path, county: str, adv: int, total: int, file_label: str
) -> list[str]:
    raw = page.read_text(encoding="utf-8")
    title, description = _TITLE.search(raw), _DESCRIPTION.search(raw)
    assert title and description
    t, d = html.unescape(title.group(1)), html.unescape(description.group(1))
    lede = lede_of(page)
    texts = {"title": t, "description": d, "lede": lede}
    problems = [
        f"{county}: {s}" for text in texts.values()
        for s in affirmative_safety_claims(text)
    ]  # fmt: skip
    if adv == 0:
        return problems + [
            f"{county}: {where} states a count with none"
            for where, text in texts.items() if _COUNT.search(text)
        ]  # fmt: skip
    found = _COUNT.search(t)
    if not found or found.groups() != (str(adv), str(total)):
        problems.append(f"{county}: title count is not {adv} of {total}")
    problems += [
        f"{county}: {where} count is not {adv} of {total}"
        for where in ("lede", "description")
        if not _says_count(texts[where], adv, total)
    ]
    if file_label not in d:
        problems.append(f"{county}: description lacks the state's file date")
    return problems


def county_snippet_problems(root: Path) -> list[str]:
    """County pages whose title, description or first line disagree with the
    snapshot about how many waters have an advisory as their latest record,
    or that state a count for a county with none (DECISIONS 0002: a bare
    "0 of 2" would read as an all-clear)."""
    snap = snapshot_of(root)
    file_date = next(
        f["file_date"] for f in snap["source_files"] if f["source"] == "ca-swrcb-fhab"
    )
    problems = []
    for county, (adv, total) in sorted(expected_county_counts(snap).items()):
        page = root / "county" / site.slugify(county) / "index.html"
        problems += _one_county_problems(
            page, county, adv, total, wording.date_label(file_date)
        )
    return problems


@pytest.mark.parametrize("which", ["traps_site", "sample_site"])
def test_county_snippets_count_what_the_snapshot_holds(
    which: str, request: pytest.FixtureRequest
) -> None:
    root: Path = request.getfixturevalue(which)
    assert county_snippet_problems(root) == []


def test_county_fixtures_cover_both_sides(traps_site: Path) -> None:
    kinds: dict[str, set[bool]] = {}
    for w in snapshot_of(traps_site)["waterbodies"]:
        for county in w["counties"]:
            kinds.setdefault(county, set()).add(w["status"]["kind"] == "advisory")
    assert any(True in k for k in kinds.values())
    assert any(k == {False} for k in kinds.values())


def test_county_snippet_check_catches_a_wrong_count(tmp_path: Path) -> None:
    # Negative control: each sabotage must apply and must be reported.
    root = build(tmp_path)
    snap = snapshot_of(root)
    counted = {c for w in snap["waterbodies"] if w["status"]["kind"] == "advisory"
               for c in w["counties"]}  # fmt: skip
    every = {c for w in snap["waterbodies"] for c in w["counties"]}
    with_one, without = sorted(counted)[0], sorted(every - counted)[0]
    page = root / "county" / site.slugify(with_one) / "index.html"
    raw = page.read_text(encoding="utf-8")
    changed = _TITLE.sub(
        lambda m: _COUNT.sub("99 of 99 waters", m.group(0)), raw, count=1
    )
    assert changed != raw
    page.write_text(changed, encoding="utf-8")
    page = root / "county" / site.slugify(without) / "index.html"
    raw = page.read_text(encoding="utf-8")
    changed = _TITLE.sub(f"<title>{without} County algae: 0 of 2 waters</title>", raw)
    assert changed != raw
    page.write_text(changed, encoding="utf-8")
    problems = county_snippet_problems(root)
    assert f"{with_one}: title count is not" in " ".join(problems)
    assert f"{without}: title states a count with none" in problems


def test_county_title_and_description_fit_and_never_count_zero() -> None:
    long = "Extraordinarily Long Named Imaginary"
    for county, adv, total in [("Riverside", 25, 40), ("San Luis Obispo", 9, 12),
                               ("Amador", 1, 1), (long, 3, 120), ("Glenn", 0, 2)]:  # fmt: skip
        title = site.county_title(county, adv, total)
        line = site.county_description(county, adv, total, "2026-11-03")
        assert len(title) <= site.TITLE_MAX, title
        assert len(line) <= site.DESCRIPTION_MAX, line
    assert site.county_title("Riverside", 25, 40) == (
        "Riverside County lake algae advisories: 25 of 40 waters"
    )
    assert site.county_title("Amador", 1, 1).endswith("1 of 1 water")
    assert site.county_title("Glenn", 0, 2) == (
        "Glenn County lake toxic algae advisories | Lake Notice"
    )
    assert site.county_count_line("Glenn", 0, 2, "2026-11-03") == ""
    assert "0 of" not in site.county_description("Glenn", 0, 2, "2026-11-03")
    assert "dated" not in site.county_count_line("Riverside", 25, 40, None)
    assert site.county_count_line("Colusa", 1, 3, None) == (
        "1 of the 3 waters in Colusa County has an advisory as its latest state record."
    )


def test_advisory_list_description_counts_each_state_it_lists(
    traps_site: Path, tmp_path: Path
) -> None:
    raw = (traps_site / "advisories" / "index.html").read_text(encoding="utf-8")
    description = _DESCRIPTION.search(raw)
    assert description
    d = html.unescape(description.group(1))
    links = re.findall(r'href="\.\./water/([a-z]{2})-', raw)
    for state, name in site.STATE_NAMES.items():
        n = links.count(state.lower())
        if n:
            assert f"{n} {name}" in d, (state, d)
        else:
            assert name not in d.split(" lakes")[0], (state, d)
    assert site.advisories_description([]).startswith("Lakes and rivers")
    many = [{"state": "CA"}] * 479 + [{"state": "MO"}] * 47
    line = site.advisories_description(many)
    assert line.startswith("479 California and 47 Missouri lakes and rivers")
    assert len(line) <= site.DESCRIPTION_MAX
