"""Position serializer."""

from decimal import Decimal

from rest_framework import serializers


class PositionSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    """Serializer for opening a position via a market order."""

    instrument = serializers.CharField(required=True, max_length=10)
    direction = serializers.ChoiceField(required=True, choices=["long", "short"])
    units = serializers.DecimalField(
        required=True,
        max_digits=15,
        decimal_places=2,
        min_value=Decimal("0.01"),
    )
    take_profit = serializers.DecimalField(
        required=False,
        allow_null=True,
        max_digits=10,
        decimal_places=5,
    )
    stop_loss = serializers.DecimalField(
        required=False,
        allow_null=True,
        max_digits=10,
        decimal_places=5,
    )
