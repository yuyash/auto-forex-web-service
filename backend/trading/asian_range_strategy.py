"""
Asian Range Strategy implementation.

This module implements an Asian Range Strategy that:
- Detects the Asian trading session (Tokyo: 00:00-09:00 GMT)
- Identifies the high/low range during the Asian session
- Trades range-bound (buy at support, sell at resistance)
- Detects breakouts for range exit

Requirements: 5.1, 5.3
"""

from datetime import datetime, time
from datetime import timezone as dt_timezone
from decimal import Decimal
from typing import Any

from django.utils import timezone

from .base_strategy import BaseStrategy
from .models import Order, Position
from .strategy_registry import register_strategy
from .tick_data_models import TickData


class AsianSessionDetector:
    """
    Detect Asian trading session times (Tokyo session).

    Requirements: 5.1, 5.3
    """

    def __init__(self) -> None:
        """Initialize the Asian session detector."""
        # Tokyo session: 00:00-09:00 GMT
        self.session_start = time(0, 0, 0)
        self.session_end = time(9, 0, 0)

    def is_asian_session(self, dt: datetime) -> bool:
        """
        Check if current time is within Asian trading session (00:00-09:00 GMT).

        Args:
            dt: Datetime to check (should be in GMT/UTC)

        Returns:
            True if within Asian session
        """
        current_time = dt.time()
        return self.session_start <= current_time < self.session_end


class AsianRangeDetector:
    """
    Detect high/low range during Asian session.

    Requirements: 5.1, 5.3
    """

    def __init__(self) -> None:
        """Initialize the Asian range detector."""
        self.range_high: Decimal | None = None
        self.range_low: Decimal | None = None
        self.range_established = False
        self.last_detection_date: datetime | None = None

    def update_range(self, price: Decimal, dt: datetime) -> None:
        """
        Update the range high/low during Asian session.

        Args:
            price: Current price
            dt: Current datetime
        """
        # Reset range if it's a new day
        if self.last_detection_date is None or dt.date() != self.last_detection_date.date():
            self.reset_range()
            self.last_detection_date = dt

        # Update range high/low
        if self.range_high is None or price > self.range_high:
            self.range_high = price

        if self.range_low is None or price < self.range_low:
            self.range_low = price

        # Mark as established once we have both high and low
        if self.range_high is not None and self.range_low is not None:
            self.range_established = True

    def reset_range(self) -> None:
        """Reset the range for a new day."""
        self.range_high = None
        self.range_low = None
        self.range_established = False

    def is_breakout_above(self, price: Decimal) -> bool:
        """
        Check if price breaks above range high.

        Args:
            price: Current price

        Returns:
            True if breakout above range
        """
        if not self.range_established or self.range_high is None:
            return False
        return price > self.range_high

    def is_breakout_below(self, price: Decimal) -> bool:
        """
        Check if price breaks below range low.

        Args:
            price: Current price

        Returns:
            True if breakout below range
        """
        if not self.range_established or self.range_low is None:
            return False
        return price < self.range_low

    def is_near_support(self, price: Decimal, tolerance_pips: Decimal, instrument: str) -> bool:
        """
        Check if price is near support (range low).

        Args:
            price: Current price
            tolerance_pips: Tolerance in pips
            instrument: Currency pair

        Returns:
            True if near support
        """
        if not self.range_established or self.range_low is None:
            return False

        pip_value = Decimal("0.01") if "JPY" in instrument else Decimal("0.0001")
        tolerance = tolerance_pips * pip_value

        return abs(price - self.range_low) <= tolerance

    def is_near_resistance(self, price: Decimal, tolerance_pips: Decimal, instrument: str) -> bool:
        """
        Check if price is near resistance (range high).

        Args:
            price: Current price
            tolerance_pips: Tolerance in pips
            instrument: Currency pair

        Returns:
            True if near resistance
        """
        if not self.range_established or self.range_high is None:
            return False

        pip_value = Decimal("0.01") if "JPY" in instrument else Decimal("0.0001")
        tolerance = tolerance_pips * pip_value

        return abs(price - self.range_high) <= tolerance

    def get_range_size_pips(self, instrument: str) -> Decimal:
        """
        Get the range size in pips.

        Args:
            instrument: Currency pair

        Returns:
            Range size in pips
        """
        if self.range_high is None or self.range_low is None:
            return Decimal("0")

        range_size = self.range_high - self.range_low

        # JPY pairs have different pip calculation
        if "JPY" in instrument:
            return range_size / Decimal("0.01")

        return range_size / Decimal("0.0001")


class AsianRangeStrategy(BaseStrategy):
    """
    Asian Range Strategy.

    This strategy:
    - Detects the Asian trading session (Tokyo: 00:00-09:00 GMT)
    - Identifies the high/low range during the Asian session
    - Trades range-bound (buy at support, sell at resistance)
    - Detects breakouts for range exit

    Requirements: 5.1, 5.3
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the Asian Range Strategy."""
        super().__init__(*args, **kwargs)

        # Configuration
        self.base_units = Decimal(str(self.get_config_value("base_units", 1000)))
        self.support_tolerance_pips = Decimal(
            str(self.get_config_value("support_tolerance_pips", 5))
        )
        self.resistance_tolerance_pips = Decimal(
            str(self.get_config_value("resistance_tolerance_pips", 5))
        )
        self.stop_loss_pips = Decimal(str(self.get_config_value("stop_loss_pips", 15)))
        self.take_profit_pips = Decimal(str(self.get_config_value("take_profit_pips", 30)))
        self.min_range_pips = Decimal(str(self.get_config_value("min_range_pips", 15)))

        # Components
        self.session_detector = AsianSessionDetector()
        self.range_detectors: dict[str, AsianRangeDetector] = {}

        # Initialize range detectors for each instrument
        for instrument in self.instruments:
            self.range_detectors[instrument] = AsianRangeDetector()

    def on_tick(  # pylint: disable=too-many-return-statements,too-many-branches
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

        # Convert timestamp to GMT/UTC
        dt_utc = tick_data.timestamp
        if timezone.is_aware(dt_utc):
            dt_utc = dt_utc.astimezone(dt_timezone.utc)

        range_detector = self.range_detectors.get(tick_data.instrument)
        if not range_detector:
            return orders

        # Update range during Asian session
        if self.session_detector.is_asian_session(dt_utc):
            range_detector.update_range(tick_data.mid, dt_utc)

            # Log range establishment
            if range_detector.range_established:
                range_size = range_detector.get_range_size_pips(tick_data.instrument)
                if range_size > Decimal("0"):
                    self.log_strategy_event(
                        "asian_range_updated",
                        f"Asian range updated: {range_size} pips",
                        {
                            "instrument": tick_data.instrument,
                            "range_high": str(range_detector.range_high),
                            "range_low": str(range_detector.range_low),
                            "range_size_pips": str(range_size),
                        },
                    )

        # Check if range is established and large enough
        if not range_detector.range_established:
            return orders

        range_size = range_detector.get_range_size_pips(tick_data.instrument)
        if range_size < self.min_range_pips:
            return orders

        # Get open positions for this instrument
        open_positions = self.get_open_positions(tick_data.instrument)

        # Check for breakouts first (exit condition)
        breakout_orders = self._check_breakouts(tick_data, range_detector, open_positions)
        if breakout_orders:
            orders.extend(breakout_orders)
            return orders

        # Check for range-bound trading opportunities
        range_orders = self._check_range_trading(tick_data, range_detector, open_positions)
        orders.extend(range_orders)

        return orders

    def _check_breakouts(
        self,
        tick_data: TickData,
        range_detector: AsianRangeDetector,
        positions: list[Position],
    ) -> list[Order]:
        """
        Check for breakout conditions and close positions.

        Args:
            tick_data: Current tick data
            range_detector: Range detector for this instrument
            positions: List of open positions

        Returns:
            List of orders to execute
        """
        orders: list[Order] = []
        current_price = tick_data.mid

        # Check for breakout above range
        if range_detector.is_breakout_above(current_price):
            # Close all positions on breakout
            for position in positions:
                close_order = self._create_close_order(position, tick_data, "breakout_above")
                if close_order:
                    orders.append(close_order)

            # Reset range after breakout
            if orders:
                range_detector.reset_range()

        # Check for breakout below range
        elif range_detector.is_breakout_below(current_price):
            # Close all positions on breakout
            for position in positions:
                close_order = self._create_close_order(position, tick_data, "breakout_below")
                if close_order:
                    orders.append(close_order)

            # Reset range after breakout
            if orders:
                range_detector.reset_range()

        return orders

    def _check_range_trading(
        self,
        tick_data: TickData,
        range_detector: AsianRangeDetector,
        positions: list[Position],
    ) -> list[Order]:
        """
        Check for range-bound trading opportunities.

        Args:
            tick_data: Current tick data
            range_detector: Range detector for this instrument
            positions: List of open positions

        Returns:
            List of orders to execute
        """
        orders: list[Order] = []
        current_price = tick_data.mid

        # Check if price is near support (buy opportunity)
        if range_detector.is_near_support(
            current_price, self.support_tolerance_pips, tick_data.instrument
        ) and not any(p.direction == "long" for p in positions):
            # Only enter if we don't have a long position
            entry_order = self._create_entry_order(
                tick_data, "long", range_detector.range_high, range_detector.range_low
            )
            if entry_order:
                orders.append(entry_order)

        # Check if price is near resistance (sell opportunity)
        elif range_detector.is_near_resistance(
            current_price, self.resistance_tolerance_pips, tick_data.instrument
        ) and not any(p.direction == "short" for p in positions):
            # Only enter if we don't have a short position
            entry_order = self._create_entry_order(
                tick_data, "short", range_detector.range_high, range_detector.range_low
            )
            if entry_order:
                orders.append(entry_order)

        return orders

    def _create_entry_order(
        self,
        tick_data: TickData,
        direction: str,
        range_high: Decimal | None,
        range_low: Decimal | None,
    ) -> Order | None:
        """
        Create entry order for range-bound trading.

        Args:
            tick_data: Current tick data
            direction: Position direction ('long' or 'short')
            range_high: Range high level
            range_low: Range low level

        Returns:
            Order instance or None
        """
        if range_high is None or range_low is None:
            return None

        # Calculate stop-loss and take-profit
        pip_value = Decimal("0.01") if "JPY" in tick_data.instrument else Decimal("0.0001")

        if direction == "long":
            # Stop below range low
            stop_loss = range_low - (self.stop_loss_pips * pip_value)
            # Take profit at resistance
            take_profit = range_high - (self.resistance_tolerance_pips * pip_value)
        else:  # short
            # Stop above range high
            stop_loss = range_high + (self.stop_loss_pips * pip_value)
            # Take profit at support
            take_profit = range_low + (self.support_tolerance_pips * pip_value)

        order = Order(
            account=self.account,
            strategy=self.strategy,
            order_id=f"asian_range_{direction}_{tick_data.timestamp.timestamp()}",
            instrument=tick_data.instrument,
            order_type="market",
            direction=direction,
            units=self.base_units,
            price=tick_data.mid,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )

        self.log_strategy_event(
            "asian_range_entry",
            f"Asian range entry: {direction}",
            {
                "instrument": tick_data.instrument,
                "direction": direction,
                "units": str(self.base_units),
                "price": str(tick_data.mid),
                "range_high": str(range_high),
                "range_low": str(range_low),
                "stop_loss": str(stop_loss),
                "take_profit": str(take_profit),
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
            order_id=f"asian_close_{position.position_id}_{tick_data.timestamp.timestamp()}",
            instrument=position.instrument,
            order_type="market",
            direction=close_direction,
            units=position.units,
            price=tick_data.mid,
        )

        self.log_strategy_event(
            "asian_range_exit",
            f"Asian range exit: {reason}",
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
        # Log position updates for monitoring
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

        # Validate support tolerance pips
        support_tolerance_pips = config.get("support_tolerance_pips", 5)
        try:
            support_tolerance_decimal = Decimal(str(support_tolerance_pips))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid support_tolerance_pips: {support_tolerance_pips}") from exc

        if support_tolerance_decimal <= Decimal("0"):
            raise ValueError("support_tolerance_pips must be positive")

        # Validate resistance tolerance pips
        resistance_tolerance_pips = config.get("resistance_tolerance_pips", 5)
        try:
            resistance_tolerance_decimal = Decimal(str(resistance_tolerance_pips))
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Invalid resistance_tolerance_pips: {resistance_tolerance_pips}"
            ) from exc

        if resistance_tolerance_decimal <= Decimal("0"):
            raise ValueError("resistance_tolerance_pips must be positive")

        # Validate stop loss pips
        stop_loss_pips = config.get("stop_loss_pips", 15)
        try:
            stop_loss_decimal = Decimal(str(stop_loss_pips))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid stop_loss_pips: {stop_loss_pips}") from exc

        if stop_loss_decimal <= Decimal("0"):
            raise ValueError("stop_loss_pips must be positive")

        # Validate take profit pips
        take_profit_pips = config.get("take_profit_pips", 30)
        try:
            take_profit_decimal = Decimal(str(take_profit_pips))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid take_profit_pips: {take_profit_pips}") from exc

        if take_profit_decimal <= Decimal("0"):
            raise ValueError("take_profit_pips must be positive")

        # Validate minimum range pips
        min_range_pips = config.get("min_range_pips", 15)
        try:
            min_range_decimal = Decimal(str(min_range_pips))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid min_range_pips: {min_range_pips}") from exc

        if min_range_decimal <= Decimal("0"):
            raise ValueError("min_range_pips must be positive")

        return True


# Configuration schema for Asian Range Strategy
ASIAN_RANGE_STRATEGY_CONFIG_SCHEMA = {
    "type": "object",
    "title": "Asian Range Strategy Configuration",
    "description": "Configuration for Asian Range Strategy with range-bound trading",
    "properties": {
        "base_units": {
            "type": "number",
            "title": "Base Units",
            "description": "Base position size in units",
            "default": 1000,
            "minimum": 1,
        },
        "support_tolerance_pips": {
            "type": "number",
            "title": "Support Tolerance Pips",
            "description": "Tolerance in pips for support level entry",
            "default": 5,
            "minimum": 1,
        },
        "resistance_tolerance_pips": {
            "type": "number",
            "title": "Resistance Tolerance Pips",
            "description": "Tolerance in pips for resistance level entry",
            "default": 5,
            "minimum": 1,
        },
        "stop_loss_pips": {
            "type": "number",
            "title": "Stop Loss Pips",
            "description": "Stop loss distance in pips from range boundary",
            "default": 15,
            "minimum": 1,
        },
        "take_profit_pips": {
            "type": "number",
            "title": "Take Profit Pips",
            "description": "Take profit distance in pips from entry",
            "default": 30,
            "minimum": 1,
        },
        "min_range_pips": {
            "type": "number",
            "title": "Minimum Range Pips",
            "description": "Minimum range size in pips to trade",
            "default": 15,
            "minimum": 1,
        },
    },
    "required": [],
}

# Register the strategy
register_strategy("asian_range", ASIAN_RANGE_STRATEGY_CONFIG_SCHEMA)(AsianRangeStrategy)
