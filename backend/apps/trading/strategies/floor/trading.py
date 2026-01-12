"""Trading logic for Floor strategy."""

from decimal import Decimal

from apps.trading.dataclasses import Tick
from apps.trading.events import StrategyEvent
from apps.trading.strategies.floor.calculators import PriceCalculator
from apps.trading.strategies.floor.components import FloorDirectionDecider, FloorLayerManager
from apps.trading.strategies.floor.enums import Direction, DirectionMethod, LotMode, Progression
from apps.trading.strategies.floor.event import EventFactory
from apps.trading.strategies.floor.history import PriceHistoryManager
from apps.trading.strategies.floor.models import FloorStrategyConfig, FloorStrategyState, LayerState


class TradingEngine:
    """Manages all trading decisions and executions."""

    def __init__(
        self,
        config: FloorStrategyConfig,
        price_calc: PriceCalculator,
        direction_decider: FloorDirectionDecider,
        layer_manager: FloorLayerManager,
        history_manager: PriceHistoryManager,
    ) -> None:
        self.config = config
        self.price_calc = price_calc
        self.direction_decider = direction_decider
        self.layer_manager = layer_manager
        self.history_manager = history_manager

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

        # Decide direction
        history = (
            self.history_manager.get_momentum_history(state)
            if self.config.direction_method == DirectionMethod.MOMENTUM
            else state.price_history
        )
        direction = self.direction_decider.decide_direction(history)

        # Create initial layer
        entry_price = tick.ask if direction == Direction.LONG else tick.bid
        layer = LayerState(
            index=0,
            direction=direction,
            entry_price=entry_price,
            lot_size=self._calculate_lot_size(0),
        )

        state.active_layers = [layer]
        state.initialized = True
        state.cycle_entry_time = tick.timestamp.isoformat()

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
        """Handle take profit logic."""
        events: list[StrategyEvent] = []

        if not state.active_layers:
            return events

        total_pips = self.price_calc.calculate_pnl(state.active_layers, tick.bid, tick.ask)
        if total_pips < self.config.take_profit_pips:
            return events

        # Calculate P&L
        total_units = sum((layer.lot_size for layer in state.active_layers), Decimal("0"))
        weighted_entry = Decimal("0")
        if total_units > 0:
            weighted_entry = (
                sum(
                    (
                        layer.entry_price * layer.lot_size
                        for layer in state.active_layers
                        if layer.lot_size > 0
                    ),
                    Decimal("0"),
                )
                / total_units
            )

        # Determine overall direction
        directions = {layer.direction for layer in state.active_layers}
        if len(directions) == 1:
            overall_direction = next(iter(directions))
            exit_price = tick.bid if overall_direction == Direction.LONG else tick.ask
            direction_out: str | None = str(overall_direction)
        else:
            exit_price = tick.mid
            direction_out = "mixed"

        # Calculate total P&L in quote currency
        total_pnl = Decimal("0")
        for layer in state.active_layers:
            if layer.lot_size <= 0:
                continue
            if layer.direction == Direction.LONG:
                total_pnl += (tick.bid - layer.entry_price) * layer.lot_size
            else:
                total_pnl += (layer.entry_price - tick.ask) * layer.lot_size

        # Parse entry_time from cycle_entry_time string
        from datetime import datetime

        entry_time = None
        if state.cycle_entry_time:
            try:
                entry_time = datetime.fromisoformat(state.cycle_entry_time)
            except (ValueError, TypeError):
                pass

        events.append(
            EventFactory.create_take_profit(
                timestamp=tick.timestamp,
                direction=direction_out,
                entry_price=weighted_entry if total_units > 0 else None,
                exit_price=exit_price,
                units=total_units if total_units > 0 else None,
                pnl=total_pnl,
                pips=total_pips,
                entry_time=entry_time,
            )
        )

        # Close all layers
        for layer in state.active_layers:
            events.append(
                EventFactory.create_remove_layer(timestamp=tick.timestamp, layer=layer.index)
            )

        state.active_layers = []
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

        if against_pips < trigger_pips or len(state.active_layers) > self.config.max_layers:
            return events

        # Execute retracement
        layer.retracements += 1
        prev_lot_size = layer.lot_size
        lot_size = self._calculate_retracement_lot_size(prev_lot_size)
        added_lot = lot_size - prev_lot_size

        fill_price = tick.ask if layer.direction == Direction.LONG else tick.bid

        # Update weighted average entry price
        if lot_size > 0 and added_lot > 0 and prev_lot_size > 0:
            layer.entry_price = (
                (layer.entry_price * prev_lot_size) + (fill_price * added_lot)
            ) / lot_size
        layer.lot_size = lot_size

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
            next_layer_events = self._open_next_layer(state, tick)
            events.extend(next_layer_events)

        return events

    def _open_next_layer(self, state: FloorStrategyState, tick: Tick) -> list[StrategyEvent]:
        """Open the next layer."""
        events: list[StrategyEvent] = []
        next_idx = len(state.active_layers)

        # Re-evaluate direction for new layer
        history = (
            self.history_manager.get_momentum_history(state)
            if self.config.direction_method == DirectionMethod.MOMENTUM
            else state.price_history
        )
        new_direction = self.direction_decider.decide_direction(history)
        new_fill_price = tick.ask if new_direction == Direction.LONG else tick.bid

        new_layer = LayerState(
            index=next_idx,
            direction=new_direction,
            entry_price=new_fill_price,
            lot_size=self._calculate_lot_size(next_idx),
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
