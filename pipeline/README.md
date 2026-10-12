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

```sh
uv sync
uv run pytest
uv run caalgae --fixture-page tests/fixtures/dataset-page-2026-10-12.html \
  --fixture-csv tests/fixtures/responses-traps_2026-10-09.csv \
  --run-today 2026-10-12 --history /tmp/caalgae/history.json \
  --snapshot-out /tmp/caalgae/snapshot.json --site-out /tmp/caalgae/site
```

A live run (no `--fixture-*` flags) makes exactly two requests: the dataset
page and the file it links. It never calls `data.ca.gov/api/` and never
touches `mywaterquality.ca.gov` (`fetch.guard_url`).

## Fixtures

- `dataset-page-2026-10-12.html`: the dataset page as served on 2026-10-12.
- `responses-traps_2026-10-09.csv`: 17 hand-built rows with the real header,
  one or two per trap (blank end date, explicit None, NA, end dates in the
  past and future, casing variants, multi-county, out-of-state county, bad
  dates, blank name, blank level, same-day ordering).
- `responses-sample_2026-10-09.csv`: every real row for twelve waterbodies,
  from the 2026-10-09 file. Public domain (see `../NOTICE`).
