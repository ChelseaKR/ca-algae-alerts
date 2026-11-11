"""/llms.txt in the format llmstxt.org specifies: an H1 with the site's name,
a blockquote summary, plain text, then H2 sections that are lists of
``[name](url): note`` links. The same pattern as Trout Truck's and Next Home
Game's files.

Every state, source and date here comes from the snapshot the build is
reading; nothing is listed from memory. The wording follows wording.py: a
water is never called safe, and no advisory is never an all-clear.
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from caalgae.site import SiteBuilder

SPEC_URL = "https://llmstxt.org/"


def _join(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return f"{', '.join(items[:-1])}, and {items[-1]}"


def _file_dates(builder: SiteBuilder) -> list[str]:
    """One line per live state: the date of the state file this build read.
    A state without a file date says so in words, never with a stand-in."""
    out = []
    for state in builder.live_states:
        name = builder.common["state_names"][state]
        day = builder._file_date(state)
        if state in builder.unavailable:
            since = builder.unavailable[state]["since"]
            out.append(
                f"- {name}: the state's data has been unavailable to this site since {since}; "
                "pages show the last records it read and say so."
            )
        elif day:
            out.append(f"- {name}: the state file this build read is dated {day}.")
        else:
            out.append(f"- {name}: the state file's date is not known to this build.")
    return out


def render(builder: SiteBuilder) -> str:
    from caalgae.site import SITE_NAME

    base = builder.base_url.rstrip("/")
    names = [builder.common["state_names"][s] for s in builder.live_states]
    sources: list[dict[str, Any]] = [
        s for s in builder.snap["sources"] if s["record_kind"] == "official_advisory"
    ]
    estimates: list[dict[str, Any]] = [
        s for s in builder.snap["sources"] if s["record_kind"] != "official_advisory"
    ]
    run_date: dt.date = builder.run_date
    app = builder.common["app_store_url"]
    what = "website and iPhone app" if app else "website"
    lines = [
        f"# {SITE_NAME}",
        "",
        f"> {SITE_NAME} is a free {what} that mirrors state "
        f"harmful algal bloom (toxic algae) advisories for lakes and rivers in "
        f"{_join(names)}, one page per water, with every advisory the state has "
        "recorded there. It shows what a state agency published and when; it is "
        "never a determination that a water is safe. It is independent and not "
        "affiliated with any agency.",
        "",
        "What an advisory level means: California posts three levels at the water. "
        "Caution means algae that can make toxins may be present: keep people, "
        "children and pets away from algae and scum. Warning adds no swimming. "
        "Danger means stay out of the water. No level makes the water fit to drink. "
        "Other states' advisories (such as Missouri's) have no levels, and the site "
        "does not invent any. The sign posted at the water and the state's own "
        "notice always govern.",
        "",
        'Never an all-clear: an advisory reads "last posted <date>, no all-clear '
        'recorded" until the state records an explicit end. A water with no '
        "advisory on file is not a water the state has checked and found safe: "
        "reporting is voluntary and incomplete. The most the data supports is "
        '"the state\'s latest record recommended no advisory", with its date. '
        "Satellite estimates of cyanobacteria are shown in their own labeled "
        'section and are never an advisory, never the end of one, and never "safe".',
        "",
        f"Update cadence: the site is rebuilt once a day (14:41 UTC). This build's "
        f"data date is {run_date.isoformat()}. Every status on the site is shown with "
        "its date.",
        *_file_dates(builder),
        "",
        f"How to cite: credit the state agency as the source and name this site, "
        f'with the date shown on the page. Example: "{SITE_NAME} ({base}/), '
        "mirroring the state's advisory records as of <date>; check the sign at the "
        "water and the state's own map before you go.\"",
        "",
        f"This file follows the llms.txt format described at {SPEC_URL}.",
        "",
        "## Pages",
        "",
        f"- [Home]({base}/): what the site is, and the states it covers",
        f"- [Open advisories]({base}/advisories/): every water whose latest state record is an advisory, with the date it was posted",
        f"- Water pages: {base}/water/<id>/, one per water, with its latest status, its sampling spots and every record since 2016",
        f"- [Counties]({base}/county/): California counties, one page each under /county/<name>/",
    ]
    for state in builder.live_states:
        name = builder.common["state_names"][state]
        lines.append(
            f"- [{name}]({base}/state/{state.lower()}/): every {name} water with a page"
        )
    if builder.ny is not None:
        lines.append(
            f"- [New York bloom history]({base}/state/ny/): yearly bloom history only, "
            "not current advisories"
        )
    lines += [
        f"- [Dogs and algae]({base}/dogs/): how to read an advisory before a trip with a dog",
        f"- [Where to check]({base}/where-to-check/): the agencies' own maps and notices",
        f"- [About the data and its limits]({base}/about/): sources, licenses and what the data cannot tell you",
        *([f"- [iPhone app]({app}): favorites, alerts and a widget"] if app else []),
        f"- [Sitemap]({base}/sitemap.xml)",
        "",
        "## Sources",
        "",
    ]
    for s in sources:
        lines.append(
            f"- [{s['agency']}]({s['dataset_url']}): {s['program']}; license: "
            f"{s['license']}; the agency's map: {s['official_map_url']}"
        )
    for s in estimates:
        lines.append(
            f"- [{s['agency']}]({s['dataset_url']}): {s['program']}, satellite "
            f"estimates only, never an advisory; license: {s['license']}"
        )
    if builder.ny is not None:
        lines.append(f"- {builder.common['ny_attribution']}")
    lines += [
        f"- [Snapshot (JSON)]({base}/snapshot/v1.json): every record this build used, "
        "with each source's license and attribution",
        "",
    ]
    return "\n".join(lines)
