# docs/app-store/

- `LISTING.md`: draft listing copy (leads with dogs in the subtitle, first
  caption and keywords; the description covers everyone).
- `REVIEW-NOTES.md`: the App Review notes and a draft 2.1 reply.
- `screenshots/`: simulator captures, 6.3-inch (iPhone 17 Pro). App Store
  Connect also wants 6.9-inch; capture those on an iPhone 17 Pro Max
  simulator with `ios/scripts/screenshots.sh` before submission.

## What has to exist before submission (owner steps)

1. Register the bundle id `net.chelseakr.algaealerts` (or the final one)
   and the widget's `net.chelseakr.algaealerts.widgets`, with the App Group
   `group.net.chelseakr.algaealerts`, in the developer account, and set
   `DEVELOPMENT_TEAM` in `ios/project.yml`.
2. Create the App Store Connect app record (US only, version 1.0.0).
3. Create the in-app purchase: non-consumable, product id
   `net.chelseakr.algaealerts.fullaccess`, USD 9.99, display name "Full
   Access". It must match `PurchaseManager.productID` and
   `ios/AlgaeAlerts/Configuration.storekit`.
4. Decide hosting: the app fetches
   `https://chelseakr.github.io/ca-algae-alerts/snapshot/v1.json`, which does
   not serve until Pages is on (docs/DECISIONS.md 0008). If a domain is
   chosen instead, change `SnapshotEndpoint` before the first build ships,
   because shipped builds keep the URL they were built with.
5. Privacy policy and support URLs: the site's `/privacy/` and `/support/`
   pages, once published.
