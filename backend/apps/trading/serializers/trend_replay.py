"""Trend replay serializers."""

from rest_framework import serializers

from apps.trading.serializers.events import PositionSerializer, TradeSerializer


class TaskTrendReplayMetaSerializer(serializers.Serializer):
    """Metadata for a trend replay payload."""

    mode = serializers.CharField()
    page = serializers.IntegerField()
    page_size = serializers.IntegerField()
    total_trades = serializers.IntegerField()
    returned_trades = serializers.IntegerField()
    has_more_trades = serializers.BooleanField()
    latest_trade_updated_at = serializers.DateTimeField(allow_null=True)
    range_from = serializers.DateTimeField(allow_null=True)
    range_to = serializers.DateTimeField(allow_null=True)


class TaskTrendReplaySerializer(serializers.Serializer):
    """Combined trend replay payload for the chart view."""

    trades = TradeSerializer(many=True)
    positions = PositionSerializer(many=True)
    meta = TaskTrendReplayMetaSerializer()
