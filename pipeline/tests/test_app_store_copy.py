"""The App Store copy reads as Lake Notice's own, not a Trout Truck template
(launch review 2026-11-05 §5.2, DECISIONS 0030), and its purchase name agrees
everywhere while the product id never changes."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
LISTING = ROOT / "docs" / "app-store" / "LISTING.md"
NOTES = ROOT / "docs" / "app-store" / "REVIEW-NOTES.md"
STOREKIT = ROOT / "ios" / "AlgaeAlerts" / "Configuration.storekit"
FREE_TIER = ROOT / "ios" / "AlgaeCore" / "Sources" / "AlgaeCore" / "FreeTier.swift"
PURCHASE_MANAGER = ROOT / "ios" / "AlgaeAlerts" / "App" / "PurchaseManager.swift"

PRODUCT_ID = "net.chelseakr.algaealerts.fullaccess"

# Trout Truck's own listing headings, caption and purchase name
# (ca-fish-planting-alerts docs/APP-STORE-LISTING.md), and this listing's
# earlier copies of them.
TROUT_TRUCK = (
    "Full Access",
    "FULL ACCESS",
    "ONE PURCHASE",
    "PRIVATE BY DESIGN",
    "HONEST ABOUT",
    "EVERY WATER, WEEK BY WEEK",
    "FREE, WITH ONE OPTIONAL PURCHASE",
    "No account. No tracking.",
    "No account, no tracking",
)


def _quoted(text: str, heading: str) -> str:
    """The ``>``-quoted block under a ``## heading``: the paste-ready text."""
    section = text.split(f"## {heading}\n", 1)[1].split("\n## ", 1)[0]
    section = section.split("\n### ", 1)[0]
    lines = [
        ln[1:].removeprefix(" ") for ln in section.splitlines() if ln.startswith(">")
    ]
    return "\n".join(lines)


def _notes_field() -> str:
    text = NOTES.read_text(encoding="utf-8")
    return text.split("## Notes field\n", 1)[1].split("\n## ", 1)[0].strip()


def _purchase_name() -> str:
    match = re.search(
        r'purchaseName = "([^"]+)"', FREE_TIER.read_text(encoding="utf-8")
    )
    assert match
    return match.group(1)


@pytest.mark.parametrize("path", [LISTING, NOTES])
def test_no_trout_truck_heading_caption_or_name(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    assert [s for s in TROUT_TRUCK if s in text] == []


def test_the_purchase_name_agrees_and_the_id_does_not_move() -> None:
    name = _purchase_name()
    assert len(name) <= 30 and "full access" not in name.lower()
    product = json.loads(STOREKIT.read_text(encoding="utf-8"))["products"]
    assert [p["productID"] for p in product] == [PRODUCT_ID]
    assert [loc["displayName"] for loc in product[0]["localizations"]] == [name]
    assert f'productID = "{PRODUCT_ID}"' in PURCHASE_MANAGER.read_text(encoding="utf-8")
    listing = LISTING.read_text(encoding="utf-8")
    assert f"- Display name: {name}\n" in listing
    assert f"`{PRODUCT_ID}`" in listing
    assert name in _quoted(listing, "Description")
    assert name in _notes_field()


def test_the_description_fits_and_never_promises() -> None:
    description = _quoted(LISTING.read_text(encoding="utf-8"), "Description")
    assert 500 < len(description) < 4000
    lower = " ".join(description.lower().split())
    for phrase in ("protect your dog", "know before you go", "all clear "):
        assert phrase not in lower
    # "real time" only to say alerts are not.
    assert lower.count("real time") == lower.count("not real time")
    # "safe" only inside "not a finding that the water is safe now".
    assert lower.count("safe") == lower.count("is safe now") == 1
    assert "new york" not in lower


def test_the_notes_are_filled_in_short_and_name_every_agency() -> None:
    notes = _notes_field()
    assert len(notes) < 4000
    assert "<Name>" not in notes and "<SNAPSHOT URL>" not in notes
    assert "https://lakenotice.com/snapshot/v1.json" in notes
    assert "any California agency" not in NOTES.read_text(encoding="utf-8")
    assert "any state or federal agency" in notes
    assert "has no code paths, data or screens for fish stocking" in notes
