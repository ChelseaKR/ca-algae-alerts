"""Fixture paths and dates shared by the tests."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"
PAGE = FIXTURES / "dataset-page-2026-10-12.html"
TRAPS = FIXTURES / "responses-traps_2026-10-09.csv"
SAMPLE = FIXTURES / "responses-sample_2026-10-09.csv"
FILE_DATE = dt.date(2026, 10, 9)
RUN_DATE = dt.date(2026, 10, 12)
