"""Trading logic for Floor strategy."""

from datetime import datetime
from decimal import Decimal
from logging import Logger, getLogger

from apps.trading.dataclasses import Tick
from apps.trading.enums import TradingMode
from apps.trading.events import StrategyEvent
from apps.trading.strategies.floor.calculators import PriceCalculator
from apps.trading.strategies.floor.components import FloorDirectionDecider, FloorLayerManager
from apps.trading.strategies.floor.enums import Direction, DirectionMethod, LotMode, Progression
from apps.trading.strategies.floor.event import EventFactory
from apps.trading.strategies.floor.history import PriceHistoryManager
from apps.trading.strategies.floor.models import (
    FloorStrategyConfig,
    FloorStrategyState,
    LayerState,
    Position,
)

logger: Logger = getLogger(name=__name__)


class TradingEngine:
    """Manages all trading decisions and executions."""

    def __init__(
        self,
        config: FloorStrategyConfig,
        price_calc: PriceCalculator,
        direction_decider: FloorDirectionDecider,
        layer_manager: FloorLayerManager,
        history_manager: PriceHistoryManager,
        trading_mode: TradingMode = TradingMode.NETTING,
    ) -> None:
        self.config = config
        self.price_calc = price_calc
        self.direction_decider = direction_decider
        self.layer_manager = layer_manager
        self.history_manager = history_manager
        self.trading_mode = trading_mode
        logger.info("Initialized trading engine with mode: %s", trading_mode)

    def _progress_value(
        self, base: Decimal, index: int, mode: Progression, inc: Decimal
    ) -> Decimal:
        """Calculate progressive value based on mode."""
        i = max(0, int(index))
        if mode == Progression.EQUAL:
            return base
        if mode == Progression.INVERSE:
            return base / Decimal(i + 1)
        if mode == Progression.EXPONENTIAL:
            return base * (inc ** Decimal(i))
        # additive
        return base + (inc * Decimal(i))

    def process_initial_entry(self, state: FloorStrategyState, tick: Tick) -> list[StrategyEvent]:
        """Handle initial entry logic."""
        events: list[StrategyEvent] = []
        if state.initialized or not self.history_manager.has_enough_history_for_entry(state):
            return events

        logger.info("Processing initial entry (mode=%s)...", self.trading_mode)

        # Decide direction
        history = (
            self.history_manager.get_momentum_history(state)
            if self.config.direction_method == DirectionMethod.MOMENTUM
            else state.price_history
        )
        direction = self.direction_decider.decide_direction(history)

        logger.info("Initial entry direction: %s", direction)

        # Create initial layer
        entry_price = tick.ask if direction == Direction.LONG else tick.bid
        lot_size = self._calculate_lot_size(0)

        # Create position list for Hedging Mode
        positions = []
        if self.trading_mode == TradingMode.HEDGING:
            positions = [
                Position(
                    entry_price=entry_price,
                    lot_size=lot_size,
                    entry_time=tick.timestamp,
                )
            ]
            logger.debug("Created initial position for hedging mode")

        layer = LayerState(
            index=0,
            direction=direction,
            entry_price=entry_price,
            lot_size=lot_size,
            positions=positions,
        )

        state.active_layers = [layer]
        state.initialized = True
        state.cycle_entry_time = tick.timestamp.isoformat()

        logger.info(
            "Created initial entry layer: direction=%s, price=%s, lot=%s",
            direction,
            entry_price,
            lot_size,
        )

        events.append(
            EventFactory.create_initial_entry(
                timestamp=tick.timestamp,
                layer=0,
                direction=direction,
                entry_price=entry_price,
                lot_size=layer.lot_size,
            )
        )
        events.append(EventFactory.create_add_layer(timestamp=tick.timestamp, layer=0))

        return events

    def process_take_profit(self, state: FloorStrategyState, tick: Tick) -> list[StrategyEvent]:
        """Handle take profit logic.

        Evaluates each layer individually and closes those that meet take profit criteria.
        In Netting Mode: Closes entire layer when weighted average P&L meets criteria.
        In Hedging Mode: Closes individual positions within layer when they meet criteria.
        """
        events: list[StrategyEvent] = []

        if not state.active_layers:
            return events

        logger.debug(
            "Evaluating take profit: mode=%s, layers=%d, target_pips=%s",
            self.trading_mode,
            len(state.active_layers),
            self.config.take_profit_pips,
        )

        if self.trading_mode == TradingMode.HEDGING:
            return self._process_take_profit_hedging(state, tick)
        return self._process_take_profit_netting(state, tick)

    def _process_take_profit_netting(
        self, state: FloorStrategyState, tick: Tick
    ) -> list[StrategyEvent]:
        """Handle take profit for Netting Mode - evaluate each layer individually."""
        events: list[StrategyEvent] = []
        layers_to_remove: list[int] = []

        for layer in state.active_layers:
            # Calculate P&L for this layer
            layer_pips = self.price_calc.calculate_layer_pnl(layer, tick.bid, tick.ask)

            logger.debug(
                "Layer %d (Netting): pips=%s, target=%s, direction=%s, entry=%s, lot=%s",
                layer.index,
                layer_pips,
                self.config.take_profit_pips,
                layer.direction,
                layer.entry_price,
                layer.lot_size,
            )

            if layer_pips < self.config.take_profit_pips:
                continue  # This layer hasn't reached take profit yet

            logger.info(
                "Take profit triggered (Netting) - Layer %d: pips=%s (target=%s), pnl=%s",
                layer.index,
                layer_pips,
                self.config.take_profit_pips,
                (tick.bid - layer.entry_price) * layer.lot_size
                if layer.direction == Direction.LONG
                else (layer.entry_price - tick.ask) * layer.lot_size,
            )

            # This layer meets take profit criteria - close it
            exit_price = tick.bid if layer.direction == Direction.LONG else tick.ask

            # Calculate P&L in quote currency
            if layer.direction == Direction.LONG:
                pnl = (tick.bid - layer.entry_price) * layer.lot_size
            else:
                pnl = (layer.entry_price - tick.ask) * layer.lot_size

            # Get entry time from cycle_entry_time or None
            entry_time = None
            if state.cycle_entry_time:
                try:
                    entry_time = datetime.fromisoformat(state.cycle_entry_time)
                except (ValueError, TypeError):
                    pass

            events.append(
                EventFactory.create_take_profit(
                    timestamp=tick.timestamp,
                    direction=str(layer.direction),
                    entry_price=layer.entry_price,
                    exit_price=exit_price,
                    units=layer.lot_size,
                    pnl=pnl,
                    pips=layer_pips,
                    entry_time=entry_time,
                )
            )

            events.append(
                EventFactory.create_remove_layer(timestamp=tick.timestamp, layer=layer.index)
            )

            layers_to_remove.append(layer.index)

        # Remove closed layers
        state.active_layers = [
            layer for layer in state.active_layers if layer.index not in layers_to_remove
        ]

        # If all layers are closed, reset state
        if not state.active_layers:
            logger.info("All layers closed (Netting), resetting strategy state")
            state.initialized = False
            state.cycle_entry_time = None

        return events

    def _process_take_profit_hedging(
        self, state: FloorStrategyState, tick: Tick
    ) -> list[StrategyEvent]:
        """Handle take profit for Hedging Mode - evaluate each position individually."""
        events: list[StrategyEvent] = []
        layers_to_remove: list[int] = []

        for layer in state.active_layers:
            positions_to_close: list[int] = []

            logger.debug(
                "Evaluating layer %d (Hedging): positions=%d, direction=%s",
                layer.index,
                len(layer.positions),
                layer.direction,
            )

            # Evaluate each position in the layer
            for pos_idx, position in enumerate(layer.positions):
                # Calculate P&L for this position
                mark = tick.bid if layer.direction == Direction.LONG else tick.ask
                pips = self.price_calc.pips_between(position.entry_price, mark)

                if layer.direction == Direction.SHORT:
                    pips = -pips

                logger.debug(
                    "Position %d in layer %d: pips=%s, target=%s, entry=%s, lot=%s",
                    pos_idx,
                    layer.index,
                    pips,
                    self.config.take_profit_pips,
                    position.entry_price,
                    position.lot_size,
                )

                if pips < self.config.take_profit_pips:
                    continue  # This position hasn't reached take profit yet

                # This position meets take profit criteria - close it
                exit_price = tick.bid if layer.direction == Direction.LONG else tick.ask

                # Calculate P&L in quote currency
                if layer.direction == Direction.LONG:
                    pnl = (tick.bid - position.entry_price) * position.lot_size
                else:
                    pnl = (position.entry_price - tick.ask) * position.lot_size

                logger.info(
                    "Take profit triggered (Hedging) - Layer %d, Position %d: pips=%s, pnl=%s",
                    layer.index,
                    pos_idx,
                    pips,
                    pnl,
                )

                events.append(
                    EventFactory.create_take_profit(
                        timestamp=tick.timestamp,
                        direction=str(layer.direction),
                        entry_price=position.entry_price,
                        exit_price=exit_price,
                        units=position.lot_size,
                        pnl=pnl,
                        pips=pips,
                        entry_time=position.entry_time,
                    )
                )

                # Mark position for closure
                positions_to_close.append(pos_idx)

                # Update position with exit information
                position.exit_price = exit_price
                position.exit_time = tick.timestamp

            # Remove closed positions from layer
            if positions_to_close:
                logger.info(
                    "Closing %d positions in layer %d",
                    len(positions_to_close),
                    layer.index,
                )

                layer.positions = [
                    pos for idx, pos in enumerate(layer.positions) if idx not in positions_to_close
                ]

                # Update layer lot_size
                layer.lot_size = sum((pos.lot_size for pos in layer.positions), Decimal("0"))

                logger.debug(
                    "Layer %d after position closure: remaining_positions=%d, remaining_lot=%s",
                    layer.index,
                    len(layer.positions),
                    layer.lot_size,
                )

                # If layer has no more positions, mark for removal
                if not layer.positions or layer.lot_size <= 0:
                    logger.info("Layer %d is now empty, marking for removal", layer.index)
                    events.append(
                        EventFactory.create_remove_layer(
                            timestamp=tick.timestamp, layer=layer.index
                        )
                    )
                    layers_to_remove.append(layer.index)

        # Remove empty layers
        state.active_layers = [
            layer for layer in state.active_layers if layer.index not in layers_to_remove
        ]

        # If all layers are closed, reset state
        if not state.active_layers:
            logger.info("All layers closed (Hedging), resetting strategy state")
            state.initialized = False
            state.cycle_entry_time = None

        return events

    def process_retracements(self, state: FloorStrategyState, tick: Tick) -> list[StrategyEvent]:
        """Handle retracement logic for all layers."""
        events: list[StrategyEvent] = []

        for layer in list(state.active_layers):
            layer_events = self._process_layer_retracement(state, layer, tick)
            events.extend(layer_events)

        return events

    def _process_layer_retracement(
        self, state: FloorStrategyState, layer: LayerState, tick: Tick
    ) -> list[StrategyEvent]:
        """Handle retracement for a single layer."""
        events: list[StrategyEvent] = []

        if layer.retracements >= self.config.max_retracements_per_layer:
            return events

        against_pips = self.price_calc.against_position_pips(layer, tick.bid, tick.ask)
        trigger_pips = self._calculate_retracement_trigger(layer.index)

        logger.debug(
            "Layer %d retracement check: against=%s, trigger=%s, count=%d/%d",
            layer.index,
            against_pips,
            trigger_pips,
            layer.retracements,
            self.config.max_retracements_per_layer,
        )

        if against_pips < trigger_pips or len(state.active_layers) > self.config.max_layers:
            return events

        # Execute retracement
        layer.retracements += 1
        prev_lot_size = layer.lot_size
        lot_size = self._calculate_retracement_lot_size(prev_lot_size)
        added_lot = lot_size - prev_lot_size

        fill_price = tick.ask if layer.direction == Direction.LONG else tick.bid

        logger.info(
            "Retracement triggered - Layer %d: count=%d, against_pips=%s, trigger=%s, "
            "prev_lot=%s, new_lot=%s, added=%s, price=%s",
            layer.index,
            layer.retracements,
            against_pips,
            trigger_pips,
            prev_lot_size,
            lot_size,
            added_lot,
            fill_price,
        )

        # Update based on trading mode
        if self.trading_mode == TradingMode.HEDGING:
            # Add new position to positions list
            layer.positions.append(
                Position(
                    entry_price=fill_price,
                    lot_size=added_lot,
                    entry_time=tick.timestamp,
                )
            )
            layer.lot_size = lot_size
            logger.debug(
                "Added new position to layer %d (Hedging): total_positions=%d",
                layer.index,
                len(layer.positions),
            )
        else:
            # Netting Mode: Update weighted average entry price
            old_entry = layer.entry_price
            if lot_size > 0 and added_lot > 0 and prev_lot_size > 0:
                layer.entry_price = (
                    (layer.entry_price * prev_lot_size) + (fill_price * added_lot)
                ) / lot_size
            layer.lot_size = lot_size
            logger.debug(
                "Updated layer %d (Netting): old_entry=%s, new_entry=%s, weighted_avg",
                layer.index,
                old_entry,
                layer.entry_price,
            )

        events.append(
            EventFactory.create_retracement(
                timestamp=tick.timestamp,
                layer=layer.index,
                direction=layer.direction,
                entry_price=fill_price,
                lot_size=lot_size,
                retracement=layer.retracements,
            )
        )

        # Check if we should open next layer
        if (
            layer.retracements >= self.config.max_retracements_per_layer
            and len(state.active_layers) < self.config.max_layers
        ):
            logger.info(
                "Layer %d reached max retracements, opening next layer",
                layer.index,
            )
            next_layer_events = self._open_next_layer(state, tick)
            events.extend(next_layer_events)

        return events

    def _open_next_layer(self, state: FloorStrategyState, tick: Tick) -> list[StrategyEvent]:
        """Open the next layer."""
        events: list[StrategyEvent] = []
        next_idx = len(state.active_layers)

        logger.info("Opening next layer: index=%d", next_idx)

        # Re-evaluate direction for new layer
        history = (
            self.history_manager.get_momentum_history(state)
            if self.config.direction_method == DirectionMethod.MOMENTUM
            else state.price_history
        )
        new_direction = self.direction_decider.decide_direction(history)
        new_fill_price = tick.ask if new_direction == Direction.LONG else tick.bid
        lot_size = self._calculate_lot_size(next_idx)

        logger.info(
            "New layer %d: direction=%s, price=%s, lot=%s",
            next_idx,
            new_direction,
            new_fill_price,
            lot_size,
        )

        # Create position list for Hedging Mode
        positions = []
        if self.trading_mode == TradingMode.HEDGING:
            positions = [
                Position(
                    entry_price=new_fill_price,
                    lot_size=lot_size,
                    entry_time=tick.timestamp,
                )
            ]
            logger.debug("Created initial position for new layer (Hedging)")

        new_layer = LayerState(
            index=next_idx,
            direction=new_direction,
            entry_price=new_fill_price,
            lot_size=lot_size,
            positions=positions,
        )
        state.active_layers.append(new_layer)

        events.append(
            EventFactory.create_initial_entry(
                timestamp=tick.timestamp,
                layer=next_idx,
                direction=new_direction,
                entry_price=new_fill_price,
                lot_size=new_layer.lot_size,
            )
        )
        events.append(EventFactory.create_add_layer(timestamp=tick.timestamp, layer=next_idx))

        return events

    def _calculate_lot_size(self, layer_index: int) -> Decimal:
        """Calculate lot size for a layer."""
        return self._progress_value(
            base=self.config.base_lot_size,
            index=layer_index,
            mode=self.config.lot_size_progression,
            inc=self.config.lot_size_increment,
        )

    def _calculate_retracement_trigger(self, layer_index: int) -> Decimal:
        """Calculate retracement trigger pips for a layer."""
        return self._progress_value(
            base=self.config.retracement_pips,
            index=layer_index,
            mode=self.config.retracement_trigger_progression,
            inc=self.config.retracement_trigger_increment,
        )

    def _calculate_retracement_lot_size(self, current: Decimal) -> Decimal:
        """Calculate new lot size after retracement."""
        if self.config.retracement_lot_mode == LotMode.MULTIPLICATIVE:
            return current * self.config.retracement_lot_amount
        return current + self.config.retracement_lot_amount
