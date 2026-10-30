# Sources, terms, attribution

Read before the first pipeline fetch, 2026-10-12. **Unknown = not used**
(docs/DECISIONS.md 0004). Nobody was contacted.

| Source | What we take | Terms (verbatim, where, date read) | Commercial reuse | Attribution | Cadence |
|---|---|---|---|---|---|
| State Water Resources Control Board, "Surface Water – Freshwater Harmful Algal Blooms" on data.ca.gov | The Responses table (`hab-responses_<date>.csv`): one row per advisory action on one bloom report | Dataset page <https://data.ca.gov/dataset/surface-water-freshwater-harmful-algal-blooms>, read 2026-10-12: "License: Other (Public Domain)"; "Rights: No Restrictions on Public Use". Program contact: CyanoHAB.Reports@waterboards.ca.gov (recorded, not contacted). | Permitted (public domain, no restriction stated) | Not required by the terms. We credit the source on every page and screen anyway (below). | The files are republished about daily; advisory updates arrive 20 to 30 a week in season |
| The same dataset's disclaimer PDF (`habs-disclaimer-for-data-dictionary.pdf`) | How to read the data, not data we republish | Quoted where it decides behavior: "A blank field should be interpreted as 'unknown' and not 'none.'"; "Advisory 'End Date' can be blank for a long time"; "a recommended advisory may or may not result in a posting of the advisory on the ground"; "If a report represents a confirmed bloom, an advisory is recommended with a value other than 'none,' which corresponds with no recommended advisory based on the available information." | n/a | n/a | n/a |
| My Water Quality HAB map, <https://mywaterquality.ca.gov/habs/> | **Nothing.** Linked for readers only. | `https://mywaterquality.ca.gov/robots.txt` allows only Googlebot and sets `Disallow: /` for everyone else. The pipeline refuses this host (`fetch.guard_url`). | Not used | Linked as the official source | n/a |

## Second state and the satellite layer (added 2026-10-12)

| Source | What we take | Terms (verbatim, where, date read) | Commercial reuse | Attribution or condition | Cadence |
|---|---|---|---|---|---|
| Missouri DNR, Harmful Algal Blooms (public water bodies), `https://gis.dnr.mo.gov/host/rest/services/wqm/HAB_SUBMIT_POINTS/MapServer/6` | Only `objectid`, `WBName`, `HABODat`, `BloomStat`, `CaseStatus`, `DissDat`, `WBType` and the point. Never the agency, owner, reporter or free-text fields. | `https://mo.gov/data-policy`, read 2026-10-12: "Applications using data supplied by this site must include the following disclaimers on their sites: “The data made available here has been modified for use from its original source, which is the State of Missouri. THE STATE OF MISSOURI MAKES NO REPRESENTATIONS OR WARRANTY AS TO THE COMPLETENESS, ACCURACY, TIMELINESS, OR CONTENT OF ANY DATA MADE AVAILABLE THROUGH THIS SITE. THE STATE OF MISSOURI EXPRESSLY DISCLAIMS ALL WARRANTIES, WHETHER EXPRESS OR IMPLIED, INCLUDING ANY IMPLIED WARRANTIES OF MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE. The data is subject to change as modifications and updates are complete. It is understood that the information contained in the Web feed is being used at one’s own risk.”" And: "The State of Missouri reserves the right to modify and/or discontinue providing any or all of the data feeds at any time and to require the termination of any and all displaying, distributing or otherwise using any or all of the data for any reason including, without limitation, your violation of any provision of these Terms of Use." | Not prohibited; no commercial carve-out either way | The disclaimer, verbatim, on every Missouri page, the Missouri state page and the about page, linked from every page's footer; and the app's Missouri lake screens and About. Revocable: `sources.MO_DNR_HAB.enabled` turns Missouri off in one place. Whether mo.gov's policy covers gis.dnr.mo.gov is an owner judgment (the research lane's note). Re-read 2026-10-30: the policy text is unchanged, and dnr.mo.gov's footer links it. The department's map disclaimer ("general purposes only") is quoted beside the data. If the layer is gone or changed, Missouri is hidden (DECISIONS 0014). | One request per daily run; 278 cases since 2017 |
| U.S. EPA CyAN (CyANWeb backend), `https://qed.epa.gov/cyanweb/` | Waterbody list (name, id, state, area, centroid) and, for matched California and Missouri lakes, the weekly cells/mL series at CyAN's centroid. Nothing personal exists in either. | No license is stated on the API. `https://www.epa.gov/web-policies-and-procedures/epa-disclaimers` (via the research lane, read 2026-10-12): "geospatial data produced by the EPA is by default in the public domain … under 17 U.S.C. § 105". EPA calls CyANWeb "an experimental application … provisional … a research level tool". The research rated the API formally Unclear and the federal default Clear; the owner approved adding it on 2026-10-12. | Public domain by federal default | Credited on every lake page with an estimate and in About; "EPA does not endorse this site." | List once, then one request per matched lake, 2 s apart, at most weekly (85 lakes on 2026-10-12) |

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

- `https://gis.dnr.mo.gov/robots.txt` (Missouri's layer): **404, no file**,
  read 2026-10-12. `https://dnr.mo.gov/robots.txt` and
  `https://mo.gov/robots.txt` are 200 and allow the pages read.
- `https://qed.epa.gov/robots.txt` and `https://cyan.epa.gov/robots.txt`:
  **404, no file**. `https://www.epa.gov/robots.txt` is 200.

How the pipeline treats robots.txt for these hosts (`fetch.robots_allows`,
checked on every live run before any other request), per the owner's ruling
of 2026-10-12 (docs/DECISIONS.md 0011): a readable file is enforced; a 404 or
missing file means no rules; a 403, a 5xx, a redirect to a page that is not a
robots.txt, any other status, or no answer makes the host off-limits, and
nothing is fetched from it.

## Crawl budget

- One GET of the dataset page and one GET of the file it links, per run,
  once a day. The file GET is a 302 to signed storage that expires in about
  60 seconds, so it is followed at once.
- `User-Agent: ca-algae-alerts/<version> (+https://github.com/ChelseaKR/ca-algae-alerts)`.
- 2026-10-12, by hand while building: two dataset-page reads (one hit a
  308 to the publisher-scoped path) and three file downloads (the Responses
  CSV and two PDFs), at least 2 seconds apart.
- 2026-10-12, Missouri and CyAN while building: the two robots.txt files,
  one Missouri layer-metadata request, one Missouri query, the MO DNR HAB
  page and the mo.gov data policy (both robots-allowed), one CyAN list
  request, two CyAN sample series, then one live refresh (robots, list, 85
  series at 2 s spacing).
- The research lane's earlier slip (four CKAN `package_search` calls before
  robots.txt was read) is recorded in its own notes. This repository has
  made none.
