"""apps.trading.services.events

Event emission service for task execution.

This module provides the EventEmitter class which handles emitting and
persisting events during task execution for tracking and monitoring.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from django.utils import timezone

from apps.trading.dataclasses import EventContext, Tick, TradeData
from apps.trading.enums import StrategyType
from apps.trading.events import StrategyEvent

if TYPE_CHECKING:
    pass
else:
    # Import at runtime for database operations
    from apps.trading.models import StrategyEvents


class EventEmitter:
    """Emits and persists events during task execution.

    The EventEmitter is responsible for emitting various types of events
    that occur during task execution and persisting them to the database
    using the ExecutionStrategyEvent model. Events are assigned monotonically
    increasing sequence numbers for ordering.

    Attributes:
        context: EventContext containing execution, user, account, and instrument info
    """

    def __init__(self, context: EventContext) -> None:
        """Initialize the EventEmitter with an EventContext.

        Args:
            context: EventContext containing execution and related information
        """
        self.context = context

    def emit_tick_received(self, tick: Tick) -> StrategyEvents:
        """Emit a tick_received event.

        Called when a tick is received from the market data stream.

        Args:
            tick: Tick dataclass containing market data

        Returns:
            ExecutionStrategyEvent: The created event record
        """
        event_data = {
            "type": "tick_received",
            "instrument": tick.instrument,
            "timestamp": (
                tick.timestamp.isoformat()
                if hasattr(tick.timestamp, "isoformat")
                else str(tick.timestamp)
            ),
            "bid": str(tick.bid) if tick.bid is not None else None,
            "ask": str(tick.ask) if tick.ask is not None else None,
            "mid": str(tick.mid) if tick.mid is not None else None,
        }

        return self._persist_event(
            event_type="tick_received",
            event_data=event_data,
            timestamp=tick.timestamp,
        )

    def emit_strategy_event(
        self,
        event: StrategyEvent,
        strategy_type: StrategyType,
    ) -> StrategyEvents:
        """Emit a strategy-specific event.

        Called when a strategy generates a signal or other strategy-specific event.

        Args:
            event: StrategyEvent object containing event data
            strategy_type: Strategy type enum value (e.g., StrategyType.FLOOR)

        Returns:
            ExecutionStrategyEvent: The created event record
        """
        # Convert StrategyEvent to dict for database storage
        event_data = event.to_dict()

        # event.timestamp is already a datetime object, use it directly
        parsed_timestamp = event.timestamp if event.timestamp else timezone.now()

        return self._persist_event(
            event_type=event.event_type,
            event_data=event_data,
            strategy_type=strategy_type.value,  # Use enum value for database storage
            timestamp=parsed_timestamp,
        )

    def emit_trade_executed(
        self,
        trade: TradeData,
    ) -> StrategyEvents:
        """Emit a trade_executed event.

        Called when a trade is executed (opened or closed).

        Args:
            trade: TradeData object containing trade information

        Returns:
            ExecutionStrategyEvent: The created event record
        """
        # Convert TradeData to dict and add instrument
        event_data = {
            "type": "trade_executed",
            "instrument": self.context.instrument,
            **trade.to_dict(),
        }

        # trade.timestamp is already a datetime object, use it directly
        parsed_timestamp = trade.timestamp if trade.timestamp else timezone.now()

        return self._persist_event(
            event_type="trade_executed",
            event_data=event_data,
            timestamp=parsed_timestamp,
        )

    def emit_status_changed(
        self,
        from_status: str,
        to_status: str,
        reason: str = "",
    ) -> StrategyEvents:
        """Emit a status_changed event.

        Called when the task execution status transitions.

        Args:
            from_status: Previous status
            to_status: New status
            reason: Optional reason for the status change

        Returns:
            ExecutionStrategyEvent: The created event record
        """
        event_data = {
            "type": "status_changed",
            "from_status": from_status,
            "to_status": to_status,
            "reason": reason,
        }

        return self._persist_event(
            event_type="status_changed",
            event_data=event_data,
            timestamp=timezone.now(),
        )

    def emit_error(
        self,
        error: Exception,
        error_context: dict[str, Any] | None = None,
    ) -> StrategyEvents:
        """Emit an error event.

        Called when an error occurs during execution.

        Args:
            error: Exception that occurred
            error_context: Optional context information about where/when error occurred

        Returns:
            ExecutionStrategyEvent: The created event record
        """
        event_data = {
            "type": "error_occurred",
            "error_type": type(error).__name__,
            "error_message": str(error),
            "context": error_context or {},
        }

        return self._persist_event(
            event_type="error_occurred",
            event_data=event_data,
            timestamp=timezone.now(),
        )

    def _persist_event(
        self,
        event_type: str,
        event_data: dict[str, Any],
        timestamp: datetime,
        strategy_type: str = "",
    ) -> StrategyEvents:
        """Persist an event to the database with sequence number.

        Creates an ExecutionStrategyEvent record with a monotonically
        increasing sequence number.

        Args:
            event_type: Type of event for filtering
            event_data: Event data dictionary
            timestamp: Event timestamp
            strategy_type: Optional strategy type identifier

        Returns:
            ExecutionStrategyEvent: The created event record
        """
        # Get the next sequence number
        sequence = self._next_event_sequence()

        # Create and save the event
        event = StrategyEvents.objects.create(
            execution=self.context.execution,
            sequence=sequence,
            event_type=event_type,
            strategy_type=strategy_type,
            timestamp=timestamp,
            event=event_data,
        )

        return event

    def _next_event_sequence(self) -> int:
        """Get the next sequence number for an event.

        Queries the database for the highest sequence number and returns
        the next value. Starts at 0 if no events exist.

        Returns:
            int: Next sequence number
        """
        last_event = (
            StrategyEvents.objects.filter(execution=self.context.execution)
            .order_by("-sequence")
            .first()
        )

        if last_event is None:
            return 0

        return last_event.sequence + 1

    def _parse_timestamp(self, timestamp_str: str) -> datetime:
        """Parse an ISO format timestamp string to datetime.

        Args:
            timestamp_str: ISO format timestamp string

        Returns:
            datetime: Parsed datetime object (timezone-aware)
        """
        # Try parsing with timezone info first
        try:
            return datetime.fromisoformat(timestamp_str)
        except ValueError:
            # If that fails, parse without timezone and make it aware
            dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                return timezone.make_aware(dt)
            return dt
