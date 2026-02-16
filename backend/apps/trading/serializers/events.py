"""Event serializers for trading app."""

from rest_framework import serializers

from apps.trading.enums import Direction
from apps.trading.models import TradingEvent


class TradingEventSerializer(serializers.ModelSerializer):
    """Serializer for TradingEvent model."""

    class Meta:
        model = TradingEvent
        fields = [
            "id",
            "event_type",
            "severity",
            "description",
            "user",
            "account",
            "instrument",
            "task_type",
            "task_id",
            "celery_task_id",
            "details",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class TradeSerializer(serializers.Serializer):
    """Serializer for trade data from Trades model."""

    direction = serializers.ChoiceField(choices=Direction.choices)
    units = serializers.IntegerField()
    instrument = serializers.CharField()
    price = serializers.DecimalField(max_digits=20, decimal_places=10)
    execution_method = serializers.CharField()
    layer_index = serializers.IntegerField(required=False, allow_null=True)
    pnl = serializers.DecimalField(
        max_digits=20, decimal_places=10, required=False, allow_null=True
    )
    timestamp = serializers.DateTimeField()
