"""The app's guidance sentences are the website's, word for word.

``ios/AlgaeCore/Sources/AlgaeCore/StatusWording.swift`` mirrors
``LEVEL_GUIDANCE``, ``GENERIC_GUIDANCE`` and ``STATE_GUIDANCE`` in
``wording.py``. This reads the Swift string literals, fills in the
``\\(name)`` interpolations from the Swift file's own constants, and checks
that every guidance string on each side is on the other.
"""

from __future__ import annotations

import re
from pathlib import Path

from caalgae import wording

SWIFT = (
    Path(__file__).resolve().parents[2]
    / "ios/AlgaeCore/Sources/AlgaeCore/StatusWording.swift"
)
_LITERAL = re.compile(r'"((?:[^"\\]|\\.)*)"')
_CONST = re.compile(r'static let (\w+)\s*=\s*"((?:[^"\\]|\\.)*)"')
_INTERP = re.compile(r"\\\((\w+)\)")


def _swift_strings(source: str, region: str | None = None) -> set[str]:
    """The literals in ``region`` (all of ``source`` by default), filled in
    from the constants anywhere in ``source``."""
    consts = dict(_CONST.findall(source))

    def fill(text: str) -> str:
        for _ in range(5):
            text = _INTERP.sub(lambda m: consts.get(m.group(1), m.group(0)), text)
        return text

    consts = {k: fill(v) for k, v in consts.items()}
    return {fill(s) for s in _LITERAL.findall(source if region is None else region)}


def _python_guidance() -> list[str]:
    return [
        *wording.LEVEL_GUIDANCE.values(),
        wording.GENERIC_GUIDANCE,
        *wording.STATE_GUIDANCE.values(),
    ]


def test_every_guidance_string_is_in_the_app() -> None:
    swift = _swift_strings(SWIFT.read_text(encoding="utf-8"))
    missing = [s for s in _python_guidance() if s not in swift]
    assert missing == []


def test_the_app_has_no_guidance_the_website_lacks() -> None:
    source = SWIFT.read_text(encoding="utf-8")
    start = source.index("public static func guidance(_ tier: AdvisoryTier)")
    end = source.index("/// What this level asks")
    swift = _swift_strings(source, source[start:end])
    # Leaves out the "MO" dictionary key and the pieces (waterUse, fish)
    # the shown strings are built from, which are never shown alone.
    pieces = {wording.WATER_USE, wording._FISH}
    shown = {s for s in swift if len(s) > 40 and s not in pieces}
    assert shown - set(_python_guidance()) == set()


def test_the_parity_check_is_not_vacuous() -> None:
    source = SWIFT.read_text(encoding="utf-8").replace(
        "go into or drink the water, or eat scum", "drink the water, or eat scum", 1
    )
    assert source != SWIFT.read_text(encoding="utf-8")  # the sabotage applied
    swift = _swift_strings(source)
    assert [s for s in _python_guidance() if s not in swift] != []
