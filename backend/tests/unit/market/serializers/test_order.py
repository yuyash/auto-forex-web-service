"""Pure unit tests for OrderSerializer (no DB)."""

from decimal import Decimal

from apps.market.serializers import OrderSerializer


class TestOrderSerializerUnit:
    """Pure unit tests for OrderSerializer."""

    def test_valid_market_order_data(self) -> None:
        """Test serializing valid market order data."""
        data = {
            "instrument": "EUR_USD",
            "order_type": "market",
            "direction": "long",
            "units": Decimal("1000.00"),
        }

        serializer = OrderSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_limit_order_requires_price(self) -> None:
        """Test that limit order requires price."""
        data = {
            "instrument": "EUR_USD",
            "order_type": "limit",
            "direction": "long",
            "units": Decimal("1000.00"),
        }

        serializer = OrderSerializer(data=data)
        assert not serializer.is_valid()
        assert "non_field_errors" in serializer.errors

    def test_oco_order_requires_both_prices(self) -> None:
        """Test that OCO order requires both limit and stop prices."""
        data = {
            "instrument": "EUR_USD",
            "order_type": "oco",
            "direction": "long",
            "units": Decimal("1000.00"),
            "limit_price": Decimal("1.11000"),
            # Missing stop_price
        }

        serializer = OrderSerializer(data=data)
        assert not serializer.is_valid()
        assert "non_field_errors" in serializer.errors
