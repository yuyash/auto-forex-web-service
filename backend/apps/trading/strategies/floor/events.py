"""Event creation for Floor strategy."""

from datetime import datetime
from decimal import Decimal

from apps.trading.enums import EventType
from apps.trading.events import (
    AddLayerEvent,
    InitialEntryEvent,
    MarginProtectionEvent,
    RemoveLayerEvent,
    RetracementEvent,
    StrategyEvent,
    TakeProfitEvent,
)
from apps.trading.strategies.floor.enums import Direction


class EventFactory:
    """Factory for creating strategy events."""

    @staticmethod
    def create_initial_entry(
        timestamp: datetime,
        layer_index: int,
        direction: Direction,
        entry_price: Decimal,
        units: Decimal,
    ) -> StrategyEvent:
        """Create initial entry event."""
        return InitialEntryEvent(
            event_type=EventType.INITIAL_ENTRY,
            timestamp=timestamp,
            layer_number=layer_index,
            direction=direction.value,
            price=entry_price,
            units=int(units),
            entry_time=timestamp,
            retracement_count=0,
        )

    @staticmethod
    def create_retracement(
        timestamp: datetime,
        layer_index: int,
        retracement_count: int,
        entry_price: Decimal,
        units: Decimal,
    ) -> StrategyEvent:
        """Create retracement event."""
        return RetracementEvent(
            event_type=EventType.RETRACEMENT,
            timestamp=timestamp,
            layer_number=layer_index,
            direction="",  # Will be set by caller if needed
            price=entry_price,
            units=int(units),
            entry_time=timestamp,
            retracement_count=retracement_count,
        )

    @staticmethod
    def create_take_profit(
        timestamp: datetime,
        layer_index: int,
        exit_price: Decimal,
        units: Decimal,
        pnl_pips: Decimal,
        pnl_amount: Decimal,
    ) -> StrategyEvent:
        """Create take profit event."""
        return TakeProfitEvent(
            event_type=EventType.TAKE_PROFIT,
            timestamp=timestamp,
            layer_number=layer_index,
            direction="",  # Will be set by caller if needed
            entry_price=Decimal("0"),  # Not available in this context
            exit_price=exit_price,
            units=int(units),
            pnl=pnl_amount,
            pips=pnl_pips,
            exit_time=timestamp,
        )

    @staticmethod
    def create_margin_protection(
        timestamp: datetime,
        margin_ratio: Decimal,
        units_closed: Decimal,
    ) -> StrategyEvent:
        """Create margin protection event."""
        return MarginProtectionEvent(
            event_type=EventType.MARGIN_PROTECTION,
            timestamp=timestamp,
            reason=f"Margin ratio {margin_ratio:.2%} exceeded threshold",
            current_margin=margin_ratio,
            positions_closed=int(units_closed),
        )

    @staticmethod
    def create_layer_created(
        timestamp: datetime,
        layer_index: int,
    ) -> StrategyEvent:
        """Create layer created event."""
        return AddLayerEvent(
            event_type=EventType.ADD_LAYER,
            timestamp=timestamp,
            layer_number=layer_index,
            add_time=timestamp,
        )

    @staticmethod
    def create_layer_closed(
        timestamp: datetime,
        layer_index: int,
    ) -> StrategyEvent:
        """Create layer closed event."""
        return RemoveLayerEvent(
            event_type=EventType.REMOVE_LAYER,
            timestamp=timestamp,
            layer_number=layer_index,
            remove_time=timestamp,
        )
