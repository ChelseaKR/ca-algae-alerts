#!/usr/bin/env bash
# Rebuild the snapshot that ships inside the app from the committed history
# and CyAN cache, without touching the network: the history already holds
# every record. Run
# before an App Store build so a first launch with no network still shows
# recent data.
set -euo pipefail
root="$(cd "$(dirname "$0")/../.." && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
cp "$root/pipeline/data/history.json" "$work/history.json"
cd "$root/pipeline"
uv run --frozen python - "$work/history.json" "$root/pipeline/data/cyan.json" "$root/ios/AlgaeAlerts/Resources/snapshot.json" <<'PY'
import datetime as dt, sys
from collections import Counter
from pathlib import Path
from caalgae import cyan, history, snapshot
from caalgae.sources import CA_SWRCB_FHAB, MO_DNR_HAB
h = history.load(Path(sys.argv[1]))
ca = h.last_file(CA_SWRCB_FHAB.id)
mo = h.last_file(MO_DNR_HAB.id)
quarantine = Counter(ca["quarantined_by_reason"])
if mo:
    quarantine += Counter({f"Missouri: {k}": v for k, v in mo["quarantined_by_reason"].items()})
snap = snapshot.build(
    h,
    run_date=dt.date.fromisoformat(ca["fetched_at"][:10]),
    generated_at=dt.datetime.fromisoformat(ca["fetched_at"].replace("Z", "+00:00")),
    quarantine=quarantine,
    cyan_cache=cyan.load_cache(Path(sys.argv[2])),
)
snapshot.write(snap, Path(sys.argv[3]))
print(f"bundled snapshot: {len(snap['waterbodies'])} waterbodies from {ca['file_name']}")
PY
