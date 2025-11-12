"""
London Breakout Strategy implementation.

This module implements a London Breakout Strategy that:
- Detects the London trading session (8:00-9:00 GMT)
- Identifies the high/low range during the first hour
- Enters trades when price breaks out of the range
- Exits positions at the end of the London session

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


class LondonSessionDetector:
    """
    Detect London trading session times.

    Requirements: 5.1, 5.3
    """

    def __init__(self) -> None:
        """Initialize the London session detector."""
        # London session: 8:00-9:00 GMT for range detection
        # Full session: 8:00-16:00 GMT for trading
        self.range_start = time(8, 0, 0)
        self.range_end = time(9, 0, 0)
        self.session_end = time(16, 0, 0)

    def is_range_detection_period(self, dt: datetime) -> bool:
        """
        Check if current time is within range detection period (8:00-9:00 GMT).

        Args:
            dt: Datetime to check (should be in GMT/UTC)

        Returns:
            True if within range detection period
        """
        current_time = dt.time()
        return self.range_start <= current_time < self.range_end

    def is_london_session(self, dt: datetime) -> bool:
        """
        Check if current time is within London trading session (8:00-16:00 GMT).

        Args:
            dt: Datetime to check (should be in GMT/UTC)

        Returns:
            True if within London session
        """
        current_time = dt.time()
        return self.range_start <= current_time < self.session_end

    def is_session_end(self, dt: datetime) -> bool:
        """
        Check if current time is at or past session end (16:00 GMT).

        Args:
            dt: Datetime to check (should be in GMT/UTC)

        Returns:
            True if at or past session end
        """
        current_time = dt.time()
        return current_time >= self.session_end


class RangeDetector:
    """
    Detect high/low range during London session first hour.

    Requirements: 5.1, 5.3
    """

    def __init__(self) -> None:
        """Initialize the range detector."""
        self.range_high: Decimal | None = None
        self.range_low: Decimal | None = None
        self.range_established = False
        self.last_detection_date: datetime | None = None

    def update_range(self, price: Decimal, dt: datetime) -> None:
        """
        Update the range high/low during detection period.

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

    def finalize_range(self) -> None:
        """Mark the range as established after detection period ends."""
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


class LondonBreakoutStrategy(BaseStrategy):
    """
    London Breakout Strategy.

    This strategy:
    - Detects the London trading session (8:00-9:00 GMT)
    - Identifies the high/low range during the first hour
    - Enters trades when price breaks out of the range
    - Exits positions at the end of the London session

    Requirements: 5.1, 5.3
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the London Breakout Strategy."""
        super().__init__(*args, **kwargs)

        # Configuration
        self.base_units = Decimal(str(self.get_config_value("base_units", 1000)))
        self.stop_loss_pips = Decimal(str(self.get_config_value("stop_loss_pips", 20)))
        self.take_profit_pips = Decimal(str(self.get_config_value("take_profit_pips", 40)))
        self.min_range_pips = Decimal(str(self.get_config_value("min_range_pips", 10)))

        # Components
        self.session_detector = LondonSessionDetector()
        self.range_detectors: dict[str, RangeDetector] = {}

        # Initialize range detector for the instrument
        self.range_detectors[self.instrument] = RangeDetector()

        # State tracking
        self.in_detection_period: dict[str, bool] = {}
        self.breakout_entered: dict[str, bool] = {}

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

        # Check if we're in range detection period
        if self.session_detector.is_range_detection_period(dt_utc):
            # Update range during first hour
            range_detector.update_range(tick_data.mid, dt_utc)
            self.in_detection_period[tick_data.instrument] = True

        elif self.in_detection_period.get(tick_data.instrument, False):
            # Just exited detection period, finalize range
            range_detector.finalize_range()
            self.in_detection_period[tick_data.instrument] = False

            # Log range establishment
            if range_detector.range_established:
                range_size = range_detector.get_range_size_pips(tick_data.instrument)
                self.log_strategy_event(
                    "london_range_established",
                    f"London range established: {range_size} pips",
                    {
                        "instrument": tick_data.instrument,
                        "range_high": str(range_detector.range_high),
                        "range_low": str(range_detector.range_low),
                        "range_size_pips": str(range_size),
                    },
                )

        # Check for session end - close all positions
        if self.session_detector.is_session_end(dt_utc):
            exit_orders = self._process_session_end(tick_data)
            orders.extend(exit_orders)
            # Reset for next day
            range_detector.reset_range()
            self.breakout_entered[tick_data.instrument] = False
            return orders

        # Only trade during London session after range is established
        if not self.session_detector.is_london_session(dt_utc):
            return orders

        if not range_detector.range_established:
            return orders

        # Check if range is large enough to trade
        range_size = range_detector.get_range_size_pips(tick_data.instrument)
        if range_size < self.min_range_pips:
            return orders

        # Get open positions for this instrument
        open_positions = self.get_open_positions(tick_data.instrument)

        # Check for breakouts
        breakout_orders = self._check_breakouts(tick_data, range_detector, open_positions)
        orders.extend(breakout_orders)

        return orders

    def _check_breakouts(  # pylint: disable=too-many-branches
        self,
        tick_data: TickData,
        range_detector: RangeDetector,
        positions: list[Position],
    ) -> list[Order]:
        """
        Check for breakout conditions.

        Args:
            tick_data: Current tick data
            range_detector: Range detector for this instrument
            positions: List of open positions

        Returns:
            List of orders to execute
        """
        orders: list[Order] = []
        current_price = tick_data.mid

        # Don't enter if we already have a breakout position
        if self.breakout_entered.get(tick_data.instrument, False):
            return orders

        # Check for breakout above range (bullish)
        if range_detector.is_breakout_above(current_price):
            # Close any short positions
            for position in positions:
                if position.direction == "short":
                    close_order = self._create_close_order(
                        position, tick_data, "range_breakout_above"
                    )
                    if close_order:
                        orders.append(close_order)

            # Enter long position if we don't have one
            if not any(p.direction == "long" for p in positions):
                entry_order = self._create_entry_order(
                    tick_data, "long", range_detector.range_high, range_detector.range_low
                )
                if entry_order:
                    orders.append(entry_order)
                    self.breakout_entered[tick_data.instrument] = True

        # Check for breakout below range (bearish)
        elif range_detector.is_breakout_below(current_price):
            # Close any long positions
            for position in positions:
                if position.direction == "long":
                    close_order = self._create_close_order(
                        position, tick_data, "range_breakout_below"
                    )
                    if close_order:
                        orders.append(close_order)

            # Enter short position if we don't have one
            if not any(p.direction == "short" for p in positions):
                entry_order = self._create_entry_order(
                    tick_data, "short", range_detector.range_high, range_detector.range_low
                )
                if entry_order:
                    orders.append(entry_order)
                    self.breakout_entered[tick_data.instrument] = True

        return orders

    def _create_entry_order(
        self,
        tick_data: TickData,
        direction: str,
        range_high: Decimal | None,
        range_low: Decimal | None,
    ) -> Order | None:
        """
        Create entry order for breakout.

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
            # Take profit above entry
            take_profit = tick_data.mid + (self.take_profit_pips * pip_value)
        else:  # short
            # Stop above range high
            stop_loss = range_high + (self.stop_loss_pips * pip_value)
            # Take profit below entry
            take_profit = tick_data.mid - (self.take_profit_pips * pip_value)

        order = Order(
            account=self.account,
            strategy=self.strategy,
            order_id=f"london_breakout_{direction}_{tick_data.timestamp.timestamp()}",
            instrument=tick_data.instrument,
            order_type="market",
            direction=direction,
            units=self.base_units,
            price=tick_data.mid,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )

        self.log_strategy_event(
            "london_breakout_entry",
            f"London breakout entry: {direction}",
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
            order_id=f"london_close_{position.position_id}_{tick_data.timestamp.timestamp()}",
            instrument=position.instrument,
            order_type="market",
            direction=close_direction,
            units=position.units,
            price=tick_data.mid,
        )

        self.log_strategy_event(
            "london_breakout_exit",
            f"London breakout exit: {reason}",
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

    def _process_session_end(self, tick_data: TickData) -> list[Order]:
        """
        Process end of London session - close all positions.

        Args:
            tick_data: Current tick data

        Returns:
            List of close orders
        """
        orders: list[Order] = []
        open_positions = self.get_open_positions(tick_data.instrument)

        for position in open_positions:
            close_order = self._create_close_order(position, tick_data, "session_end")
            if close_order:
                orders.append(close_order)

        return orders

    def on_position_update(self, position: Position) -> None:
        """
        Handle position updates.

        Args:
            position: Position that was updated

        Requirements: 5.1, 5.3
        """
        # Reset breakout tracking when position is closed
        if position.closed_at is not None and position.instrument in self.breakout_entered:
            self.breakout_entered[position.instrument] = False

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

        # Validate stop loss pips
        stop_loss_pips = config.get("stop_loss_pips", 20)
        try:
            stop_loss_decimal = Decimal(str(stop_loss_pips))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid stop_loss_pips: {stop_loss_pips}") from exc

        if stop_loss_decimal <= Decimal("0"):
            raise ValueError("stop_loss_pips must be positive")

        # Validate take profit pips
        take_profit_pips = config.get("take_profit_pips", 40)
        try:
            take_profit_decimal = Decimal(str(take_profit_pips))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid take_profit_pips: {take_profit_pips}") from exc

        if take_profit_decimal <= Decimal("0"):
            raise ValueError("take_profit_pips must be positive")

        # Validate minimum range pips
        min_range_pips = config.get("min_range_pips", 10)
        try:
            min_range_decimal = Decimal(str(min_range_pips))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid min_range_pips: {min_range_pips}") from exc

        if min_range_decimal <= Decimal("0"):
            raise ValueError("min_range_pips must be positive")

        return True


# Configuration schema for London Breakout Strategy
LONDON_BREAKOUT_STRATEGY_CONFIG_SCHEMA = {
    "type": "object",
    "title": "London Breakout Strategy Configuration",
    "description": "Configuration for London Breakout Strategy with session-based trading",
    "properties": {
        "base_units": {
            "type": "number",
            "title": "Base Units",
            "description": "Base position size in units",
            "default": 1000,
            "minimum": 1,
        },
        "stop_loss_pips": {
            "type": "number",
            "title": "Stop Loss Pips",
            "description": "Stop loss distance in pips from range boundary",
            "default": 20,
            "minimum": 1,
        },
        "take_profit_pips": {
            "type": "number",
            "title": "Take Profit Pips",
            "description": "Take profit distance in pips from entry",
            "default": 40,
            "minimum": 1,
        },
        "min_range_pips": {
            "type": "number",
            "title": "Minimum Range Pips",
            "description": "Minimum range size in pips to trade",
            "default": 10,
            "minimum": 1,
        },
    },
    "required": [],
}

# Register the strategy
register_strategy(
    "london_breakout",
    LONDON_BREAKOUT_STRATEGY_CONFIG_SCHEMA,
    display_name="London Breakout Strategy",
)(LondonBreakoutStrategy)
