"""
Swing Trading Strategy implementation.

This module implements a Swing Trading Strategy that:
- Detects multi-day trends using moving averages
- Enters on pullbacks within the trend
- Uses wider stop-loss (50-100 pips)
- Sets profit targets based on previous swing highs/lows

Requirements: 5.1, 5.3
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from .base_strategy import BaseStrategy
from .models import Order, Position
from .strategy_registry import register_strategy
from .tick_data_models import TickData


class TrendDetector:
    """
    Detect multi-day trends using moving averages.

    Requirements: 5.1, 5.3
    """

    def __init__(self, short_period: int = 20, long_period: int = 50) -> None:
        """
        Initialize the trend detector.

        Args:
            short_period: Short-term MA period in days
            long_period: Long-term MA period in days
        """
        self.short_period = short_period
        self.long_period = long_period
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

        # Keep only necessary history (long_period + buffer)
        max_history = self.long_period * 2
        if len(self.price_history[instrument]) > max_history:
            self.price_history[instrument] = self.price_history[instrument][-max_history:]

    def calculate_ma(
        self,
        instrument: str,
        period: int,
        current_time: datetime,
    ) -> Decimal | None:
        """
        Calculate moving average for given period.

        Args:
            instrument: Currency pair
            period: MA period in days
            current_time: Current timestamp

        Returns:
            Moving average value or None if insufficient data
        """
        if instrument not in self.price_history:
            return None

        history = self.price_history[instrument]
        if not history:
            return None

        # Get daily closing prices (last price of each day)
        daily_prices: dict[str, Decimal] = {}
        for ts, price in history:
            # Only consider prices up to current_time
            if ts <= current_time:
                date_key = ts.date().isoformat()
                daily_prices[date_key] = price

        # Get last N days
        sorted_dates = sorted(daily_prices.keys())
        if len(sorted_dates) < period:
            return None

        recent_prices = [daily_prices[date] for date in sorted_dates[-period:]]
        return sum(recent_prices, Decimal("0")) / Decimal(str(period))

    def detect_trend(self, instrument: str, current_time: datetime) -> str | None:
        """
        Detect trend direction using MA crossover.

        Args:
            instrument: Currency pair
            current_time: Current timestamp

        Returns:
            'bullish', 'bearish', or None
        """
        short_ma = self.calculate_ma(instrument, self.short_period, current_time)
        long_ma = self.calculate_ma(instrument, self.long_period, current_time)

        if short_ma is None or long_ma is None:
            return None

        if short_ma > long_ma:
            return "bullish"
        if short_ma < long_ma:
            return "bearish"

        return None


class SwingDetector:
    """
    Detect swing highs and lows for profit targets.

    Requirements: 5.1, 5.3
    """

    def __init__(self, lookback_days: int = 10) -> None:
        """
        Initialize the swing detector.

        Args:
            lookback_days: Days to look back for swing points
        """
        self.lookback_days = lookback_days
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

        # Clean old data
        cutoff = timestamp - timedelta(days=self.lookback_days * 2)
        self.price_history[instrument] = [
            (ts, p) for ts, p in self.price_history[instrument] if ts > cutoff
        ]

    def get_swing_high(self, instrument: str, current_time: datetime) -> Decimal | None:
        """
        Get the highest swing high in lookback period.

        Args:
            instrument: Currency pair
            current_time: Current timestamp

        Returns:
            Swing high price or None
        """
        if instrument not in self.price_history:
            return None

        cutoff = current_time - timedelta(days=self.lookback_days)
        recent_prices = [p for ts, p in self.price_history[instrument] if ts >= cutoff]

        if not recent_prices:
            return None

        return max(recent_prices)

    def get_swing_low(self, instrument: str, current_time: datetime) -> Decimal | None:
        """
        Get the lowest swing low in lookback period.

        Args:
            instrument: Currency pair
            current_time: Current timestamp

        Returns:
            Swing low price or None
        """
        if instrument not in self.price_history:
            return None

        cutoff = current_time - timedelta(days=self.lookback_days)
        recent_prices = [p for ts, p in self.price_history[instrument] if ts >= cutoff]

        if not recent_prices:
            return None

        return min(recent_prices)


class PullbackDetector:
    """
    Detect pullbacks within a trend.

    Requirements: 5.1, 5.3
    """

    def __init__(self, pullback_pips: Decimal | None = None) -> None:
        """
        Initialize the pullback detector.

        Args:
            pullback_pips: Minimum pullback size in pips
        """
        if pullback_pips is None:
            pullback_pips = Decimal("30")
        self.pullback_pips = pullback_pips
        self.recent_high: dict[str, Decimal] = {}
        self.recent_low: dict[str, Decimal] = {}

    def update_extremes(self, instrument: str, price: Decimal) -> None:
        """
        Update recent high and low prices.

        Args:
            instrument: Currency pair
            price: Current price
        """
        if instrument not in self.recent_high:
            self.recent_high[instrument] = price
            self.recent_low[instrument] = price
            return

        if price > self.recent_high[instrument]:
            self.recent_high[instrument] = price

        if price < self.recent_low[instrument]:
            self.recent_low[instrument] = price

    def is_bullish_pullback(self, instrument: str, current_price: Decimal) -> bool:
        """
        Check if current price is a bullish pullback.

        Args:
            instrument: Currency pair
            current_price: Current price

        Returns:
            True if bullish pullback detected
        """
        if instrument not in self.recent_high:
            return False

        recent_high = self.recent_high[instrument]
        pip_value = Decimal("0.01") if "JPY" in instrument else Decimal("0.0001")
        pullback_distance = (recent_high - current_price) / pip_value

        return pullback_distance >= self.pullback_pips

    def is_bearish_pullback(self, instrument: str, current_price: Decimal) -> bool:
        """
        Check if current price is a bearish pullback.

        Args:
            instrument: Currency pair
            current_price: Current price

        Returns:
            True if bearish pullback detected
        """
        if instrument not in self.recent_low:
            return False

        recent_low = self.recent_low[instrument]
        pip_value = Decimal("0.01") if "JPY" in instrument else Decimal("0.0001")
        pullback_distance = (current_price - recent_low) / pip_value

        return pullback_distance >= self.pullback_pips

    def reset_extremes(self, instrument: str) -> None:
        """
        Reset extremes for new trend cycle.

        Args:
            instrument: Currency pair
        """
        if instrument in self.recent_high:
            del self.recent_high[instrument]
        if instrument in self.recent_low:
            del self.recent_low[instrument]


class SwingTradingStrategy(BaseStrategy):
    """
    Swing Trading Strategy.

    This strategy:
    - Detects multi-day trends using moving averages
    - Enters on pullbacks within the trend
    - Uses wider stop-loss (50-100 pips)
    - Sets profit targets based on previous swing highs/lows

    Requirements: 5.1, 5.3
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the Swing Trading Strategy."""
        super().__init__(*args, **kwargs)

        # Configuration
        self.base_units = Decimal(str(self.get_config_value("base_units", 1000)))
        self.short_ma_period = int(self.get_config_value("short_ma_period", 20))
        self.long_ma_period = int(self.get_config_value("long_ma_period", 50))
        self.pullback_pips = Decimal(str(self.get_config_value("pullback_pips", 30)))
        self.stop_loss_pips = Decimal(str(self.get_config_value("stop_loss_pips", 75)))
        self.swing_lookback_days = int(self.get_config_value("swing_lookback_days", 10))

        # Components
        self.trend_detector = TrendDetector(self.short_ma_period, self.long_ma_period)
        self.swing_detector = SwingDetector(self.swing_lookback_days)
        self.pullback_detector = PullbackDetector(self.pullback_pips)

    def on_tick(
        self, tick_data: TickData
    ) -> list[Order]:  # pylint: disable=too-many-return-statements
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

        # Update price history
        self.trend_detector.add_price(tick_data.instrument, tick_data.timestamp, tick_data.mid)
        self.swing_detector.add_price(tick_data.instrument, tick_data.timestamp, tick_data.mid)
        self.pullback_detector.update_extremes(tick_data.instrument, tick_data.mid)

        # Get open positions for this instrument
        open_positions = self.get_open_positions(tick_data.instrument)

        # Don't enter new positions if we already have one
        if open_positions:
            return orders

        # Detect trend
        trend = self.trend_detector.detect_trend(tick_data.instrument, tick_data.timestamp)

        if trend is None:
            return orders

        # Check for pullback entry opportunities
        if trend == "bullish" and self.pullback_detector.is_bullish_pullback(
            tick_data.instrument, tick_data.mid
        ):
            entry_order = self._create_entry_order(tick_data, "long", trend)
            if entry_order:
                orders.append(entry_order)
                # Reset extremes after entry
                self.pullback_detector.reset_extremes(tick_data.instrument)

        elif trend == "bearish" and self.pullback_detector.is_bearish_pullback(
            tick_data.instrument, tick_data.mid
        ):
            entry_order = self._create_entry_order(tick_data, "short", trend)
            if entry_order:
                orders.append(entry_order)
                # Reset extremes after entry
                self.pullback_detector.reset_extremes(tick_data.instrument)

        return orders

    def _create_entry_order(self, tick_data: TickData, direction: str, trend: str) -> Order | None:
        """
        Create entry order for swing trade.

        Args:
            tick_data: Current tick data
            direction: Position direction ('long' or 'short')
            trend: Detected trend ('bullish' or 'bearish')

        Returns:
            Order instance or None
        """
        pip_value = Decimal("0.01") if "JPY" in tick_data.instrument else Decimal("0.0001")

        # Calculate stop-loss
        if direction == "long":
            stop_loss = tick_data.mid - (self.stop_loss_pips * pip_value)
        else:  # short
            stop_loss = tick_data.mid + (self.stop_loss_pips * pip_value)

        # Calculate take-profit based on swing highs/lows
        take_profit = self._calculate_take_profit(tick_data, direction, pip_value)

        order = Order(
            account=self.account,
            strategy=self.strategy,
            order_id=(f"swing_{direction}_" f"{tick_data.timestamp.timestamp()}"),
            instrument=tick_data.instrument,
            order_type="market",
            direction=direction,
            units=self.base_units,
            price=tick_data.mid,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )

        self.log_strategy_event(
            "swing_entry",
            f"Swing trade entry: {direction}",
            {
                "instrument": tick_data.instrument,
                "direction": direction,
                "trend": trend,
                "units": str(self.base_units),
                "price": str(tick_data.mid),
                "stop_loss": str(stop_loss),
                "take_profit": str(take_profit),
            },
        )

        return order

    def _calculate_take_profit(
        self, tick_data: TickData, direction: str, pip_value: Decimal
    ) -> Decimal:
        """
        Calculate take-profit based on swing highs/lows.

        Args:
            tick_data: Current tick data
            direction: Position direction
            pip_value: Pip value for instrument

        Returns:
            Take-profit price
        """
        if direction == "long":
            # Target previous swing high
            swing_high = self.swing_detector.get_swing_high(
                tick_data.instrument, tick_data.timestamp
            )
            if swing_high is not None and swing_high > tick_data.mid:
                return swing_high
            # Fallback: use fixed pip target
            return tick_data.mid + (Decimal("100") * pip_value)

        # short direction
        # Target previous swing low
        swing_low = self.swing_detector.get_swing_low(tick_data.instrument, tick_data.timestamp)
        if swing_low is not None and swing_low < tick_data.mid:
            return swing_low
        # Fallback: use fixed pip target
        return tick_data.mid - (Decimal("100") * pip_value)

    def on_position_update(self, position: Position) -> None:
        """
        Handle position updates.

        Args:
            position: Position that was updated

        Requirements: 5.1, 5.3
        """
        if position.closed_at is not None:
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

    def _validate_decimal_param(
        self, config: dict[str, Any], key: str, default: int, min_value: Decimal | None = None
    ) -> Decimal:
        """Validate a decimal configuration parameter."""
        value = config.get(key, default)
        try:
            decimal_value = Decimal(str(value))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid {key}: {value}") from exc

        if decimal_value <= Decimal("0"):
            raise ValueError(f"{key} must be positive")

        if min_value is not None and decimal_value < min_value:
            raise ValueError(f"{key} must be at least {min_value}")

        return decimal_value

    def _validate_int_param(self, config: dict[str, Any], key: str, default: int) -> int:
        """Validate an integer configuration parameter."""
        value = config.get(key, default)
        try:
            int_value = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid {key}: {value}") from exc

        if int_value <= 0:
            raise ValueError(f"{key} must be positive")

        return int_value

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
        self._validate_decimal_param(config, "base_units", 1000)

        # Validate MA periods
        short_ma_int = self._validate_int_param(config, "short_ma_period", 20)
        long_ma_int = self._validate_int_param(config, "long_ma_period", 50)

        if long_ma_int <= short_ma_int:
            raise ValueError("long_ma_period must be greater than short_ma_period")

        # Validate pullback pips
        self._validate_decimal_param(config, "pullback_pips", 30)

        # Validate stop loss pips (minimum 50 for swing trading)
        stop_loss = self._validate_decimal_param(config, "stop_loss_pips", 75, Decimal("50"))
        if stop_loss < Decimal("50"):
            raise ValueError("stop_loss_pips must be at least 50 for swing trading")

        # Validate swing lookback days
        self._validate_int_param(config, "swing_lookback_days", 10)

        return True


# Configuration schema for Swing Trading Strategy
SWING_TRADING_STRATEGY_CONFIG_SCHEMA = {
    "type": "object",
    "title": "Swing Trading Strategy Configuration",
    "description": ("Configuration for Swing Trading Strategy with " "multi-day trend following"),
    "properties": {
        "base_units": {
            "type": "number",
            "title": "Base Units",
            "description": "Base position size in units",
            "default": 1000,
            "minimum": 1,
        },
        "short_ma_period": {
            "type": "number",
            "title": "Short MA Period (Days)",
            "description": "Short-term moving average period in days",
            "default": 20,
            "minimum": 1,
        },
        "long_ma_period": {
            "type": "number",
            "title": "Long MA Period (Days)",
            "description": "Long-term moving average period in days",
            "default": 50,
            "minimum": 1,
        },
        "pullback_pips": {
            "type": "number",
            "title": "Pullback Pips",
            "description": "Minimum pullback size in pips to enter",
            "default": 30,
            "minimum": 10,
        },
        "stop_loss_pips": {
            "type": "number",
            "title": "Stop Loss Pips",
            "description": "Wider stop loss distance in pips (50-100)",
            "default": 75,
            "minimum": 50,
        },
        "swing_lookback_days": {
            "type": "number",
            "title": "Swing Lookback Days",
            "description": "Days to look back for swing highs/lows",
            "default": 10,
            "minimum": 1,
        },
    },
    "required": [],
}

# Register the strategy
register_strategy("swing_trading", SWING_TRADING_STRATEGY_CONFIG_SCHEMA)(SwingTradingStrategy)
