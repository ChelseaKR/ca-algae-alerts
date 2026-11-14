# Decisions

Owner decisions are marked **(owner, date)**. Everything else is a build
decision made while carrying them out, and can be changed.

## 0001 — The product: a free site and a paid iPhone app, Trout Truck's pattern (owner, 2026-10-12)

A California toxic-algae (harmful algal bloom) lake-advisory product on the
Trout Truck pattern (`ChelseaKR/ca-fish-planting-alerts`):

- A free static website, one page per waterbody, is the discovery surface.
- A paid iPhone app: **free download, one $9.99 non-consumable in-app
  purchase** ("Full access"). Browsing, search, favorites and every lake's
  history are free. **Alerts and the widget are the unlock.** The app's free
  tier is never worse than the free site.
- Build now, **submit in winter**, ahead of the spring and summer season.
- **New private repository**, `ChelseaKR/ca-algae-alerts`.
- Placeholders until the owner registers them: bundle id
  `net.chelseakr.algaealerts`, widget `net.chelseakr.algaealerts.widgets`,
  App Group `group.net.chelseakr.algaealerts`, product id
  `net.chelseakr.algaealerts.fullaccess`, URL scheme `algaealerts`. No
  development team is set. Nothing was copied from Trout Truck's signing,
  App Store ids or bundle id.

## 0002 — Status only from explicit records; never "safe" (owner, 2026-10-12)

- A lake shows "advisory posted" **until the state records an explicit
  all-clear**. Silence never ends an advisory, and nothing is inferred.
- A lake whose last advisory was never lifted reads **"last advisory posted
  <date>, no all-clear recorded"**. The site and the app use the form
  "<Level> advisory, last posted <date>. No all-clear recorded."
- **Never "safe".** The most the data supports is "the state's latest record,
  from <date>, recommends no advisory", followed by a sentence saying it is
  not a finding that the water is safe now. Copy guards on both sides fail
  any sentence that mentions safety or an all-clear without negating it.

How this is implemented (build decisions):

- What counts as explicit: the state's **"None"** record ("no recommended
  advisory based on the available information", per the dataset's
  disclaimer) at the same reported spot, or an **end date the state
  recorded** that is on or before the run date. A blank end date is
  unknown (the disclaimer's own words), never "ended".
- "NA - refer to Report Details" and blank levels decide nothing.
- A waterbody shows an advisory if any of its reported spots does. A
  "None" at one spot does not clear another spot.
- The schema and the app's decoder both refuse an advisory without a
  posted date and an end without a date.
- "Posted" here means published in the state's records. The about page says
  so, because the state notes that a recommended advisory "may or may not
  result in a posting of the advisory on the ground". **Owner to confirm
  the word** (NOTES.md in the hand-off).

## 0003 — Multi-state from day one, California only for now (owner, 2026-10-12)

Every waterbody carries a `state` field and every record a `source` id; the
snapshot carries each source's license, rights and attribution text
(`pipeline/src/caalgae/sources.py`). Superseded in part by 0010, which adds
Missouri and the EPA CyAN layer.
A parallel research lane surveys other states'
data (`_agent-tools/remediate-2026-10-12/algae-states/RESEARCH.md`).

## 0004 — License before bytes; robots.txt is binding (2026-10-12)

The dataset page's terms ("Other (Public Domain)", "No Restrictions on
Public Use") were read and quoted in `docs/LICENSES-AND-ATTRIBUTION.md`
before the first pipeline fetch. Unknown = not used. The pipeline never
calls `data.ca.gov/api/` or any other disallowed prefix and never touches
`mywaterquality.ca.gov`, whose robots.txt admits only Googlebot. The dated
file name is discovered from the dataset page's HTML.

## 0005 — Audience: neutral product, marketing that leads with dogs (owner, 2026-10-12)

Replaces the morning's "primary audience dog owners".

- The product and its name are **neutral**, for anyone who uses California
  lakes: swimmers, families, kayakers and paddlers, anglers, dog owners.
- App copy, the introduction and lake pages speak to everyone: the advisory
  level and who it asks to take care (people, children, pets).
- Dog guidance is a **clearly labeled section** on each lake page and lake
  screen ("Dogs at <lake>", "Dogs"), not the whole framing.
- The **store listing draft leads with dogs** in the subtitle, the first
  screenshot caption and the keywords; the description covers everyone.
- The free site has dog-focused landing content (`/dogs/`, "Is this lake
  safe for my dog?") answered honestly: the records cannot say yes, and no
  advisory is not an all-clear.
- Name candidates are neutral: no "bloom", nothing dog-specific in the app
  name. A dog angle may go in the subtitle.
- No fear-led copy.

## 0006 — Alerts are local notifications from a refreshed snapshot (2026-10-12)

As Trout Truck (its decision 0001): no server push, no accounts, no device
tokens. The app refreshes the snapshot (background task and on open, at most
every 6 hours) and plans alerts on the phone. Honest because the state
republishes about daily; copy says "within about a day", never "real time".

The rule (`AlertPlanner`): a favorite alerts when its status becomes an
advisory (from a recorded end, an unclassified report, or nothing) or when
an advisory's level changes. A weekly re-posting at the same level does not
alert. The app never sends an "all-clear" alert. The first sighting of a
favorite only records it. Each alert has a "Mute this lake" button.

## 0007 — Data posture: the app collects nothing; the site gets GA4 under GPC (2026-10-12)

The portfolio rule: GA4 on the website only, honoring Global Privacy
Control and Do Not Track, ads features off, Consent Mode denials in the
EEA, UK and Switzerland, a footer opt-out. The tag is built in
(`_ga4.html.jinja`) but **off until the owner creates a GA4 property** and
sets `GA4_MEASUREMENT_ID` in `site.py`. With it empty, the privacy page says
nothing is collected, and that is true. The app has no analytics and no
SDK; its privacy label is Data Not Collected.

## 0008 — Nothing is published yet (owner, 2026-10-12)

GitHub Pages stays off until the owner decides (Pages on a private
repository may be billable). The publish workflow is manual-only and
uploads the built site as a run artifact; it deploys only when the
repository variable `PAGES_ENABLED` is `true`. The app's snapshot URL
(`https://chelseakr.github.io/ca-algae-alerts/snapshot/v1.json`) does not
serve yet, so the app relies on the snapshot bundled at build time and says
when a check did not finish. No App Store Connect record, no domain.

## 0009 — Waterbody identity (2026-10-12)

The source has no waterbody id. A waterbody is the case-insensitive water
body name within the source's county text; its id is
`<state>-<county>-<name>` slugged (`ca-alameda-lake-temescal`). Measured:
no bloom report changes name or county, and casing variants ("Lake perris")
merge. Known limit: a lake typed under two county texts (Lake Tahoe under
El Dorado and under Placer) becomes two pages. A curated alias table, as
Trout Truck keeps, is the fix if the owner wants it.

**Display names (2026-11-04).** The state's files type names by hand, and
some reached page titles as typed: "Big bear lake ca", "Briars pond",
"crystal pool", and "Lake Havasu (Arizona), Arizona State" where a county
belongs. The site now shows a display name and place
(`pipeline/src/caalgae/water_names.py`). The history, the snapshot, the
app and every id keep the source's spelling, so this is display only and
leaves identity as above.

- A reviewed override table, keyed by water id and the exact source
  spelling, for the three names no rule fixes safely. A retyped name drops
  out of the table and gets the rules.
- A trailing suffix naming the water's own state is dropped: " ca" after a
  water word in California, ", MO" or ", Missouri" in Missouri. Missouri's
  " CA" (a conservation area) and "Lake California" are kept.
- Casing: a lowercase first letter is capitalized. A proper name whose
  lowercase words are one run at its end, led or ended by a water word, is
  capitalized ("Diamond valley lake" to "Diamond Valley Lake"). Names that
  describe a water ("Unnamed pond", "Private pond"), names with a comma,
  and small words ("of", "du") are left alone. No word is ever dropped:
  "Fee fee creek" is Fee Fee Creek.
- Place: "Nevada State" and "Arizona State" show as "Nevada" and "Arizona",
  as a Missouri water shows "Missouri". Other county text that names no
  California county shows nothing. A county is never guessed, and a place
  the name already carries is not repeated.
- Titles add a county only when the source spelling is shared, as before,
  so a display name never adds or drops a county from a title.

On the 2026-11-04 snapshot this changes 41 waters (37 names, 4 places) and
the titles of 37 water pages, 12 of them indexable. NY names (staged
branch) needed no fix. Undo: make `display_water` return the water
unchanged.

## 0010 — The multi-state wave: Missouri and EPA CyAN (owner, 2026-10-12)

The owner approved the state research lane's recommendations
(`_agent-tools/remediate-2026-10-12/algae-states/RESEARCH.md`): make the
model multi-state now, add Missouri as the second state, and add EPA CyAN as
a separate satellite layer for California and Missouri lakes. North Dakota,
Rhode Island, New Jersey and North Carolina are **not** added.

The model, per source (`sources.py`) and per record:

- `state`, `source`, license, rights, attribution text, a
  `required_disclaimer` shown verbatim, `revocable` and the revocation
  clause, and `enabled`, one switch per source.
- `lift_semantics`, how the source records an end: `explicit_record`
  (California's "None"), `explicit_field` (Missouri's dissipation date),
  `rolling_window` (none enabled; expiry is never an end), `none_recorded`
  (satellite estimates).
- `record_kind`: `official_advisory` or `satellite_estimate`. Only official
  advisories decide a status. Satellite estimates live in their own block
  per waterbody, are labeled "Satellite estimate (not an advisory)", explain
  abundance versus toxins and that small ponds are not covered, never alert
  and never end an advisory. The schema and the app's decoder refuse
  anything else.
- Only explicit non-personal fields are requested from any source.

Missouri, build decisions an owner should confirm (NOTES.md):

- The department publishes no definitions of its status codes. `advise` and
  `notice` are read as advisories; `dissap` with a dissipation date as an
  explicit end; `dissap` without one, `notthr`, `notver`, `report` and blank
  as deciding nothing. Each is shown with its code ("Advisory (advise)").
- A **closed case is not an end** without a dissipation date. 33 closed
  `advise` cases from past years therefore read "last posted <date>, no
  all-clear recorded".
- Missouri's layer names no county; its waters get a state page
  (`/state/mo/`) and ids like `mo-truman-lake`.
- The required disclaimer appears on every Missouri lake page, the Missouri
  page and the about page, and every page's footer links to it; the app
  shows it on Missouri lake screens and in About.

CyAN, build decisions:

- Matched to our waterbodies by state, exact normalized name and distance
  (at most max(15 km, 2 × √area)); a water without coordinates is never
  matched. 85 lakes on 2026-10-12, 57 with readings.
- A week the satellite could not see is dropped, never zero; a lake with no
  usable week says "no satellite reading on file", a gap and not a reading.
- Refreshed weekly (the composite's cadence), 2 s between requests, cached
  in `pipeline/data/cyan.json`. A failed refresh keeps the cache, and every
  reading shows its week.

## 0011 — robots.txt: missing is "no rules"; errors and redirects are off-limits (owner, 2026-10-12)

The owner's ruling, settled 2026-10-12:

- A **404 or missing robots.txt** counts as **no rules**. Missouri's host
  (`gis.dnr.mo.gov`) and CyAN's (`qed.epa.gov`) both answer 404, so both
  sources stay on.
- A **403, a 5xx, or a redirect to a page that is not a robots.txt** makes
  the host **off-limits** (ArcGIS's `servicesN.arcgis.com` 403 "Invalid
  URL" is the example). So does any other status, or no answer.
- A readable robots.txt is enforced for our User-Agent.

Every live run checks robots.txt first (`fetch.robots_allows`), before any
other request to that host. An off-limits host stops that source only;
California is never stopped by Missouri or CyAN. Tests cover each case,
including a redirect to a sign-in page (off-limits) and a redirect to
another robots.txt (read).

## 0012 — The name is Lake Notice; the domain is lakenotice.com (owner, 2026-10-21)

The working title Algae Alerts is retired. The product, the site and both
iOS display names are **Lake Notice**; the domain is **lakenotice.com** in
the member account created for this app (registered by the owner; nothing
in this repository registers or changes it). The name has no "bloom" and nothing in it or in the copy
that changes with it says "safe" or leads with fear (0002).

What changed: `SITE_NAME` and the default base URL in `site.py` (so titles,
the home-page structured data, `og:site_name`, the privacy and about copy
and the sitemap base follow), both `CFBundleDisplayName` values, the README,
the style sheet header and the listing draft. `pipeline/tests/test_naming.py`
fails if any of those names drifts from `SITE_NAME`.

What did not change, on purpose: the bundle ids, the widget id, the App Group,
the StoreKit product id, the URL scheme, the background task id and the
snapshot URL. They are set when the App Store record is created, and shipped
builds keep what they were built with, so changing them is a separate
owner-gated decision (proposed values: docs/DOMAIN.md). Internal code names
(the `AlgaeAlerts` Xcode project and targets, the `AlgaeCore` package, the
`caalgae` module, the repository name, the fetch User-Agent and the
analytics opt-out storage key) are not user-visible and stay.

Not done: a trademark screen (USPTO TESS) and an App Store name availability
check. Both are the owner's before the record is created.


## 0013 — Serve lakenotice.com from this repo; Missouri in 1.0 pending confirmation; affiliates with a second id (owner, 2026-10-22)

Four owner decisions made on 2026-10-22, recorded together.

**Hosting: design A.** lakenotice.com is served from this repository with
GitHub Pages and the existing `upload-pages-artifact` and `deploy-pages` jobs.
There is no second repository, no deploy key and no gh-pages branch (Trout
Truck needed that only because its app was already in review with a github.io
URL; no build of this app has shipped). The app's permanent URLs are therefore
`https://lakenotice.com/snapshot/v1.json` and `https://lakenotice.com/`
(`SnapshotEndpoint`), keyed to `SITE_DOMAIN` in `site.py` by
`tests/test_preflight_urls.py`. This supersedes the github.io URL in 0008.
Shipped builds keep their URL, so the domain must stay registered with
auto-renew on; if it ever lapses, the app falls back to its bundled snapshot
and says so. `publish.yml` now carries the daily schedule (`41 14 * * *`,
07:41 PDT, 06:41 PST after 2026-11-01) but a scheduled run is skipped while
`PAGES_ENABLED` is unset, so nothing is committed or published until the owner
sets that variable. `GA4_MEASUREMENT_ID` stays empty (a documented
placeholder) until the property exists.

**Missouri is in 1.0, pending her confirmation.** The status-code readings and
the closed-case rule are unchanged and are listed exactly as coded in
`docs/MISSOURI-READINGS.md`. The owner confirms them before the first publish;
if she does not, Missouri goes off by its one switch and 1.0 is California
only. Nothing was changed to those readings.

**Affiliates: yes, dog gear only, a second Amazon tracking id.** Plain Amazon
search links on lake pages (dog life jacket, portable dog water bottle,
post-swim rinse), `rel="sponsored nofollow noopener"`, Amazon's sentence "As an
Amazon Associate I earn from qualifying purchases.", and a sentence that the
links are Lake Notice's and not the Water Board's (Missouri DNR's on Missouri
pages), with a privacy-page section. Same design as Trout Truck 0029, with
three differences: the id is Lake Notice's own (never `trouttruck-20`) and is
an empty constant, `AMAZON_ASSOCIATE_TAG`, so the block and the privacy
paragraph render nothing until the owner creates the id and sets it; there is
no GA4 click event (the site sends none yet); and **never a home toxin test
kit**, because a negative strip is not safety and nothing on the site may imply
that a product makes water safe. The block's own text says no gear changes
what is in the water. `tests/test_site_affiliate.py` fails on test-kit or
safety wording in the categories or any built page. If the Associates account
has made fewer than 3 qualifying sales within 180 days of opening it, Amazon
closes it; the links then come out in one edit (delete `GEAR_CATEGORIES` and
the include in `water.html.jinja`).

**iOS submission waits for Trout Truck's App Review verdict**, as for the
other apps. Nothing to do now; the snapshot URL above is already final for
the first build.

## 0014 — GA4 is on, with Lake Notice's own property (2026-10-31)

The owner's portfolio rule (GA4 on every public site, 2026-09-17) applies
here, and the site has been live since 2026-10-22. Property 561648146
("Lake Notice", account ChelseaKR) was created through the Admin API with the
same settings as Trout Truck's: 14-month retention, Google signals off,
enhanced measurement without site search, form interactions or page changes,
and `purchase` as the only key event (the site sends no custom events yet).
`GA4_MEASUREMENT_ID` is `G-75YLGQKDHG`, so 0007's tag and privacy text are
now live. Nothing else in 0007 changes: the app collects nothing, and the tag
never loads under Global Privacy Control, Do Not Track or the footer opt-out.
Owner-only steps in the GA web interface, as for the other properties:
accept the Data Processing Terms, turn data sharing off, and leave
user-provided data collection off.

## 0015 — Announce new and changed pages to IndexNow after each deploy (2026-11-03)

ChatGPT search leans on Bing's index, and IndexNow is how a site tells Bing
(and the other participating engines) that a page is new or changed instead
of waiting for the next crawl. Trout Truck and Next Home Game have run this
since 2026-10-23, and both get HTTP 200 from the endpoint on their daily runs;
this is the same `indexnow.py`, renamed to this package.

`publish.yml` picks the pages in the build job, before the deploy replaces the
live site: a sitemap URL is announced when it is new or its `lastmod` differs
from the live `sitemap.xml`. Because a page's `lastmod` is its newest record
date, not the build date, an unchanged day announces nothing and sends no
request. Only https URLs on lakenotice.com, only built pages without a robots
noindex, at most 10,000 a request. A separate `indexnow` job submits the list
only after `deploy` succeeded. If the live sitemap cannot be read, nothing is
announced (unknown is not "everything changed"). The script exits 0 on any
problem and prints a notice, so there is no `continue-on-error` (the
standards ban it) and a refused ping never opens the publish-failure issue.

The key file at the site root is public by design: the protocol checks
ownership by fetching it. It lives in `templates/` and only a build for
lakenotice.com carries it. To stop announcing, delete the `indexnow` job and
the two IndexNow steps; nothing else depends on them.

## 0016 — Open water pages with a dated answer; index waters with five or more records (2026-11-03)

Measured on 2026-11-03: Trout Truck got 34 engaged ChatGPT visits from
2026-10-20 to 2026-11-03, nearly all landing on a water page. Lake Notice got
none, but its GA4 tag has only run since 2026-10-31 and the site went live
2026-10-22. ChatGPT search leans on Bing, and IndexNow (0015) merged the same
day. So most of the gap is age and Bing discovery, which no page change fixes.
Two page changes still help:

- **A dated answer first.** Every water page's first sentence now reads "As
  of the state's data dated <file date>, the records for <water> (<county>)
  show: <headline>". It is the status box's headline (0002 wording), with the
  water, the county and the date of the state's file, so it stays true when a
  search snippet or an assistant quotes it alone. A status that is not an
  advisory adds "That is not a finding that the water is safe now." in the
  same paragraph. Without a file date there is no "as of" clause. Trout
  Truck's pages open the same way ("last scheduled the week of <date>, as of
  the schedule check on <date>").
- **Five records make a page indexable.** The 2026-10-23 staging keeps a water
  page out of the index unless the state recorded an advisory in the last 24
  months, because one- and two-record pages were 85 to 92% template. That
  also hid waters people ask about (Lake Arrowhead, Shasta Lake, Lake Merced,
  Lake Natoma, Trinity Lake, two Salton Sea entries), whose pages carry 8 to
  89 records. A water is now also indexable with at least
  `INDEX_MIN_RECORDS = 5` state records, whatever their age. On the
  2026-11-03 snapshot that lists 118 more water pages (426 of 1,128 instead
  of 308) and leaves every one- to four-record page out. **Owner to confirm**:
  this widens the owner's 2026-10-23 staging rule. To undo, set the constant to a
  number no water reaches.

## 0017 — A spot is the state's coordinates; the headline leads with the highest level of the last 12 months, dated by its own posting; old advisories say their age (owner, 2026-11-03)

Found 2026-11-03: Lake Notice showed "Danger advisory, last posted Sep 24,
2026" for Lake Elsinore. Every record the state posted there that day was a
Caution, at the five city monitoring spots. The Danger came from bloom reports
filed between 2016 and 2022. The City of Lake Elsinore's Lake Watch page said
"no advisory at this time" (its update dated Aug 25, 2026; its lab table,
updated 9/17/26, shows microcystin at or below 0.33 ppb through 9/5/26). The
state's file is newer than that page and still records Caution. Two defects,
both fixed here:

- **The headline mixed two records.** `water_status` took the highest level
  from one spot and the newest date from any spot. 81 of 540 waters with an
  advisory in the 2026-11-03 snapshot showed a level that was not posted on
  the date shown. Now a headline's level and date always come from the same
  posting. When another spot has a newer posting at a lower level, the water
  page and the advisory lists add "The newest advisory posting here is
  lower: <level>, posted <date> at <n> reported spots. No all-clear
  recorded." The home page's "posted in the last 30 days" list and the
  newest-first order use the newest posting at any level, so a new lower
  posting is not hidden.
- **A reported spot was a bloom report id.** The state files the same
  monitoring spot under a new bloom report each season, with the same
  coordinates to six decimals (Lake Elsinore's "In open water near TMDL
  LE02" is report 3289 in 2022 and 3927 in 2023 to 2026). So a later "None"
  at that spot never reached the older report's Danger. California reports
  that share their latest coordinates are now one spot, named by the report
  with the newest record. That makes the "None" an explicit record at the
  same reported spot, which is what 0002 already requires. Measured on the
  2026-11-03 file: 2,740 reports become 2,185 spots; 280 spots hold more than
  one report, and where their landmarks differ they are spellings of one
  station ("Oaks Arm (DWR site CL-4)" and "(CL-04)"). Spots with an advisory
  fall from 1,322 to 1,088, and 15 waters move from an advisory to the
  state's latest record recommending none. Nothing is matched by name or by
  distance: two points a meter apart stay two spots, and a report without
  coordinates is its own spot. (Superseded in part by 0022, which also
  matches the same landmark within 25 m.) Missouri is not matched (its readings are
  owner-confirmed per case, 0013).

The state's data has no other end signal. Checked on the 2026-11-03 files:
`DisplayAdvisoryToMap` is "Yes" on all 14,519 rows; `Advisory_End_Date` is
filled on 326; `Case_Status` and `Case_End_Date` mark a staff folder, which
the data dictionary says "does not reflect the severity" and "can stay in
open status for a lengthy period". So silence still ends nothing (0002).
Instead, an advisory whose level was last posted more than `STALE_DAYS` (90)
before the state's file date now says so on its page: "That level was last
posted <date>, <age> before the state's data dated <date>, and the state has
not recorded an end to it. The state's newest record of any kind for <water>
is from <date>." On the 2026-11-03 file, under the headline rule below,
that is 370 of 479 California waters with an advisory.

**Which posting leads (owner, 2026-11-03).** The headline is the highest
advisory level posted in the 12 months before the state's file date
(`HEADLINE_WINDOW_MONTHS`, calendar months), at that level's own last posted
date. If no spot had an advisory posted in those 12 months, the headline is
the newest posting, with its own level, and the age sentence above. A
higher advisory posted before the window, with no all-clear, is never
dropped. It no longer leads, and the water page and the advisory lists name
it: "An older, higher advisory is also on file: <level>, last posted <date>
at <n> reported spots. No all-clear recorded." Lake Elsinore now leads with
"Caution advisory, last posted Sep 24, 2026", the level the state posted at
the five city spots that day. Its 2017 Danger reports are on the next line.
A Danger posted within the 12 months still leads over a newer Caution
(tested). On the 2026-11-03 file this changes 60 of 479 headlines from the
previous build of this decision. All 60 now lead with a lower, more recent
level, and each names the older, higher one.
The app reads the same fields, so its headline is the pipeline's.

**App parity (2026-11-04).** The app did not show the lines under the
headline. Its lists ordered and filed waters by the headline's date, and its
bundled snapshot, from the state's file dated 2026-10-09, still led Lake
Elsinore with "Danger advisory, last posted Sep 24, 2026". Now:

- The lake screen shows the website's notes in the website's order: the
  newer, lower posting, the older, higher advisory, and the age sentence,
  counted to the file date of the water's own state. With more than one spot
  under an advisory, it also explains how the headline is chosen. List rows
  carry the first two notes, as the website's advisory lists do.
- "Newest posting first" and "Posted in the last 30 days" use the newest
  posting at any level, as the website does.
- The sentences live in `AdvisoryNotes.swift` and mirror `wording.py`. The
  app cannot run the pipeline, so `pipeline/tests/test_ios_parity_fixture.py`
  builds `elsinore-parity.json` from the same Lake Elsinore records as
  `test_spots_and_age.py`: six cases, each with the pipeline's snapshot and
  the website's sentences. `AdvisoryParityTests` decodes each snapshot with
  the app's strict decoder and compares the app's sentences word for word.
  The pipeline test fails when the committed fixture is stale. Negative
  controls lower the old Dangers and move the file date across the 90-day
  line, and check that the lines change.
- The bundled snapshot is rebuilt from the state's file dated 2026-11-03,
  with `ios/scripts/sync-bundled-snapshot.sh`. On it, 120 of the waters in
  both copies have a different headline. Of 526 waters with an advisory, 60
  name an older, higher advisory, 2 a newer, lower posting, and 403 carry
  the age sentence.
- Alerts are unchanged. They still fire when the headline's kind or level
  changes. A higher advisory that leaves the 12-month window can lower a
  favorite's headline level, and the app then says "now a caution advisory".
  The wording says what the headline now shows. It does not say the higher
  advisory ended.

## 0018 — Search titles lead with the advisory and its date; descriptions carry the state's file date and the not-a-finding sentence (2026-11-03)

Measured in Search Console on 2026-11-03 (all data, 2026-10-22 to
2026-11-03): 666 impressions and 35 clicks (5.3%). Water pages had 559 of the
impressions and 28 of the clicks, across 152 pages, mostly at positions 5
to 9. Google showed only 13 queries; the rest are below its privacy
threshold. Five of the 13 ask "is <water> safe to swim in", and most of the
rest are "<water> algae". Every water title read "<water> toxic algae
advisories | Lake Notice", which is the same for a Danger posted today and a
Caution posted in 2019, so the result did not show the answer the searcher
came for.

- **An advisory's title leads with the water, the level and its date.**
  "Castaic Lake algae: Danger advisory, last posted Nov 3, 2026". The level
  and date are the headline's (0002 wording, 0017's headline posting), so a
  title never says more than the status box. To fit the 60-character limit,
  "toxic" goes first, then "last posted" ("Lake Berryessa algae: Caution
  advisory, Aug 28, 2026"), then "algae". The date is never dropped. A name
  too long for any of those keeps the plain title. On the 2026-11-03 snapshot,
  312 of 352 indexable water pages with an advisory get a dated title. The
  site name is left out of those titles to make room: `og:site_name` still
  names it, and Google shows the site name above the title.
- **Any other status keeps the plain title.** "The state's latest record
  recommends no advisory" must be followed by the not-a-finding sentence
  (0002), and a title has no room for both.
- **Descriptions match the page's first line (0016).** After the status, a
  description adds "From the state's data dated <file date>." when it fits
  (341 of 427 indexable pages). A status that is not an advisory now carries
  "That is not a finding that the water is safe now." in every candidate.
  Before, it was missing from all 603 such descriptions (75 of them
  indexable), because descriptions were built from the headline alone.
- **No "safe" question in titles.** A title such as "Is Lake Berryessa safe
  to swim?" would pass the copy guard, because the guard skips questions.
  It is not used. A title is often quoted without the description (browser
  tabs, shares, an assistant's citation), and on more than a thousand pages
  it would make "safe" the word the site is known for in search. **Owner to
  confirm** if the question form is wanted later. It would go in
  `site.water_title`, with the not-a-finding sentence in the description.

A test checks every built water page. Its title and description must pass
the copy guard. Any date in the title must appear in the page's first line.
A status that is not an advisory must keep the not-a-finding sentence in its
description. A negative control changes a title's date and puts a safety
claim in a description, and checks that both are reported. To undo, call
`water_title` without the status.

**County pages and the advisory list (2026-11-04).** Search Console, 2026-10-06
to 2026-11-02: the 33 county pages had 83 impressions and 3 clicks (3.6%) at
an average position of 6.2, against 4.5% for water pages. The advisory list
had 38 impressions and no clicks at 7.1. All of that predates the water
titles above, which went live on 2026-11-04. County titles still read
"<county> County lake toxic algae advisories | Lake Notice", the same for a
county with 25 waters under an advisory and one with none.

- **A county with an advisory says how many.** "Riverside County lake algae
  advisories: 25 of 40 waters". The count is the county index's "Latest
  record is an advisory" column. The description and the page's first line
  open with the same sentence, dated by the state's file: "25 of the 40
  waters in Riverside County have an advisory as their latest state record,
  in the state's data dated Nov 3, 2026." As in the water titles above, a
  counted title leaves out the site name, which `og:site_name` still carries.
- **A county with none keeps the plain title and description.** "0 of 2
  waters" in a title, with no room for the not-a-finding sentence, would read
  as an all-clear (0002). Two counties are like this on the 2026-11-03 file
  (Glenn, San Benito).
- **The advisory list's description counts each state it lists.** It listed 47
  Missouri waters while its description said California only. It now reads
  "479 California and 47 Missouri lakes and rivers whose latest state record
  is a toxic algae advisory, with its level and date." Its title is
  unchanged. Whether the title should name Missouri is the owner's call, with
  the home page title (2026-10-23 audit, finding 9).

A test checks every built county page against the snapshot: the count in
the title, the description and the first line, the file date, the copy
guard, and no count at all for a county with none. A negative control writes
a wrong count into one title and "0 of 2 waters" into another, and checks
that both are reported. To undo, have `county_title` return the plain title.

## 0019 — Missouri fails closed, and carries the department's own caveat (owner, 2026-10-30)

The department's layer description says it plans to retire this service. Before this decision, a failed
Missouri fetch kept the last records on the site with no limit, and a
malformed answer stopped the whole run, California included. Now:

- **Gone or changed: hidden at once.** HTTP 404 or 410, an ArcGIS error
  answer, an answer that is not a JSON object, a missing expected field,
  fewer than `MIN_ROWS` rows, or no case the pipeline can place raises
  `missouri.LayerUnavailable`. The run leaves Missouri out of the snapshot
  entirely: no Missouri waters, no /state/mo/, no Missouri source or file, no
  footer link. California publishes as usual. Missouri's history is kept, so
  a good read later brings it back.
- **A passing failure** (network error, another HTTP status, robots.txt
  unreadable) shows Missouri, with its read date, only while the last good
  read is at most `MO_STALE_AFTER_DAYS` (2) days old, then hides it.
- An absence is never shown as "no advisory": a hidden state has no pages.
- Missouri pages, /state/mo/ and About quote the department's HAB Reports Map
  disclaimer verbatim, with a link: "The data presented in the map should be
  used for general purposes only. The exact location, extent and toxicity of
  the reported bloom may not be accurate due to changing environmental
  conditions." (`sources.MO_MAP_CAVEAT`, read 2026-10-30.)

Tests: `pipeline/tests/test_missouri_fail_closed.py`, with the real layer as
the negative control.

Amended by 0024: a gone or changed layer now keeps Missouri's pages up in a
dated "data unavailable" mode instead of removing them. Switching the source
off (the State's revocation) still removes everything.

## 0020 — New York's yearly bloom summary, as history only, behind a switch (owner, 2026-11-02)

**The owner's decision, 2026-11-02:** add New York State DEC's yearly
summary of confirmed harmful algal blooms from data.ny.gov, under the
OPEN-NY Terms of Use. This **lifts the 2026-10-30 launch-readiness template
freeze for this one page type only** (the New York state page and New York
water pages, plus the lines that link to them). The freeze stands for every
other page family until mid-January. It also answers the state research's
ruling R3 (`_agent-tools/growth/lake-notice-state-expansion-2026-11-02.md`):
a yearly confirmed-bloom summary is a record kind Lake Notice shows, as
history and never as a status.

The rules she set, and how they are built:

- **History only.** Each row is a year in which DEC confirmed a bloom at a
  water, with the first and last report dates that year and the number of
  reports. The pages never call a row an advisory, never show a current
  status, never treat a last report as an end date or a year without a row
  as a finding, and never alert. New York data never enters the snapshot,
  `status.py` or the app (`newyork.py`, separate templates
  `ny_state.html.jinja` and `ny_water.html.jinja`). A copy test fails any
  New York sentence that uses advisory, current, ended, lifted, clear, safe
  and similar words without negating them.
- **Different wording from the California and Missouri pages.** The pages are
  titled "algae bloom history", carry no status box, dog section or
  "no all-clear" copy, and open with "What this record is, and what it is
  not". They link to DEC's notifications page for anything current.
- **No thin-page flood.** A New York page may be indexed only when DEC lists
  2 or more bloom years **or** 5 or more reports for that water
  (`newyork.MIN_YEARS`, `MIN_REPORTS`). Every other page is built with
  `noindex,follow`, no canonical, and is left out of the sitemap. Each page
  shows its years and report count. A test with a negative control proves a
  water one report short of the threshold is never indexed, and that the
  same check flips when the threshold is sabotaged.
- **Off by default, staged on.** `site.NY_HISTORY_ENABLED = False`, so merging
  publishes nothing. Turning it on with `NY_INDEX_LIMIT = 50` lets only the
  50 waters with the most reports be indexed; after about three weeks of
  Search Console, setting the limit to `None` lets all waters over the
  threshold be indexed. Turning the switch off removes the section, the nav
  link, the footer line and the about-page paragraph in one change.

Measured from the pinned file (read 2026-11-02, DEC's rows updated
2026-01-14, seasons 2019 to 2025):

- 1,371 rows, every one `bloom_type` "confirmed". The dataset defines S
  (suspicious), C (confirmed) and HT (confirmed with high toxins); a row with
  any value other than "confirmed" is held back and counted, never shown.
- 477 named waters get a page; 102 rows for "Unnamed Water" or "Unnamed
  Tributary ..." name no single water and get none (the state page says so).
- 284 waters meet the threshold (283 with 2 or more years, 180 with 5 or more
  reports). The research's estimate was 190 to 300.
- Identity: rows with the same name whose points lie within 1 mile are one
  water. DEC repeats a water's point exactly across years, even when it spells
  the counties differently (Seneca Lake: one point, four county spellings);
  same-name waters are miles apart (Suffolk County's two Long Ponds, 2.9 mi).
  The id is `ny-<name>`, plus the county when the name repeats in the state,
  plus the point when it repeats in one county. The refresh prints any id it
  removes, because that is a published page that would disappear.
- The research counted 555 "waters" by name and county text; that count split
  multi-county lakes by spelling and included unnamed rows.

### The terms, re-read 2026-11-02 (0004)

Source: "OPEN-NY Terms of Use", <https://data.ny.gov/dataset/OPEN-NY-Terms-Of-Use/77gx-ii52>,
the PDF `OPEN-NY_20Terms_20of_20Use.pdf` (SHA-256
`9437c849705d58df008f01fc23f404444becce6b86676adc3974f9160a4cb650`), headed
"LAST MODIFIED: March 8, 2013". Verbatim:

- Grant: "You are welcome to freely download and use this Content as long as
  you abide by these Terms of Use ("Terms of Use," or "Terms"), which
  constitute a contract between you and the State." And: "The State grants
  you a non-exclusive, revocable license to use the Content contained on this
  website in a manner consistent with the Terms of Use."
- No attribution or other condition: "The OPEN NY Terms of Service do not
  contain restrictions requiring members of the public to use attribution, to
  re-post the license terms with any re-uses of the data, to impose share-alike
  or technical restrictions, nor require the public to obtain pre-approval
  before re-use of the data." And: "So long as you are not doing anything
  malicious with NYS data, you may use it as you wish, subject to no other
  requirements." We credit DEC on every page anyway.
- Dataset-specific terms: "Other terms may apply generally to the OPEN-NY
  website, such as its Privacy Policy, or may be imposed specifically on
  specific Content." The dataset's metadata (`/api/views/95my-wijm.json`,
  read 2026-11-02) has no license (`license` null) and names
  "NYS Department of Environmental Conservation" as its attribution.
- **Revocation (flagged).** "The State may require you, by providing you with
  a notice in writing with which you shall comply, to cease using or
  displaying its Content if the State reasonably believes you are violating
  these Terms of Use, violating other terms posted on OPEN-NY and applicable to
  the website's Content, or that you are failing to abide by international,
  federal, state, or local laws, regulations, or ordinances." And: "The State
  reserves the right to modify, discontinue or remove any Content on OPEN-NY
  or terminate your access to OPEN-NY for any reason, without notice, at any
  time, and without liability to you. Upon termination, all licenses and other
  rights granted to you in these Terms of Use will immediately cease." If
  either happens, `NY_HISTORY_ENABLED = False` removes the section.
- **Indemnity (flagged).** "By accessing or using OPEN-NY, you represent and
  warrant that your activities are lawful in every jurisdiction where you
  access or use OPEN-NY. You agree to defend, indemnify and hold harmless the
  State, its officers, directors, employees and agents, and OPEN-NY's
  contributors, any entity jointly created by them, their respective
  affiliates and their respective directors, officers, employees, and agents
  from and against any and all claims, liabilities, damages, losses or
  expenses, including reasonable attorneys' fees and costs, arising out of or
  in any way connected with your access to or use of the OPEN-NY website, in
  reference to any claim however caused and on any theory of legal liability,
  whether in contract, strict liability, or tort, including negligence." This
  is the research's ruling R2. The decision above proceeds under these terms;
  the clause is recorded here so it is on file before the switch is turned on.
- Changes: "The State may modify these Terms of Use at any time and without
  notice other than posting its modifications on this webpage. Each time you
  use OPEN-NY you are required to review these Terms of Use for any changes
  since your last visit." The refresh plan below re-reads them each time.
- Shown on every New York page: "The State also does not vouch for the
  continued accuracy or currency of Content after it has been downloaded from
  OPEN-NY, nor the quality or accuracy of any analyses or re-uses of that
  Content."
- Read but judged not to apply (flagged for the owner): the "Public
  Participation" section says "You must not create accounts with OPEN-NY or
  access the site through unauthorized means, including but not limited to,
  by using an automated device, script, bot, spider, crawler or scraper." That
  section opens "To the extent OPEN-NY activates a module or forum for public
  comment or the uploading of Content ... the following provisions concerning
  acceptable use apply, and uploading such information indicates your
  agreement". Lake Notice uploads nothing, and the dataset's documented API
  (`/resource/`) is the access the portal publishes. The refresh is one
  person-run command a year.

### robots.txt, re-read 2026-11-02 (0011)

`https://data.ny.gov/robots.txt` answered HTTP 200 with `User-agent: *`,
`Crawl-delay: 1`, and disallow rules for browse, catalog, facet and page
queries plus `Disallow: /OData.svc/`, `Disallow: /api/odata/`,
`Disallow: /tiles/` and `Disallow: /api/collocate*`. The two paths the refresh
reads, `/api/views/95my-wijm.json` and `/resource/95my-wijm.json`, are
allowed. `fetch.guard_url` refuses the four API prefixes above.

### Fetching, the pin, and the refresh plan

- The daily publish **never fetches New York**. The site is built from the
  cache in `pipeline/data/ny/` (`95my-wijm.rows.json`, byte for byte as served,
  and `95my-wijm.meta.json`: URL, columns, DEC's update time, read time,
  SHA-256). `newyork.PINNED_SHA256` pins the rows. While the section is on,
  a cache that is missing, malformed, or does not match its sidecar or the
  pin **refuses the whole run**, before anything is written, so a refresh
  that forgets the pin cannot drop every `/state/ny/` page from a green
  publish (2026-11-05 branch review; it used to warn and build without New
  York). While it is off, the cache is never read and never stops a run.
- `uv run --frozen python -m caalgae.newyork` (from `pipeline/`) is the only
  thing that reads data.ny.gov: robots.txt first (a 403, 5xx, redirect or a
  disallow stops it), then at least 2 s, the metadata, at least 2 s (longer if
  robots.txt asks), the rows with nine named columns. Three requests in all.
- **Refresh plan.** DEC posts once a year ("Posting Frequency: Annually"; the
  2025 season posted 2026-01-14). From mid-January 2027, check the dataset
  page monthly until the 2026 season appears. Then: re-read the OPEN-NY terms
  (stop and re-review if "LAST MODIFIED" is not March 8, 2013) and
  robots.txt; run the refresh; review the printed counts, held-back rows and
  any REMOVED ids; update `PINNED_SHA256`, the counts in
  `tests/test_newyork.py` and this entry's numbers in the same commit; run
  `make verify`; open a PR. No scheduled job does this: a yearly file deserves
  a person reading the diff.

## 0021 — Turn New York's bloom history on, first stage: 50 indexable waters (prepared 2026-11-04)

The owner approved New York's yearly summary under the OPEN-NY terms on
2026-11-02 (0020), with the turn-on planned one to two weeks after
2026-11-03. This change flips `site.NY_HISTORY_ENABLED` to True and keeps
`NY_INDEX_LIMIT = 50`. Nothing else about the data changes.

**Re-checked 2026-11-04, before the flip (0004, 0011):**

- The terms are unchanged. The OPEN-NY Terms of Use dataset page still
  links the same PDF. It is byte for byte the file 0020 read (SHA-256
  `9437c849705d58df008f01fc23f404444becce6b86676adc3974f9160a4cb650`), headed
  "LAST MODIFIED: March 8, 2013". It still says "The State grants you a
  non-exclusive, revocable license to use the Content", "So long as you are
  not doing anything malicious with NYS data, you may use it as you wish,
  subject to no other requirements", and "You agree to defend, indemnify and
  hold harmless the State". The revocation and indemnity clauses the owner
  accepted are the same text.
- `https://data.ny.gov/robots.txt` answered 200 with the same rules as on
  2026-11-02 (`User-agent: *`, `Crawl-delay: 1`, and nothing that covers
  `/api/views/` or `/resource/`).
- `95my-wijm` metadata: rows updated 2026-01-14T17:36:47Z, the same as the
  pin; "Posting Frequency: Annually"; `license` null; attribution "NYS
  Department of Environmental Conservation". The live rows, read with the
  pinned query, are byte for byte the pinned file (SHA-256 `a9b3a0e8…3623`,
  1,371 rows, 2019 to 2025). So the 2026 season is not posted yet, as
  expected (0020's refresh plan starts mid-January 2027).
- `qtg2-hjth` (2012 to 2018) is reachable under the same robots.txt and
  terms. Its rows were last updated 2019-05-31, so it is a closed archive.
  It is **not used**. Its fields count weeks "on DEC notification list",
  which is closer to an advisory than 95my-wijm's report counts, and its
  bloom types include S (suspicious). Adding it would need its own owner
  decision on that wording.

**What the pages say, matched to 0016 to 0018 for this data type.** The
New York pages have no status box, so 0017's 12-month headline and age
line do not reach them (tested since 0020: no "no all-clear" copy). The
other rules carry over in New York's own words:

- **A dated first line (0016).** Every water page now opens "As of DEC's
  yearly summary dated Jan 14, 2026, the records for <water> (<counties>,
  New York) show a confirmed harmful algal bloom in <n> years (<first> to
  <last>), with <n> reports in all. That is history, not an advisory or a
  current status." The date is DEC's own "rows updated" time, which plays
  the role of the state's file date. The New York page opens the same way.
- **Titles lead with what the summary records, and its years (0018).**
  "Seneca Lake, NY: confirmed blooms in 7 years, 2019 to 2025". Shorter
  forms first add "algae" when it fits ("Adirondack Lake, NY algae: a
  confirmed bloom in 2025") or drop "confirmed" ("Allegheny Reservoir, NY:
  blooms in 3 years, 2020 to 2025"). A form such as "confirmed blooms 2020
  to 2025" is not used, because it reads as a bloom every year. The years
  in a title always appear in the first sentence. A title never says
  advisory, status, current, ended, lifted, clear or safe. On the pinned
  file: 453 of 477 titles carry their years, 23 names are too long and keep
  the plain "… NY bloom history | Lake Notice" title, and one name (50
  characters) is the whole title rather than being cut.
- **Descriptions carry the file date.** "Seneca Lake, NY: DEC's summary
  dated Jan 14, 2026 lists confirmed algal blooms in 7 years (2019 to
  2025), 732 reports. History, not a current status." 444 of 477 fit the
  dated form.

**Index effect, measured by building from the 2026-11-04 snapshot.** With
the switch off the sitemap lists 495 URLs. On, at the first stage, it lists
546: the New York page and the 50 waters with the most reports. Of those
50 titles, 47 carry their years. All 477 water pages are built; 427 are
`noindex,follow` with no canonical: 193 are under the thin-page threshold
and 234 are past the staged limit. No existing URL leaves the
sitemap and no existing lastmod changes, so the first deploy's IndexNow
announcement (0015) is the 51 new URLs. Every page gains the "New York
history" nav link and the footer credit line. At the second stage
(`NY_INDEX_LIMIT = None`) the sitemap would list 780 URLs: 284 New York
waters plus the New York page. That stage waits for about three weeks of
Search Console data on the first 50 (0020).

**Tests.** The default build now reads the pinned cache. Every one of the
477 real pages must pass the copy guard on its title, description and body.
The water's own name is left out of that check, because Clear Lake, Lake
Clear and Follensby Clear Pond are names, not findings. Each page must also
open with the dated line and repeat its title's years in the first
sentence. A negative control sabotages a real page five ways (a "clear"
finding after the name is removed, an "ended" in the description, a wrong
year in the title, an undated first line, no history sentence) and checks
each is reported. That control found a gap: the guard did not split a
sentence after a closing quotation mark, so a claim after a quote passed
because the quote contained "not". The guard now splits there. A second
control checks that the switched-off build's "no New York anywhere" test
finds New York in a default build. The California and Missouri page tests
(`test_site.py`, `test_lastmod_breadcrumb.py`) build with `--ny-history
off`, because they check pages against the snapshot alone.

**To undo:** set `NY_HISTORY_ENABLED = False`. One change removes every New
York page, link, sitemap URL and credit line (tested). If DEC or the State
sends a notice under the revocation clause, do that first.

## 0022 — The same landmark within 25 m is the same spot (owner, 2026-11-05)

This supersedes 0017's "nothing is matched by name or by distance" for
California. Found in the 2026-11-05 quality audit: the state adds a station
code to a landmark and moves its point a few meters, so a later "None"
landed on a new spot and the older advisory stayed open. At Lake Havasu,
"Skiers Island" (Danger, 2022-12-09, -114.31938) and "Skiers Island
(714SKIERS)" (None, 2026-04-16, -114.31936) are about 2 m apart.

- Two reports of a coordinate-matched source (`SPOT_BY_COORDINATES`, still
  California only) are one spot when their latest landmarks are the same
  after removing one trailing parenthetical, case and extra spacing
  (`snapshot.landmark_key`), and their latest coordinates are within
  `SAME_NAME_METERS` (25) of each other. Sharing coordinates still joins
  reports too (0017). Each link meets one of the two tests, so a chain of
  same-name links can span more than 25 m (Four Island Lake's "Bear Valley
  Springs" reports span 34 m).
- Two different station codes are never joined by name. When both
  landmarks carry a trailing parenthetical, they match only if the codes are
  the same after case and spacing are set aside (`snapshot.landmark_code`),
  so Lake Havasu's "Nuwuvi Park (714NVWVVI-01)" and "(714NVWVVI-02)" stay
  two stations if the state ever moves one of them. An uncoded landmark
  still matches a coded one, nearest pair first, and a link that would put
  two different codes on one spot is refused, so a "None" at one station
  can never end an advisory at the other through an uncoded report between
  them. Shared coordinates still join any codes (0017's "CL-4" and
  "CL-04"). Added after the 2026-11-05 branch review; on the 2026-11-03
  file it changes no spot, because the two Nuwuvi Park stations share
  coordinates today.
- Different names are never matched by distance alone. McLeod Lake's
  "Morelli Park Boat Launch" (Danger, 2020) stays apart from "Morelli Park
  (MP)" (None, 2026), about 4 m away. A landmark that is only a code, such as
  "(MP)", matches nothing. Reports without coordinates and Missouri are not
  matched (0013).
- The spot is still named by the report with the newest record, and a later
  "None" there is an explicit record at the same spot (0002). Silence still
  ends nothing.

Measured on `pipeline/data/history.json` (California file dated
2026-11-03): spots fall from 2,450 to 2,425 and spots with an open advisory
from 1,138 to 1,129. 9 waters change. Four Island Lake moves from "Caution
advisory, last posted Aug 8, 2022" to the state's latest record
recommending none. Antelope Creek, East Creek, H.V. Eastman Lake, Lake
Havasu, Lake Tahoe, McKinley Park, Mormon Slough and Pyramid Lake keep their
headline and count one fewer spot under an advisory. Counted the audit's
way (an open spot with a later "None" within 25 m, whatever its name), 22
waters qualified on this file before and 15 after; those 15 have a
differently named "None" nearby, such as McLeod Lake, and are left to the
wording in batch LN-B.

Tests: `pipeline/tests/test_same_name_spots.py`, with the audit's Lake
Havasu, Antelope Creek and Four Island Lake records, and McLeod Lake and a
33 m move as negative controls, plus two Nuwuvi Park station codes 20 m
apart, an uncoded report between them, and the same-code control.

## 0024 — A state whose data stops is shown as "data unavailable since <date>", not hidden; the publish is guarded (owner, 2026-11-05)

Accepted 2026-11-05 by Chelsea, as the plan recommended (decision 1b, with the deploy guard of 2a).

Amends 0019. The department plans to retire Missouri's layer, and the risk
is not a sudden 404 but an old layer that keeps answering with frozen data.
Hiding Missouri also made its 41 sitemap URLs (its best performers in
Search Console) return 404. Now three situations get three answers
(growth/ln-expansion-plan-2026-11-05.md, section 1.3):

- **A passing failure** (timeout, 5xx, robots.txt unreadable): as before,
  shown with its read date while the last good read is at most 2 days old.
  After that it becomes unavailable (below), never hidden.
- **Unavailable.** Any of:
  - gone or changed: HTTP 404 or 410, an ArcGIS error, missing fields,
    fewer than 50 rows, no placeable case (0019's checks);
  - partial: an answer that would withdraw more than 5% of Missouri's
    records (it used to stop California too; source-outage audit finding 8);
  - frozen: from May 15 to Oct 15, no record dated within 30 days of the
    run. The worst measured in-season gap was 22 days (21 in 2024, 22 in
    2025, 18 in 2026). Out of season nothing is checked. In 2018 and 2020 the
    first report came after mid-May, so a quiet May can read as frozen; that
    errs toward "unavailable", which claims nothing;
  - superseded: the department's public viewer ("HAB Public Viewer PROD",
    www.arcgis.com item 96d87e1fda0e445b90c23ce52d67a2d9, its `/data` JSON)
    no longer names `HAB_SUBMIT_POINTS/MapServer/6` among its data sources.
    One request per run, after robots.txt (www.arcgis.com, read 2026-11-05:
    `User-agent: *` with no Disallow). On 2026-11-05 it names layers 4 to 8
    of that service. A failed or unreadable viewer read only warns: only a
    readable list of data sources without the layer proves the move. The
    item's `licenseInfo` is a no-warranty statement and adds no condition;
    the viewer's data is never shown, only checked.

  Every Missouri page stays built and answers 200. A notice leads each one:
  "Missouri's harmful algal bloom data stopped reaching Lake Notice on
  <since>, so Lake Notice can't show this water's current status. The records
  below are the last ones it read, on <last read>." It links the
  department's HAB Reports Map. The status box says "No current status:
  Missouri's data unavailable since <since>." and carries no level, no "No
  all-clear recorded" and no "recommends no advisory". The history table is
  headed "Records read before <since>". The State's disclaimer and the
  department's caveat stay. Titles read "<Lake> algae: Missouri data
  unavailable since <since>" (the name is cut before the date is). Missouri
  waters leave the advisory lists and the home page says why. For 30 days
  the pages stay indexed and in the sitemap; after that they carry
  `noindex,follow` and leave the sitemap, still built. `since` is the first
  run that found the outage, kept in history.json (`outages`) until a good
  read clears it. A passing failure during an outage never brings the old
  data back.

  The snapshot carries a `state_status` entry per state (`live`,
  `stale_dated` or `unavailable`, with `since`, `reason`, `last_read` and the
  map link). The app shows the same notice, reads every status of that
  state as undetermined with no current claim, lists none as an advisory,
  sends no alert, and keeps each favorite's alert baseline, so the state's
  return announces only a real change.
- **Revoked** (`MO_DNR_HAB.enabled = False`): as 0019, no Missouri content.

**Publish guard.** `publish.yml` runs `caalgae.publish_guard` after the build
and before the history commit and the Pages upload. It compares the built
sitemap with the live one per state and fails the run, keeping yesterday's
site, when a state loses all its sitemap URLs or more than 20% of them,
unless its source is switched off, the owner names it in the
`allow_page_drop` dispatch input, or it is unavailable past its 30 indexed
days with every dropped page still built. The failure issue names the
state and the counts. A state in its unavailable mode deploys and opens or
updates the issue "publish: a state's data is unavailable" the same day.
No live sitemap (first deploy, 404, unreachable) means nothing live to
protect, and the run says so.

Tests: `pipeline/tests/test_data_unavailable.py`,
`pipeline/tests/test_publish_guard.py`, the updated
`test_missouri_fail_closed.py` and `test_publish_workflow.py`, and
`ios/AlgaeCore/Tests/AlgaeCoreTests/UnavailableStateTests.swift`. Negative
controls: the real layer and the real viewer are live; a live build has no
outage wording; an unchanged build passes the guard; a live snapshot alerts
and lists Missouri advisories.

## 0025 — Spanish groundwork: a catalog with a status per string, a review gate, and the levels page, all switched off (2026-11-05)

Plan: `_agent-tools/growth/spanish-pages-plan-tt-ln-2026-11-05.md`, its first
PR. Nothing changes on the live site: `i18n.LEVELS_ENABLED` and
`i18n.ES_ENABLED` are both False, so a build writes neither /levels/ nor
/es/niveles/, and the sitemap is unchanged.

- **One catalog, one status per string.** `pipeline/src/caalgae/locales/es.json`
  holds the Spanish strings and `es.status.json` their status: `state` (the
  state's own words, with URL, date read and a SHA-256 of the text),
  `reviewed` (reviewer initials and date), `same` (correct Spanish is
  identical to English) or `draft`. `safety: true` marks safety strings: the
  level names, guidance and sign wording, after-contact and dog advice, the
  not-a-finding sentence, the not-medical-advice line and the attribution
  caveats. The English catalog (`i18n.EN`) reads `wording.py` and
  `sources.py`, so English output is unchanged and the existing tests still
  pin it.
- **Always checked (`make i18n`, inside `make verify`).** Key and placeholder
  parity; a Spanish string identical to English must be `same` or `draft`;
  a stale `same` fails; a safety string cannot be `same`; a `state` string
  must still hash to its quote; a `reviewed` string needs its sign-off; a
  paste placeholder can only be `draft`. Ported from Family Greenhouse's
  `check-i18n-catalogs.mjs` (`todo` and `intentionallyEqual`).
- **Checked when Spanish is on, in `make i18n` and in the build itself.** No
  safety string may be `draft`, no placeholder may remain, and the Spanish
  copy guard applies: never "seguro" and its forms, "sin peligro", "apta
  para nadar", "limpia" or "libre de toxinas"; "Peligro" only as the level's
  label. A missing string raises during rendering; there is no English
  fallback.
- **Rendered-page check.** After the Spanish page is written, every /es/
  page must have `lang="es"` (every other page `lang="en"`) and no run of
  four or more English words, and English stopwords must be at most 3% of its
  words. It reads visible text, the title, `alt`, `aria-label`, `title`
  attributes, the description and script string literals. Proper nouns come
  from the snapshot (waters, counties, spots, agencies, programs), never a
  hand list. The English vocabulary is read from the English catalog only,
  so English pasted into es.json cannot teach the check its own words.
- **The state's Spanish sign wording is not in the repo yet.** The four
  `level.*.sign` strings are marked placeholders (`⟦PEGAR…`). The host,
  mywaterquality.ca.gov, admits only Googlebot, so no script fetched it.
  **Owner:** open the sign PDFs in a browser, paste each level's Spanish text,
  then set its status to `state` with `url`, `read_on` and `sha256` (`cd
  pipeline && uv run python -m caalgae.i18n --hash KEY`). The Spanish level
  names (Precaución, Advertencia, Peligro) are drafts too, seen only in a
  search-index summary; they become `state` from the same paste.
- **All Spanish safety strings are drafts.** No reviewer has signed off.
  Turning Spanish on today fails with 26 problems (22 draft safety strings,
  4 placeholders), by design.
- **Known blocker before turn-on:** `_ga4.html.jinja`'s opt-out messages are
  English, and GA4 is on in production, so the rendered-page check fails the
  Spanish page until they come from the catalog. A test records it.
- **No hreflang yet.** It waits until after the ~2026-11-25 read of the dated
  titles (0018). The twins link to each other with a plain "En español" /
  "In English" link only when both are built.
- The levels pages use `_base_i18n.html.jinja`, a copy of `base.html.jinja`
  with every string from the catalog. A test checks that the English header
  and footer are byte-for-byte those of the dogs page, so the copy cannot
  drift without failing.

Four sabotages each turn the gate red, and each test checks the sabotage
applied first: English in a safety key, one word changed in a state quote,
an English sentence hard-coded in the Spanish template (the rendered bytes
differ), and a safety claim ("segura") in a reviewed string. Tests:
`pipeline/tests/test_i18n_catalog.py`, `pipeline/tests/test_es_pages.py`. To
undo: delete `i18n.py`, `levels.py`, `locales/`, the two templates, the
`i18n` make target and the one `levels.build` line in `site.py`.

## 0027 — A short or reshaped California file cannot flip a live advisory (2026-11-05)

The source-outage audit of 2026-11-05 cut the newest 5% of advisory rows
from the real history. The old guard, which refused only above 5% withdrawn
(713 of 14,270 records), let it through, and 10 waters flipped from a current
advisory to "The state's latest record ... recommends no advisory"; 37 more
went to undetermined. The next good file would bring the advisories back and
the app would alert again. In 15 runs the state withdrew 0 records. Now:

- **At most 25 withdrawn records per California run** (`MAX_REMOVED_RECORDS`),
  whatever the fraction. The 5% limit stays, for every source.
- **No withdrawal of a report's current advisory** (the report's latest
  deciding record, when that record is an advisory). Withdrawing it would let
  an older record speak for the spot, so the run is refused.
- **The quarantine may grow by at most 25 rows per run** (`cli.MAX_QUARANTINE_GROWTH`).
  It held at exactly 249 for 15 runs; a date-format change would quarantine
  every new posting silently.
- **A refused run publishes nothing**, so yesterday's site stays live and the
  publish-failure issue opens. After reading the state's file, the owner can
  let it through with the publish workflow's `accept_ca_edits` input
  (`caalgae --accept-ca-edits`).
- **A level this pipeline does not recognize decides its spot as undetermined.**
  A blank level still decides nothing. A non-blank level with no mapping (a
  new spelling such as "Danger - Closure") used to decide nothing too, so an
  older "None" showed through it. Now the spot, and the water unless another
  spot has an advisory, reads "The state's latest record says “Danger -
  Closure”, a level this site does not recognize, so it cannot say what
  applies. Check the official map." A later "None" still ends it. The run
  warns with the levels it could not read. The same rule covers a Missouri
  status code outside the known list. Today's data has no such level (all
  57 California `unknown` records and all 80 Missouri ones are blank), so
  nothing on the site changes.

Tests: `pipeline/tests/test_ca_short_file.py`, run on the committed
history.json. Negative controls: the real file passes unchanged; the 4% cut
passes the old guard alone (the sabotage applies) and is refused by the new
one; 25 withdrawals pass and 26 are refused; a superseded advisory can be
withdrawn; a blank level after "None" still reads as lifted.

## 0029 — Dog-gear links on the dogs page only, with Lake Notice's own Associates id (owner, 2026-10-30; id 2026-11-05)

The owner approved a small Amazon Associates section on the Dogs and algae
page (`/dogs/`) and nowhere else. This narrows the affiliate part of 0013,
which put the gear block on every lake page (off until a tag was set). The
block comes off lake pages because Trout Truck lost most of its search
impressions within two days of shipping an identical affiliate block on about
1,900 pages.

- **Placement.** Only `dogs.html.jinja` includes `_gear.html.jinja`, and
  `site.py` passes gear links to the dogs page alone. Lake, county, state,
  advisories, home and every other page carry no Amazon link.
  `tests/test_site_affiliate.py` checks this, with a negative control that a
  tagged link put into a lake page is caught.
- **Tracking id.** `AMAZON_ASSOCIATE_TAG` is Lake Notice's own Associates
  id, `lakenotice-20`, which the owner created on 2026-11-05. It is never
  Trout Truck's `trouttruck-20`, as 0013 says. Before this ships, the owner
  adds lakenotice.com to the Associates account's website list.
- **Items.** Five generic Amazon searches, each tied to the page's own advice:
  a water bottle and a collapsible bowl (bring fresh drinking water so the dog
  does not drink from the lake), a long leash (keep the dog out of the water
  and away from scum), a rinse bottle and a towel (rinse the dog with fresh
  water if it goes in, and do not let it lick its coat). No life jacket: it
  ties to no algae advice. Search links, not products, so nothing goes stale.
- **Unchanged from 0013.** Plain links with `rel="sponsored nofollow noopener"`,
  no Amazon script, image or price, Amazon's sentence and the "Affiliate links"
  label before the links, the non-endorsement sentence naming both agencies, a
  privacy-page section, no click tracking, never in the iOS app, never a home
  toxin test kit, and the block's own text says no gear changes what is in the
  water. Removal is one edit: set the tag to `""`.

## 0030 — The app reads as Lake Notice's own, and a new state or a changed CyAN answer never stops updates (2026-11-05)

The launch review of 2026-11-05 (§5) found that the app shared a reviewer's
view of Trout Truck, which drew a second 4.3(a) on 2026-11-03: the same
purchase name, the same listing headings and the same last caption. Its §3
also found two ways a shipped app could stop updating. This changes only
what is true of the product; nothing was invented to look different.

- **The purchase is "Lake Alerts & Widget"** (reference name "Lake Notice
  Alerts"), named for what it adds, in `Configuration.storekit`,
  `FreeTier.purchaseName` (the unlock screen's title and About's section),
  LISTING.md and REVIEW-NOTES.md. **The product id stays
  `net.chelseakr.algaealerts.fullaccess`**; the name is a display string and
  an id cannot change once the record exists. The owner can still pick
  another name (launch review decision 3); the copy test then says every
  place to change.
- **The listing is written around what an algae advisory is**: sign levels,
  the dogs section, after-contact steps, spot-by-spot history, the separately
  labeled satellite estimate and "never an all-clear". It has none of Trout
  Truck's headings, and caption 6 is "Your favorite lakes stay on your
  iPhone." instead of Trout Truck's "No account. No tracking." Alert timing
  is "when iOS lets the app check, often within a day, not real time" in the
  listing, the unlock screen and Favorites.
- **The Review Notes open with a factual "what Lake Notice is" paragraph**,
  fill in the name and snapshot URL, say "any state or federal agency", mark
  every Missouri sentence for removal if Missouri is off at submission, and
  stay under 4,000 characters.
- **A state this build does not know is left out of the snapshot before it
  is decoded**: its waterbodies, sources, source files and state-status
  entries, and any source in a record kind this build does not know. A New
  York water in a new `bloom_history` kind used to make the whole file
  undecodable, so shipped apps would have kept old California data forever.
  States the build knows are still decoded strictly: an unknown status or
  record kind on a California or Missouri water still refuses the file and
  keeps the copy on the phone. A new state reaches the app only in a build
  that knows it. A file with nothing unknown is decoded from its own bytes.
- **A CyAN answer in another shape is a failed refresh.** The list and each
  weekly series are shape-checked (`cyan.ShapeError`, a `FetchError`), so a
  renamed or mistyped field keeps the cache and the run goes on, instead of a
  `KeyError` stopping every run (source-outage audit finding 8). A lake in
  another state is never checked.

Tests: `ios/AlgaeCore/Tests/AlgaeCoreTests/UnknownStateTests.swift`,
`PurchaseNameTests.swift`, `pipeline/tests/test_cyan_shape.py`,
`pipeline/tests/test_app_store_copy.py`. Negative controls: the injected New
York file fails a plain decode (the sabotage applies) and fails the tests
with the filter removed; the same water labeled California is refused; the
old CyAN read raises `KeyError` on the renamed field; Trout Truck's heading
or the old display name put back turns the copy test red.

Not done here, and why: the widget's "Part of full access." line waits for
PR #32, which rewrites that block; Missouri's data-unavailable mode and its
`HistoryError` catch are PR #31 (DECISIONS 0024); the icon, screenshots, the
name check, the subtitle and category picks, the Missouri readings and the
level summaries are the owner's.

## 0031 — App words come from the snapshot, an alert is delivered once, and the support page says the app is not out (2026-11-05)

The launch review of 2026-11-05 left six small app items after PR #36
(DECISIONS 0030). Each one is a place where the app could say something the
data on the phone does not support.

- **"The last 30 days" counts back from the snapshot's run date**, not from
  this iPhone's today. On an old copy (no network, a stuck source) the list
  used to say "None posted in the last 30 days" about advisories posted the
  week the file was made. The header now names the date: "Posted in the 30
  days to Oct 12, 2026". `AppEnvironment.today` is removed so nothing else
  measures from the device's calendar.
- **The "All lakes" footer no longer says a missing lake has "no advisory
  records at all".** Some waters have only rows Lake Notice cannot read, and a
  state's layer can drop a lake. It now reads "As of the data dated <run
  date>, a lake missing from this list has no advisory record Lake Notice
  could read. Most lakes are never tested."
- **About and the introduction name the states the snapshot carries
  waters for**, in source order, with each state's first record year taken
  from its records. A state whose source is listed but whose waters are gone
  is not named. A state with no dated record gets no year, never a made-up
  one. With no snapshot, no state is named.
- **An alert key is delivered at most once.** The key is the water, the
  level and the posted date (`PlannedNotification.id`). Keys iOS accepted are
  saved to `delivered-alerts.json`, so a relaunch or a new snapshot cannot
  repeat one. The baseline alone could: a short file that drops an advisory
  and a later file that brings it back reads as "no advisory, then
  advisory". A new posting date or a new level is a new key and still
  alerts. A missing or corrupt file reads as empty, which can only allow an
  alert, never hide a new one. Keys are kept; a few favorites make a few
  keys a year.
- **`processing` is removed from `UIBackgroundModes`.** The app registers
  one `BGAppRefreshTask` and no `BGProcessingTask`, so `fetch` is the only
  mode in use. An unused mode invites an App Review question.
- **The PrivacyInfo comment no longer points to `docs/APP-STORE.md`**, which
  does not exist. It names Xcode's archive privacy report instead.
- **The support page's app section says only what is true today**: the
  iPhone app is not released, cannot be downloaded or bought, and the website
  does not need it. The old "When do app alerts arrive?" answer, which
  promised timing for an app nobody can install, is gone, and so is "help
  with the iPhone app" in the page description. Restore, refund and alert
  help is written when the app is released.

Tests: `ios/AlgaeCore/Tests/AlgaeCoreTests/CoverageCopyTests.swift`,
`DeliveredAlertsTests.swift`, `pipeline/tests/test_support_app_section.py`,
and the UI test's header check. Negative controls: measuring from the
device's today turns the stale-snapshot test red; an empty delivered set
turns the drop-and-return, relaunch and one-key tests red.

## 0032 — The home and /advisories/ titles name Missouri while its data is live (owner, 2026-11-05)

The search read of 2026-11-05 (growth/ln-search-demand-2026-11-05.md) found
/advisories/ the site's top page by impressions (45, 0 clicks, position about
7) and the home page fourth (29, 0 clicks). Both titles said "California"
while /advisories/ listed 47 Missouri waters. The owner chose option C1:
name Missouri in both now. They are not water pages, so the dated-title read
of water pages (~2026-11-25) is not disturbed.

- **States come from the build's data, never a constant.** The home page
  names every state in `STATE_NAMES` with waters in the snapshot and its
  source listed (`SiteBuilder.live_states`, the same test `state_pages`
  uses). /advisories/ names the states its own table lists, the states its
  description already counts. A Missouri source that is dropped or empty
  drops the word, and a Missouri with no open advisory is not named on
  /advisories/.
- **California alone keeps the launch titles byte for byte**: "California
  lake toxic algae advisories by date | Lake Notice" and "All California
  toxic algae advisories on file | Lake Notice".
- **With Missouri**: "California and Missouri toxic algae advisories by date"
  and "All California and Missouri toxic algae advisories on file". Neither
  fits 60 characters with "| Lake Notice", so the site name is left out, as
  0018 does for dated water titles; `og:site_name` still names the site.
- **The home description names the same states.** "Since 2016" is
  California's span, so with another state it says "history" with no year.
- **Not changed**: every water, county and state page title and
  description. New York (#17, #34) is not in `STATE_NAMES`, so turning it on
  does not change these titles; adding it there would.

Tests: `pipeline/tests/test_state_titles.py`, both a California-only build
and the California-and-Missouri fixture build.

## 0036 — The app takes the website's identity, with worded empty states, sharing, support and a rare review ask (2026-11-05)

The website's identity (0035, docs/DESIGN.md) is a notice posted at the
shore. The app now follows it instead of the system default, and fills the
gaps the 2026-11-05 parity audit found. The owner chose that each app takes
its own site's identity, with no shared kit across apps (audit D1).

- **Colors are the site's tokens**, as asset-catalog colors with light and
  dark variants: Paper, Surface, Ink, Muted, Brand, Rule and AccentColor
  (the link indigo), and a band and band ink for each sign. Lists sit on
  the paper, rows on the surface. The old amber and teal are gone. No color
  is green. `AppTests` checks every text token on both backgrounds and each
  band's ink on its band at 4.5:1 in both appearances, and that no identity
  color reads as green.
- **A lake's status is drawn as its posted notice**: a band in the sign's
  color with the level's words in capitals and one to three square rank
  marks (Caution 1, Warning 2, Danger 3), a rule, then the record. Danger
  has the heavier edge. Missouri's levels and California's algal-mat signs
  get the slate band and no marks. Anything that is not an advisory says
  "Latest state record" on a neutral band with a dashed edge, never a level
  word or color. List rows, reported spots and Favorites carry the same band
  as a chip; history rows carry a swatch beside the level's words.
  VoiceOver reads the band as words and rank ("Danger advisory sign, 3 of 3
  marks"; "Latest state record, not an advisory"). `NoticeBand` in AlgaeCore
  holds the mapping and is tested.
- **Signage-style type from system fonts**: the system sans at condensed
  width for navigation titles, section titles (under a short brand rule,
  the site's depth mark), a lake's name and the bands. It scales with
  Dynamic Type; at accessibility sizes the rank marks move under the words.
- **The mark** (the sign board on a post, from the site's `mark.svg`) is
  drawn in code in the introduction, About and the empty screens. The app
  icon is not changed here; that is an owner item.
- **Empty, error and offline screens are worded**, each on a blank notice
  board: no records on the phone (with "Try again"), offline with no records,
  a search with no match ("That is not a finding about the water"), no saved
  lakes (with "Browse lakes"), and a lake gone from the file. Offline with
  data, the list stays and says it is showing the copy already on the phone,
  with the data file's date. `NWPathMonitor` only reports offline; it never
  hides data.
- **Share a lake**: the lake screen shares the lake's page on lakenotice.com
  (the same URL as "This lake on the website"), with a message about what
  the page holds, never what the water is like. About can share the site.
- **Support**: About's "Email support" row names the address and opens mail
  to chelsea@chelseakr.com with "Lake Notice for iPhone <version>" as the
  subject. With no version in the bundle, the subject leaves it out.
- **The review ask follows Apple's rules**: never at launch and never from a
  button. The app may call `requestReview` only when someone leaves a lake
  screen where they just saved that lake, keeps at least two saved lakes,
  has opened the app on three different days, and has not been asked in this
  version. iOS still decides whether to show anything. The day count uses
  the phone's calendar because it measures use, not data; nothing about
  advisories is measured from it (0031 still holds). It never runs under UI
  tests.

Tests: `PostedNoticeTests` (AlgaeCore), `AppTests` (contrast, no green, the
review rule under UI tests, day counting), and UI tests for the sign and
share, the no-match search, empty Favorites, the offline and no-data screens,
offline with data, and the support row. The accessibility audit now also
covers the offline no-data screen and empty Favorites, at the default size
and at AX5.

## 0037 — Oregon and Kansas readers are built and tested behind flags that are off (2026-11-06)

(0020 to 0036 are on main or on open branches, so this is the next free
number.)

Each state has a reader, `pipeline/src/caalgae/oregon.py` and
`pipeline/src/caalgae/kansas.py`, registered in `pipeline/src/caalgae/flagged.py`.
Neither agency publishes a reuse grant, so under 0004 each license is
recorded as `unknown` and the data is not used. Permission was asked in
writing on 2026-11-02 (OHA and KDHE). Nothing goes live until an agency says
yes in writing; this is the same pattern as Trout Truck's DECISIONS 0055.

- **The flags.** `LN_ENABLE_OREGON` and `LN_ENABLE_KANSAS`, environment
  variables: `1` is on; unset, empty and `0` are off; anything else refuses
  the run before anything is written. No workflow sets either (a test reads
  every workflow).
- **Off means identical.** With both off, the run fetches nothing, prints
  nothing and writes nothing for these states. A default build of the
  fixture site, snapshot and history is byte-identical whether or not the
  readers are registered, and with both flags set to `0`
  (`pipeline/tests/test_flagged_states.py`).
- **On is review only.** A flag that is on reads that state (or the fixture
  given with `--state-fixture XX=path`) and writes
  `--state-review-out/<xx>-review.json`, which may not sit inside the site.
  Its records never enter the history, snapshot, site or app; a test builds
  with both flags on and checks the published files are the default's byte
  for byte. A fixture given while its flag is off refuses the run. Wiring a
  state into pages and the app is a later change, after the written yes.
- **Sources are off and unlisted.** `sources.OR_OHA_HAB` and
  `sources.KS_KDHE_HAB` have `enabled=False`, no attribution, and are kept
  out of `SOURCES`, so the snapshot never names them.
- **The agency's own words, no level invented.** Every advisory keeps the
  agency's status as its `level`, under the `other_advisory` tier, never
  California's caution, warning or danger.
  - **Oregon (OHA).** One request to the SharePoint list behind the
    advisories page, for nine named fields; robots.txt read first.
    "Advisory in effect", "Precaution in effect", "Permanent Advisory" and
    the legend's "Advisory downgraded to precaution" are advisories; "…has
    been lifted" is an explicit end. Markup is stripped from the stretch
    description and toxin notes. The list has no coordinates, so none is
    given. A water leaving the list is never read as an end. A row with no
    date, more than one status, or not shown on OHA's page is quarantined.
    A record's id carries its status and date, because OHA edits one item
    per water in place.
  - **Kansas (KDHE).** Layer 6 of KDHE's own MapServer, every status since
    2010, read in 2,000-row pages 5 s apart, with robots.txt (404, no rules)
    read first. Watch, Warning, Advisory and Lake Hazard are advisories;
    Lifted is an explicit end. "Historical Pending" and "MIXED" decide
    nothing until KDHE says what they mean (asked 11-02). A read that stops
    before the layer's last row, misses a field or has under 1,000 rows is
    refused whole.
  - **Any other status** is undetermined (0027), never an end.
- **Fixtures are invented.** `pipeline/tests/fixtures/states-invented/` is
  written by hand in each agency's format with invented waters ("Invented
  Lake", "INVENTED LAKE A"); no agency data is committed.
- **Development reads, 2026-11-06.** Each host's robots.txt, then the Kansas
  layer metadata, a status count, a four-row sample and one full read (two
  pages); one read of the Oregon list. Against them: Oregon gave 56 records
  from 57 rows (one "Permanent Advisory" row has no date and is
  quarantined); Kansas gave 3,105 records from 3,116 rows (11 repeated
  status rows). Nothing from these reads is committed.
- **Turning one on** is the owner's call after the agency's yes: record the
  grant's text in docs/LICENSES-AND-ATTRIBUTION.md, then a separate change
  adds the state to `SOURCES`, `site.STATE_NAMES`, the snapshot and the app.

Open questions for the agencies, before any page: what a lifted Oregon
row's date records (the lift, or the last change), whether Oregon has
coordinates Lake Notice may use, and what Kansas's "Historical Pending" and
"MIXED" mean.

## 0038 — An Iowa reader is built and tested behind a flag that is off (2026-11-06)

Same pattern as 0037, for the Iowa Department of Natural Resources' beach
monitoring results (AQuIA). The reader is `pipeline/src/caalgae/iowa.py`,
registered in `pipeline/src/caalgae/flagged.py` under `LN_ENABLE_IOWA`. No
reuse terms were found at all (AQuIA's "Site Policies" link answered 404 on
2026-11-06), so under 0004 the license is recorded as `unknown` and the data
is not used. Permission has not been asked yet; the draft is for the AQuIA
contact form, topic "Beaches".

- **The flag, off means identical, on is review only, the source is off and
  unlisted:** exactly as 0037. `sources.IA_DNR_BEACHES` has `enabled=False`,
  no attribution, and is kept out of `SOURCES`. A default build of the
  fixture site, snapshot and history is byte-identical with or without the
  Iowa reader registered and with `LN_ENABLE_IOWA=0`; with it on, the
  published files are still the default's byte for byte and only
  `ia-review.json` is written (`pipeline/tests/test_flagged_iowa.py`).
- **What is read.** The two CSV downloads on programs.iowadnr.gov (robots.txt
  404, no rules under 0011), `DownloadBeachResults/State` and
  `.../CountyCity`, 5 s apart: `siteID`, `name`, `sampleDate`,
  `microcystin`, `status`, `comments`. The E. coli columns are never read.
  The files have no coordinates, so none is given.
- **The sign is shared, so the toxin result decides.** The DNR posts
  "Swimming is Not Recommended" for indicator bacteria and for
  cyanobacteria toxins alike. A row is an algae advisory only when that sign
  is posted and the microcystin result is over the DNR's own threshold,
  "8 µg/L total microcystins". The level is the file's own status text,
  under the `other_advisory` tier; no level is invented.
  - The same sign with a result of 8, under 8, blank or unreadable decides
    nothing (it may be a bacteria advisory, and is not shown as "no
    advisory").
  - "Watch / General Information" with a result under 8 (a reporting limit
    like `<0.3` counts as under only when the limit is) is an explicit end.
    With a result over 8 it is undetermined (0027); with 8 or no result it
    decides nothing.
  - "Beach Closed", "Special Status", "Insufficient Data", "County-City
    Beach" and a blank status decide nothing. Any other status is
    undetermined (0027).
  - Both spellings are read: the beach page's "Swimming is Not Recommended"
    and "Watch / General Information", and AQuIA's status reference's
    "Swimming Not Recommended" and "Ok for Swimming". Which one the download
    carries was not seen (off season).
- **Refusals.** A download missing a column, answering a web page, not
  UTF-8, or with no rows at all is refused whole. Out of season the DNR
  publishes no rows, and an empty read is never taken as "no advisory".
- **Fixtures are invented.** `ia-state.csv` and `ia-countycity.csv` under
  `pipeline/tests/fixtures/states-invented/`, written by hand in AQuIA's
  column layout with invented beaches ("Invented Lake Beach") and site ids
  in the 99000000s; no DNR data is committed.
- **Development reads, 2026-11-06,** with a User-Agent naming Lake Notice and
  chelsea@chelseakr.com: programs.iowadnr.gov/robots.txt (404), the API
  guide, the beach page, the State download (header only, no rows, off
  season), the status reference and the weekly results (an empty list).
  Nothing from these reads is committed.
- **Turning it on** is the owner's call after the DNR's written yes, as in
  0037.

Open questions for the DNR, before any page: which status words the
download carries in season; whether a result of exactly 8 µg/L is over the
threshold; whether a "Swimming is Not Recommended" sign with a high
microcystin result can still be for bacteria alone; and coordinates Lake
Notice may use.

## 0039 — A saved lake missing from the data says what is missing, dated, and is not a finding (2026-11-07)

The pre-submission check of 2026-11-07 found one app line left from the
launch review's honesty list (source-outage audit finding 9). Favorites
saves only a lake's id, and a saved lake the data on the phone does not
have showed "A saved lake / No longer in the state's current file." That
claims something the phone cannot know. With no data file on the phone it
was shown for every favorite, and a lake can also leave Lake Notice's data
because a state's layer dropped it or a state is switched off.

- **No data on the phone:** "Lake Notice has no lake data on this iPhone
  yet, so it can't show this lake's status."
- **A state with no lakes in the data** (the id's state prefix, when this
  build knows the state): "Lake Notice's data dated <run date> has no
  Missouri lakes, so it can't show this lake's status."
- **Otherwise:** "This lake is not in Lake Notice's data dated <run date>,
  so it can't show its status."
- Each ends with "That is not a finding of no advisory." No level, no
  "no advisory" and no state's-file claim. An id prefix this build does not
  know names no state.

The copy is `SavedLakeCopy` in AlgaeCore. The widget already counted these
lakes as "not in the current data" and is unchanged. Everything else on the
launch review's pre-submission code list was already on main (0024, 0027,
0030) or is in open PRs #37 (0031) and #42 (0036).

Tests: `ios/AlgaeCore/Tests/AlgaeCoreTests/SavedLakeCopyTests.swift`.
Negative controls: the old line fails the same checks, and with `detail`
returning it three of the five tests fail; with Missouri waters in the data
a Missouri id reads as a missing lake, not a missing state.

## 0040 — Chesterfield: the two lakes with an advisory are already indexed, and the park lake stays out (2026-11-13)

The search read of 2026-11-12 (growth/ln-search-gaps-2026-11-12.md) saw the
query "chesterfield lake" at position 29.5 and guessed that the Missouri
pages it matches were among the noindexed thin pages. The owner chose
"index Chesterfield Lake" (2026-11-12). Built from the history of
2026-11-13, three Missouri waters carry the name, and the guess holds for
only one of them:

- **Lake Chesterfield (and tributary)** and **Harbors at Lake
  Chesterfield** were already indexable. Each has one record, an "Advisory
  (advise)" posted Jul 5 and Jul 16, 2026, inside the 24-month window
  (0016). Both pages have no robots tag, a canonical of their own and a
  sitemap entry. Nothing in the index rule needed to change for them.
- **Chesterfield Central Park Lake stays `noindex,follow` and out of the
  sitemap.** It has one record, "Dissipated (dissap)" from Aug 17, 2024,
  and its page's only status line is "Reports on file, with no advisory
  level the state has classified." The noindex audit of 2026-11-07
  (growth/ln-noindex-audit-2026-11-07.md) sets out why such a page is held
  back: built from one record, in a search result, it reads as an
  all-clear (0002). The page is still built and linked from /state/mo/.
- **No index rule changed.** The search read also proposed indexing any
  thin page that Search Console shows impressions for. That rule would
  index pages like the park lake's, so it is not adopted here. **Owner to
  confirm.**
- **Not changed, and worth knowing:** both indexed pages have names too
  long for a dated title (0018), so they read "Lake Chesterfield (and
  tributary) | Lake Notice" and "Harbors at Lake Chesterfield algae
  advisories | Lake Notice". Water titles are under the dated-title read
  until about 2026-11-25. Both pages leave the index in July 2028 if the
  department posts nothing newer.

Tests: `pipeline/tests/test_missouri_indexing.py`. The site tests build
California only, so this is the first check of the staging rule (robots tag,
canonical and sitemap agreeing with the snapshot) on a build with Missouri
in it. It then checks the three Chesterfield waters by name. Negative
control: with `INDEX_MIN_RECORDS` set to 1 the park lake's page becomes
indexable, so the record floor is what holds it back.
