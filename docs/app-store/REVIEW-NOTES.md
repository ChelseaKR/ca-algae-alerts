# App Review notes (draft)

New developer accounts are often asked, under guideline 2.1, for a screen
recording and answers about purpose, setup, external services, regions and
data licensing. This is the draft for that reply and for the App Review
Information "Notes" field. `<VERSION>` and `<IOS VERSION>` are filled in at
submission. Keep the Notes field under 4,000 characters
(`pipeline/tests/test_app_store_copy.py` checks it).

Missouri is written in as live. On submission day, if Missouri is turned off
or in its data-unavailable mode, remove each sentence marked [MO] below and
change "California and Missouri" to "California". If Missouri is live,
delete only the [MO] markers.

## Notes field

WHAT LAKE NOTICE IS
Lake Notice is built around one kind of record: harmful algal bloom
advisories, which have sign levels, spots and no reliable end date. Most of
the app's work is saying what a record does not mean. Each lake shows what
its level asks of people, children and pets, a dogs section, what to do
after contact, and every spot's history. The app never sends an all-clear
and never says a water is safe. It shares a developer with Trout Truck but
has no code paths, data or screens for fish stocking, and Trout Truck has
none of this.

No account or sign-in exists in this app, so no demo account, credentials or
sample files are needed. There is no user-generated content.

WHO IT IS FOR
Swimmers, families, paddlers, anglers and dog owners. It shows the
advisories California and Missouri have recorded for lakes, rivers and
shorelines, from the states' public records. Every status carries its date,
and an advisory stays listed until the state records an end.

WHERE TO LOOK
- First launch shows a one-page introduction; tap "Start browsing".
- Search for "Temescal" and open Lake Temescal: its status, what the level
  asks of people, children and pets, the dogs section, after-contact steps,
  each reported spot, and every record since 2016.
- Favorites: the star on a lake's screen.
- Lake Alerts & Widget (one non-consumable purchase): Favorites > "See the
  one-time unlock". In the sandbox the purchase sheet is Apple's.
- Alerts (after the purchase): Favorites > "Turn on alerts". The app
  explains first; iOS asks for notification permission only then, never at
  launch. Alerts are local notifications planned on the iPhone from the
  data it downloads; there is no push service.
- Widget: "Favorite lakes" in the widget gallery. It makes no network
  request.

DATA AND NETWORK
- Sources: the California State Water Resources Control Board's Freshwater
  Harmful Algal Bloom Program dataset on data.ca.gov; [MO] the Missouri
  Department of Natural Resources' harmful algal bloom map layer; and U.S.
  EPA CyAN weekly satellite estimates for large lakes, in a separately
  labeled section that is never an advisory and never alerts. The app never
  contacts any of them. A daily job reads the public data and publishes one
  JSON file: https://lakenotice.com/snapshot/v1.json
- The app's one request is an HTTPS GET of that file (at launch and on
  return to the app when its data is more than 6 hours old, on pull to
  refresh, and in Background App Refresh), conditional on an ETag. It
  carries no identifier.
- Payment: one non-consumable in-app purchase through StoreKit.
- None of: authentication, analytics, ads, crash reporting, AI services,
  third-party SDKs. Privacy label: Data Not Collected.

REGIONS
Offered on the United States App Store only. The data covers California
and Missouri waters.

DATA LICENSE AND ATTRIBUTION (5.2.2)
The California dataset page states "License: Other (Public Domain)" and
"Rights: No Restrictions on Public Use":
https://data.ca.gov/dataset/surface-water-freshwater-harmful-algal-blooms
Every lake screen and the About screen credit the source and link to the
state's official map. About states the app is not affiliated with or
endorsed by any state or federal agency. The app uses no state seals or
logos. [MO] Missouri data is used under the State of Missouri Data Policy
(https://mo.gov/data-policy), whose required disclaimer appears verbatim on
every Missouri lake screen and in About. EPA CyAN estimates are a U.S.
Government work, credited on every screen that shows one.

HEALTH AND SAFETY (1.4)
The app republishes official records and makes no assessment of its own.
Each lake says it is not medical advice. When the state's latest record
recommends no advisory, the app gives the date and says it is not a finding
that the water is safe now.

## 2.1 reply (if asked)

Thank you for the review. Here is the information requested for Lake Notice
<VERSION>.

1. Screen recording: attached (iPhone, iOS <IOS VERSION>, build <VERSION>
   from TestFlight). It starts at launch and shows the introduction, the
   Lakes tab with advisories and their dates, search, a lake (status, what
   the level asks, the dogs section, after-contact steps, reported spots and
   history), adding a favorite, the Lake Alerts & Widget purchase screen,
   turning on alerts, the widget, and About with the data sources and
   licenses. There is no account, login or user-generated content.

2. Purpose and audience: the toxic algae advisories California and
   Missouri have recorded for lakes and rivers, from the states' public
   records, for swimmers, families, paddlers, anglers and dog owners
   deciding whether to go in the water. Every status carries its date; the
   app never says a water is safe.

3. Setup: no login, credentials or sample files are needed. Tap "Start
   browsing", search for "Temescal" and open Lake Temescal. Alerts: buy Lake
   Alerts & Widget, favorite a lake, then Favorites > "Turn on alerts".
   Widget: "Favorite lakes" in the widget gallery.

4. External services: data from the California State Water Resources
   Control Board via data.ca.gov, [MO] the Missouri Department of Natural
   Resources, and U.S. EPA CyAN. The app never contacts them; a daily job
   publishes one JSON file (https://lakenotice.com/snapshot/v1.json), the
   app's one network request. Payment: one non-consumable in-app purchase.
   No authentication, analytics, ads, push service, AI services or
   third-party SDKs.

5. Regions: United States App Store only. The data covers California and
   Missouri.

6. Not a regulated industry. The California data is public domain ("Other
   (Public Domain)", "No Restrictions on Public Use",
   https://data.ca.gov/dataset/surface-water-freshwater-harmful-algal-blooms).
   [MO] The Missouri data is used under the State of Missouri Data Policy,
   with its required disclaimer shown in the app. Every lake screen and
   About credit the source and link to the state's official map, and About
   states the app is not affiliated with or endorsed by any state or
   federal agency. We have no separate agreement with either state and can
   send a dated copy of each dataset page.
