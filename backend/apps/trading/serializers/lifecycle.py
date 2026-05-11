"""Serializers for task position lifecycle payloads."""

from __future__ import annotations

from rest_framework import serializers

from apps.trading.serializers.money import CurrencyConversionContextSerializer, MoneySerializer


class PositionLifecycleRealizedPnlFieldsSerializer(serializers.Serializer):
    """Shared realized-PnL money fields for lifecycle events and summaries."""

    realized_pnl = serializers.CharField(required=False, allow_null=True)
    realized_pnl_currency = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    realized_pnl_money = MoneySerializer(required=False, allow_null=True)
    realized_pnl_display_money = MoneySerializer(required=False, allow_null=True)
    realized_pnl_display_conversion_context = CurrencyConversionContextSerializer(
        required=False,
        allow_null=True,
    )


class PositionLifecycleEventSerializer(PositionLifecycleRealizedPnlFieldsSerializer):
    """Serializer for one point in a position lifecycle timeline."""

    id = serializers.CharField()
    kind = serializers.CharField()
    timestamp = serializers.DateTimeField(required=False, allow_null=True)
    position_id = serializers.UUIDField()
    related_position_id = serializers.UUIDField(required=False, allow_null=True)
    direction = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    units = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    entry_price = serializers.CharField(required=False, allow_null=True)
    exit_price = serializers.CharField(required=False, allow_null=True)
    planned_exit_price = serializers.CharField(required=False, allow_null=True)
    planned_exit_price_formula = serializers.CharField(required=False, allow_null=True)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    close_reason = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class PositionLifecycleSummarySerializer(PositionLifecycleRealizedPnlFieldsSerializer):
    """Serializer for one position summary within a lifecycle chain."""

    position_id = serializers.UUIDField()
    direction = serializers.CharField()
    units = serializers.IntegerField()
    is_open = serializers.BooleanField()
    is_rebuild = serializers.BooleanField()
    instrument = serializers.CharField()
    layer_index = serializers.IntegerField(required=False, allow_null=True)
    retracement_count = serializers.IntegerField(required=False, allow_null=True)
    entry_price = serializers.CharField()
    entry_time = serializers.DateTimeField(required=False, allow_null=True)
    exit_price = serializers.CharField(required=False, allow_null=True)
    exit_time = serializers.DateTimeField(required=False, allow_null=True)
    planned_exit_price = serializers.CharField(required=False, allow_null=True)
    planned_exit_price_formula = serializers.CharField(required=False, allow_null=True)
    stop_loss_price = serializers.CharField(required=False, allow_null=True)
    close_reason = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class PositionLifecycleItemSerializer(serializers.Serializer):
    """Serializer for a position and its lifecycle timeline."""

    position_id = serializers.UUIDField()
    original_position_id = serializers.UUIDField(required=False, allow_null=True)
    rebuilt_position_ids = serializers.ListField(child=serializers.UUIDField())
    summary = PositionLifecycleSummarySerializer()
    events = PositionLifecycleEventSerializer(many=True)


class PositionLifecycleResponseSerializer(serializers.Serializer):
    """Serializer for a complete position lifecycle chain response."""

    requested_position_id = serializers.CharField()
    matched_position_id = serializers.UUIDField()
    position_ids = serializers.ListField(child=serializers.UUIDField())
    positions = PositionLifecycleItemSerializer(many=True)
    chain_realized_pnl = serializers.CharField(allow_null=True)
    chain_realized_pnl_currency = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    chain_realized_pnl_money = MoneySerializer(required=False, allow_null=True)
    chain_realized_pnl_display_money = MoneySerializer(required=False, allow_null=True)
    chain_realized_pnl_display_conversion_context = CurrencyConversionContextSerializer(
        required=False,
        allow_null=True,
    )
