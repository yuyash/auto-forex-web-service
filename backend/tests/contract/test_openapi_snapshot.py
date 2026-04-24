"""OpenAPI contract guardrails.

This test intentionally checks a small, stable subset so it catches
accidental endpoint regressions without being overly brittle.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.mark.contract
def test_openapi_snapshot_contains_core_trading_paths() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    openapi_path = repo_root / "docs" / "openapi.json"
    payload = json.loads(openapi_path.read_text(encoding="utf-8"))

    paths = payload.get("paths", {})
    required_paths = {
        "/api/trading/tasks/backtest/",
        "/api/trading/tasks/backtest/{id}/metrics/",
        "/api/trading/tasks/trading/",
        "/api/trading/tasks/trading/{id}/metrics/",
        "/api/trading/strategy-configs/",
    }
    missing = sorted(required_paths - set(paths.keys()))
    assert not missing, f"Missing required OpenAPI paths: {missing}"

    components = payload.get("components", {}).get("schemas", {})
    assert "BacktestTask" in components
    assert "TradingTask" in components
