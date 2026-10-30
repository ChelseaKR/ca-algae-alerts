# Serving lakenotice.com

Status: the domain is registered and nothing is published. Hosting is
decided (docs/DECISIONS.md 0013): this repository serves lakenotice.com with
GitHub Pages directly, so there is no second repository, no deploy key and no
gh-pages branch. `publish.yml` carries its daily schedule, but
`PAGES_ENABLED` is unset, so every run uploads the built site as an artifact
and deploys nothing until the owner sets that variable. Trout Truck's runbook
(`_agent-tools/remediate-2026-10-01/tt-domain/RUNBOOK.md`, Design B) is the
model for the order of steps where it applies; the owner runbook for this
site is `_agent-tools/growth/lake-notice-publish-runbook-2026-10-22.md`.

## What the build reads

- `SITE_BASE_URL` (repository variable, read by `publish.yml` and passed as
  `--base-url`). Empty falls back to `DEFAULT_BASE_URL` in `site.py`, which is
  `https://lakenotice.com/`. Every canonical link, the sitemap, robots.txt's
  sitemap line and the structured data take it.
- `SUPPORT_EMAIL` (variable): the support address on the support page.
- `APP_STORE_URL` (variable): the store link, empty until the record exists.
- `PAGES_ENABLED` (variable): `true` makes the workflow upload a Pages
  artifact and run the deploy job. Leave it unset until the domain serves.

There are no secrets to set for this model. Design B in Trout Truck adds
`DOMAIN_SITE_DEPLOY_KEY` (secret) and `DOMAIN_SITE_REPO` (variable) because
it pushes to a second repository; that is not needed here unless the owner
chooses that design, which would be its own change.

## Order, when the owner is ready

1. The domain is registered (member account for this app); nothing to buy.
2. Verify lakenotice.com with GitHub at the account level (a TXT record
   named `_github-pages-challenge-ChelseaKR`; keep it).
3. Pages on a private repository, source GitHub Actions; custom domain
   `lakenotice.com`; DNS A records to GitHub's four Pages addresses and a
   `www` CNAME to `chelseakr.github.io` (Trout Truck's runbook lists them).
4. Set the variables: `SITE_BASE_URL=https://lakenotice.com`,
   `SUPPORT_EMAIL`, then `PAGES_ENABLED=true`; run publish once. The schedule
   line is already in `publish.yml` and only deploys once `PAGES_ENABLED` is
   true.
5. Search Console: the domain property is verified; submit
   `https://lakenotice.com/sitemap.xml`.
6. Enforce HTTPS once GitHub offers it.

## After the site is live

- GA4: create a property named Lake Notice, put its measurement id in
  `GA4_MEASUREMENT_ID` in `site.py` (empty until then). The site sends no
  custom events yet (no `app_store_click`, no `gear_click`): the affiliate
  links add no tracking (DECISIONS 0013), so there is nothing to mark as a
  key event until that is built.
- Affiliate links: `AMAZON_ASSOCIATE_TAG` in `site.py` defaults to the existing
  Associates id `trouttruck-20`, so lakenotice.com must be on that account's
  website list before the links ship. They appear on the dogs page only. To
  use a Lake Notice id instead, create it and change that one constant; `""`
  removes the block and the privacy paragraph. DECISIONS 0013 and 0014.

## iOS identifiers to decide when the App Store record is created

None of these are changed by the naming change. Proposed values, current
values in parentheses:

- Bundle id: `net.chelseakr.lakenotice` (`net.chelseakr.algaealerts`)
- Widget: `net.chelseakr.lakenotice.widgets` (`...algaealerts.widgets`)
- Tests: `net.chelseakr.lakenotice.tests` and `.uitests`
- App Group: `group.net.chelseakr.lakenotice` (`group.net.chelseakr.algaealerts`)
- StoreKit product id: `net.chelseakr.lakenotice.fullaccess`
  (`net.chelseakr.algaealerts.fullaccess`); must match
  `PurchaseManager.productID` and `Configuration.storekit`
- Background task id: `net.chelseakr.lakenotice.refresh`
- URL scheme: `lakenotice` (`algaealerts`); `WaterLink.scheme`, `Info.plist`

Already decided and done (DECISIONS 0013): the snapshot URL
`https://lakenotice.com/snapshot/v1.json` and the site URL
`https://lakenotice.com/`, both in `SnapshotEndpoint`. Installed builds keep
the URL they were built with, so the domain must stay registered with
auto-renew on.
