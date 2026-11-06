# App Store listing (draft)

Draft copy for the US App Store. Nothing is submitted. The name is Lake
Notice (docs/DECISIONS.md 0012); its App Store availability is unverified
until the record is created. Per docs/DECISIONS.md 0005, the subtitle, the
first screenshot caption and the keywords lead with dogs; the description
covers everyone.

Rules for this copy:

- Never "safe", never "real time" except to say alerts are not, no
  uniqueness claims ("only", "first"), no "protect your dog", no "know
  before you go".
- Written around what an algae advisory is: sign levels, spots, no reliable
  end date. It shares no headings, captions or structure with Trout Truck's
  listing (DECISIONS 0030); `pipeline/tests/test_app_store_copy.py` checks
  that.
- Never mention New York: its history is web only and nothing of it reaches
  the app.
- Level summaries are the app's own (`StatusWording.swift`), still waiting
  for the owner's confirmation; this copy only says that each lake shows
  what its level asks, and never restates a level.

## Name (30 characters max)

`Lake Notice` (11)

## Subtitle (30 characters max), owner's pick

- `Lake algae advisories & dogs` (28), recommended in the 2026-11-05
  launch review: true in every state, leads with dogs.
- `CA lake algae alerts for dogs` (29): drops Missouri.
- `Toxic algae alerts: dogs, kids` (30): children plus "alerts" reads as a
  safety service; not recommended.

## Promotional text (170 characters max)

> Before a lake day with your dog: see the state's toxic algae advisories
> for the lake, each with its date and what its level asks of people and
> pets.

## Description

> Toxic algae (harmful algal blooms) can make people sick and can kill dogs.
> California's Water Boards and Missouri's Department of Natural Resources
> record advisories for lakes, rivers and shorelines. Lake Notice shows those
> records one lake at a time, with what each one does and does not tell you.
>
> An advisory has a sign level, a date and the spots where it was reported.
> On each lake, Lake Notice shows the state's level and the date it was
> posted, then what that level asks of people, children and pets.
>
> Dogs get their own section on every lake. They are more exposed than
> people: they swim through scum, drink the water and lick algae off their
> fur. The section says what to do if your dog goes in, and which signs
> mean calling a veterinarian at once.
>
> If someone has already been in the water, each lake lists the steps for
> people (rinse off, and who to call) and for dogs. Lake Notice is not
> medical advice; in an emergency, call 911.
>
> Every reported spot on a lake has its own history: each posting, change
> and end the state recorded, California's since 2016 and Missouri's since
> 2017. One lake can have a Danger posting at its boat ramp and an older,
> different record at its swim beach.
>
> An advisory stays listed until the state records an end, and an old one
> says its age. When the state's latest record recommends no advisory, Lake
> Notice gives the date and says that it is not a finding that the water is
> safe now. No advisory on file does not mean no algae: most waters are
> never tested, and reporting is voluntary.
>
> For large lakes, a separate section shows the U.S. EPA's weekly satellite
> estimate of cyanobacteria. It is labeled as an estimate, it does not
> measure toxins, and it never changes a lake's advisory or sends an alert.
>
> Browsing, search, favorites and every lake's history are free. One
> purchase, Lake Alerts & Widget, adds an alert when a favorite lake gets a
> new advisory or its level changes, and a Home Screen and Lock Screen widget
> for your favorites. Lake Notice never sends an all-clear. Alerts come when
> iOS lets the app check, often within a day of the state publishing, and
> are not real time.
>
> The app collects no data. Favorites and alerts are worked out on your
> iPhone; its one network request downloads the public advisory file.
>
> Data: California State Water Resources Control Board, Freshwater Harmful
> Algal Bloom Program, via data.ca.gov (public domain); Missouri Department
> of Natural Resources (used under the State of Missouri Data Policy, with
> its required disclaimer in the app); U.S. EPA Cyanobacteria Assessment
> Network satellite estimates. Lake Notice is independent and is not
> affiliated with or endorsed by any state or federal agency. Advisories are
> recommendations. Always follow signs posted at the water.

### If Missouri is off or unavailable at submission

Check on submission day (launch review §6). If Missouri is turned off or in
its data-unavailable mode, change only these:

- First paragraph: "California's Water Boards record advisories for lakes,
  rivers and shorelines."
- History paragraph: "California's since 2016".
- Data line: drop the Missouri clause.
- Keywords: drop `Missouri` (and REVIEW-NOTES drops it too).

## Keywords (100 characters max, comma-separated, no spaces)

`dog,dogs,toxic algae,blue green algae,lake,cyanobacteria,HAB,swim,California,Missouri,pet` (89)

## Screenshot captions

The set opens on a lake, not a list (launch review §5.2.3). Caption 1 leads
with dogs (DECISIONS 0005).

1. "Taking your dog to the lake? See what its advisory asks." (lake screen,
   level and dogs section)
2. "What each sign level asks of people, children and pets." (level guidance)
3. "Every reported spot, with its own history." (spots and records)
4. "What to do after contact, for people and for dogs." (after-contact steps)
5. "Alerts for your favorite lakes. Never an all-clear." (Favorites, alerts on)
6. "Your favorite lakes stay on your iPhone." (About, with sources)

## Category, owner's pick

- Weather primary, Travel secondary: recommended in the launch review.
- Not Health & Fitness, which invites medical scrutiny (guideline 1.4).

## Copyright

`2027 Chelsea Kelly-Reif`

## Age rating

The owner answers Apple's questionnaire. No user-generated content and no
web view. The app gives after-contact steps and veterinary advice for dogs,
so answer the medical or treatment information question truthfully and
accept the rating that results.

## In-app purchase

- Reference name: Lake Notice Alerts
- Product id: `net.chelseakr.algaealerts.fullaccess` (unchanged; it must
  match `PurchaseManager.productID`)
- Type: non-consumable, USD 9.99
- Display name: Lake Alerts & Widget
- Description: "Alerts and a widget for your favorite lakes"

## Privacy

- Privacy label: Data Not Collected.
- Privacy policy URL: https://lakenotice.com/privacy/
- Support URL: https://lakenotice.com/support/; support email
  chelsea@chelseakr.com.
