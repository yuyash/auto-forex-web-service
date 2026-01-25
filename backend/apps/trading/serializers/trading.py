"""Serializers for trading tasks."""

from rest_framework import serializers

from apps.market.models import OandaAccounts
from apps.trading.models import StrategyConfigurations, TradingTasks


class TradingTaskSerializer(serializers.ModelSerializer):
    """
    Serializer for TradingTask full details.
    """

    user_id = serializers.IntegerField(source="user.id", read_only=True)
    config_id = serializers.IntegerField(source="config.id", read_only=True)
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
        model = TradingTasks
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
            "has_strategy_state",
            "can_resume",
            "created_at",
            "updated_at",
        ]

    def get_instrument(self, obj: TradingTasks) -> str:
        """Get instrument from configuration parameters."""
        if obj.config and obj.config.parameters:
            instrument = obj.config.parameters.get("instrument")
            if instrument:
                return str(instrument)
        return "EUR_USD"

    def get_has_strategy_state(self, obj: TradingTasks) -> bool:
        """Check if task has saved strategy state."""
        return obj.has_strategy_state()

    def get_can_resume(self, obj: TradingTasks) -> bool:
        """Check if task can be resumed with state recovery."""
        return obj.can_resume()


class TradingTaskListSerializer(serializers.ModelSerializer):
    """
    Serializer for TradingTask list view (summary only).
    """

    user_id = serializers.IntegerField(source="user.id", read_only=True)
    config_id = serializers.IntegerField(source="config.id", read_only=True)
    config_name = serializers.CharField(source="config.name", read_only=True)
    strategy_type = serializers.CharField(source="config.strategy_type", read_only=True)
    instrument = serializers.SerializerMethodField()
    account_id = serializers.IntegerField(source="oanda_account.id", read_only=True)
    account_name = serializers.CharField(source="oanda_account.account_id", read_only=True)
    account_type = serializers.CharField(source="oanda_account.api_type", read_only=True)

    class Meta:
        model = TradingTasks
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
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_instrument(self, obj: TradingTasks) -> str:
        """Get instrument from configuration parameters."""
        if obj.config and obj.config.parameters:
            instrument = obj.config.parameters.get("instrument")
            if instrument:
                return str(instrument)
        return "EUR_USD"


class TradingTaskCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating and updating TradingTask.

    Includes validation for account ownership and configuration.
    """

    class Meta:
        model = TradingTasks
        fields = [
            "config",
            "oanda_account",
            "name",
            "description",
            "sell_on_stop",
        ]
        # Make fields optional for partial updates (PATCH)
        extra_kwargs = {
            "config": {"required": False},
            "oanda_account": {"required": False},
            "name": {"required": False},
            "description": {"required": False},
            "sell_on_stop": {"required": False},
        }

    def validate_config(self, value: StrategyConfigurations) -> StrategyConfigurations:
        """Validate that config belongs to the user."""
        user = self.context["request"].user
        if value.user != user:
            raise serializers.ValidationError("Configuration does not belong to the current user")
        return value

    def validate_oanda_account(self, value: OandaAccounts) -> OandaAccounts:
        """Validate that account belongs to the user and is active."""
        user = self.context["request"].user
        if value.user != user:
            raise serializers.ValidationError("Account does not belong to the current user")
        if not value.is_active:
            raise serializers.ValidationError("Account is not active")
        return value

    def validate(self, attrs: dict) -> dict:
        """Validate configuration parameters."""
        # Validate configuration parameters
        config = attrs.get("config")
        if config:
            is_valid, error_message = config.validate_parameters()
            if not is_valid:
                raise serializers.ValidationError({"config": error_message})

            # Validate configuration has instrument parameter
            if not config.parameters.get("instrument"):
                raise serializers.ValidationError(
                    {"config": "Configuration must have an instrument parameter"}
                )

        return attrs

    def create(self, validated_data: dict) -> TradingTasks:
        """Create trading task with user from context."""
        user = self.context["request"].user
        validated_data["user"] = user
        return TradingTasks.objects.create(**validated_data)

    def update(self, instance: TradingTasks, validated_data: dict) -> TradingTasks:
        """Update trading task."""
        # Don't allow updating if task is running
        if instance.status == "running":
            raise serializers.ValidationError("Cannot update a running task. Stop it first.")

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
