"""Unit tests for trading serializers tick."""

from apps.trading.serializers.tick import TickDataCSVSerializer, TickDataSerializer


class TestTickDataSerializer:
    """Test TickDataSerializer."""

    def test_meta_fields(self):
        expected = [
            "id",
            "instrument",
            "timestamp",
            "bid",
            "ask",
            "mid",
            "spread",
            "created_at",
        ]
        assert TickDataSerializer.Meta.fields == expected

    def test_all_fields_readonly(self):
        assert TickDataSerializer.Meta.read_only_fields == TickDataSerializer.Meta.fields

    def test_has_get_spread_method(self):
        assert hasattr(TickDataSerializer, "get_spread")


class TestTickDataCSVSerializer:
    """Test TickDataCSVSerializer."""

    def test_meta_fields(self):
        expected = ["timestamp", "instrument", "bid", "ask", "mid", "spread"]
        assert TickDataCSVSerializer.Meta.fields == expected

    def test_all_fields_readonly(self):
        assert TickDataCSVSerializer.Meta.read_only_fields == TickDataCSVSerializer.Meta.fields
