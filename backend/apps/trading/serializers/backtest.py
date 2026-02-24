"""Serializers for backtest tasks."""

import logging
from decimal import Decimal

from rest_framework import serializers

from apps.trading.models import BacktestTask, StrategyConfiguration

logger = logging.getLogger(__name__)


class BacktestTaskSerializer(serializers.ModelSerializer):
    """Serializer for BacktestTask full details."""

    user_id = serializers.IntegerField(source="user.id", read_only=True)
    config_id = serializers.UUIDField(source="config.id", read_only=True)
    config_name = serializers.CharField(source="config.name", read_only=True)
    strategy_type = serializers.CharField(source="config.strategy_type", read_only=True)

    class Meta:
        model = BacktestTask
        fields = [
            "id",
            "user_id",
            "config_id",
            "config_name",
            "strategy_type",
            "name",
            "description",
            "data_source",
            "start_time",
            "end_time",
            "initial_balance",
            "commission_per_trade",
            "pip_size",
            "instrument",
            "status",
            "started_at",
            "completed_at",
            "error_message",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "user_id",
            "config_id",
            "config_name",
            "strategy_type",
            "status",
            "started_at",
            "completed_at",
            "error_message",
            "created_at",
            "updated_at",
        ]


class BacktestTaskListSerializer(serializers.ModelSerializer):
    """Serializer for BacktestTask list view (summary only)."""

    user_id = serializers.IntegerField(source="user.id", read_only=True)
    config_id = serializers.UUIDField(source="config.id", read_only=True)
    config_name = serializers.CharField(source="config.name", read_only=True)
    strategy_type = serializers.CharField(source="config.strategy_type", read_only=True)

    class Meta:
        model = BacktestTask
        fields = [
            "id",
            "user_id",
            "config_id",
            "config_name",
            "strategy_type",
            "name",
            "description",
            "data_source",
            "start_time",
            "end_time",
            "initial_balance",
            "pip_size",
            "instrument",
            "status",
            "started_at",
            "completed_at",
            "error_message",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class BacktestTaskCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating BacktestTask."""

    class Meta:
        model = BacktestTask
        fields = [
            "config",
            "name",
            "description",
            "data_source",
            "start_time",
            "end_time",
            "initial_balance",
            "account_currency",
            "commission_per_trade",
            "pip_size",
            "instrument",
        ]
        # Make fields optional for partial updates (PATCH)
        extra_kwargs = {
            "name": {"required": False},
            "data_source": {"required": False},
            "start_time": {"required": False},
            "end_time": {"required": False},
            "initial_balance": {"required": False},
            "account_currency": {"required": False},
            "commission_per_trade": {"required": False},
            "pip_size": {"required": False},
            "instrument": {"required": False},
        }

    def validate_config(self, value: StrategyConfiguration) -> StrategyConfiguration:
        """Validate that config belongs to the user."""
        user = self.context["request"].user
        if value.user != user:
            raise serializers.ValidationError("Configuration does not belong to the current user")
        return value

    def validate_initial_balance(self, value: Decimal) -> Decimal:
        """Validate initial balance is positive."""
        if value <= 0:
            raise serializers.ValidationError("Initial balance must be positive")
        return value

    def validate_pip_size(self, value: Decimal | None) -> Decimal | None:
        """Validate pip size is positive if provided."""
        if value is not None and value <= 0:
            raise serializers.ValidationError("Pip size must be positive")
        return value

    def validate(self, attrs: dict) -> dict:
        """Validate date ranges and configuration."""
        from django.utils import timezone

        start_time = attrs.get("start_time")
        end_time = attrs.get("end_time")
        now = timezone.now()

        # Validate date range
        if start_time and end_time and start_time >= end_time:
            raise serializers.ValidationError({"start_time": "start_time must be before end_time"})

        # Validate end_time is not in the future
        if end_time and end_time > now:
            raise serializers.ValidationError(
                {
                    "end_time": (
                        "end_time cannot be in the future. Backtesting requires historical data."
                    )
                }
            )

        # Validate start_time is not in the future
        if start_time and start_time > now:
            raise serializers.ValidationError(
                {
                    "start_time": (
                        "start_time cannot be in the future. Backtesting requires historical data."
                    )
                }
            )

        # Validate configuration parameters
        config = attrs.get("config")
        if not config:
            raise serializers.ValidationError({"config": "Strategy configuration is required"})

        is_valid, error_message = config.validate_parameters()
        if not is_valid:
            raise serializers.ValidationError({"config": error_message})

        # Validate instrument is provided
        instrument = attrs.get("instrument")
        if not instrument:
            raise serializers.ValidationError({"instrument": "Instrument is required"})

        # Validate tick data exists for the requested date range
        if start_time and end_time and instrument:
            from django.db.models import Max, Min

            from apps.market.models import TickData

            agg = TickData.objects.filter(instrument=instrument).aggregate(
                min_ts=Min("timestamp"),
                max_ts=Max("timestamp"),
            )
            if agg["min_ts"] is None:
                raise serializers.ValidationError(
                    {
                        "instrument": (
                            f"No tick data available for {instrument}. "
                            "Please choose an instrument that has historical data."
                        )
                    }
                )
            if start_time < agg["min_ts"]:
                raise serializers.ValidationError(
                    {
                        "start_time": (
                            f"start_time is before the earliest available tick data "
                            f"({agg['min_ts'].isoformat()}). "
                            "Please choose a later start time."
                        )
                    }
                )
            if end_time > agg["max_ts"]:
                raise serializers.ValidationError(
                    {
                        "end_time": (
                            f"end_time is after the latest available tick data "
                            f"({agg['max_ts'].isoformat()}). "
                            "Please choose an earlier end time."
                        )
                    }
                )

        return attrs

    def create(self, validated_data: dict) -> BacktestTask:
        """Create backtest task with user from context."""
        from apps.trading.utils import pip_size_for_instrument

        user = self.context["request"].user
        validated_data["user"] = user

        # Auto-populate pip_size from instrument when not explicitly provided
        instrument = validated_data.get("instrument")
        if instrument and not validated_data.get("pip_size"):
            validated_data["pip_size"] = pip_size_for_instrument(instrument)

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
