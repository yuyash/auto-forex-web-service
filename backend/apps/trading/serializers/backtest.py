"""Serializers for backtest tasks."""

from decimal import Decimal

from rest_framework import serializers

from apps.trading.models import BacktestTask, StrategyConfig


class BacktestTaskSerializer(serializers.ModelSerializer):
    """Serializer for BacktestTask full details."""

    user_id = serializers.IntegerField(source="user.id", read_only=True)
    config_id = serializers.IntegerField(source="config.id", read_only=True)
    config_name = serializers.CharField(source="config.name", read_only=True)
    strategy_type = serializers.CharField(source="config.strategy_type", read_only=True)
    latest_execution = serializers.SerializerMethodField()

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
            "trading_mode",
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
    """Serializer for BacktestTask list view (summary only)."""

    user_id = serializers.IntegerField(source="user.id", read_only=True)
    config_id = serializers.IntegerField(source="config.id", read_only=True)
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
            "trading_mode",
            "status",
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
            "commission_per_trade",
            "pip_size",
            "instrument",
            "trading_mode",
        ]
        # Make fields optional for partial updates (PATCH)
        extra_kwargs = {
            "config": {"required": False},
            "name": {"required": False},
            "data_source": {"required": False},
            "start_time": {"required": False},
            "end_time": {"required": False},
            "initial_balance": {"required": False},
            "commission_per_trade": {"required": False},
            "pip_size": {"required": False},
            "instrument": {"required": False},
            "trading_mode": {"required": False},
        }

    def validate_config(self, value: StrategyConfig) -> StrategyConfig:
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
        if config:
            is_valid, error_message = config.validate_parameters()
            if not is_valid:
                raise serializers.ValidationError({"config": error_message})

        # Validate instrument is provided
        instrument = attrs.get("instrument")
        if not instrument:
            raise serializers.ValidationError({"instrument": "Instrument is required"})

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
