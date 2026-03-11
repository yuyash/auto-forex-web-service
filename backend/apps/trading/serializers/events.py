"""Event serializers for trading app."""

from __future__ import annotations

from typing import Any, cast

from rest_framework import serializers

from apps.trading.enums import Direction, EventType
from apps.trading.models import StrategyEventRecord, TradingEvent


class TradingEventSerializer(serializers.ModelSerializer):
    """Serializer for TradingEvent model."""

    event_type = serializers.ChoiceField(choices=EventType.choices)
    event_type_display = serializers.SerializerMethodField(
        help_text="Human-readable display name for the event type.",
    )
    event_scope = serializers.SerializerMethodField(
        help_text="Event scope: trading or task.",
    )

    class Meta:
        model = TradingEvent
        fields = [
            "id",
            "event_type",
            "event_type_display",
            "event_scope",
            "severity",
            "description",
            "user",
            "account",
            "instrument",
            "task_type",
            "task_id",
            "execution_id",
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

    def get_event_scope(self, obj: TradingEvent) -> str:
        details = obj.details if isinstance(obj.details, dict) else {}
        return EventType.scope_of(obj.event_type, details=details)


class StrategyEventSerializer(serializers.ModelSerializer):
    """Serializer for strategy-internal events."""

    event_type_display = serializers.SerializerMethodField(
        help_text="Human-readable display name for the event type.",
    )
    event_scope = serializers.CharField(default="strategy", read_only=True)

    class Meta:
        model = StrategyEventRecord
        fields = [
            "id",
            "event_type",
            "event_type_display",
            "event_scope",
            "severity",
            "description",
            "user",
            "account",
            "instrument",
            "task_type",
            "task_id",
            "execution_id",
            "details",
            "created_at",
        ]
        read_only_fields = ["id", "event_type_display", "event_scope", "created_at"]

    def get_event_type_display(self, obj: StrategyEventRecord) -> str:
        try:
            return EventType(obj.event_type).label
        except ValueError:
            return obj.event_type


class TradeSerializer(serializers.Serializer):
    """Serializer for trade data from Trades model."""

    id = serializers.UUIDField(required=False)
    direction = serializers.ChoiceField(choices=Direction.choices, allow_null=True)
    units = serializers.IntegerField()
    instrument = serializers.CharField()
    price = serializers.DecimalField(max_digits=20, decimal_places=10)
    execution_method = serializers.ChoiceField(choices=EventType.choices)
    execution_method_display = serializers.SerializerMethodField(
        help_text="Human-readable display name for the execution method.",
    )
    layer_index = serializers.IntegerField(required=False, allow_null=True)
    retracement_count = serializers.IntegerField(required=False, allow_null=True)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    timestamp = serializers.DateTimeField()
    position_id = serializers.UUIDField(required=False, allow_null=True)
    updated_at = serializers.DateTimeField(required=False, allow_null=True)

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
    is_open = serializers.BooleanField()
    layer_index = serializers.IntegerField(required=False, allow_null=True)
    retracement_count = serializers.IntegerField(required=False, allow_null=True)
    planned_exit_price = serializers.DecimalField(
        max_digits=20, decimal_places=10, required=False, allow_null=True
    )
    trade_ids = serializers.SerializerMethodField()
    updated_at = serializers.DateTimeField(required=False, allow_null=True)

    def get_trade_ids(self, obj: object) -> list[str]:
        """Return the IDs of trades linked to this position."""
        if hasattr(obj, "prefetched_trade_ids"):
            return obj.prefetched_trade_ids  # type: ignore[return-value]
        if hasattr(obj, "trades"):
            return list(obj.trades.values_list("id", flat=True))  # type: ignore[union-attr]
        return []


class OrderSerializer(serializers.Serializer):
    """Serializer for order data from Order model."""

    id = serializers.UUIDField()
    broker_order_id = serializers.CharField(required=False, allow_null=True)
    oanda_trade_id = serializers.CharField(required=False, allow_null=True)
    position_id = serializers.UUIDField(required=False, allow_null=True)
    instrument = serializers.CharField()
    order_type = serializers.CharField()
    direction = serializers.CharField(required=False, allow_null=True)
    units = serializers.IntegerField()
    requested_price = serializers.DecimalField(
        max_digits=20, decimal_places=10, required=False, allow_null=True
    )
    fill_price = serializers.DecimalField(
        max_digits=20, decimal_places=10, required=False, allow_null=True
    )
    status = serializers.CharField()
    submitted_at = serializers.DateTimeField()
    filled_at = serializers.DateTimeField(required=False, allow_null=True)
    cancelled_at = serializers.DateTimeField(required=False, allow_null=True)
    stop_loss = serializers.DecimalField(
        max_digits=20, decimal_places=10, required=False, allow_null=True
    )
    error_message = serializers.CharField(required=False, allow_null=True)
    is_dry_run = serializers.BooleanField()
    layer_index = serializers.IntegerField(required=False, allow_null=True)
    retracement_count = serializers.IntegerField(required=False, allow_null=True)
