"""Serializers for trading tasks."""

import logging

from rest_framework import serializers

from apps.market.models import OandaAccounts
from apps.trading.models import StrategyConfiguration, TradingTask

logger = logging.getLogger(__name__)


class TradingTaskSerializer(serializers.ModelSerializer):
    """
    Serializer for TradingTask full details.
    """

    user_id = serializers.IntegerField(source="user.id", read_only=True)
    config_id = serializers.UUIDField(source="config.id", read_only=True)
    config_name = serializers.CharField(source="config.name", read_only=True)
    strategy_type = serializers.CharField(source="config.strategy_type", read_only=True)
    instrument = serializers.SerializerMethodField()
    account_id = serializers.IntegerField(source="oanda_account.id", read_only=True)
    account_name = serializers.CharField(source="oanda_account.account_id", read_only=True)
    account_type = serializers.CharField(source="oanda_account.api_type", read_only=True)
    # State management fields for frontend button logic
    has_strategy_state = serializers.SerializerMethodField()
    can_resume = serializers.SerializerMethodField()

    class Meta:
        model = TradingTask
        fields = [
            "id",
            "user_id",
            "config_id",
            "config_name",
            "strategy_type",
            "instrument",
            "account_id",
            "account_name",
            "account_type",
            "name",
            "description",
            "sell_on_stop",
            "dry_run",
            "hedging_enabled",
            "pip_size",
            "status",
            # State management fields
            "has_strategy_state",
            "can_resume",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "user_id",
            "config_id",
            "config_name",
            "strategy_type",
            "instrument",
            "account_id",
            "account_name",
            "account_type",
            "status",
            "pip_size",
            "has_strategy_state",
            "can_resume",
            "created_at",
            "updated_at",
        ]

    def get_instrument(self, obj: TradingTask) -> str:
        """Get instrument from configuration parameters."""
        if obj.config and obj.config.parameters:
            instrument = obj.config.parameters.get("instrument")
            if instrument:
                return str(instrument)
        return "EUR_USD"

    def get_has_strategy_state(self, obj: TradingTask) -> bool:
        """Check if task has saved strategy state."""
        return obj.has_strategy_state()

    def get_can_resume(self, obj: TradingTask) -> bool:
        """Check if task can be resumed with state recovery."""
        return obj.can_resume()


class TradingTaskListSerializer(serializers.ModelSerializer):
    """
    Serializer for TradingTask list view (summary only).
    """

    user_id = serializers.IntegerField(source="user.id", read_only=True)
    config_id = serializers.UUIDField(source="config.id", read_only=True)
    config_name = serializers.CharField(source="config.name", read_only=True)
    strategy_type = serializers.CharField(source="config.strategy_type", read_only=True)
    instrument = serializers.SerializerMethodField()
    account_id = serializers.IntegerField(source="oanda_account.id", read_only=True)
    account_name = serializers.CharField(source="oanda_account.account_id", read_only=True)
    account_type = serializers.CharField(source="oanda_account.api_type", read_only=True)

    class Meta:
        model = TradingTask
        fields = [
            "id",
            "user_id",
            "config_id",
            "config_name",
            "strategy_type",
            "instrument",
            "account_id",
            "account_name",
            "account_type",
            "name",
            "description",
            "sell_on_stop",
            "dry_run",
            "hedging_enabled",
            "pip_size",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_instrument(self, obj: TradingTask) -> str:
        """Get instrument from configuration parameters."""
        if obj.config and obj.config.parameters:
            instrument = obj.config.parameters.get("instrument")
            if instrument:
                return str(instrument)
        return "EUR_USD"


class TradingTaskCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating and updating TradingTask.

    Accepts config_id and account_id from the frontend, mapping them
    to the config and oanda_account FK fields.
    """

    config_id = serializers.PrimaryKeyRelatedField(
        queryset=StrategyConfiguration.objects.all(),
        source="config",
        required=False,
    )
    account_id = serializers.PrimaryKeyRelatedField(
        queryset=OandaAccounts.objects.all(),
        source="oanda_account",
        required=False,
    )

    class Meta:
        model = TradingTask
        fields = [
            "config_id",
            "account_id",
            "name",
            "description",
            "sell_on_stop",
            "dry_run",
            "hedging_enabled",
        ]
        extra_kwargs = {
            "name": {"required": False},
            "description": {"required": False},
            "sell_on_stop": {"required": False},
            "dry_run": {"required": False},
            "hedging_enabled": {"required": False},
        }

    def validate_config_id(self, value: StrategyConfiguration) -> StrategyConfiguration:
        """Validate that config belongs to the user."""
        user = self.context["request"].user
        if value.user != user:
            raise serializers.ValidationError("Configuration does not belong to the current user")
        return value

    def validate_account_id(self, value: OandaAccounts) -> OandaAccounts:
        """Validate that account belongs to the user and is active."""
        user = self.context["request"].user
        if value.user != user:
            raise serializers.ValidationError("Account does not belong to the current user")
        if not value.is_active:
            raise serializers.ValidationError("Account is not active")
        return value

    def validate(self, attrs: dict) -> dict:
        """Validate configuration parameters."""
        # On create, config and oanda_account are required
        if not self.instance:
            if "config" not in attrs:
                raise serializers.ValidationError({"config_id": "This field is required."})
            if "oanda_account" not in attrs:
                raise serializers.ValidationError({"account_id": "This field is required."})

        # Validate hedging: if hedging_enabled, check account supports hedging
        hedging_enabled = attrs.get("hedging_enabled", True)
        oanda_account = attrs.get("oanda_account") or (
            self.instance.oanda_account if self.instance else None
        )
        if hedging_enabled and oanda_account:
            try:
                from apps.market.services.oanda import OandaService

                client = OandaService(oanda_account)
                account_resource = client.get_account_resource()
                account_hedging = bool(account_resource.get("hedgingEnabled", False))
                if not account_hedging:
                    raise serializers.ValidationError(
                        {
                            "hedging_enabled": (
                                "This OANDA account does not support hedging. "
                                "Disable hedging or use a hedging-enabled account."
                            )
                        }
                    )
            except serializers.ValidationError:
                raise
            except Exception as e:
                logger.warning(
                    "Failed to check hedging support for account %s: %s",
                    oanda_account.account_id,
                    e,
                )

        # Validate configuration parameters
        config = attrs.get("config")
        if config:
            is_valid, error_message = config.validate_parameters()
            if not is_valid:
                raise serializers.ValidationError({"config_id": error_message})

        return attrs

    def create(self, validated_data: dict) -> TradingTask:
        """Create trading task with user from context."""
        from apps.trading.utils import pip_size_for_instrument

        user = self.context["request"].user
        validated_data["user"] = user

        # Set instrument and pip_size from config if not explicitly provided
        config = validated_data.get("config")
        if config and config.parameters:
            instrument = config.parameters.get("instrument")
            if instrument:
                validated_data.setdefault("instrument", instrument)
                # Derive pip_size from instrument (JPY pairs use 0.01, others use 0.0001)
                validated_data.setdefault("pip_size", pip_size_for_instrument(instrument))

        return TradingTask.objects.create(**validated_data)

    def update(self, instance: TradingTask, validated_data: dict) -> TradingTask:
        """Update trading task."""
        # Don't allow updating if task is running
        if instance.status == "running":
            raise serializers.ValidationError("Cannot update a running task. Stop it first.")

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
