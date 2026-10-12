# Sources, terms, attribution

Read before the first pipeline fetch, 2026-10-12. **Unknown = not used**
(docs/DECISIONS.md 0004). Nobody was contacted.

| Source | What we take | Terms (verbatim, where, date read) | Commercial reuse | Attribution | Cadence |
|---|---|---|---|---|---|
| State Water Resources Control Board, "Surface Water – Freshwater Harmful Algal Blooms" on data.ca.gov | The Responses table (`hab-responses_<date>.csv`): one row per advisory action on one bloom report | Dataset page <https://data.ca.gov/dataset/surface-water-freshwater-harmful-algal-blooms>, read 2026-10-12: "License: Other (Public Domain)"; "Rights: No Restrictions on Public Use". Program contact: CyanoHAB.Reports@waterboards.ca.gov (recorded, not contacted). | Permitted (public domain, no restriction stated) | Not required by the terms. We credit the source on every page and screen anyway (below). | The files are republished about daily; advisory updates arrive 20 to 30 a week in season |
| The same dataset's disclaimer PDF (`habs-disclaimer-for-data-dictionary.pdf`) | How to read the data, not data we republish | Quoted where it decides behavior: "A blank field should be interpreted as 'unknown' and not 'none.'"; "Advisory 'End Date' can be blank for a long time"; "a recommended advisory may or may not result in a posting of the advisory on the ground"; "If a report represents a confirmed bloom, an advisory is recommended with a value other than 'none,' which corresponds with no recommended advisory based on the available information." | n/a | n/a | n/a |
| My Water Quality HAB map, <https://mywaterquality.ca.gov/habs/> | **Nothing.** Linked for readers only. | `https://mywaterquality.ca.gov/robots.txt` allows only Googlebot and sets `Disallow: /` for everyone else. The pipeline refuses this host (`fetch.guard_url`). | Not used | Linked as the official source | n/a |

## Attribution shown

Every site page footer and the app's About screen carry:

> Advisory data: California State Water Resources Control Board, Freshwater
> Harmful Algal Bloom Program, via data.ca.gov (public domain). Advisories
> are recommendations; reporting is voluntary and incomplete.

with a link to the dataset page and to the official map. The text lives in
`pipeline/src/caalgae/sources.py` and is copied into every snapshot
(`sources[].attribution`), with the license, per source. Every record names
its source id, so a second state's records carry their own terms.

## robots.txt (read 2026-10-12)

- `https://data.ca.gov/robots.txt`: `Disallow: /api/`, `/datastore/`,
  `/search?`; `Allow: /`.
- `https://publish.data.ca.gov/robots.txt`: `Disallow: /api/`,
  `Crawl-Delay: 10`.
- `https://mywaterquality.ca.gov/robots.txt`: Googlebot only.

The pipeline never builds a URL under a disallowed prefix; `fetch.guard_url`
refuses one if it ever did, and the tests try each.

## Crawl budget

- One GET of the dataset page and one GET of the file it links, per run,
  once a day. The file GET is a 302 to signed storage that expires in about
  60 seconds, so it is followed at once.
- `User-Agent: ca-algae-alerts/<version> (+https://github.com/ChelseaKR/ca-algae-alerts)`.
- 2026-10-12, by hand while building: two dataset-page reads (one hit a
  308 to the publisher-scoped path) and three file downloads (the Responses
  CSV and two PDFs), at least 2 seconds apart.
- The research lane's earlier slip (four CKAN `package_search` calls before
  robots.txt was read) is recorded in its own notes. This repository has
  made none.
