# Changelog

All notable changes to this project are recorded here. The format follows
Keep a Changelog, and versions follow Semantic Versioning.

## [Unreleased]

### Added

- A plain-language terms of use page at /terms/, linked from every page's
  footer next to privacy and listed in the sitemap. It names who runs the
  site, says in bold that the site is not a safety determination, tells
  readers to follow posted signs and the managing agency, says the records
  can be wrong or late, and sets California law. It never calls a water safe
  (DECISIONS 0002); its affiliate paragraph renders only once the Associates
  tag is set (0013). Not reviewed by an attorney.
- After each deploy, new and changed pages are announced to IndexNow
  (https://www.indexnow.org/documentation), which Bing and the other
  participating engines share, so they are crawled sooner. The list comes from
  comparing the new `sitemap.xml` with the live one; a day with no change
  sends nothing. A failed or refused announcement logs a notice and never
  fails the deploy. The key file at the site root is public by design
  (docs/DECISIONS.md 0015).
- New York bloom history (docs/DECISIONS.md 0019), **off by default**
  (`site.NY_HISTORY_ENABLED`). When on: a `/state/ny/` page and one page per
  named water from New York DEC's yearly summary of confirmed blooms, 2019 to
  2025 (477 waters), as history only, never an advisory, a status or an end,
  with no alerts and nothing in the app's snapshot. Only waters with 2 or more
  bloom years or 5 or more reports may be indexed (284), and while
  `NY_INDEX_LIMIT` is 50 only the 50 with the most reports. Built from a
  pinned cache in `pipeline/data/ny/`; `python -m caalgae.newyork` refreshes
  it about once a year.

### Changed

- A water page with an advisory now has a search title that leads with the
  level and date from its headline, for example "Castaic Lake algae: Danger
  advisory, last posted Nov 3, 2026". Before, every title read "<water> toxic
  algae advisories | Lake Notice". Descriptions add the date of the state's
  file. A description whose status is not an advisory now carries the same
  not-a-finding sentence as the page's first line. Before, 603 descriptions
  left it out (docs/DECISIONS.md 0018).
- A water's headline now leads with the highest advisory level posted in
  the 12 months before the state's file date, dated by that posting. If
  nothing was posted in those 12 months, it leads with the newest posting.
  Before, a water could read "Danger advisory, last posted Sep 24, 2026" when
  the Danger came from an older report and Sep 24's posting was a Caution
  (Lake Elsinore; 81 waters on 2026-11-03). Lake Elsinore now reads "Caution
  advisory, last posted Sep 24, 2026". Older, higher advisories with no
  all-clear, and newer, lower postings, are named on the next line. Reports
  the state filed at the same coordinates are now one reported spot, so a
  later "None" there ends an older advisory at that spot. An advisory last
  posted more than 90 days before the state's file says how old it is and
  when the state last wrote anything for that water. Nothing is ever ended
  by silence (docs/DECISIONS.md 0017).

- Every water page now opens with one dated sentence: the state's data date,
  the water and its county, and the status headline, so the page answers "is
  there an algae advisory at this lake?" in its first line. A water outside
  the 24-month index window is indexable again when the state has published
  five or more records for it, which lists 118 more water pages on the
  2026-11-03 snapshot (docs/DECISIONS.md 0016).
- Google Analytics 4 is on for the website: Lake Notice's own property
  (measurement id `G-75YLGQKDHG`, docs/DECISIONS.md 0014). The tag is the one
  already built in (not loaded under Global Privacy Control, Do Not Track or the
  footer opt-out; ad signals denied; EEA, UK and Switzerland cookieless). The
  privacy page's GA4 text is now live, dated 2026-10-31, and says the data file
  the app downloads carries no analytics. The iPhone app is unchanged.
- A water page whose name matches another entry in the state's file within 6
  miles (another county, a stray "CA", swapped words) lists those entries with
  their own status, as "may be the same water". 56 pages on the 2026-10-29
  snapshot, for example Big Bear Lake, Lake Tulloch and Crowley Lake.
- The advisories page title and description name "toxic algae" and the level
  and date that each row shows.
- Each sitemap URL's `lastmod` is the newest record date the page shows, not
  the build date: a water's newest record, a county's or state's newest water,
  and the newest record overall for the home, advisories, county index and dogs
  pages. About, privacy and support carry no `lastmod`. A date after the
  snapshot's `run_date` is dropped. Two builds of one snapshot give the same
  sitemap bytes.
- A water page's breadcrumb (visible trail and BreadcrumbList) is now Home,
  the water's first county, the water, linking to the county page. Waters with
  no county keep Home, the water.
- The sitemap lists only waters with a state advisory in the last 24 months of
  the build's data date (`INDEX_WINDOW_MONTHS` in `site.py`). Every other water
  page is still built and linked, with `noindex,follow` and no canonical, and
  an identical body. Home, advisories, county and dogs pages are unchanged.
- Every page title is at most 60 characters and every description at most 155,
  so search results no longer cut them off. A water's title is now its name and
  "toxic algae advisories"; two waters in one state with the same name carry
  their county in the title. Descriptions drop "County not recorded".
- The product is named Lake Notice and the domain is lakenotice.com
  (docs/DECISIONS.md 0012). The site name, both iOS display names, the
  default base URL and the listing draft change; bundle ids, the App Group
  and the product id do not (docs/DOMAIN.md).
- The app's snapshot and site URLs are https://lakenotice.com/snapshot/v1.json
  and https://lakenotice.com/ (docs/DECISIONS.md 0013); the site is served from
  this repository. The publish workflow has its daily schedule, skipped until
  the PAGES_ENABLED variable is set.
- Missouri stays in 1.0 pending the owner's confirmation of its status-code
  readings (docs/MISSOURI-READINGS.md).

### Added

- Website: a dog-gear block of Amazon search links on lake pages and a
  privacy-page section, both off until `AMAZON_ASSOCIATE_TAG` in `site.py` is
  set (docs/DECISIONS.md 0013). Never a home toxin test kit.
- Pipeline: discovers the dated FHAB Responses CSV from the data.ca.gov
  dataset page, normalizes it with the state's own advisory levels and a
  mapped tier, keeps an append-only history seeded from the 2026-10-09 file,
  and builds a schema-validated snapshot whose statuses come only from
  explicit records.
- Free static site: latest advisories with dates, every open advisory, one
  page per waterbody with its history, county pages, a dogs page, about,
  privacy and support pages, sitemap and structured data.
- iPhone app: browse and search, lake screens with history, favorites, local
  alerts and a widget behind a one-time unlock, an introduction.
- Multi-state model: per-source license, attribution, required disclaimer,
  revocation and lift semantics, and a record kind that separates official
  advisories from satellite estimates. Missouri DNR cases (since 2017) and
  EPA CyAN weekly satellite estimates for matched California and Missouri
  lakes.
- CI: `make verify`, Swift package tests, site accessibility and performance
  gates, workflow SAST, a scheduled secret scan, and a manual publish
  workflow (Pages off).
