"""Shared serializers for currency-aware amounts."""

from rest_framework import serializers


class MoneySerializer(serializers.Serializer):
    """Serializer for a numeric amount paired with its currency code."""

    amount = serializers.DecimalField(max_digits=24, decimal_places=10)
    currency = serializers.CharField(max_length=3, allow_blank=True)
