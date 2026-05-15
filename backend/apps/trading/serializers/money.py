"""Shared serializers for currency-aware amounts."""

from rest_framework import serializers


class MoneySerializer(serializers.Serializer):
    """Serializer for a numeric amount paired with its currency code."""

    amount = serializers.DecimalField(max_digits=24, decimal_places=10)
    currency = serializers.CharField(max_length=3, allow_blank=True)


class TaskMoneyContextSerializer(serializers.Serializer):
    """Serializer for task-level money and display-currency context."""

    task_type = serializers.CharField()
    account_currency = serializers.CharField(max_length=3, allow_blank=True)
    account_currency_source = serializers.CharField()
    display_currency = serializers.CharField(max_length=3, allow_blank=True)
    display_currency_source = serializers.CharField()
    currency_options = serializers.ListField(child=serializers.CharField(max_length=3))
    initial_balance_money = MoneySerializer(allow_null=True, required=False)
    commission_per_trade_money = MoneySerializer(allow_null=True, required=False)
    display_uses_account_currency = serializers.BooleanField()
    display_requires_conversion = serializers.BooleanField()
    conversion_policy = serializers.CharField()


class CurrencyConversionContextSerializer(serializers.Serializer):
    """Serializer for display-currency conversion metadata."""

    source_currency = serializers.CharField(max_length=3, allow_blank=True)
    target_currency = serializers.CharField(max_length=3, allow_blank=True)
    rate = serializers.DecimalField(
        max_digits=24,
        decimal_places=12,
        allow_null=True,
        required=False,
    )
    rate_source = serializers.CharField()
    rate_as_of = serializers.DateTimeField(allow_null=True, required=False)
    rate_path = serializers.ListField(child=serializers.CharField())
    conversion_available = serializers.BooleanField()
    conversion_policy = serializers.CharField()
