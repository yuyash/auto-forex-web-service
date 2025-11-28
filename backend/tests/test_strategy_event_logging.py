"""
Unit tests for strategy event logging to execution logs.

Tests cover:
- _log_strategy_events_to_execution function
- Floor strategy event types (initial, retracement, close, take_profit, etc.)
- Event deduplication via last_event_index tracking

Requirements: Floor Strategy Enhancements - Task Execution Logs
"""

from typing import Any
from unittest.mock import MagicMock

from trading.services.task_executor import _log_strategy_events_to_execution


class MockExecution:
    """Mock TaskExecution for testing."""

    def __init__(self) -> None:
        self.logs: list[dict[str, Any]] = []

    def add_log(self, level: str, message: str) -> None:
        """Add a log entry."""
        self.logs.append({"level": level, "message": message})


class MockStrategy:
    """Mock strategy with backtest events."""

    def __init__(self, events: list[dict[str, Any]] | None = None) -> None:
        self._backtest_events = events or []


class MockEngine:
    """Mock BacktestEngine for testing."""

    def __init__(self, strategy: MockStrategy | None = None) -> None:
        self.strategy = strategy


class TestLogStrategyEventsToExecution:
    """Tests for _log_strategy_events_to_execution function."""

    def test_returns_zero_when_no_strategy(self):
        """Test returns 0 when engine has no strategy."""
        execution = MockExecution()
        engine = MockEngine(strategy=None)

        result = _log_strategy_events_to_execution(execution, engine, 0)  # type: ignore[arg-type]

        assert result == 0
        assert len(execution.logs) == 0

    def test_returns_zero_when_no_backtest_events(self):
        """Test returns 0 when strategy has no _backtest_events attribute."""
        execution = MockExecution()
        strategy = MagicMock(spec=[])  # No _backtest_events attribute
        engine = MockEngine(strategy=strategy)

        result = _log_strategy_events_to_execution(execution, engine, 0)  # type: ignore[arg-type]

        assert result == 0
        assert len(execution.logs) == 0

    def test_logs_initial_entry_event(self):
        """Test logging of initial entry events."""
        execution = MockExecution()
        strategy = MockStrategy(
            events=[
                {
                    "event_type": "initial_entry",
                    "description": "Initial entry: LONG 1.0 units @ 1.10000",
                    "details": {
                        "event_type": "initial",
                        "direction": "long",
                        "units": "1.0",
                        "price": "1.10000",
                        "layer": 1,
                    },
                }
            ]
        )
        engine = MockEngine(strategy=strategy)

        result = _log_strategy_events_to_execution(execution, engine, 0)  # type: ignore[arg-type]

        assert result == 1
        assert len(execution.logs) == 1
        assert (
            "[FLOOR] Layer 1 Initial Entry: LONG 1.0 units @ 1.10000"
            in execution.logs[0]["message"]
        )

    def test_logs_retracement_event(self):
        """Test logging of retracement events."""
        execution = MockExecution()
        strategy = MockStrategy(
            events=[
                {
                    "event_type": "scale_in",
                    "description": "Retracement: LONG 2.0 units @ 1.09700",
                    "details": {
                        "event_type": "retracement",
                        "direction": "long",
                        "units": "2.0",
                        "price": "1.09700",
                        "layer": 1,
                        "retracement_count": 1,
                    },
                }
            ]
        )
        engine = MockEngine(strategy=strategy)

        result = _log_strategy_events_to_execution(execution, engine, 0)  # type: ignore[arg-type]

        assert result == 1
        assert len(execution.logs) == 1
        assert "[FLOOR] Layer 1 Retracement #1" in execution.logs[0]["message"]
        assert "LONG 2.0 units @ 1.09700" in execution.logs[0]["message"]

    def test_logs_close_event(self):
        """Test logging of close events."""
        execution = MockExecution()
        strategy = MockStrategy(
            events=[
                {
                    "event_type": "strategy_close",
                    "description": "Closing position",
                    "details": {
                        "event_type": "close",
                        "direction": "long",
                        "units": "1.0",
                        "entry_price": "1.10000",
                        "exit_price": "1.10250",
                        "pnl": 25.0,
                        "reason_display": "Take Profit",
                        "layer_number": 1,
                        "entry_retracement_count": 1,
                        "retracement_count": 0,
                    },
                }
            ]
        )
        engine = MockEngine(strategy=strategy)

        result = _log_strategy_events_to_execution(execution, engine, 0)  # type: ignore[arg-type]

        assert result == 1
        assert len(execution.logs) == 1
        assert "[FLOOR] Layer 1 Take Profit" in execution.logs[0]["message"]
        assert "Entry: 1.10000 → Exit: 1.10250" in execution.logs[0]["message"]
        assert "+$25.00" in execution.logs[0]["message"]
        assert "Entry Retracement #1" in execution.logs[0]["message"]
        assert "Remaining Retracements: 0" in execution.logs[0]["message"]

    def test_logs_take_profit_event(self):
        """Test logging of take profit events."""
        execution = MockExecution()
        strategy = MockStrategy(
            events=[
                {
                    "event_type": "take_profit",
                    "description": "Take profit triggered",
                    "details": {
                        "event_type": "take_profit",
                        "direction": "short",
                        "units": "2.0",
                        "entry_price": "1.10500",
                        "exit_price": "1.10250",
                        "pnl": 50.0,
                        "reason_display": "Take Profit",
                        "entry_retracement_count": 2,
                        "retracement_count": 1,
                    },
                }
            ]
        )
        engine = MockEngine(strategy=strategy)

        result = _log_strategy_events_to_execution(execution, engine, 0)  # type: ignore[arg-type]

        assert result == 1
        assert len(execution.logs) == 1
        assert "[FLOOR]" in execution.logs[0]["message"]
        assert "Take Profit" in execution.logs[0]["message"]
        assert "+$50.00" in execution.logs[0]["message"]
        assert "Entry Retracement #2" in execution.logs[0]["message"]
        assert "Remaining Retracements: 1" in execution.logs[0]["message"]

    def test_logs_volatility_lock_event(self):
        """Test logging of volatility lock events."""
        execution = MockExecution()
        strategy = MockStrategy(
            events=[
                {
                    "event_type": "volatility_lock",
                    "description": "Volatility lock triggered",
                    "details": {
                        "event_type": "volatility_lock",
                        "direction": "long",
                        "units": "1.0",
                        "entry_price": "1.10000",
                        "exit_price": "1.09500",
                        "pnl": -50.0,
                        "reason_display": "Volatility Lock",
                        "entry_retracement_count": None,
                        "retracement_count": 3,
                    },
                }
            ]
        )
        engine = MockEngine(strategy=strategy)

        result = _log_strategy_events_to_execution(execution, engine, 0)  # type: ignore[arg-type]

        assert result == 1
        assert len(execution.logs) == 1
        assert "[FLOOR]" in execution.logs[0]["message"]
        assert "Volatility Lock" in execution.logs[0]["message"]
        assert "-$50.00" in execution.logs[0]["message"]

    def test_logs_margin_protection_event(self):
        """Test logging of margin protection events."""
        execution = MockExecution()
        strategy = MockStrategy(
            events=[
                {
                    "event_type": "margin_protection",
                    "description": "Margin protection triggered",
                    "details": {
                        "event_type": "margin_protection",
                        "direction": "long",
                        "units": "3.0",
                        "entry_price": "1.10000",
                        "exit_price": "1.08000",
                        "pnl": -200.0,
                        "reason_display": "Margin Protection",
                    },
                }
            ]
        )
        engine = MockEngine(strategy=strategy)

        result = _log_strategy_events_to_execution(execution, engine, 0)  # type: ignore[arg-type]

        assert result == 1
        assert len(execution.logs) == 1
        assert "[FLOOR]" in execution.logs[0]["message"]
        assert "Margin Protection" in execution.logs[0]["message"]
        assert "-$200.00" in execution.logs[0]["message"]

    def test_logs_layer_retracement_detected_event(self):
        """Test logging of layer/retracement detected events."""
        execution = MockExecution()
        strategy = MockStrategy(
            events=[
                {
                    "event_type": "retracement_detected",
                    "description": "Retracement: 35.5 pips from peak",
                    "details": {
                        "event_type": "layer",
                        "layer": 1,
                        "direction": "long",
                        "retracement_pips": "35.5",
                    },
                }
            ]
        )
        engine = MockEngine(strategy=strategy)

        result = _log_strategy_events_to_execution(execution, engine, 0)  # type: ignore[arg-type]

        assert result == 1
        assert len(execution.logs) == 0

    def test_skips_already_logged_events(self):
        """Test that events before last_event_index are skipped."""
        execution = MockExecution()
        strategy = MockStrategy(
            events=[
                {
                    "event_type": "initial_entry",
                    "description": "First event",
                    "details": {
                        "event_type": "initial",
                        "direction": "long",
                        "units": "1.0",
                        "price": "1.10000",
                        "layer": 1,
                    },
                },
                {
                    "event_type": "scale_in",
                    "description": "Second event",
                    "details": {
                        "event_type": "retracement",
                        "direction": "long",
                        "units": "2.0",
                        "price": "1.09700",
                        "layer": 1,
                        "retracement_count": 1,
                    },
                },
            ]
        )
        engine = MockEngine(strategy=strategy)

        # Start from index 1, should only log the second event
        result = _log_strategy_events_to_execution(execution, engine, 1)  # type: ignore[arg-type]

        assert result == 2
        assert len(execution.logs) == 1
        assert "Retracement #1" in execution.logs[0]["message"]

    def test_logs_multiple_events(self):
        """Test logging of multiple events in sequence."""
        execution = MockExecution()
        strategy = MockStrategy(
            events=[
                {
                    "event_type": "initial_entry",
                    "description": "Initial entry",
                    "details": {
                        "event_type": "initial",
                        "direction": "long",
                        "units": "1.0",
                        "price": "1.10000",
                        "layer": 1,
                    },
                },
                {
                    "event_type": "scale_in",
                    "description": "Retracement",
                    "details": {
                        "event_type": "retracement",
                        "direction": "long",
                        "units": "2.0",
                        "price": "1.09700",
                        "layer": 1,
                        "retracement_count": 1,
                    },
                },
                {
                    "event_type": "strategy_close",
                    "description": "Close",
                    "details": {
                        "event_type": "take_profit",
                        "direction": "long",
                        "units": "1.0",
                        "entry_price": "1.10000",
                        "exit_price": "1.10250",
                        "pnl": 25.0,
                        "reason_display": "Take Profit",
                    },
                },
            ]
        )
        engine = MockEngine(strategy=strategy)

        result = _log_strategy_events_to_execution(execution, engine, 0)  # type: ignore[arg-type]

        assert result == 3
        assert len(execution.logs) == 3
        assert "Initial Entry" in execution.logs[0]["message"]
        assert "Retracement #1" in execution.logs[1]["message"]
        assert "Take Profit" in execution.logs[2]["message"]

    def test_skips_entry_signal_events(self):
        """Test that entry_signal_triggered events are skipped to reduce noise."""
        execution = MockExecution()
        strategy = MockStrategy(
            events=[
                {
                    "event_type": "entry_signal_triggered",
                    "description": "LONG entry: Momentum signal",
                    "details": {"direction": "long", "reason": "Momentum"},
                },
            ]
        )
        engine = MockEngine(strategy=strategy)

        result = _log_strategy_events_to_execution(execution, engine, 0)  # type: ignore[arg-type]

        assert result == 1
        assert len(execution.logs) == 0  # Should be skipped

    def test_skips_no_entry_signal_events(self):
        """Test that no_entry_signal events are skipped."""
        execution = MockExecution()
        strategy = MockStrategy(
            events=[
                {
                    "event_type": "no_entry_signal",
                    "description": "No entry signal yet",
                    "details": {},
                },
            ]
        )
        engine = MockEngine(strategy=strategy)

        result = _log_strategy_events_to_execution(execution, engine, 0)  # type: ignore[arg-type]

        assert result == 1
        assert len(execution.logs) == 0  # Should be skipped

    def test_skips_inactive_instrument_events(self):
        """Test that inactive_instrument events are skipped."""
        execution = MockExecution()
        strategy = MockStrategy(
            events=[
                {
                    "event_type": "inactive_instrument",
                    "description": "Skipping tick for inactive instrument",
                    "details": {},
                },
            ]
        )
        engine = MockEngine(strategy=strategy)

        result = _log_strategy_events_to_execution(execution, engine, 0)  # type: ignore[arg-type]

        assert result == 1
        assert len(execution.logs) == 0  # Should be skipped
