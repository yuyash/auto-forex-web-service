"""apps.trading.services.events

Event emission service for task execution.

This module provides the EventEmitter class which handles emitting and
persisting events during task execution for tracking and monitoring.
"""

from datetime import datetime
from typing import Any

from django.utils import timezone

from apps.trading.dataclasses import EventContext, Tick
from apps.trading.models import ExecutionStrategyEvent


# Backward compatibility alias for legacy code
class TradingEventService:
    """Legacy event service for backward compatibility.

    This class exists to maintain compatibility with existing code
    that hasn't been refactored yet. New code should use EventEmitter directly.

    This is a no-op implementation that doesn't actually log events,
    since the old event logging system is being replaced by the new
    EventEmitter system.
    """

    def log_event(
        self, event_type: str, severity: str, details: dict[str, Any] | None = None, **kwargs: Any
    ) -> None:
        """No-op log_event for backward compatibility.

        This method exists to prevent errors in legacy code that hasn't
        been refactored yet. It doesn't actually log events.

        Args:
            event_type: Type of event
            severity: Event severity level
            details: Optional event details
            **kwargs: Additional keyword arguments (ignored)
        """
        # No-op - legacy code will be refactored to use EventEmitter
        pass


class EventEmitter:
    """Emits and persists events during task execution.

    The EventEmitter is responsible for emitting various types of events
    that occur during task execution and persisting them to the database
    using the ExecutionStrategyEvent model. Events are assigned monotonically
    increasing sequence numbers for ordering.

    Attributes:
        context: EventContext containing execution, user, account, and instrument info

    Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6
    """

    def __init__(self, context: EventContext) -> None:
        """Initialize the EventEmitter with an EventContext.

        Args:
            context: EventContext containing execution and related information
        """
        self.context = context

    def emit_tick_received(self, tick: Tick) -> ExecutionStrategyEvent:
        """Emit a tick_received event.

        Called when a tick is received from the market data stream.

        Args:
            tick: Tick dataclass containing market data

        Returns:
            ExecutionStrategyEvent: The created event record

        Requirements: 1.1
        """
        event_data = {
            "type": "tick_received",
            "instrument": tick.instrument,
            "timestamp": tick.timestamp,
            "bid": tick.bid,
            "ask": tick.ask,
            "mid": tick.mid,
        }

        return self._persist_event(
            event_type="tick_received",
            event_data=event_data,
            timestamp=self._parse_timestamp(tick.timestamp),
        )

    def emit_strategy_event(
        self,
        event_type: str,
        strategy_type: str,
        event_data: dict[str, Any],
        timestamp: str | None = None,
    ) -> ExecutionStrategyEvent:
        """Emit a strategy-specific event.

        Called when a strategy generates a signal or other strategy-specific event.

        Args:
            event_type: Type of strategy event (e.g., "signal", "layer_added")
            strategy_type: Strategy type identifier (e.g., "floor", "momentum")
            event_data: Strategy-specific event data dictionary
            timestamp: Optional ISO format timestamp, defaults to current time

        Returns:
            ExecutionStrategyEvent: The created event record

        Requirements: 1.2
        """
        # Ensure event_data has a type field
        full_event_data = {
            "type": event_type,
            **event_data,
        }

        parsed_timestamp = self._parse_timestamp(timestamp) if timestamp else timezone.now()

        return self._persist_event(
            event_type=event_type,
            event_data=full_event_data,
            strategy_type=strategy_type,
            timestamp=parsed_timestamp,
        )

    def emit_trade_executed(
        self,
        trade_data: dict[str, Any],
        timestamp: str | None = None,
    ) -> ExecutionStrategyEvent:
        """Emit a trade_executed event.

        Called when a trade is executed (opened or closed).

        Args:
            trade_data: Trade information dictionary containing:
                - direction: "long" or "short"
                - units: Number of units
                - price: Execution price
                - order_id: Order identifier (optional)
                - position_id: Position identifier (optional)
                - pnl: Profit/loss if closing (optional)
            timestamp: Optional ISO format timestamp, defaults to current time

        Returns:
            ExecutionStrategyEvent: The created event record

        Requirements: 1.3
        """
        event_data = {
            "type": "trade_executed",
            "instrument": self.context.instrument,
            **trade_data,
        }

        parsed_timestamp = self._parse_timestamp(timestamp) if timestamp else timezone.now()

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
    ) -> ExecutionStrategyEvent:
        """Emit a status_changed event.

        Called when the task execution status transitions.

        Args:
            from_status: Previous status
            to_status: New status
            reason: Optional reason for the status change

        Returns:
            ExecutionStrategyEvent: The created event record

        Requirements: 1.4
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
    ) -> ExecutionStrategyEvent:
        """Emit an error event.

        Called when an error occurs during execution.

        Args:
            error: Exception that occurred
            error_context: Optional context information about where/when error occurred

        Returns:
            ExecutionStrategyEvent: The created event record

        Requirements: 1.5
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
    ) -> ExecutionStrategyEvent:
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

        Requirements: 1.6
        """
        # Get the next sequence number
        sequence = self._next_event_sequence()

        # Create and save the event
        event = ExecutionStrategyEvent.objects.create(
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
            ExecutionStrategyEvent.objects.filter(execution=self.context.execution)
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
