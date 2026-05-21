"""Unit tests for trading serializers backtest."""

from unittest.mock import MagicMock

import pytest
from rest_framework import serializers

from apps.trading.enums import TaskStatus
from apps.trading.serializers.backtest import (
    BacktestTaskCreateSerializer,
    BacktestTaskListSerializer,
    BacktestTaskSerializer,
)


class TestBacktestTaskSerializer:
    """Test BacktestTaskSerializer."""

    def test_meta_fields(self):
        fields = BacktestTaskSerializer.Meta.fields
        assert "id" in fields
        assert "status" in fields
        assert "data_source" in fields
        assert "tick_granularity" in fields
        assert "tick_window_value_mode" in fields
        assert "max_tick_gap_hours" in fields
        assert "spread_filter_enabled" in fields
        assert "max_spread_pips" in fields
        assert "oanda_candle_filter_enabled" in fields
        assert "oanda_candle_filter_account" in fields
        assert "oanda_candle_filter_granularity" in fields
        assert "oanda_candle_filter_tolerance_pips" in fields
        assert "start_time" in fields
        assert "end_time" in fields
        assert "initial_balance" in fields
        assert "initial_balance_money" in fields
        assert "progress" not in fields
        assert "current_tick" not in fields
        assert "account_currency" in fields
        assert "display_currency" in fields
        assert "money_context" in fields
        assert "commission_per_trade_money" in fields
        assert "instrument_context" in fields


class TestBacktestTaskListSerializer:
    """Test BacktestTaskListSerializer."""

    def test_meta_fields(self):
        fields = BacktestTaskListSerializer.Meta.fields
        assert "id" in fields
        assert "status" in fields
        assert "data_source" in fields
        assert "tick_granularity" in fields
        assert "tick_window_value_mode" in fields
        assert "max_tick_gap_hours" in fields
        assert "spread_filter_enabled" in fields
        assert "max_spread_pips" in fields
        assert "oanda_candle_filter_enabled" in fields
        assert "oanda_candle_filter_account" in fields
        assert "oanda_candle_filter_granularity" in fields
        assert "oanda_candle_filter_tolerance_pips" in fields
        assert "progress" not in fields
        assert "account_currency" in fields
        assert "display_currency" in fields
        assert "money_context" in fields
        assert "initial_balance_money" in fields
        assert "commission_per_trade" not in fields
        assert "commission_per_trade_money" not in fields
        assert "instrument_context" in fields


class TestBacktestTaskCreateSerializer:
    """Test BacktestTaskCreateSerializer."""

    def test_meta_fields(self):
        fields = BacktestTaskCreateSerializer.Meta.fields
        assert "name" in fields
        assert "config" in fields
        assert "data_source" in fields
        assert "tick_granularity" in fields
        assert "tick_window_value_mode" in fields
        assert "max_tick_gap_hours" in fields
        assert "spread_filter_enabled" in fields
        assert "max_spread_pips" in fields
        assert "oanda_candle_filter_enabled" in fields
        assert "oanda_candle_filter_account" in fields
        assert "oanda_candle_filter_granularity" in fields
        assert "oanda_candle_filter_tolerance_pips" in fields
        assert "start_time" in fields
        assert "end_time" in fields

    def test_update_validation_error_suppresses_exception_chain(self):
        serializer = BacktestTaskCreateSerializer()
        task = MagicMock()
        task.status = TaskStatus.RUNNING

        with pytest.raises(serializers.ValidationError) as exc_info:
            serializer.update(task, {"name": "Updated"})

        assert exc_info.value.__cause__ is None

    def test_validate_excluded_dates_accepts_closed_windows(self):
        serializer = BacktestTaskCreateSerializer()

        result = serializer.validate_excluded_dates(
            [
                {
                    "start": "2024-12-24T16:59:00-05:00",
                    "end": "2024-12-25T17:05:00-05:00",
                    "timezone": "America/New_York",
                }
            ]
        )

        assert result == [
            {
                "start": "2024-12-24T21:59:00Z",
                "end": "2024-12-25T22:05:00Z",
                "timezone": "America/New_York",
            }
        ]

    def test_validate_excluded_dates_rejects_invalid_closed_windows(self):
        serializer = BacktestTaskCreateSerializer()

        with pytest.raises(serializers.ValidationError):
            serializer.validate_excluded_dates(
                [
                    {
                        "start": "2024-12-25T17:05:00-05:00",
                        "end": "2024-12-24T16:59:00-05:00",
                        "timezone": "America/New_York",
                    }
                ]
            )
