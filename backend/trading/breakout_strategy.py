"""
Breakout Strategy implementation with support/resistance level detection.

This module implements a Breakout Strategy that:
- Detects support and resistance levels from recent price action
- Identifies breakouts when price breaks above resistance or below support
- Optionally confirms breakouts with volume
- Places stop-loss at previous support/resistance levels

Requirements: 5.1, 5.3
"""

from collections import deque
from decimal import Decimal
from typing import Any

from .base_strategy import BaseStrategy
from .models import Order, Position
from .strategy_registry import register_strategy
from .tick_data_models import TickData


class SupportResistanceDetector:
    """
    Detect support and resistance levels from price action.

    Requirements: 5.1, 5.3
    """

    def __init__(self, lookback_period: int = 50, threshold_pips: Decimal | None = None) -> None:
        """
        Initialize the support/resistance detector.

        Args:
            lookback_period: Number of prices to analyze for levels
            threshold_pips: Minimum pip distance between levels
        """
        self.lookback_period = lookback_period
        self.threshold_pips = threshold_pips if threshold_pips is not None else Decimal("10")
        self.prices: deque[Decimal] = deque(maxlen=lookback_period)
        self.highs: deque[Decimal] = deque(maxlen=lookback_period)
        self.lows: deque[Decimal] = deque(maxlen=lookback_period)

    def add_price(self, high: Decimal, low: Decimal, close: Decimal) -> None:
        """
        Add a new price bar to the detector.

        Args:
            high: High price of the bar
            low: Low price of the bar
            close: Close price of the bar
        """
        self.prices.append(close)
        self.highs.append(high)
        self.lows.append(low)

    def get_resistance_level(self) -> Decimal | None:
        """
        Get the current resistance level.

        Returns:
            Resistance price level or None if not enough data
        """
        if len(self.highs) < self.lookback_period // 2:
            return None

        # Find recent swing highs
        swing_highs = self._find_swing_highs()

        if not swing_highs:
            return None

        # Cluster swing highs to find resistance
        resistance = self._cluster_levels(swing_highs)

        return resistance

    def get_support_level(self) -> Decimal | None:
        """
        Get the current support level.

        Returns:
            Support price level or None if not enough data
        """
        if len(self.lows) < self.lookback_period // 2:
            return None

        # Find recent swing lows
        swing_lows = self._find_swing_lows()

        if not swing_lows:
            return None

        # Cluster swing lows to find support
        support = self._cluster_levels(swing_lows)

        return support

    def _find_swing_highs(self) -> list[Decimal]:
        """
        Find swing high points in the price data.

        Returns:
            List of swing high prices
        """
        swing_highs = []
        highs_list = list(self.highs)

        # Look for local maxima (swing highs)
        for i in range(2, len(highs_list) - 2):
            if (
                highs_list[i] > highs_list[i - 1]
                and highs_list[i] > highs_list[i - 2]
                and highs_list[i] > highs_list[i + 1]
                and highs_list[i] > highs_list[i + 2]
            ):
                swing_highs.append(highs_list[i])

        return swing_highs

    def _find_swing_lows(self) -> list[Decimal]:
        """
        Find swing low points in the price data.

        Returns:
            List of swing low prices
        """
        swing_lows = []
        lows_list = list(self.lows)

        # Look for local minima (swing lows)
        for i in range(2, len(lows_list) - 2):
            if (
                lows_list[i] < lows_list[i - 1]
                and lows_list[i] < lows_list[i - 2]
                and lows_list[i] < lows_list[i + 1]
                and lows_list[i] < lows_list[i + 2]
            ):
                swing_lows.append(lows_list[i])

        return swing_lows

    def _cluster_levels(self, levels: list[Decimal]) -> Decimal | None:
        """
        Cluster price levels to find the most significant level.

        Args:
            levels: List of price levels to cluster

        Returns:
            Most significant level or None
        """
        if not levels:
            return None

        # Sort levels
        sorted_levels = sorted(levels)

        # Find clusters of levels within threshold
        clusters: list[list[Decimal]] = []
        current_cluster: list[Decimal] = [sorted_levels[0]]

        for i in range(1, len(sorted_levels)):
            pip_diff = abs(sorted_levels[i] - current_cluster[-1]) * Decimal("10000")

            if pip_diff <= self.threshold_pips:
                current_cluster.append(sorted_levels[i])
            else:
                clusters.append(current_cluster)
                current_cluster = [sorted_levels[i]]

        clusters.append(current_cluster)

        # Find the largest cluster
        largest_cluster = max(clusters, key=len)

        # Return the average of the largest cluster
        return sum(largest_cluster) / Decimal(len(largest_cluster))

    def is_ready(self) -> bool:
        """
        Check if detector has enough data.

        Returns:
            True if ready
        """
        return len(self.prices) >= self.lookback_period // 2


class VolumeConfirmation:
    """
    Confirm breakouts with volume analysis.

    Requirements: 5.1, 5.3
    """

    def __init__(self, lookback_period: int = 20, volume_multiplier: Decimal | None = None) -> None:
        """
        Initialize volume confirmation.

        Args:
            lookback_period: Number of bars to calculate average volume
            volume_multiplier: Multiplier for average volume to confirm breakout
        """
        self.lookback_period = lookback_period
        self.volume_multiplier = (
            volume_multiplier if volume_multiplier is not None else Decimal("1.5")
        )
        self.volumes: deque[Decimal] = deque(maxlen=lookback_period)

    def add_volume(self, volume: Decimal) -> None:
        """
        Add a new volume bar.

        Args:
            volume: Volume for the bar
        """
        self.volumes.append(volume)

    def is_volume_confirmed(self, current_volume: Decimal) -> bool:
        """
        Check if current volume confirms a breakout.

        Args:
            current_volume: Current bar volume

        Returns:
            True if volume is above threshold
        """
        if len(self.volumes) < self.lookback_period // 2:
            # Not enough data, assume confirmed
            return True

        avg_volume = sum(self.volumes) / Decimal(len(self.volumes))
        threshold = avg_volume * self.volume_multiplier

        return current_volume >= threshold

    def is_ready(self) -> bool:
        """
        Check if volume confirmation has enough data.

        Returns:
            True if ready
        """
        return len(self.volumes) >= self.lookback_period // 2


class BreakoutStrategy(BaseStrategy):
    """
    Breakout Strategy with support/resistance level detection.

    This strategy:
    - Detects support and resistance levels from recent price action
    - Identifies breakouts when price breaks above resistance or below support
    - Optionally confirms breakouts with volume
    - Places stop-loss at previous support/resistance levels

    Requirements: 5.1, 5.3
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the Breakout Strategy."""
        super().__init__(*args, **kwargs)

        # Configuration
        self.lookback_period = int(self.get_config_value("lookback_period", 50))
        self.threshold_pips = Decimal(str(self.get_config_value("threshold_pips", 10)))
        self.base_units = Decimal(str(self.get_config_value("base_units", 1000)))
        self.use_volume_confirmation = bool(self.get_config_value("use_volume_confirmation", False))
        self.volume_multiplier = Decimal(str(self.get_config_value("volume_multiplier", 1.5)))
        self.stop_loss_buffer_pips = Decimal(str(self.get_config_value("stop_loss_buffer_pips", 5)))

        # Components
        self.sr_detectors: dict[str, SupportResistanceDetector] = {}
        self.volume_confirmations: dict[str, VolumeConfirmation] = {}

        # Initialize component for the instrument
        self.sr_detectors[self.instrument] = SupportResistanceDetector(
            lookback_period=self.lookback_period, threshold_pips=self.threshold_pips
        )

        if self.use_volume_confirmation:
            self.volume_confirmations[self.instrument] = VolumeConfirmation(
                lookback_period=20, volume_multiplier=self.volume_multiplier
            )

        # State tracking
        self.last_breakout: dict[str, str | None] = {}  # instrument -> 'resistance' or 'support'

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

        detector = self.sr_detectors.get(tick_data.instrument)
        if not detector:
            return orders

        # Update detector with new price
        # For tick data, we use mid as high, low, and close
        detector.add_price(tick_data.mid, tick_data.mid, tick_data.mid)

        if not detector.is_ready():
            return orders

        # Get support and resistance levels
        resistance = detector.get_resistance_level()
        support = detector.get_support_level()

        if resistance is None or support is None:
            return orders

        # Get open positions for this instrument
        open_positions = self.get_open_positions(tick_data.instrument)

        # Check for breakouts
        breakout_orders = self._check_breakouts(tick_data, resistance, support, open_positions)
        orders.extend(breakout_orders)

        return orders

    def _check_breakouts(
        self,
        tick_data: TickData,
        resistance: Decimal,
        support: Decimal,
        positions: list[Position],
    ) -> list[Order]:
        """
        Check for breakout conditions.

        Args:
            tick_data: Current tick data
            resistance: Current resistance level
            support: Current support level
            positions: List of open positions

        Returns:
            List of orders to execute
        """
        orders: list[Order] = []
        current_price = tick_data.mid

        # Check for resistance breakout (bullish)
        if current_price > resistance and self._is_valid_breakout(tick_data, "resistance"):
            breakout_orders = self._process_resistance_breakout(tick_data, resistance, positions)
            orders.extend(breakout_orders)
            self.last_breakout[tick_data.instrument] = "resistance"

        # Check for support breakout (bearish)
        elif current_price < support and self._is_valid_breakout(tick_data, "support"):
            breakout_orders = self._process_support_breakout(tick_data, support, positions)
            orders.extend(breakout_orders)
            self.last_breakout[tick_data.instrument] = "support"

        return orders

    def _is_valid_breakout(self, tick_data: TickData, breakout_type: str) -> bool:
        """
        Validate breakout with volume confirmation if enabled.

        Args:
            tick_data: Current tick data
            breakout_type: Type of breakout ('resistance' or 'support')

        Returns:
            True if breakout is valid
        """
        # Check if we already processed this breakout recently
        last_breakout = self.last_breakout.get(tick_data.instrument)
        if last_breakout == breakout_type:
            # Already in a breakout position
            return False

        # Volume confirmation if enabled
        if self.use_volume_confirmation:
            volume_conf = self.volume_confirmations.get(tick_data.instrument)
            if volume_conf is not None and volume_conf.is_ready():
                # For tick data, we don't have volume, so we'll use spread as a proxy
                # Wider spread might indicate higher activity
                spread = tick_data.ask - tick_data.bid
                return volume_conf.is_volume_confirmed(spread * Decimal("10000"))

        return True

    def _process_resistance_breakout(
        self, tick_data: TickData, resistance: Decimal, positions: list[Position]
    ) -> list[Order]:
        """
        Process resistance breakout (bullish).

        Args:
            tick_data: Current tick data
            resistance: Resistance level that was broken
            positions: List of open positions

        Returns:
            List of orders to execute
        """
        orders: list[Order] = []

        # Close any short positions
        for position in positions:
            if position.direction == "short":
                close_order = self._create_close_order(position, tick_data, "resistance_breakout")
                if close_order:
                    orders.append(close_order)

        # Enter long position if we don't have one
        if not any(p.direction == "long" for p in positions):
            entry_order = self._create_entry_order(tick_data, "long", resistance)
            if entry_order:
                orders.append(entry_order)

        return orders

    def _process_support_breakout(
        self, tick_data: TickData, support: Decimal, positions: list[Position]
    ) -> list[Order]:
        """
        Process support breakout (bearish).

        Args:
            tick_data: Current tick data
            support: Support level that was broken
            positions: List of open positions

        Returns:
            List of orders to execute
        """
        orders: list[Order] = []

        # Close any long positions
        for position in positions:
            if position.direction == "long":
                close_order = self._create_close_order(position, tick_data, "support_breakout")
                if close_order:
                    orders.append(close_order)

        # Enter short position if we don't have one
        if not any(p.direction == "short" for p in positions):
            entry_order = self._create_entry_order(tick_data, "short", support)
            if entry_order:
                orders.append(entry_order)

        return orders

    def _create_entry_order(
        self, tick_data: TickData, direction: str, breakout_level: Decimal
    ) -> Order | None:
        """
        Create entry order for breakout.

        Args:
            tick_data: Current tick data
            direction: Position direction ('long' or 'short')
            breakout_level: The support/resistance level that was broken

        Returns:
            Order instance or None
        """
        # Calculate stop-loss at previous support/resistance with buffer
        pip_value = Decimal("0.0001")
        buffer = self.stop_loss_buffer_pips * pip_value

        if direction == "long":
            # Stop below broken resistance
            stop_loss = breakout_level - buffer
        else:  # short
            # Stop above broken support
            stop_loss = breakout_level + buffer

        order = Order(
            account=self.account,
            strategy=self.strategy,
            order_id=f"breakout_{direction}_{tick_data.timestamp.timestamp()}",
            instrument=tick_data.instrument,
            order_type="market",
            direction=direction,
            units=self.base_units,
            price=tick_data.mid,
            stop_loss=stop_loss,
        )

        self.log_strategy_event(
            "breakout_entry",
            f"Breakout entry: {direction} breakout detected",
            {
                "instrument": tick_data.instrument,
                "direction": direction,
                "units": str(self.base_units),
                "price": str(tick_data.mid),
                "breakout_level": str(breakout_level),
                "stop_loss": str(stop_loss),
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
            order_id=f"breakout_close_{position.position_id}_{tick_data.timestamp.timestamp()}",
            instrument=position.instrument,
            order_type="market",
            direction=close_direction,
            units=position.units,
            price=tick_data.mid,
        )

        self.log_strategy_event(
            "breakout_exit",
            f"Breakout exit: {reason}",
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
        # Reset breakout tracking when position is closed
        if position.closed_at is not None and position.instrument in self.last_breakout:
            self.last_breakout[position.instrument] = None

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
        # Validate lookback period
        lookback_period = config.get("lookback_period", 50)
        if not isinstance(lookback_period, int) or lookback_period < 10:
            raise ValueError("lookback_period must be an integer >= 10")

        # Validate threshold pips
        threshold_pips = config.get("threshold_pips", 10)
        try:
            threshold_decimal = Decimal(str(threshold_pips))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid threshold_pips: {threshold_pips}") from exc

        if threshold_decimal <= Decimal("0"):
            raise ValueError("threshold_pips must be positive")

        # Validate base units
        base_units = config.get("base_units", 1000)
        try:
            base_units_decimal = Decimal(str(base_units))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid base_units: {base_units}") from exc

        if base_units_decimal <= Decimal("0"):
            raise ValueError("base_units must be positive")

        # Validate volume multiplier if volume confirmation is enabled
        use_volume = config.get("use_volume_confirmation", False)
        if use_volume:
            volume_multiplier = config.get("volume_multiplier", 1.5)
            try:
                vol_mult_decimal = Decimal(str(volume_multiplier))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Invalid volume_multiplier: {volume_multiplier}") from exc

            if vol_mult_decimal <= Decimal("0"):
                raise ValueError("volume_multiplier must be positive")

        # Validate stop loss buffer pips
        stop_loss_buffer = config.get("stop_loss_buffer_pips", 5)
        try:
            buffer_decimal = Decimal(str(stop_loss_buffer))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid stop_loss_buffer_pips: {stop_loss_buffer}") from exc

        if buffer_decimal < Decimal("0"):
            raise ValueError("stop_loss_buffer_pips must be non-negative")

        return True


# Configuration schema for Breakout Strategy
BREAKOUT_STRATEGY_CONFIG_SCHEMA = {
    "type": "object",
    "title": "Breakout Strategy Configuration",
    "description": "Configuration for Breakout Strategy with support/resistance detection",
    "properties": {
        "lookback_period": {
            "type": "integer",
            "title": "Lookback Period",
            "description": "Number of price bars to analyze for support/resistance levels",
            "default": 50,
            "minimum": 10,
        },
        "threshold_pips": {
            "type": "number",
            "title": "Threshold Pips",
            "description": "Minimum pip distance between support/resistance levels",
            "default": 10,
            "minimum": 1,
        },
        "base_units": {
            "type": "number",
            "title": "Base Units",
            "description": "Base position size in units",
            "default": 1000,
            "minimum": 1,
        },
        "use_volume_confirmation": {
            "type": "boolean",
            "title": "Use Volume Confirmation",
            "description": "Require volume confirmation for breakouts",
            "default": False,
        },
        "volume_multiplier": {
            "type": "number",
            "title": "Volume Multiplier",
            "description": "Multiplier for average volume to confirm breakout",
            "default": 1.5,
            "minimum": 1.0,
        },
        "stop_loss_buffer_pips": {
            "type": "number",
            "title": "Stop Loss Buffer Pips",
            "description": "Buffer in pips beyond support/resistance for stop-loss",
            "default": 5,
            "minimum": 0,
        },
    },
    "required": [],
}

# Register the strategy
register_strategy("breakout", BREAKOUT_STRATEGY_CONFIG_SCHEMA, display_name="Breakout Strategy")(
    BreakoutStrategy
)
