"""Event handler for executing orders based on strategy events."""

from __future__ import annotations

from logging import Logger, getLogger
from typing import TYPE_CHECKING

from apps.trading.enums import Direction
from apps.trading.events import (
    InitialEntryEvent,
    MarginProtectionEvent,
    RetracementEvent,
    StrategyEvent,
    TakeProfitEvent,
    VolatilityLockEvent,
)
from apps.trading.models import Position
from apps.trading.services.order import OrderService, OrderServiceError

if TYPE_CHECKING:
    from apps.trading.models import TradingEvent

logger: Logger = getLogger(__name__)


class EventHandler:
    """Handles strategy events by executing corresponding orders.

    This class bridges the gap between strategy events (trading signals)
    and actual order execution through the OrderService.

    Attributes:
        order_service: Service for executing orders
        instrument: Trading instrument
        position_map: Maps layer numbers to Position instances
    """

    def __init__(self, order_service: OrderService, instrument: str):
        """Initialize event handler.

        Args:
            order_service: OrderService instance for executing trades
            instrument: Trading instrument (e.g., 'EUR_USD')
        """
        self.order_service = order_service
        self.instrument = instrument
        self.position_map: dict[int, Position] = {}  # layer_number -> Position

    def handle_event(self, trading_event: TradingEvent) -> None:
        """Handle a single trading event by executing appropriate order.

        Args:
            trading_event: TradingEvent instance from database

        Raises:
            OrderServiceError: If order execution fails
        """
        # Convert TradingEvent back to StrategyEvent
        strategy_event = StrategyEvent.from_dict(trading_event.details)

        # Dispatch to appropriate handler based on event type
        if isinstance(strategy_event, InitialEntryEvent):
            self.handle_initial_entry(strategy_event)
        elif isinstance(strategy_event, RetracementEvent):
            self.handle_retracement(strategy_event)
        elif isinstance(strategy_event, TakeProfitEvent):
            self.handle_take_profit(strategy_event)
        elif isinstance(strategy_event, VolatilityLockEvent):
            self.handle_volatility_lock(strategy_event)
        elif isinstance(strategy_event, MarginProtectionEvent):
            self.handle_margin_protection(strategy_event)
        # ADD_LAYER and REMOVE_LAYER are informational only, no action needed

    def handle_initial_entry(self, event: InitialEntryEvent) -> Position:
        """Open initial position for a layer.

        Args:
            event: Initial entry event with position details

        Returns:
            Position: Created position

        Raises:
            OrderServiceError: If order execution fails
        """
        direction = Direction(event.direction)
        position = self.order_service.open_position(
            instrument=self.instrument,
            units=event.units,
            direction=direction,
        )

        # Track position by layer number
        self.position_map[event.layer_number] = position

        logger.info(
            "Initial entry executed: layer=%s, direction=%s, units=%s, position_id=%s",
            event.layer_number,
            direction,
            event.units,
            position.id,
        )

        return position

    def handle_retracement(self, event: RetracementEvent) -> Position:
        """Add to existing position (retracement).

        Args:
            event: Retracement event with position details

        Returns:
            Position: Updated or created position

        Raises:
            OrderServiceError: If order execution fails
        """
        direction = Direction(event.direction)
        position = self.order_service.open_position(
            instrument=self.instrument,
            units=event.units,
            direction=direction,
        )

        # Update position map (OrderService handles position merging)
        self.position_map[event.layer_number] = position

        logger.info(
            "Retracement executed: layer=%s, direction=%s, units=%s, count=%s, position_id=%s",
            event.layer_number,
            direction,
            event.units,
            event.retracement_count,
            position.id,
        )

        return position

    def handle_take_profit(self, event: TakeProfitEvent) -> Position | None:
        """Close position for take profit.

        Args:
            event: Take profit event with close details

        Returns:
            Position | None: Closed position, or None if position not found

        Raises:
            OrderServiceError: If order execution fails
        """
        # Find position by layer number
        position = self.position_map.get(event.layer_number)

        if not position:
            # Fallback: find by direction and instrument
            logger.warning(
                "Position not found in map for layer %s, searching by direction",
                event.layer_number,
            )
            positions = self.order_service.get_open_positions(self.instrument)
            direction = Direction(event.direction)
            position = next((p for p in positions if p.direction == direction), None)

        if not position:
            logger.error(
                "Cannot close position: no open position found for layer %s, direction %s",
                event.layer_number,
                event.direction,
            )
            return None

        # Close position (full or partial based on units)
        units_to_close = event.units if event.units > 0 else None
        closed_position = self.order_service.close_position(
            position=position,
            units=units_to_close,
        )

        # Remove from map if fully closed
        if not closed_position.is_open:
            self.position_map.pop(event.layer_number, None)
            logger.info(
                "Take profit executed (full close): layer=%s, pnl=%s, position_id=%s",
                event.layer_number,
                closed_position.realized_pnl,
                closed_position.id,
            )
        else:
            logger.info(
                "Take profit executed (partial close): layer=%s, units_closed=%s, remaining=%s, position_id=%s",
                event.layer_number,
                units_to_close,
                abs(closed_position.units),
                closed_position.id,
            )

        return closed_position

    def handle_volatility_lock(self, event: VolatilityLockEvent) -> list[Position]:
        """Close all open positions due to volatility.

        Args:
            event: Volatility lock event

        Returns:
            list[Position]: List of closed positions

        Raises:
            OrderServiceError: If order execution fails
        """
        closed_positions: list[Position] = []

        logger.warning(
            "Volatility lock triggered: %s (closing %s positions)",
            event.reason,
            len(self.position_map),
        )

        # Close all tracked positions
        for layer_number, position in list(self.position_map.items()):
            if position.is_open:
                try:
                    closed = self.order_service.close_position(position)
                    closed_positions.append(closed)
                    logger.info(
                        "Closed position due to volatility: layer=%s, position_id=%s, pnl=%s",
                        layer_number,
                        closed.id,
                        closed.realized_pnl,
                    )
                except OrderServiceError as e:
                    logger.error(
                        "Failed to close position %s during volatility lock: %s",
                        position.id,
                        e,
                    )
                    # Continue closing other positions

        # Clear position map
        self.position_map.clear()

        logger.info("Volatility lock complete: closed %s positions", len(closed_positions))

        return closed_positions

    def handle_margin_protection(self, event: MarginProtectionEvent) -> list[Position]:
        """Close all open positions due to margin protection.

        Args:
            event: Margin protection event

        Returns:
            list[Position]: List of closed positions

        Raises:
            OrderServiceError: If order execution fails
        """
        closed_positions: list[Position] = []

        logger.warning(
            "Margin protection triggered: %s (closing %s positions)",
            event.reason,
            len(self.position_map),
        )

        # Close all tracked positions
        for layer_number, position in list(self.position_map.items()):
            if position.is_open:
                try:
                    closed = self.order_service.close_position(position)
                    closed_positions.append(closed)
                    logger.info(
                        "Closed position due to margin protection: layer=%s, position_id=%s, pnl=%s",
                        layer_number,
                        closed.id,
                        closed.realized_pnl,
                    )
                except OrderServiceError as e:
                    logger.error(
                        "Failed to close position %s during margin protection: %s",
                        position.id,
                        e,
                    )
                    # Continue closing other positions

        # Clear position map
        self.position_map.clear()

        logger.info("Margin protection complete: closed %s positions", len(closed_positions))

        return closed_positions

    def get_open_positions(self) -> list[Position]:
        """Get all currently tracked open positions.

        Returns:
            list[Position]: List of open positions
        """
        return [p for p in self.position_map.values() if p.is_open]

    def clear_positions(self) -> None:
        """Clear the position map.

        Useful for cleanup or reset operations.
        """
        self.position_map.clear()
        logger.debug("Position map cleared")
