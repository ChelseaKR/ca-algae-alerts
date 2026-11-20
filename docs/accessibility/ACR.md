# Lake Notice website: Accessibility Conformance Report

Accessibility Conformance Report (ACR), based on the VPAT® 2.5 Rev WCAG
edition.

VPAT® is a registered service mark of the Information Technology Industry
Council (ITI).

> **Accessibility status: WCAG 2.2 AA target. Automated and synthetic
> evidence passed for this release; human assistive-technology review
> remains pending.**

## Name of product and version

Lake Notice website, lakenotice.com (the static site this repository
builds; pipeline package `caalgae` 0.1.0). Evaluated at `origin/main`
48b1485 plus the branch `a11y/acr-2026-11`.

## Report date

2026-11-20 (evaluation run 2026-11-19).

## Product description

A free static website that republishes state harmful algal bloom (toxic
algae) advisory records for lakes and rivers: California and Missouri
advisories, New York's yearly bloom history, and a separately labeled EPA
satellite estimate for large lakes. One page per water with its status and
full record history, lists by county and state, a page for dog owners, and
about, privacy, terms and support pages. No accounts, no forms, no media,
no embedded map. The only executable script is the Google Analytics loader
with its footer opt-out button.

Out of scope: the iPhone app (not released; it has its own XCTest
accessibility audit in `ios/`), and third-party pages the site links to
(state maps, data portals, Amazon, Ko-fi). The site sends no email and
serves no PDFs.

## Contact information

The support page, <https://lakenotice.com/support/>. Accessibility problems
can be reported there or as an issue on this repository.

## Notes

- **This report is provisional.** Rows marked "provisional" rest on
  automated tools, rendered-browser scripts and code reading. A human pass
  with a screen reader (Appendix B) has not been done yet. Until it is, no
  row here is a human-verified conformance finding, and Lake Notice does not
  claim WCAG conformance.
- **Remarks describe the site after the `a11y/acr-2026-11` branch.** That
  branch wraps every table in a keyboard-focusable scroll region named by
  its caption and stops the stylesheet from turning tables into blocks on
  narrow screens, and makes the axe gate scan the dark color scheme too.
  Before it, every table on a phone-width screen was set to
  `display: block`, which can drop row and column semantics in some
  browser and screen reader pairings (1.3.1), and a table that did scroll
  could not be reached from a keyboard in Safari if it held no link
  (2.1.1); in the evaluated build no table was wider than a 320px screen.
  The report is true of lakenotice.com only once that branch is merged and
  deployed.
- **Advisory levels never rest on color.** Every status is a sentence that
  names the level and its date, such as "Danger advisory, last posted
  Oct 3, 2026. No all-clear recorded." The colored box border only repeats
  it. Lists carry the level in a text column. Nothing on the site uses
  color, an icon or a map to say a level.
- **No embedded map.** Pages link to each state's official map, and the
  site's own lists and water pages are the text form of what those maps
  show.
- **Nothing reads as an all-clear.** Every status that is not an advisory
  is followed in the status box by "It is not a finding that the water is
  safe now". The site's copy tests fail any sentence that calls a water
  safe without negating it.

## Evaluation methods used

- **axe-core 4.13.0** (through `@axe-core/puppeteer`) with the WCAG 2.0,
  2.1 and 2.2 A and AA tags, on all 264 pages of the site built from the
  committed real-data fixture, at 1280px in the light and the dark color
  scheme: 0 violations.
- **pa11y-ci 5.0.0** (pa11y 10.0.0, axe runner, WCAG2AA) on all 264 pages:
  264/264 passed, 0 errors.
- **Lighthouse 13.5.0 CI**, three runs each on home, about, a water page and
  a county page: accessibility score at or above the 0.90 budget.
- **A 320 CSS px reflow check** on every page (no sideways page scroll).
- **Supplementary rendered checks** (Chrome for Testing 156, headless) on 18
  representative pages, one or more per template, before and after the
  branch: axe in dark mode at 320px and light mode at 320px; a WCAG 1.4.12
  text-spacing override at 1280px and 320px looking for clipped text; the
  display and focusability of every table at 320px; a scripted Tab walk
  at 1280px and 320px recording focus order, a visible focus outline, and
  whether the focused element is on screen.
- **Contrast** computed from the stylesheet's color tokens, light and dark
  (Appendix A).
- **Code reading** of every page template, the stylesheet, the analytics
  script and the wording module.
- **Tests in the repository's suite** (`pipeline/tests/test_site_a11y.py`)
  that hold the table regions, the stylesheet rule and the dark-mode axe
  scan in place.

Not performed: any human screen-reader pass (NVDA, VoiceOver, TalkBack), a
human keyboard-only pass, real browser zoom, Windows forced colors, and
Firefox or Safari rendering.

## Applicable standards and guidelines

| Standard/guideline | Included in report |
|---|---|
| Web Content Accessibility Guidelines 2.2 | Level A (Yes), Level AA (Yes), Level AAA (No) |

WCAG 2.2 includes every WCAG 2.0 and 2.1 success criterion except 4.1.1
Parsing, which WCAG 2.2 removed as obsolete. Conformance to 2.2 Level AA
covers 2.0 and 2.1 Level AA.

## Terms

- **Supports**: the functionality of the product has at least one method
  that meets the criterion without known defects or meets with equivalent
  facilitation.
- **Partially Supports**: some functionality of the product does not meet
  the criterion.
- **Does Not Support**: the majority of product functionality does not meet
  the criterion.
- **Not Applicable**: the criterion is not relevant to the product.
- **Not Evaluated**: the product has not been evaluated against the
  criterion. Used only for Level AAA here.

"Provisional" in a remark means the row rests on automated, scripted and
code-reading evidence, and its human screen-reader step in Appendix B is
still open.

## WCAG 2.2 report

### Table 1: Success Criteria, Level A

| Criteria | Conformance level | Remarks and explanations |
|---|---|---|
| 1.1.1 Non-text Content | Supports | The pages have no images, icons, SVG, canvas or embedded media. The breadcrumb separator is CSS-generated with empty alternative text. |
| 1.2.1 Audio-only and Video-only (Prerecorded) | Not Applicable | No audio or video. |
| 1.2.2 Captions (Prerecorded) | Not Applicable | No video. |
| 1.2.3 Audio Description or Media Alternative (Prerecorded) | Not Applicable | No video. |
| 1.3.1 Info and Relationships | Supports | Provisional. Headings in order, lists, header/nav/main/footer landmarks, labeled Primary and Breadcrumb navigation, definition lists, and data tables with captions and `scope` headers. After this branch every table keeps table semantics at every width (before, narrow screens set tables to `display: block`, which can drop table semantics in some browser and screen reader pairings). Needs a human screen-reader pass: Appendix B steps 1 to 4. |
| 1.3.2 Meaningful Sequence | Supports | Source order is reading order; no CSS reorders content. |
| 1.3.3 Sensory Characteristics | Supports | Instructions refer to sections by name ("listed under Reported spots below"), not by shape, color or position alone. |
| 1.4.1 Use of Color | Supports | Advisory levels are always in words (the status sentence on water pages and the Level or Latest record column in lists); the box color only repeats them. Links in text are underlined. No legend, chart or map uses color. |
| 1.4.2 Audio Control | Not Applicable | No audio. |
| 2.1.1 Keyboard | Supports | Provisional. Everything is a native link or button. After this branch each table's scroll region takes focus, so a table wider than the screen can be scrolled with arrow keys even when it holds no link (history, spots). In the evaluated build no table was wider than 320px. Scripted Tab walk reached every link, button and region. Needs a human keyboard-only pass: Appendix B step 5. |
| 2.1.2 No Keyboard Trap | Supports | Scripted Tab walk passed through every page to the end with no trap. No widgets capture keys. |
| 2.1.4 Character Key Shortcuts | Not Applicable | No keyboard shortcuts. |
| 2.2.1 Timing Adjustable | Not Applicable | No time limits. |
| 2.2.2 Pause, Stop, Hide | Not Applicable | No moving, blinking, scrolling or auto-updating content. Data changes only when a new static build is published. |
| 2.3.1 Three Flashes or Below Threshold | Supports | Nothing flashes; the stylesheet has no animation. |
| 2.4.1 Bypass Blocks | Supports | A "Skip to main content" link is the first focus stop on every page, and pages use landmarks. |
| 2.4.2 Page Titled | Supports | Every page has a descriptive title; a test fails a build where two pages share a title. |
| 2.4.3 Focus Order | Supports | Provisional. Focus follows source order: skip link, site name, primary navigation, breadcrumb, content, footer. No positive `tabindex`. Needs a human keyboard pass: Appendix B step 5. |
| 2.4.4 Link Purpose (In Context) | Supports | Link text names its destination, or the sentence around it does (for example "Official map:" before the map's address, and "Source" after the quote it sources). |
| 2.5.1 Pointer Gestures | Not Applicable | No multipoint or path-based gestures. |
| 2.5.2 Pointer Cancellation | Supports | Only native links and one native button, which act on release. |
| 2.5.3 Label in Name | Supports | Each link's and the button's accessible name is its visible text. |
| 2.5.4 Motion Actuation | Not Applicable | No motion input. |
| 3.1.1 Language of Page | Supports | `lang="en"` on every page. |
| 3.2.1 On Focus | Supports | Focus never changes context. |
| 3.2.2 On Input | Supports | No form inputs. The analytics opt-out button changes a setting only when pressed and says so in a status line. |
| 3.2.6 Consistent Help | Supports | The support page link sits in the same place in the footer of every page, in the same order with the other footer links. |
| 3.3.1 Error Identification | Not Applicable | No forms or input. |
| 3.3.2 Labels or Instructions | Not Applicable | No forms or input. |
| 3.3.7 Redundant Entry | Not Applicable | No multi-step process or input. |
| 4.1.1 Parsing (WCAG 2.0 and 2.1 only) | Supports | Removed from WCAG 2.2 as obsolete; for 2.0 and 2.1, WCAG's errata treats it as always met for HTML. Templates emit unique ids, checked by a test for table captions. |
| 4.1.2 Name, Role, Value | Supports | Provisional. Native links and a native button with visible-text names; `aria-current="page"` on the last breadcrumb; table regions named by their captions (`aria-labelledby`). axe and pa11y found 0 issues on 264 pages. Needs a human screen-reader pass: Appendix B steps 1 to 4 and 6. |

### Table 2: Success Criteria, Level AA

| Criteria | Conformance level | Remarks and explanations |
|---|---|---|
| 1.2.4 Captions (Live) | Not Applicable | No live media. |
| 1.2.5 Audio Description (Prerecorded) | Not Applicable | No video. |
| 1.3.4 Orientation | Supports | No orientation lock; the layout is one fluid column. |
| 1.3.5 Identify Input Purpose | Not Applicable | No input fields. |
| 1.4.3 Contrast (Minimum) | Supports | Every text color is at least 6.90:1 against every background it can sit on in light mode and 8.42:1 in dark mode (Appendix A); the threshold is 4.5:1. axe found 0 contrast issues on 264 pages in light and in dark mode. |
| 1.4.4 Resize Text | Supports | Sizes are in rem with a fluid layout; at 320 CSS px (400% of a 1280px window) nothing overflows. Checked by viewport, not by a human using browser zoom (Appendix B step 7). |
| 1.4.5 Images of Text | Not Applicable | No images of text. |
| 1.4.10 Reflow | Supports | At 320 CSS px no page scrolls sideways (all 264 pages light, 18 pages dark). Wide data tables scroll inside their own region, which the reflow exception for data tables allows. |
| 1.4.11 Non-text Contrast | Supports | Focus outline (3px) is 7.72:1 light and 10.57:1 dark against the page, and at least 6.90:1 on every background. Box and table borders are decorative: the words carry the status. |
| 1.4.12 Text Spacing | Supports | With WCAG's spacing override applied at 1280px and 320px, no text was clipped and no page scrolled sideways (18 pages). |
| 1.4.13 Content on Hover or Focus | Not Applicable | No content appears on hover or focus; no tooltips. |
| 2.4.5 Multiple Ways | Supports | Primary navigation, the all-advisories list, county and state lists, breadcrumbs, and links between related waters. |
| 2.4.6 Headings and Labels | Supports | Headings name their sections ("What the state's records say", "Reported spots", "Advisory history"); every table has a caption. |
| 2.4.7 Focus Visible | Supports | A 3px outline on every focused link, button and table region; the scripted Tab walk found an outline at every stop. |
| 2.4.11 Focus Not Obscured (Minimum) | Supports | No sticky or fixed headers, banners or overlays; the scripted walk found every focused element on screen at 1280px and 320px. |
| 2.5.7 Dragging Movements | Not Applicable | No dragging. |
| 2.5.8 Target Size (Minimum) | Supports | axe's target-size rule passes on every page. Links inside sentences use the inline exception; breadcrumb links and the opt-out button keep a 24px minimum height; other links are spaced so a 24px circle around each touches no other. |
| 3.1.2 Language of Parts | Supports | All text is English. Place names are proper names. The Spanish pages are built only behind a switch that is off. |
| 3.2.3 Consistent Navigation | Supports | The same header navigation and footer, in the same order, on every page of a build. |
| 3.2.4 Consistent Identification | Supports | The same functions use the same names on every page (for example the support link and "Skip to main content"). |
| 3.3.3 Error Suggestion | Not Applicable | No input. |
| 3.3.4 Error Prevention (Legal, Financial, Data) | Not Applicable | No transactions or submissions. |
| 3.3.8 Accessible Authentication (Minimum) | Not Applicable | No sign-in. |
| 4.1.3 Status Messages | Supports | Provisional. The one status message, the analytics opt-out result in the footer, is in a `role="status"` region that is in the page before it changes. Needs a human screen-reader check: Appendix B step 6. |

### Table 3: Success Criteria, Level AAA

Not Evaluated.

## Legal disclaimer

This report describes the Lake Notice website as evaluated on the date
above, by the methods listed. It is provided for information. It is not a
warranty, and it is provisional until the human review in Appendix B is
done.

## Appendix A: contrast, from the stylesheet's tokens

Ratios against the page background (`--bg`) and the lightest-contrast
background each color is drawn on.

| Color | Light: on page | Light: lowest | Dark: on page | Dark: lowest |
|---|---|---|---|---|
| Body text | 16.33:1 | 14.60:1 (status box) | 15.99:1 | 13.74:1 (status box) |
| Muted text | 7.86:1 | 7.02:1 (status box) | 10.47:1 | 9.00:1 (status box) |
| Link | 7.72:1 | 6.90:1 (status box) | 10.57:1 | 9.08:1 (status box) |
| Visited link | 10.16:1 | 9.09:1 (status box) | 9.80:1 | 8.42:1 (status box) |
| Focus outline | 7.72:1 | 6.90:1 | 10.57:1 | 9.08:1 |
| Advisory box border (repeats words) | 5.43:1 | 4.85:1 | 8.34:1 | 7.16:1 |

## Appendix B: human walkthrough (open)

About 90 minutes for both pairings. Record the result, date, browser and
screen reader for each step in `docs/accessibility/walkthrough-YYYY-MM-DD.md`.
Pages: the home page, `/advisories/`, `/county/`, one county page, one
water page with an advisory and a long history (Silverwood Lake), one with
"recommends no advisory", a Missouri water, `/state/ny/`, one New York
water, `/dogs/`, `/about/`, `/support/`.

Pairings: VoiceOver with Safari on macOS; NVDA with Firefox or Chrome on
Windows; VoiceOver with Safari on iPhone for steps 1, 3 and 5.

1. **Water page, status.** Move by heading to "What the state's records
   say". Listen for the full status sentence, level and date first ("Danger
   advisory, last posted ..."), then "No all-clear recorded." For a water
   with no current advisory, listen for "recommends no advisory" followed by
   "It is not a finding that the water is safe now." Nothing should be
   conveyed only by the box color.
2. **Headings and landmarks.** Open the headings list (VoiceOver rotor,
   NVDA Insert+F7). One h1, h2s in order. Landmarks: banner, Primary
   navigation, Breadcrumb navigation, main, content info, and one region per
   table named by its caption.
3. **Tables.** In the history table, move by cell (VoiceOver Ctrl+Option+
   arrows, NVDA Ctrl+Alt+arrows). Listen for column headers announced with
   each cell (Date, Spot, State's level, Notes), and the row and column
   count. Repeat on an iPhone in portrait, where the table scrolls sideways.
4. **Lists.** On `/advisories/` and a county page, the Level or Latest
   record cell is read as words for every row.
5. **Keyboard only, no pointer.** Tab from the top of a water page at a
   narrow window (about 320px wide, or 400% zoom). The skip link appears
   first and works; focus is always visible and never hidden; Tab reaches
   each table region and the arrow keys scroll it sideways; Tab reaches the
   footer and leaves the page with no trap.
6. **Analytics opt-out.** In a browser that does not send Global Privacy
   Control, press "Opt out of analytics" in the footer. The status line
   should be announced ("Analytics is off on this device.") without moving
   focus, and the button should be read as "Opt back in".
7. **Zoom.** Browser zoom to 200% and 400% on a water page and the home
   page: no text cut off, no sideways page scroll, tables scroll in place.
8. **Dark mode.** Repeat steps 1 and 5 with the system in dark mode.
