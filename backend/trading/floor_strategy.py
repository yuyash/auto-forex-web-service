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


class Layer:
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
        self.last_entry_price: Decimal | None = None
        self.current_lot_size = Decimal(str(config.get("base_lot_size", 1.0)))
        self.is_active = True
        self.peak_price: Decimal | None = None  # Track peak price for retracement detection
        self.has_scaled_at_current_level = False  # Prevent multiple scales at same level
        self.has_pending_initial_entry = False  # Track if initial entry order is pending
        self.last_scale_tick_id: str | None = None  # Track last scaling tick (unique ID)
        self.last_initial_entry_tick_id: str | None = None  # Track last initial entry tick

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
        """Increment the retracement count for this layer."""
        self.retracement_count += 1

    def should_create_new_layer(self) -> bool:
        """
        Check if a new layer should be created based on retracement count.

        Returns:
            True if new layer should be created
        """
        trigger: int = self.config.get("retracement_count_trigger", 10)
        return self.retracement_count >= trigger


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


class FloorStrategy(BaseStrategy):
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
        self.volatility_lock_multiplier = Decimal(
            str(self.get_config_value("volatility_lock_multiplier", 5.0))
        )

        # Entry signal configuration
        self.entry_signal_lookback_ticks = self.get_config_value("entry_signal_lookback_ticks", 10)

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
                    layer.retracement_count = layer_state.get("retracement_count", 0)
                    layer.current_lot_size = Decimal(
                        str(layer_state.get("current_lot_size", self.base_lot_size))
                    )

    def _save_state(self) -> None:
        """Save strategy state to database."""
        layer_states = {}
        for layer in self.layer_manager.layers:
            layer_states[str(layer.layer_number)] = {
                "retracement_count": layer.retracement_count,
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
        Check for entry signal using simple technical analysis.

        According to spec: "Direction (long or short) is chosen after a quick
        technical check (trend, support/resistance, indicator)."

        This implementation uses a simple price momentum check:
        - Compare current price to price from N ticks ago
        - If price is rising consistently, signal long
        - If price is falling consistently, signal short

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

        # Keep only last 100 ticks
        if len(instrument_history) > 100:
            self._price_history[tick_data.instrument] = instrument_history[-100:]
            instrument_history = self._price_history[tick_data.instrument]

        # Need at least N ticks for signal (configurable)
        if len(instrument_history) < self.entry_signal_lookback_ticks:
            return None

        # Calculate price momentum over last N ticks
        recent_prices = [
            p["price"] for p in instrument_history[-self.entry_signal_lookback_ticks :]
        ]
        oldest_price = recent_prices[0]
        current_price = recent_prices[-1]

        # Calculate pip movement
        pip_movement = (current_price - oldest_price) * Decimal("10000")

        # Log periodically for debugging
        # Log at key milestones: when we first reach lookback threshold, then every 100 ticks
        should_log = (
            len(instrument_history) == self.entry_signal_lookback_ticks
            or len(instrument_history) % 100 == 0
        )
        if should_log:
            lookback = self.entry_signal_lookback_ticks
            momentum_msg = f"Analyzing momentum: {pip_movement:.1f} pips over {lookback} ticks"
            self.log_strategy_event(
                "entry_signal_check",
                momentum_msg,
                {
                    "instrument": tick_data.instrument,
                    "pip_movement": str(pip_movement),
                    "oldest_price": str(oldest_price),
                    "current_price": str(current_price),
                    "history_length": len(instrument_history),
                    "lookback_ticks": lookback,
                },
            )

        # Spec says: "Initial entry: Any price level is acceptable"
        # So we ALWAYS enter, just determine direction based on momentum
        if pip_movement > 0:
            direction = "long"
            reason = f"Upward momentum: {pip_movement:.1f} pips"
        else:
            direction = "short"
            reason = f"Downward momentum: {pip_movement:.1f} pips"

        lookback = self.entry_signal_lookback_ticks
        entry_msg = f"{direction.upper()} entry: {pip_movement:.1f} pips " f"over {lookback} ticks"
        self.log_strategy_event(
            "entry_signal_triggered",
            entry_msg,
            {
                "direction": direction,
                "pip_movement": str(pip_movement),
                "lookback_ticks": lookback,
            },
        )

        return {
            "direction": direction,
            "reason": reason,
        }

    def _process_layer(self, layer: Layer, tick_data: TickData) -> list[Order]:
        """
        Process a single layer.

        Args:
            layer: Layer to process
            tick_data: Current tick data

        Returns:
            List of orders to execute
        """
        orders: list[Order] = []

        # If no positions in layer, create initial entry (only once)
        if not layer.positions and not layer.has_pending_initial_entry:
            logger.debug(
                f"Layer {layer.layer_number} has no positions (count={len(layer.positions)}), "
                f"creating initial entry at {tick_data.timestamp}"
            )
            order = self._create_initial_entry_order(layer, tick_data)
            if order:
                layer.has_pending_initial_entry = True  # Mark as pending
                self.log_strategy_event(
                    "order_created",
                    f"Created order for layer {layer.layer_number}",
                    {
                        "order_id": order.order_id,
                        "direction": order.direction,
                        "units": str(order.units),
                        "price": str(order.price),
                    },
                )
                orders.append(order)
            return orders

        if not layer.positions:
            # Waiting for pending order to execute
            logger.debug(f"Layer {layer.layer_number} waiting for pending initial entry to execute")
            return orders

        logger.debug(
            f"Layer {layer.layer_number} has {len(layer.positions)} positions, "
            f"checking for Step 2 / scaling / TP"
        )

        # Check for take-profit on ALL positions (including initial lot)
        tp_orders = self._check_take_profit(layer, tick_data)
        if tp_orders:
            orders.extend(tp_orders)
            return orders

        # STEP 3+: Track peak price and check for retracement to scale in
        # Retracement means: price moved in our favor, then moved AGAINST us
        if layer.last_entry_price and layer.peak_price is not None and layer.positions:
            direction = layer.positions[0].direction

            # CRITICAL: Use bid/ask prices, not mid, to match position entry prices
            # Long positions use ASK (buy price), Short positions use BID (sell price)
            current_price = tick_data.ask if direction == "long" else tick_data.bid

            # Log current state for debugging (only first few times)
            if layer.retracement_count < 3:
                logger.debug(
                    f"Layer {layer.layer_number}: peak={layer.peak_price}, "
                    f"current={current_price}, direction={direction}, "
                    f"has_scaled={layer.has_scaled_at_current_level}"
                )

            # Update peak price based on direction (most favorable price seen)
            should_update_peak = (direction == "long" and current_price > layer.peak_price) or (
                direction == "short" and current_price < layer.peak_price
            )
            if should_update_peak:
                layer.peak_price = current_price
                layer.has_scaled_at_current_level = False  # Reset flag at new peak

            # Check if price has RETRACED from peak (moved against us)
            # Prevent scaling multiple times in the same tick
            tick_id = f"{tick_data.timestamp.timestamp()}_{current_price}"
            if not layer.has_scaled_at_current_level and layer.last_scale_tick_id != tick_id:
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

                # Safety check: Only scale if retracement is positive (price moved against us)
                # and meets the threshold
                if retracement_pips > 0 and retracement_pips >= self.retracement_pips:
                    retracement_msg = (
                        f"[RETRACEMENT DETECTED] Layer {layer.layer_number} | "
                        f"{direction.upper()} position | "
                        f"Price moved from peak {layer.peak_price} to {current_price} | "
                        f"Retracement: {retracement_pips:.1f} pips "
                        f"(Threshold: {self.retracement_pips} pips) | "
                        f"Preparing to scale-in"
                    )
                    logger.info(retracement_msg)

                    # Log the retracement details
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
                            "event_type": "retracement",
                        },
                    )
                    # Price has retraced enough from peak - scale in
                    scale_order = self._create_scale_order(layer, tick_data)
                    if scale_order:
                        orders.append(scale_order)
                        layer.increment_retracement_count()
                        layer.has_scaled_at_current_level = True  # Prevent multiple scales
                        layer.last_scale_tick_id = tick_id  # Track tick ID

        return orders

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
                    },
                )
                self._no_signal_log_count += 1
            return None

        direction = entry_signal["direction"]

        # IMPORTANT: Only create initial entry if layer truly has no positions
        # This prevents creating opposite direction positions
        if layer.positions:
            logger.warning(
                f"Layer {layer.layer_number} already has {len(layer.positions)} positions, "
                f"skipping initial entry"
            )
            return None

        # Prevent creating multiple initial entries in the same tick
        # Use a unique tick ID (timestamp + price) to handle sub-second ticks
        tick_id = f"{tick_data.timestamp.timestamp()}_{tick_data.mid}"
        if layer.last_initial_entry_tick_id == tick_id:
            logger.warning(
                f"Layer {layer.layer_number} already created initial entry for tick {tick_id}, "
                f"skipping duplicate"
            )
            return None

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
                "event_type": "position_open",
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

        # Get direction from existing positions
        if not layer.positions:
            return None

        direction = layer.positions[0].direction

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
            f"[SCALE-IN] Layer {layer.layer_number} | "
            f"Adding {direction.upper()} position | "
            f"Size: {next_lot_size} units @ {order_price} | "
            f"Peak: {layer.peak_price} | "
            f"Retracement #{layer.retracement_count + 1}"
        )
        logger.info(scale_in_msg)

        scale_log_msg = (
            f"Scale-in: {direction.upper()} {next_lot_size} units @ {order_price} "
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
                "retracement_count": layer.retracement_count,
                "event_type": "position_open",
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
            reason: Reason for closing (initial_profit, take_profit, etc.)

        Returns:
            Close order or None
        """
        # Reverse direction for closing
        close_direction = "short" if position.direction == "long" else "long"

        order = Order(
            account=self.account,
            strategy=self.strategy,
            order_id=f"floor_close_{position.position_id}_{tick_data.timestamp.timestamp()}",
            instrument=position.instrument,
            order_type="market",
            direction=close_direction,
            units=position.units,
            price=tick_data.mid,
        )
        # Add layer metadata for backtest engine
        order.layer_number = getattr(position, "layer_number", None)  # type: ignore[attr-defined]
        order.is_first_lot = False  # type: ignore[attr-defined]

        # Calculate pip difference for logging
        pip_size = Decimal("0.01") if "JPY" in position.instrument else Decimal("0.0001")
        price_diff = tick_data.mid - position.entry_price
        if position.direction == "short":
            price_diff = -price_diff
        pip_diff = float(price_diff / pip_size)

        # Human-friendly reason
        reason_map = {
            "strategy_close": "Take Profit",
            "take_profit": "Take Profit",
            "stop_loss": "Stop Loss",
            "volatility_lock": "Volatility Lock",
            "margin_protection": "Margin Protection",
        }
        reason_display = reason_map.get(reason, reason.replace("_", " ").title())

        close_msg = (
            f"Closing position: {position.direction.upper()} {position.units} units | "
            f"{pip_diff:+.1f} pips | {reason_display}"
        )
        self.log_strategy_event(
            reason,
            close_msg,
            {
                "position_id": position.position_id,
                "instrument": position.instrument,
                "direction": position.direction,
                "entry_price": str(position.entry_price),
                "exit_price": str(tick_data.mid),
                "units": str(position.units),
                "pip_diff": pip_diff,
                "reason": reason,
                "reason_display": reason_display,
                "event_type": "position_close",
            },
        )

        return order

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
                        self.log_strategy_event(
                            "new_layer_created",
                            f"Created new layer {next_layer_num}",
                            {
                                "layer": next_layer_num,
                                "trigger_layer": layer.layer_number,
                                "retracement_count": layer.retracement_count,
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
        base_trigger = self.get_config_value("retracement_trigger_base", 10)
        trigger_progression = self.get_config_value("retracement_trigger_progression", "additive")
        trigger_increment = self.get_config_value("retracement_trigger_increment", 5)

        retracement_trigger = self._calculate_progression_value(
            base_value=base_trigger,
            layer_num=layer_num,
            progression_mode=trigger_progression,
            increment=trigger_increment,
        )

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
            "retracement_count_trigger": int(retracement_trigger),
            "base_lot_size": float(lot_size),
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
                    logger.debug(f"Position already in layer {layer.layer_number}")
                break

    def on_position_closed(self, position: Position) -> None:
        """
        Handle position closures - remove position from layer.

        Args:
            position: Position that was closed
        """
        logger.debug(
            f"on_position_closed called: layer={position.layer_number}, "
            f"position_id={position.position_id}"
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
                        logger.debug(f"Cleared first_lot_position for layer {layer.layer_number}")
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
        "volatility_lock_multiplier": {
            "type": "number",
            "title": "Volatility Lock Multiplier",
            "description": (
                "ATR multiplier to trigger volatility lock " "(e.g., 5.0 = 5x normal ATR)"
            ),
            "default": 5.0,
            "minimum": 1.0,
        },
        "retracement_trigger_base": {
            "type": "integer",
            "title": "Base Retracement Trigger",
            "description": "Base number of retracements for layer 1",
            "default": 10,
            "minimum": 1,
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
