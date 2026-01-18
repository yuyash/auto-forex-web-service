"""Unit tests for trading enums."""

from apps.trading.enums import (
    DataSource,
    EventType,
    LogLevel,
    StopMode,
    StrategyType,
    TaskStatus,
    TaskType,
    TradingMode,
)


class TestTaskType:
    """Test TaskType enum."""

    def test_task_type_values(self):
        """Test TaskType has expected values."""
        assert TaskType.BACKTEST == "backtest"
        assert TaskType.TRADING == "trading"

    def test_task_type_choices(self):
        """Test TaskType choices."""
        choices = TaskType.choices
        assert len(choices) == 2


class TestTaskStatus:
    """Test TaskStatus enum."""

    def test_task_status_values(self):
        """Test TaskStatus has expected values."""
        assert TaskStatus.STOPPED == "stopped"
        assert TaskStatus.RUNNING == "running"
        assert TaskStatus.CREATED == "created"
        assert TaskStatus.COMPLETED == "completed"
        assert TaskStatus.FAILED == "failed"

    def test_task_status_choices(self):
        """Test TaskStatus choices."""
        choices = TaskStatus.choices
        assert len(choices) >= 5


class TestDataSource:
    """Test DataSource enum."""

    def test_data_source_values(self):
        """Test DataSource has expected values."""
        assert DataSource.ATHENA == "athena"
        assert DataSource.POSTGRESQL == "postgresql"
        assert DataSource.S3 == "s3"

    def test_data_source_choices(self):
        """Test DataSource choices."""
        choices = DataSource.choices
        assert len(choices) >= 3


class TestStopMode:
    """Test StopMode enum."""

    def test_stop_mode_values(self):
        """Test StopMode has expected values."""
        assert StopMode.IMMEDIATE == "immediate"
        assert StopMode.GRACEFUL == "graceful"
        assert hasattr(StopMode, "GRACEFUL_CLOSE")

    def test_stop_mode_choices(self):
        """Test StopMode choices."""
        choices = StopMode.choices
        assert len(choices) >= 3


class TestEventType:
    """Test EventType enum."""

    def test_event_type_values(self):
        """Test EventType has expected values."""
        assert EventType.TICK_RECEIVED == "tick_received"
        assert EventType.TRADE_EXECUTED == "trade_executed"
        assert EventType.INITIAL_ENTRY == "initial_entry"
        assert EventType.TAKE_PROFIT == "take_profit"

    def test_event_type_choices(self):
        """Test EventType choices."""
        choices = EventType.choices
        assert len(choices) > 10  # Many event types


class TestStrategyType:
    """Test StrategyType enum."""

    def test_strategy_type_values(self):
        """Test StrategyType has expected values."""
        assert StrategyType.FLOOR == "floor"
        assert StrategyType.CUSTOM == "custom"

    def test_strategy_type_choices(self):
        """Test StrategyType choices."""
        choices = StrategyType.choices
        assert len(choices) >= 2


class TestLogLevel:
    """Test LogLevel enum."""

    def test_log_level_values(self):
        """Test LogLevel has expected values."""
        assert LogLevel.DEBUG == "DEBUG"
        assert LogLevel.INFO == "INFO"
        assert LogLevel.WARNING == "WARNING"
        assert LogLevel.ERROR == "ERROR"
        assert LogLevel.CRITICAL == "CRITICAL"

    def test_log_level_choices(self):
        """Test LogLevel choices."""
        choices = LogLevel.choices
        assert len(choices) >= 5


class TestTradingMode:
    """Test TradingMode enum."""

    def test_trading_mode_values(self):
        """Test TradingMode has expected values."""
        assert TradingMode.NETTING == "netting"
        assert TradingMode.HEDGING == "hedging"

    def test_trading_mode_choices(self):
        """Test TradingMode choices."""
        choices = TradingMode.choices
        assert len(choices) >= 2
