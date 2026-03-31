"""Unit tests for fedlex-mcp server (non-live)."""
from __future__ import annotations

import pytest


@pytest.mark.parametrize("sr_number", ["101", "210.10", "172.021"])
def test_sr_number_format_valid(sr_number: str) -> None:
    """SR numbers in correct format are accepted."""
    import re
    pattern = r"^\d{3}(\.\d+)*$"
    assert re.match(pattern, sr_number), f"Invalid SR format: {sr_number}"


def test_server_imports() -> None:
    """Server module can be imported."""
    import importlib
    mod = importlib.import_module("fedlex_mcp.server")
    assert hasattr(mod, "mcp"), "mcp instance not found"


# Live tests (skipped in CI via: pytest -m 'not live')
@pytest.mark.live
def test_live_sparql_endpoint() -> None:
    """Live test against the real Fedlex SPARQL endpoint."""
    pass  # Placeholder for live tests
