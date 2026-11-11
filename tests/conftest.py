"""Shared fixtures: saved L1 pages from Wed 11 Nov 2026."""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def weer_html() -> str:
    return (FIXTURES / "weer.html").read_text("utf-8")


@pytest.fixture
def nieuws_html() -> str:
    return (FIXTURES / "nieuws.html").read_text("utf-8")


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Let Home Assistant load custom_components/l1_weer in tests."""
    return
