# schema/

`snapshot.v1.json` is the contract between the pipeline and its two
consumers, the site and the iOS app. The pipeline validates every snapshot
against it before writing anything; `pipeline/src/caalgae/snapshot.v1.json`
is the packaged copy and a test keeps the two identical.

What the schema enforces, beyond shapes:

- An `advisory` status always has a tier and a posted date, and never a
  lift.
- A `no_advisory_recorded` status always has a lift kind
  (`no_advisory_record`, the state's explicit "None", or `end_date`, an
  end date the state recorded) and a lift date. There is no other way to
  end an advisory.
- `undetermined` has neither.

Published at `<site>/snapshot/v1.json`. A breaking change is `v2.json`
beside it; v1 keeps being published while any app build reads it.
