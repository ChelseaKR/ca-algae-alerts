#!/usr/bin/env python3
"""Refresh pipeline/data/trout_truck_pages.json from a Trout Truck snapshot.

Lake Notice links a water page to the same water on Trout Truck (DECISIONS
0026). The pairs live in pipeline/data/trout_truck_pairs.json, and the build
drops a pair whose Trout Truck page is not in this list, so the site never
links to a page Trout Truck no longer has. Trout Truck commits no sitemap, so
the list is read from its committed app snapshot. Read only; this never
writes to the Trout Truck repo.

    git -C ../ca-fish-planting-alerts show \\
        origin/main:android/app/src/main/assets/snapshot.json > /tmp/tt.json
    python3 scripts/trout_truck_pages.py /tmp/tt.json --commit de884ae
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "pipeline" / "data" / "trout_truck_pages.json"
SNAPSHOT_PATH = "android/app/src/main/assets/snapshot.json"


def page_list(snapshot: dict[str, Any], commit: str) -> dict[str, Any]:
    waters: list[dict[str, Any]] = snapshot["waters"]
    paths = sorted(
        {
            str(w["site_path"])
            for w in waters
            if w.get("state") == "CA" and w.get("site_path")
        }
    )
    return {
        "source": f"ChelseaKR/ca-fish-planting-alerts@{commit}:{SNAPSHOT_PATH}",
        "generated_at": snapshot["generated_at"],
        "paths": paths,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--commit", required=True)
    args = parser.parse_args()
    data = page_list(json.loads(args.snapshot.read_text("utf-8")), args.commit)
    OUT.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
