# Changelog

All notable changes to this project are recorded here. The format follows
Keep a Changelog, and versions follow Semantic Versioning.

## [Unreleased]

### Changed

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
