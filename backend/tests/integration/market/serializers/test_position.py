"""Unit tests for PositionSerializer."""

from decimal import Decimal

from apps.market.serializers import PositionSerializer


class TestPositionSerializer:
    """Test PositionSerializer."""

    def test_valid_position_data(self) -> None:
        """Test serializing valid position data."""
        data = {
            "instrument": "EUR_USD",
            "direction": "long",
            "units": Decimal("1000.00"),
            "take_profit": Decimal("1.10000"),
            "stop_loss": Decimal("1.09000"),
        }

        serializer = PositionSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

        validated = serializer.validated_data
        assert validated["instrument"] == "EUR_USD"
        assert validated["direction"] == "long"
        assert validated["units"] == Decimal("1000.00")

    def test_missing_required_fields(self) -> None:
        """Test validation with missing required fields."""
        data = {
            "instrument": "EUR_USD",
            # Missing direction and units
        }

        serializer = PositionSerializer(data=data)
        assert not serializer.is_valid()
        assert "direction" in serializer.errors
        assert "units" in serializer.errors

    def test_invalid_direction(self) -> None:
        """Test validation with invalid direction."""
        data = {
            "instrument": "EUR_USD",
            "direction": "invalid",
            "units": Decimal("1000.00"),
        }

        serializer = PositionSerializer(data=data)
        assert not serializer.is_valid()
        assert "direction" in serializer.errors

    def test_optional_fields(self) -> None:
        """Test that take_profit and stop_loss are optional."""
        data = {
            "instrument": "GBP_USD",
            "direction": "short",
            "units": Decimal("500.00"),
        }

        serializer = PositionSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

        validated = serializer.validated_data
        assert "take_profit" not in validated or validated["take_profit"] is None
        assert "stop_loss" not in validated or validated["stop_loss"] is None
