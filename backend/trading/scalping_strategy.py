"""
Scalping Strategy implementation.

This module implements a Scalping Strategy that:
- Detects short-term momentum (1-5 minute timeframe)
- Implements quick entry/exit logic (5-10 pip targets)
- Uses tight stop-loss (3-5 pips)
- Enforces maximum holding time (5-15 minutes)

Requirements: 5.1, 5.3
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from .base_strategy import BaseStrategy
from .models import Order, Position
from .strategy_registry import register_strategy
from .tick_data_models import TickData


class MomentumDetector:
    """
    Detect short-term momentum using price changes.

    Requirements: 5.1, 5.3
    """

    def __init__(self, lookback_seconds: int = 60) -> None:
        """
        Initialize the momentum detector.

        Args:
            lookback_seconds: Lookback period in seconds for momentum
        """
        self.lookback_seconds = lookback_seconds
        self.price_history: dict[str, list[tuple[datetime, Decimal]]] = {}

    def add_price(self, instrument: str, timestamp: datetime, price: Decimal) -> None:
        """
        Add price to history.

        Args:
            instrument: Currency pair
            timestamp: Price timestamp
            price: Price value
        """
        if instrument not in self.price_history:
            self.price_history[instrument] = []

        self.price_history[instrument].append((timestamp, price))

        # Clean old prices
        cutoff_time = timestamp - timedelta(seconds=self.lookback_seconds * 2)
        self.price_history[instrument] = [
            (ts, p) for ts, p in self.price_history[instrument] if ts > cutoff_time
        ]

    def detect_momentum(
        self, instrument: str, current_time: datetime
    ) -> tuple[str | None, Decimal]:
        """
        Detect momentum direction and strength.

        Args:
            instrument: Currency pair
            current_time: Current timestamp

        Returns:
            Tuple of (direction, strength_pips)
            direction: 'bullish', 'bearish', or None
            strength_pips: Momentum strength in pips
        """
        if instrument not in self.price_history:
            return None, Decimal("0")

        history = self.price_history[instrument]
        if len(history) < 2:
            return None, Decimal("0")

        # Get prices from lookback period
        cutoff_time = current_time - timedelta(seconds=self.lookback_seconds)
        recent_prices = [(ts, p) for ts, p in history if ts >= cutoff_time]

        if len(recent_prices) < 2:
            return None, Decimal("0")

        # Calculate price change
        start_price = recent_prices[0][1]
        end_price = recent_prices[-1][1]
        price_change = end_price - start_price

        # Calculate pip change
        pip_value = Decimal("0.01") if "JPY" in instrument else Decimal("0.0001")
        pip_change = price_change / pip_value

        # Determine direction
        if pip_change > Decimal("0"):
            return "bullish", abs(pip_change)
        if pip_change < Decimal("0"):
            return "bearish", abs(pip_change)

        return None, Decimal("0")


class ScalpingStrategy(BaseStrategy):
    """
    Scalping Strategy.

    This strategy:
    - Detects short-term momentum (1-5 minute timeframe)
    - Implements quick entry/exit logic (5-10 pip targets)
    - Uses tight stop-loss (3-5 pips)
    - Enforces maximum holding time (5-15 minutes)

    Requirements: 5.1, 5.3
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the Scalping Strategy."""
        super().__init__(*args, **kwargs)

        # Configuration
        self.base_units = Decimal(str(self.get_config_value("base_units", 1000)))
        self.momentum_lookback_seconds = int(self.get_config_value("momentum_lookback_seconds", 60))
        self.min_momentum_pips = Decimal(str(self.get_config_value("min_momentum_pips", 3)))
        self.stop_loss_pips = Decimal(str(self.get_config_value("stop_loss_pips", 4)))
        self.take_profit_pips = Decimal(str(self.get_config_value("take_profit_pips", 7)))
        self.max_holding_minutes = int(self.get_config_value("max_holding_minutes", 10))

        # Components
        self.momentum_detector = MomentumDetector(self.momentum_lookback_seconds)

        # Track position entry times
        self.position_entry_times: dict[str, datetime] = {}

    def on_tick(  # pylint: disable=too-many-return-statements
        self, tick_data: TickData
    ) -> list[Order]:
        """
        Process incoming tick data and generate trading signals.

        Args:
            tick_data: TickData instance containing market data

        Returns:
            List of Order instances to execute

        Requirements: 5.1, 5.3
        """
        orders: list[Order] = []

        # Validate prerequisites
        if not self.is_instrument_active(tick_data.instrument):
            return orders

        # Add price to momentum detector
        self.momentum_detector.add_price(tick_data.instrument, tick_data.timestamp, tick_data.mid)

        # Get open positions for this instrument
        open_positions = self.get_open_positions(tick_data.instrument)

        # Check for maximum holding time exits
        holding_time_orders = self._check_holding_time(tick_data, open_positions)
        if holding_time_orders:
            orders.extend(holding_time_orders)
            return orders

        # Don't enter new positions if we already have one
        if open_positions:
            return orders

        # Detect momentum
        direction, strength = self.momentum_detector.detect_momentum(
            tick_data.instrument, tick_data.timestamp
        )

        # Check if momentum is strong enough
        if direction is None or strength < self.min_momentum_pips:
            return orders

        # Generate entry signal
        entry_order = self._create_entry_order(tick_data, direction)
        if entry_order:
            orders.append(entry_order)

        return orders

    def _check_holding_time(self, tick_data: TickData, positions: list[Position]) -> list[Order]:
        """
        Check if positions exceed maximum holding time.

        Args:
            tick_data: Current tick data
            positions: List of open positions

        Returns:
            List of close orders
        """
        orders: list[Order] = []
        max_holding_delta = timedelta(minutes=self.max_holding_minutes)

        for position in positions:
            position_id = position.position_id

            # Track entry time
            if position_id not in self.position_entry_times:
                self.position_entry_times[position_id] = position.opened_at

            entry_time = self.position_entry_times[position_id]
            holding_time = tick_data.timestamp - entry_time

            # Close if holding time exceeded
            if holding_time >= max_holding_delta:
                close_order = self._create_close_order(position, tick_data, "max_holding_time")
                if close_order:
                    orders.append(close_order)
                    # Clean up tracking
                    del self.position_entry_times[position_id]

        return orders

    def _create_entry_order(self, tick_data: TickData, direction: str) -> Order | None:
        """
        Create entry order for scalping.

        Args:
            tick_data: Current tick data
            direction: Momentum direction ('bullish' or 'bearish')

        Returns:
            Order instance or None
        """
        # Map momentum direction to position direction
        position_direction = "long" if direction == "bullish" else "short"

        # Calculate stop-loss and take-profit
        pip_value = Decimal("0.01") if "JPY" in tick_data.instrument else Decimal("0.0001")

        if position_direction == "long":
            stop_loss = tick_data.mid - (self.stop_loss_pips * pip_value)
            take_profit = tick_data.mid + (self.take_profit_pips * pip_value)
        else:  # short
            stop_loss = tick_data.mid + (self.stop_loss_pips * pip_value)
            take_profit = tick_data.mid - (self.take_profit_pips * pip_value)

        order = Order(
            account=self.account,
            strategy=self.strategy,
            order_id=(f"scalping_{position_direction}_" f"{tick_data.timestamp.timestamp()}"),
            instrument=tick_data.instrument,
            order_type="market",
            direction=position_direction,
            units=self.base_units,
            price=tick_data.mid,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )

        self.log_strategy_event(
            "scalping_entry",
            f"Scalping entry: {position_direction}",
            {
                "instrument": tick_data.instrument,
                "direction": position_direction,
                "units": str(self.base_units),
                "price": str(tick_data.mid),
                "stop_loss": str(stop_loss),
                "take_profit": str(take_profit),
                "momentum_direction": direction,
            },
        )

        return order

    def _create_close_order(
        self, position: Position, tick_data: TickData, reason: str
    ) -> Order | None:
        """
        Create order to close a position.

        Args:
            position: Position to close
            tick_data: Current tick data
            reason: Reason for closing

        Returns:
            Close order or None
        """
        # Reverse direction for closing
        close_direction = "short" if position.direction == "long" else "long"

        order = Order(
            account=self.account,
            strategy=self.strategy,
            order_id=(
                f"scalping_close_{position.position_id}_" f"{tick_data.timestamp.timestamp()}"
            ),
            instrument=position.instrument,
            order_type="market",
            direction=close_direction,
            units=position.units,
            price=tick_data.mid,
        )

        self.log_strategy_event(
            "scalping_exit",
            f"Scalping exit: {reason}",
            {
                "position_id": position.position_id,
                "instrument": position.instrument,
                "direction": position.direction,
                "entry_price": str(position.entry_price),
                "exit_price": str(tick_data.mid),
                "units": str(position.units),
                "reason": reason,
            },
        )

        return order

    def on_position_update(self, position: Position) -> None:
        """
        Handle position updates.

        Args:
            position: Position that was updated

        Requirements: 5.1, 5.3
        """
        # Clean up tracking when position is closed
        if position.closed_at is not None:
            position_id = position.position_id
            if position_id in self.position_entry_times:
                del self.position_entry_times[position_id]

            self.log_strategy_event(
                "position_closed",
                f"Position closed: {position.position_id}",
                {
                    "position_id": position.position_id,
                    "instrument": position.instrument,
                    "direction": position.direction,
                    "entry_price": str(position.entry_price),
                    "exit_price": str(position.current_price),
                    "units": str(position.units),
                },
            )

    def validate_config(
        self, config: dict[str, Any]
    ) -> bool:  # pylint: disable=too-many-return-statements
        """
        Validate strategy configuration.

        Args:
            config: Configuration dictionary

        Returns:
            True if valid

        Raises:
            ValueError: If configuration is invalid

        Requirements: 5.1
        """
        # Validate base units
        base_units = config.get("base_units", 1000)
        try:
            base_units_decimal = Decimal(str(base_units))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid base_units: {base_units}") from exc

        if base_units_decimal <= Decimal("0"):
            raise ValueError("base_units must be positive")

        # Validate momentum lookback seconds
        momentum_lookback_seconds = config.get("momentum_lookback_seconds", 60)
        try:
            lookback_int = int(momentum_lookback_seconds)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Invalid momentum_lookback_seconds: " f"{momentum_lookback_seconds}"
            ) from exc

        if lookback_int <= 0:
            raise ValueError("momentum_lookback_seconds must be positive")

        # Validate minimum momentum pips
        min_momentum_pips = config.get("min_momentum_pips", 3)
        try:
            min_momentum_decimal = Decimal(str(min_momentum_pips))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid min_momentum_pips: {min_momentum_pips}") from exc

        if min_momentum_decimal <= Decimal("0"):
            raise ValueError("min_momentum_pips must be positive")

        # Validate stop loss pips
        stop_loss_pips = config.get("stop_loss_pips", 4)
        try:
            stop_loss_decimal = Decimal(str(stop_loss_pips))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid stop_loss_pips: {stop_loss_pips}") from exc

        if stop_loss_decimal <= Decimal("0"):
            raise ValueError("stop_loss_pips must be positive")

        # Validate take profit pips
        take_profit_pips = config.get("take_profit_pips", 7)
        try:
            take_profit_decimal = Decimal(str(take_profit_pips))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid take_profit_pips: {take_profit_pips}") from exc

        if take_profit_decimal <= Decimal("0"):
            raise ValueError("take_profit_pips must be positive")

        # Validate maximum holding minutes
        max_holding_minutes = config.get("max_holding_minutes", 10)
        try:
            max_holding_int = int(max_holding_minutes)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid max_holding_minutes: {max_holding_minutes}") from exc

        if max_holding_int <= 0:
            raise ValueError("max_holding_minutes must be positive")

        return True


# Configuration schema for Scalping Strategy
SCALPING_STRATEGY_CONFIG_SCHEMA = {
    "type": "object",
    "title": "Scalping Strategy Configuration",
    "description": ("Configuration for Scalping Strategy with " "short-term momentum trading"),
    "properties": {
        "base_units": {
            "type": "number",
            "title": "Base Units",
            "description": "Base position size in units",
            "default": 1000,
            "minimum": 1,
        },
        "momentum_lookback_seconds": {
            "type": "number",
            "title": "Momentum Lookback Seconds",
            "description": "Lookback period in seconds for momentum",
            "default": 60,
            "minimum": 10,
        },
        "min_momentum_pips": {
            "type": "number",
            "title": "Minimum Momentum Pips",
            "description": "Minimum momentum strength in pips to enter",
            "default": 3,
            "minimum": 1,
        },
        "stop_loss_pips": {
            "type": "number",
            "title": "Stop Loss Pips",
            "description": "Tight stop loss distance in pips",
            "default": 4,
            "minimum": 1,
        },
        "take_profit_pips": {
            "type": "number",
            "title": "Take Profit Pips",
            "description": "Quick take profit target in pips",
            "default": 7,
            "minimum": 1,
        },
        "max_holding_minutes": {
            "type": "number",
            "title": "Maximum Holding Minutes",
            "description": "Maximum time to hold a position in minutes",
            "default": 10,
            "minimum": 1,
        },
    },
    "required": [],
}

# Register the strategy
register_strategy("scalping", SCALPING_STRATEGY_CONFIG_SCHEMA, display_name="Scalping Strategy")(
    ScalpingStrategy
)
