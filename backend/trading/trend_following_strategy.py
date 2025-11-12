"""
Trend Following Strategy implementation with moving averages and trailing stop-loss.

This module implements a Trend Following Strategy that:
- Detects trends using EMA 20 and EMA 50
- Enters positions on trend confirmation
- Uses trailing stop-loss mechanism
- Sizes positions based on ATR

Requirements: 5.1, 5.3
"""

from collections import deque
from decimal import Decimal
from typing import Any

from .base_strategy import BaseStrategy
from .models import Order, Position
from .strategy_registry import register_strategy
from .tick_data_models import TickData


class MovingAverageCalculator:
    """
    Calculate Exponential Moving Averages (EMA).

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
                self.ema = sum(list(self.prices)[-self.period :]) / Decimal(self.period)
        else:
            # Calculate EMA: EMA = (Price - Previous EMA) * Multiplier + Previous EMA
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


class TrendDetector:
    """
    Detect trends using two EMAs (fast and slow).

    Requirements: 5.1, 5.3
    """

    def __init__(self, fast_period: int = 20, slow_period: int = 50) -> None:
        """
        Initialize the trend detector.

        Args:
            fast_period: Period for fast EMA (default: 20)
            slow_period: Period for slow EMA (default: 50)
        """
        self.fast_ema = MovingAverageCalculator(fast_period)
        self.slow_ema = MovingAverageCalculator(slow_period)
        self.previous_trend: str | None = None

    def add_price(self, price: Decimal) -> None:
        """
        Add a new price to both EMAs.

        Args:
            price: New price to add
        """
        self.fast_ema.add_price(price)
        self.slow_ema.add_price(price)

    def get_trend(self) -> str | None:
        """
        Get the current trend direction.

        Returns:
            'bullish' if fast EMA > slow EMA
            'bearish' if fast EMA < slow EMA
            None if not enough data
        """
        if not self.is_ready():
            return None

        fast = self.fast_ema.get_ema()
        slow = self.slow_ema.get_ema()

        if fast is None or slow is None:
            return None

        if fast > slow:
            return "bullish"
        if fast < slow:
            return "bearish"
        return None

    def is_trend_confirmed(self) -> bool:
        """
        Check if trend has just been confirmed (crossover occurred).

        Returns:
            True if trend just changed direction
        """
        current_trend = self.get_trend()

        if current_trend is None or self.previous_trend is None:
            self.previous_trend = current_trend
            return False

        # Check if trend changed
        trend_changed = current_trend != self.previous_trend
        self.previous_trend = current_trend

        return trend_changed

    def is_ready(self) -> bool:
        """
        Check if both EMAs are ready.

        Returns:
            True if both EMAs have enough data
        """
        return self.fast_ema.is_ready() and self.slow_ema.is_ready()


class TrailingStopLoss:
    """
    Manage trailing stop-loss for positions.

    Requirements: 5.1, 5.3
    """

    def __init__(self, atr_multiplier: Decimal | None = None) -> None:
        """
        Initialize trailing stop-loss manager.

        Args:
            atr_multiplier: Multiplier for ATR to set stop distance
        """
        self.atr_multiplier = atr_multiplier if atr_multiplier is not None else Decimal("2.0")
        self.stop_prices: dict[str, Decimal] = {}  # position_id -> stop_price

    def initialize_stop(
        self, position_id: str, entry_price: Decimal, direction: str, atr: Decimal
    ) -> Decimal:
        """
        Initialize stop-loss for a new position.

        Args:
            position_id: Position identifier
            entry_price: Entry price of the position
            direction: Position direction ('long' or 'short')
            atr: Current ATR value

        Returns:
            Initial stop-loss price
        """
        stop_distance = atr * self.atr_multiplier

        if direction == "long":
            stop_price = entry_price - stop_distance
        else:  # short
            stop_price = entry_price + stop_distance

        self.stop_prices[position_id] = stop_price
        return stop_price

    def update_stop(
        self, position_id: str, current_price: Decimal, direction: str, atr: Decimal
    ) -> Decimal:
        """
        Update trailing stop-loss based on current price.

        Args:
            position_id: Position identifier
            current_price: Current market price
            direction: Position direction ('long' or 'short')
            atr: Current ATR value

        Returns:
            Updated stop-loss price
        """
        if position_id not in self.stop_prices:
            return self.initialize_stop(position_id, current_price, direction, atr)

        current_stop = self.stop_prices[position_id]
        stop_distance = atr * self.atr_multiplier

        if direction == "long":
            # For long positions, only move stop up
            new_stop = current_price - stop_distance
            if new_stop > current_stop:
                self.stop_prices[position_id] = new_stop
                return new_stop
        else:  # short
            # For short positions, only move stop down
            new_stop = current_price + stop_distance
            if new_stop < current_stop:
                self.stop_prices[position_id] = new_stop
                return new_stop

        return current_stop

    def should_stop_out(self, position_id: str, current_price: Decimal, direction: str) -> bool:
        """
        Check if position should be stopped out.

        Args:
            position_id: Position identifier
            current_price: Current market price
            direction: Position direction ('long' or 'short')

        Returns:
            True if stop-loss is hit
        """
        if position_id not in self.stop_prices:
            return False

        stop_price = self.stop_prices[position_id]

        if direction == "long":
            return current_price <= stop_price
        # short
        return current_price >= stop_price

    def remove_stop(self, position_id: str) -> None:
        """
        Remove stop-loss for a closed position.

        Args:
            position_id: Position identifier
        """
        if position_id in self.stop_prices:
            del self.stop_prices[position_id]


class TrendFollowingStrategy(BaseStrategy):
    """
    Trend Following Strategy using moving averages and trailing stop-loss.

    This strategy:
    - Detects trends using EMA 20 and EMA 50
    - Enters long when fast EMA crosses above slow EMA (bullish)
    - Enters short when fast EMA crosses below slow EMA (bearish)
    - Uses trailing stop-loss based on ATR
    - Sizes positions based on ATR

    Requirements: 5.1, 5.3
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the Trend Following Strategy."""
        super().__init__(*args, **kwargs)

        # Configuration
        self.fast_period = int(self.get_config_value("fast_period", 20))
        self.slow_period = int(self.get_config_value("slow_period", 50))
        self.atr_multiplier = Decimal(str(self.get_config_value("atr_multiplier", 2.0)))
        self.base_units = Decimal(str(self.get_config_value("base_units", 1000)))
        self.risk_per_trade = Decimal(str(self.get_config_value("risk_per_trade", 0.02)))

        # Components
        self.trend_detectors: dict[str, TrendDetector] = {}
        self.trailing_stops = TrailingStopLoss(atr_multiplier=self.atr_multiplier)

        # Initialize trend detector for the instrument
        self.trend_detectors[self.instrument] = TrendDetector(self.fast_period, self.slow_period)

        # Load state
        self._load_state()

    def _load_state(self) -> None:
        """Load strategy state from database."""
        state = self.get_strategy_state()
        if state:
            # Load trailing stops
            stop_prices = state.get("stop_prices", {})
            for position_id, stop_price in stop_prices.items():
                self.trailing_stops.stop_prices[position_id] = Decimal(str(stop_price))

    def _save_state(self) -> None:
        """Save strategy state to database."""
        # Convert stop prices to strings for JSON serialization
        stop_prices = {
            position_id: str(stop_price)
            for position_id, stop_price in self.trailing_stops.stop_prices.items()
        }

        self.update_strategy_state({"stop_prices": stop_prices})

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
        if not self._validate_tick_prerequisites(tick_data):
            return orders

        detector = self.trend_detectors[tick_data.instrument]
        atr = self._get_atr(tick_data.instrument)

        # ATR should be available after validation, but check for type safety
        if atr is None:
            return orders

        open_positions = self.get_open_positions(tick_data.instrument)

        # Process existing positions
        stop_orders = self._process_existing_positions(open_positions, tick_data, atr)
        orders.extend(stop_orders)

        # Process trend signals
        if detector.is_trend_confirmed():
            trend_orders = self._process_trend_confirmation(
                detector, open_positions, tick_data, atr
            )
            orders.extend(trend_orders)

        # Save state
        self._save_state()

        return orders

    def _validate_tick_prerequisites(self, tick_data: TickData) -> bool:
        """
        Validate prerequisites for processing tick data.

        Args:
            tick_data: Current tick data

        Returns:
            True if all prerequisites are met
        """
        if not self.is_instrument_active(tick_data.instrument):
            return False

        detector = self.trend_detectors.get(tick_data.instrument)
        if not detector:
            return False

        detector.add_price(tick_data.mid)

        if not detector.is_ready():
            return False

        atr = self._get_atr(tick_data.instrument)
        if atr is None or atr == Decimal("0"):
            return False

        return True

    def _process_existing_positions(
        self, positions: list[Position], tick_data: TickData, atr: Decimal
    ) -> list[Order]:
        """
        Process existing positions and check for stop-outs.

        Args:
            positions: List of open positions
            tick_data: Current tick data
            atr: Current ATR value

        Returns:
            List of stop-loss orders
        """
        orders: list[Order] = []

        for position in positions:
            self._update_trailing_stop(position, tick_data.mid, atr)

            if self.trailing_stops.should_stop_out(
                position.position_id, tick_data.mid, position.direction
            ):
                close_order = self._create_close_order(position, tick_data, "stop_loss")
                if close_order:
                    orders.append(close_order)

        return orders

    def _process_trend_confirmation(
        self,
        detector: TrendDetector,
        positions: list[Position],
        tick_data: TickData,
        atr: Decimal,
    ) -> list[Order]:
        """
        Process trend confirmation and generate entry/exit orders.

        Args:
            detector: Trend detector instance
            positions: List of open positions
            tick_data: Current tick data
            atr: Current ATR value

        Returns:
            List of orders for trend reversal and entry
        """
        orders: list[Order] = []
        current_trend = detector.get_trend()

        # Close opposite positions
        for position in positions:
            if self._is_opposite_direction(current_trend, position.direction):
                close_order = self._create_close_order(position, tick_data, "trend_reversal")
                if close_order:
                    orders.append(close_order)

        # Enter new position if needed
        if not self._has_position_in_trend(current_trend, positions):
            entry_order = self._create_entry_order(tick_data, current_trend, atr)
            if entry_order:
                orders.append(entry_order)

        return orders

    def _is_opposite_direction(self, trend: str | None, direction: str) -> bool:
        """
        Check if position direction is opposite to trend.

        Args:
            trend: Current trend ('bullish' or 'bearish')
            direction: Position direction ('long' or 'short')

        Returns:
            True if opposite
        """
        return (trend == "bullish" and direction == "short") or (
            trend == "bearish" and direction == "long"
        )

    def _has_position_in_trend(self, trend: str | None, positions: list[Position]) -> bool:
        """
        Check if there's already a position in the trend direction.

        Args:
            trend: Current trend ('bullish' or 'bearish')
            positions: List of open positions

        Returns:
            True if position exists in trend direction
        """
        return any(
            (trend == "bullish" and p.direction == "long")
            or (trend == "bearish" and p.direction == "short")
            for p in positions
        )

    def _get_atr(self, instrument: str) -> Decimal | None:
        """
        Get current ATR value for an instrument.

        Args:
            instrument: Currency pair

        Returns:
            ATR value or None if not available
        """
        state = self.get_strategy_state()
        atr_values = state.get("atr_values", {})
        atr_str = atr_values.get(instrument)

        if atr_str:
            return Decimal(str(atr_str))
        return None

    def _calculate_position_size(self, atr: Decimal) -> Decimal:
        """
        Calculate position size based on ATR and risk parameters.

        Args:
            atr: Current ATR value

        Returns:
            Position size in units
        """
        # Get account balance
        account_balance = self.account.balance

        # Calculate risk amount
        risk_amount = account_balance * self.risk_per_trade

        # Calculate stop distance
        stop_distance = atr * self.atr_multiplier

        # Calculate position size: risk_amount / stop_distance
        if stop_distance > Decimal("0"):
            position_size = risk_amount / stop_distance
            # Round to reasonable precision
            return position_size.quantize(Decimal("1"))

        return self.base_units

    def _create_entry_order(
        self, tick_data: TickData, trend: str | None, atr: Decimal
    ) -> Order | None:
        """
        Create entry order based on trend confirmation.

        Args:
            tick_data: Current tick data
            trend: Current trend direction
            atr: Current ATR value

        Returns:
            Order instance or None
        """
        if trend is None:
            return None

        direction = "long" if trend == "bullish" else "short"
        units = self._calculate_position_size(atr)

        # Calculate initial stop-loss
        stop_price = self.trailing_stops.initialize_stop(
            f"pending_{tick_data.timestamp.timestamp()}",
            tick_data.mid,
            direction,
            atr,
        )

        order = Order(
            account=self.account,
            strategy=self.strategy,
            order_id=f"trend_{direction}_{tick_data.timestamp.timestamp()}",
            instrument=tick_data.instrument,
            order_type="market",
            direction=direction,
            units=units,
            price=tick_data.mid,
            stop_loss=stop_price,
        )

        self.log_strategy_event(
            "trend_entry",
            f"Trend following entry: {trend} trend confirmed",
            {
                "instrument": tick_data.instrument,
                "trend": trend,
                "direction": direction,
                "units": str(units),
                "price": str(tick_data.mid),
                "stop_loss": str(stop_price),
                "atr": str(atr),
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
            reason: Reason for closing ('stop_loss' or 'trend_reversal')

        Returns:
            Close order or None
        """
        # Reverse direction for closing
        close_direction = "short" if position.direction == "long" else "long"

        order = Order(
            account=self.account,
            strategy=self.strategy,
            order_id=f"trend_close_{position.position_id}_{tick_data.timestamp.timestamp()}",
            instrument=position.instrument,
            order_type="market",
            direction=close_direction,
            units=position.units,
            price=tick_data.mid,
        )

        self.log_strategy_event(
            "trend_exit",
            f"Trend following exit: {reason}",
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

        # Remove trailing stop
        self.trailing_stops.remove_stop(position.position_id)

        return order

    def _update_trailing_stop(
        self, position: Position, current_price: Decimal, atr: Decimal
    ) -> None:
        """
        Update trailing stop-loss for a position.

        Args:
            position: Position to update
            current_price: Current market price
            atr: Current ATR value
        """
        new_stop = self.trailing_stops.update_stop(
            position.position_id, current_price, position.direction, atr
        )

        # Log if stop was updated
        old_stop = self.trailing_stops.stop_prices.get(position.position_id)
        if old_stop != new_stop:
            self.log_strategy_event(
                "trailing_stop_update",
                f"Trailing stop updated for position {position.position_id}",
                {
                    "position_id": position.position_id,
                    "old_stop": str(old_stop) if old_stop else None,
                    "new_stop": str(new_stop),
                    "current_price": str(current_price),
                },
            )

    def on_position_update(self, position: Position) -> None:
        """
        Handle position updates.

        Args:
            position: Position that was updated

        Requirements: 5.1, 5.3
        """
        # If position is closed, remove its trailing stop
        if position.closed_at is not None:
            self.trailing_stops.remove_stop(position.position_id)
            self._save_state()

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
        # Validate periods
        fast_period = config.get("fast_period", 20)
        slow_period = config.get("slow_period", 50)

        if not isinstance(fast_period, int) or fast_period < 1:
            raise ValueError("fast_period must be a positive integer")

        if not isinstance(slow_period, int) or slow_period < 1:
            raise ValueError("slow_period must be a positive integer")

        if fast_period >= slow_period:
            raise ValueError("fast_period must be less than slow_period")

        # Validate ATR multiplier
        atr_multiplier = config.get("atr_multiplier", 2.0)
        try:
            atr_mult_decimal = Decimal(str(atr_multiplier))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid atr_multiplier: {atr_multiplier}") from exc

        if atr_mult_decimal <= Decimal("0"):
            raise ValueError("atr_multiplier must be positive")

        # Validate base units
        base_units = config.get("base_units", 1000)
        try:
            base_units_decimal = Decimal(str(base_units))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid base_units: {base_units}") from exc

        if base_units_decimal <= Decimal("0"):
            raise ValueError("base_units must be positive")

        # Validate risk per trade
        risk_per_trade = config.get("risk_per_trade", 0.02)
        try:
            risk_decimal = Decimal(str(risk_per_trade))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid risk_per_trade: {risk_per_trade}") from exc

        if risk_decimal <= Decimal("0") or risk_decimal > Decimal("1"):
            raise ValueError("risk_per_trade must be between 0 and 1")

        return True


# Configuration schema for Trend Following Strategy
TREND_FOLLOWING_CONFIG_SCHEMA = {
    "type": "object",
    "title": "Trend Following Strategy Configuration",
    "description": "Configuration for Trend Following Strategy using moving averages",
    "properties": {
        "fast_period": {
            "type": "integer",
            "title": "Fast EMA Period",
            "description": "Period for fast exponential moving average",
            "default": 20,
            "minimum": 1,
        },
        "slow_period": {
            "type": "integer",
            "title": "Slow EMA Period",
            "description": "Period for slow exponential moving average",
            "default": 50,
            "minimum": 1,
        },
        "atr_multiplier": {
            "type": "number",
            "title": "ATR Multiplier",
            "description": "Multiplier for ATR to set trailing stop distance",
            "default": 2.0,
            "minimum": 0.1,
        },
        "base_units": {
            "type": "number",
            "title": "Base Units",
            "description": "Base position size in units (fallback if ATR calculation fails)",
            "default": 1000,
            "minimum": 1,
        },
        "risk_per_trade": {
            "type": "number",
            "title": "Risk Per Trade",
            "description": "Percentage of account balance to risk per trade (0.01 = 1%)",
            "default": 0.02,
            "minimum": 0.001,
            "maximum": 1.0,
        },
    },
    "required": [],
}

# Register the strategy
register_strategy(
    "trend_following", TREND_FOLLOWING_CONFIG_SCHEMA, display_name="Trend Following Strategy"
)(TrendFollowingStrategy)
