# Lake Notice

Toxic-algae (harmful algal bloom) advisories for lakes and rivers, per
waterbody, with full history: California from the State Water Resources
Control Board's public-domain FHAB data (since 2016) and Missouri from the
Department of Natural Resources' HAB layer (since 2017), plus a separately
labeled EPA CyAN satellite estimate for large lakes, which is never an
advisory (docs/DECISIONS.md 0010). A free static website
with no account, on the pattern of Trout Truck
(`ChelseaKR/ca-fish-planting-alerts`).

The domain is lakenotice.com (docs/DOMAIN.md has the variables to set when
it is served).

**Status:** live at lakenotice.com since 2026-10-22. Public repository.
Website only; there is no app.

The one rule: an advisory stands until the state records an explicit end.
Nothing here ever says a water is safe, and silence never ends an advisory.

```sh
make verify
```

See `pipeline/README.md` for the pipeline and `docs/LICENSES-AND-ATTRIBUTION.md`
for the data terms.
`docs/accessibility/ACR.md` is the website's Accessibility Conformance Report
(WCAG 2.2 A and AA, provisional until its human screen-reader walkthrough).
