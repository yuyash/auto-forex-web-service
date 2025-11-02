"""
Base strategy abstract class for trading strategies.

This module provides the abstract base class that all trading strategies must inherit from.
It defines the interface for strategy implementations and provides common utility methods.

Requirements: 5.1, 5.3
"""

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any

from django.utils import timezone

from .models import Order, Position, Strategy
from .tick_data_models import TickData


class BaseStrategy(ABC):
    """
    Abstract base class for all trading strategies.

    All strategy implementations must inherit from this class and implement
    the abstract methods: on_tick, on_position_update, and validate_config.

    Requirements: 5.1, 5.3
    """

    def __init__(self, strategy: Strategy) -> None:
        """
        Initialize the strategy with a Strategy model instance.

        Args:
            strategy: Strategy model instance containing configuration
        """
        self.strategy = strategy
        self.account = strategy.account
        self.config = strategy.config
        self.instruments = strategy.instruments

    @abstractmethod
    def on_tick(self, tick_data: TickData) -> list[Order]:
        """
        Process incoming tick data and generate trading signals.

        This method is called for every tick received from the market data stream.
        Implementations should analyze the tick data and return a list of orders
        to execute based on the strategy logic.

        Args:
            tick_data: TickData instance containing bid, ask, mid prices and timestamp

        Returns:
            List of Order instances to be executed (can be empty)

        Requirements: 5.3
        """
        pass  # pylint: disable=unnecessary-pass

    @abstractmethod
    def on_position_update(self, position: Position) -> None:
        """
        Handle position updates (opens, closes, P&L changes).

        This method is called whenever a position is updated, allowing the strategy
        to react to position changes, track performance, or adjust its behavior.

        Args:
            position: Position instance that was updated

        Requirements: 5.3
        """
        pass  # pylint: disable=unnecessary-pass

    @abstractmethod
    def validate_config(self, config: dict[str, Any]) -> bool:
        """
        Validate strategy configuration parameters.

        This method should check that all required configuration parameters are present
        and have valid values. It should raise ValueError with descriptive messages
        for invalid configurations.

        Args:
            config: Dictionary containing strategy configuration parameters

        Returns:
            True if configuration is valid

        Raises:
            ValueError: If configuration is invalid with descriptive error message

        Requirements: 5.1
        """
        pass  # pylint: disable=unnecessary-pass

    # Common utility methods

    def get_config_value(self, key: str, default: Any = None, required: bool = False) -> Any:
        """
        Get a configuration value with optional default and required validation.

        Args:
            key: Configuration key to retrieve
            default: Default value if key is not found
            required: If True, raises ValueError if key is not found

        Returns:
            Configuration value or default

        Raises:
            ValueError: If required=True and key is not found
        """
        if key not in self.config:
            if required:
                raise ValueError(f"Required configuration key '{key}' not found")
            return default
        return self.config[key]

    def get_open_positions(self, instrument: str | None = None) -> list[Position]:
        """
        Get all open positions for this strategy.

        Args:
            instrument: Optional instrument filter (e.g., 'EUR_USD')

        Returns:
            List of open Position instances
        """
        queryset = Position.objects.filter(
            account=self.account, strategy=self.strategy, closed_at__isnull=True
        )

        if instrument:
            queryset = queryset.filter(instrument=instrument)

        return list(queryset.order_by("opened_at"))

    def get_pending_orders(self, instrument: str | None = None) -> list[Order]:
        """
        Get all pending orders for this strategy.

        Args:
            instrument: Optional instrument filter (e.g., 'EUR_USD')

        Returns:
            List of pending Order instances
        """
        queryset = Order.objects.filter(
            account=self.account, strategy=self.strategy, status="pending"
        )

        if instrument:
            queryset = queryset.filter(instrument=instrument)

        return list(queryset.order_by("created_at"))

    def calculate_position_size(
        self, base_units: Decimal, scaling_factor: Decimal | None = None
    ) -> Decimal:
        """
        Calculate position size with optional scaling.

        Args:
            base_units: Base position size in units
            scaling_factor: Multiplier for scaling (default: 1.0)

        Returns:
            Calculated position size
        """
        if scaling_factor is None:
            scaling_factor = Decimal("1.0")
        return base_units * scaling_factor

    def calculate_pips(self, price1: Decimal, price2: Decimal, instrument: str) -> Decimal:
        """
        Calculate pip difference between two prices.

        For most currency pairs, 1 pip = 0.0001
        For JPY pairs, 1 pip = 0.01

        Args:
            price1: First price
            price2: Second price
            instrument: Currency pair (e.g., 'EUR_USD', 'USD_JPY')

        Returns:
            Pip difference
        """
        price_diff = abs(price2 - price1)

        # JPY pairs have different pip calculation
        if "JPY" in instrument:
            return price_diff / Decimal("0.01")

        return price_diff / Decimal("0.0001")

    def is_instrument_active(self, instrument: str) -> bool:
        """
        Check if an instrument is in the strategy's active instruments list.

        Args:
            instrument: Currency pair to check (e.g., 'EUR_USD')

        Returns:
            True if instrument is active for this strategy
        """
        return instrument in self.instruments

    def update_strategy_state(self, state_updates: dict[str, Any]) -> None:
        """
        Update strategy state with new values.

        Args:
            state_updates: Dictionary of state updates to apply
        """
        if not hasattr(self.strategy, "state"):
            # Create state if it doesn't exist
            # pylint: disable=import-outside-toplevel
            from .models import StrategyState

            StrategyState.objects.create(strategy=self.strategy)
            self.strategy.refresh_from_db()

        state = self.strategy.state

        # Update state fields
        for key, value in state_updates.items():
            if hasattr(state, key):
                setattr(state, key, value)

        state.last_tick_time = timezone.now()
        state.save()

    def get_strategy_state(self) -> dict[str, Any]:
        """
        Get current strategy state as a dictionary.

        Returns:
            Dictionary containing strategy state
        """
        if not hasattr(self.strategy, "state"):
            return {}

        state = self.strategy.state
        return {
            "current_layer": state.current_layer,
            "layer_states": state.layer_states,
            "atr_values": state.atr_values,
            "normal_atr": state.normal_atr,
            "last_tick_time": state.last_tick_time,
        }

    def log_strategy_event(
        self, event_type: str, description: str, details: dict[str, Any] | None = None
    ) -> None:
        """
        Log a strategy event for auditing and monitoring.

        Args:
            event_type: Type of event (e.g., 'signal_generated', 'position_opened')
            description: Human-readable description of the event
            details: Optional dictionary with additional event details
        """
        # pylint: disable=import-outside-toplevel
        from .event_models import Event

        if details is None:
            details = {}

        Event.objects.create(
            category="trading",
            event_type=event_type,
            severity="info",
            user=self.account.user,
            account=self.account,
            description=description,
            details=details,
        )

    def __str__(self) -> str:
        """String representation of the strategy."""
        return f"{self.__class__.__name__} for {self.account.account_id}"

    def __repr__(self) -> str:
        """Developer-friendly representation of the strategy."""
        return (
            f"<{self.__class__.__name__} "
            f"strategy_id={self.strategy.id} "
            f"account={self.account.account_id} "
            f"active={self.strategy.is_active}>"
        )
