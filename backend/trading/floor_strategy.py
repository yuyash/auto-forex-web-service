"""
Floor Strategy implementation with dynamic scaling and ATR-based volatility lock.

This module implements the Floor Strategy as specified in floor_strategy.md.
The strategy supports:
- Dynamic scaling-in (additive or multiplicative)
- Multi-layer position management (up to 3 layers)
- ATR-based volatility lock
- Margin-maintenance stop-losses

Requirements: 13.1, 13.2, 13.3, 13.4, 13.5
"""

# pylint: disable=too-many-lines

import logging
from decimal import Decimal
from typing import Any

from .base_strategy import BaseStrategy
from .models import Order, Position
from .strategy_registry import register_strategy
from .tick_data_models import TickData

logger = logging.getLogger(__name__)


class LayerManager:
    """
    Manage multiple trading layers.

    Each layer represents a complete cycle of scaling-in and scaling-out.
    Up to 3 layers can be active simultaneously.

    Requirements: 13.1, 13.3
    """

    def __init__(self, max_layers: int) -> None:
        """
        Initialize the layer manager.

        Args:
            max_layers: Maximum number of concurrent layers
        """
        self.max_layers = max_layers
        self.layers: list[Layer] = []

    def create_layer(self, layer_number: int, config: dict[str, Any]) -> "Layer | None":
        """
        Create a new layer.

        Args:
            layer_number: Layer number
            config: Layer configuration

        Returns:
            Layer instance or None if max layers reached
        """
        if len(self.layers) >= self.max_layers:
            return None

        layer = Layer(layer_number=layer_number, config=config)
        self.layers.append(layer)
        return layer

    def get_layer(self, layer_number: int) -> "Layer | None":
        """
        Get a layer by number.

        Args:
            layer_number: Layer number to retrieve

        Returns:
            Layer instance or None if not found
        """
        for layer in self.layers:
            if layer.layer_number == layer_number:
                return layer
        return None

    def get_first_lot_positions(self) -> list[Position]:
        """
        Get first lot positions from all layers for margin protection.

        Returns:
            List of first lot positions
        """
        first_lots = []
        for layer in self.layers:
            if layer.first_lot_position:
                first_lots.append(layer.first_lot_position)
        return first_lots

    def get_all_positions(self) -> list[Position]:
        """
        Get all positions from all layers.

        Returns:
            List of all positions
        """
        all_positions = []
        for layer in self.layers:
            all_positions.extend(layer.positions)
        return all_positions

    def remove_layer(self, layer_number: int) -> None:
        """
        Remove a layer.

        Args:
            layer_number: Layer number to remove
        """
        self.layers = [layer for layer in self.layers if layer.layer_number != layer_number]


class Layer:  # pylint: disable=too-many-instance-attributes
    """
    Represents a single trading layer.

    A layer tracks positions, retracement count, and scaling state.

    Requirements: 13.1, 13.3
    """

    def __init__(self, layer_number: int, config: dict[str, Any]) -> None:
        """
        Initialize a layer.

        Args:
            layer_number: Layer number
            config: Layer configuration
        """
        self.layer_number = layer_number
        self.config = config
        self.positions: list[Position] = []
        self.first_lot_position: Position | None = None
        self.retracement_count = 0
        self.max_retracements_per_layer = int(config.get("max_retracements_per_layer", 10))
        self.last_entry_price: Decimal | None = None
        # Store base_lot_size from config for resetting (Requirements 7.1, 7.3, 7.4)
        self.base_lot_size = Decimal(str(config.get("base_lot_size", 1.0)))
        self.current_lot_size = self.base_lot_size
        self.is_active = True
        self.peak_price: Decimal | None = None  # Track peak price for retracement detection
        self.has_scaled_at_current_level = False  # Prevent multiple scales at same level
        self.has_pending_initial_entry = False  # Track if initial entry order is pending
        self.last_scale_tick_id: str | None = None  # Track last scaling tick (unique ID)
        self.last_initial_entry_tick_id: str | None = None  # Track last initial entry tick
        self.direction: str | None = (
            None  # Store direction for retracements (Requirements 8.1, 8.2, 8.3)
        )

    def add_position(self, position: Position, is_first_lot: bool = False) -> None:
        """
        Add a position to this layer.

        Args:
            position: Position to add
            is_first_lot: Whether this is the first lot of the layer
        """
        self.positions.append(position)
        if is_first_lot:
            self.first_lot_position = position
            self.has_pending_initial_entry = False  # Clear pending flag
            # Initialize peak price for first position
            self.peak_price = position.entry_price
        self.last_entry_price = position.entry_price
        # DO NOT reset has_scaled_at_current_level here!
        # It should only be reset when we see a new peak price

    def increment_retracement_count(self) -> None:
        """Increment retracement count while respecting configured limit."""
        if self.retracement_count < self.max_retracements_per_layer:
            self.retracement_count += 1

    def reset_retracement_count(self) -> None:
        """Reset the retracement count to zero for a new initial entry."""
        self.retracement_count = 0

    def decrement_retracement_count(self, count: int = 1) -> None:
        """Decrease retracement count when positions close."""
        if count < 1:
            return
        self.retracement_count = max(0, self.retracement_count - count)

    def has_retracement_capacity(self) -> bool:
        """Return True if the layer can scale further this cycle."""
        return self.retracement_count < self.max_retracements_per_layer

    def reset_unit_size(self) -> None:
        """
        Reset the unit size to base_lot_size for a new initial entry.

        Requirements: 7.1, 7.3, 7.4
        """
        self.current_lot_size = self.base_lot_size

    def should_create_new_layer(self) -> bool:
        """
        Check if a new layer should be created based on retracement count.

        Returns:
            True if new layer should be created
        """
        trigger_value = self.config.get("retracement_count_trigger")
        auto_advance = self.config.get("auto_advance_on_low_trigger", False)

        # Always unlock a new layer if this layer has exhausted its capacity
        if self.retracement_count >= self.max_retracements_per_layer:
            return True

        if auto_advance:
            return True

        if trigger_value is None:
            trigger_value = self.max_retracements_per_layer

        return self.retracement_count >= trigger_value


class ScalingEngine:
    """
    Handle position scaling logic.

    Supports additive and multiplicative scaling modes.

    Requirements: 13.2
    """

    def __init__(self, mode: str = "additive", amount: Decimal | None = None) -> None:
        """
        Initialize the scaling engine.

        Args:
            mode: Scaling mode ('additive' or 'multiplicative')
            amount: Scaling amount (added for additive, multiplier for multiplicative)
        """
        self.mode = mode
        self.amount = amount if amount is not None else Decimal("1.0")

    def calculate_next_lot_size(self, current_size: Decimal) -> Decimal:
        """
        Calculate next lot size based on scaling mode.

        Args:
            current_size: Current lot size

        Returns:
            Next lot size
        """
        if self.mode == "additive":
            return current_size + self.amount
        if self.mode == "multiplicative":
            return current_size * self.amount
        return current_size

    def should_scale(
        self, entry_price: Decimal, current_price: Decimal, retracement_pips: Decimal
    ) -> bool:
        """
        Check if retracement threshold is met for scaling.

        Args:
            entry_price: Entry price of the position
            current_price: Current market price
            retracement_pips: Retracement threshold in pips

        Returns:
            True if should scale
        """
        pip_movement = abs(current_price - entry_price) * Decimal("10000")
        return pip_movement >= retracement_pips


class FloorStrategy(BaseStrategy):  # pylint: disable=too-many-instance-attributes
    """
    Floor strategy with dynamic scaling and ATR-based volatility lock.

    This strategy implements:
    - Dynamic scaling-in on retracements
    - Multi-layer position management (up to 3 layers)
    - ATR-based volatility lock
    - Margin-maintenance stop-losses
    - Take-profit logic

    Requirements: 13.1, 13.2, 13.3, 13.4, 13.5
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the Floor Strategy."""
        super().__init__(*args, **kwargs)

        # Initialize components
        max_layers = self.get_config_value("max_layers", 3)
        self.layer_manager = LayerManager(max_layers=max_layers)

        scaling_mode = self.get_config_value("scaling_mode", "additive")
        scaling_amount = Decimal(str(self.get_config_value("scaling_amount", 1.0)))
        self.scaling_engine = ScalingEngine(mode=scaling_mode, amount=scaling_amount)

        # Configuration
        self.base_lot_size = Decimal(str(self.get_config_value("base_lot_size", 1.0)))
        self.retracement_pips = Decimal(str(self.get_config_value("retracement_pips", 30)))
        self.take_profit_pips = Decimal(str(self.get_config_value("take_profit_pips", 25)))
        self.max_retracements_per_layer = int(
            self.get_config_value("max_retracements_per_layer", 10)
        )
        self.volatility_lock_multiplier = Decimal(
            str(self.get_config_value("volatility_lock_multiplier", 5.0))
        )

        # Entry signal configuration
        self.entry_signal_lookback_ticks = self.get_config_value("entry_signal_lookback_ticks", 10)

        # Direction decision method configuration
        # Tick-based: "momentum", "sma_crossover", "ema_crossover", "price_vs_sma", "rsi"
        # OHLC-based: "ohlc_sma_crossover", "ohlc_ema_crossover", "ohlc_price_vs_sma"
        self.direction_method = self.get_config_value("direction_method", "momentum")

        # Moving average periods (in ticks) - for tick-based methods
        self.sma_fast_period = self.get_config_value("sma_fast_period", 10)
        self.sma_slow_period = self.get_config_value("sma_slow_period", 30)
        self.ema_fast_period = self.get_config_value("ema_fast_period", 12)
        self.ema_slow_period = self.get_config_value("ema_slow_period", 26)

        # RSI configuration
        self.rsi_period = self.get_config_value("rsi_period", 14)
        self.rsi_overbought = self.get_config_value("rsi_overbought", 70)
        self.rsi_oversold = self.get_config_value("rsi_oversold", 30)

        # OHLC-based configuration
        # Granularity in seconds: 3600=H1, 14400=H4, 86400=D1
        self.ohlc_granularity = self.get_config_value("ohlc_granularity", 3600)  # Default: 1 hour
        self.ohlc_fast_period = self.get_config_value("ohlc_fast_period", 10)  # Fast MA period
        self.ohlc_slow_period = self.get_config_value("ohlc_slow_period", 20)  # Slow MA period

        # OHLC candle storage (aggregated from ticks)
        self._ohlc_candles: dict[str, list[dict[str, Any]]] = {}
        self._current_candle: dict[str, dict[str, Any] | None] = {}

        # State
        self.is_locked = False
        self.normal_atr: Decimal | None = None

        # Initialize tracking attributes
        self._logged_inactive_instruments: set[str] = set()
        self._price_history: dict[str, list[dict[str, Any]]] = {}
        self._no_signal_log_count = 0
        self._tick_count = 0
        self._state_save_interval = self.get_config_value("state_save_interval", 1000)
        self._last_processed_tick_id: str | None = None  # Track last processed tick globally

        # Load state from database if exists
        self._load_state()

        # Create initial layer if no layers exist
        if not self.layer_manager.layers:
            layer_config = self._get_layer_config(1)
            self.layer_manager.create_layer(1, layer_config)

    def _load_state(self) -> None:
        """Load strategy state from database."""
        state = self.get_strategy_state()
        if state:
            self.normal_atr = state.get("normal_atr")
            layer_states = state.get("layer_states", {})

            # Reconstruct layers from state
            for layer_num_str, layer_state in layer_states.items():
                layer_num = int(layer_num_str)
                layer_config = self._get_layer_config(layer_num)
                layer = self.layer_manager.create_layer(layer_num, layer_config)
                if layer:
                    # Retracement counters intentionally reset on restart per product spec
                    layer.reset_retracement_count()

                    # Restore persisted layer parameters when available
                    saved_lot_raw = layer_state.get("current_lot_size")
                    try:
                        saved_lot = (
                            Decimal(saved_lot_raw)
                            if saved_lot_raw is not None
                            else layer.base_lot_size
                        )
                    except (ArithmeticError, ValueError, TypeError):
                        saved_lot = layer.base_lot_size
                    layer.current_lot_size = saved_lot
                    layer.is_active = layer_state.get("is_active", layer.is_active)

    def _save_state(self) -> None:
        """Save strategy state to database."""
        layer_states = {}
        for layer in self.layer_manager.layers:
            layer_states[str(layer.layer_number)] = {
                "current_lot_size": str(layer.current_lot_size),
                "is_active": layer.is_active,
            }

        self.update_strategy_state(
            {
                "layer_states": layer_states,
                "normal_atr": self.normal_atr,
            }
        )

    def on_tick(self, tick_data: TickData) -> list[Order]:
        """
        Process incoming tick data and generate trading signals.

        Args:
            tick_data: TickData instance containing market data

        Returns:
            List of Order instances to execute

        Requirements: 13.1, 13.2, 13.3, 13.4, 13.5
        """
        # CRITICAL: Prevent processing the same tick multiple times
        # This can happen if orders are executed synchronously and trigger callbacks
        tick_id = f"{tick_data.timestamp.timestamp()}_{tick_data.mid}"
        if self._last_processed_tick_id == tick_id:
            logger.debug(f"Skipping duplicate tick processing: {tick_id}")
            return []
        self._last_processed_tick_id = tick_id

        orders: list[Order] = []

        # Check if instrument is active for this strategy
        if not self.is_instrument_active(tick_data.instrument):
            # Log first time we see an inactive instrument
            if not hasattr(self, "_logged_inactive_instruments"):
                self._logged_inactive_instruments = set()
            if tick_data.instrument not in self._logged_inactive_instruments:
                self.log_strategy_event(
                    "inactive_instrument",
                    f"Skipping tick for inactive instrument: {tick_data.instrument}",
                    {
                        "instrument": tick_data.instrument,
                        "strategy_instrument": str(self.instrument),
                    },
                )
                self._logged_inactive_instruments.add(tick_data.instrument)
            return orders

        # Check volatility lock
        if self._check_volatility_lock(tick_data):
            if not self.is_locked:
                self._execute_volatility_lock()
            return orders

        # Check margin protection
        if self._check_margin_liquidation():
            margin_orders = self._execute_margin_protection()
            orders.extend(margin_orders)
            return orders

        # Process each layer
        for layer in self.layer_manager.layers:
            if not layer.is_active:
                continue

            layer_orders = self._process_layer(layer, tick_data)
            orders.extend(layer_orders)

        # Check if we need to create a new layer
        self._check_new_layer_creation()

        # Save state periodically (not on every tick to avoid performance issues)
        self._tick_count += 1
        if self._tick_count % self._state_save_interval == 0:
            self._save_state()

        return orders

    def _check_entry_signal(self, tick_data: TickData) -> dict[str, Any] | None:
        """
        Check for entry signal using configurable technical analysis methods.

        Supported methods (configured via direction_method):
        - "momentum": Simple price momentum over N ticks
        - "sma_crossover": Fast SMA crosses above/below slow SMA
        - "ema_crossover": Fast EMA crosses above/below slow EMA
        - "price_vs_sma": Price above/below SMA
        - "rsi": RSI overbought/oversold levels

        Args:
            tick_data: Current tick data

        Returns:
            Dictionary with direction and reason, or None if no signal
        """
        # Get or create history for this instrument
        if tick_data.instrument not in self._price_history:
            self._price_history[tick_data.instrument] = []

        instrument_history = self._price_history[tick_data.instrument]

        # Add current price to history
        instrument_history.append(
            {
                "timestamp": tick_data.timestamp.timestamp(),
                "price": tick_data.mid,
            }
        )

        # Keep enough history for all indicators (max of all periods + buffer)
        max_period = max(
            self.entry_signal_lookback_ticks,
            self.sma_slow_period,
            self.ema_slow_period,
            self.rsi_period + 1,
        )
        history_limit = max_period + 50
        if len(instrument_history) > history_limit:
            self._price_history[tick_data.instrument] = instrument_history[-history_limit:]
            instrument_history = self._price_history[tick_data.instrument]

        # Get prices as list
        prices = [p["price"] for p in instrument_history]

        # Dispatch to appropriate method using dictionary lookup
        method = self.direction_method.lower()

        # Methods that require prices list
        price_based_methods = {
            "momentum": self._check_momentum_signal,
            "sma_crossover": self._check_sma_crossover_signal,
            "ema_crossover": self._check_ema_crossover_signal,
            "price_vs_sma": self._check_price_vs_sma_signal,
            "rsi": self._check_rsi_signal,
        }

        # Methods that only need tick_data
        ohlc_methods = {
            "ohlc_sma_crossover": self._check_ohlc_sma_crossover_signal,
            "ohlc_ema_crossover": self._check_ohlc_ema_crossover_signal,
            "ohlc_price_vs_sma": self._check_ohlc_price_vs_sma_signal,
        }

        if method in price_based_methods:
            return price_based_methods[method](prices, tick_data)
        if method in ohlc_methods:
            return ohlc_methods[method](tick_data)
        # Default to momentum
        return self._check_momentum_signal(prices, tick_data)

    def _calculate_sma(self, prices: list[Decimal], period: int) -> Decimal | None:
        """Calculate Simple Moving Average."""
        if len(prices) < period:
            return None
        return sum(prices[-period:]) / Decimal(str(period))

    def _calculate_ema(self, prices: list[Decimal], period: int) -> Decimal | None:
        """Calculate Exponential Moving Average."""
        if len(prices) < period:
            return None
        multiplier = Decimal("2") / Decimal(str(period + 1))
        ema = sum(prices[:period]) / Decimal(str(period))  # Start with SMA
        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema
        return ema

    def _calculate_rsi(self, prices: list[Decimal], period: int) -> Decimal | None:
        """Calculate Relative Strength Index."""
        if len(prices) < period + 1:
            return None

        gains = []
        losses = []
        for i in range(1, len(prices)):
            change = prices[i] - prices[i - 1]
            if change > 0:
                gains.append(change)
                losses.append(Decimal("0"))
            else:
                gains.append(Decimal("0"))
                losses.append(abs(change))

        if len(gains) < period:
            return None

        avg_gain = sum(gains[-period:]) / Decimal(str(period))
        avg_loss = sum(losses[-period:]) / Decimal(str(period))

        if avg_loss == 0:
            return Decimal("100")

        rs = avg_gain / avg_loss
        rsi = Decimal("100") - (Decimal("100") / (Decimal("1") + rs))
        return rsi

    def _check_momentum_signal(
        self, prices: list[Decimal], tick_data: TickData
    ) -> dict[str, Any] | None:
        """Check for entry signal using price momentum."""
        if len(prices) < self.entry_signal_lookback_ticks:
            return None

        oldest_price = prices[-self.entry_signal_lookback_ticks]
        current_price = prices[-1]
        pip_movement = (current_price - oldest_price) * Decimal("10000")

        if pip_movement > 0:
            direction = "long"
            reason = (
                f"Momentum: +{pip_movement:.1f} pips over {self.entry_signal_lookback_ticks} ticks"
            )
        else:
            direction = "short"
            reason = (
                f"Momentum: {pip_movement:.1f} pips over {self.entry_signal_lookback_ticks} ticks"
            )

        self._log_entry_signal(
            direction, reason, tick_data, {"method": "momentum", "pip_movement": str(pip_movement)}
        )
        return {"direction": direction, "reason": reason}

    def _check_sma_crossover_signal(
        self, prices: list[Decimal], tick_data: TickData
    ) -> dict[str, Any] | None:
        """Check for entry signal using SMA crossover."""
        fast_sma = self._calculate_sma(prices, self.sma_fast_period)
        slow_sma = self._calculate_sma(prices, self.sma_slow_period)

        if fast_sma is None or slow_sma is None:
            return None

        if fast_sma > slow_sma:
            direction = "long"
            reason = (
                f"SMA Crossover: Fast({self.sma_fast_period})={fast_sma:.5f} > "
                f"Slow({self.sma_slow_period})={slow_sma:.5f}"
            )
        else:
            direction = "short"
            reason = (
                f"SMA Crossover: Fast({self.sma_fast_period})={fast_sma:.5f} < "
                f"Slow({self.sma_slow_period})={slow_sma:.5f}"
            )

        self._log_entry_signal(
            direction,
            reason,
            tick_data,
            {"method": "sma_crossover", "fast_sma": str(fast_sma), "slow_sma": str(slow_sma)},
        )
        return {"direction": direction, "reason": reason}

    def _check_ema_crossover_signal(
        self, prices: list[Decimal], tick_data: TickData
    ) -> dict[str, Any] | None:
        """Check for entry signal using EMA crossover."""
        fast_ema = self._calculate_ema(prices, self.ema_fast_period)
        slow_ema = self._calculate_ema(prices, self.ema_slow_period)

        if fast_ema is None or slow_ema is None:
            return None

        if fast_ema > slow_ema:
            direction = "long"
            reason = (
                f"EMA Crossover: Fast({self.ema_fast_period})={fast_ema:.5f} > "
                f"Slow({self.ema_slow_period})={slow_ema:.5f}"
            )
        else:
            direction = "short"
            reason = (
                f"EMA Crossover: Fast({self.ema_fast_period})={fast_ema:.5f} < "
                f"Slow({self.ema_slow_period})={slow_ema:.5f}"
            )

        self._log_entry_signal(
            direction,
            reason,
            tick_data,
            {"method": "ema_crossover", "fast_ema": str(fast_ema), "slow_ema": str(slow_ema)},
        )
        return {"direction": direction, "reason": reason}

    def _check_price_vs_sma_signal(
        self, prices: list[Decimal], tick_data: TickData
    ) -> dict[str, Any] | None:
        """Check for entry signal using price vs SMA."""
        sma = self._calculate_sma(prices, self.sma_slow_period)

        if sma is None:
            return None

        current_price = prices[-1]

        if current_price > sma:
            direction = "long"
            reason = f"Price vs SMA: {current_price:.5f} > SMA({self.sma_slow_period})={sma:.5f}"
        else:
            direction = "short"
            reason = f"Price vs SMA: {current_price:.5f} < SMA({self.sma_slow_period})={sma:.5f}"

        self._log_entry_signal(
            direction,
            reason,
            tick_data,
            {"method": "price_vs_sma", "price": str(current_price), "sma": str(sma)},
        )
        return {"direction": direction, "reason": reason}

    def _check_rsi_signal(
        self, prices: list[Decimal], tick_data: TickData
    ) -> dict[str, Any] | None:
        """Check for entry signal using RSI."""
        rsi = self._calculate_rsi(prices, self.rsi_period)

        if rsi is None:
            return None

        # RSI strategy: go long when oversold, short when overbought
        # If RSI is in neutral zone, use momentum as tiebreaker
        if rsi < self.rsi_oversold:
            direction = "long"
            reason = f"RSI Oversold: RSI({self.rsi_period})={rsi:.1f} < {self.rsi_oversold}"
        elif rsi > self.rsi_overbought:
            direction = "short"
            reason = f"RSI Overbought: RSI({self.rsi_period})={rsi:.1f} > {self.rsi_overbought}"
        else:
            # Neutral zone - use momentum as tiebreaker
            if len(prices) >= 2:
                momentum = prices[-1] - prices[-2]
                direction = "long" if momentum > 0 else "short"
                reason = f"RSI Neutral: RSI({self.rsi_period})={rsi:.1f}, using momentum"
            else:
                direction = "long"
                reason = f"RSI Neutral: RSI({self.rsi_period})={rsi:.1f}, defaulting to long"

        self._log_entry_signal(direction, reason, tick_data, {"method": "rsi", "rsi": str(rsi)})
        return {"direction": direction, "reason": reason}

    def _log_entry_signal(
        self, direction: str, reason: str, tick_data: TickData, extra_details: dict[str, Any]
    ) -> None:
        """Log entry signal event."""
        self.log_strategy_event(
            "entry_signal_triggered",
            f"{direction.upper()} entry: {reason}",
            {
                "direction": direction,
                "reason": reason,
                "instrument": tick_data.instrument,
                "price": str(tick_data.mid),
                **extra_details,
            },
        )

    # ==================== OHLC-based Direction Methods ====================

    def _update_ohlc_candle(self, tick_data: TickData) -> None:
        """
        Update OHLC candle data from tick.

        Aggregates tick data into OHLC candles based on configured granularity.
        """
        instrument = tick_data.instrument
        timestamp = tick_data.timestamp.timestamp()
        price = tick_data.mid

        # Calculate candle start time based on granularity
        candle_start = int(timestamp // self.ohlc_granularity) * self.ohlc_granularity

        # Initialize storage if needed
        if instrument not in self._ohlc_candles:
            self._ohlc_candles[instrument] = []
        if instrument not in self._current_candle:
            self._current_candle[instrument] = None

        current = self._current_candle[instrument]

        # Check if we need to start a new candle
        if current is None or current["time"] != candle_start:
            # Save completed candle
            if current is not None:
                self._ohlc_candles[instrument].append(current)
                # Keep only enough candles for analysis
                max_candles = max(self.ohlc_fast_period, self.ohlc_slow_period) + 10
                if len(self._ohlc_candles[instrument]) > max_candles:
                    self._ohlc_candles[instrument] = self._ohlc_candles[instrument][-max_candles:]

            # Start new candle
            self._current_candle[instrument] = {
                "time": candle_start,
                "open": price,
                "high": price,
                "low": price,
                "close": price,
            }
        else:
            # Update current candle
            current["high"] = max(current["high"], price)
            current["low"] = min(current["low"], price)
            current["close"] = price

    def _get_ohlc_closes(self, instrument: str) -> list[Decimal]:
        """Get list of close prices from completed OHLC candles."""
        candles = self._ohlc_candles.get(instrument, [])
        return [c["close"] for c in candles]

    def _check_ohlc_sma_crossover_signal(self, tick_data: TickData) -> dict[str, Any] | None:
        """
        Check for entry signal using OHLC-based SMA crossover.

        Uses completed candles (hourly/daily) for longer-term trend analysis.
        """
        # Update candle data
        self._update_ohlc_candle(tick_data)

        # Get close prices from completed candles
        closes = self._get_ohlc_closes(tick_data.instrument)

        # Need enough candles for slow period
        if len(closes) < self.ohlc_slow_period:
            return None

        fast_sma = self._calculate_sma(closes, self.ohlc_fast_period)
        slow_sma = self._calculate_sma(closes, self.ohlc_slow_period)

        if fast_sma is None or slow_sma is None:
            return None

        granularity_name = self._get_granularity_name()

        if fast_sma > slow_sma:
            direction = "long"
            reason = (
                f"OHLC SMA Crossover ({granularity_name}): "
                f"Fast({self.ohlc_fast_period})={fast_sma:.5f} > "
                f"Slow({self.ohlc_slow_period})={slow_sma:.5f}"
            )
        else:
            direction = "short"
            reason = (
                f"OHLC SMA Crossover ({granularity_name}): "
                f"Fast({self.ohlc_fast_period})={fast_sma:.5f} < "
                f"Slow({self.ohlc_slow_period})={slow_sma:.5f}"
            )

        self._log_entry_signal(
            direction,
            reason,
            tick_data,
            {
                "method": "ohlc_sma_crossover",
                "granularity": granularity_name,
                "fast_sma": str(fast_sma),
                "slow_sma": str(slow_sma),
                "candles_count": len(closes),
            },
        )
        return {"direction": direction, "reason": reason}

    def _check_ohlc_ema_crossover_signal(self, tick_data: TickData) -> dict[str, Any] | None:
        """
        Check for entry signal using OHLC-based EMA crossover.

        Uses completed candles (hourly/daily) for longer-term trend analysis.
        """
        # Update candle data
        self._update_ohlc_candle(tick_data)

        # Get close prices from completed candles
        closes = self._get_ohlc_closes(tick_data.instrument)

        # Need enough candles for slow period
        if len(closes) < self.ohlc_slow_period:
            return None

        fast_ema = self._calculate_ema(closes, self.ohlc_fast_period)
        slow_ema = self._calculate_ema(closes, self.ohlc_slow_period)

        if fast_ema is None or slow_ema is None:
            return None

        granularity_name = self._get_granularity_name()

        if fast_ema > slow_ema:
            direction = "long"
            reason = (
                f"OHLC EMA Crossover ({granularity_name}): "
                f"Fast({self.ohlc_fast_period})={fast_ema:.5f} > "
                f"Slow({self.ohlc_slow_period})={slow_ema:.5f}"
            )
        else:
            direction = "short"
            reason = (
                f"OHLC EMA Crossover ({granularity_name}): "
                f"Fast({self.ohlc_fast_period})={fast_ema:.5f} < "
                f"Slow({self.ohlc_slow_period})={slow_ema:.5f}"
            )

        self._log_entry_signal(
            direction,
            reason,
            tick_data,
            {
                "method": "ohlc_ema_crossover",
                "granularity": granularity_name,
                "fast_ema": str(fast_ema),
                "slow_ema": str(slow_ema),
                "candles_count": len(closes),
            },
        )
        return {"direction": direction, "reason": reason}

    def _check_ohlc_price_vs_sma_signal(self, tick_data: TickData) -> dict[str, Any] | None:
        """
        Check for entry signal using current price vs OHLC-based SMA.

        Compares current tick price against longer-term moving average.
        """
        # Update candle data
        self._update_ohlc_candle(tick_data)

        # Get close prices from completed candles
        closes = self._get_ohlc_closes(tick_data.instrument)

        # Need enough candles for slow period
        if len(closes) < self.ohlc_slow_period:
            return None

        sma = self._calculate_sma(closes, self.ohlc_slow_period)

        if sma is None:
            return None

        current_price = tick_data.mid
        granularity_name = self._get_granularity_name()

        if current_price > sma:
            direction = "long"
            reason = (
                f"Price vs OHLC SMA ({granularity_name}): "
                f"{current_price:.5f} > SMA({self.ohlc_slow_period})={sma:.5f}"
            )
        else:
            direction = "short"
            reason = (
                f"Price vs OHLC SMA ({granularity_name}): "
                f"{current_price:.5f} < SMA({self.ohlc_slow_period})={sma:.5f}"
            )

        self._log_entry_signal(
            direction,
            reason,
            tick_data,
            {
                "method": "ohlc_price_vs_sma",
                "granularity": granularity_name,
                "price": str(current_price),
                "sma": str(sma),
                "candles_count": len(closes),
            },
        )
        return {"direction": direction, "reason": reason}

    def _get_granularity_name(self) -> str:
        """Get human-readable name for the configured OHLC granularity."""
        granularity_names = {
            300: "M5",
            900: "M15",
            1800: "M30",
            3600: "H1",
            7200: "H2",
            14400: "H4",
            28800: "H8",
            43200: "H12",
            86400: "D1",
            604800: "W1",
        }
        return granularity_names.get(self.ohlc_granularity, f"{self.ohlc_granularity}s")

    # ==================== End OHLC-based Direction Methods ====================

    def _process_layer(self, layer: Layer, tick_data: TickData) -> list[Order]:
        """
        Process a single layer.

        Args:
            layer: Layer to process
            tick_data: Current tick data

        Returns:
            List of orders to execute
        """
        empty_state_orders = self._handle_empty_layer(layer, tick_data)
        if empty_state_orders is not None:
            return empty_state_orders

        logger.debug(
            "Layer %s has %s positions, checking for Step 2 / scaling / TP",
            layer.layer_number,
            len(layer.positions),
        )

        # Check for take-profit on ALL positions (including initial lot)
        tp_orders = self._check_take_profit(layer, tick_data)
        if tp_orders:
            return tp_orders

        return self._handle_retracement_scaling(layer, tick_data)

    def _handle_empty_layer(self, layer: Layer, tick_data: TickData) -> list[Order] | None:
        """Handle initial-entry creation or pending state for empty layers."""
        if layer.positions:
            return None

        if not layer.has_pending_initial_entry:
            logger.debug(
                "Layer %s has no positions (count=%s), creating initial entry at %s",
                layer.layer_number,
                len(layer.positions),
                tick_data.timestamp,
            )
            order = self._create_initial_entry_order(layer, tick_data)
            if not order:
                return []

            layer.has_pending_initial_entry = True
            self.log_strategy_event(
                "order_created",
                f"Created order for layer {layer.layer_number}",
                {
                    "order_id": order.order_id,
                    "direction": order.direction,
                    "units": str(order.units),
                    "price": str(order.price),
                    "layer": layer.layer_number,
                    "retracement_count": layer.retracement_count,
                    "max_retracements": layer.max_retracements_per_layer,
                },
            )
            return [order]

        logger.debug(
            "Layer %s waiting for pending initial entry to execute",
            layer.layer_number,
        )
        return []

    def _handle_retracement_scaling(self, layer: Layer, tick_data: TickData) -> list[Order]:
        """Handle retracement math and scale-in order creation."""
        if not (layer.last_entry_price and layer.peak_price is not None and layer.positions):
            return []

        direction = layer.positions[0].direction

        # CRITICAL: Use bid/ask prices, not mid, to match position entry prices
        # Long positions use ASK (buy price), Short positions use BID (sell price)
        current_price = tick_data.ask if direction == "long" else tick_data.bid

        # Log current state for debugging (only first few times)
        if layer.retracement_count < 3:
            logger.debug(
                "Layer %s: peak=%s, current=%s, direction=%s, has_scaled=%s",
                layer.layer_number,
                layer.peak_price,
                current_price,
                direction,
                layer.has_scaled_at_current_level,
            )

        # Update peak price based on direction (most favorable price seen)
        if (direction == "long" and current_price > layer.peak_price) or (
            direction == "short" and current_price < layer.peak_price
        ):
            layer.peak_price = current_price
            layer.has_scaled_at_current_level = False  # Reset flag at new peak

        # Check if price has RETRACED from peak (moved against us)
        # Prevent scaling multiple times in the same tick
        tick_id = f"{tick_data.timestamp.timestamp()}_{current_price}"

        # Calculate retracement: how far price moved AGAINST us from peak
        # IMPORTANT: We need SIGNED difference, not absolute value from calculate_pips
        # JPY pairs: 1 pip = 0.01, other pairs: 1 pip = 0.0001
        pip_size = Decimal("0.01") if "JPY" in tick_data.instrument else Decimal("0.0001")

        if direction == "long":
            # Long: retracement is when price drops from peak (negative movement)
            # We want positive pips when price drops, so: peak - current
            retracement_pips = (layer.peak_price - current_price) / pip_size
        else:  # short
            # Short: retracement is when price rises from peak (positive movement)
            # We want positive pips when price rises, so: current - peak
            retracement_pips = (current_price - layer.peak_price) / pip_size

        # FIX: When we've already scaled and price continues moving against us by another
        # retracement threshold, reset the flag and update peak to allow another scale.
        # This enables continuous scaling as price keeps moving unfavorably.
        if layer.has_scaled_at_current_level and retracement_pips >= self.retracement_pips:
            # Update peak to current price so next retracement is measured from here
            layer.peak_price = current_price
            layer.has_scaled_at_current_level = False

        # Check if we should scale (either first time or after reset above)
        # Conditions: not already scaled, different tick, positive retracement >= threshold
        should_scale = (
            not layer.has_scaled_at_current_level
            and layer.last_scale_tick_id != tick_id
            and retracement_pips > 0
            and retracement_pips >= self.retracement_pips
        )
        if not should_scale:
            return []

        if not layer.has_retracement_capacity():
            self.log_strategy_event(
                "retracement_limit_reached",
                (
                    f"Layer {layer.layer_number} reached max retracements "
                    f"({layer.max_retracements_per_layer}) — waiting for closures"
                ),
                {
                    "layer": layer.layer_number,
                    "direction": direction,
                    "retracement_count": layer.retracement_count,
                    "max_retracements": layer.max_retracements_per_layer,
                    "event_type": "layer",
                    "timestamp": tick_data.timestamp.isoformat(),
                },
            )
            layer.last_scale_tick_id = tick_id
            return []

        retracement_msg = (
            f"[RETRACEMENT DETECTED] Layer {layer.layer_number} | "
            f"{direction.upper()} position | "
            f"Price moved from peak {layer.peak_price} to {current_price} | "
            f"Retracement: {retracement_pips:.1f} pips "
            f"(Threshold: {self.retracement_pips} pips) | "
            f"Preparing to retracement"
        )
        logger.info(retracement_msg)

        retracement_detail = (
            f"Retracement: {retracement_pips:.1f} pips "
            f"from peak {layer.peak_price} to {current_price}"
        )
        self.log_strategy_event(
            "retracement_detected",
            retracement_detail,
            {
                "layer": layer.layer_number,
                "direction": direction,
                "peak_price": str(layer.peak_price),
                "current_price": str(current_price),
                "retracement_pips": str(retracement_pips),
                "threshold_pips": str(self.retracement_pips),
                "event_type": "layer",
                "timestamp": tick_data.timestamp.isoformat(),
                "retracement_count": layer.retracement_count,
                "max_retracements": layer.max_retracements_per_layer,
            },
        )

        scale_order = self._create_scale_order(layer, tick_data)
        if not scale_order:
            return []

        layer.increment_retracement_count()
        layer.has_scaled_at_current_level = True
        layer.last_scale_tick_id = tick_id
        return [scale_order]

    def _sync_layer_lot_size(self, layer: Layer) -> None:
        """Recalculate the layer's current lot size based on retracement depth."""
        recalculated_size = layer.base_lot_size
        if layer.retracement_count == 0:
            layer.current_lot_size = recalculated_size
            return

        for _ in range(layer.retracement_count):
            recalculated_size = self.scaling_engine.calculate_next_lot_size(recalculated_size)

        layer.current_lot_size = recalculated_size

    def _create_initial_entry_order(self, layer: Layer, tick_data: TickData) -> Order | None:
        """
        Create initial entry order for a layer.

        Args:
            layer: Layer to create entry for
            tick_data: Current tick data

        Returns:
            Order instance or None
        """
        # Determine entry signal and direction
        entry_signal = self._check_entry_signal(tick_data)
        if not entry_signal:
            # Log why we're not entering (only first few times to avoid spam)
            if self._no_signal_log_count < 3:
                history_len = 0
                if tick_data.instrument in self._price_history:
                    history_len = len(self._price_history[tick_data.instrument])
                required = self.entry_signal_lookback_ticks
                msg = f"No entry signal yet - need {required} ticks, " f"have {history_len}"
                self.log_strategy_event(
                    "no_entry_signal",
                    msg,
                    {
                        "layer": layer.layer_number,
                        "history_length": history_len,
                        "required_ticks": required,
                        "retracement_count": layer.retracement_count,
                        "max_retracements": layer.max_retracements_per_layer,
                    },
                )
                self._no_signal_log_count += 1
            return None

        direction = entry_signal["direction"]

        # IMPORTANT: Only create initial entry if layer truly has no positions
        # This prevents creating opposite direction positions
        if layer.positions:
            logger.warning(
                "Layer %s already has %s positions, skipping initial entry",
                layer.layer_number,
                len(layer.positions),
            )
            return None

        # Prevent creating multiple initial entries in the same tick
        # Use a unique tick ID (timestamp + price) to handle sub-second ticks
        tick_id = f"{tick_data.timestamp.timestamp()}_{tick_data.mid}"
        if layer.last_initial_entry_tick_id == tick_id:
            logger.warning(
                "Layer %s already created initial entry for tick %s, skipping duplicate",
                layer.layer_number,
                tick_id,
            )
            return None

        # Reset retracement counter for new initial entry (Requirements 6.1, 6.3, 6.4)
        layer.reset_retracement_count()

        # Reset unit size to base_lot_size for new initial entry (Requirements 7.1, 7.4)
        layer.reset_unit_size()

        # Store direction in layer for subsequent retracements (Requirements 8.1, 8.2, 8.3)
        layer.direction = direction

        # Use bid/ask for order price
        order_price = tick_data.ask if direction == "long" else tick_data.bid

        order = Order(
            account=self.account,
            strategy=self.strategy,
            order_id=f"floor_{layer.layer_number}_{tick_data.timestamp.timestamp()}",
            instrument=tick_data.instrument,
            order_type="market",
            direction=direction,
            units=self.base_lot_size,
            price=tick_data.mid,
        )
        # Add layer metadata for backtest engine
        order.layer_number = layer.layer_number  # type: ignore[attr-defined]
        order.is_first_lot = True  # type: ignore[attr-defined]

        # Mark tick ID to prevent duplicates
        layer.last_initial_entry_tick_id = tick_id

        initial_entry_msg = (
            f"[INITIAL ENTRY] Layer {layer.layer_number} | "
            f"Opening {direction.upper()} position | "
            f"Size: {self.base_lot_size} units @ {order_price} | "
            f"Signal: {entry_signal.get('reason', 'N/A')}"
        )
        logger.info(initial_entry_msg)

        entry_log_msg = (
            f"Initial entry: {direction.upper()} {self.base_lot_size} units " f"@ {order_price}"
        )
        self.log_strategy_event(
            "initial_entry",
            entry_log_msg,
            {
                "layer": layer.layer_number,
                "instrument": tick_data.instrument,
                "direction": direction,
                "units": str(self.base_lot_size),
                "price": str(order_price),
                "signal": entry_signal.get("reason", ""),
                "event_type": "initial",
                "timestamp": tick_data.timestamp.isoformat(),
                "retracement_count": 0,
                "max_retracements": layer.max_retracements_per_layer,
            },
        )

        return order

    def _create_scale_order(self, layer: Layer, tick_data: TickData) -> Order | None:
        """
        Create scaling order for a layer (Step 3+: retracement scaling).
        These positions will be checked for 25-pip take-profit by _check_take_profit().

        Args:
            layer: Layer to scale
            tick_data: Current tick data

        Returns:
            Order instance or None
        """
        next_lot_size = self.scaling_engine.calculate_next_lot_size(layer.current_lot_size)
        layer.current_lot_size = next_lot_size

        # Get direction from layer (Requirements 8.3)
        # Direction is set during initial entry and should not be recalculated for retracements
        if not layer.direction:
            # Fallback to getting from positions if direction not set
            if not layer.positions:
                return None
            direction = layer.positions[0].direction
        else:
            direction = layer.direction

        # NOTE: We do NOT set take_profit on the order
        # The strategy's _check_take_profit() method will handle closing at 25 pips
        # Use bid/ask for order price
        order_price = tick_data.ask if direction == "long" else tick_data.bid

        order = Order(
            account=self.account,
            strategy=self.strategy,
            order_id=f"floor_scale_{layer.layer_number}_{tick_data.timestamp.timestamp()}",
            instrument=tick_data.instrument,
            order_type="market",
            direction=direction,
            units=next_lot_size,
            price=tick_data.mid,
            # take_profit=None - let strategy handle it
        )
        # Add layer metadata for backtest engine
        order.layer_number = layer.layer_number  # type: ignore[attr-defined]
        order.is_first_lot = False  # type: ignore[attr-defined]

        scale_in_msg = (
            f"[RETRACEMENT] Layer {layer.layer_number} | "
            f"Adding {direction.upper()} position | "
            f"Size: {next_lot_size} units @ {order_price} | "
            f"Peak: {layer.peak_price} | "
            f"Retracement #{layer.retracement_count + 1}"
        )
        logger.info(scale_in_msg)

        scale_log_msg = (
            f"Retracement: {direction.upper()} {next_lot_size} units @ {order_price} "
            f"(Retracement #{layer.retracement_count + 1})"
        )
        self.log_strategy_event(
            "scale_in",
            scale_log_msg,
            {
                "layer": layer.layer_number,
                "instrument": tick_data.instrument,
                "direction": direction,
                "units": str(next_lot_size),
                "price": str(order_price),
                "peak_price": str(layer.peak_price),
                "retracement_count": layer.retracement_count + 1,
                "max_retracements": layer.max_retracements_per_layer,
                "event_type": "retracement",
                "timestamp": tick_data.timestamp.isoformat(),
            },
        )

        return order

    def _check_take_profit(self, layer: Layer, tick_data: TickData) -> list[Order]:
        """
        Check if take-profit should be triggered for all positions.

        Args:
            layer: Layer to check
            tick_data: Current tick data

        Returns:
            List of close orders
        """
        orders: list[Order] = []

        for position in layer.positions:
            if self._should_take_profit(position, tick_data):
                # Log before creating order
                current_price = tick_data.bid if position.direction == "long" else tick_data.ask
                pip_movement = self.calculate_pips(
                    position.entry_price, current_price, position.instrument
                )

                is_first_lot = position == layer.first_lot_position
                position_type = "INITIAL" if is_first_lot else "SCALED"

                tp_msg = (
                    f"[TAKE PROFIT] Layer {layer.layer_number} | "
                    f"Closing {position_type} {position.direction.upper()} position | "
                    f"Size: {position.units} units | "
                    f"Entry: {position.entry_price} → Exit: {current_price} | "
                    f"Profit: +{pip_movement:.1f} pips "
                    f"(Target: {self.take_profit_pips} pips)"
                )
                logger.info(tp_msg)

                close_order = self._create_close_order(position, tick_data, reason="strategy_close")
                if close_order:
                    orders.append(close_order)

        return orders

    def _should_take_profit(self, position: Position, tick_data: TickData) -> bool:
        """
        Check if position should take profit.

        Args:
            position: Position to check
            tick_data: Current tick data

        Returns:
            True if should take profit
        """
        # Use bid/ask prices consistently
        # Long closes at BID (sell price), Short closes at ASK (buy price)
        current_price = tick_data.bid if position.direction == "long" else tick_data.ask

        pip_movement = self.calculate_pips(position.entry_price, current_price, position.instrument)

        if position.direction == "long":
            return current_price > position.entry_price and pip_movement >= self.take_profit_pips
        # short
        return current_price < position.entry_price and pip_movement >= self.take_profit_pips

    def _create_close_order(
        self, position: Position, tick_data: TickData, reason: str = "take_profit"
    ) -> Order | None:
        """
        Create order to close a position.

        Args:
            position: Position to close
            tick_data: Current tick data
            reason: Reason for closing (strategy_close, take_profit, volatility_lock,
                   margin_protection, etc.)

        Returns:
            Close order or None
        """
        # Create close order
        order = Order(
            account=self.account,
            strategy=self.strategy,
            order_id=f"floor_close_{position.position_id}_{tick_data.timestamp.timestamp()}",
            instrument=position.instrument,
            order_type="market",
            direction="short" if position.direction == "long" else "long",
            units=position.units,
            price=tick_data.mid,
        )
        order.layer_number = getattr(position, "layer_number", None)  # type: ignore[attr-defined]
        order.is_first_lot = False  # type: ignore[attr-defined]

        # Calculate pip metrics
        is_jpy = "JPY" in position.instrument
        pip_size = Decimal("0.01") if is_jpy else Decimal("0.0001")
        price_diff = tick_data.mid - position.entry_price
        if position.direction == "short":
            price_diff = -price_diff
        pip_diff = float(price_diff / pip_size)

        # Calculate P&L in USD (matching backtest_engine.py calculation)
        # units represents lot size (1.0 = 1 lot = 1,000 base currency units)
        base_currency_amount = position.units * Decimal("1000")
        pnl_raw = price_diff * base_currency_amount

        # For JPY pairs, P&L is in JPY and needs conversion to USD
        if is_jpy:
            pnl = float(pnl_raw / tick_data.mid)
        else:
            pnl = float(pnl_raw)

        # Get event metadata
        event_type, reason_display = self._get_close_event_metadata(reason)
        layer = self.layer_manager.get_layer(getattr(position, "layer_number", 0))

        # Log close event
        self.log_strategy_event(
            reason,
            f"Closing position: {position.direction.upper()} {position.units} units | "
            f"{pip_diff:+.1f} pips | {reason_display}",
            {
                "position_id": position.position_id,
                "instrument": position.instrument,
                "direction": position.direction,
                "entry_price": str(position.entry_price),
                "exit_price": str(tick_data.mid),
                "units": str(position.units),
                "pip_diff": pip_diff,
                "pnl": pnl,
                "reason": reason,
                "reason_display": reason_display,
                "event_type": event_type,
                "timestamp": tick_data.timestamp.isoformat(),
                "layer_number": getattr(position, "layer_number", None),
                "retracement_count": layer.retracement_count if layer else None,
                "max_retracements": layer.max_retracements_per_layer if layer else None,
            },
        )

        return order

    def _get_close_event_metadata(self, reason: str) -> tuple[str, str]:
        """
        Get event_type and display name for close reason.

        Args:
            reason: Close reason

        Returns:
            Tuple of (event_type, reason_display)
        """
        reason_to_event_type = {
            "strategy_close": "close",
            "take_profit": "take_profit",
            "stop_loss": "close",
            "volatility_lock": "volatility_lock",
            "margin_protection": "margin_protection",
        }
        reason_to_display = {
            "strategy_close": "Take Profit",
            "take_profit": "Take Profit",
            "stop_loss": "Stop Loss",
            "volatility_lock": "Volatility Lock",
            "margin_protection": "Margin Protection",
        }
        event_type = reason_to_event_type.get(reason, "close")
        reason_display = reason_to_display.get(reason, reason.replace("_", " ").title())
        return event_type, reason_display

    def _calculate_take_profit_price(
        self, entry_price: Decimal, direction: str, tp_pips: Decimal
    ) -> Decimal:
        """
        Calculate take-profit price.

        Args:
            entry_price: Entry price
            direction: Position direction
            tp_pips: Take-profit in pips

        Returns:
            Take-profit price
        """
        pip_value = Decimal("0.0001")  # Standard pip value
        pip_offset = tp_pips * pip_value

        if direction == "long":
            return entry_price + pip_offset
        # short
        return entry_price - pip_offset

    def _check_volatility_lock(self, tick_data: TickData) -> bool:
        """
        Check if volatility lock should be triggered.

        Args:
            tick_data: Current tick data

        Returns:
            True if volatility lock should be triggered
        """
        # Get current ATR from state
        state = self.get_strategy_state()
        atr_values = state.get("atr_values", {})
        current_atr_str = atr_values.get(tick_data.instrument)

        if not current_atr_str or not self.normal_atr:
            return False

        current_atr = Decimal(current_atr_str)
        threshold = self.normal_atr * self.volatility_lock_multiplier

        return current_atr >= threshold

    def _execute_volatility_lock(self) -> None:
        """
        Execute volatility lock: close all positions and pause trading.

        Requirements: 13.4
        """
        self.is_locked = True

        self.log_strategy_event(
            "volatility_lock",
            "Volatility lock triggered - closing all positions",
            {
                "normal_atr": str(self.normal_atr) if self.normal_atr else None,
                "multiplier": str(self.volatility_lock_multiplier),
                "event_type": "volatility_lock",
            },
        )

        # In production, this would close all positions at break-even
        # For now, we just mark the strategy as locked
        # The actual position closing would be handled by the order executor

    def _check_margin_liquidation(self) -> bool:
        """
        Check if margin-liquidation ratio has reached 100% or more.

        Returns:
            True if margin protection should be triggered
        """
        # Get account margin data
        # Refresh from database to get latest values
        if not self.account:
            return False

        self.account.refresh_from_db()
        margin_used = self.account.margin_used
        unrealized_pnl = self.account.unrealized_pnl

        if margin_used == 0:
            return False

        # Margin-liquidation ratio = (Margin + Unrealized P&L) / Margin
        # When this reaches 0 or below (100% of margin consumed), trigger liquidation
        margin_liquidation_ratio = (margin_used + unrealized_pnl) / margin_used
        return margin_liquidation_ratio <= Decimal("0.0")

    def _execute_margin_protection(self) -> list[Order]:
        """
        Execute margin protection: liquidate first lot of first layer.

        Returns:
            List of liquidation orders

        Requirements: 13.4
        """
        orders: list[Order] = []

        first_lots = self.layer_manager.get_first_lot_positions()
        if not first_lots:
            return orders

        # Liquidate first lot of first layer
        first_lot = first_lots[0]
        first_lot_layer = self.layer_manager.get_layer(getattr(first_lot, "layer_number", 0))

        # Create close order
        close_direction = "short" if first_lot.direction == "long" else "long"

        order = Order(
            account=self.account,
            strategy=self.strategy,
            order_id=f"floor_margin_protection_{first_lot.position_id}",
            instrument=first_lot.instrument,
            order_type="market",
            direction=close_direction,
            units=first_lot.units,
            price=first_lot.current_price,
        )
        # Add layer metadata for backtest engine
        order.layer_number = getattr(first_lot, "layer_number", None)  # type: ignore[attr-defined]
        order.is_first_lot = False  # type: ignore[attr-defined]

        orders.append(order)

        self.log_strategy_event(
            "margin_protection",
            "Margin protection triggered - liquidating first lot",
            {
                "position_id": first_lot.position_id,
                "layer": first_lot.layer_number,
                "instrument": first_lot.instrument,
                "units": str(first_lot.units),
                "event_type": "margin_protection",
                "retracement_count": (
                    first_lot_layer.retracement_count if first_lot_layer else None
                ),
                "max_retracements": (
                    first_lot_layer.max_retracements_per_layer if first_lot_layer else None
                ),
            },
        )

        return orders

    def _check_new_layer_creation(self) -> None:
        """Check if a new layer should be created based on retracement counts."""
        for layer in self.layer_manager.layers:
            if layer.should_create_new_layer():
                next_layer_num = layer.layer_number + 1
                if next_layer_num <= self.layer_manager.max_layers:
                    # Get layer-specific config from individual parameters
                    layer_config = self._get_layer_config(next_layer_num)

                    new_layer = self.layer_manager.create_layer(next_layer_num, layer_config)
                    if new_layer:
                        # Prevent duplicate auto-advance attempts once the next layer exists
                        if layer.config.get("auto_advance_on_low_trigger"):
                            layer.config["auto_advance_on_low_trigger"] = False
                        self.log_strategy_event(
                            "new_layer_created",
                            f"Created new layer {next_layer_num}",
                            {
                                "layer": next_layer_num,
                                "trigger_layer": layer.layer_number,
                                "retracement_count": layer.retracement_count,
                                "max_retracements": new_layer.max_retracements_per_layer,
                            },
                        )
                        # Save state immediately when creating new layer
                        self._save_state()

    def _get_layer_config(self, layer_num: int) -> dict[str, Any]:
        """
        Get configuration for a specific layer using progression modes.

        Args:
            layer_num: Layer number

        Returns:
            Layer configuration dictionary
        """
        # Calculate retracement trigger based on progression mode
        base_trigger = float(self.max_retracements_per_layer)
        trigger_progression = self.get_config_value("retracement_trigger_progression", "additive")
        trigger_increment = self.get_config_value("retracement_trigger_increment", 5)

        retracement_trigger = self._calculate_progression_value(
            base_value=base_trigger,
            layer_num=layer_num,
            progression_mode=trigger_progression,
            increment=trigger_increment,
        )
        trigger_auto_advance = retracement_trigger < 1
        trigger_threshold = 1 if trigger_auto_advance else int(retracement_trigger)

        # Calculate lot size based on progression mode
        lot_progression = self.get_config_value("lot_size_progression", "additive")
        lot_increment = self.get_config_value("lot_size_increment", 0.5)

        lot_size = self._calculate_progression_value(
            base_value=float(self.base_lot_size),
            layer_num=layer_num,
            progression_mode=lot_progression,
            increment=lot_increment,
        )

        return {
            "retracement_count_trigger": trigger_threshold,
            "auto_advance_on_low_trigger": trigger_auto_advance,
            "base_lot_size": float(lot_size),
            "max_retracements_per_layer": self.max_retracements_per_layer,
        }

    def _calculate_progression_value(
        self,
        base_value: float,
        layer_num: int,
        progression_mode: str,
        increment: float,
    ) -> float:
        """
        Calculate value for a layer based on progression mode.

        Args:
            base_value: Base value for layer 1
            layer_num: Layer number
            progression_mode: Progression mode (equal, additive, exponential, inverse)
            increment: Increment value for additive/exponential modes

        Returns:
            Calculated value for the layer
        """
        if progression_mode == "equal":
            # All layers use the same value
            return base_value

        if progression_mode == "additive":
            # Each layer adds the increment: base, base+inc, base+2*inc
            return base_value + (increment * (layer_num - 1))

        if progression_mode == "exponential":
            # Each layer multiplies by increment: base, base*inc, base*inc^2
            return base_value * (increment ** (layer_num - 1))

        if progression_mode == "inverse":
            # Each layer divides: base, base/2, base/3
            return base_value / layer_num

        # Default to equal if unknown mode
        return base_value

    def on_position_update(self, position: Position) -> None:
        """
        Handle position updates.

        Args:
            position: Position that was updated

        Requirements: 13.1
        """
        update_msg = (
            f"on_position_update called: layer={position.layer_number}, "
            f"is_first={position.is_first_lot}"
        )
        logger.debug(update_msg)
        # Find the layer this position belongs to
        for layer in self.layer_manager.layers:
            if position.layer_number == layer.layer_number:
                # Update layer's position list if needed
                if position not in layer.positions:
                    new_count = len(layer.positions) + 1
                    add_msg = (
                        f"Adding position to layer {layer.layer_number}, "
                        f"now has {new_count} positions"
                    )
                    logger.debug(add_msg)
                    layer.add_position(position, position.is_first_lot)
                    # Save state immediately when position is added (important event)
                    self._save_state()
                else:
                    logger.debug("Position already in layer %s", layer.layer_number)
                break

    def on_position_closed(self, position: Position) -> None:
        """
        Handle position closures - remove position from layer.

        Args:
            position: Position that was closed
        """
        logger.debug(
            "on_position_closed called: layer=%s, position_id=%s",
            position.layer_number,
            position.position_id,
        )
        # Find the layer this position belongs to and remove it
        for layer in self.layer_manager.layers:
            if position.layer_number == layer.layer_number:
                if position in layer.positions:
                    layer.positions.remove(position)
                    remove_msg = (
                        f"Removed position from layer {layer.layer_number}, "
                        f"now has {len(layer.positions)} positions"
                    )
                    logger.debug(remove_msg)
                    # Clear first_lot_position if this was it
                    if layer.first_lot_position == position:
                        layer.first_lot_position = None
                        logger.debug(
                            "Cleared first_lot_position for layer %s",
                            layer.layer_number,
                        )
                    else:
                        # Non-first positions correspond to retracement scaling
                        previous_count = layer.retracement_count
                        layer.decrement_retracement_count()
                        if layer.retracement_count != previous_count:
                            self._sync_layer_lot_size(layer)
                            closed_timestamp = getattr(position, "closed_at", None)
                            event_timestamp = (
                                closed_timestamp.isoformat() if closed_timestamp else None
                            )
                            self.log_strategy_event(
                                "retracement_released",
                                (
                                    f"Layer {layer.layer_number} retracement count decreased to "
                                    f"{layer.retracement_count} after closing scaled position"
                                ),
                                {
                                    "layer": layer.layer_number,
                                    "position_id": position.position_id,
                                    "retracement_count": layer.retracement_count,
                                    "max_retracements": layer.max_retracements_per_layer,
                                    "event_type": "layer",
                                    "timestamp": event_timestamp,
                                },
                            )
                    # Save state immediately when position is removed
                    self._save_state()
                break

    def validate_config(self, config: dict[str, Any]) -> bool:
        """
        Validate strategy configuration.

        Args:
            config: Configuration dictionary

        Returns:
            True if valid

        Raises:
            ValueError: If configuration is invalid

        Requirements: 13.1
        """
        required_keys = [
            "base_lot_size",
            "scaling_mode",
            "retracement_pips",
            "take_profit_pips",
        ]

        for key in required_keys:
            if key not in config:
                raise ValueError(f"Required configuration key '{key}' not found")

        # Validate scaling mode
        scaling_mode = config.get("scaling_mode")
        if scaling_mode not in ["additive", "multiplicative"]:
            error_msg = (
                f"Invalid scaling_mode: {scaling_mode}. " f"Must be 'additive' or 'multiplicative'"
            )
            raise ValueError(error_msg)

        # Validate numeric values
        numeric_keys = [
            "base_lot_size",
            "retracement_pips",
            "take_profit_pips",
        ]
        for key in numeric_keys:
            value = config.get(key)
            if value is not None:
                try:
                    float_value = float(value)
                except (TypeError, ValueError) as exc:
                    raise ValueError(f"Invalid {key}: {value}") from exc

                if float_value <= 0:
                    raise ValueError(f"{key} must be positive")

        # Validate max_layers
        max_layers = config.get("max_layers", 3)
        if not isinstance(max_layers, int) or max_layers < 1:
            raise ValueError("max_layers must be a positive integer")

        max_retracements = config.get("max_retracements_per_layer", 10)
        if not isinstance(max_retracements, int) or max_retracements < 1:
            raise ValueError("max_retracements_per_layer must be a positive integer")

        # Validate progression modes
        valid_progressions = ["equal", "additive", "exponential", "inverse"]
        retracement_progression = config.get("retracement_trigger_progression", "additive")
        if retracement_progression not in valid_progressions:
            error_msg = (
                f"Invalid retracement_trigger_progression: {retracement_progression}. "
                f"Must be one of {valid_progressions}"
            )
            raise ValueError(error_msg)

        lot_progression = config.get("lot_size_progression", "additive")
        if lot_progression not in valid_progressions:
            error_msg = (
                f"Invalid lot_size_progression: {lot_progression}. "
                f"Must be one of {valid_progressions}"
            )
            raise ValueError(error_msg)

        return True

    def finalize(self) -> None:
        """
        Finalize strategy execution and save final state.

        This method should be called at the end of backtest or trading session
        to ensure all state is persisted.
        """
        self._save_state()


# Configuration schema for Floor Strategy
FLOOR_STRATEGY_CONFIG_SCHEMA = {
    "type": "object",
    "title": "Floor Strategy Configuration",
    "description": (
        "Configuration for the Floor Strategy with dynamic scaling " "and ATR-based volatility lock"
    ),
    "properties": {
        "base_lot_size": {
            "type": "number",
            "title": "Base Lot Size",
            "description": (
                "Initial lot size for first entry. "
                "1 lot = 1,000 units of base currency. "
                "For USD/JPY: 1.0 = 1,000 USD"
            ),
            "default": 1.0,
            "minimum": 0.01,
        },
        "scaling_mode": {
            "type": "string",
            "title": "Scaling Mode",
            "description": "Mode for scaling position size on retracements",
            "enum": ["additive", "multiplicative"],
            "default": "additive",
        },
        "scaling_amount": {
            "type": "number",
            "title": "Scaling Amount",
            "description": (
                "Amount to add (additive) or multiply by (multiplicative) " "on each retracement"
            ),
            "default": 1.0,
            "minimum": 0.01,
        },
        "retracement_pips": {
            "type": "number",
            "title": "Retracement Pips",
            "description": ("Number of pips retracement required to trigger scaling"),
            "default": 30,
            "minimum": 1,
        },
        "take_profit_pips": {
            "type": "number",
            "title": "Take Profit Pips",
            "description": "Number of pips profit to trigger position close for all positions",
            "default": 25,
            "minimum": 1,
        },
        "max_layers": {
            "type": "integer",
            "title": "Maximum Layers",
            "description": "Maximum number of concurrent layers",
            "default": 3,
            "minimum": 1,
            "maximum": 3,
        },
        "max_retracements_per_layer": {
            "type": "integer",
            "title": "Max Retracements Per Layer",
            "description": (
                "Upper bound on how many retracement scale-ins a layer can perform before "
                "requiring positions to close or the layer to reset. Hitting this limit now "
                "also unlocks the next layer if one is available."
            ),
            "default": 10,
            "minimum": 1,
        },
        "volatility_lock_multiplier": {
            "type": "number",
            "title": "Volatility Lock Multiplier",
            "description": (
                "ATR multiplier to trigger volatility lock " "(e.g., 5.0 = 5x normal ATR)"
            ),
            "default": 5.0,
            "minimum": 1.0,
        },
        "retracement_trigger_progression": {
            "type": "string",
            "title": "Retracement Trigger Progression",
            "description": "How retracement triggers progress across layers",
            "enum": ["equal", "additive", "exponential", "inverse"],
            "default": "additive",
        },
        "retracement_trigger_increment": {
            "type": "number",
            "title": "Retracement Trigger Increment",
            "description": (
                "Value to add (additive) or multiply by (exponential). "
                "Not used for equal/inverse"
            ),
            "default": 5,
            "minimum": 0,
            "dependsOn": {
                "field": "retracement_trigger_progression",
                "values": ["additive", "exponential"],
            },
        },
        "lot_size_progression": {
            "type": "string",
            "title": "Lot Size Progression",
            "description": "How lot sizes progress across layers",
            "enum": ["equal", "additive", "exponential", "inverse"],
            "default": "additive",
        },
        "lot_size_increment": {
            "type": "number",
            "title": "Lot Size Increment",
            "description": (
                "Value to add (additive) or multiply by (exponential). "
                "Not used for equal/inverse"
            ),
            "default": 0.5,
            "minimum": 0,
            "dependsOn": {
                "field": "lot_size_progression",
                "values": ["additive", "exponential"],
            },
        },
        "entry_signal_lookback_ticks": {
            "type": "integer",
            "title": "Initial Entry: Lookback Ticks",
            "description": (
                "Number of ticks to analyze for determining entry direction "
                "(Step 1: 'quick technical check'). "
                "Analyzes momentum over this period to decide long vs short. "
                "Per spec: 'Any price level is acceptable' - "
                "we always enter after this many ticks."
            ),
            "default": 10,
            "minimum": 5,
            "maximum": 100,
        },
        "direction_method": {
            "type": "string",
            "title": "Direction Decision Method",
            "description": (
                "Technical analysis method used to determine trade direction. "
                "Tick-based methods use raw tick data. "
                "OHLC methods aggregate ticks into candles for longer-term analysis."
            ),
            "enum": [
                "momentum",
                "sma_crossover",
                "ema_crossover",
                "price_vs_sma",
                "rsi",
                "ohlc_sma_crossover",
                "ohlc_ema_crossover",
                "ohlc_price_vs_sma",
            ],
            "default": "momentum",
        },
        "ohlc_granularity": {
            "type": "integer",
            "title": "OHLC Candle Granularity",
            "description": (
                "Candle period in seconds for OHLC-based methods. "
                "Common values: 3600 (1 hour), 14400 (4 hours), 86400 (1 day)."
            ),
            "enum": [300, 900, 1800, 3600, 7200, 14400, 28800, 43200, 86400, 604800],
            "default": 3600,
        },
        "ohlc_fast_period": {
            "type": "integer",
            "title": "OHLC Fast MA Period",
            "description": "Number of candles for fast moving average in OHLC methods.",
            "default": 10,
            "minimum": 2,
            "maximum": 100,
        },
        "ohlc_slow_period": {
            "type": "integer",
            "title": "OHLC Slow MA Period",
            "description": "Number of candles for slow moving average in OHLC methods.",
            "default": 20,
            "minimum": 5,
            "maximum": 200,
        },
        "sma_fast_period": {
            "type": "integer",
            "title": "SMA Fast Period",
            "description": (
                "Period for fast Simple Moving Average (in ticks). "
                "Used by sma_crossover and price_vs_sma methods."
            ),
            "default": 10,
            "minimum": 2,
            "maximum": 200,
        },
        "sma_slow_period": {
            "type": "integer",
            "title": "SMA Slow Period",
            "description": (
                "Period for slow Simple Moving Average (in ticks). "
                "Used by sma_crossover and price_vs_sma methods."
            ),
            "default": 30,
            "minimum": 5,
            "maximum": 500,
        },
        "ema_fast_period": {
            "type": "integer",
            "title": "EMA Fast Period",
            "description": (
                "Period for fast Exponential Moving Average (in ticks). "
                "Used by ema_crossover method."
            ),
            "default": 12,
            "minimum": 2,
            "maximum": 200,
        },
        "ema_slow_period": {
            "type": "integer",
            "title": "EMA Slow Period",
            "description": (
                "Period for slow Exponential Moving Average (in ticks). "
                "Used by ema_crossover method."
            ),
            "default": 26,
            "minimum": 5,
            "maximum": 500,
        },
        "rsi_period": {
            "type": "integer",
            "title": "RSI Period",
            "description": (
                "Period for Relative Strength Index calculation (in ticks). " "Used by rsi method."
            ),
            "default": 14,
            "minimum": 2,
            "maximum": 100,
        },
        "rsi_overbought": {
            "type": "integer",
            "title": "RSI Overbought Level",
            "description": (
                "RSI level above which the market is considered overbought (triggers short). "
                "Used by rsi method."
            ),
            "default": 70,
            "minimum": 50,
            "maximum": 100,
        },
        "rsi_oversold": {
            "type": "integer",
            "title": "RSI Oversold Level",
            "description": (
                "RSI level below which the market is considered oversold (triggers long). "
                "Used by rsi method."
            ),
            "default": 30,
            "minimum": 0,
            "maximum": 50,
        },
    },
    "required": [
        "base_lot_size",
        "scaling_mode",
        "retracement_pips",
        "take_profit_pips",
    ],
}

# Register the strategy
register_strategy("floor", FLOOR_STRATEGY_CONFIG_SCHEMA, display_name="Floor Strategy")(
    FloorStrategy
)
