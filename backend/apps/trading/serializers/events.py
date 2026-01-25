"""Event serializers for trading app."""

from rest_framework import serializers

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
            "details",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class TradeSerializer(serializers.Serializer):
    """Serializer for trade data from ExecutionTrade model."""

    direction = serializers.ChoiceField(choices=["long", "short"])
    units = serializers.IntegerField()
    entry_price = serializers.DecimalField(max_digits=20, decimal_places=5)
    exit_price = serializers.DecimalField(
        max_digits=20, decimal_places=5, required=False, allow_null=True
    )
    pnl = serializers.DecimalField(max_digits=20, decimal_places=5, required=False, allow_null=True)
    pips = serializers.DecimalField(
        max_digits=20, decimal_places=5, required=False, allow_null=True
    )
    entry_timestamp = serializers.DateTimeField()
    exit_timestamp = serializers.DateTimeField(required=False, allow_null=True)
    exit_reason = serializers.CharField(required=False, allow_null=True)


class EquityPointSerializer(serializers.Serializer):
    """Serializer for equity curve data points from ExecutionEquity model."""

    timestamp = serializers.DateTimeField()
    balance = serializers.DecimalField(max_digits=20, decimal_places=2)
