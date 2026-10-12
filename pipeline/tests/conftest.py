from __future__ import annotations

import pytest
from paths import FILE_DATE, PAGE, TRAPS

from caalgae import normalize


@pytest.fixture
def traps() -> normalize.Normalized:
    return normalize.normalize_csv(TRAPS.read_bytes(), FILE_DATE)


@pytest.fixture
def page_html() -> str:
    return PAGE.read_text(encoding="utf-8")
