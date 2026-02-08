"""Layer management for Floor strategy."""

from datetime import datetime
from decimal import Decimal
from logging import Logger, getLogger

from apps.trading.strategies.floor.calculators import ProgressionCalculator
from apps.trading.strategies.floor.enums import Direction
from apps.trading.strategies.floor.models import (
    FloorStrategyConfig,
    FloorStrategyState,
    Layer,
    Position,
)

logger: Logger = getLogger(__name__)


class LayerManager:
    """Manage trading layers."""

    def __init__(self, config: FloorStrategyConfig) -> None:
        """Initialize layer manager.

        Args:
            config: Strategy configuration
        """
        self.config = config
        self.progression_calc = ProgressionCalculator()

    def create_initial_layer(
        self,
        state: FloorStrategyState,
        direction: Direction,
        entry_price: Decimal,
        timestamp: datetime,
    ) -> Layer:
        """Create initial layer with first position.

        Args:
            state: Strategy state
            direction: Trading direction
            entry_price: Entry price
            timestamp: Entry timestamp

        Returns:
            Created layer
        """
        layer_index = len(state.layers)
        units = self._calculate_units(layer_index, 0)

        position = Position(
            entry_price=entry_price,
            units=units,
            entry_time=timestamp,
            direction=direction,
        )

        layer = Layer(index=layer_index)
        layer.add_position(position)

        state.layers.append(layer)

        logger.info(
            f"Created initial layer {layer_index}: direction={direction.value}, "
            f"price={entry_price}, units={units}"
        )

        return layer

    def add_retracement_position(
        self,
        layer: Layer,
        entry_price: Decimal,
        timestamp: datetime,
    ) -> Position:
        """Add retracement position to layer.

        Args:
            layer: Target layer
            entry_price: Entry price
            timestamp: Entry timestamp

        Returns:
            Created position
        """
        if not layer.direction:
            raise ValueError("Layer has no direction")

        units = self._calculate_units(layer.index, layer.retracement_count + 1)

        position = Position(
            entry_price=entry_price,
            units=units,
            entry_time=timestamp,
            direction=layer.direction,
        )

        layer.add_position(position)
        layer.retracement_count += 1

        logger.info(
            f"Added retracement to layer {layer.index}: "
            f"count={layer.retracement_count}, price={entry_price}, units={units}"
        )

        return position

    def close_layer(self, state: FloorStrategyState, layer: Layer) -> None:
        """Close and remove layer.

        Args:
            state: Strategy state
            layer: Layer to close
        """
        state.layers = [lyr for lyr in state.layers if lyr.index != layer.index]

        logger.info(f"Closed layer {layer.index}")

    def close_oldest_positions_for_margin(
        self,
        state: FloorStrategyState,
        units_to_close: Decimal,
    ) -> list[tuple[Layer, list[Position]]]:
        """Close oldest positions across all layers for margin protection.

        Uses FIFO across all layers.

        Args:
            state: Strategy state
            units_to_close: Total units to close

        Returns:
            List of (layer, closed_positions) tuples
        """
        closed_by_layer: list[tuple[Layer, list[Position]]] = []
        remaining = units_to_close

        # 全レイヤーの全ポジションをFIFO順にソート
        all_positions: list[tuple[Layer, Position]] = []
        for layer in state.layers:
            for position in layer.positions:
                all_positions.append((layer, position))

        # エントリー時刻でソート（古い順）
        all_positions.sort(key=lambda x: x[1].entry_time)

        # 古いポジションからクローズ
        for layer, position in all_positions:
            if remaining <= 0:
                break

            if position.units <= remaining:
                # ポジション全体をクローズ
                layer.positions.remove(position)
                closed_by_layer.append((layer, [position]))
                remaining -= position.units
                logger.info(
                    f"Closed full position from layer {layer.index}: "
                    f"units={position.units}, remaining={remaining}"
                )
            else:
                # 部分クローズ
                closed_portion = Position(
                    entry_price=position.entry_price,
                    units=remaining,
                    entry_time=position.entry_time,
                    direction=position.direction,
                )
                position.units -= remaining
                closed_by_layer.append((layer, [closed_portion]))
                logger.info(
                    f"Partially closed position from layer {layer.index}: "
                    f"closed={remaining}, remaining_in_position={position.units}"
                )
                remaining = Decimal("0")

        # 空になったレイヤーを削除
        state.layers = [layer for layer in state.layers if layer.positions]

        return closed_by_layer

    def can_add_retracement(self, layer: Layer) -> bool:
        """Check if can add retracement to layer.

        Args:
            layer: Layer to check

        Returns:
            True if can add retracement
        """
        return layer.retracement_count < self.config.max_retracements_per_layer

    def can_create_new_layer(self, state: FloorStrategyState) -> bool:
        """Check if can create new layer.

        Args:
            state: Strategy state

        Returns:
            True if can create new layer
        """
        return len(state.layers) < self.config.max_layers

    def calculate_retracement_trigger_pips(self, layer: Layer) -> Decimal:
        """Calculate retracement trigger distance for layer.

        Args:
            layer: Layer

        Returns:
            Trigger distance in pips
        """
        return self.progression_calc.calculate(
            base=self.config.initial_retracement_pips,
            index=layer.retracement_count,
            mode=self.config.retracement_progression,
            increment=self.config.retracement_increment,
        )

    def _calculate_units(self, layer_index: int, retracement_index: int) -> Decimal:
        """Calculate units for position.

        Args:
            layer_index: Layer index
            retracement_index: Retracement index within layer

        Returns:
            Units
        """
        # レイヤーとリトレースメントの両方を考慮
        total_index = layer_index + retracement_index

        return self.progression_calc.calculate(
            base=self.config.initial_units,
            index=total_index,
            mode=self.config.unit_progression,
            increment=self.config.unit_increment,
        )
