"""Serializers for tick data."""

from decimal import Decimal

from rest_framework import serializers

from apps.market.models import TickData


class TickDataSerializer(serializers.ModelSerializer):
    """
    Serializer for tick data retrieval.

    Provides read-only access to historical tick data with all fields.
    """

    spread = serializers.SerializerMethodField()

    def get_spread(self, obj: TickData) -> Decimal:
        return obj.spread

    class Meta:  # pylint: disable=missing-class-docstring,too-few-public-methods
        model = TickData
        fields = [
            "id",
            "instrument",
            "timestamp",
            "bid",
            "ask",
            "mid",
            "spread",
            "created_at",
        ]
        read_only_fields = fields


class TickDataCSVSerializer(serializers.ModelSerializer):
    """
    Serializer for tick data CSV export.

    Provides a simplified format optimized for backtesting and analysis.
    """

    spread = serializers.SerializerMethodField()

    def get_spread(self, obj: TickData) -> Decimal:
        return obj.spread

    class Meta:  # pylint: disable=missing-class-docstring,too-few-public-methods
        model = TickData
        fields = [
            "timestamp",
            "instrument",
            "bid",
            "ask",
            "mid",
            "spread",
        ]
        read_only_fields = fields
