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

## 0016 — New York's yearly bloom summary, as history only, behind a switch (owner, 2026-11-02)

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
  SHA-256). `newyork.PINNED_SHA256` pins the rows; a cache that does not match
  its sidecar or the pin is refused, and the site is built without New York
  with a warning (California and Missouri are never stopped by it).
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
