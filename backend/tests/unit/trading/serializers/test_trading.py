"""Unit tests for trading serializers trading."""

from unittest.mock import MagicMock

from apps.trading.serializers.trading import (
    TradingTaskCreateSerializer,
    TradingTaskListSerializer,
    TradingTaskSerializer,
)


class TestTradingTaskSerializer:
    """Test TradingTaskSerializer."""

    def test_meta_fields(self):
        fields = TradingTaskSerializer.Meta.fields
        assert "id" in fields
        assert "status" in fields
        assert "sell_on_stop" in fields
        assert "has_strategy_state" in fields
        assert "can_resume" in fields

    def test_get_instrument_from_config(self):
        serializer = TradingTaskSerializer()
        obj = MagicMock()
        obj.config.parameters = {"instrument": "USD_JPY"}
        result = serializer.get_instrument(obj)
        assert result == "USD_JPY"

    def test_get_instrument_default(self):
        serializer = TradingTaskSerializer()
        obj = MagicMock()
        obj.config = None
        result = serializer.get_instrument(obj)
        assert result == "EUR_USD"

    def test_get_has_strategy_state(self):
        serializer = TradingTaskSerializer()
        obj = MagicMock()
        obj.has_strategy_state.return_value = True
        assert serializer.get_has_strategy_state(obj) is True

    def test_get_can_resume(self):
        serializer = TradingTaskSerializer()
        obj = MagicMock()
        obj.can_resume.return_value = False
        assert serializer.get_can_resume(obj) is False


class TestTradingTaskListSerializer:
    """Test TradingTaskListSerializer."""

    def test_meta_fields(self):
        fields = TradingTaskListSerializer.Meta.fields
        assert "id" in fields
        assert "status" in fields
        # List view should not have has_strategy_state
        assert "has_strategy_state" not in fields

    def test_get_instrument_from_config(self):
        serializer = TradingTaskListSerializer()
        obj = MagicMock()
        obj.config.parameters = {"instrument": "GBP_USD"}
        result = serializer.get_instrument(obj)
        assert result == "GBP_USD"


class TestTradingTaskCreateSerializer:
    """Test TradingTaskCreateSerializer."""

    def test_meta_fields(self):
        fields = TradingTaskCreateSerializer.Meta.fields
        assert "config_id" in fields
        assert "account_id" in fields
        assert "name" in fields
