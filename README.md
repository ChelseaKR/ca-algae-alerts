# Algae Alerts (working title)

Toxic-algae (harmful algal bloom) advisories for lakes and rivers, per
waterbody, with full history: California from the State Water Resources
Control Board's public-domain FHAB data (since 2016) and Missouri from the
Department of Natural Resources' HAB layer (since 2017), plus a separately
labeled EPA CyAN satellite estimate for large lakes, which is never an
advisory (docs/DECISIONS.md 0010). A free static site
and a paid iPhone app with local alerts, no account for either, on the
pattern of Trout Truck (`ChelseaKR/ca-fish-planting-alerts`).

**Status:** in build. Private repository. Nothing is published: GitHub
Pages is off and no App Store record exists.

The one rule: an advisory stands until the state records an explicit end.
Nothing here ever says a water is safe, and silence never ends an advisory.

```sh
make verify
```

See `pipeline/README.md` for the pipeline and `docs/LICENSES-AND-ATTRIBUTION.md`
for the data terms.
