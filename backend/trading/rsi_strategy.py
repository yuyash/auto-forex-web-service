"""
RSI Strategy implementation with oversold/overbought signals.

This module implements an RSI (Relative Strength Index) Strategy that:
- Calculates RSI using 14-period default
- Enters long when RSI < 30 (oversold)
- Exits when RSI > 70 (overbought)
- Optionally detects bullish/bearish divergence

Requirements: 5.1, 5.3
"""

from collections import deque
from decimal import Decimal
from typing import Any

from .base_strategy import BaseStrategy
from .models import Order, Position
from .strategy_registry import register_strategy
from .tick_data_models import TickData


class RSICalculator:
    """
    Calculate Relative Strength Index (RSI).

    RSI = 100 - (100 / (1 + RS))
    where RS = Average Gain / Average Loss

    Requirements: 5.1, 5.3
    """

    def __init__(self, period: int = 14) -> None:
        """
        Initialize the RSI calculator.

        Args:
            period: Number of periods for RSI calculation (default: 14)
        """
        self.period = period
        self.prices: deque[Decimal] = deque(maxlen=period + 1)
        self.gains: deque[Decimal] = deque(maxlen=period)
        self.losses: deque[Decimal] = deque(maxlen=period)
        self.avg_gain: Decimal | None = None
        self.avg_loss: Decimal | None = None
        self.rsi: Decimal | None = None

    def add_price(self, price: Decimal) -> None:
        """
        Add a new price and update RSI.

        Args:
            price: New price to add
        """
        self.prices.append(price)

        # Need at least 2 prices to calculate gain/loss
        if len(self.prices) < 2:
            return

        # Calculate price change
        price_change = self.prices[-1] - self.prices[-2]

        # Separate into gains and losses
        if price_change > Decimal("0"):
            self.gains.append(price_change)
            self.losses.append(Decimal("0"))
        else:
            self.gains.append(Decimal("0"))
            self.losses.append(abs(price_change))

        # Calculate RSI once we have enough data
        if len(self.gains) >= self.period:
            self._calculate_rsi()

    def _calculate_rsi(self) -> None:
        """Calculate RSI using Wilder's smoothing method."""
        gains_list = list(self.gains)
        losses_list = list(self.losses)

        if self.avg_gain is None or self.avg_loss is None:
            # Initial average: simple average of first period
            self.avg_gain = sum(gains_list[-self.period :]) / Decimal(self.period)
            self.avg_loss = sum(losses_list[-self.period :]) / Decimal(self.period)
        else:
            # Wilder's smoothing: (previous avg * (period - 1) + current) / period
            self.avg_gain = (self.avg_gain * Decimal(self.period - 1) + gains_list[-1]) / Decimal(
                self.period
            )
            self.avg_loss = (self.avg_loss * Decimal(self.period - 1) + losses_list[-1]) / Decimal(
                self.period
            )

        # Calculate RS and RSI
        if self.avg_loss == Decimal("0"):
            self.rsi = Decimal("100")
        else:
            rs = self.avg_gain / self.avg_loss
            self.rsi = Decimal("100") - (Decimal("100") / (Decimal("1") + rs))

    def get_rsi(self) -> Decimal | None:
        """
        Get the current RSI value.

        Returns:
            Current RSI (0-100) or None if not enough data
        """
        return self.rsi

    def is_ready(self) -> bool:
        """
        Check if RSI has enough data to be calculated.

        Returns:
            True if RSI is ready
        """
        return self.rsi is not None


class DivergenceDetector:
    """
    Detect bullish and bearish divergence between price and RSI.

    Requirements: 5.1, 5.3
    """

    def __init__(self, lookback_period: int = 5) -> None:
        """
        Initialize divergence detector.

        Args:
            lookback_period: Number of periods to look back for divergence
        """
        self.lookback_period = lookback_period
        self.price_history: deque[Decimal] = deque(maxlen=lookback_period)
        self.rsi_history: deque[Decimal] = deque(maxlen=lookback_period)

    def add_data(self, price: Decimal, rsi: Decimal) -> None:
        """
        Add price and RSI data point.

        Args:
            price: Current price
            rsi: Current RSI value
        """
        self.price_history.append(price)
        self.rsi_history.append(rsi)

    def detect_bullish_divergence(self) -> bool:
        """
        Detect bullish divergence (price making lower lows, RSI making higher lows).

        Returns:
            True if bullish divergence detected
        """
        if len(self.price_history) < self.lookback_period:
            return False

        prices = list(self.price_history)
        rsis = list(self.rsi_history)

        # Check if price is making lower lows
        if prices[-1] >= prices[0]:
            return False

        # Check if RSI is making higher lows
        if rsis[-1] <= rsis[0]:
            return False

        return True

    def detect_bearish_divergence(self) -> bool:
        """
        Detect bearish divergence (price making higher highs, RSI making lower highs).

        Returns:
            True if bearish divergence detected
        """
        if len(self.price_history) < self.lookback_period:
            return False

        prices = list(self.price_history)
        rsis = list(self.rsi_history)

        # Check if price is making higher highs
        if prices[-1] <= prices[0]:
            return False

        # Check if RSI is making lower highs
        if rsis[-1] >= rsis[0]:
            return False

        return True

    def is_ready(self) -> bool:
        """
        Check if detector has enough data.

        Returns:
            True if ready
        """
        return len(self.price_history) >= self.lookback_period


class RSIStrategy(BaseStrategy):
    """
    RSI Strategy with oversold/overbought signals and divergence detection.

    This strategy:
    - Calculates RSI using 14-period default
    - Enters long when RSI < 30 (oversold)
    - Exits when RSI > 70 (overbought)
    - Optionally detects bullish/bearish divergence for additional signals

    Requirements: 5.1, 5.3
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the RSI Strategy."""
        super().__init__(*args, **kwargs)

        # Configuration
        self.rsi_period = int(self.get_config_value("rsi_period", 14))
        self.oversold_threshold = Decimal(str(self.get_config_value("oversold_threshold", 30)))
        self.overbought_threshold = Decimal(str(self.get_config_value("overbought_threshold", 70)))
        self.base_units = Decimal(str(self.get_config_value("base_units", 1000)))
        self.use_divergence = bool(self.get_config_value("use_divergence", False))
        self.divergence_lookback = int(self.get_config_value("divergence_lookback", 5))

        # Components
        self.rsi_calculators: dict[str, RSICalculator] = {}
        self.divergence_detectors: dict[str, DivergenceDetector] = {}

        # Initialize components for each instrument
        for instrument in self.instruments:
            self.rsi_calculators[instrument] = RSICalculator(self.rsi_period)

            if self.use_divergence:
                self.divergence_detectors[instrument] = DivergenceDetector(self.divergence_lookback)

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

        calculator = self.rsi_calculators.get(tick_data.instrument)
        if not calculator:
            return orders

        # Update RSI with new price
        calculator.add_price(tick_data.mid)

        if not calculator.is_ready():
            return orders

        rsi = calculator.get_rsi()
        if rsi is None:
            return orders

        # Update divergence detector if enabled
        if self.use_divergence:
            divergence_detector = self.divergence_detectors.get(tick_data.instrument)
            if divergence_detector:
                divergence_detector.add_data(tick_data.mid, rsi)

        # Get open positions for this instrument
        open_positions = self.get_open_positions(tick_data.instrument)

        # Check for exit signals (overbought)
        if rsi >= self.overbought_threshold:
            exit_orders = self._process_overbought(open_positions, tick_data, rsi)
            orders.extend(exit_orders)

        # Check for entry signals (oversold)
        elif rsi <= self.oversold_threshold:
            entry_orders = self._process_oversold(open_positions, tick_data, rsi)
            orders.extend(entry_orders)

        # Check for divergence signals if enabled
        if self.use_divergence and not open_positions:
            divergence_orders = self._process_divergence(tick_data, rsi)
            orders.extend(divergence_orders)

        return orders

    def _process_oversold(
        self,
        positions: list[Position],
        tick_data: TickData,
        rsi: Decimal,
    ) -> list[Order]:
        """
        Process oversold condition (RSI < 30).

        Args:
            positions: List of open positions
            tick_data: Current tick data
            rsi: Current RSI value

        Returns:
            List of orders to execute
        """
        orders: list[Order] = []

        # Only enter if we don't have a long position
        if not any(p.direction == "long" for p in positions):
            entry_order = self._create_entry_order(tick_data, "long", rsi, "oversold")
            if entry_order:
                orders.append(entry_order)

        return orders

    def _process_overbought(
        self,
        positions: list[Position],
        tick_data: TickData,
        rsi: Decimal,
    ) -> list[Order]:
        """
        Process overbought condition (RSI > 70).

        Args:
            positions: List of open positions
            tick_data: Current tick data
            rsi: Current RSI value

        Returns:
            List of orders to execute
        """
        orders: list[Order] = []

        # Close any long positions
        for position in positions:
            if position.direction == "long":
                close_order = self._create_close_order(position, tick_data, "overbought", rsi)
                if close_order:
                    orders.append(close_order)

        return orders

    def _process_divergence(self, tick_data: TickData, rsi: Decimal) -> list[Order]:
        """
        Process divergence signals.

        Args:
            tick_data: Current tick data
            rsi: Current RSI value

        Returns:
            List of orders to execute
        """
        orders: list[Order] = []

        divergence_detector = self.divergence_detectors.get(tick_data.instrument)
        if not divergence_detector or not divergence_detector.is_ready():
            return orders

        # Check for bullish divergence
        if divergence_detector.detect_bullish_divergence():
            entry_order = self._create_entry_order(tick_data, "long", rsi, "bullish_divergence")
            if entry_order:
                orders.append(entry_order)

        # Check for bearish divergence
        elif divergence_detector.detect_bearish_divergence():
            entry_order = self._create_entry_order(tick_data, "short", rsi, "bearish_divergence")
            if entry_order:
                orders.append(entry_order)

        return orders

    def _create_entry_order(
        self,
        tick_data: TickData,
        direction: str,
        rsi: Decimal,
        reason: str,
    ) -> Order | None:
        """
        Create entry order based on RSI signal.

        Args:
            tick_data: Current tick data
            direction: Position direction ('long' or 'short')
            rsi: Current RSI value
            reason: Reason for entry ('oversold', 'bullish_divergence', etc.)

        Returns:
            Order instance or None
        """
        order = Order(
            account=self.account,
            strategy=self.strategy,
            order_id=(f"rsi_{direction}_{tick_data.timestamp.timestamp()}"),
            instrument=tick_data.instrument,
            order_type="market",
            direction=direction,
            units=self.base_units,
            price=tick_data.mid,
        )

        self.log_strategy_event(
            "rsi_entry",
            f"RSI entry: {reason}",
            {
                "instrument": tick_data.instrument,
                "direction": direction,
                "units": str(self.base_units),
                "price": str(tick_data.mid),
                "rsi": str(rsi),
                "reason": reason,
            },
        )

        return order

    def _create_close_order(
        self,
        position: Position,
        tick_data: TickData,
        reason: str,
        rsi: Decimal,
    ) -> Order | None:
        """
        Create order to close a position.

        Args:
            position: Position to close
            tick_data: Current tick data
            reason: Reason for closing
            rsi: Current RSI value

        Returns:
            Close order or None
        """
        # Reverse direction for closing
        close_direction = "short" if position.direction == "long" else "long"

        order = Order(
            account=self.account,
            strategy=self.strategy,
            order_id=(f"rsi_close_{position.position_id}_" f"{tick_data.timestamp.timestamp()}"),
            instrument=position.instrument,
            order_type="market",
            direction=close_direction,
            units=position.units,
            price=tick_data.mid,
        )

        self.log_strategy_event(
            "rsi_exit",
            f"RSI exit: {reason}",
            {
                "position_id": position.position_id,
                "instrument": position.instrument,
                "direction": position.direction,
                "entry_price": str(position.entry_price),
                "exit_price": str(tick_data.mid),
                "units": str(position.units),
                "rsi": str(rsi),
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
        # No special handling needed for RSI strategy

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
        # Validate RSI period
        rsi_period = config.get("rsi_period", 14)
        if not isinstance(rsi_period, int) or rsi_period < 2:
            raise ValueError("rsi_period must be an integer >= 2")

        # Validate oversold threshold
        oversold = config.get("oversold_threshold", 30)
        try:
            oversold_decimal = Decimal(str(oversold))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid oversold_threshold: {oversold}") from exc

        if oversold_decimal < Decimal("0") or oversold_decimal > Decimal("100"):
            raise ValueError("oversold_threshold must be between 0 and 100")

        # Validate overbought threshold
        overbought = config.get("overbought_threshold", 70)
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

        # Validate divergence lookback if divergence is enabled
        use_divergence = config.get("use_divergence", False)
        if use_divergence:
            divergence_lookback = config.get("divergence_lookback", 5)
            if not isinstance(divergence_lookback, int) or divergence_lookback < 2:
                raise ValueError("divergence_lookback must be an integer >= 2")

        return True


# Configuration schema for RSI Strategy
RSI_STRATEGY_CONFIG_SCHEMA = {
    "type": "object",
    "title": "RSI Strategy Configuration",
    "description": "Configuration for RSI Strategy with oversold/overbought signals",
    "properties": {
        "rsi_period": {
            "type": "integer",
            "title": "RSI Period",
            "description": "Number of periods for RSI calculation",
            "default": 14,
            "minimum": 2,
        },
        "oversold_threshold": {
            "type": "number",
            "title": "Oversold Threshold",
            "description": "RSI level below which market is considered oversold",
            "default": 30,
            "minimum": 0,
            "maximum": 100,
        },
        "overbought_threshold": {
            "type": "number",
            "title": "Overbought Threshold",
            "description": "RSI level above which market is considered overbought",
            "default": 70,
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
        "use_divergence": {
            "type": "boolean",
            "title": "Use Divergence Detection",
            "description": "Enable bullish/bearish divergence detection",
            "default": False,
        },
        "divergence_lookback": {
            "type": "integer",
            "title": "Divergence Lookback Period",
            "description": "Number of periods to look back for divergence",
            "default": 5,
            "minimum": 2,
        },
    },
    "required": [],
}

# Register the strategy
register_strategy("rsi", RSI_STRATEGY_CONFIG_SCHEMA)(RSIStrategy)
