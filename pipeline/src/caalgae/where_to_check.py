"""The "Where to check an algae advisory" page: a dated snapshot of the pages
people use, and what each covers and does not.

Every row states a fact the 2026-10-23 research read on the page itself
(growth/lake-notice-buyer-research-2026-10-23.md and the fetch log it
carries). A row has a link, the date it was read, what it covers and what it
does not. Nothing here says that any source is wrong, and nothing implies that
an agency reviewed or approved this page.

The page's own data date is the newest read date below (``AS_OF``). The
sitemap's lastmod for the page is that date: never the clock, never the build.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

TITLE = "Where to check a California algae advisory"
DESCRIPTION = (
    "A dated list of where Californians check toxic algae advisories: state, "
    "county, park district and lake sources, and what each does and does not cover."
)


@dataclass(frozen=True)
class Source:
    name: str
    url: str  # "" means this site's home page
    read_on: dt.date
    covers: str
    does_not_cover: str
    also_label: str = ""
    also_url: str = ""
    # Lake Notice water ids this source is specific to, so that water's page
    # can point to it ("Swimming at <water>", DECISIONS 0033). Only a source
    # that names one water gets ids; a district-wide or national page does not.
    waters: tuple[str, ...] = ()


READ = dt.date(2026, 10, 23)

SOURCES: tuple[Source, ...] = (
    Source(
        name="Water Boards: freshwater harmful algal bloom (FHAB) program page",
        url="https://www.waterboards.ca.gov/water_issues/programs/swamp/freshwater_cyanobacteria.html",
        read_on=READ,
        covers=(
            "The state program behind the advisory records. The page lists "
            "recent advisories and notifications (for 2026 it named nine "
            "events, the latest dated Oct 2), a report form, a web map and "
            "the full data file."
        ),
        does_not_cover=(
            "The page read had no page for each water, no alerts and no dog "
            "guidance. The web map's site allows only Google's crawler in its "
            "robots.txt, so we did not read the map and say "
            "nothing here about what it shows."
        ),
        also_label="The web map the program page points to",
        also_url="https://mywaterquality.ca.gov/habs/",
    ),
    Source(
        name="Water Boards advisory records on data.ca.gov",
        url="https://data.ca.gov/dataset/surface-water-freshwater-harmful-algal-blooms",
        read_on=READ,
        covers=(
            "The state's advisory records as one data file, listed as public "
            "domain with no restrictions on public use and shown as last "
            "updated Oct 23, 2026. This is the file Lake Notice republishes."
        ),
        does_not_cover=(
            "A data file, not a lookup page for one lake. Reports are "
            "voluntary and many waters are never tested, so a water missing "
            "from the file is not a finding about the water."
        ),
    ),
    Source(
        name="Sacramento County environmental health: recreational health program",
        url="https://emd.saccounty.gov/us/en/environmental-health/rec-health-program.html",
        read_on=READ,
        covers="Recreational health program pages that list pools and lake inspections.",
        does_not_cover=(
            "We found no algae advisory content on the page read, and did not "
            "crawl the rest of the site."
        ),
    ),
    Source(
        name="San Bernardino County Environmental Health: recreation and aquatic facilities",
        url="https://ehs.sbcounty.gov/programs/recreation-and-aquatic-facilities/",
        read_on=READ,
        covers="Recreational health program pages that list pools and lake inspections.",
        does_not_cover=(
            "We found no algae advisory page on the pages read, and did not "
            "crawl the rest of the site."
        ),
    ),
    Source(
        name="East Bay Regional Park District: water quality",
        url="https://www.ebparks.org/natural-resources/water-quality",
        read_on=READ,
        covers=(
            "A table of alert levels for East Bay regional park swim areas "
            "(Danger, Caution, or No Advisory Posted), with a dog warning on "
            "the district's blue-green algae page. On Oct 23, 2026 it listed "
            "the Del Valle East swim beach at Caution and Lake Temescal at "
            "Danger."
        ),
        does_not_cover=(
            "Only the district's own parks, shown as one current table. The "
            "pages read showed no history, no page for each water and no "
            "alert sign-up. A table that lists a swim area and a state record "
            "that covers a whole lake can show different levels on one day."
        ),
        also_label="The district's blue-green algae page",
        also_url="https://www.ebparks.org/natural-resources/water-quality/blue-green-algae",
    ),
    Source(
        name="Big Valley Band of Pomo: Clear Lake cyanotoxin program",
        url="https://www.bvrancheria.com/clearlakecyanotoxins",
        read_on=READ,
        covers=(
            "The tribe's own sampling at Clear Lake: its page says samples "
            "are taken every two weeks in summer, lists current monitoring "
            "results and historical cyanotoxin data, and says the program "
            "began in 2014 with the Elem Indian Colony."
        ),
        does_not_cover=(
            "Clear Lake only. These are toxin samples, a different kind of "
            "record from the state's advisory records, and we did not read "
            "the results themselves."
        ),
        waters=("ca-clear-lake", "ca-lake-clear-lake"),
    ),
    Source(
        name="Lake Elsinore and San Jacinto Watersheds Authority: lake conditions",
        url="https://mywatersheds.com/about-us/about-lake-elsinore/lake-elsinore-conditions/",
        read_on=READ,
        covers=(
            "Lake Elsinore. The page says lake conditions are available at "
            "Elsinore Valley MWD."
        ),
        does_not_cover=(
            "We could not read Elsinore Valley MWD's site on Oct 23, 2026, so "
            "we say nothing about what it shows."
        ),
        waters=("ca-riverside-lake-elsinore",),
    ),
    Source(
        name="U.S. EPA: harmful algal bloom advisories",
        url="https://www.epa.gov/habs/hab-advisories",
        read_on=READ,
        covers=(
            "A national page. EPA says it compiles and displays recreational "
            "and drinking HAB occurrence and/or advisory data publicly "
            "reported by states, on a monthly basis."
        ),
        does_not_cover=(
            "The page read is a national summary updated monthly, with no "
            "page for each lake."
        ),
    ),
    Source(
        name="Swim Guide: California beaches",
        url="https://www.theswimguide.org/beaches/california",
        read_on=READ,
        covers=(
            "Free water quality information for more than 10,000 beaches, "
            "lakes, rivers and swimming holes, with status icons and "
            "historical status. California affiliates include Los Angeles "
            "Waterkeeper and San Diego Coastkeeper."
        ),
        does_not_cover=(
            "The pages read describe bacteria as the main indicator of beach "
            "water quality and did not describe an algae advisory. Grey means "
            "data more than a year old. The California page is mostly coast."
        ),
    ),
    Source(
        name="Lake Notice",
        url="",
        read_on=READ,
        covers=(
            "The state's advisory records, one page for each water: the "
            "latest status, the date it was posted, whether the state "
            "recorded an end, each reported spot and every record on file "
            "since 2016. It adds nothing the state did not record."
        ),
        does_not_cover=(
            "Lake Notice is not the source of any record and takes no water "
            "samples. It reads the state's file about once a day, so it can "
            "trail the state by about a day. It lists only waters in the "
            "state's data, and a water not listed may still have an advisory: "
            "check the state's map and posted signs. Most waters are never "
            "tested. The website sends "
            "no alerts. It is independent and is not affiliated with or "
            "reviewed by any agency."
        ),
    ),
)

# Counties the research could not read on 2026-10-23 (the three other counties
# with the most listed waters). The page says so and says nothing else.
UNREAD_COUNTIES = ("San Diego", "Riverside", "Contra Costa")

AS_OF = max(s.read_on for s in SOURCES)

# Waters listed per county in Lake Notice's county index, read 2026-10-23.
COUNTY_COUNTS: tuple[tuple[str, int], ...] = (
    ("San Diego", 67),
    ("Riverside", 40),
    ("Sacramento", 39),
    ("San Bernardino", 36),
    ("Contra Costa", 32),
)


def sources_for(water_id: str) -> list[Source]:
    """The where-to-check sources specific to one water, in page order."""
    return [src for src in SOURCES if water_id in src.waters]
