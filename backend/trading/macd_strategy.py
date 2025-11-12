"""
MACD Strategy implementation with signal line crossovers.

This module implements a MACD (Moving Average Convergence Divergence) Strategy that:
- Calculates MACD using 12, 26, 9 periods (fast EMA, slow EMA, signal line)
- Enters long when MACD crosses above signal line (bullish signal)
- Enters short when MACD crosses below signal line (bearish signal)
- Analyzes histogram for momentum confirmation

Requirements: 5.1, 5.3
"""

from collections import deque
from decimal import Decimal
from typing import Any

from .base_strategy import BaseStrategy
from .models import Order, Position
from .strategy_registry import register_strategy
from .tick_data_models import TickData


class MACDCalculator:
    """
    Calculate MACD (Moving Average Convergence Divergence).

    MACD Line = 12-period EMA - 26-period EMA
    Signal Line = 9-period EMA of MACD Line
    Histogram = MACD Line - Signal Line

    Requirements: 5.1, 5.3
    """

    def __init__(
        self, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9
    ) -> None:
        """
        Initialize the MACD calculator.

        Args:
            fast_period: Period for fast EMA (default: 12)
            slow_period: Period for slow EMA (default: 26)
            signal_period: Period for signal line EMA (default: 9)
        """
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period

        # Price storage
        self.prices: deque[Decimal] = deque(maxlen=slow_period * 2)

        # EMA values
        self.fast_ema: Decimal | None = None
        self.slow_ema: Decimal | None = None
        self.signal_ema: Decimal | None = None

        # MACD values
        self.macd_line: Decimal | None = None
        self.signal_line: Decimal | None = None
        self.histogram: Decimal | None = None

        # MACD line history for signal line calculation
        self.macd_history: deque[Decimal] = deque(maxlen=signal_period * 2)

        # Multipliers for EMA calculation
        self.fast_multiplier = Decimal(2) / Decimal(fast_period + 1)
        self.slow_multiplier = Decimal(2) / Decimal(slow_period + 1)
        self.signal_multiplier = Decimal(2) / Decimal(signal_period + 1)

    def add_price(self, price: Decimal) -> None:
        """
        Add a new price and update MACD.

        Args:
            price: New price to add
        """
        self.prices.append(price)

        # Update fast EMA
        if self.fast_ema is None:
            if len(self.prices) >= self.fast_period:
                # Initialize with SMA
                sma = sum(list(self.prices)[-self.fast_period :]) / Decimal(self.fast_period)
                self.fast_ema = sma
        else:
            # Calculate EMA
            self.fast_ema = (price - self.fast_ema) * self.fast_multiplier + self.fast_ema

        # Update slow EMA
        if self.slow_ema is None:
            if len(self.prices) >= self.slow_period:
                # Initialize with SMA
                sma = sum(list(self.prices)[-self.slow_period :]) / Decimal(self.slow_period)
                self.slow_ema = sma
        else:
            # Calculate EMA
            self.slow_ema = (price - self.slow_ema) * self.slow_multiplier + self.slow_ema

        # Calculate MACD line if both EMAs are ready
        if self.fast_ema is not None and self.slow_ema is not None:
            self.macd_line = self.fast_ema - self.slow_ema
            self.macd_history.append(self.macd_line)

            # Calculate signal line
            if self.signal_ema is None:
                if len(self.macd_history) >= self.signal_period:
                    # Initialize with SMA of MACD line
                    sma = sum(list(self.macd_history)[-self.signal_period :]) / Decimal(
                        self.signal_period
                    )
                    self.signal_ema = sma
                    self.signal_line = sma
            else:
                # Calculate signal line EMA
                self.signal_ema = (
                    self.macd_line - self.signal_ema
                ) * self.signal_multiplier + self.signal_ema
                self.signal_line = self.signal_ema

            # Calculate histogram
            if self.signal_line is not None:
                self.histogram = self.macd_line - self.signal_line

    def get_macd_line(self) -> Decimal | None:
        """
        Get the current MACD line value.

        Returns:
            Current MACD line or None if not enough data
        """
        return self.macd_line

    def get_signal_line(self) -> Decimal | None:
        """
        Get the current signal line value.

        Returns:
            Current signal line or None if not enough data
        """
        return self.signal_line

    def get_histogram(self) -> Decimal | None:
        """
        Get the current histogram value.

        Returns:
            Current histogram or None if not enough data
        """
        return self.histogram

    def is_ready(self) -> bool:
        """
        Check if MACD has enough data to be calculated.

        Returns:
            True if MACD is ready
        """
        return (
            self.macd_line is not None
            and self.signal_line is not None
            and self.histogram is not None
        )


class MACDCrossoverDetector:
    """
    Detect MACD crossovers and histogram momentum.

    Requirements: 5.1, 5.3
    """

    def __init__(self) -> None:
        """Initialize the crossover detector."""
        self.previous_macd: Decimal | None = None
        self.previous_signal: Decimal | None = None
        self.previous_histogram: Decimal | None = None

    def update(self, macd: Decimal, signal: Decimal, histogram: Decimal) -> None:
        """
        Update with new MACD values.

        Args:
            macd: Current MACD line value
            signal: Current signal line value
            histogram: Current histogram value
        """
        self.previous_macd = macd
        self.previous_signal = signal
        self.previous_histogram = histogram

    def detect_crossover(self, macd: Decimal, signal: Decimal) -> str | None:
        """
        Detect MACD crossover signals.

        Args:
            macd: Current MACD line value
            signal: Current signal line value

        Returns:
            'bullish' if MACD crosses above signal (buy signal)
            'bearish' if MACD crosses below signal (sell signal)
            None if no crossover or not enough data
        """
        if self.previous_macd is None or self.previous_signal is None:
            return None

        # Bullish crossover: MACD crosses above signal
        if self.previous_macd <= self.previous_signal and macd > signal:
            return "bullish"

        # Bearish crossover: MACD crosses below signal
        if self.previous_macd >= self.previous_signal and macd < signal:
            return "bearish"

        return None

    def analyze_histogram_momentum(self, histogram: Decimal) -> str:
        """
        Analyze histogram for momentum.

        Args:
            histogram: Current histogram value

        Returns:
            'increasing' if histogram is growing (strengthening momentum)
            'decreasing' if histogram is shrinking (weakening momentum)
            'neutral' if no previous data
        """
        if self.previous_histogram is None:
            return "neutral"

        if histogram > self.previous_histogram:
            return "increasing"
        if histogram < self.previous_histogram:
            return "decreasing"
        return "neutral"

    def get_histogram_direction(self, histogram: Decimal) -> str:
        """
        Get histogram direction (positive or negative).

        Args:
            histogram: Current histogram value

        Returns:
            'positive' if histogram > 0 (bullish)
            'negative' if histogram < 0 (bearish)
            'zero' if histogram == 0
        """
        if histogram > Decimal("0"):
            return "positive"
        if histogram < Decimal("0"):
            return "negative"
        return "zero"


class MACDStrategy(BaseStrategy):
    """
    MACD Strategy with signal line crossovers and histogram analysis.

    This strategy:
    - Calculates MACD using 12, 26, 9 periods
    - Enters long when MACD crosses above signal line (bullish signal)
    - Enters short when MACD crosses below signal line (bearish signal)
    - Analyzes histogram for momentum confirmation

    Requirements: 5.1, 5.3
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the MACD Strategy."""
        super().__init__(*args, **kwargs)

        # Configuration
        self.fast_period = int(self.get_config_value("fast_period", 12))
        self.slow_period = int(self.get_config_value("slow_period", 26))
        self.signal_period = int(self.get_config_value("signal_period", 9))
        self.base_units = Decimal(str(self.get_config_value("base_units", 1000)))
        self.use_histogram_confirmation = bool(
            self.get_config_value("use_histogram_confirmation", True)
        )

        # Components
        self.macd_calculators: dict[str, MACDCalculator] = {}
        self.crossover_detectors: dict[str, MACDCrossoverDetector] = {}

        # Initialize component for the instrument
        self.macd_calculators[self.instrument] = MACDCalculator(
            self.fast_period, self.slow_period, self.signal_period
        )
        self.crossover_detectors[self.instrument] = MACDCrossoverDetector()

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

        calculator = self.macd_calculators.get(tick_data.instrument)
        detector = self.crossover_detectors.get(tick_data.instrument)

        if not calculator or not detector:
            return orders

        # Update MACD with new price
        calculator.add_price(tick_data.mid)

        if not calculator.is_ready():
            return orders

        # Get MACD values
        macd = calculator.get_macd_line()
        signal = calculator.get_signal_line()
        histogram = calculator.get_histogram()

        if macd is None or signal is None or histogram is None:
            return orders

        # Detect crossover
        crossover_signal = detector.detect_crossover(macd, signal)

        # Analyze histogram momentum
        momentum = detector.analyze_histogram_momentum(histogram)
        histogram_direction = detector.get_histogram_direction(histogram)

        # Update detector with current values
        detector.update(macd, signal, histogram)

        # Get open positions for this instrument
        open_positions = self.get_open_positions(tick_data.instrument)

        # Process crossover signal if detected
        if crossover_signal:
            # Check histogram confirmation if enabled
            if self.use_histogram_confirmation and not self._confirm_with_histogram(
                crossover_signal, histogram_direction
            ):
                return orders

            crossover_orders = self._process_crossover(
                crossover_signal, open_positions, tick_data, macd, signal, histogram, momentum
            )
            orders.extend(crossover_orders)

        return orders

    def _confirm_with_histogram(self, signal: str, histogram_direction: str) -> bool:
        """
        Confirm crossover signal with histogram direction.

        Args:
            signal: Crossover signal ('bullish' or 'bearish')
            histogram_direction: Histogram direction ('positive', 'negative', 'zero')

        Returns:
            True if histogram confirms the signal
        """
        # Bullish signal should have positive or zero histogram
        if signal == "bullish":
            return histogram_direction in ("positive", "zero")

        # Bearish signal should have negative or zero histogram
        if signal == "bearish":
            return histogram_direction in ("negative", "zero")

        return False

    def _process_crossover(  # pylint: disable=too-many-positional-arguments
        self,
        signal: str,
        positions: list[Position],
        tick_data: TickData,
        macd: Decimal,
        signal_line: Decimal,
        histogram: Decimal,
        momentum: str,
    ) -> list[Order]:
        """
        Process crossover signal and generate orders.

        Args:
            signal: Crossover signal ('bullish' or 'bearish')
            positions: List of open positions
            tick_data: Current tick data
            macd: Current MACD line value
            signal_line: Current signal line value
            histogram: Current histogram value
            momentum: Histogram momentum ('increasing', 'decreasing', 'neutral')

        Returns:
            List of orders to execute
        """
        orders: list[Order] = []

        # Close opposite positions
        for position in positions:
            if self._is_opposite_signal(signal, position.direction):
                close_order = self._create_close_order(
                    position, tick_data, "opposite_crossover", macd, signal_line, histogram
                )
                if close_order:
                    orders.append(close_order)

        # Enter new position if we don't have one in the signal direction
        if not self._has_position_in_direction(signal, positions):
            entry_order = self._create_entry_order(
                tick_data, signal, macd, signal_line, histogram, momentum
            )
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

    def _create_entry_order(  # pylint: disable=too-many-positional-arguments
        self,
        tick_data: TickData,
        signal: str,
        macd: Decimal,
        signal_line: Decimal,
        histogram: Decimal,
        momentum: str,
    ) -> Order | None:
        """
        Create entry order based on MACD crossover signal.

        Args:
            tick_data: Current tick data
            signal: Crossover signal ('bullish' or 'bearish')
            macd: Current MACD line value
            signal_line: Current signal line value
            histogram: Current histogram value
            momentum: Histogram momentum

        Returns:
            Order instance or None
        """
        direction = "long" if signal == "bullish" else "short"

        order = Order(
            account=self.account,
            strategy=self.strategy,
            order_id=f"macd_{direction}_{tick_data.timestamp.timestamp()}",
            instrument=tick_data.instrument,
            order_type="market",
            direction=direction,
            units=self.base_units,
            price=tick_data.mid,
        )

        self.log_strategy_event(
            "macd_entry",
            f"MACD entry: {signal} crossover detected",
            {
                "instrument": tick_data.instrument,
                "signal": signal,
                "direction": direction,
                "units": str(self.base_units),
                "price": str(tick_data.mid),
                "macd": str(macd),
                "signal_line": str(signal_line),
                "histogram": str(histogram),
                "momentum": momentum,
            },
        )

        return order

    def _create_close_order(  # pylint: disable=too-many-positional-arguments
        self,
        position: Position,
        tick_data: TickData,
        reason: str,
        macd: Decimal,
        signal_line: Decimal,
        histogram: Decimal,
    ) -> Order | None:
        """
        Create order to close a position.

        Args:
            position: Position to close
            tick_data: Current tick data
            reason: Reason for closing
            macd: Current MACD line value
            signal_line: Current signal line value
            histogram: Current histogram value

        Returns:
            Close order or None
        """
        # Reverse direction for closing
        close_direction = "short" if position.direction == "long" else "long"

        order = Order(
            account=self.account,
            strategy=self.strategy,
            order_id=f"macd_close_{position.position_id}_{tick_data.timestamp.timestamp()}",
            instrument=position.instrument,
            order_type="market",
            direction=close_direction,
            units=position.units,
            price=tick_data.mid,
        )

        self.log_strategy_event(
            "macd_exit",
            f"MACD exit: {reason}",
            {
                "position_id": position.position_id,
                "instrument": position.instrument,
                "direction": position.direction,
                "entry_price": str(position.entry_price),
                "exit_price": str(tick_data.mid),
                "units": str(position.units),
                "macd": str(macd),
                "signal_line": str(signal_line),
                "histogram": str(histogram),
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
        # No special handling needed for MACD strategy

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
        signal_period = config.get("signal_period", 9)

        if not isinstance(fast_period, int) or fast_period < 1:
            raise ValueError("fast_period must be a positive integer")

        if not isinstance(slow_period, int) or slow_period < 1:
            raise ValueError("slow_period must be a positive integer")

        if not isinstance(signal_period, int) or signal_period < 1:
            raise ValueError("signal_period must be a positive integer")

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


# Configuration schema for MACD Strategy
MACD_STRATEGY_CONFIG_SCHEMA = {
    "type": "object",
    "title": "MACD Strategy Configuration",
    "description": "Configuration for MACD Strategy with signal line crossovers",
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
        "signal_period": {
            "type": "integer",
            "title": "Signal Line Period",
            "description": "Period for signal line EMA",
            "default": 9,
            "minimum": 1,
        },
        "base_units": {
            "type": "number",
            "title": "Base Units",
            "description": "Base position size in units",
            "default": 1000,
            "minimum": 1,
        },
        "use_histogram_confirmation": {
            "type": "boolean",
            "title": "Use Histogram Confirmation",
            "description": "Require histogram direction to confirm crossover signals",
            "default": True,
        },
    },
    "required": [],
}

# Register the strategy
register_strategy("macd", MACD_STRATEGY_CONFIG_SCHEMA, display_name="MACD Strategy")(MACDStrategy)
