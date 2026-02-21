"""Layer management for Floor strategy."""

from dataclasses import dataclass
from decimal import Decimal
from logging import Logger, getLogger
from typing import Dict

from apps.trading.models import Layer, Position
from apps.trading.strategies.floor.models import FloorStrategyConfig

logger: Logger = getLogger(name=__name__)


@dataclass
class PositionInfo:
    """Information about a closed position."""

    entry_price: Decimal
    units: Decimal
    entry_time: int
    direction: str


class LayerManager:
    """Manage trading layers."""

    def __init__(self, config: FloorStrategyConfig) -> None:
        """Initialize layer manager.

        Args:
            config: Strategy configuration
        """
        self.config = config
        self.layers: Dict[int, Layer] = {}

    def get_layer_count(self) -> int:
        """Get number of active layers.

        Returns:
            Number of layers
        """
        return len(self.layers)

    def clear_layers(self) -> None:
        """Clear all layers."""
        self.layers = {}
        logger.info("Cleared all layers")

    def create_layer(self) -> int:
        """Create layer.

        Returns:
            Created layer index
        """
        index: int = len(self.layers)
        layer = Layer(index=index)
        self.layers[index] = layer
        logger.info(msg=f"Created initial layer {index}.")
        return index

    def add_position(
        self,
        layer_index: int,
        entry_price: Decimal,
        timestamp: int,
    ) -> bool:
        """Add position to the specified layer.

        Args:
            layer_index: Index of the layer to add position to
            entry_price: Entry price for the position
            timestamp: Entry timestamp

        Returns:
            True if position was added, False if layer not found
        """
        layer = self.layers.get(layer_index)
        if not layer:
            logger.warning(f"Cannot add retracement: layer {layer_index} not found")
            return False

        if not layer.direction:
            raise ValueError(f"Layer {layer_index} has no direction")

        units = self._calculate_units(layer.index, layer.retracement_count + 1)

        # Note: Position creation is handled elsewhere
        # This method just updates the layer state

        # Increment retracement count
        layer.retracement_count += 1

        logger.info(
            f"Added retracement to layer {layer.index}: "
            f"count={layer.retracement_count}, price={entry_price}, units={units}"
        )

        return True

    def close_layer(self, layer_index: int) -> bool:
        """Close and remove layer.

        Args:
            layer_index: Layer index to close

        Returns:
            True if layer was closed, False if not found
        """
        if layer_index in self.layers:
            del self.layers[layer_index]
            logger.info(f"Closed layer {layer_index}")
            return True
        else:
            logger.warning(f"Attempted to close non-existent layer {layer_index}")
            return False

    def close_oldest_positions_for_margin(
        self,
        units_to_close: Decimal,
    ) -> list[tuple[int, list[PositionInfo]]]:
        """Close oldest positions across all layers for margin protection.

        Uses FIFO across all layers.

        Args:
            units_to_close: Total units to close

        Returns:
            List of (layer_index, closed_positions) tuples
        """
        closed_by_layer: list[tuple[int, list[PositionInfo]]] = []

        # Sort all positions across all layers in FIFO order
        all_positions: list[tuple[Layer, int]] = []
        for layer in self.layers.values():
            # Get position count from the layer
            position_count = layer.position_count
            for i in range(position_count):
                all_positions.append((layer, i))

        # Note: This is a simplified version that doesn't actually access
        # the positions from the database. In a real implementation, you would
        # need to query Position.objects.filter(layer_index=layer.index, is_open=True)
        # and sort by entry_time

        logger.warning(
            "close_oldest_positions_for_margin is not fully implemented. "
            "This requires database access to Position objects."
        )

        return closed_by_layer

    def can_add_retracement(self, layer_index: int) -> bool:
        """Check if can add retracement to layer.

        Args:
            layer_index: Layer index to check

        Returns:
            True if can add retracement, False if layer not found or at limit
        """
        layer = self.layers.get(layer_index)
        if not layer:
            return False
        return layer.retracement_count < self.config.max_retracements_per_layer

    def can_create_new_layer(self) -> bool:
        """Check if can create new layer.

        Returns:
            True if can create new layer
        """
        return len(self.layers) < self.config.max_layers

    def calculate_retracement_trigger_pips(self, layer_index: int) -> Decimal | None:
        """Calculate retracement trigger distance for layer.

        Args:
            layer_index: Layer index

        Returns:
            Trigger distance in pips, or None if layer not found
        """
        layer = self.layers.get(layer_index)
        if not layer:
            return None

        return self.config.floor_retracement_pips(layer.index)

    def _calculate_units(self, layer_index: int, retracement_index: int) -> int:
        """Calculate units for position.

        Args:
            layer_index: Layer index
            retracement_index: Retracement index within layer

        Returns:
            Units
        """
        if retracement_index <= 0:
            lots = self.config.base_lot_size
        elif self.config.retracement_lot_mode == "constant":
            lots = self.config.base_lot_size
        elif self.config.retracement_lot_mode == "additive":
            lots = self.config.base_lot_size + (
                self.config.retracement_lot_amount * Decimal(retracement_index)
            )
        elif self.config.retracement_lot_mode == "subtractive":
            lots = self.config.base_lot_size - (
                self.config.retracement_lot_amount * Decimal(retracement_index)
            )
            lots = max(lots, Decimal("0.01"))
        elif self.config.retracement_lot_mode == "divisive":
            divisor = Decimal(2**retracement_index)
            lots = max(self.config.base_lot_size / divisor, Decimal("0.01"))
        else:
            # multiplicative
            multiplier = Decimal(2**retracement_index)
            lots = self.config.base_lot_size * multiplier
        return int(lots * self.config.lot_unit_size)

    def _position_to_info(self, position: Position) -> PositionInfo:
        """Convert Position model to PositionInfo dataclass.

        Args:
            position: Position model instance

        Returns:
            PositionInfo dataclass
        """
        return PositionInfo(
            entry_price=position.entry_price,
            units=Decimal(str(position.units)),
            entry_time=int(position.entry_time.timestamp()),
            direction=position.direction,
        )
