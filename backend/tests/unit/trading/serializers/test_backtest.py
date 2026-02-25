"""Unit tests for trading serializers backtest."""

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
        assert "start_time" in fields
        assert "end_time" in fields
        assert "initial_balance" in fields
        assert "progress" not in fields
        assert "current_tick" not in fields
        assert "account_currency" not in fields


class TestBacktestTaskListSerializer:
    """Test BacktestTaskListSerializer."""

    def test_meta_fields(self):
        fields = BacktestTaskListSerializer.Meta.fields
        assert "id" in fields
        assert "status" in fields
        assert "data_source" in fields
        assert "progress" not in fields
        assert "account_currency" not in fields


class TestBacktestTaskCreateSerializer:
    """Test BacktestTaskCreateSerializer."""

    def test_meta_fields(self):
        fields = BacktestTaskCreateSerializer.Meta.fields
        assert "name" in fields
        assert "config" in fields
        assert "data_source" in fields
        assert "start_time" in fields
        assert "end_time" in fields
