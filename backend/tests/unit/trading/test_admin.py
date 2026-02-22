"""Unit tests for trading admin.py."""

from apps.trading.admin import (
    BacktestTaskAdmin,
    CeleryTaskStatusAdmin,
    EquityAdmin,
    ExecutionStateAdmin,
    LayerAdmin,
    OrderAdmin,
    PositionAdmin,
    StrategyConfigurationAdmin,
    TaskLogAdmin,
    TradeAdmin,
    TradingEventAdmin,
    TradingTaskAdmin,
)


class TestStrategyConfigurationAdmin:
    """Test StrategyConfigurationAdmin configuration."""

    def test_list_display(self):
        assert "id" in StrategyConfigurationAdmin.list_display
        assert "user" in StrategyConfigurationAdmin.list_display
        assert "strategy_type" in StrategyConfigurationAdmin.list_display

    def test_list_filter(self):
        assert "strategy_type" in StrategyConfigurationAdmin.list_filter

    def test_search_fields(self):
        assert "name" in StrategyConfigurationAdmin.search_fields


class TestBacktestTaskAdmin:
    """Test BacktestTaskAdmin configuration."""

    def test_list_display(self):
        assert "id" in BacktestTaskAdmin.list_display
        assert "status" in BacktestTaskAdmin.list_display
        assert "data_source" in BacktestTaskAdmin.list_display

    def test_list_filter(self):
        assert "status" in BacktestTaskAdmin.list_filter
        assert "data_source" in BacktestTaskAdmin.list_filter


class TestTradingTaskAdmin:
    """Test TradingTaskAdmin configuration."""

    def test_list_display(self):
        assert "id" in TradingTaskAdmin.list_display
        assert "status" in TradingTaskAdmin.list_display
        assert "sell_on_stop" in TradingTaskAdmin.list_display

    def test_list_filter(self):
        assert "status" in TradingTaskAdmin.list_filter


class TestCeleryTaskStatusAdmin:
    """Test CeleryTaskStatusAdmin configuration."""

    def test_list_display(self):
        assert "task_name" in CeleryTaskStatusAdmin.list_display
        assert "status" in CeleryTaskStatusAdmin.list_display
        assert "worker" in CeleryTaskStatusAdmin.list_display


class TestTradingEventAdmin:
    """Test TradingEventAdmin configuration."""

    def test_list_display(self):
        assert "event_type" in TradingEventAdmin.list_display
        assert "severity" in TradingEventAdmin.list_display

    def test_list_filter(self):
        assert "severity" in TradingEventAdmin.list_filter
        assert "event_type" in TradingEventAdmin.list_filter


class TestTaskLogAdmin:
    """Test TaskLogAdmin configuration."""

    def test_list_display(self):
        assert "level" in TaskLogAdmin.list_display
        assert "message" in TaskLogAdmin.list_display

    def test_readonly_fields(self):
        assert "message" in TaskLogAdmin.readonly_fields
        assert "details" in TaskLogAdmin.readonly_fields


class TestExecutionStateAdmin:
    """Test ExecutionStateAdmin configuration."""

    def test_list_display(self):
        assert "task_type" in ExecutionStateAdmin.list_display
        assert "task_id" in ExecutionStateAdmin.list_display


class TestOrderAdmin:
    """Test OrderAdmin configuration."""

    def test_list_display(self):
        assert "instrument" in OrderAdmin.list_display
        assert "direction" in OrderAdmin.list_display
        assert "status" in OrderAdmin.list_display


class TestPositionAdmin:
    """Test PositionAdmin configuration."""

    def test_list_display(self):
        assert "instrument" in PositionAdmin.list_display
        assert "entry_price" in PositionAdmin.list_display


class TestTradeAdmin:
    """Test TradeAdmin configuration."""

    def test_list_display(self):
        assert "instrument" in TradeAdmin.list_display
        assert "direction" in TradeAdmin.list_display
        assert "price" in TradeAdmin.list_display


class TestEquityAdmin:
    """Test EquityAdmin configuration."""

    def test_list_display(self):
        assert "balance" in EquityAdmin.list_display
        assert "ticks_processed" in EquityAdmin.list_display


class TestLayerAdmin:
    """Test LayerAdmin configuration."""

    def test_list_display(self):
        assert "index" in LayerAdmin.list_display
        assert "direction" in LayerAdmin.list_display
        assert "is_active" in LayerAdmin.list_display
