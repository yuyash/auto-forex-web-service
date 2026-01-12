"""Event adapter for Floor strategy.

This module provides adapters to convert Floor strategy domain events
to the unified global event system.
"""

from datetime import datetime
from decimal import Decimal

from apps.trading.enums import EventType
from apps.trading.events import (
    AddLayerEvent,
    InitialEntryEvent,
    MarginProtectionEvent,
    RemoveLayerEvent,
    RetracementEvent,
    TakeProfitEvent,
    VolatilityLockEvent,
)
from apps.trading.strategies.floor.enums import Direction


class EventFactory:
    """Factory for creating unified strategy events."""

    @staticmethod
    def create_initial_entry(
        timestamp: datetime,
        layer: int,
        direction: Direction,
        entry_price: Decimal,
        lot_size: Decimal,
    ) -> InitialEntryEvent:
        """Create an initial entry event."""
        return InitialEntryEvent(
            event_type=EventType.INITIAL_ENTRY,
            timestamp=timestamp,
            layer_number=layer,
            direction=str(direction.value),
            price=entry_price,
            units=int(lot_size),  # Convert Decimal to int for units
            entry_time=timestamp,
            retracement_count=0,
        )

    @staticmethod
    def create_retracement(
        timestamp: datetime,
        layer: int,
        direction: Direction,
        entry_price: Decimal,
        lot_size: Decimal,
        retracement: int,
    ) -> RetracementEvent:
        """Create a retracement event."""
        return RetracementEvent(
            event_type=EventType.RETRACEMENT,
            timestamp=timestamp,
            layer_number=layer,
            direction=str(direction.value),
            price=entry_price,
            units=int(lot_size),
            entry_time=timestamp,
            retracement_count=retracement,
        )

    @staticmethod
    def create_take_profit(
        timestamp: datetime,
        direction: str | None,
        entry_price: Decimal | None,
        exit_price: Decimal,
        units: Decimal | None,
        pnl: Decimal,
        pips: Decimal,
        entry_time: datetime | None,
    ) -> TakeProfitEvent:
        """Create a take profit event."""
        return TakeProfitEvent(
            event_type=EventType.TAKE_PROFIT,
            timestamp=timestamp,
            layer_number=0,  # Represents all layers
            direction=direction or "mixed",
            entry_price=entry_price or Decimal("0"),
            exit_price=exit_price,
            units=int(units) if units else 0,
            pnl=pnl,
            pips=pips,
            entry_time=entry_time,
            exit_time=timestamp,
            retracement_count=0,
        )

    @staticmethod
    def create_add_layer(
        timestamp: datetime,
        layer: int,
    ) -> AddLayerEvent:
        """Create an add layer event."""
        return AddLayerEvent(
            event_type=EventType.ADD_LAYER,
            timestamp=timestamp,
            layer_number=layer,
            add_time=timestamp,
        )

    @staticmethod
    def create_remove_layer(
        timestamp: datetime,
        layer: int,
        add_time: datetime | None = None,
    ) -> RemoveLayerEvent:
        """Create a remove layer event."""
        return RemoveLayerEvent(
            event_type=EventType.REMOVE_LAYER,
            timestamp=timestamp,
            layer_number=layer,
            add_time=add_time,
            remove_time=timestamp,
        )

    @staticmethod
    def create_volatility_lock(
        timestamp: datetime,
        atr_pips: Decimal | None,
        current_range_pips: Decimal | None,
        multiplier: Decimal,
    ) -> VolatilityLockEvent:
        """Create a volatility lock event."""
        reason = f"ATR exceeded threshold (multiplier: {multiplier})"
        return VolatilityLockEvent(
            event_type=EventType.VOLATILITY_LOCK,
            timestamp=timestamp,
            reason=reason,
            atr_value=atr_pips,
            threshold=atr_pips * multiplier if atr_pips else None,
        )

    @staticmethod
    def create_margin_protection(
        timestamp: datetime,
        current_layers: int,
        max_layers: int,
    ) -> MarginProtectionEvent:
        """Create a margin protection event."""
        reason = f"Maximum layers reached ({current_layers}/{max_layers})"
        return MarginProtectionEvent(
            event_type=EventType.MARGIN_PROTECTION,
            timestamp=timestamp,
            reason=reason,
            current_margin=None,
            threshold=None,
            positions_closed=None,
        )
