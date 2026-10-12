# App Review notes (draft)

New developer accounts are often asked, under guideline 2.1, for a screen
recording and answers about purpose, setup, external services, regions and
data licensing. This is the draft for that reply and for the App Review
Information "Notes" field, shaped like Queer Frame's 2026-10 answers.
`<Name>` and `<VERSION>` are filled in at submission.

## Notes field

No account or sign-in exists in this app, so no demo account, credentials or
sample files are needed. There is no user-generated content.

PURPOSE AND AUDIENCE
<Name> shows California's harmful algal bloom (toxic algae) advisories for
lakes, rivers and shorelines, from the State Water Resources Control
Board's public records, with each water's history since 2016. It is for
anyone heading to the water: swimmers, families, paddlers, anglers and dog
owners. Every status carries its date. An advisory stays listed until the
state records an end, and the app never says a water is safe.

HOW TO SEE THE MAIN FEATURES
- First launch shows a one-page introduction; tap "Start browsing" (About >
  "Show the introduction again" shows it again).
- Lakes tab: current advisories first, each with its posted date. Search
  for "Temescal" and open Lake Temescal for its status, what the level asks
  of people, children and pets, a section on dogs, each reported spot, and
  every record since 2016.
- Favorites: the star on a lake's screen.
- Full access (one non-consumable purchase): Favorites > "See the one-time
  unlock". It adds alerts and the widget. In the sandbox the purchase sheet
  is Apple's.
- Alerts (after the purchase): Favorites > "Turn on alerts". The app
  explains first; iOS asks for notification permission only then, never at
  launch. Alerts are local notifications planned on the iPhone from the
  data it downloads; there is no push service.
- Widget: "Favorite lakes" in the widget gallery. It reads a file the app
  writes into its own App Group container and makes no network request.

EXTERNAL SERVICES
- Data: the California State Water Resources Control Board's Freshwater
  Harmful Algal Bloom Program dataset on data.ca.gov; the Missouri
  Department of Natural Resources' harmful algal bloom map layer; and U.S.
  EPA CyAN weekly satellite estimates for large lakes, shown in a separately
  labeled section that is never an advisory. The app never contacts any of
  them. A daily job reads the public data and publishes
  one JSON file: <SNAPSHOT URL>
- Network: the app's only request is an HTTPS GET of that file (at launch
  and on return to the app when its data is more than 6 hours old, on pull
  to refresh, and in Background App Refresh), conditional on an ETag. It
  carries no identifier.
- Payment: one non-consumable in-app purchase through StoreKit.
- None of: authentication, analytics, ads, crash reporting, AI services,
  third-party SDKs. Privacy label: Data Not Collected.

REGIONS
Offered on the United States App Store only. The data covers California
and Missouri waters.

DATA LICENSE AND ATTRIBUTION (5.2.2)
The dataset page states "License: Other (Public Domain)" and "Rights: No
Restrictions on Public Use":
https://data.ca.gov/dataset/surface-water-freshwater-harmful-algal-blooms
Every lake screen and the About screen credit the source and link to the
state's official map. The About screen states the app is not affiliated
with or endorsed by any California agency. The app uses no state seals or
logos. Missouri data is used under the State of Missouri Data Policy
(https://mo.gov/data-policy), whose required disclaimer appears verbatim on
every Missouri lake screen and in About. EPA CyAN estimates are a U.S.
Government work, credited on every screen that shows one.

HEALTH AND SAFETY (1.4)
The app republishes official advisory records and does not give medical
advice or make its own assessment. It never describes a water as safe; when
the state's latest record recommends no advisory, it says so with the date
and that this is not a finding that the water is safe now. It tells people
to check posted signs and the official map. The level descriptions
summarize the state's sign levels.

## 2.1 reply (if asked)

Thank you for the review. Here is the information requested for <Name>
<VERSION>.

1. Screen recording: attached (iPhone, iOS <IOS VERSION>, build <VERSION>
   from TestFlight). It starts at launch and shows the introduction, the
   Lakes tab with current advisories and their dates, search, a lake
   (status, what the level asks, the dogs section, reported spots and
   history), adding a favorite, the full-access purchase screen, turning on
   alerts, the widget, and About with the data source and license. There is
   no account, login or user-generated content.

2. Purpose and audience: California's toxic algae advisories for lakes and
   rivers, from the state's public records, for swimmers, families,
   paddlers, anglers and dog owners deciding whether to go in the water.
   Every status carries its date; the app never says a water is safe.

3. Setup: no login, credentials or sample files are needed. Tap "Start
   browsing", search for "Temescal" and open Lake Temescal. Alerts: buy
   full access, favorite a lake, then Favorites > "Turn on alerts". Widget:
   "Favorite lakes" in the widget gallery.

4. External services: data from the California State Water Resources
   Control Board via data.ca.gov. The app never contacts the state; a daily
   job publishes one JSON file (<SNAPSHOT URL>), the app's only network
   request. Payment: one non-consumable in-app purchase. No
   authentication, analytics, ads, push service, AI services or third-party
   SDKs.

5. Regions: United States App Store only. The data covers California and
   Missouri.

6. Not a regulated industry. The advisory data is public domain ("Other
   (Public Domain)", "No Restrictions on Public Use",
   https://data.ca.gov/dataset/surface-water-freshwater-harmful-algal-blooms).
   Every lake screen and About credit the source and link to the state's
   official map, and About states the app is not affiliated with or
   endorsed by any California agency. We have no separate agreement with
   the state and can send a dated copy of the dataset page.
