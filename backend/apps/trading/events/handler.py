"""Event handler for executing orders based on strategy events."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from decimal import Decimal
from logging import Logger, getLogger

from apps.trading.dataclasses import EntryExecutionBinding, EventExecutionResult
from apps.trading.enums import Direction
from apps.trading.events import (
    ClosePositionEvent,
    MarginProtectionEvent,
    OpenPositionEvent,
    StrategyEvent,
    VolatilityHedgeNeutralizeEvent,
    VolatilityLockEvent,
)
from apps.trading.models import Order, Position, Trade, TradingEvent
from apps.trading.order import OrderService, OrderServiceError

logger: Logger = getLogger(name=__name__)
lifecycle_logger: Logger = getLogger(name="position.lifecycle")


EventDispatchFn = Callable[[StrategyEvent], EventExecutionResult]


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
        self._event_dispatch: dict[str, EventDispatchFn] = {
            "open_position": self._dispatch_open_position,
            "close_position": self._dispatch_close_position,
            "volatility_lock": self._dispatch_volatility_lock,
            "volatility_hedge_neutralize": self._dispatch_volatility_hedge_neutralize,
            "margin_protection": self._dispatch_margin_protection,
        }
        self._category_dispatch: dict[str, EventDispatchFn] = {
            "info": self._dispatch_informational,
            "entry": self._dispatch_unhandled_category,
            "exit": self._dispatch_unhandled_category,
            "risk": self._dispatch_unhandled_category,
        }
        # Maps strategy-internal entry_id → Trade.cycle_id (UUID).
        # Populated by handle_open_position so that subsequent close
        # trades and child entries can inherit the correct cycle_id.
        self._entry_id_to_cycle_id: dict[int, str] = {}
        # Sequence number from the current TradingEvent being processed.
        self._current_sequence_number: int = 0

    @staticmethod
    def _event_type_key(strategy_event: StrategyEvent) -> str:
        event_type = getattr(strategy_event, "event_type", "")
        return str(getattr(event_type, "value", event_type))

    def register_event_handler(self, event_type: str, handler: EventDispatchFn) -> None:
        """Register/override a handler for a specific event_type."""
        key = str(event_type).strip()
        if not key:
            raise ValueError("event_type must be non-empty")
        self._event_dispatch[key] = handler

    def register_category_handler(self, category: str, handler: EventDispatchFn) -> None:
        """Register/override a handler for an event category."""
        key = str(category).strip()
        if not key:
            raise ValueError("category must be non-empty")
        self._category_dispatch[key] = handler

    @property
    def _task_pk(self):
        return self.order_service.task.id

    @property
    def _execution_id(self):
        return self.order_service.execution_id

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
                execution_id=self._execution_id,
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
                execution_id=self._execution_id,
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

    def _find_close_position_target(self, event: ClosePositionEvent) -> Position | None:
        # If the event carries a specific position_id, use it directly.
        if event.position_id:
            candidate = self._get_open_position_by_id(event.position_id)
            if candidate:
                return candidate
            logger.warning(
                "position_id %s from ClosePositionEvent not found or already closed, "
                "falling back to entry-time lookup for layer %s",
                event.position_id,
                event.layer_number,
            )

        layer_number = event.layer_number
        direction = Direction(event.direction)
        self._rehydrate_layer_positions(layer_number)
        stack = self.layer_position_ids.get(layer_number, [])

        # Oldest first (entry-time order), filtered by direction
        stale_ids: list[str] = []
        result: Position | None = None
        for candidate_id in stack:
            candidate = self._get_open_position_by_id(candidate_id)
            if not candidate:
                stale_ids.append(candidate_id)
                continue
            if candidate.direction == direction.value:
                result = candidate
                break
        for sid in stale_ids:
            stack.remove(sid)
        if result:
            return result

        fallback = (
            Position.objects.filter(
                task_type=self.order_service.task_type,
                task_id=self._task_pk,
                execution_id=self._execution_id,
                instrument=self.instrument,
                direction=direction,
                is_open=True,
                layer_index=layer_number,
            )
            .order_by("entry_time")
            .first()
        )
        return fallback

    def _prune_closed_position(self, layer_number: int, position: Position) -> None:
        pos_id = str(position.id)
        if position.is_open:
            self._position_cache[pos_id] = position
            self.position_map[layer_number] = position
            return

        # Remove closed position from cache to prevent unbounded memory growth
        self._position_cache.pop(pos_id, None)
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
                execution_id=self._execution_id,
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
        direction: Direction | None,
        units: int,
        instrument: str,
        price: Decimal,
        execution_method: str,
        timestamp,
        layer_index: int | None = None,
        retracement_count: int | None = None,
        oanda_trade_id: str | None = None,
        position: Position | None = None,
        order: Order | None = None,
        description: str = "",
        cycle_id: str | None = None,
    ) -> Trade:
        trade = Trade.objects.create(
            task_type=self.order_service.task_type.value,
            task_id=self._task_pk,
            execution_id=self._execution_id,
            timestamp=timestamp,
            direction=direction.value if direction else None,
            units=units,
            instrument=instrument,
            price=price,
            execution_method=execution_method,
            layer_index=layer_index,
            retracement_count=retracement_count,
            oanda_trade_id=oanda_trade_id,
            position=position,
            order=order,
            description=description,
            cycle_id=cycle_id,
            sequence_number=self._current_sequence_number,
        )
        return trade

    def handle_event(self, trading_event: TradingEvent) -> EventExecutionResult:
        """Handle a single trading event by executing appropriate order.

        Args:
            trading_event: TradingEvent instance from database

        Returns:
            EventExecutionResult: Realized pnl and optional entry-position binding

        Raises:
            OrderServiceError: If order execution fails
        """
        strategy_event = StrategyEvent.from_dict(trading_event.details)
        self._current_sequence_number = getattr(trading_event, "sequence_number", 0) or 0
        # Restore cycle-tracking fields from TradingEvent model columns
        # (these are not stored in the details JSON).
        if trading_event.root_entry_id is not None:
            strategy_event.root_entry_id = trading_event.root_entry_id
        if trading_event.parent_entry_id is not None:
            strategy_event.parent_entry_id = trading_event.parent_entry_id
        event_key = self._event_type_key(strategy_event)
        event_handler = self._event_dispatch.get(event_key)
        if event_handler:
            return event_handler(strategy_event)

        category = str(getattr(strategy_event, "category", "info"))
        category_handler = self._category_dispatch.get(category, self._dispatch_informational)
        return category_handler(strategy_event)

    def _dispatch_open_position(self, strategy_event: StrategyEvent) -> EventExecutionResult:
        if not isinstance(strategy_event, OpenPositionEvent):
            return self._dispatch_type_mismatch(strategy_event, OpenPositionEvent)
        position = self.handle_open_position(strategy_event)
        binding = EntryExecutionBinding(
            entry_id=strategy_event.entry_id,
            position_id=str(position.id),
        )
        return EventExecutionResult(
            realized_pnl_delta=Decimal("0"),
            entry_binding=binding,
        )

    def _dispatch_close_position(self, strategy_event: StrategyEvent) -> EventExecutionResult:
        if not isinstance(strategy_event, ClosePositionEvent):
            return self._dispatch_type_mismatch(strategy_event, ClosePositionEvent)
        return EventExecutionResult(
            realized_pnl_delta=self.handle_close_position(strategy_event),
        )

    def _dispatch_volatility_lock(self, strategy_event: StrategyEvent) -> EventExecutionResult:
        if not isinstance(strategy_event, VolatilityLockEvent):
            return self._dispatch_type_mismatch(strategy_event, VolatilityLockEvent)
        return EventExecutionResult(
            realized_pnl_delta=self.handle_volatility_lock(strategy_event),
        )

    def _dispatch_volatility_hedge_neutralize(
        self, strategy_event: StrategyEvent
    ) -> EventExecutionResult:
        if not isinstance(strategy_event, VolatilityHedgeNeutralizeEvent):
            return self._dispatch_type_mismatch(strategy_event, VolatilityHedgeNeutralizeEvent)
        return EventExecutionResult(
            realized_pnl_delta=self.handle_volatility_hedge_neutralize(strategy_event),
        )

    def _dispatch_margin_protection(self, strategy_event: StrategyEvent) -> EventExecutionResult:
        if not isinstance(strategy_event, MarginProtectionEvent):
            return self._dispatch_type_mismatch(strategy_event, MarginProtectionEvent)
        return EventExecutionResult(
            realized_pnl_delta=self.handle_margin_protection(strategy_event),
        )

    def _dispatch_informational(self, strategy_event: StrategyEvent) -> EventExecutionResult:
        logger.debug(
            "Informational event ignored by execution handler: event_type=%s, category=%s",
            self._event_type_key(strategy_event),
            getattr(strategy_event, "category", "info"),
        )
        return EventExecutionResult(realized_pnl_delta=Decimal("0"))

    def _dispatch_unhandled_category(self, strategy_event: StrategyEvent) -> EventExecutionResult:
        logger.warning(
            "No execution handler registered for event category '%s' (event_type=%s)",
            getattr(strategy_event, "category", "unknown"),
            self._event_type_key(strategy_event),
        )
        return EventExecutionResult(realized_pnl_delta=Decimal("0"))

    def _dispatch_type_mismatch(
        self,
        strategy_event: StrategyEvent,
        expected_cls: type[StrategyEvent],
    ) -> EventExecutionResult:
        logger.error(
            "Event dispatch type mismatch for event_type=%s: expected %s, got %s",
            self._event_type_key(strategy_event),
            expected_cls.__name__,
            strategy_event.__class__.__name__,
        )
        return EventExecutionResult(realized_pnl_delta=Decimal("0"))

    def _resolve_cycle_id_for_open(self, event: OpenPositionEvent) -> str | None:
        """Determine the cycle_id for a new open trade.

        - If parent_entry_id is None this is a cycle-starting entry
          (Initial Entry or Trend re-entry).  The cycle_id will be the
          Trade.id of the trade we are about to create — the caller must
          back-fill it after creation.
        - Otherwise, look up the root_entry_id in the mapping to find
          the cycle_id of the cycle this entry belongs to.

        Returns None when the entry starts a new cycle (caller must
        set cycle_id = trade.id after creation).
        """
        root_eid = getattr(event, "root_entry_id", None)
        parent_eid = getattr(event, "parent_entry_id", None)

        if parent_eid is None:
            # New cycle — cycle_id will be this trade's own id.
            return None

        # Child entry — inherit cycle_id from root.
        if root_eid is not None and root_eid in self._entry_id_to_cycle_id:
            return self._entry_id_to_cycle_id[root_eid]

        # Fallback: try parent chain.
        if parent_eid in self._entry_id_to_cycle_id:
            return self._entry_id_to_cycle_id[parent_eid]

        # DB fallback: look up cycle_id from existing TradingEvent records.
        # This handles the case where the EventHandler was re-created (e.g.
        # after a task resume) and the in-memory mapping was lost.
        cycle_id = self._resolve_cycle_id_from_db(root_eid, parent_eid)
        if cycle_id is not None:
            # Cache for future lookups within this session.
            if root_eid is not None:
                self._entry_id_to_cycle_id[root_eid] = cycle_id
            if parent_eid is not None:
                self._entry_id_to_cycle_id[parent_eid] = cycle_id
            return cycle_id

        logger.warning(
            "Could not resolve cycle_id for entry_id=%s (root=%s, parent=%s)",
            event.entry_id,
            root_eid,
            parent_eid,
        )
        return None

    def _resolve_cycle_id_from_db(self, root_eid: int | None, parent_eid: int | None) -> str | None:
        """Look up cycle_id from Trade records by matching entry_id in TradingEvent."""
        try:
            for eid in (root_eid, parent_eid):
                if eid is None:
                    continue
                te = (
                    TradingEvent.objects.filter(
                        task_type=self.order_service.task_type,
                        task_id=self._task_pk,
                        execution_id=self._execution_id,
                        entry_id=eid,
                        event_type="open_position",
                    )
                    .values_list("event_timestamp", flat=True)
                    .first()
                )
                if te is None:
                    continue
                trade = (
                    Trade.objects.filter(
                        task_type=self.order_service.task_type.value,
                        task_id=self._task_pk,
                        execution_id=self._execution_id,
                        timestamp=te,
                        execution_method="open_position",
                        cycle_id__isnull=False,
                    )
                    .values_list("cycle_id", flat=True)
                    .first()
                )
                if trade is not None:
                    return str(trade)
        except (TypeError, ValueError):
            pass
        return None

    def handle_open_position(self, event: OpenPositionEvent) -> Position:
        """Open position for execution.

        Args:
            event: Open position event with position details

        Returns:
            Position: Created position

        Raises:
            OrderServiceError: If order execution fails
        """
        direction = Direction(event.direction)
        position, order = self.order_service.open_position(
            instrument=self.instrument,
            units=event.units,
            direction=direction,
            layer_index=event.layer_number,
            merge_with_existing=False,
            override_price=event.price if event.price else None,
            tick_timestamp=event.timestamp,
            retracement_count=event.retracement_count,
            planned_exit_price=event.planned_exit_price,
            planned_exit_price_formula=getattr(event, "planned_exit_price_formula", None),
        )

        cycle_id = self._resolve_cycle_id_for_open(event)

        # Persist adverse pips (distance from previous entry) on the position
        adverse = getattr(event, "actual_interval_pips", None)
        if adverse is not None:
            position.adverse_pips = adverse
            position.save(update_fields=["adverse_pips"])

        self._cache_position(event.layer_number, position)
        trade = self._record_trade(
            direction=direction,
            units=event.units,
            instrument=position.instrument,
            price=position.entry_price,
            execution_method=str(event.event_type.value),
            timestamp=event.timestamp,
            layer_index=event.layer_number,
            retracement_count=event.retracement_count,
            oanda_trade_id=position.oanda_trade_id,
            position=position,
            order=order,
            description=getattr(event, "description", ""),
            cycle_id=cycle_id,
        )

        # New cycle: back-fill cycle_id = trade's own id.
        if cycle_id is None:
            trade.cycle_id = str(trade.id)
            trade.save(update_fields=["cycle_id"])
            cycle_id = str(trade.id)

        # Register mapping so child entries and close events can look up
        # the cycle_id by their root_entry_id or entry_id.
        if event.entry_id is not None:
            self._entry_id_to_cycle_id[event.entry_id] = cycle_id

        logger.info(
            "Open position executed: layer=%s, direction=%s, units=%s, count=%s, position_id=%s",
            event.layer_number,
            direction,
            event.units,
            event.retracement_count,
            position.id,
        )

        lifecycle_logger.info(
            "POSITION_OPENED: %s %s %s units @ %s (layer=%s, retracement=%s, planned_exit=%s)",
            direction.value,
            position.instrument,
            event.units,
            position.entry_price,
            event.layer_number,
            event.retracement_count,
            position.planned_exit_price,
            extra={
                "position_id": str(position.id),
                "lifecycle_event": "OPENED",
                "direction": direction.value,
                "instrument": position.instrument,
                "units": event.units,
                "entry_price": str(position.entry_price),
                "entry_time": str(event.timestamp),
                "layer_index": event.layer_number,
                "retracement_count": event.retracement_count,
                "planned_exit_price": str(position.planned_exit_price)
                if position.planned_exit_price
                else None,
                "planned_exit_price_formula": position.planned_exit_price_formula,
                "oanda_trade_id": position.oanda_trade_id,
                "order_id": str(order.id),
            },
        )

        return position

    def _resolve_cycle_id_for_close(self, event: ClosePositionEvent) -> str | None:
        """Look up cycle_id for a close trade from the entry being closed."""
        eid = getattr(event, "entry_id", None)
        if eid is not None and eid in self._entry_id_to_cycle_id:
            return self._entry_id_to_cycle_id[eid]

        root_eid = getattr(event, "root_entry_id", None)
        if root_eid is not None and root_eid in self._entry_id_to_cycle_id:
            return self._entry_id_to_cycle_id[root_eid]

        return None

    def _resolve_cycle_id_for_position(self, position: Position) -> str | None:
        """Look up cycle_id from the Trade that opened a position.

        Protection handlers (shrink, lock, margin) don't carry entry_id
        metadata, so we fall back to the Trade table to find which cycle
        the position belongs to.
        """
        pos_id = str(position.id)
        # Check in-memory cache first
        for eid, cid in self._entry_id_to_cycle_id.items():
            if cid and str(eid) == pos_id:
                return cid

        # DB lookup: find the open_position trade that created this position
        try:
            open_trade = (
                Trade.objects.filter(
                    task_type=self.order_service.task_type.value,
                    task_id=self._task_pk,
                    execution_id=self._execution_id,
                    position_id=position.id,
                    execution_method="open_position",
                    cycle_id__isnull=False,
                )
                .values_list("cycle_id", flat=True)
                .first()
            )
            return str(open_trade) if open_trade else None
        except Exception:
            return None

    def handle_close_position(self, event: ClosePositionEvent) -> Decimal:
        """Close one or more positions.

        When the requested units exceed a single position's size, this
        method iterates through multiple positions in the same layer
        until the full amount is closed or no more open positions remain.

        Args:
            event: Close position event with close details

        Returns:
            Decimal: Realized pnl delta from this event

        Raises:
            OrderServiceError: If order execution fails
        """
        override_price = event.exit_price if event.exit_price else None
        total_requested = event.units if event.units > 0 else None
        remaining = total_requested
        realized_delta_total = Decimal("0")

        while True:
            position = self._find_close_position_target(event)
            if not position:
                if realized_delta_total == Decimal("0"):
                    logger.error(
                        "Cannot close position: no open position found for layer %s, direction %s",
                        event.layer_number,
                        event.direction,
                    )
                else:
                    logger.warning(
                        "Close position: exhausted open positions for layer %s before fully "
                        "closing requested %s units (%s remaining)",
                        event.layer_number,
                        total_requested,
                        remaining,
                    )
                break

            pos_units = abs(position.units)

            if remaining is None:
                # Full close of this single position
                units_to_close = None
                closed_units = pos_units
            else:
                units_to_close = min(remaining, pos_units)
                closed_units = units_to_close

            closed_position, realized_delta, close_order = self.order_service.close_position(
                position=position,
                units=units_to_close,
                override_price=override_price,
                tick_timestamp=event.timestamp,
            )
            realized_delta_total += realized_delta

            self._record_trade(
                direction=Direction(position.direction),
                units=closed_units,
                instrument=position.instrument,
                price=Decimal(str(closed_position.exit_price or position.entry_price)),
                execution_method=str(event.event_type.value),
                timestamp=event.timestamp,
                layer_index=event.layer_number,
                retracement_count=event.retracement_count,
                oanda_trade_id=position.oanda_trade_id,
                position=position,
                order=close_order,
                description=getattr(event, "description", ""),
                cycle_id=self._resolve_cycle_id_for_close(event),
            )

            self._prune_closed_position(event.layer_number, closed_position)

            if not closed_position.is_open:
                logger.info(
                    "Close position executed (full close): layer=%s, pnl=%s, position_id=%s",
                    event.layer_number,
                    realized_delta,
                    closed_position.id,
                )
                lifecycle_logger.info(
                    "POSITION_CLOSED: %s %s (full close) exit @ %s, pnl=%s (layer=%s)",
                    closed_position.direction,
                    closed_position.instrument,
                    closed_position.exit_price,
                    realized_delta,
                    event.layer_number,
                    extra={
                        "position_id": str(closed_position.id),
                        "lifecycle_event": "CLOSED",
                        "close_type": "full",
                        "direction": closed_position.direction,
                        "instrument": closed_position.instrument,
                        "units_closed": closed_units,
                        "entry_price": str(closed_position.entry_price),
                        "exit_price": str(closed_position.exit_price),
                        "entry_time": str(closed_position.entry_time),
                        "exit_time": str(closed_position.exit_time),
                        "realized_pnl": str(realized_delta),
                        "layer_index": event.layer_number,
                        "retracement_count": event.retracement_count,
                        "close_reason": str(event.event_type.value),
                        "description": getattr(event, "description", ""),
                        "oanda_trade_id": closed_position.oanda_trade_id,
                        "order_id": str(close_order.id) if close_order else None,
                    },
                )
            else:
                logger.info(
                    "Close position executed (partial close): layer=%s, units_closed=%s, remaining=%s, position_id=%s",
                    event.layer_number,
                    units_to_close,
                    abs(closed_position.units),
                    closed_position.id,
                )
                lifecycle_logger.info(
                    "POSITION_PARTIAL_CLOSE: %s %s, %s units closed, %s remaining (layer=%s, pnl=%s)",
                    closed_position.direction,
                    closed_position.instrument,
                    units_to_close,
                    abs(closed_position.units),
                    event.layer_number,
                    realized_delta,
                    extra={
                        "position_id": str(closed_position.id),
                        "lifecycle_event": "PARTIAL_CLOSE",
                        "close_type": "partial",
                        "direction": closed_position.direction,
                        "instrument": closed_position.instrument,
                        "units_closed": units_to_close,
                        "units_remaining": abs(closed_position.units),
                        "entry_price": str(closed_position.entry_price),
                        "exit_price": str(closed_position.exit_price or override_price),
                        "realized_pnl": str(realized_delta),
                        "layer_index": event.layer_number,
                        "retracement_count": event.retracement_count,
                        "close_reason": str(event.event_type.value),
                        "description": getattr(event, "description", ""),
                        "oanda_trade_id": closed_position.oanda_trade_id,
                        "order_id": str(close_order.id) if close_order else None,
                    },
                )

            # If no specific amount was requested, we only close one position
            if remaining is None:
                break

            remaining -= closed_units
            if remaining <= 0:
                break

        return realized_delta_total

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

        for position in self._ordered_positions_for_margin_close():
            if not position.is_open:
                continue
            try:
                closed, realized_delta, close_order = self.order_service.close_position(
                    position,
                    tick_timestamp=event.timestamp,
                )
                closed_positions.append(closed)
                self._prune_closed_position(position.layer_index or 0, closed)
                realized_delta_total += realized_delta
                self._record_trade(
                    direction=Direction(position.direction),
                    units=abs(position.units),
                    instrument=position.instrument,
                    price=Decimal(str(closed.exit_price or position.entry_price)),
                    execution_method=str(event.event_type.value),
                    timestamp=event.timestamp,
                    layer_index=position.layer_index,
                    oanda_trade_id=position.oanda_trade_id,
                    position=position,
                    order=close_order,
                    description=f"[PROTECTION] Volatility lock: close all positions ({event.reason})",
                    cycle_id=self._resolve_cycle_id_for_position(position),
                )
                logger.info(
                    "Closed position due to volatility: layer=%s, position_id=%s, pnl=%s",
                    position.layer_index,
                    closed.id,
                    realized_delta,
                )
                lifecycle_logger.info(
                    "POSITION_CLOSED: %s %s (volatility lock) exit @ %s, pnl=%s (reason=%s)",
                    position.direction,
                    position.instrument,
                    closed.exit_price,
                    realized_delta,
                    event.reason,
                    extra={
                        "position_id": str(closed.id),
                        "lifecycle_event": "CLOSED",
                        "close_type": "full",
                        "direction": position.direction,
                        "instrument": position.instrument,
                        "units_closed": abs(position.units),
                        "entry_price": str(position.entry_price),
                        "exit_price": str(closed.exit_price),
                        "entry_time": str(position.entry_time),
                        "exit_time": str(closed.exit_time),
                        "realized_pnl": str(realized_delta),
                        "layer_index": position.layer_index,
                        "close_reason": "volatility_lock",
                        "description": f"Volatility lock: {event.reason}",
                        "oanda_trade_id": position.oanda_trade_id,
                        "order_id": str(close_order.id) if close_order else None,
                    },
                )
            except OrderServiceError as e:
                logger.error(
                    "Failed to process position %s during volatility lock: %s",
                    position.id,
                    e,
                )
                # Continue processing other positions

        self.position_map.clear()
        self.layer_position_ids.clear()
        self._position_cache.clear()

        logger.info("Volatility lock complete: closed %s positions", len(closed_positions))

        return realized_delta_total

    def handle_volatility_hedge_neutralize(self, event: VolatilityHedgeNeutralizeEvent) -> Decimal:
        """Open hedge positions to neutralize net exposure during volatility spike.

        For each instruction in the event, opens an opposite-direction position
        that mirrors an existing open position.  No positions are closed, so
        realized PnL is always zero.

        Args:
            event: Hedge neutralize event with instructions.

        Returns:
            Decimal: Always ``Decimal("0")`` — no realized PnL.
        """
        logger.warning(
            "Volatility hedge neutralize triggered: %s (hedging %d positions)",
            event.reason,
            len(event.hedge_instructions),
        )

        for instr in event.hedge_instructions:
            direction_str = str(instr.get("direction", "long")).upper()
            direction = Direction.LONG if direction_str == "LONG" else Direction.SHORT
            units = abs(int(instr.get("units", 0)))
            layer_index = int(instr.get("layer_index", 0))
            if units <= 0:
                continue
            try:
                hedged, _order = self.order_service.open_position(
                    instrument=self.instrument,
                    units=units,
                    direction=direction,
                    layer_index=layer_index,
                    merge_with_existing=False,
                    tick_timestamp=event.timestamp,
                )
                self._cache_position(layer_index, hedged)
                logger.info(
                    "Opened hedge-neutralize position: layer=%s, direction=%s, "
                    "units=%s, hedge_id=%s, source_entry=%s",
                    layer_index,
                    direction_str,
                    units,
                    hedged.id,
                    instr.get("source_entry_id"),
                )
                lifecycle_logger.info(
                    "POSITION_OPENED: %s %s %s units @ %s (hedge neutralize, layer=%s)",
                    direction_str,
                    self.instrument,
                    units,
                    hedged.entry_price,
                    layer_index,
                    extra={
                        "position_id": str(hedged.id),
                        "lifecycle_event": "OPENED",
                        "direction": direction_str,
                        "instrument": self.instrument,
                        "units": units,
                        "entry_price": str(hedged.entry_price),
                        "entry_time": str(event.timestamp),
                        "layer_index": layer_index,
                        "open_reason": "volatility_hedge_neutralize",
                        "description": f"Hedge neutralize: {event.reason}",
                        "oanda_trade_id": hedged.oanda_trade_id,
                        "order_id": str(_order.id),
                    },
                )
            except OrderServiceError as e:
                logger.error(
                    "Failed to open hedge-neutralize position for source_entry %s: %s",
                    instr.get("source_entry_id"),
                    e,
                )

        logger.info(
            "Volatility hedge neutralize complete: %d hedge positions opened",
            len(event.hedge_instructions),
        )
        return Decimal("0")

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
                closed, realized_delta, close_order = self.order_service.close_position(
                    position,
                    units=units_to_close,
                    tick_timestamp=event.timestamp,
                )
                closed_positions.append(closed)
                self._prune_closed_position(position.layer_index or 0, closed)
                realized_delta_total += realized_delta
                self._record_trade(
                    direction=Direction(position.direction),
                    units=units_to_close or abs(position.units),
                    instrument=position.instrument,
                    price=Decimal(str(closed.exit_price or position.entry_price)),
                    execution_method=str(event.event_type.value),
                    timestamp=event.timestamp,
                    layer_index=position.layer_index,
                    oanda_trade_id=position.oanda_trade_id,
                    position=position,
                    order=close_order,
                    description=f"[PROTECTION] Margin protection: forced close ({event.reason})",
                    cycle_id=self._resolve_cycle_id_for_position(position),
                )
                touched_positions += 1
                if remaining_units is not None:
                    remaining_units -= units_to_close or 0
                logger.info(
                    "Closed position due to margin protection: layer=%s, position_id=%s, "
                    "units_requested=%s, remaining_units=%s, realized_delta=%s",
                    position.layer_index,
                    closed.id,
                    units_to_close,
                    remaining_units,
                    realized_delta,
                )
                lifecycle_logger.info(
                    "POSITION_CLOSED: %s %s (margin protection) exit @ %s, pnl=%s (reason=%s)",
                    position.direction,
                    position.instrument,
                    closed.exit_price,
                    realized_delta,
                    event.reason,
                    extra={
                        "position_id": str(closed.id),
                        "lifecycle_event": "CLOSED",
                        "close_type": "full" if not closed.is_open else "partial",
                        "direction": position.direction,
                        "instrument": position.instrument,
                        "units_closed": units_to_close or abs(position.units),
                        "entry_price": str(position.entry_price),
                        "exit_price": str(closed.exit_price),
                        "entry_time": str(position.entry_time),
                        "exit_time": str(closed.exit_time) if closed.exit_time else None,
                        "realized_pnl": str(realized_delta),
                        "layer_index": position.layer_index,
                        "close_reason": "margin_protection",
                        "description": f"Margin protection: {event.reason}",
                        "oanda_trade_id": position.oanda_trade_id,
                        "order_id": str(close_order.id) if close_order else None,
                    },
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
        self._entry_id_to_cycle_id.clear()
        logger.debug("Position map cleared")
