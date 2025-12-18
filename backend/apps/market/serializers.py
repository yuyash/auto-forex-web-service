"""
Serializers for OANDA account (moved from accounts).
"""

from decimal import Decimal
from typing import Any

from rest_framework import serializers
from apps.market.models import OandaAccount, OandaApiHealthStatus
from apps.market.enums import ApiType, Jurisdiction


class OandaAccountSerializer(serializers.ModelSerializer):
    """
    Serializer for OANDA account.
    """

    api_token = serializers.CharField(
        write_only=True,
        required=True,
        help_text="OANDA API token (will be encrypted)",
    )

    class Meta:
        model = OandaAccount
        fields = [
            "id",
            "account_id",
            "api_token",
            "api_type",
            "jurisdiction",
            "currency",
            "balance",
            "margin_used",
            "margin_available",
            "unrealized_pnl",
            "is_active",
            "is_default",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "balance",
            "margin_used",
            "margin_available",
            "unrealized_pnl",
            "created_at",
            "updated_at",
        ]

    def validate_account_id(self, value: str) -> str:
        request = self.context.get("request")
        user = request.user if request and hasattr(request, "user") else None
        if (
            user
            and hasattr(user, "is_authenticated")
            and user.is_authenticated
            and OandaAccount.objects.filter(user=user, account_id=value).exists()
        ):
            raise serializers.ValidationError("You already have an account with this account ID.")
        return value

    def validate_api_type(self, value: str) -> str:
        if value not in ApiType.values:
            raise serializers.ValidationError(
                f"API type must be one of: {', '.join(ApiType.values)}"
            )
        return value

    def validate_jurisdiction(self, value: str) -> str:
        if value not in Jurisdiction.values:
            raise serializers.ValidationError(
                f"Jurisdiction must be one of: {', '.join(Jurisdiction.values)}"
            )
        return value

    def create(self, validated_data: dict[str, Any]) -> OandaAccount:
        api_token = validated_data.pop("api_token")
        is_default = validated_data.pop("is_default", False)
        request = self.context.get("request")
        if not request or not hasattr(request, "user"):
            raise serializers.ValidationError("User context is required")
        user = request.user
        existing_accounts_count = OandaAccount.objects.filter(user=user).count()
        if existing_accounts_count == 0:
            is_default = True
        account = OandaAccount.objects.create(user=user, **validated_data)
        account.set_api_token(api_token)
        account.save()
        if is_default:
            account.set_as_default()
        return account

    def update(self, instance: OandaAccount, validated_data: dict[str, Any]) -> OandaAccount:
        api_token = validated_data.pop("api_token", None)
        is_default = validated_data.pop("is_default", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if api_token:
            instance.set_api_token(api_token)
        if is_default is not None and is_default != instance.is_default:
            if is_default:
                instance.set_as_default()
            else:
                instance.is_default = False
                instance.save()
        else:
            instance.save()
        return instance


class PositionSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    """Serializer for opening a position via a market order."""

    instrument = serializers.CharField(required=True, max_length=10)
    direction = serializers.ChoiceField(required=True, choices=["long", "short"])
    units = serializers.DecimalField(
        required=True,
        max_digits=15,
        decimal_places=2,
        min_value=Decimal("0.01"),
    )
    take_profit = serializers.DecimalField(
        required=False,
        allow_null=True,
        max_digits=10,
        decimal_places=5,
    )
    stop_loss = serializers.DecimalField(
        required=False,
        allow_null=True,
        max_digits=10,
        decimal_places=5,
    )


class OrderSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    """Serializer for creating orders."""

    instrument = serializers.CharField(
        required=True,
        max_length=10,
        help_text="Currency pair (e.g., 'EUR_USD')",
    )
    order_type = serializers.ChoiceField(
        required=True,
        choices=["market", "limit", "stop", "oco"],
        help_text="Type of order",
    )
    direction = serializers.ChoiceField(
        required=True,
        choices=["long", "short"],
        help_text="Trade direction",
    )
    units = serializers.DecimalField(
        required=True,
        max_digits=15,
        decimal_places=2,
        min_value=Decimal("0.01"),
        help_text="Number of units to trade",
    )
    price = serializers.DecimalField(
        required=False,
        allow_null=True,
        max_digits=10,
        decimal_places=5,
        help_text="Order price (required for limit/stop orders)",
    )
    take_profit = serializers.DecimalField(
        required=False,
        allow_null=True,
        max_digits=10,
        decimal_places=5,
        help_text="Take-profit price",
    )
    stop_loss = serializers.DecimalField(
        required=False,
        allow_null=True,
        max_digits=10,
        decimal_places=5,
        help_text="Stop-loss price",
    )
    limit_price = serializers.DecimalField(
        required=False,
        allow_null=True,
        max_digits=10,
        decimal_places=5,
        help_text="Limit price (for OCO orders)",
    )
    stop_price = serializers.DecimalField(
        required=False,
        allow_null=True,
        max_digits=10,
        decimal_places=5,
        help_text="Stop price (for OCO orders)",
    )

    def validate(
        self, attrs: dict[str, Any]
    ) -> dict[str, Any]:  # pylint: disable=arguments-renamed
        """Validate order data based on order type."""
        order_type = attrs.get("order_type")

        if order_type in ["limit", "stop"] and not attrs.get("price"):
            raise serializers.ValidationError(f"Price is required for {order_type} orders")

        if order_type == "oco" and (not attrs.get("limit_price") or not attrs.get("stop_price")):
            raise serializers.ValidationError(
                "Both limit_price and stop_price are required for OCO orders"
            )

        return attrs


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
