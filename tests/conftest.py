"""Shared test fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture()
def forecast_response() -> dict:
    """Real WU forecast API response."""
    return json.loads((FIXTURES_DIR / "forecast_response.json").read_text())


@pytest.fixture()
def current_response() -> dict:
    """Real WU current conditions API response."""
    return json.loads((FIXTURES_DIR / "current_response.json").read_text())
