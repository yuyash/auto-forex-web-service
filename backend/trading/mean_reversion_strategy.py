"""
Mean Reversion Strategy implementation using Bollinger Bands.

This module implements a Mean Reversion Strategy that:
- Calculates Bollinger Bands (20-period, 2 standard deviations)
- Enters long when price touches lower band (oversold)
- Exits when price reaches middle band or upper band
- Implements stop-loss below lower band

Requirements: 5.1, 5.3
"""

from collections import deque
from decimal import Decimal
from typing import Any

from .base_strategy import BaseStrategy
from .models import Order, Position
from .strategy_registry import register_strategy
from .tick_data_models import TickData


class BollingerBandsCalculator:
    """
    Calculate Bollinger Bands.

    Bollinger Bands consist of:
    - Middle Band: Simple Moving Average (SMA)
    - Upper Band: SMA + (Standard Deviation * multiplier)
    - Lower Band: SMA - (Standard Deviation * multiplier)

    Requirements: 5.1, 5.3
    """

    def __init__(self, period: int = 20, std_dev_multiplier: Decimal | None = None) -> None:
        """
        Initialize the Bollinger Bands calculator.

        Args:
            period: Number of periods for SMA calculation (default: 20)
            std_dev_multiplier: Standard deviation multiplier (default: 2.0)
        """
        self.period = period
        self.std_dev_multiplier = (
            std_dev_multiplier if std_dev_multiplier is not None else Decimal("2.0")
        )
        self.prices: deque[Decimal] = deque(maxlen=period)
        self.middle_band: Decimal | None = None
        self.upper_band: Decimal | None = None
        self.lower_band: Decimal | None = None

    def add_price(self, price: Decimal) -> None:
        """
        Add a new price and update Bollinger Bands.

        Args:
            price: New price to add
        """
        self.prices.append(price)

        # Calculate bands once we have enough data
        if len(self.prices) >= self.period:
            self._calculate_bands()

    def _calculate_bands(self) -> None:
        """Calculate Bollinger Bands using current price data."""
        prices_list = list(self.prices)

        # Calculate middle band (SMA)
        self.middle_band = sum(prices_list) / Decimal(self.period)

        # Calculate standard deviation
        variance = sum((p - self.middle_band) ** 2 for p in prices_list) / Decimal(self.period)
        std_dev = variance.sqrt()

        # Calculate upper and lower bands
        self.upper_band = self.middle_band + (std_dev * self.std_dev_multiplier)
        self.lower_band = self.middle_band - (std_dev * self.std_dev_multiplier)

    def get_bands(self) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
        """
        Get the current Bollinger Bands.

        Returns:
            Tuple of (upper_band, middle_band, lower_band) or (None, None, None) if not ready
        """
        return (self.upper_band, self.middle_band, self.lower_band)

    def is_ready(self) -> bool:
        """
        Check if Bollinger Bands have enough data to be calculated.

        Returns:
            True if bands are ready
        """
        return self.middle_band is not None


class MeanReversionStrategy(BaseStrategy):
    """
    Mean Reversion Strategy using Bollinger Bands.

    This strategy:
    - Calculates Bollinger Bands (20-period, 2 std dev)
    - Enters long when price touches lower band (oversold)
    - Exits when price reaches middle band or upper band
    - Implements stop-loss below lower band

    Requirements: 5.1, 5.3
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the Mean Reversion Strategy."""
        super().__init__(*args, **kwargs)

        # Configuration
        self.bb_period = int(self.get_config_value("bb_period", 20))
        self.bb_std_dev = Decimal(str(self.get_config_value("bb_std_dev", 2.0)))
        self.base_units = Decimal(str(self.get_config_value("base_units", 1000)))
        self.stop_loss_pips = Decimal(str(self.get_config_value("stop_loss_pips", 10)))
        self.exit_at_middle = bool(self.get_config_value("exit_at_middle", True))

        # Components
        self.bb_calculators: dict[str, BollingerBandsCalculator] = {}

        # Initialize component for the instrument
        self.bb_calculators[self.instrument] = BollingerBandsCalculator(
            self.bb_period, self.bb_std_dev
        )

        # Track entry prices for stop-loss calculation
        self.entry_lower_bands: dict[str, Decimal] = {}

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

        calculator = self.bb_calculators.get(tick_data.instrument)
        if not calculator:
            return orders

        # Update Bollinger Bands with new price
        calculator.add_price(tick_data.mid)

        if not calculator.is_ready():
            return orders

        upper_band, middle_band, lower_band = calculator.get_bands()
        if upper_band is None or middle_band is None or lower_band is None:
            return orders

        # Get open positions for this instrument
        open_positions = self.get_open_positions(tick_data.instrument)

        # Check for exit signals
        if open_positions:
            exit_orders = self._process_exit_signals(
                open_positions,
                tick_data,
                upper_band=upper_band,
                middle_band=middle_band,
                lower_band=lower_band,
            )
            orders.extend(exit_orders)

        # Check for entry signals (only if no open positions)
        elif self._is_price_at_lower_band(tick_data.mid, lower_band):
            entry_order = self._create_entry_order(tick_data, lower_band)
            if entry_order:
                orders.append(entry_order)
                # Store the lower band value for stop-loss calculation
                self.entry_lower_bands[tick_data.instrument] = lower_band

        return orders

    def _is_price_at_lower_band(self, price: Decimal, lower_band: Decimal) -> bool:
        """
        Check if price is touching or below the lower Bollinger Band.

        Args:
            price: Current price
            lower_band: Lower Bollinger Band value

        Returns:
            True if price is at or below lower band
        """
        # Consider price "at" lower band if within 0.1% tolerance
        tolerance = lower_band * Decimal("0.001")
        return price <= (lower_band + tolerance)

    def _is_price_at_middle_band(self, price: Decimal, middle_band: Decimal) -> bool:
        """
        Check if price has reached the middle Bollinger Band.

        Args:
            price: Current price
            middle_band: Middle Bollinger Band value

        Returns:
            True if price is at or above middle band
        """
        return price >= middle_band

    def _is_price_at_upper_band(self, price: Decimal, upper_band: Decimal) -> bool:
        """
        Check if price has reached the upper Bollinger Band.

        Args:
            price: Current price
            upper_band: Upper Bollinger Band value

        Returns:
            True if price is at or above upper band
        """
        # Consider price "at" upper band if within 0.1% tolerance
        tolerance = upper_band * Decimal("0.001")
        return price >= (upper_band - tolerance)

    def _check_stop_loss(
        self, position: Position, current_price: Decimal, lower_band: Decimal
    ) -> bool:
        """
        Check if stop-loss should be triggered.

        Stop-loss is placed below the lower band by stop_loss_pips.

        Args:
            position: Open position
            current_price: Current market price
            lower_band: Current lower Bollinger Band value

        Returns:
            True if stop-loss should be triggered
        """
        # Get the entry lower band if available, otherwise use current
        entry_lower_band = self.entry_lower_bands.get(position.instrument, lower_band)

        # Calculate stop-loss price
        pip_value = Decimal("0.01") if "JPY" in position.instrument else Decimal("0.0001")
        stop_loss_price = entry_lower_band - (self.stop_loss_pips * pip_value)

        return current_price <= stop_loss_price

    def _process_exit_signals(
        self,
        positions: list[Position],
        tick_data: TickData,
        *,
        upper_band: Decimal,
        middle_band: Decimal,
        lower_band: Decimal,
    ) -> list[Order]:
        """
        Process exit signals for open positions.

        Args:
            positions: List of open positions
            tick_data: Current tick data
            upper_band: Upper Bollinger Band
            middle_band: Middle Bollinger Band
            lower_band: Lower Bollinger Band

        Returns:
            List of orders to execute
        """
        orders: list[Order] = []

        for position in positions:
            if position.direction != "long":
                continue

            # Check stop-loss first
            if self._check_stop_loss(position, tick_data.mid, lower_band):
                close_order = self._create_close_order(position, tick_data, "stop_loss")
                if close_order:
                    orders.append(close_order)
                    # Clean up entry lower band
                    self.entry_lower_bands.pop(position.instrument, None)
                continue

            # Check exit at middle band
            if self.exit_at_middle and self._is_price_at_middle_band(tick_data.mid, middle_band):
                close_order = self._create_close_order(position, tick_data, "middle_band")
                if close_order:
                    orders.append(close_order)
                    # Clean up entry lower band
                    self.entry_lower_bands.pop(position.instrument, None)
                continue

            # Check exit at upper band
            if self._is_price_at_upper_band(tick_data.mid, upper_band):
                close_order = self._create_close_order(position, tick_data, "upper_band")
                if close_order:
                    orders.append(close_order)
                    # Clean up entry lower band
                    self.entry_lower_bands.pop(position.instrument, None)

        return orders

    def _create_entry_order(self, tick_data: TickData, lower_band: Decimal) -> Order | None:
        """
        Create entry order when price touches lower band.

        Args:
            tick_data: Current tick data
            lower_band: Lower Bollinger Band value

        Returns:
            Order instance or None
        """
        order = Order(
            account=self.account,
            strategy=self.strategy,
            order_id=f"mean_reversion_long_{tick_data.timestamp.timestamp()}",
            instrument=tick_data.instrument,
            order_type="market",
            direction="long",
            units=self.base_units,
            price=tick_data.mid,
        )

        self.log_strategy_event(
            "mean_reversion_entry",
            "Mean reversion entry at lower band",
            {
                "instrument": tick_data.instrument,
                "direction": "long",
                "units": str(self.base_units),
                "price": str(tick_data.mid),
                "lower_band": str(lower_band),
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
                f"mean_reversion_close_{position.position_id}_" f"{tick_data.timestamp.timestamp()}"
            ),
            instrument=position.instrument,
            order_type="market",
            direction=close_direction,
            units=position.units,
            price=tick_data.mid,
        )

        self.log_strategy_event(
            "mean_reversion_exit",
            f"Mean reversion exit: {reason}",
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
        # Clean up entry lower band when position is closed
        if position.closed_at is not None:
            self.entry_lower_bands.pop(position.instrument, None)

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
        # Validate Bollinger Bands period
        bb_period = config.get("bb_period", 20)
        if not isinstance(bb_period, int) or bb_period < 2:
            raise ValueError("bb_period must be an integer >= 2")

        # Validate standard deviation multiplier
        bb_std_dev = config.get("bb_std_dev", 2.0)
        try:
            bb_std_dev_decimal = Decimal(str(bb_std_dev))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid bb_std_dev: {bb_std_dev}") from exc

        if bb_std_dev_decimal <= Decimal("0"):
            raise ValueError("bb_std_dev must be positive")

        # Validate base units
        base_units = config.get("base_units", 1000)
        try:
            base_units_decimal = Decimal(str(base_units))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid base_units: {base_units}") from exc

        if base_units_decimal <= Decimal("0"):
            raise ValueError("base_units must be positive")

        # Validate stop-loss pips
        stop_loss_pips = config.get("stop_loss_pips", 10)
        try:
            stop_loss_pips_decimal = Decimal(str(stop_loss_pips))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid stop_loss_pips: {stop_loss_pips}") from exc

        if stop_loss_pips_decimal <= Decimal("0"):
            raise ValueError("stop_loss_pips must be positive")

        return True


# Configuration schema for Mean Reversion Strategy
MEAN_REVERSION_STRATEGY_CONFIG_SCHEMA = {
    "type": "object",
    "title": "Mean Reversion Strategy Configuration",
    "description": "Configuration for Mean Reversion Strategy using Bollinger Bands",
    "properties": {
        "bb_period": {
            "type": "integer",
            "title": "Bollinger Bands Period",
            "description": "Number of periods for Bollinger Bands calculation",
            "default": 20,
            "minimum": 2,
        },
        "bb_std_dev": {
            "type": "number",
            "title": "Standard Deviation Multiplier",
            "description": "Standard deviation multiplier for Bollinger Bands",
            "default": 2.0,
            "minimum": 0.1,
        },
        "base_units": {
            "type": "number",
            "title": "Base Units",
            "description": "Base position size in units",
            "default": 1000,
            "minimum": 1,
        },
        "stop_loss_pips": {
            "type": "number",
            "title": "Stop Loss (Pips)",
            "description": "Stop-loss distance below lower band in pips",
            "default": 10,
            "minimum": 1,
        },
        "exit_at_middle": {
            "type": "boolean",
            "title": "Exit at Middle Band",
            "description": (
                "Exit position when price reaches middle band "
                "(if false, only exit at upper band)"
            ),
            "default": True,
        },
    },
    "required": [],
}

# Register the strategy
register_strategy(
    "mean_reversion", MEAN_REVERSION_STRATEGY_CONFIG_SCHEMA, display_name="Mean Reversion Strategy"
)(MeanReversionStrategy)
