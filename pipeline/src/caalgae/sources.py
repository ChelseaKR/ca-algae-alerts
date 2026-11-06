"""The data sources this pipeline may read.

Multi-state from day one (docs/DECISIONS.md 0003, 0010). Every normalized
record names its source; the snapshot carries each source's license,
attribution, required disclaimer and how that source records the end of an
advisory. A source is added only after its terms are quoted verbatim in
docs/LICENSES-AND-ATTRIBUTION.md ("unknown = not used", decision 0004) and
its host's robots.txt has been read (decision 0011).

Two record kinds, never mixed:

- ``official_advisory``: a state agency's advisory record. Only these decide
  a waterbody's status.
- ``satellite_estimate``: EPA CyAN's satellite-derived cyanobacteria
  abundance. Shown in its own labeled section; never an advisory, never an
  end of one, never "safe".

How each source records the end of an advisory (``lift_semantics``):

- ``explicit_record``: a later record says no advisory (California's "None").
- ``explicit_field``: a dated field on the record (Missouri's dissipation date).
- ``rolling_window``: listings expire after a fixed time. Expiry is never
  read as an end. (No source of this kind is enabled.)
- ``none_recorded``: the source records no ends at all (satellite estimates).
"""

from __future__ import annotations

import dataclasses

OFFICIAL_ADVISORY = "official_advisory"
SATELLITE_ESTIMATE = "satellite_estimate"
LIFT_SEMANTICS = (
    "explicit_record",
    "explicit_field",
    "rolling_window",
    "none_recorded",
)


@dataclasses.dataclass(frozen=True)
class Source:
    """One data source, as the snapshot describes it."""

    id: str
    state: str
    agency: str
    program: str
    dataset_url: str
    official_map_url: str
    license: str
    rights: str
    license_read_on: str
    attribution: str
    contact: str
    record_kind: str = OFFICIAL_ADVISORY
    lift_semantics: str = "explicit_record"
    lift_explanation: str = ""
    # Shown verbatim wherever this source's data is shown, when non-empty.
    required_disclaimer: str = ""
    # The publisher may withdraw permission; see docs/LICENSES-AND-ATTRIBUTION.md.
    revocable: bool = False
    revocation_clause: str = ""
    # The publisher's own caveat on how to use its data, verbatim, with the
    # page it comes from. Shown beside the data when non-empty.
    publisher_caveat: str = ""
    publisher_caveat_url: str = ""
    # A switch per source, so a revoked or changed source is turned off in
    # one place without touching its history.
    enabled: bool = True
    # The agency's own map of current reports, linked when this source's data
    # is unavailable (DECISIONS 0024). Empty: ``official_map_url``.
    reports_map_url: str = ""

    def as_json(self) -> dict[str, object]:
        out = dataclasses.asdict(self)
        out.pop("enabled")
        out.pop("reports_map_url")
        return out

    @property
    def current_map_url(self) -> str:
        return self.reports_map_url or self.official_map_url


CA_SWRCB_FHAB = Source(
    id="ca-swrcb-fhab",
    state="CA",
    agency="California State Water Resources Control Board",
    program="Freshwater and Estuarine Harmful Algal Bloom (FHAB) Program",
    dataset_url="https://data.ca.gov/dataset/surface-water-freshwater-harmful-algal-blooms",
    official_map_url="https://mywaterquality.ca.gov/habs/",
    # Verbatim from the dataset page, read 2026-10-12 (License and Rights rows).
    license="Other (Public Domain)",
    rights="No Restrictions on Public Use",
    license_read_on="2026-10-12",
    attribution=(
        "Advisory data: California State Water Resources Control Board, "
        "Freshwater Harmful Algal Bloom Program, via data.ca.gov "
        "(public domain). Advisories are recommendations; reporting is "
        "voluntary and incomplete."
    ),
    contact="CyanoHAB.Reports@waterboards.ca.gov",
    lift_semantics="explicit_record",
    lift_explanation=(
        'An advisory ends only when the state records a later "None" '
        "(no advisory recommended) at the same spot, or an end date. A blank "
        "end date is unknown."
    ),
)

# Verbatim from https://mo.gov/data-policy, read 2026-10-12 ("Source Data").
MO_REQUIRED_DISCLAIMER = (
    "The data made available here has been modified for use from its original "
    "source, which is the State of Missouri. THE STATE OF MISSOURI MAKES NO "
    "REPRESENTATIONS OR WARRANTY AS TO THE COMPLETENESS, ACCURACY, TIMELINESS, "
    "OR CONTENT OF ANY DATA MADE AVAILABLE THROUGH THIS SITE. THE STATE OF "
    "MISSOURI EXPRESSLY DISCLAIMS ALL WARRANTIES, WHETHER EXPRESS OR IMPLIED, "
    "INCLUDING ANY IMPLIED WARRANTIES OF MERCHANTABILITY, OR FITNESS FOR A "
    "PARTICULAR PURPOSE. The data is subject to change as modifications and "
    "updates are complete. It is understood that the information contained in "
    "the Web feed is being used at one\u2019s own risk."
)
# Verbatim, same page ("Right to Modify and/or Discontinue Feeds").
MO_REVOCATION_CLAUSE = (
    "The State of Missouri reserves the right to modify and/or discontinue "
    "providing any or all of the data feeds at any time and to require the "
    "termination of any and all displaying, distributing or otherwise using any "
    "or all of the data for any reason including, without limitation, your "
    "violation of any provision of these Terms of Use."
)

# Verbatim from the department's HAB Reports Map page, read 2026-10-30
# ("Disclaimer"; the paragraph's first two sentences).
MO_MAP_CAVEAT_URL = (
    "https://dnr.mo.gov/water/alerts-hazards/harmful-algal-bloom-hab-reports-map"
)
MO_MAP_CAVEAT = (
    "The data presented in the map should be used for general purposes only. "
    "The exact location, extent and toxicity of the reported bloom may not be "
    "accurate due to changing environmental conditions."
)

MO_DNR_HAB = Source(
    id="mo-dnr-hab",
    state="MO",
    agency="Missouri Department of Natural Resources",
    program="Harmful Algal Bloom Response (public water bodies)",
    dataset_url=(
        "https://gis.dnr.mo.gov/host/rest/services/wqm/HAB_SUBMIT_POINTS/MapServer/6"
    ),
    official_map_url=(
        "https://dnr.mo.gov/water/hows-water/pollutants-sources/harmful-algal-blooms-habs"
    ),
    license="State of Missouri Data Policy (https://mo.gov/data-policy)",
    rights="Use permitted with the required disclaimer; revocable by the State",
    license_read_on="2026-10-12",
    attribution=(
        "Missouri data: Missouri Department of Natural Resources, Harmful Algal "
        "Bloom response map. Status codes are the department's; their plain-English "
        "labels here are this site's reading of the codes."
    ),
    contact="Missouri Department of Natural Resources",
    lift_semantics="explicit_field",
    lift_explanation=(
        "An advisory ends only when the department records a dissipation date. "
        "A closed case without one is not read as an end."
    ),
    required_disclaimer=MO_REQUIRED_DISCLAIMER,
    revocable=True,
    revocation_clause=MO_REVOCATION_CLAUSE,
    publisher_caveat=MO_MAP_CAVEAT,
    publisher_caveat_url=MO_MAP_CAVEAT_URL,
    reports_map_url=MO_MAP_CAVEAT_URL,
)

EPA_CYAN = Source(
    id="epa-cyan",
    state="US",
    agency="U.S. Environmental Protection Agency",
    program="Cyanobacteria Assessment Network (CyAN), Sentinel-3 OLCI weekly composite",
    dataset_url="https://www.epa.gov/water-research/cyanobacteria-assessment-network-cyan",
    official_map_url="https://qed.epa.gov/cyanweb/",
    license="U.S. Government work (public domain under 17 U.S.C. § 105); no license is stated on the CyANWeb API",
    rights="EPA calls CyANWeb experimental and provisional, a research-level tool",
    license_read_on="2026-10-12",
    attribution=(
        "Satellite estimates: U.S. EPA Cyanobacteria Assessment Network (CyAN), "
        "from Copernicus Sentinel-3 data. Provisional, research-level estimates; "
        "EPA does not endorse this site."
    ),
    contact="U.S. EPA Office of Research and Development",
    record_kind=SATELLITE_ESTIMATE,
    lift_semantics="none_recorded",
    lift_explanation=(
        "A satellite estimate is never an advisory and never ends one. It measures "
        "how much cyanobacteria there is, not toxins."
    ),
)

SOURCES: dict[str, Source] = {s.id: s for s in (CA_SWRCB_FHAB, MO_DNR_HAB, EPA_CYAN)}


def enabled_sources() -> list[Source]:
    return [s for s in SOURCES.values() if s.enabled]
