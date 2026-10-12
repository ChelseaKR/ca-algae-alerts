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

## 0011 — robots.txt: a 404 is "no rules"; any other error is off-limits (2026-10-12, owner to confirm)

The owner's ruling: hosts whose robots.txt returns an error (for example
ArcGIS's 403 "Invalid URL") are off-limits, and Missouri is added only if
its host's robots.txt is readable and allows the paths. Missouri's host
(`gis.dnr.mo.gov`) and CyAN's (`qed.epa.gov`) both answer **404**: there is
no robots file. This build reads a 404 as RFC 9309 does, "no rules", and so
added both; the CyAN instruction came with the research's note that its
host's robots.txt is a 404. The stricter reading ("not readable", so
off-limits) would remove both: set `enabled=False` on `MO_DNR_HAB` and
`EPA_CYAN`. Every live run checks robots.txt first (`fetch.robots_allows`):
a readable file is enforced, a 404 passes, and any other status stops that
source without touching California.
