"""
Stochastic Oscillator Strategy implementation.

This module implements a Stochastic Oscillator Strategy that:
- Calculates Stochastic Oscillator using 14, 3, 3 periods (default)
- Enters long when %K < 20 (oversold)
- Exits when %K > 80 (overbought)
- Detects %K and %D crossover signals

Requirements: 5.1, 5.3
"""

from collections import deque
from decimal import Decimal
from typing import Any

from .base_strategy import BaseStrategy
from .models import Order, Position
from .strategy_registry import register_strategy
from .tick_data_models import TickData


class StochasticCalculator:
    """
    Calculate Stochastic Oscillator (%K and %D).

    %K = 100 * (Close - Lowest Low) / (Highest High - Lowest Low)
    %D = SMA of %K over smoothing period

    Requirements: 5.1, 5.3
    """

    def __init__(self, k_period: int = 14, k_smoothing: int = 3, d_smoothing: int = 3) -> None:
        """
        Initialize the Stochastic calculator.

        Args:
            k_period: Number of periods for %K calculation (default: 14)
            k_smoothing: Smoothing period for %K (default: 3)
            d_smoothing: Smoothing period for %D (default: 3)
        """
        self.k_period = k_period
        self.k_smoothing = k_smoothing
        self.d_smoothing = d_smoothing

        self.prices: deque[Decimal] = deque(maxlen=k_period)
        self.raw_k_values: deque[Decimal] = deque(maxlen=k_smoothing)
        self.k_values: deque[Decimal] = deque(maxlen=d_smoothing)

        self.current_k: Decimal | None = None
        self.current_d: Decimal | None = None

    def add_price(self, price: Decimal) -> None:
        """
        Add a new price and update Stochastic values.

        Args:
            price: New price to add
        """
        self.prices.append(price)

        # Need at least k_period prices to calculate
        if len(self.prices) < self.k_period:
            return

        # Calculate raw %K
        prices_list = list(self.prices)
        lowest_low = min(prices_list)
        highest_high = max(prices_list)
        current_close = prices_list[-1]

        # Avoid division by zero
        if highest_high == lowest_low:
            raw_k = Decimal("50")  # Neutral value
        else:
            raw_k = Decimal("100") * (current_close - lowest_low) / (highest_high - lowest_low)

        self.raw_k_values.append(raw_k)

        # Calculate smoothed %K (SMA of raw %K)
        if len(self.raw_k_values) >= self.k_smoothing:
            raw_k_list = list(self.raw_k_values)
            self.current_k = sum(raw_k_list[-self.k_smoothing :]) / Decimal(self.k_smoothing)
            self.k_values.append(self.current_k)

            # Calculate %D (SMA of %K)
            if len(self.k_values) >= self.d_smoothing:
                k_list = list(self.k_values)
                self.current_d = sum(k_list[-self.d_smoothing :]) / Decimal(self.d_smoothing)

    def get_k(self) -> Decimal | None:
        """
        Get the current %K value.

        Returns:
            Current %K (0-100) or None if not enough data
        """
        return self.current_k

    def get_d(self) -> Decimal | None:
        """
        Get the current %D value.

        Returns:
            Current %D (0-100) or None if not enough data
        """
        return self.current_d

    def is_ready(self) -> bool:
        """
        Check if Stochastic has enough data to be calculated.

        Returns:
            True if both %K and %D are ready
        """
        return self.current_k is not None and self.current_d is not None


class CrossoverDetector:
    """
    Detect crossovers between %K and %D lines.

    Requirements: 5.1, 5.3
    """

    def __init__(self) -> None:
        """Initialize crossover detector."""
        self.prev_k: Decimal | None = None
        self.prev_d: Decimal | None = None

    def update(self, k: Decimal, d: Decimal) -> None:
        """
        Update with new %K and %D values.

        Args:
            k: Current %K value
            d: Current %D value
        """
        self.prev_k = k
        self.prev_d = d

    def detect_bullish_crossover(self, k: Decimal, d: Decimal) -> bool:
        """
        Detect bullish crossover (%K crosses above %D).

        Args:
            k: Current %K value
            d: Current %D value

        Returns:
            True if bullish crossover detected
        """
        if self.prev_k is None or self.prev_d is None:
            return False

        # %K was below %D and is now above
        return self.prev_k <= self.prev_d and k > d

    def detect_bearish_crossover(self, k: Decimal, d: Decimal) -> bool:
        """
        Detect bearish crossover (%K crosses below %D).

        Args:
            k: Current %K value
            d: Current %D value

        Returns:
            True if bearish crossover detected
        """
        if self.prev_k is None or self.prev_d is None:
            return False

        # %K was above %D and is now below
        return self.prev_k >= self.prev_d and k < d


class StochasticStrategy(BaseStrategy):
    """
    Stochastic Oscillator Strategy with oversold/overbought and crossover signals.

    This strategy:
    - Calculates Stochastic Oscillator using 14, 3, 3 periods (default)
    - Enters long when %K < 20 (oversold)
    - Exits when %K > 80 (overbought)
    - Uses %K and %D crossover signals for additional confirmation

    Requirements: 5.1, 5.3
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the Stochastic Strategy."""
        super().__init__(*args, **kwargs)

        # Configuration
        self.k_period = int(self.get_config_value("k_period", 14))
        self.k_smoothing = int(self.get_config_value("k_smoothing", 3))
        self.d_smoothing = int(self.get_config_value("d_smoothing", 3))
        self.oversold_threshold = Decimal(str(self.get_config_value("oversold_threshold", 20)))
        self.overbought_threshold = Decimal(str(self.get_config_value("overbought_threshold", 80)))
        self.base_units = Decimal(str(self.get_config_value("base_units", 1000)))
        self.use_crossover = bool(self.get_config_value("use_crossover", True))

        # Components
        self.stochastic_calculators: dict[str, StochasticCalculator] = {}
        self.crossover_detectors: dict[str, CrossoverDetector] = {}

        # Initialize component for the instrument
        self.stochastic_calculators[self.instrument] = StochasticCalculator(
            self.k_period, self.k_smoothing, self.d_smoothing
        )

        if self.use_crossover:
            self.crossover_detectors[self.instrument] = CrossoverDetector()

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

        calculator = self.stochastic_calculators.get(tick_data.instrument)
        if not calculator:
            return orders

        # Update Stochastic with new price
        calculator.add_price(tick_data.mid)

        if not calculator.is_ready():
            return orders

        k = calculator.get_k()
        d = calculator.get_d()
        if k is None or d is None:
            return orders

        # Get open positions for this instrument
        open_positions = self.get_open_positions(tick_data.instrument)

        # Check for crossover signals if enabled
        if self.use_crossover:
            crossover_orders = self._process_crossover(open_positions, tick_data, k, d)
            orders.extend(crossover_orders)

        # Check for exit signals (overbought)
        if k >= self.overbought_threshold:
            exit_orders = self._process_overbought(open_positions, tick_data, k, d)
            orders.extend(exit_orders)

        # Check for entry signals (oversold)
        elif k <= self.oversold_threshold:
            entry_orders = self._process_oversold(open_positions, tick_data, k, d)
            orders.extend(entry_orders)

        # Update crossover detector
        if self.use_crossover:
            crossover_detector = self.crossover_detectors.get(tick_data.instrument)
            if crossover_detector:
                crossover_detector.update(k, d)

        return orders

    def _process_oversold(
        self,
        positions: list[Position],
        tick_data: TickData,
        k: Decimal,
        d: Decimal,
    ) -> list[Order]:
        """
        Process oversold condition (%K < 20).

        Args:
            positions: List of open positions
            tick_data: Current tick data
            k: Current %K value
            d: Current %D value

        Returns:
            List of orders to execute
        """
        orders: list[Order] = []

        # Only enter if we don't have a long position
        if not any(p.direction == "long" for p in positions):
            entry_order = self._create_entry_order(tick_data, "long", k, d, "oversold")
            if entry_order:
                orders.append(entry_order)

        return orders

    def _process_overbought(
        self,
        positions: list[Position],
        tick_data: TickData,
        k: Decimal,
        d: Decimal,
    ) -> list[Order]:
        """
        Process overbought condition (%K > 80).

        Args:
            positions: List of open positions
            tick_data: Current tick data
            k: Current %K value
            d: Current %D value

        Returns:
            List of orders to execute
        """
        orders: list[Order] = []

        # Close any long positions
        for position in positions:
            if position.direction == "long":
                close_order = self._create_close_order(position, tick_data, "overbought", k, d)
                if close_order:
                    orders.append(close_order)

        return orders

    def _process_crossover(
        self,
        positions: list[Position],
        tick_data: TickData,
        k: Decimal,
        d: Decimal,
    ) -> list[Order]:
        """
        Process %K and %D crossover signals.

        Args:
            positions: List of open positions
            tick_data: Current tick data
            k: Current %K value
            d: Current %D value

        Returns:
            List of orders to execute
        """
        orders: list[Order] = []

        crossover_detector = self.crossover_detectors.get(tick_data.instrument)
        if not crossover_detector:
            return orders

        # Check for bullish crossover (entry signal)
        if crossover_detector.detect_bullish_crossover(k, d):
            # Only enter if we don't have a long position
            if not any(p.direction == "long" for p in positions):
                entry_order = self._create_entry_order(tick_data, "long", k, d, "bullish_crossover")
                if entry_order:
                    orders.append(entry_order)

        # Check for bearish crossover (exit signal)
        elif crossover_detector.detect_bearish_crossover(k, d):
            # Close any long positions
            for position in positions:
                if position.direction == "long":
                    close_order = self._create_close_order(
                        position, tick_data, "bearish_crossover", k, d
                    )
                    if close_order:
                        orders.append(close_order)

        return orders

    def _create_entry_order(  # pylint: disable=too-many-positional-arguments
        self,
        tick_data: TickData,
        direction: str,
        k: Decimal,
        d: Decimal,
        reason: str,
    ) -> Order | None:
        """
        Create entry order based on Stochastic signal.

        Args:
            tick_data: Current tick data
            direction: Position direction ('long' or 'short')
            k: Current %K value
            d: Current %D value
            reason: Reason for entry

        Returns:
            Order instance or None
        """
        order = Order(
            account=self.account,
            strategy=self.strategy,
            order_id=(f"stochastic_{direction}_{tick_data.timestamp.timestamp()}"),
            instrument=tick_data.instrument,
            order_type="market",
            direction=direction,
            units=self.base_units,
            price=tick_data.mid,
        )

        self.log_strategy_event(
            "stochastic_entry",
            f"Stochastic entry: {reason}",
            {
                "instrument": tick_data.instrument,
                "direction": direction,
                "units": str(self.base_units),
                "price": str(tick_data.mid),
                "k": str(k),
                "d": str(d),
                "reason": reason,
            },
        )

        return order

    def _create_close_order(  # pylint: disable=too-many-positional-arguments
        self,
        position: Position,
        tick_data: TickData,
        reason: str,
        k: Decimal,
        d: Decimal,
    ) -> Order | None:
        """
        Create order to close a position.

        Args:
            position: Position to close
            tick_data: Current tick data
            reason: Reason for closing
            k: Current %K value
            d: Current %D value

        Returns:
            Close order or None
        """
        # Reverse direction for closing
        close_direction = "short" if position.direction == "long" else "long"

        order = Order(
            account=self.account,
            strategy=self.strategy,
            order_id=(
                f"stochastic_close_{position.position_id}_" f"{tick_data.timestamp.timestamp()}"
            ),
            instrument=position.instrument,
            order_type="market",
            direction=close_direction,
            units=position.units,
            price=tick_data.mid,
        )

        self.log_strategy_event(
            "stochastic_exit",
            f"Stochastic exit: {reason}",
            {
                "position_id": position.position_id,
                "instrument": position.instrument,
                "direction": position.direction,
                "entry_price": str(position.entry_price),
                "exit_price": str(tick_data.mid),
                "units": str(position.units),
                "k": str(k),
                "d": str(d),
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
        # No special handling needed for Stochastic strategy

    def validate_config(self, config: dict[str, Any]) -> bool:  # noqa: C901
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
        # Validate k_period
        k_period = config.get("k_period", 14)
        if not isinstance(k_period, int) or k_period < 2:
            raise ValueError("k_period must be an integer >= 2")

        # Validate k_smoothing
        k_smoothing = config.get("k_smoothing", 3)
        if not isinstance(k_smoothing, int) or k_smoothing < 1:
            raise ValueError("k_smoothing must be an integer >= 1")

        # Validate d_smoothing
        d_smoothing = config.get("d_smoothing", 3)
        if not isinstance(d_smoothing, int) or d_smoothing < 1:
            raise ValueError("d_smoothing must be an integer >= 1")

        # Validate oversold threshold
        oversold = config.get("oversold_threshold", 20)
        try:
            oversold_decimal = Decimal(str(oversold))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid oversold_threshold: {oversold}") from exc

        if oversold_decimal < Decimal("0") or oversold_decimal > Decimal("100"):
            raise ValueError("oversold_threshold must be between 0 and 100")

        # Validate overbought threshold
        overbought = config.get("overbought_threshold", 80)
        try:
            overbought_decimal = Decimal(str(overbought))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid overbought_threshold: {overbought}") from exc

        if overbought_decimal < Decimal("0") or overbought_decimal > Decimal("100"):
            raise ValueError("overbought_threshold must be between 0 and 100")

        # Validate that oversold < overbought
        if oversold_decimal >= overbought_decimal:
            raise ValueError("oversold_threshold must be less than overbought_threshold")

        # Validate base units
        base_units = config.get("base_units", 1000)
        try:
            base_units_decimal = Decimal(str(base_units))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid base_units: {base_units}") from exc

        if base_units_decimal <= Decimal("0"):
            raise ValueError("base_units must be positive")

        return True


# Configuration schema for Stochastic Strategy
STOCHASTIC_STRATEGY_CONFIG_SCHEMA = {
    "type": "object",
    "title": "Stochastic Oscillator Strategy Configuration",
    "description": "Configuration for Stochastic Oscillator Strategy",
    "properties": {
        "k_period": {
            "type": "integer",
            "title": "%K Period",
            "description": "Number of periods for %K calculation",
            "default": 14,
            "minimum": 2,
        },
        "k_smoothing": {
            "type": "integer",
            "title": "%K Smoothing",
            "description": "Smoothing period for %K",
            "default": 3,
            "minimum": 1,
        },
        "d_smoothing": {
            "type": "integer",
            "title": "%D Smoothing",
            "description": "Smoothing period for %D (signal line)",
            "default": 3,
            "minimum": 1,
        },
        "oversold_threshold": {
            "type": "number",
            "title": "Oversold Threshold",
            "description": "%K level below which market is considered oversold",
            "default": 20,
            "minimum": 0,
            "maximum": 100,
        },
        "overbought_threshold": {
            "type": "number",
            "title": "Overbought Threshold",
            "description": "%K level above which market is considered overbought",
            "default": 80,
            "minimum": 0,
            "maximum": 100,
        },
        "base_units": {
            "type": "number",
            "title": "Base Units",
            "description": "Base position size in units",
            "default": 1000,
            "minimum": 1,
        },
        "use_crossover": {
            "type": "boolean",
            "title": "Use Crossover Signals",
            "description": "Enable %K and %D crossover detection",
            "default": True,
        },
    },
    "required": [],
}

# Register the strategy
register_strategy(
    "stochastic", STOCHASTIC_STRATEGY_CONFIG_SCHEMA, display_name="Stochastic Strategy"
)(StochasticStrategy)
