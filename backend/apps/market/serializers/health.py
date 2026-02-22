"""Health status serializer."""

from rest_framework import serializers

from apps.market.models import OandaApiHealthStatus


class OandaApiHealthStatusSerializer(serializers.ModelSerializer):
    oanda_account_id = serializers.CharField(source="account.account_id", read_only=True)
    api_type = serializers.CharField(source="account.api_type", read_only=True)

    class Meta:
        model = OandaApiHealthStatus
        fields = [
            "id",
            "account",
            "oanda_account_id",
            "api_type",
            "is_available",
            "checked_at",
            "latency_ms",
            "http_status",
            "error_message",
        ]
        read_only_fields = fields
