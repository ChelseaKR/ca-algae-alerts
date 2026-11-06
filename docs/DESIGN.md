# Lake Notice design

The look of lakenotice.com (docs/DECISIONS.md 0035). Everything lives in
`pipeline/src/caalgae/templates/style.css` and the two base templates. No
build step, no web fonts, no script.

## The idea

A notice posted at the shore. The thing people actually meet at a lake is a
sign with a colored band across the top, so the site is built around that:
paper and ink, a sign-board mark, a signage typeface, and depth contours
from a lake survey as the only ornament.

It must not look like Trout Truck (dark green header band, gold Bitter
wordmark, Atkinson body) or Family Greenhouse (green and orange, Bitter
serif). The two water sites share a developer and an App Store 4.3(a) risk.

## Tokens

| Token | Light | Dark | Use |
|---|---|---|---|
| `--paper` | #fbfaf6 | #0f1120 | Page |
| `--surface` | #ffffff | #161930 | Status box, tables |
| `--wash` | #eeeff7 | #141733 | Header, footer |
| `--ink` | #16182b (16.8:1) | #ecedf7 (16.1:1) | Text |
| `--muted` | #4a4e66 (7.8:1) | #b3b6cc (9.3:1) | Secondary text |
| `--link` | #3634a8 (9.1:1) | #aeb3ff (9.5:1) | Links, focus ring |
| `--brand` | #262a6b | #c9ccff | Wordmark, survey line, section marks |

Ratios are against `--paper`; `test_design_identity.py` checks every text
token against every background at 4.5:1 or more.

## Advisory levels

The colors of California's posted signs. The band text is the level's
words; the marks repeat the rank. Color is never the only signal.

| Level | Band light | Band dark | Text on band | Marks |
|---|---|---|---|---|
| Caution | #f6c800 | #f6c800 | #1a1700 (11.3:1) | 1 of 3 |
| Warning | #e66a00 | #f07a12 | #1a0d00 (5.8 / 6.8:1) | 2 of 3 |
| Danger | #b5121b | #c81e28 | #ffffff (6.8 / 5.7:1) | 3 of 3, heavier border |
| Missouri levels | #4b4d70 | #6a6d99 | #ffffff (8.1 / 4.9:1) | none (not the same scale) |
| Not an advisory | #e4e5ee | #262a45 | ink (14.0 / 12.0:1) | none, dashed box |

Rules:

- Only an advisory gets a level color. A record that recommends no
  advisory, or an undetermined one, says "Latest state record" on a neutral
  band, never anything that reads as an all-clear.
- No token is green. Green reads as "go", and this site never says a water
  is safe.
- In forced-colors mode the band keeps a border and the words; in print the
  band colors are kept.

## Type

- Signage face (wordmark, headings, table heads, nav): DIN Alternate,
  Bahnschrift, D-DIN, Roboto Condensed, Arial Narrow, then the system sans.
- Text: Avenir Next, Segoe UI, Roboto, Helvetica Neue, Arial.
- Numbers are tabular, so dates line up in history tables.

## Mark

A notice board on a post at the waterline, with two ripples
(`templates/mark.svg`, inline in the header with `aria-hidden`, and the
favicon). It uses `currentColor` in the header, so it follows the theme.
