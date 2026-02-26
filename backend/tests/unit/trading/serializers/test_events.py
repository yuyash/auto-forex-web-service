"""Unit tests for trading serializers events."""

from unittest.mock import MagicMock

from apps.trading.enums import EventType
from apps.trading.serializers.events import (
    OrderSerializer,
    PositionSerializer,
    TradeSerializer,
    TradingEventSerializer,
)


class TestTradingEventSerializer:
    """Test TradingEventSerializer."""

    def test_meta_fields_include_event_type(self):
        assert "event_type" in TradingEventSerializer.Meta.fields
        assert "event_type_display" in TradingEventSerializer.Meta.fields

    def test_get_event_type_display_valid(self):
        serializer = TradingEventSerializer()
        obj = MagicMock()
        obj.event_type = EventType.TICK_RECEIVED.value
        result = serializer.get_event_type_display(obj)
        assert result == "Tick Received"

    def test_get_event_type_display_invalid(self):
        serializer = TradingEventSerializer()
        obj = MagicMock()
        obj.event_type = "nonexistent_type"
        result = serializer.get_event_type_display(obj)
        assert result == "nonexistent_type"

    def test_get_event_scope_task(self):
        serializer = TradingEventSerializer()
        obj = MagicMock()
        obj.event_type = EventType.STATUS_CHANGED.value
        obj.details = {"kind": "task_stop_requested"}
        assert serializer.get_event_scope(obj) == "task"

    def test_get_event_scope_trading(self):
        serializer = TradingEventSerializer()
        obj = MagicMock()
        obj.event_type = EventType.OPEN_POSITION.value
        obj.details = {"event_type": "initial_entry", "strategy_event_type": "initial_entry"}
        assert serializer.get_event_scope(obj) == "trading"


class TestTradeSerializer:
    """Test TradeSerializer."""

    def test_fields_exist(self):
        serializer = TradeSerializer()
        assert "direction" in serializer.fields
        assert "units" in serializer.fields
        assert "instrument" in serializer.fields
        assert "price" in serializer.fields

    def test_get_execution_method_display_valid(self):
        serializer = TradeSerializer()
        obj = MagicMock()
        obj.execution_method = EventType.INITIAL_ENTRY.value
        result = serializer.get_execution_method_display(obj)
        assert result == "Initial Entry"

    def test_get_execution_method_display_empty(self):
        serializer = TradeSerializer()
        obj = MagicMock()
        obj.execution_method = None
        result = serializer.get_execution_method_display(obj)
        assert result == ""

    def test_get_execution_method_display_from_dict(self):
        serializer = TradeSerializer()
        obj = {"execution_method": EventType.TAKE_PROFIT.value}
        result = serializer.get_execution_method_display(obj)
        assert result == "Take Profit"


class TestPositionSerializer:
    """Test PositionSerializer."""

    def test_fields_exist(self):
        serializer = PositionSerializer()
        assert "id" in serializer.fields
        assert "instrument" in serializer.fields
        assert "direction" in serializer.fields
        assert "is_open" in serializer.fields

    def test_get_trade_ids_with_prefetched(self):
        serializer = PositionSerializer()
        obj = MagicMock()
        obj.prefetched_trade_ids = ["id1", "id2"]
        result = serializer.get_trade_ids(obj)
        assert result == ["id1", "id2"]

    def test_get_trade_ids_no_trades(self):
        serializer = PositionSerializer()
        obj = MagicMock(spec=[])  # No attributes
        result = serializer.get_trade_ids(obj)
        assert result == []


class TestOrderSerializer:
    """Test OrderSerializer."""

    def test_fields_exist(self):
        serializer = OrderSerializer()
        assert "id" in serializer.fields
        assert "instrument" in serializer.fields
        assert "status" in serializer.fields
        assert "is_dry_run" in serializer.fields
