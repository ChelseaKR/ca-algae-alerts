# Changelog

All notable changes to this project are recorded here. The format follows
Keep a Changelog, and versions follow Semantic Versioning.

## [Unreleased]

### Added

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
