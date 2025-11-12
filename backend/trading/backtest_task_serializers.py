"""
Serializers for BacktestTask management.

This module contains serializers for:
- BacktestTask CRUD operations
- BacktestTask list and detail views
- BacktestTask creation and validation

Requirements: 2.1, 2.2, 8.7
"""

from decimal import Decimal

from rest_framework import serializers

from .backtest_task_models import BacktestTask
from .models import StrategyConfig


class BacktestTaskSerializer(serializers.ModelSerializer):
    """
    Serializer for BacktestTask full details.

    Requirements: 2.1, 2.2, 8.7
    """

    user_id = serializers.IntegerField(source="user.id", read_only=True)
    config_id = serializers.IntegerField(source="config.id", read_only=True)
    config_name = serializers.CharField(source="config.name", read_only=True)
    strategy_type = serializers.CharField(source="config.strategy_type", read_only=True)
    oanda_account_id = serializers.IntegerField(
        source="oanda_account.id", read_only=True, allow_null=True
    )
    oanda_account_name = serializers.CharField(
        source="oanda_account.account_id", read_only=True, allow_null=True
    )
    latest_execution = serializers.SerializerMethodField()

    class Meta:
        model = BacktestTask
        fields = [
            "id",
            "user_id",
            "config_id",
            "config_name",
            "strategy_type",
            "oanda_account_id",
            "oanda_account_name",
            "name",
            "description",
            "data_source",
            "start_time",
            "end_time",
            "initial_balance",
            "commission_per_trade",
            "instrument",
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
            "oanda_account_id",
            "oanda_account_name",
            "status",
            "latest_execution",
            "created_at",
            "updated_at",
        ]

    def get_latest_execution(self, obj: BacktestTask) -> dict | None:
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


class BacktestTaskListSerializer(serializers.ModelSerializer):
    """
    Serializer for BacktestTask list view (summary only).

    Requirements: 2.1, 2.2, 8.7
    """

    user_id = serializers.IntegerField(source="user.id", read_only=True)
    config_id = serializers.IntegerField(source="config.id", read_only=True)
    config_name = serializers.CharField(source="config.name", read_only=True)
    strategy_type = serializers.CharField(source="config.strategy_type", read_only=True)
    oanda_account_id = serializers.IntegerField(
        source="oanda_account.id", read_only=True, allow_null=True
    )
    oanda_account_name = serializers.CharField(
        source="oanda_account.account_id", read_only=True, allow_null=True
    )

    class Meta:
        model = BacktestTask
        fields = [
            "id",
            "user_id",
            "config_id",
            "config_name",
            "strategy_type",
            "oanda_account_id",
            "oanda_account_name",
            "name",
            "description",
            "data_source",
            "start_time",
            "end_time",
            "initial_balance",
            "instrument",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class BacktestTaskCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating and updating BacktestTask.

    Includes validation for date ranges and configuration.

    Requirements: 2.1, 2.2, 8.7
    """

    class Meta:
        model = BacktestTask
        fields = [
            "config",
            "oanda_account",
            "name",
            "description",
            "data_source",
            "start_time",
            "end_time",
            "initial_balance",
            "commission_per_trade",
            "instrument",
        ]

    def validate_config(self, value: StrategyConfig) -> StrategyConfig:
        """Validate that config belongs to the user."""
        user = self.context["request"].user
        if value.user != user:
            raise serializers.ValidationError("Configuration does not belong to the current user")
        return value

    def validate_oanda_account(self, value):  # type: ignore[no-untyped-def]
        """Validate that account belongs to the user and is practice account."""
        if value is None:
            return value

        user = self.context["request"].user
        if value.user != user:
            raise serializers.ValidationError("Account does not belong to the current user")
        if not value.is_active:
            raise serializers.ValidationError("Account is not active")
        if value.api_type == "live":
            raise serializers.ValidationError(
                "Live OANDA accounts cannot be used for backtesting. "
                "Please use a practice account."
            )
        return value

    def validate_initial_balance(self, value: Decimal) -> Decimal:
        """Validate initial balance is positive."""
        if value <= 0:
            raise serializers.ValidationError("Initial balance must be positive")
        return value

    def validate(self, attrs: dict) -> dict:
        """Validate date ranges and configuration."""
        start_time = attrs.get("start_time")
        end_time = attrs.get("end_time")

        # Validate date range
        if start_time and end_time and start_time >= end_time:
            raise serializers.ValidationError({"start_time": "start_time must be before end_time"})

        # Validate configuration parameters
        config = attrs.get("config")
        if config:
            is_valid, error_message = config.validate_parameters()
            if not is_valid:
                raise serializers.ValidationError({"config": error_message})

        return attrs

    def create(self, validated_data: dict) -> BacktestTask:
        """Create backtest task with user from context."""
        user = self.context["request"].user
        validated_data["user"] = user
        return BacktestTask.objects.create(**validated_data)

    def update(self, instance: BacktestTask, validated_data: dict) -> BacktestTask:
        """Update backtest task."""
        # Don't allow updating if task is running
        if instance.status == "running":
            raise serializers.ValidationError("Cannot update a running task. Stop it first.")

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
