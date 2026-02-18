"""Event handler for executing orders based on strategy events."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from logging import Logger, getLogger

from apps.trading.enums import Direction
from apps.trading.events import (
    InitialEntryEvent,
    MarginProtectionEvent,
    RetracementEvent,
    StrategyEvent,
    TakeProfitEvent,
    VolatilityLockEvent,
)
from apps.trading.models import Position, Trade, TradingEvent
from apps.trading.order import OrderService, OrderServiceError

logger: Logger = getLogger(name=__name__)


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
        self.layer_position_ids: dict[int, list[str]] = defaultdict(list)
        self._position_cache: dict[str, Position] = {}

    @property
    def _task_pk(self):
        return self.order_service.task.id

    def _cache_position(self, layer_number: int, position: Position) -> None:
        pos_id = str(position.id)
        if pos_id not in self.layer_position_ids[layer_number]:
            self.layer_position_ids[layer_number].append(pos_id)
        self._position_cache[pos_id] = position
        self.position_map[layer_number] = position

    def _get_open_position_by_id(self, position_id: str) -> Position | None:
        cached = self._position_cache.get(position_id)
        if cached and cached.is_open:
            return cached
        position = (
            Position.objects.filter(
                id=position_id,
                task_type=self.order_service.task_type,
                task_id=self._task_pk,
                is_open=True,
            )
            .order_by("-entry_time")
            .first()
        )
        if position:
            self._position_cache[position_id] = position
        return position

    def _rehydrate_layer_positions(self, layer_number: int) -> None:
        if self.layer_position_ids.get(layer_number):
            return
        open_positions = list(
            Position.objects.filter(
                task_type=self.order_service.task_type,
                task_id=self._task_pk,
                instrument=self.instrument,
                is_open=True,
                layer_index=layer_number,
            ).order_by("entry_time", "created_at")
        )
        if not open_positions:
            return
        self.layer_position_ids[layer_number] = [str(p.id) for p in open_positions]
        for position in open_positions:
            self._position_cache[str(position.id)] = position
        self.position_map[layer_number] = open_positions[-1]

    def _find_take_profit_target(self, event: TakeProfitEvent) -> Position | None:
        layer_number = event.layer_number
        self._rehydrate_layer_positions(layer_number)
        stack = self.layer_position_ids.get(layer_number, [])
        while stack:
            candidate_id = stack[-1]  # LIFO for TP (newest first)
            candidate = self._get_open_position_by_id(candidate_id)
            if candidate:
                return candidate
            stack.pop()

        direction = Direction(event.direction)
        fallback = (
            Position.objects.filter(
                task_type=self.order_service.task_type,
                task_id=self._task_pk,
                instrument=self.instrument,
                direction=direction,
                is_open=True,
                layer_index=layer_number,
            )
            .order_by("-entry_time")
            .first()
        )
        return fallback

    def _prune_closed_position(self, layer_number: int, position: Position) -> None:
        pos_id = str(position.id)
        self._position_cache[pos_id] = position
        if position.is_open:
            self.position_map[layer_number] = position
            return

        ids = self.layer_position_ids.get(layer_number, [])
        if pos_id in ids:
            ids.remove(pos_id)
        if not ids:
            self.layer_position_ids.pop(layer_number, None)
            self.position_map.pop(layer_number, None)
            return
        replacement = self._get_open_position_by_id(ids[-1])
        if replacement:
            self.position_map[layer_number] = replacement
        else:
            self.position_map.pop(layer_number, None)

    def _ordered_positions_for_margin_close(self) -> list[Position]:
        open_positions = list(
            Position.objects.filter(
                task_type=self.order_service.task_type,
                task_id=self._task_pk,
                instrument=self.instrument,
                is_open=True,
            ).order_by("layer_index", "entry_time", "created_at")
        )
        for position in open_positions:
            self._cache_position(position.layer_index or 0, position)
        return open_positions

    def _record_trade(
        self,
        *,
        direction: Direction,
        units: int,
        instrument: str,
        price: Decimal,
        execution_method: str,
        timestamp,
        layer_index: int | None = None,
        pnl: Decimal | None = None,
        open_price: Decimal | None = None,
        open_timestamp=None,
        close_price: Decimal | None = None,
        close_timestamp=None,
    ) -> None:
        Trade.objects.create(
            task_type=self.order_service.task_type.value,
            task_id=self._task_pk,
            celery_task_id=self.order_service.task.celery_task_id,
            timestamp=timestamp,
            direction=direction.value,
            units=units,
            instrument=instrument,
            price=price,
            execution_method=execution_method,
            layer_index=layer_index,
            pnl=pnl,
            open_price=open_price,
            open_timestamp=open_timestamp,
            close_price=close_price,
            close_timestamp=close_timestamp,
        )

    def handle_event(self, trading_event: TradingEvent) -> Decimal:
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
            return Decimal("0")
        if isinstance(strategy_event, RetracementEvent):
            self.handle_retracement(strategy_event)
            return Decimal("0")
        if isinstance(strategy_event, TakeProfitEvent):
            return self.handle_take_profit(strategy_event)
        if isinstance(strategy_event, VolatilityLockEvent):
            return self.handle_volatility_lock(strategy_event)
        if isinstance(strategy_event, MarginProtectionEvent):
            return self.handle_margin_protection(strategy_event)
        # ADD_LAYER and REMOVE_LAYER are informational only, no pnl impact.
        return Decimal("0")

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
            layer_index=event.layer_number,
            merge_with_existing=False,
        )

        self._cache_position(event.layer_number, position)
        self._record_trade(
            direction=direction,
            units=event.units,
            instrument=position.instrument,
            price=position.entry_price,
            execution_method=str(event.event_type.value),
            timestamp=event.timestamp,
            layer_index=event.layer_number,
            open_price=position.entry_price,
            open_timestamp=event.timestamp,
        )

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
            layer_index=event.layer_number,
            merge_with_existing=False,
        )

        self._cache_position(event.layer_number, position)
        self._record_trade(
            direction=direction,
            units=event.units,
            instrument=position.instrument,
            price=position.entry_price,
            execution_method=str(event.event_type.value),
            timestamp=event.timestamp,
            layer_index=event.layer_number,
            open_price=position.entry_price,
            open_timestamp=event.timestamp,
        )

        logger.info(
            "Retracement executed: layer=%s, direction=%s, units=%s, count=%s, position_id=%s",
            event.layer_number,
            direction,
            event.units,
            event.retracement_count,
            position.id,
        )

        return position

    def handle_take_profit(self, event: TakeProfitEvent) -> Decimal:
        """Close position for take profit.

        Args:
            event: Take profit event with close details

        Returns:
            Decimal: Realized pnl delta from this event

        Raises:
            OrderServiceError: If order execution fails
        """
        position = self._find_take_profit_target(event)

        if not position:
            logger.error(
                "Cannot close position: no open position found for layer %s, direction %s",
                event.layer_number,
                event.direction,
            )
            return Decimal("0")

        # Close position (full or partial based on units)
        units_to_close = event.units if event.units > 0 else None
        closed_units = units_to_close if units_to_close is not None else abs(position.units)
        # Pass event exit_price so dry-run uses the strategy's price instead of
        # a potentially stale tick from the database.
        override_price = event.exit_price if event.exit_price else None
        closed_position, realized_delta = self.order_service.close_position(
            position=position,
            units=units_to_close,
            override_price=override_price,
        )
        close_direction = (
            Direction.SHORT if position.direction == Direction.LONG else Direction.LONG
        )
        self._record_trade(
            direction=close_direction,
            units=closed_units,
            instrument=position.instrument,
            price=Decimal(str(closed_position.exit_price or position.entry_price)),
            execution_method=str(event.event_type.value),
            timestamp=event.timestamp,
            layer_index=event.layer_number,
            pnl=realized_delta,
            open_price=position.entry_price,
            open_timestamp=position.entry_time,
            close_price=Decimal(str(closed_position.exit_price or position.entry_price)),
            close_timestamp=event.timestamp,
        )

        self._prune_closed_position(event.layer_number, closed_position)
        if not closed_position.is_open:
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

        return realized_delta

    def handle_volatility_lock(self, event: VolatilityLockEvent) -> Decimal:
        """Close all open positions due to volatility.

        Args:
            event: Volatility lock event

        Returns:
            Decimal: Realized pnl delta from this event

        Raises:
            OrderServiceError: If order execution fails
        """
        closed_positions: list[Position] = []
        realized_delta_total = Decimal("0")

        logger.warning(
            "Volatility lock triggered: %s (closing %s positions)",
            event.reason,
            len(self.position_map),
        )

        hedge_mode = "[HEDGE]" in str(event.reason or "").upper()
        for position in self._ordered_positions_for_margin_close():
            if not position.is_open:
                continue
            try:
                if hedge_mode:
                    opposite = (
                        Direction.SHORT if position.direction == Direction.LONG else Direction.LONG
                    )
                    hedged = self.order_service.open_position(
                        instrument=position.instrument,
                        units=abs(position.units),
                        direction=opposite,
                        layer_index=position.layer_index,
                        merge_with_existing=False,
                    )
                    self._cache_position(position.layer_index or 0, hedged)
                    closed_positions.append(hedged)
                    logger.info(
                        "Hedged position due to volatility: layer=%s, source=%s, hedge=%s",
                        position.layer_index,
                        position.id,
                        hedged.id,
                    )
                else:
                    closed, realized_delta = self.order_service.close_position(position)
                    closed_positions.append(closed)
                    self._prune_closed_position(position.layer_index or 0, closed)
                    realized_delta_total += realized_delta
                    close_direction = (
                        Direction.SHORT if position.direction == Direction.LONG else Direction.LONG
                    )
                    self._record_trade(
                        direction=close_direction,
                        units=abs(position.units),
                        instrument=position.instrument,
                        price=Decimal(str(closed.exit_price or position.entry_price)),
                        execution_method=str(event.event_type.value),
                        timestamp=event.timestamp,
                        layer_index=position.layer_index,
                        pnl=realized_delta,
                        open_price=position.entry_price,
                        open_timestamp=position.entry_time,
                        close_price=Decimal(str(closed.exit_price or position.entry_price)),
                        close_timestamp=event.timestamp,
                    )
                    logger.info(
                        "Closed position due to volatility: layer=%s, position_id=%s, pnl=%s",
                        position.layer_index,
                        closed.id,
                        closed.realized_pnl,
                    )
            except OrderServiceError as e:
                logger.error(
                    "Failed to process position %s during volatility lock: %s",
                    position.id,
                    e,
                )
                # Continue processing other positions

        if not hedge_mode:
            self.position_map.clear()
            self.layer_position_ids.clear()
            self._position_cache.clear()

        logger.info("Volatility lock complete: closed %s positions", len(closed_positions))

        return realized_delta_total

    def handle_margin_protection(self, event: MarginProtectionEvent) -> Decimal:
        """Close all open positions due to margin protection.

        Args:
            event: Margin protection event

        Returns:
            Decimal: Realized pnl delta from this event

        Raises:
            OrderServiceError: If order execution fails
        """
        closed_positions: list[Position] = []
        realized_delta_total = Decimal("0")

        logger.warning(
            "Margin protection triggered: %s (closing %s positions)",
            event.reason,
            len(self.position_map),
        )

        remaining_units = (
            int(event.units_to_close)
            if event.units_to_close and int(event.units_to_close) > 0
            else None
        )
        limit = (
            event.positions_closed
            if event.positions_closed and event.positions_closed > 0
            else None
        )
        touched_positions = 0
        for position in self._ordered_positions_for_margin_close():
            if remaining_units is not None and remaining_units <= 0:
                break
            if limit is not None and touched_positions >= limit:
                break
            if not position.is_open:
                continue
            try:
                units_to_close = None
                if remaining_units is not None:
                    units_to_close = min(abs(position.units), remaining_units)
                closed, realized_delta = self.order_service.close_position(
                    position, units=units_to_close
                )
                closed_positions.append(closed)
                self._prune_closed_position(position.layer_index or 0, closed)
                realized_delta_total += realized_delta
                close_direction = (
                    Direction.SHORT if position.direction == Direction.LONG else Direction.LONG
                )
                self._record_trade(
                    direction=close_direction,
                    units=units_to_close or abs(position.units),
                    instrument=position.instrument,
                    price=Decimal(str(closed.exit_price or position.entry_price)),
                    execution_method=str(event.event_type.value),
                    timestamp=event.timestamp,
                    layer_index=position.layer_index,
                    pnl=realized_delta,
                    open_price=position.entry_price,
                    open_timestamp=position.entry_time,
                    close_price=Decimal(str(closed.exit_price or position.entry_price)),
                    close_timestamp=event.timestamp,
                )
                touched_positions += 1
                if remaining_units is not None:
                    remaining_units -= units_to_close or 0
                logger.info(
                    "Closed position due to margin protection: layer=%s, position_id=%s, "
                    "units_requested=%s, remaining_units=%s, realized_delta=%s, pnl=%s",
                    position.layer_index,
                    closed.id,
                    units_to_close,
                    remaining_units,
                    realized_delta,
                    closed.realized_pnl,
                )
            except OrderServiceError as e:
                logger.error(
                    "Failed to close position %s during margin protection: %s",
                    position.id,
                    e,
                )
                # Continue closing other positions

        # Remove stale/closed ids from cache structures
        stale_layers: list[int] = []
        for layer_number, ids in self.layer_position_ids.items():
            open_ids = [pid for pid in ids if self._get_open_position_by_id(pid)]
            self.layer_position_ids[layer_number] = open_ids
            if not open_ids:
                stale_layers.append(layer_number)
        for layer_number in stale_layers:
            self.layer_position_ids.pop(layer_number, None)
            self.position_map.pop(layer_number, None)

        logger.info("Margin protection complete: closed %s positions", len(closed_positions))

        return realized_delta_total

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
        self.layer_position_ids.clear()
        self._position_cache.clear()
        logger.debug("Position map cleared")
