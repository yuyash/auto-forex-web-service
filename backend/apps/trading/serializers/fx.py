"""Serializers for FX conversion endpoints."""

from decimal import Decimal

from rest_framework import serializers


def _normalize_currency(value: str, *, field_name: str) -> str:
    currency = str(value or "").strip().upper()
    if len(currency) != 3 or not currency.isalpha():
        raise serializers.ValidationError(f"{field_name} must be a 3-letter currency code")
    return currency


class FxRateQuerySerializer(serializers.Serializer):
    """Query parameters for resolving a display-currency FX rate."""

    source_currency = serializers.CharField(max_length=3)
    target_currency = serializers.CharField(max_length=3)
    instrument = serializers.CharField(required=False, allow_blank=True, max_length=20)
    mid_price = serializers.DecimalField(
        required=False,
        max_digits=20,
        decimal_places=10,
        min_value=Decimal("0.0000000001"),
    )
    as_of = serializers.DateTimeField(required=False)

    def validate_source_currency(self, value: str) -> str:
        """Normalize source currency."""
        return _normalize_currency(value, field_name="source_currency")

    def validate_target_currency(self, value: str) -> str:
        """Normalize target currency."""
        return _normalize_currency(value, field_name="target_currency")


class FxRateResponseSerializer(serializers.Serializer):
    """Response for a resolved FX conversion rate."""

    source_currency = serializers.CharField(max_length=3)
    target_currency = serializers.CharField(max_length=3)
    rate = serializers.DecimalField(max_digits=24, decimal_places=12)
    instrument = serializers.CharField(allow_blank=True)
    as_of = serializers.DateTimeField(allow_null=True)
    source = serializers.CharField()
    path = serializers.ListField(child=serializers.CharField())
