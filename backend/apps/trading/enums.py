"""
Enums for trading models.

This module contains enum definitions for:
- DataSource: Data source options for backtesting
- TaskStatus: Task lifecycle states
- TaskType: Types of tasks (backtest or trading)
"""

from django.db import models


class DataSource(models.TextChoices):
    """
    Data source options for backtesting.
    """

    POSTGRESQL = "postgresql", "PostgreSQL"
    ATHENA = "athena", "AWS Athena"
    S3 = "s3", "AWS S3"


class TaskStatus(models.TextChoices):
    """
    Task lifecycle states.
    """

    CREATED = "created", "Created"
    RUNNING = "running", "Running"
    PAUSED = "paused", "Paused"
    STOPPED = "stopped", "Stopped"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"


class TaskType(models.TextChoices):
    """
    Types of tasks.
    """

    BACKTEST = "backtest", "Backtest"
    TRADING = "trading", "Trading"


class StopMode(models.TextChoices):
    """
    Stop modes for trading tasks.

    - IMMEDIATE: Stop immediately without closing positions (fastest)
    - GRACEFUL: Stop gracefully, wait for pending operations to complete
    - GRACEFUL_CLOSE: Stop gracefully and close all open positions
    """

    IMMEDIATE = "immediate", "Immediate Stop"
    GRACEFUL = "graceful", "Graceful Stop (Keep Positions)"
    GRACEFUL_CLOSE = "graceful_close", "Graceful Stop (Close Positions)"


class EventType(models.TextChoices):
    """
    Types of strategy events.

    These events are emitted by strategies during execution to track
    significant occurrences like opening positions, closing positions,
    and other strategy-specific actions.
    """

    # Core events
    TICK_RECEIVED = "tick_received", "Tick Received"
    STRATEGY_SIGNAL = "strategy_signal", "Strategy Signal"
    TRADE_EXECUTED = "trade_executed", "Trade Executed"
    STATUS_CHANGED = "status_changed", "Status Changed"
    ERROR_OCCURRED = "error_occurred", "Error Occurred"

    # Floor strategy events
    INITIAL_ENTRY = "initial_entry", "Initial Entry"
    RETRACEMENT = "retracement", "Retracement"
    TAKE_PROFIT = "take_profit", "Take Profit"
    ADD_LAYER = "add_layer", "Add Layer"
    REMOVE_LAYER = "remove_layer", "Remove Layer"
    VOLATILITY_LOCK = "volatility_lock", "Volatility Lock"
    MARGIN_PROTECTION = "margin_protection", "Margin Protection"

    # Lifecycle events
    STRATEGY_STARTED = "strategy_started", "Strategy Started"
    STRATEGY_PAUSED = "strategy_paused", "Strategy Paused"
    STRATEGY_RESUMED = "strategy_resumed", "Strategy Resumed"
    STRATEGY_STOPPED = "strategy_stopped", "Strategy Stopped"


class StrategyType(models.TextChoices):
    """
    Types of trading strategies.

    Identifies the strategy algorithm being used for trading decisions.
    """

    FLOOR = "floor", "Floor Strategy"
    CUSTOM = "custom", "Custom Strategy"


class LogLevel(models.TextChoices):
    """
    Log levels for execution logs.

    Standard log levels used in execution logging to indicate
    the severity or type of log message.
    """

    DEBUG = "DEBUG", "Debug"
    INFO = "INFO", "Info"
    WARNING = "WARNING", "Warning"
    ERROR = "ERROR", "Error"
    CRITICAL = "CRITICAL", "Critical"


class TradingMode(models.TextChoices):
    """
    Trading modes for position management.

    - NETTING: Positions are aggregated per instrument (FIFO for partial closes)
    - HEDGING: Multiple independent trades can exist per instrument
    """

    NETTING = "netting", "Netting Mode"
    HEDGING = "hedging", "Hedging Mode"
