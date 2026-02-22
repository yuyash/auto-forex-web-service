"""Unit tests for OrderSerializer."""

from decimal import Decimal

from apps.market.serializers import OrderSerializer


class TestOrderSerializer:
    """Test OrderSerializer."""

    def test_valid_market_order(self) -> None:
        """Test serializing valid market order."""
        data = {
            "instrument": "EUR_USD",
            "order_type": "market",
            "direction": "long",
            "units": Decimal("1000.00"),
        }

        serializer = OrderSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_valid_limit_order(self) -> None:
        """Test serializing valid limit order."""
        data = {
            "instrument": "EUR_USD",
            "order_type": "limit",
            "direction": "long",
            "units": Decimal("1000.00"),
            "price": Decimal("1.10000"),
        }

        serializer = OrderSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_limit_order_without_price(self) -> None:
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

    def test_valid_oco_order(self) -> None:
        """Test serializing valid OCO order."""
        data = {
            "instrument": "EUR_USD",
            "order_type": "oco",
            "direction": "long",
            "units": Decimal("1000.00"),
            "limit_price": Decimal("1.11000"),
            "stop_price": Decimal("1.09000"),
        }

        serializer = OrderSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_oco_order_missing_prices(self) -> None:
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

    def test_invalid_order_type(self) -> None:
        """Test validation with invalid order type."""
        data = {
            "instrument": "EUR_USD",
            "order_type": "invalid",
            "direction": "long",
            "units": Decimal("1000.00"),
        }

        serializer = OrderSerializer(data=data)
        assert not serializer.is_valid()
        assert "order_type" in serializer.errors
