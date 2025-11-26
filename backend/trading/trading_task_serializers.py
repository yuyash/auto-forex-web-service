"""
Serializers for TradingTask management.

This module contains serializers for:
- TradingTask CRUD operations
- TradingTask list and detail views
- TradingTask creation and validation

Requirements: 3.1, 3.2, 8.6, 8.7
"""

from rest_framework import serializers

from accounts.models import OandaAccount

from .models import StrategyConfig
from .trading_task_models import TradingTask


class TradingTaskSerializer(serializers.ModelSerializer):
    """
    Serializer for TradingTask full details.

    Requirements: 3.1, 3.2, 8.7
    """

    user_id = serializers.IntegerField(source="user.id", read_only=True)
    config_id = serializers.IntegerField(source="config.id", read_only=True)
    config_name = serializers.CharField(source="config.name", read_only=True)
    strategy_type = serializers.CharField(source="config.strategy_type", read_only=True)
    account_id = serializers.IntegerField(source="oanda_account.id", read_only=True)
    account_name = serializers.CharField(source="oanda_account.account_id", read_only=True)
    account_type = serializers.CharField(source="oanda_account.api_type", read_only=True)
    latest_execution = serializers.SerializerMethodField()

    class Meta:
        model = TradingTask
        fields = [
            "id",
            "user_id",
            "config_id",
            "config_name",
            "strategy_type",
            "account_id",
            "account_name",
            "account_type",
            "name",
            "description",
            "sell_on_stop",
            "status",
            "latest_execution",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "user_id",
            "config_id",
            "config_name",
            "strategy_type",
            "account_id",
            "account_name",
            "account_type",
            "status",
            "latest_execution",
            "created_at",
            "updated_at",
        ]

    def get_latest_execution(self, obj: TradingTask) -> dict | None:
        """Get summary of latest execution."""
        execution = obj.get_latest_execution()
        if not execution:
            return None

        return {
            "id": execution.id,
            "execution_number": execution.execution_number,
            "status": execution.status,
            "started_at": execution.started_at,
            "completed_at": execution.completed_at,
        }


class TradingTaskListSerializer(serializers.ModelSerializer):
    """
    Serializer for TradingTask list view (summary only).

    Requirements: 3.1, 3.2, 8.7
    """

    user_id = serializers.IntegerField(source="user.id", read_only=True)
    config_id = serializers.IntegerField(source="config.id", read_only=True)
    config_name = serializers.CharField(source="config.name", read_only=True)
    strategy_type = serializers.CharField(source="config.strategy_type", read_only=True)
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


class TradingTaskCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating and updating TradingTask.

    Includes validation for account ownership and configuration.

    Requirements: 3.1, 3.2, 8.6, 8.7
    """

    class Meta:
        model = TradingTask
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

    def validate_config(self, value: StrategyConfig) -> StrategyConfig:
        """Validate that config belongs to the user."""
        user = self.context["request"].user
        if value.user != user:
            raise serializers.ValidationError("Configuration does not belong to the current user")
        return value

    def validate_oanda_account(self, value: OandaAccount) -> OandaAccount:
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

        return attrs

    def create(self, validated_data: dict) -> TradingTask:
        """Create trading task with user from context."""
        user = self.context["request"].user
        validated_data["user"] = user
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
