"""
ADX (Average Directional Index) Trend Strength Strategy implementation.

This module implements an ADX Strategy that:
- Calculates ADX using 14-period (default)
- Detects trend strength (ADX > 25 = strong trend)
- Uses directional movement (+DI, -DI) for entry signals
- Exits when ADX falls below 20 (weak trend)

Requirements: 5.1, 5.3
"""

from collections import deque
from decimal import Decimal
from typing import Any

from .base_strategy import BaseStrategy
from .models import Order, Position
from .strategy_registry import register_strategy
from .tick_data_models import TickData


class ADXCalculator:
    """
    Calculate Average Directional Index (ADX) and Directional Indicators (+DI, -DI).

    ADX measures trend strength on a scale of 0-100:
    - ADX < 20: Weak or no trend
    - ADX 20-25: Emerging trend
    - ADX > 25: Strong trend
    - ADX > 50: Very strong trend

    +DI and -DI indicate trend direction:
    - +DI > -DI: Uptrend
    - -DI > +DI: Downtrend

    Requirements: 5.1, 5.3
    """

    def __init__(self, period: int = 14) -> None:
        """
        Initialize the ADX calculator.

        Args:
            period: Number of periods for ADX calculation (default: 14)
        """
        self.period = period

        # Price history
        self.highs: deque[Decimal] = deque(maxlen=period + 1)
        self.lows: deque[Decimal] = deque(maxlen=period + 1)
        self.closes: deque[Decimal] = deque(maxlen=period + 1)

        # True Range components
        self.tr_values: deque[Decimal] = deque(maxlen=period)

        # Directional Movement
        self.plus_dm_values: deque[Decimal] = deque(maxlen=period)
        self.minus_dm_values: deque[Decimal] = deque(maxlen=period)

        # Smoothed values
        self.smoothed_tr: Decimal | None = None
        self.smoothed_plus_dm: Decimal | None = None
        self.smoothed_minus_dm: Decimal | None = None

        # DX values for ADX calculation
        self.dx_values: deque[Decimal] = deque(maxlen=period)

        # Current values
        self.current_adx: Decimal | None = None
        self.current_plus_di: Decimal | None = None
        self.current_minus_di: Decimal | None = None

    def add_price(self, high: Decimal, low: Decimal, close: Decimal) -> None:
        """
        Add a new price bar and update ADX values.

        Args:
            high: High price of the period
            low: Low price of the period
            close: Close price of the period
        """
        self.highs.append(high)
        self.lows.append(low)
        self.closes.append(close)

        # Need at least 2 prices to calculate
        if len(self.closes) < 2:
            return

        # Calculate True Range (TR)
        tr = self._calculate_true_range()
        self.tr_values.append(tr)

        # Calculate Directional Movement (+DM, -DM)
        plus_dm, minus_dm = self._calculate_directional_movement()
        self.plus_dm_values.append(plus_dm)
        self.minus_dm_values.append(minus_dm)

        # Need at least period values to start smoothing
        if len(self.tr_values) < self.period:
            return

        # Initialize or update smoothed values
        if self.smoothed_tr is None:
            # First smoothed value is the sum
            self.smoothed_tr = sum(self.tr_values, Decimal("0"))
            self.smoothed_plus_dm = sum(self.plus_dm_values, Decimal("0"))
            self.smoothed_minus_dm = sum(self.minus_dm_values, Decimal("0"))
        else:
            # Wilder's smoothing: (previous * (period - 1) + current) / period
            # At this point, smoothed values are guaranteed to be non-None (from if block)
            assert self.smoothed_tr is not None
            assert self.smoothed_plus_dm is not None
            assert self.smoothed_minus_dm is not None

            self.smoothed_tr = (self.smoothed_tr * Decimal(self.period - 1) + tr) / Decimal(
                self.period
            )
            self.smoothed_plus_dm = (
                self.smoothed_plus_dm * Decimal(self.period - 1) + plus_dm
            ) / Decimal(self.period)
            self.smoothed_minus_dm = (
                self.smoothed_minus_dm * Decimal(self.period - 1) + minus_dm
            ) / Decimal(self.period)

        # Calculate +DI and -DI
        # At this point, smoothed values are guaranteed to be non-None
        assert self.smoothed_tr is not None
        assert self.smoothed_plus_dm is not None
        assert self.smoothed_minus_dm is not None

        if self.smoothed_tr > Decimal("0"):
            self.current_plus_di = Decimal("100") * self.smoothed_plus_dm / self.smoothed_tr
            self.current_minus_di = Decimal("100") * self.smoothed_minus_dm / self.smoothed_tr

            # Calculate DX (Directional Index)
            di_sum = self.current_plus_di + self.current_minus_di
            if di_sum > Decimal("0"):
                di_diff = abs(self.current_plus_di - self.current_minus_di)
                dx = Decimal("100") * di_diff / di_sum
                self.dx_values.append(dx)

                # Calculate ADX (smoothed DX)
                if len(self.dx_values) >= self.period:
                    if self.current_adx is None:
                        # First ADX is the average of DX values
                        self.current_adx = sum(self.dx_values) / Decimal(self.period)
                    else:
                        # Wilder's smoothing for ADX
                        latest_dx = self.dx_values[-1]
                        self.current_adx = (
                            self.current_adx * Decimal(self.period - 1) + latest_dx
                        ) / Decimal(self.period)

    def _calculate_true_range(self) -> Decimal:
        """
        Calculate True Range (TR).

        TR = max(high - low, abs(high - prev_close), abs(low - prev_close))

        Returns:
            True Range value
        """
        current_high = self.highs[-1]
        current_low = self.lows[-1]
        prev_close = self.closes[-2]

        tr1 = current_high - current_low
        tr2 = abs(current_high - prev_close)
        tr3 = abs(current_low - prev_close)

        return max(tr1, tr2, tr3)

    def _calculate_directional_movement(self) -> tuple[Decimal, Decimal]:
        """
        Calculate Directional Movement (+DM, -DM).

        +DM = current_high - prev_high (if positive and > down_move)
        -DM = prev_low - current_low (if positive and > up_move)

        Returns:
            Tuple of (+DM, -DM)
        """
        current_high = self.highs[-1]
        current_low = self.lows[-1]
        prev_high = self.highs[-2]
        prev_low = self.lows[-2]

        up_move = current_high - prev_high
        down_move = prev_low - current_low

        plus_dm = Decimal("0")
        minus_dm = Decimal("0")

        if up_move > down_move and up_move > Decimal("0"):
            plus_dm = up_move

        if down_move > up_move and down_move > Decimal("0"):
            minus_dm = down_move

        return plus_dm, minus_dm

    def get_adx(self) -> Decimal | None:
        """
        Get the current ADX value.

        Returns:
            Current ADX (0-100) or None if not enough data
        """
        return self.current_adx

    def get_plus_di(self) -> Decimal | None:
        """
        Get the current +DI value.

        Returns:
            Current +DI (0-100) or None if not enough data
        """
        return self.current_plus_di

    def get_minus_di(self) -> Decimal | None:
        """
        Get the current -DI value.

        Returns:
            Current -DI (0-100) or None if not enough data
        """
        return self.current_minus_di

    def is_ready(self) -> bool:
        """
        Check if ADX has enough data to be calculated.

        Returns:
            True if ADX, +DI, and -DI are ready
        """
        return (
            self.current_adx is not None
            and self.current_plus_di is not None
            and self.current_minus_di is not None
        )


class ADXStrategy(BaseStrategy):
    """
    ADX (Average Directional Index) Trend Strength Strategy.

    This strategy:
    - Calculates ADX using 14-period (default)
    - Enters long when ADX > 25 (strong trend) and +DI > -DI
    - Enters short when ADX > 25 (strong trend) and -DI > +DI
    - Exits when ADX falls below 20 (weak trend)

    Requirements: 5.1, 5.3
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the ADX Strategy."""
        super().__init__(*args, **kwargs)

        # Configuration
        self.period = int(self.get_config_value("period", 14))
        self.strong_trend_threshold = Decimal(
            str(self.get_config_value("strong_trend_threshold", 25))
        )
        self.weak_trend_threshold = Decimal(str(self.get_config_value("weak_trend_threshold", 20)))
        self.base_units = Decimal(str(self.get_config_value("base_units", 1000)))
        self.allow_short = bool(self.get_config_value("allow_short", False))

        # ADX calculators for each instrument
        self.adx_calculators: dict[str, ADXCalculator] = {}

        # Initialize calculators for each instrument
        for instrument in self.instruments:
            self.adx_calculators[instrument] = ADXCalculator(self.period)

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

        calculator = self.adx_calculators.get(tick_data.instrument)
        if not calculator:
            return orders

        # Update ADX with new price (using mid as close, bid as low, ask as high)
        # In real implementation, we'd use actual OHLC data
        calculator.add_price(
            high=tick_data.ask,
            low=tick_data.bid,
            close=tick_data.mid,
        )

        if not calculator.is_ready():
            return orders

        adx = calculator.get_adx()
        plus_di = calculator.get_plus_di()
        minus_di = calculator.get_minus_di()

        if adx is None or plus_di is None or minus_di is None:
            return orders

        # Get open positions for this instrument
        open_positions = self.get_open_positions(tick_data.instrument)

        # Check for exit signals (weak trend)
        if adx < self.weak_trend_threshold:
            exit_orders = self._process_weak_trend(open_positions, tick_data, adx)
            orders.extend(exit_orders)
            return orders

        # Check for entry signals (strong trend)
        if adx > self.strong_trend_threshold:
            entry_orders = self._process_strong_trend(
                open_positions, tick_data, adx=adx, plus_di=plus_di, minus_di=minus_di
            )
            orders.extend(entry_orders)

        return orders

    def _process_strong_trend(
        self,
        positions: list[Position],
        tick_data: TickData,
        *,
        adx: Decimal,
        plus_di: Decimal,
        minus_di: Decimal,
    ) -> list[Order]:
        """
        Process strong trend condition (ADX > 25).

        Args:
            positions: List of open positions
            tick_data: Current tick data
            adx: Current ADX value
            plus_di: Current +DI value
            minus_di: Current -DI value

        Returns:
            List of orders to execute
        """
        orders: list[Order] = []

        # Determine trend direction
        is_uptrend = plus_di > minus_di
        is_downtrend = minus_di > plus_di

        # Entry logic for uptrend
        if is_uptrend and not any(p.direction == "long" for p in positions):
            # Only enter if we don't have a long position
            entry_order = self._create_entry_order(
                tick_data,
                "long",
                adx=adx,
                plus_di=plus_di,
                minus_di=minus_di,
                reason="strong_uptrend",
            )
            if entry_order:
                orders.append(entry_order)

        # Entry logic for downtrend (if allowed)
        elif (
            is_downtrend and self.allow_short and not any(p.direction == "short" for p in positions)
        ):
            # Only enter if we don't have a short position
            entry_order = self._create_entry_order(
                tick_data,
                "short",
                adx=adx,
                plus_di=plus_di,
                minus_di=minus_di,
                reason="strong_downtrend",
            )
            if entry_order:
                orders.append(entry_order)

        return orders

    def _process_weak_trend(
        self,
        positions: list[Position],
        tick_data: TickData,
        adx: Decimal,
    ) -> list[Order]:
        """
        Process weak trend condition (ADX < 20).

        Args:
            positions: List of open positions
            tick_data: Current tick data
            adx: Current ADX value

        Returns:
            List of orders to execute
        """
        orders: list[Order] = []

        # Close all positions when trend is weak
        for position in positions:
            close_order = self._create_close_order(position, tick_data, "weak_trend", adx)
            if close_order:
                orders.append(close_order)

        return orders

    def _create_entry_order(
        self,
        tick_data: TickData,
        direction: str,
        *,
        adx: Decimal,
        plus_di: Decimal,
        minus_di: Decimal,
        reason: str,
    ) -> Order | None:
        """
        Create entry order based on ADX signal.

        Args:
            tick_data: Current tick data
            direction: Position direction ('long' or 'short')
            adx: Current ADX value
            plus_di: Current +DI value
            minus_di: Current -DI value
            reason: Reason for entry

        Returns:
            Order instance or None
        """
        order = Order(
            account=self.account,
            strategy=self.strategy,
            order_id=f"adx_{direction}_{tick_data.timestamp.timestamp()}",
            instrument=tick_data.instrument,
            order_type="market",
            direction=direction,
            units=self.base_units,
            price=tick_data.mid,
        )

        self.log_strategy_event(
            "adx_entry",
            f"ADX entry: {reason}",
            {
                "instrument": tick_data.instrument,
                "direction": direction,
                "units": str(self.base_units),
                "price": str(tick_data.mid),
                "adx": str(adx),
                "plus_di": str(plus_di),
                "minus_di": str(minus_di),
                "reason": reason,
            },
        )

        return order

    def _create_close_order(
        self,
        position: Position,
        tick_data: TickData,
        reason: str,
        adx: Decimal,
    ) -> Order | None:
        """
        Create order to close a position.

        Args:
            position: Position to close
            tick_data: Current tick data
            reason: Reason for closing
            adx: Current ADX value

        Returns:
            Close order or None
        """
        # Reverse direction for closing
        close_direction = "short" if position.direction == "long" else "long"

        order = Order(
            account=self.account,
            strategy=self.strategy,
            order_id=f"adx_close_{position.position_id}_{tick_data.timestamp.timestamp()}",
            instrument=position.instrument,
            order_type="market",
            direction=close_direction,
            units=position.units,
            price=tick_data.mid,
        )

        self.log_strategy_event(
            "adx_exit",
            f"ADX exit: {reason}",
            {
                "position_id": position.position_id,
                "instrument": position.instrument,
                "direction": position.direction,
                "entry_price": str(position.entry_price),
                "exit_price": str(tick_data.mid),
                "units": str(position.units),
                "adx": str(adx),
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
        # No special handling needed for ADX strategy

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
        # Validate period
        period = config.get("period", 14)
        if not isinstance(period, int) or period < 2:
            raise ValueError("period must be an integer >= 2")

        # Validate strong trend threshold
        strong_threshold = config.get("strong_trend_threshold", 25)
        try:
            strong_decimal = Decimal(str(strong_threshold))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid strong_trend_threshold: {strong_threshold}") from exc

        if strong_decimal < Decimal("0") or strong_decimal > Decimal("100"):
            raise ValueError("strong_trend_threshold must be between 0 and 100")

        # Validate weak trend threshold
        weak_threshold = config.get("weak_trend_threshold", 20)
        try:
            weak_decimal = Decimal(str(weak_threshold))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid weak_trend_threshold: {weak_threshold}") from exc

        if weak_decimal < Decimal("0") or weak_decimal > Decimal("100"):
            raise ValueError("weak_trend_threshold must be between 0 and 100")

        # Validate that weak < strong
        if weak_decimal >= strong_decimal:
            raise ValueError("weak_trend_threshold must be less than strong_trend_threshold")

        # Validate base units
        base_units = config.get("base_units", 1000)
        try:
            base_units_decimal = Decimal(str(base_units))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid base_units: {base_units}") from exc

        if base_units_decimal <= Decimal("0"):
            raise ValueError("base_units must be positive")

        return True


# Configuration schema for ADX Strategy
ADX_STRATEGY_CONFIG_SCHEMA = {
    "type": "object",
    "title": "ADX Trend Strength Strategy Configuration",
    "description": "Configuration for ADX (Average Directional Index) Strategy",
    "properties": {
        "period": {
            "type": "integer",
            "title": "ADX Period",
            "description": "Number of periods for ADX calculation",
            "default": 14,
            "minimum": 2,
        },
        "strong_trend_threshold": {
            "type": "number",
            "title": "Strong Trend Threshold",
            "description": "ADX level above which trend is considered strong (entry signal)",
            "default": 25,
            "minimum": 0,
            "maximum": 100,
        },
        "weak_trend_threshold": {
            "type": "number",
            "title": "Weak Trend Threshold",
            "description": "ADX level below which trend is considered weak (exit signal)",
            "default": 20,
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
        "allow_short": {
            "type": "boolean",
            "title": "Allow Short Positions",
            "description": "Enable short positions on downtrends",
            "default": False,
        },
    },
    "required": [],
}

# Register the strategy
register_strategy("adx", ADX_STRATEGY_CONFIG_SCHEMA)(ADXStrategy)
