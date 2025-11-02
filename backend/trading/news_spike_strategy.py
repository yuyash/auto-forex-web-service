"""
News/Spike Strategy implementation.

This module implements a News/Spike Strategy that:
- Detects volatility spikes (sudden ATR increase)
- Implements momentum entry in spike direction
- Implements quick profit-taking (20-30 pips)
- Implements trailing stop to capture extended moves

Requirements: 5.1, 5.3
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from .base_strategy import BaseStrategy
from .models import Order, Position
from .strategy_registry import register_strategy
from .tick_data_models import TickData


class VolatilitySpikeDetector:
    """
    Detect volatility spikes using ATR changes.

    Requirements: 5.1, 5.3
    """

    def __init__(self, lookback_minutes: int = 5, spike_threshold: Decimal | None = None) -> None:
        """
        Initialize the volatility spike detector.

        Args:
            lookback_minutes: Lookback period in minutes for baseline ATR
            spike_threshold: Multiplier for spike detection (e.g., 2.0 = 2x baseline)
        """
        self.lookback_minutes = lookback_minutes
        self.spike_threshold = spike_threshold if spike_threshold is not None else Decimal("2.0")
        self.price_history: dict[str, list[tuple[datetime, Decimal, Decimal, Decimal]]] = {}
        self.baseline_atr: dict[str, Decimal] = {}

    def add_price(  # pylint: disable=too-many-positional-arguments
        self, instrument: str, timestamp: datetime, high: Decimal, low: Decimal, close: Decimal
    ) -> None:
        """
        Add price data to history.

        Args:
            instrument: Currency pair
            timestamp: Price timestamp
            high: High price
            low: Low price
            close: Close price
        """
        if instrument not in self.price_history:
            self.price_history[instrument] = []

        self.price_history[instrument].append((timestamp, high, low, close))

        # Clean old prices (keep 2x lookback for baseline calculation)
        cutoff_time = timestamp - timedelta(minutes=self.lookback_minutes * 2)
        self.price_history[instrument] = [
            (ts, h, l, c) for ts, h, l, c in self.price_history[instrument] if ts > cutoff_time
        ]

    def calculate_atr(self, instrument: str, periods: int = 14) -> Decimal | None:
        """
        Calculate Average True Range.

        Args:
            instrument: Currency pair
            periods: Number of periods for ATR

        Returns:
            ATR value or None if insufficient data
        """
        if instrument not in self.price_history:
            return None

        history = self.price_history[instrument]
        # Need at least periods + 1 data points (one extra for previous close)
        if len(history) < 2:
            return None

        true_ranges: list[Decimal] = []
        for i in range(1, len(history)):
            prev_close = history[i - 1][3]
            current_high = history[i][1]
            current_low = history[i][2]

            tr = max(
                current_high - current_low,
                abs(current_high - prev_close),
                abs(current_low - prev_close),
            )
            true_ranges.append(tr)

        if len(true_ranges) == 0:
            return None

        # Use available data, up to periods
        num_periods = min(len(true_ranges), periods)
        recent_trs = true_ranges[-num_periods:]
        atr = sum(recent_trs) / Decimal(str(num_periods))

        return atr

    def detect_spike(
        self, instrument: str, current_time: datetime  # pylint: disable=unused-argument
    ) -> tuple[bool, Decimal | None, str | None]:
        """
        Detect volatility spike.

        Args:
            instrument: Currency pair
            current_time: Current timestamp

        Returns:
            Tuple of (is_spike, current_atr, direction)
            is_spike: True if spike detected
            current_atr: Current ATR value
            direction: 'bullish' or 'bearish' or None
        """
        current_atr = self.calculate_atr(instrument)
        if current_atr is None:
            return False, None, None

        # Update baseline ATR if not set or periodically
        if instrument not in self.baseline_atr:
            self.baseline_atr[instrument] = current_atr
            return False, current_atr, None

        baseline = self.baseline_atr[instrument]

        # Detect spike
        is_spike = current_atr >= (baseline * self.spike_threshold)

        # Determine direction from recent price movement
        direction = self._determine_direction(instrument)

        # Update baseline gradually (exponential moving average)
        alpha = Decimal("0.1")
        self.baseline_atr[instrument] = (alpha * current_atr) + ((Decimal("1") - alpha) * baseline)

        return is_spike, current_atr, direction

    def _determine_direction(self, instrument: str) -> str | None:
        """
        Determine momentum direction from recent price movement.

        Args:
            instrument: Currency pair

        Returns:
            'bullish', 'bearish', or None
        """
        if instrument not in self.price_history:
            return None

        history = self.price_history[instrument]
        if len(history) < 2:
            return None

        # Compare recent closes
        recent_closes = [close for _, _, _, close in history[-5:]]
        if len(recent_closes) < 2:
            return None

        start_price = recent_closes[0]
        end_price = recent_closes[-1]

        if end_price > start_price:
            return "bullish"
        if end_price < start_price:
            return "bearish"

        return None


class NewsSpikeStrategy(BaseStrategy):
    """
    News/Spike Strategy.

    This strategy:
    - Detects volatility spikes (sudden ATR increase)
    - Implements momentum entry in spike direction
    - Implements quick profit-taking (20-30 pips)
    - Implements trailing stop to capture extended moves

    Requirements: 5.1, 5.3
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the News/Spike Strategy."""
        super().__init__(*args, **kwargs)

        # Configuration
        self.base_units = Decimal(str(self.get_config_value("base_units", 1000)))
        self.spike_threshold = Decimal(str(self.get_config_value("spike_threshold", 2.0)))
        self.lookback_minutes = int(self.get_config_value("lookback_minutes", 5))
        self.quick_profit_pips = Decimal(str(self.get_config_value("quick_profit_pips", 25)))
        self.trailing_stop_pips = Decimal(str(self.get_config_value("trailing_stop_pips", 15)))
        self.trailing_activation_pips = Decimal(
            str(self.get_config_value("trailing_activation_pips", 10))
        )

        # Components
        self.spike_detector = VolatilitySpikeDetector(self.lookback_minutes, self.spike_threshold)

        # Track trailing stops for positions
        self.trailing_stops: dict[str, Decimal] = {}
        self.highest_profit: dict[str, Decimal] = {}

    def on_tick(self, tick_data: TickData) -> list[Order]:
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

        # Add price to spike detector (using mid as high/low/close for simplicity)
        self.spike_detector.add_price(
            tick_data.instrument, tick_data.timestamp, tick_data.mid, tick_data.mid, tick_data.mid
        )

        # Get open positions for this instrument
        open_positions = self.get_open_positions(tick_data.instrument)

        # Update trailing stops for existing positions
        if open_positions:
            trailing_orders = self._update_trailing_stops(tick_data, open_positions)
            if trailing_orders:
                orders.extend(trailing_orders)
                return orders

        # Don't enter new positions if we already have one
        if open_positions:
            return orders

        # Detect volatility spike
        is_spike, current_atr, direction = self.spike_detector.detect_spike(
            tick_data.instrument, tick_data.timestamp
        )

        # Check if spike detected with clear direction
        if not is_spike or direction is None:
            return orders

        # Generate entry signal
        entry_order = self._create_entry_order(tick_data, direction, current_atr)
        if entry_order:
            orders.append(entry_order)

        return orders

    def _update_trailing_stops(  # pylint: disable=too-many-branches
        self, tick_data: TickData, positions: list[Position]
    ) -> list[Order]:
        """
        Update trailing stops for open positions.

        Args:
            tick_data: Current tick data
            positions: List of open positions

        Returns:
            List of close orders if trailing stop hit
        """
        orders: list[Order] = []
        pip_value = Decimal("0.01") if "JPY" in tick_data.instrument else Decimal("0.0001")

        for position in positions:
            position_id = position.position_id

            # Calculate current profit in pips
            if position.direction == "long":
                profit_pips = (tick_data.mid - position.entry_price) / pip_value
            else:  # short
                profit_pips = (position.entry_price - tick_data.mid) / pip_value

            # Track highest profit
            if position_id not in self.highest_profit:
                self.highest_profit[position_id] = profit_pips
            else:
                self.highest_profit[position_id] = max(
                    self.highest_profit[position_id], profit_pips
                )

            # Check if trailing stop should be activated
            if self.highest_profit[position_id] >= self.trailing_activation_pips:
                # Calculate trailing stop price
                if position.direction == "long":
                    trailing_stop_price = tick_data.mid - (self.trailing_stop_pips * pip_value)
                else:  # short
                    trailing_stop_price = tick_data.mid + (self.trailing_stop_pips * pip_value)

                # Initialize or update trailing stop
                if position_id not in self.trailing_stops:
                    self.trailing_stops[position_id] = trailing_stop_price
                else:
                    # Move trailing stop only in favorable direction
                    if position.direction == "long":
                        self.trailing_stops[position_id] = max(
                            self.trailing_stops[position_id], trailing_stop_price
                        )
                    else:  # short
                        self.trailing_stops[position_id] = min(
                            self.trailing_stops[position_id], trailing_stop_price
                        )

                # Check if trailing stop hit
                stop_hit = (
                    position.direction == "long"
                    and tick_data.mid <= self.trailing_stops[position_id]
                ) or (
                    position.direction == "short"
                    and tick_data.mid >= self.trailing_stops[position_id]
                )

                if stop_hit:
                    close_order = self._create_close_order(position, tick_data, "trailing_stop")
                    if close_order:
                        orders.append(close_order)
                        # Clean up tracking
                        del self.trailing_stops[position_id]
                        del self.highest_profit[position_id]

            # Check quick profit target
            elif profit_pips >= self.quick_profit_pips:
                close_order = self._create_close_order(position, tick_data, "quick_profit")
                if close_order:
                    orders.append(close_order)
                    # Clean up tracking
                    if position_id in self.highest_profit:
                        del self.highest_profit[position_id]

        return orders

    def _create_entry_order(
        self, tick_data: TickData, direction: str, current_atr: Decimal | None
    ) -> Order | None:
        """
        Create entry order for spike trading.

        Args:
            tick_data: Current tick data
            direction: Momentum direction ('bullish' or 'bearish')
            current_atr: Current ATR value

        Returns:
            Order instance or None
        """
        # Map momentum direction to position direction
        position_direction = "long" if direction == "bullish" else "short"

        # Calculate take-profit
        pip_value = Decimal("0.01") if "JPY" in tick_data.instrument else Decimal("0.0001")

        if position_direction == "long":
            take_profit = tick_data.mid + (self.quick_profit_pips * pip_value)
        else:  # short
            take_profit = tick_data.mid - (self.quick_profit_pips * pip_value)

        order = Order(
            account=self.account,
            strategy=self.strategy,
            order_id=(f"news_spike_{position_direction}_" f"{tick_data.timestamp.timestamp()}"),
            instrument=tick_data.instrument,
            order_type="market",
            direction=position_direction,
            units=self.base_units,
            price=tick_data.mid,
            take_profit=take_profit,
        )

        self.log_strategy_event(
            "news_spike_entry",
            f"News/Spike entry: {position_direction}",
            {
                "instrument": tick_data.instrument,
                "direction": position_direction,
                "units": str(self.base_units),
                "price": str(tick_data.mid),
                "take_profit": str(take_profit),
                "current_atr": str(current_atr) if current_atr else None,
                "spike_direction": direction,
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
                f"news_spike_close_{position.position_id}_" f"{tick_data.timestamp.timestamp()}"
            ),
            instrument=position.instrument,
            order_type="market",
            direction=close_direction,
            units=position.units,
            price=tick_data.mid,
        )

        self.log_strategy_event(
            "news_spike_exit",
            f"News/Spike exit: {reason}",
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
            if position_id in self.trailing_stops:
                del self.trailing_stops[position_id]
            if position_id in self.highest_profit:
                del self.highest_profit[position_id]

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

    def validate_config(self, config: dict[str, Any]) -> bool:
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

        # Validate spike threshold
        spike_threshold = config.get("spike_threshold", 2.0)
        try:
            spike_threshold_decimal = Decimal(str(spike_threshold))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid spike_threshold: {spike_threshold}") from exc

        if spike_threshold_decimal <= Decimal("1.0"):
            raise ValueError("spike_threshold must be greater than 1.0")

        # Validate lookback minutes
        lookback_minutes = config.get("lookback_minutes", 5)
        try:
            lookback_int = int(lookback_minutes)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid lookback_minutes: {lookback_minutes}") from exc

        if lookback_int <= 0:
            raise ValueError("lookback_minutes must be positive")

        # Validate quick profit pips
        quick_profit_pips = config.get("quick_profit_pips", 25)
        try:
            quick_profit_decimal = Decimal(str(quick_profit_pips))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid quick_profit_pips: {quick_profit_pips}") from exc

        if quick_profit_decimal <= Decimal("0"):
            raise ValueError("quick_profit_pips must be positive")

        # Validate trailing stop pips
        trailing_stop_pips = config.get("trailing_stop_pips", 15)
        try:
            trailing_stop_decimal = Decimal(str(trailing_stop_pips))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid trailing_stop_pips: {trailing_stop_pips}") from exc

        if trailing_stop_decimal <= Decimal("0"):
            raise ValueError("trailing_stop_pips must be positive")

        # Validate trailing activation pips
        trailing_activation_pips = config.get("trailing_activation_pips", 10)
        try:
            trailing_activation_decimal = Decimal(str(trailing_activation_pips))
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Invalid trailing_activation_pips: {trailing_activation_pips}"
            ) from exc

        if trailing_activation_decimal <= Decimal("0"):
            raise ValueError("trailing_activation_pips must be positive")

        return True


# Configuration schema for News/Spike Strategy
NEWS_SPIKE_STRATEGY_CONFIG_SCHEMA = {
    "type": "object",
    "title": "News/Spike Strategy Configuration",
    "description": ("Configuration for News/Spike Strategy with " "volatility spike detection"),
    "properties": {
        "base_units": {
            "type": "number",
            "title": "Base Units",
            "description": "Base position size in units",
            "default": 1000,
            "minimum": 1,
        },
        "spike_threshold": {
            "type": "number",
            "title": "Spike Threshold",
            "description": "ATR multiplier for spike detection (e.g., 2.0 = 2x baseline)",
            "default": 2.0,
            "minimum": 1.1,
        },
        "lookback_minutes": {
            "type": "number",
            "title": "Lookback Minutes",
            "description": "Lookback period in minutes for baseline ATR",
            "default": 5,
            "minimum": 1,
        },
        "quick_profit_pips": {
            "type": "number",
            "title": "Quick Profit Pips",
            "description": "Quick profit target in pips (20-30 recommended)",
            "default": 25,
            "minimum": 1,
        },
        "trailing_stop_pips": {
            "type": "number",
            "title": "Trailing Stop Pips",
            "description": "Trailing stop distance in pips",
            "default": 15,
            "minimum": 1,
        },
        "trailing_activation_pips": {
            "type": "number",
            "title": "Trailing Activation Pips",
            "description": "Profit threshold to activate trailing stop",
            "default": 10,
            "minimum": 1,
        },
    },
    "required": [],
}

# Register the strategy
register_strategy("news_spike", NEWS_SPIKE_STRATEGY_CONFIG_SCHEMA)(NewsSpikeStrategy)
