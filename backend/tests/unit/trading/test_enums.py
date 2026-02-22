"""Unit tests for trading enums."""

from apps.trading.enums import (
    DataSource,
    Direction,
    EventType,
    FloorSide,
    LogLevel,
    StopMode,
    StrategyType,
    TaskStatus,
    TaskType,
)


class TestDataSource:
    """Test DataSource enum."""

    def test_values(self):
        assert DataSource.POSTGRESQL == "postgresql"
        assert DataSource.ATHENA == "athena"
        assert DataSource.S3 == "s3"

    def test_choices_count(self):
        assert len(DataSource.choices) == 3

    def test_labels(self):
        assert DataSource.POSTGRESQL.label == "PostgreSQL"
        assert DataSource.ATHENA.label == "AWS Athena"
        assert DataSource.S3.label == "AWS S3"


class TestTaskStatus:
    """Test TaskStatus enum."""

    def test_values(self):
        assert TaskStatus.CREATED == "created"
        assert TaskStatus.STARTING == "starting"
        assert TaskStatus.RUNNING == "running"
        assert TaskStatus.PAUSED == "paused"
        assert TaskStatus.STOPPING == "stopping"
        assert TaskStatus.STOPPED == "stopped"
        assert TaskStatus.COMPLETED == "completed"
        assert TaskStatus.FAILED == "failed"

    def test_choices_count(self):
        assert len(TaskStatus.choices) == 8


class TestTaskType:
    """Test TaskType enum."""

    def test_values(self):
        assert TaskType.BACKTEST == "backtest"
        assert TaskType.TRADING == "trading"

    def test_choices_count(self):
        assert len(TaskType.choices) == 2


class TestStopMode:
    """Test StopMode enum."""

    def test_values(self):
        assert StopMode.IMMEDIATE == "immediate"
        assert StopMode.GRACEFUL == "graceful"
        assert StopMode.GRACEFUL_CLOSE == "graceful_close"

    def test_choices_count(self):
        assert len(StopMode.choices) == 3


class TestEventType:
    """Test EventType enum."""

    def test_core_events(self):
        assert EventType.TICK_RECEIVED == "tick_received"
        assert EventType.STRATEGY_SIGNAL == "strategy_signal"
        assert EventType.TRADE_EXECUTED == "trade_executed"

    def test_floor_strategy_events(self):
        assert EventType.INITIAL_ENTRY == "initial_entry"
        assert EventType.RETRACEMENT == "retracement"
        assert EventType.TAKE_PROFIT == "take_profit"

    def test_lifecycle_events(self):
        assert EventType.STRATEGY_STARTED == "strategy_started"
        assert EventType.STRATEGY_STOPPED == "strategy_stopped"

    def test_choices_count(self):
        assert len(EventType.choices) == 17


class TestStrategyType:
    """Test StrategyType enum."""

    def test_values(self):
        assert StrategyType.FLOOR == "floor"
        assert StrategyType.CUSTOM == "custom"

    def test_choices_count(self):
        assert len(StrategyType.choices) == 2


class TestLogLevel:
    """Test LogLevel enum."""

    def test_values(self):
        assert LogLevel.DEBUG == "DEBUG"
        assert LogLevel.INFO == "INFO"
        assert LogLevel.WARNING == "WARNING"
        assert LogLevel.ERROR == "ERROR"
        assert LogLevel.CRITICAL == "CRITICAL"

    def test_choices_count(self):
        assert len(LogLevel.choices) == 5


class TestDirection:
    """Test Direction enum."""

    def test_values(self):
        assert Direction.LONG == "long"
        assert Direction.SHORT == "short"

    def test_choices_count(self):
        assert len(Direction.choices) == 2


class TestFloorSideAlias:
    """Test FloorSide backward compatibility alias."""

    def test_floor_side_is_direction(self):
        assert FloorSide is Direction
