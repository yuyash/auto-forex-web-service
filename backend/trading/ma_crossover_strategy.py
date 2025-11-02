"""
Moving Average Crossover Strategy implementation.

This module implements a Moving Average Crossover Strategy that:
- Uses fast EMA (12) and slow EMA (26) for crossover detection
- Enters long when fast EMA crosses above slow EMA (bullish crossover)
- Enters short when fast EMA crosses below slow EMA (bearish crossover)
- Exits positions on opposite crossover

Requirements: 5.1, 5.3
"""

from collections import deque
from decimal import Decimal
from typing import Any

from .base_strategy import BaseStrategy
from .models import Order, Position
from .strategy_registry import register_strategy
from .tick_data_models import TickData


class EMACalculator:
    """
    Calculate Exponential Moving Average (EMA).

    Requirements: 5.1, 5.3
    """

    def __init__(self, period: int) -> None:
        """
        Initialize the EMA calculator.

        Args:
            period: Number of periods for the EMA
        """
        self.period = period
        self.prices: deque[Decimal] = deque(maxlen=period * 2)
        self.ema: Decimal | None = None
        self.multiplier = Decimal(2) / Decimal(period + 1)

    def add_price(self, price: Decimal) -> None:
        """
        Add a new price and update the EMA.

        Args:
            price: New price to add
        """
        self.prices.append(price)

        if self.ema is None:
            # Initialize with SMA if we have enough data
            if len(self.prices) >= self.period:
                sma = sum(list(self.prices)[-self.period :])
                sma = sma / Decimal(self.period)
                self.ema = sma
        else:
            # Calculate EMA
            # EMA = (Price - Previous EMA) * Multiplier + Previous EMA
            self.ema = (price - self.ema) * self.multiplier + self.ema

    def get_ema(self) -> Decimal | None:
        """
        Get the current EMA value.

        Returns:
            Current EMA or None if not enough data
        """
        return self.ema

    def is_ready(self) -> bool:
        """
        Check if EMA has enough data to be calculated.

        Returns:
            True if EMA is ready
        """
        return self.ema is not None


class CrossoverDetector:
    """
    Detect moving average crossovers.

    Requirements: 5.1, 5.3
    """

    def __init__(self, fast_period: int = 12, slow_period: int = 26) -> None:
        """
        Initialize the crossover detector.

        Args:
            fast_period: Period for fast EMA (default: 12)
            slow_period: Period for slow EMA (default: 26)
        """
        self.fast_ema = EMACalculator(fast_period)
        self.slow_ema = EMACalculator(slow_period)
        self.previous_fast: Decimal | None = None
        self.previous_slow: Decimal | None = None

    def add_price(self, price: Decimal) -> None:
        """
        Add a new price to both EMAs.

        Args:
            price: New price to add
        """
        # Store previous values before updating
        self.previous_fast = self.fast_ema.get_ema()
        self.previous_slow = self.slow_ema.get_ema()

        # Update EMAs
        self.fast_ema.add_price(price)
        self.slow_ema.add_price(price)

    def get_crossover_signal(self) -> str | None:
        """
        Detect crossover signals.

        Returns:
            'bullish' if fast crosses above slow (buy signal)
            'bearish' if fast crosses below slow (sell signal)
            None if no crossover or not enough data
        """
        if not self.is_ready():
            return None

        current_fast = self.fast_ema.get_ema()
        current_slow = self.slow_ema.get_ema()

        # Need previous values to detect crossover
        if (
            self.previous_fast is None
            or self.previous_slow is None
            or current_fast is None
            or current_slow is None
        ):
            return None

        # Bullish crossover: fast crosses above slow
        if self.previous_fast <= self.previous_slow and current_fast > current_slow:
            return "bullish"

        # Bearish crossover: fast crosses below slow
        if self.previous_fast >= self.previous_slow and current_fast < current_slow:
            return "bearish"

        return None

    def get_current_position(self) -> str | None:
        """
        Get the current position of fast MA relative to slow MA.

        Returns:
            'above' if fast is above slow
            'below' if fast is below slow
            None if not enough data
        """
        if not self.is_ready():
            return None

        fast = self.fast_ema.get_ema()
        slow = self.slow_ema.get_ema()

        if fast is None or slow is None:
            return None

        if fast > slow:
            return "above"
        if fast < slow:
            return "below"
        return None

    def is_ready(self) -> bool:
        """
        Check if both EMAs are ready.

        Returns:
            True if both EMAs have enough data
        """
        return self.fast_ema.is_ready() and self.slow_ema.is_ready()


class MACrossoverStrategy(BaseStrategy):
    """
    Moving Average Crossover Strategy.

    This strategy:
    - Uses fast EMA (12) and slow EMA (26)
    - Enters long when fast EMA crosses above slow EMA (bullish crossover)
    - Enters short when fast EMA crosses below slow EMA (bearish crossover)
    - Exits positions on opposite crossover

    Requirements: 5.1, 5.3
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the MA Crossover Strategy."""
        super().__init__(*args, **kwargs)

        # Configuration
        self.fast_period = int(self.get_config_value("fast_period", 12))
        self.slow_period = int(self.get_config_value("slow_period", 26))
        self.base_units = Decimal(str(self.get_config_value("base_units", 1000)))

        # Components
        self.crossover_detectors: dict[str, CrossoverDetector] = {}

        # Initialize crossover detectors for each instrument
        for instrument in self.instruments:
            detector = CrossoverDetector(self.fast_period, self.slow_period)
            self.crossover_detectors[instrument] = detector

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

        detector = self.crossover_detectors.get(tick_data.instrument)
        if not detector:
            return orders

        # Update detector with new price
        detector.add_price(tick_data.mid)

        if not detector.is_ready():
            return orders

        # Get open positions for this instrument
        open_positions = self.get_open_positions(tick_data.instrument)

        # Check for crossover signal
        signal = detector.get_crossover_signal()

        if signal:
            # Process crossover signal
            crossover_orders = self._process_crossover(signal, open_positions, tick_data)
            orders.extend(crossover_orders)

        return orders

    def _process_crossover(
        self,
        signal: str,
        positions: list[Position],
        tick_data: TickData,
    ) -> list[Order]:
        """
        Process crossover signal and generate orders.

        Args:
            signal: Crossover signal ('bullish' or 'bearish')
            positions: List of open positions
            tick_data: Current tick data

        Returns:
            List of orders to execute
        """
        orders: list[Order] = []

        # Close opposite positions
        for position in positions:
            if self._is_opposite_signal(signal, position.direction):
                close_order = self._create_close_order(position, tick_data, "opposite_crossover")
                if close_order:
                    orders.append(close_order)

        # Enter new position if we don't have one in the signal direction
        if not self._has_position_in_direction(signal, positions):
            entry_order = self._create_entry_order(tick_data, signal)
            if entry_order:
                orders.append(entry_order)

        return orders

    def _is_opposite_signal(self, signal: str, direction: str) -> bool:
        """
        Check if position direction is opposite to signal.

        Args:
            signal: Crossover signal ('bullish' or 'bearish')
            direction: Position direction ('long' or 'short')

        Returns:
            True if opposite
        """
        return (signal == "bullish" and direction == "short") or (
            signal == "bearish" and direction == "long"
        )

    def _has_position_in_direction(self, signal: str, positions: list[Position]) -> bool:
        """
        Check if there's already a position in the signal direction.

        Args:
            signal: Crossover signal ('bullish' or 'bearish')
            positions: List of open positions

        Returns:
            True if position exists in signal direction
        """
        return any(
            (signal == "bullish" and p.direction == "long")
            or (signal == "bearish" and p.direction == "short")
            for p in positions
        )

    def _create_entry_order(self, tick_data: TickData, signal: str) -> Order | None:
        """
        Create entry order based on crossover signal.

        Args:
            tick_data: Current tick data
            signal: Crossover signal ('bullish' or 'bearish')

        Returns:
            Order instance or None
        """
        direction = "long" if signal == "bullish" else "short"

        order = Order(
            account=self.account,
            strategy=self.strategy,
            order_id=(f"ma_crossover_{direction}_" f"{tick_data.timestamp.timestamp()}"),
            instrument=tick_data.instrument,
            order_type="market",
            direction=direction,
            units=self.base_units,
            price=tick_data.mid,
        )

        self.log_strategy_event(
            "ma_crossover_entry",
            f"MA Crossover entry: {signal} crossover detected",
            {
                "instrument": tick_data.instrument,
                "signal": signal,
                "direction": direction,
                "units": str(self.base_units),
                "price": str(tick_data.mid),
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
                f"ma_crossover_close_{position.position_id}_" f"{tick_data.timestamp.timestamp()}"
            ),
            instrument=position.instrument,
            order_type="market",
            direction=close_direction,
            units=position.units,
            price=tick_data.mid,
        )

        self.log_strategy_event(
            "ma_crossover_exit",
            f"MA Crossover exit: {reason}",
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
        # No special handling needed for MA Crossover strategy

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
        # Validate periods
        fast_period = config.get("fast_period", 12)
        slow_period = config.get("slow_period", 26)

        if not isinstance(fast_period, int) or fast_period < 1:
            raise ValueError("fast_period must be a positive integer")

        if not isinstance(slow_period, int) or slow_period < 1:
            raise ValueError("slow_period must be a positive integer")

        if fast_period >= slow_period:
            raise ValueError("fast_period must be less than slow_period")

        # Validate base units
        base_units = config.get("base_units", 1000)
        try:
            base_units_decimal = Decimal(str(base_units))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid base_units: {base_units}") from exc

        if base_units_decimal <= Decimal("0"):
            raise ValueError("base_units must be positive")

        return True


# Configuration schema for MA Crossover Strategy
MA_CROSSOVER_CONFIG_SCHEMA = {
    "type": "object",
    "title": "MA Crossover Strategy Configuration",
    "description": "Configuration for Moving Average Crossover Strategy",
    "properties": {
        "fast_period": {
            "type": "integer",
            "title": "Fast EMA Period",
            "description": "Period for fast exponential moving average",
            "default": 12,
            "minimum": 1,
        },
        "slow_period": {
            "type": "integer",
            "title": "Slow EMA Period",
            "description": "Period for slow exponential moving average",
            "default": 26,
            "minimum": 1,
        },
        "base_units": {
            "type": "number",
            "title": "Base Units",
            "description": "Base position size in units",
            "default": 1000,
            "minimum": 1,
        },
    },
    "required": [],
}

# Register the strategy
register_strategy("ma_crossover", MA_CROSSOVER_CONFIG_SCHEMA)(MACrossoverStrategy)
