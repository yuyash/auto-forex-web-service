"""Unit tests for floor strategy layer manager."""

from decimal import Decimal
from unittest.mock import MagicMock

from apps.trading.strategies.floor.layer import LayerManager, PositionInfo


class TestPositionInfo:
    def test_creation(self):
        info = PositionInfo(
            entry_price=Decimal("150"), units=Decimal("1000"), entry_time=1000, direction="long"
        )
        assert info.entry_price == Decimal("150")
        assert info.direction == "long"


class TestLayerManager:
    def _make_config(self):
        config = MagicMock()
        config.max_retracements_per_layer = 5
        config.max_layers = 3
        config.base_lot_size = MagicMock()
        config.lot_unit_size = MagicMock()
        config.retracement_lot_mode = "constant"
        config.retracement_lot_amount = MagicMock()
        config.floor_retracement_pips = MagicMock(return_value=MagicMock())
        return config

    def test_create_layer(self):
        mgr = LayerManager(self._make_config())
        idx = mgr.create_layer()
        assert idx == 1
        assert mgr.get_layer_count() == 1

    def test_close_layer(self):
        mgr = LayerManager(self._make_config())
        mgr.create_layer()
        assert mgr.close_layer(1) is True
        assert mgr.get_layer_count() == 0

    def test_close_nonexistent_layer(self):
        mgr = LayerManager(self._make_config())
        assert mgr.close_layer(99) is False

    def test_clear_layers(self):
        mgr = LayerManager(self._make_config())
        mgr.create_layer()
        mgr.create_layer()
        mgr.clear_layers()
        assert mgr.get_layer_count() == 0

    def test_can_create_new_layer(self):
        config = self._make_config()
        config.max_layers = 2
        mgr = LayerManager(config)
        assert mgr.can_create_new_layer() is True
        mgr.create_layer()
        mgr.create_layer()
        assert mgr.can_create_new_layer() is False

    def test_can_add_retracement(self):
        config = self._make_config()
        config.max_retracements_per_layer = 3
        mgr = LayerManager(config)
        mgr.create_layer()
        assert mgr.can_add_retracement(1) is True
        assert mgr.can_add_retracement(99) is False

    def test_calculate_retracement_trigger_pips(self):
        config = self._make_config()
        config.floor_retracement_pips.return_value = Decimal("10")
        mgr = LayerManager(config)
        mgr.create_layer()
        assert mgr.calculate_retracement_trigger_pips(1) == Decimal("10")
        assert mgr.calculate_retracement_trigger_pips(99) is None
