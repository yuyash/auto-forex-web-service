"""Unit tests for per-tick execution collaborators."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from apps.trading.tasks.execution_tick_processing import (
    BacktestGapGuard,
    LiveTickDeliveryStateRepository,
)


class TestBacktestGapGuard:
    """Tests for backtest tick gap detection."""

    def test_weekend_gap_is_not_suspicious(self):
        previous = datetime(2026, 5, 8, 21, tzinfo=UTC)
        current = previous + timedelta(days=2, hours=1)

        assert BacktestGapGuard.is_suspicious(previous, current, max_gap_hours=24) is False

    def test_midweek_large_gap_is_suspicious(self):
        previous = datetime(2026, 5, 6, 12, tzinfo=UTC)
        current = previous + timedelta(hours=48)

        assert BacktestGapGuard.is_suspicious(previous, current, max_gap_hours=24) is True


class TestLiveTickDeliveryStateRepository:
    """Tests for execution-state delivery diagnostics persistence."""

    def test_write_current_and_merge_round_trip_payload(self):
        repository = LiveTickDeliveryStateRepository()
        loop = SimpleNamespace(state=SimpleNamespace(strategy_state={}))
        observed_at = datetime(2026, 5, 8, 12, tzinfo=UTC)
        tick_ts = observed_at - timedelta(seconds=2)

        repository.write(
            loop=loop,
            status="ok",
            tick_ts=tick_ts,
            observed_at=observed_at,
            age_seconds=2.1234,
            max_age_seconds=30,
            message="Live tick delivery is current.",
        )

        current = repository.current(loop.state)

        assert current is not None
        assert current["status"] == "ok"
        assert current["age_seconds"] == 2.123

        target = SimpleNamespace(strategy_state={"metrics": {"x": "1"}})
        repository.merge(target, current)

        assert target.strategy_state["metrics"] == {"x": "1"}
        assert target.strategy_state["live_tick_delivery"] == current
