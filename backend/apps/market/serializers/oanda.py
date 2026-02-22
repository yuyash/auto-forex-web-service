"""OANDA account serializer."""

from typing import Any

from rest_framework import serializers

from apps.market.enums import ApiType, Jurisdiction
from apps.market.models import OandaAccounts


class OandaAccountsSerializer(serializers.ModelSerializer):
    """
    Serializer for OANDA account.
    """

    api_token = serializers.CharField(
        write_only=True,
        required=True,
        help_text="OANDA API token (will be encrypted)",
    )

    class Meta:
        model = OandaAccounts
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

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:  # pylint: disable=arguments-differ
        attrs = super().validate(attrs)

        request = self.context.get("request")
        user = request.user if request and hasattr(request, "user") else None
        if not (user and getattr(user, "is_authenticated", False)):
            return attrs

        # Enforce uniqueness on (user, account_id, api_type). Duplicates are allowed
        # across different api_type values.
        account_id = attrs.get("account_id") or getattr(self.instance, "account_id", None)
        api_type = attrs.get("api_type") or getattr(self.instance, "api_type", None)

        if account_id and api_type:
            qs = OandaAccounts.objects.filter(user=user, account_id=account_id, api_type=api_type)
            if self.instance is not None and getattr(self.instance, "pk", None) is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {
                        "account_id": [
                            "You already have an account with this account ID for this API type."
                        ]
                    }
                )

        return attrs

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

    def create(self, validated_data: dict[str, Any]) -> OandaAccounts:
        api_token = validated_data.pop("api_token")
        is_default = validated_data.pop("is_default", False)
        request = self.context.get("request")
        if not request or not hasattr(request, "user"):
            raise serializers.ValidationError("User context is required")
        user = request.user
        existing_accounts_count = OandaAccounts.objects.filter(user=user).count()
        if existing_accounts_count == 0:
            is_default = True
        account = OandaAccounts.objects.create(user=user, **validated_data)
        account.set_api_token(api_token)
        account.save()
        if is_default:
            account.set_as_default()
        return account

    def update(self, instance: OandaAccounts, validated_data: dict[str, Any]) -> OandaAccounts:
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
