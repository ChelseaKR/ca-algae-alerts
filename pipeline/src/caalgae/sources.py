"""The data sources this pipeline may read, one entry per state program.

Multi-state from day one (docs/DECISIONS.md 0003): every normalized record
names the source it came from, and the snapshot carries each source's
license and attribution, so a second state is a new entry here plus its own
reader, not a change to the record shape. Only California is defined. A
state is added only after its terms are quoted verbatim in
docs/LICENSES-AND-ATTRIBUTION.md ("unknown = not used", decision 0004).
"""

from __future__ import annotations

import dataclasses


@dataclasses.dataclass(frozen=True)
class Source:
    """One state's advisory program, as the snapshot describes it."""

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

    def as_json(self) -> dict[str, str]:
        return dataclasses.asdict(self)


CA_SWRCB_FHAB = Source(
    id="ca-swrcb-fhab",
    state="CA",
    agency="California State Water Resources Control Board",
    program="Freshwater and Estuarine Harmful Algal Bloom (FHAB) Program",
    dataset_url=(
        "https://data.ca.gov/dataset/surface-water-freshwater-harmful-algal-blooms"
    ),
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
)

SOURCES: dict[str, Source] = {CA_SWRCB_FHAB.id: CA_SWRCB_FHAB}
