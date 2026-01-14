"""Monitoring components for Floor strategy."""

from datetime import datetime

from apps.trading.events import StrategyEvent
from apps.trading.strategies.floor.components import FloorVolatilityMonitor
from apps.trading.strategies.floor.event import EventFactory
from apps.trading.strategies.floor.models import FloorStrategyConfig, FloorStrategyState


class VolatilityMonitor:
    """Monitors volatility and emits events."""

    def __init__(
        self, config: FloorStrategyConfig, volatility_monitor: FloorVolatilityMonitor
    ) -> None:
        self.config = config
        self.volatility_monitor = volatility_monitor

    def check(self, state: FloorStrategyState, timestamp: datetime) -> StrategyEvent | None:
        """Check volatility and return event if lock state changed.

        Args:
            state: Strategy state
            timestamp: Current timestamp

        Returns:
            VolatilityLockEvent if lock state changed, None otherwise
        """
        volatility_series = self.volatility_monitor.get_volatility_series(state)
        lock_changed, atr_pips, current_range_pips = self.volatility_monitor.check_and_update(
            state, volatility_series
        )

        if lock_changed and state.volatility_locked:
            return EventFactory.create_volatility_lock(
                timestamp=timestamp,
                atr_pips=atr_pips,
                current_range_pips=current_range_pips,
                multiplier=self.config.volatility_lock_multiplier,
            )
        return None


class MarginProtectionMonitor:
    """Monitors margin protection and emits events."""

    def __init__(self, config: FloorStrategyConfig) -> None:
        self.config = config

    def check(self, state: FloorStrategyState, timestamp: datetime) -> StrategyEvent | None:
        """Check margin protection and return event if state changed.

        Args:
            state: Strategy state
            timestamp: Current timestamp

        Returns:
            MarginProtectionEvent if protection activated, None otherwise
        """
        current_layers = len(state.active_layers)

        # Deactivate if below threshold
        if current_layers < self.config.max_layers:
            state.margin_protection = False
            return None

        # Already activated
        if state.margin_protection:
            return None

        # Activate protection
        state.margin_protection = True
        return EventFactory.create_margin_protection(
            timestamp=timestamp,
            current_layers=current_layers,
            max_layers=self.config.max_layers,
        )
