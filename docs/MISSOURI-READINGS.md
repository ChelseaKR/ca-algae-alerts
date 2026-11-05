# Missouri status-code readings, for the owner to confirm

Missouri is in 1.0 (docs/DECISIONS.md 0013), but the owner must confirm every
reading below, and the closed-case rule, before the first publish. The
department publishes no definitions of its status codes, so each reading is
this project's, shown beside the code on the page ("Advisory (advise)"). This
file lists them exactly as `pipeline/src/caalgae/missouri.py` has them today;
nothing here was changed. If a reading is wrong, the fix is in that file and
`pipeline/tests/test_missouri.py`, not in this list.
`pipeline/tests/test_missouri_readings_doc.py` fails if this table and the
code disagree.

## The status codes (`BloomStat`, lower-cased before use)

| Code | Label shown | Treated as | Record produced |
|---|---|---|---|
| `advise` | Advisory (advise) | an advisory | `other_advisory`, dated the observation date |
| `notice` | Notice (notice) | an advisory (conservative) | `other_advisory`, dated the observation date |
| `dissap` with a dissipation date | Dissipated (dissap) | an explicit end | `no_advisory`, dated the dissipation date |
| `dissap` with no dissipation date | Dissipated (dissap) | decides nothing | `not_classified`, with the note "Marked dissipated; no date recorded." |
| `notthr` | Below threshold (notthr) | decides nothing | `not_classified` |
| `notver` | Not verified (notver) | decides nothing | `not_classified` |
| `report` | Report (report) | decides nothing | `not_classified` |
| any other code | the code as the state wrote it | undetermined: the lake reads as a level this site does not recognize, never as an older end (DECISIONS 0025) | `unknown` |
| blank | (none) | decides nothing | `unknown` |

"Decides nothing" means the record can neither raise an advisory nor end one;
it is listed in the lake's history and a lake with only such records reads
"Reports on file, with no advisory level the state has classified."

## What ends an advisory

- The end of a Missouri advisory is the department's dissipation date
  (`DissDat`), an explicit field.
- An `advise` or `notice` case that carries a dissipation date on or before
  the run date reads as ended on that date. A dissipation date after the run
  date is kept as a planned end and the advisory stands.
- `dissap` with a dissipation date is itself the explicit end, dated that day.
- A dissipation date on any other code (`notthr`, `notver`, `report`, blank)
  is ignored.

## The closed-case rule

A case marked closed (`CaseStatus`) without a dissipation date is **not** an
end. `CaseStatus` is only shown as a note ("Case closed.") and never changes a
status. A closed `advise` or `notice` case with no dissipation date therefore
still reads "last posted <date>, no all-clear recorded". On 2026-10-12, 33
closed `advise` cases from past years read this way (DECISIONS 0010).
The alternative, if you prefer it, is to read a closed case as ended on its
close date; the department publishes no close date, so that reading would
need a date this project does not have. This file does not change the rule.

## Other rules in the same file

- A case with no observation date (`HABODat`) cannot be placed in time and is
  quarantined, not shown (18 of 278 rows on 2026-10-12). So is a case whose
  observation date falls outside 2016-01-01 to the run date, one with no
  water body name, and one with no case id.
- Dates are read in US Central time.
- Fewer than 50 rows (278 on 2026-10-12), an error answer, or more rows than
  one answer carries stops the run before anything is written.
- Each row is one case with its current status, not a history of updates.
- A satellite estimate (EPA CyAN) never decides a status for Missouri or
  California; it is a separate block on the lake page.

## What the owner is asked to confirm

1. `advise` is an advisory.
2. `notice` is an advisory (the conservative reading).
3. `dissap` with a dissipation date is an explicit end.
4. `dissap` with no date, `notthr`, `notver`, `report` and blank decide
   nothing.
5. The closed-case rule: closed without a dissipation date is not an end.

If any answer is no, Missouri can be switched off for 1.0 by its one switch
(`enabled` on its source in `sources.py`), leaving California only.
