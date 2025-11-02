"""
Serializers for trading data.

This module contains serializers for:
- Tick data retrieval and export

Requirements: 7.1, 7.2, 12.1
"""

from rest_framework import serializers

from .tick_data_models import TickData


class TickDataSerializer(serializers.ModelSerializer):
    """
    Serializer for tick data retrieval.

    Provides read-only access to historical tick data with all fields.

    Requirements: 7.1, 7.2, 12.1
    """

    account_id = serializers.IntegerField(source="account.id", read_only=True)
    account_name = serializers.CharField(source="account.account_id", read_only=True)

    class Meta:
        model = TickData
        fields = [
            "id",
            "account_id",
            "account_name",
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

    Requirements: 7.1, 7.2, 12.1
    """

    class Meta:
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
