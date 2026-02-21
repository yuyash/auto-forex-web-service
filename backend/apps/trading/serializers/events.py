"""Event serializers for trading app."""

from __future__ import annotations

from typing import Any, cast

from rest_framework import serializers

from apps.trading.enums import Direction, EventType
from apps.trading.models import TradingEvent


class TradingEventSerializer(serializers.ModelSerializer):
    """Serializer for TradingEvent model."""

    event_type = serializers.ChoiceField(choices=EventType.choices)
    event_type_display = serializers.SerializerMethodField(
        help_text="Human-readable display name for the event type.",
    )

    class Meta:
        model = TradingEvent
        fields = [
            "id",
            "event_type",
            "event_type_display",
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
        read_only_fields = ["id", "event_type_display", "created_at"]

    def get_event_type_display(self, obj: TradingEvent) -> str:
        """Return the human-readable label for the event type."""
        try:
            return EventType(obj.event_type).label
        except ValueError:
            return obj.event_type


class TradeSerializer(serializers.Serializer):
    """Serializer for trade data from Trades model."""

    direction = serializers.ChoiceField(choices=Direction.choices)
    units = serializers.IntegerField()
    instrument = serializers.CharField()
    price = serializers.DecimalField(max_digits=20, decimal_places=10)
    execution_method = serializers.ChoiceField(choices=EventType.choices)
    execution_method_display = serializers.SerializerMethodField(
        help_text="Human-readable display name for the execution method.",
    )
    layer_index = serializers.IntegerField(required=False, allow_null=True)
    retracement_count = serializers.IntegerField(required=False, allow_null=True)
    timestamp = serializers.DateTimeField()

    def get_execution_method_display(self, obj: object) -> str:
        """Return the human-readable label for the execution method."""
        value = getattr(obj, "execution_method", None)
        if not value and isinstance(obj, dict):
            value = cast(dict[str, Any], obj).get("execution_method")
        if not value:
            return ""
        try:
            return EventType(value).label
        except ValueError:
            return value


class PositionSerializer(serializers.Serializer):
    """Serializer for position data from Position model."""

    id = serializers.UUIDField()
    instrument = serializers.CharField()
    direction = serializers.CharField()
    units = serializers.IntegerField()
    entry_price = serializers.DecimalField(max_digits=20, decimal_places=10)
    entry_time = serializers.DateTimeField()
    exit_price = serializers.DecimalField(
        max_digits=20, decimal_places=10, required=False, allow_null=True
    )
    exit_time = serializers.DateTimeField(required=False, allow_null=True)
    realized_pnl = serializers.DecimalField(
        max_digits=20, decimal_places=10, required=False, allow_null=True
    )
    is_open = serializers.BooleanField()
    layer_index = serializers.IntegerField(required=False, allow_null=True)
