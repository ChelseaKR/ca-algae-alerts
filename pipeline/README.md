# pipeline/

Python 3.12, managed with `uv`. One command, `caalgae`, runs the whole chain:

1. Read the dataset page
   <https://data.ca.gov/dataset/surface-water-freshwater-harmful-algal-blooms>
   and find the dated Responses file (`hab-responses_<YYYY-MM-DD>.csv`).
   The file name changes every day, and the CKAN API is disallowed by
   robots.txt, so the page is the only way to find it.
2. Download it (a redirect to short-lived signed storage, followed).
3. Normalize every row (`normalize.py`): the state's advisory level kept
   verbatim, a mapped tier beside it, dates checked, bad rows quarantined
   and counted.
4. Merge into `data/history.json`, the append-only copy (`history.py`).
5. Derive each site's and each waterbody's status from explicit records only
   (`status.py`), build the snapshot, validate it against
   `../schema/snapshot.v1.json` (`snapshot.py`).
6. Build the static site (`site.py`).

Beside California (docs/DECISIONS.md 0010): `missouri.py` reads Missouri's
HAB layer (one request, explicit non-personal fields) into the same record
shape, and `cyan.py` keeps a weekly cache of EPA CyAN satellite estimates
for matched California and Missouri lakes, in a block of its own that never
decides a status. Each live run checks each host's robots.txt first
(`fetch.robots_allows`). A Missouri or CyAN failure warns and keeps the
last data; only a California failure stops the run.

New York (docs/DECISIONS.md 0016) is history only and off by default
(`site.NY_HISTORY_ENABLED`). `newyork.py` builds it from the pinned cache in
`data/ny/`; the daily run never fetches it. About once a year, when DEC posts a
season, `uv run --frozen python -m caalgae.newyork` reads data.ny.gov's
robots.txt and then the dataset (three requests, at least 2 s apart), rewrites
the cache and prints its new SHA-256 for `newyork.PINNED_SHA256`. Preview the
section with `--ny-history on` (add `--ny-cache tests/fixtures/ny` for the
small fixture).

```sh
uv sync
uv run pytest
uv run caalgae --fixture-page tests/fixtures/dataset-page-2026-10-12.html \
  --fixture-csv tests/fixtures/responses-traps_2026-10-09.csv \
  --mo-fixture tests/fixtures/mo-hab-points-2026-10-12.json \
  --cyan-cache tests/fixtures/cyan-cache-traps.json \
  --run-today 2026-10-12 --history /tmp/caalgae/history.json \
  --snapshot-out /tmp/caalgae/snapshot.json --site-out /tmp/caalgae/site
```

A live run (no `--fixture-*` flags) makes two California requests (the
dataset page and the file it links), two Missouri requests (robots.txt and
the layer), and, at most weekly, the CyAN refresh. It never calls `data.ca.gov/api/` and never
touches `mywaterquality.ca.gov` (`fetch.guard_url`).

## Fixtures

- `dataset-page-2026-10-12.html`: the dataset page as served on 2026-10-12.
- `responses-traps_2026-10-09.csv`: 17 hand-built rows with the real header,
  one or two per trap (blank end date, explicit None, NA, end dates in the
  past and future, casing variants, multi-county, out-of-state county, bad
  dates, blank name, blank level, same-day ordering).
- `responses-sample_2026-10-09.csv`: every real row for twelve waterbodies,
  from the 2026-10-09 file. Public domain (see `../NOTICE`).
