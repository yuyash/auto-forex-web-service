"""
Enums for trading models.

This module contains enum definitions for:
- DataSource: Data source options for backtesting
- TaskStatus: Task lifecycle states
- TaskType: Types of tasks (backtest or trading)
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

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
    STARTING = "starting", "Starting"
    RUNNING = "running", "Running"
    PAUSED = "paused", "Paused"
    STOPPING = "stopping", "Stopping"
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
    OPEN_POSITION = "open_position", "Open Position"
    CLOSE_POSITION = "close_position", "Close Position"
    ADD_LAYER = "add_layer", "Add Layer"
    REMOVE_LAYER = "remove_layer", "Remove Layer"
    VOLATILITY_LOCK = "volatility_lock", "Volatility Lock"
    VOLATILITY_HEDGE_NEUTRALIZE = "volatility_hedge_neutralize", "Volatility Hedge Neutralize"
    MARGIN_PROTECTION = "margin_protection", "Margin Protection"

    # Lifecycle events
    STRATEGY_STARTED = "strategy_started", "Strategy Started"
    STRATEGY_PAUSED = "strategy_paused", "Strategy Paused"
    STRATEGY_RESUMED = "strategy_resumed", "Strategy Resumed"
    STRATEGY_STOPPED = "strategy_stopped", "Strategy Stopped"

    @classmethod
    def _normalize(cls, event_type: str | "EventType") -> str:
        return str(getattr(event_type, "value", event_type or "")).strip().lower()

    @classmethod
    def metadata_for(
        cls,
        event_type: str | "EventType",
        *,
        details: dict[str, object] | None = None,
    ) -> "EventTypeMetadata":
        normalized = cls._normalize(event_type)
        details_dict = details if isinstance(details, dict) else {}
        kind = str(details_dict.get("kind", "")).strip().lower()

        if kind.startswith("task_"):
            return EventTypeMetadata(scope="task", requires_execution=False)

        return EVENT_TYPE_METADATA.get(
            normalized,
            EventTypeMetadata(scope="strategy", requires_execution=False),
        )

    @classmethod
    def scope_of(
        cls,
        event_type: str | "EventType",
        *,
        details: dict[str, object] | None = None,
    ) -> str:
        return cls.metadata_for(event_type, details=details).scope

    @classmethod
    def requires_execution(cls, event_type: str | "EventType") -> bool:
        return cls.metadata_for(event_type).requires_execution

    @classmethod
    def values_for_scope(cls, scope: str) -> set[str]:
        normalized_scope = str(scope).strip().lower()
        return {
            event_type
            for event_type, meta in EVENT_TYPE_METADATA.items()
            if meta.scope == normalized_scope
        }

    @classmethod
    def task_scoped_values(cls) -> set[str]:
        return cls.values_for_scope("task")

    @classmethod
    def execution_event_type_for(cls, event_type: str | "EventType") -> str:
        normalized = cls._normalize(event_type)
        return EXECUTION_EVENT_TYPE_ALIASES.get(normalized, normalized)


class EventScope(models.TextChoices):
    """Scope where an event belongs."""

    TRADING = "trading", "Trading"
    TASK = "task", "Task"
    STRATEGY = "strategy", "Strategy"


@dataclass(frozen=True, slots=True)
class EventTypeMetadata:
    """Static metadata used to classify event routing and handling."""

    scope: str
    requires_execution: bool = False


def _build_event_metadata() -> dict[str, EventTypeMetadata]:
    by_scope: dict[EventScope, Iterable[EventType]] = {
        EventScope.TRADING: (
            EventType.OPEN_POSITION,
            EventType.CLOSE_POSITION,
            EventType.VOLATILITY_LOCK,
            EventType.VOLATILITY_HEDGE_NEUTRALIZE,
            EventType.MARGIN_PROTECTION,
        ),
        EventScope.TASK: (
            EventType.STATUS_CHANGED,
            EventType.STRATEGY_STARTED,
            EventType.STRATEGY_PAUSED,
            EventType.STRATEGY_RESUMED,
            EventType.STRATEGY_STOPPED,
        ),
        EventScope.STRATEGY: (
            EventType.TICK_RECEIVED,
            EventType.STRATEGY_SIGNAL,
            EventType.TRADE_EXECUTED,
            EventType.ERROR_OCCURRED,
            EventType.INITIAL_ENTRY,
            EventType.RETRACEMENT,
            EventType.TAKE_PROFIT,
            EventType.ADD_LAYER,
            EventType.REMOVE_LAYER,
        ),
    }
    metadata: dict[str, EventTypeMetadata] = {}
    for scope, event_types in by_scope.items():
        for event_type in event_types:
            metadata[event_type.value] = EventTypeMetadata(
                scope=scope.value,
                requires_execution=(scope == EventScope.TRADING),
            )
    return metadata


EVENT_TYPE_METADATA = _build_event_metadata()

EXECUTION_EVENT_TYPE_ALIASES: dict[str, str] = {
    "initial_entry": "open_position",
    "retracement": "open_position",
    "take_profit": "close_position",
}

for _source, _target in EXECUTION_EVENT_TYPE_ALIASES.items():
    if _source in EVENT_TYPE_METADATA:
        _meta = EVENT_TYPE_METADATA[_source]
        EVENT_TYPE_METADATA[_source] = EventTypeMetadata(
            scope=_meta.scope,
            requires_execution=True,
        )


class StrategyType(models.TextChoices):
    """
    Types of trading strategies.

    Identifies the strategy algorithm being used for trading decisions.
    """

    FLOOR = "floor", "Floor Strategy"
    SNOWBALL = "snowball", "Snowball Strategy"
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


class Direction(models.TextChoices):
    """
    Trading direction for positions and orders.

    - LONG: Long positions (buy)
    - SHORT: Short positions (sell)
    """

    LONG = "long", "Long"
    SHORT = "short", "Short"


# Deprecated: Use Direction instead
FloorSide = Direction  # Backward compatibility alias
