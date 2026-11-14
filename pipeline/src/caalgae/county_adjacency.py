"""Which California counties share a border, for "Also listed under
<county>" on water pages (DECISIONS 0034).

From the U.S. Census Bureau's county adjacency file, 2024 edition:
https://www2.census.gov/geo/docs/reference/county_adjacency/county_adjacency2024.txt
Downloaded 2026-11-05 (SHA-256 912ca408163016864fe64aaf667b53ad03a19ce4acbc586d3ac508395bdac980;
www2.census.gov's robots.txt has no rule for general crawlers). A work of the
U.S. government, so in the public domain (17 U.S.C. 105). Only the rows
where both counties are in California are kept, each pair once, with
"County, CA" dropped so the names match ``normalize.CA_COUNTIES``. The
Census file counts counties that meet across water (Alameda and San
Francisco, across the Bay) as neighbors; so does this table.

County lines change rarely; tests/test_split_county_links.py checks that
every county is here and every pair is symmetric and real.
"""

from __future__ import annotations

from collections import defaultdict

CA_ADJACENT_PAIRS: tuple[tuple[str, str], ...] = (
    ("Alameda", "Contra Costa"),
    ("Alameda", "San Francisco"),
    ("Alameda", "San Joaquin"),
    ("Alameda", "San Mateo"),
    ("Alameda", "Santa Clara"),
    ("Alameda", "Stanislaus"),
    ("Alpine", "Amador"),
    ("Alpine", "Calaveras"),
    ("Alpine", "El Dorado"),
    ("Alpine", "Mono"),
    ("Alpine", "Tuolumne"),
    ("Amador", "Calaveras"),
    ("Amador", "El Dorado"),
    ("Amador", "Sacramento"),
    ("Amador", "San Joaquin"),
    ("Butte", "Colusa"),
    ("Butte", "Glenn"),
    ("Butte", "Plumas"),
    ("Butte", "Sutter"),
    ("Butte", "Tehama"),
    ("Butte", "Yuba"),
    ("Calaveras", "San Joaquin"),
    ("Calaveras", "Stanislaus"),
    ("Calaveras", "Tuolumne"),
    ("Colusa", "Glenn"),
    ("Colusa", "Lake"),
    ("Colusa", "Sutter"),
    ("Colusa", "Yolo"),
    ("Contra Costa", "Marin"),
    ("Contra Costa", "Sacramento"),
    ("Contra Costa", "San Francisco"),
    ("Contra Costa", "San Joaquin"),
    ("Contra Costa", "Solano"),
    ("Contra Costa", "Sonoma"),
    ("Del Norte", "Humboldt"),
    ("Del Norte", "Siskiyou"),
    ("El Dorado", "Placer"),
    ("El Dorado", "Sacramento"),
    ("Fresno", "Inyo"),
    ("Fresno", "Kings"),
    ("Fresno", "Madera"),
    ("Fresno", "Merced"),
    ("Fresno", "Mono"),
    ("Fresno", "Monterey"),
    ("Fresno", "San Benito"),
    ("Fresno", "Tulare"),
    ("Glenn", "Lake"),
    ("Glenn", "Mendocino"),
    ("Glenn", "Tehama"),
    ("Humboldt", "Mendocino"),
    ("Humboldt", "Siskiyou"),
    ("Humboldt", "Trinity"),
    ("Imperial", "Riverside"),
    ("Imperial", "San Diego"),
    ("Inyo", "Kern"),
    ("Inyo", "Mono"),
    ("Inyo", "San Bernardino"),
    ("Inyo", "Tulare"),
    ("Kern", "Kings"),
    ("Kern", "Los Angeles"),
    ("Kern", "San Bernardino"),
    ("Kern", "San Luis Obispo"),
    ("Kern", "Santa Barbara"),
    ("Kern", "Tulare"),
    ("Kern", "Ventura"),
    ("Kings", "Monterey"),
    ("Kings", "San Luis Obispo"),
    ("Kings", "Tulare"),
    ("Lake", "Mendocino"),
    ("Lake", "Napa"),
    ("Lake", "Sonoma"),
    ("Lake", "Yolo"),
    ("Lassen", "Modoc"),
    ("Lassen", "Plumas"),
    ("Lassen", "Shasta"),
    ("Lassen", "Sierra"),
    ("Los Angeles", "Orange"),
    ("Los Angeles", "San Bernardino"),
    ("Los Angeles", "Ventura"),
    ("Madera", "Mariposa"),
    ("Madera", "Merced"),
    ("Madera", "Mono"),
    ("Madera", "Tuolumne"),
    ("Marin", "San Francisco"),
    ("Marin", "Solano"),
    ("Marin", "Sonoma"),
    ("Mariposa", "Merced"),
    ("Mariposa", "Stanislaus"),
    ("Mariposa", "Tuolumne"),
    ("Mendocino", "Sonoma"),
    ("Mendocino", "Tehama"),
    ("Mendocino", "Trinity"),
    ("Merced", "San Benito"),
    ("Merced", "Santa Clara"),
    ("Merced", "Stanislaus"),
    ("Modoc", "Shasta"),
    ("Modoc", "Siskiyou"),
    ("Mono", "Tuolumne"),
    ("Monterey", "San Benito"),
    ("Monterey", "San Luis Obispo"),
    ("Monterey", "Santa Cruz"),
    ("Napa", "Solano"),
    ("Napa", "Sonoma"),
    ("Napa", "Yolo"),
    ("Nevada", "Placer"),
    ("Nevada", "Sierra"),
    ("Nevada", "Yuba"),
    ("Orange", "Riverside"),
    ("Orange", "San Bernardino"),
    ("Orange", "San Diego"),
    ("Placer", "Sacramento"),
    ("Placer", "Sutter"),
    ("Placer", "Yuba"),
    ("Plumas", "Shasta"),
    ("Plumas", "Sierra"),
    ("Plumas", "Tehama"),
    ("Plumas", "Yuba"),
    ("Riverside", "San Bernardino"),
    ("Riverside", "San Diego"),
    ("Sacramento", "San Joaquin"),
    ("Sacramento", "Solano"),
    ("Sacramento", "Sutter"),
    ("Sacramento", "Yolo"),
    ("San Benito", "Santa Clara"),
    ("San Benito", "Santa Cruz"),
    ("San Francisco", "San Mateo"),
    ("San Joaquin", "Stanislaus"),
    ("San Luis Obispo", "Santa Barbara"),
    ("San Mateo", "Santa Clara"),
    ("San Mateo", "Santa Cruz"),
    ("Santa Barbara", "Ventura"),
    ("Santa Clara", "Santa Cruz"),
    ("Santa Clara", "Stanislaus"),
    ("Shasta", "Siskiyou"),
    ("Shasta", "Tehama"),
    ("Shasta", "Trinity"),
    ("Sierra", "Yuba"),
    ("Siskiyou", "Trinity"),
    ("Solano", "Sonoma"),
    ("Solano", "Yolo"),
    ("Stanislaus", "Tuolumne"),
    ("Sutter", "Yolo"),
    ("Sutter", "Yuba"),
    ("Tehama", "Trinity"),
)  # fmt: skip


def _neighbors() -> dict[str, frozenset[str]]:
    out: dict[str, set[str]] = defaultdict(set)
    for a, b in CA_ADJACENT_PAIRS:
        out[a].add(b)
        out[b].add(a)
    return {county: frozenset(n) for county, n in out.items()}


CA_NEIGHBORS = _neighbors()


def touching(a: list[str], b: list[str]) -> bool:
    """True when two county lists share a county or a county border."""
    return any(x == y or y in CA_NEIGHBORS.get(x, ()) for x in a for y in b)
