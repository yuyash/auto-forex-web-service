"""Order serializer."""

from decimal import Decimal
from typing import Any

from rest_framework import serializers


class OrderSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    """Serializer for creating orders."""

    instrument = serializers.CharField(
        required=True,
        max_length=10,
        help_text="Currency pair (e.g., 'EUR_USD')",
    )
    order_type = serializers.ChoiceField(
        required=True,
        choices=["market", "limit", "stop", "oco"],
        help_text="Type of order",
    )
    direction = serializers.ChoiceField(
        required=True,
        choices=["long", "short"],
        help_text="Trade direction",
    )
    units = serializers.DecimalField(
        required=True,
        max_digits=15,
        decimal_places=2,
        min_value=Decimal("0.01"),
        help_text="Number of units to trade",
    )
    price = serializers.DecimalField(
        required=False,
        allow_null=True,
        max_digits=10,
        decimal_places=5,
        help_text="Order price (required for limit/stop orders)",
    )
    take_profit = serializers.DecimalField(
        required=False,
        allow_null=True,
        max_digits=10,
        decimal_places=5,
        help_text="Take-profit price",
    )
    stop_loss = serializers.DecimalField(
        required=False,
        allow_null=True,
        max_digits=10,
        decimal_places=5,
        help_text="Stop-loss price",
    )
    limit_price = serializers.DecimalField(
        required=False,
        allow_null=True,
        max_digits=10,
        decimal_places=5,
        help_text="Limit price (for OCO orders)",
    )
    stop_price = serializers.DecimalField(
        required=False,
        allow_null=True,
        max_digits=10,
        decimal_places=5,
        help_text="Stop price (for OCO orders)",
    )

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:  # pylint: disable=arguments-renamed
        """Validate order data based on order type."""
        order_type = attrs.get("order_type")

        if order_type in ["limit", "stop"] and not attrs.get("price"):
            raise serializers.ValidationError(f"Price is required for {order_type} orders")

        if order_type == "oco" and (not attrs.get("limit_price") or not attrs.get("stop_price")):
            raise serializers.ValidationError(
                "Both limit_price and stop_price are required for OCO orders"
            )

        return attrs
