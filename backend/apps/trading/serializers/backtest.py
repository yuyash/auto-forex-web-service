"""Serializers for backtest tasks."""

import logging
from decimal import Decimal

from rest_framework import serializers

from apps.trading.enums import TaskStatus
from apps.trading.models import BacktestTask, StrategyConfiguration
from apps.trading.services.task_policy import (
    action_policy_for_task,
    task_update_validation_error,
)

logger = logging.getLogger(__name__)


class BacktestTaskSerializer(serializers.ModelSerializer):
    """Serializer for BacktestTask full details."""

    user_id = serializers.IntegerField(source="user.id", read_only=True)
    config_id = serializers.UUIDField(source="config.id", read_only=True)
    config_name = serializers.CharField(source="config.name", read_only=True)
    config_revision = serializers.IntegerField(source="config.revision", read_only=True)
    config_hash = serializers.CharField(source="config.config_hash", read_only=True)
    strategy_type = serializers.CharField(source="config.strategy_type", read_only=True)
    can_resume = serializers.SerializerMethodField()
    action_policy = serializers.SerializerMethodField()

    class Meta:
        model = BacktestTask
        fields = [
            "id",
            "user_id",
            "config_id",
            "config_name",
            "config_revision",
            "config_hash",
            "strategy_type",
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
            "hedging_enabled",
            "tick_granularity",
            "tick_window_value_mode",
            "drain_duration_hours",
            "market_idle_pre_close_minutes",
            "market_idle_resume_delay_minutes",
            "market_close_enabled",
            "market_close_weekday",
            "market_close_hour_utc",
            "market_open_weekday",
            "market_open_hour_utc",
            "max_tick_gap_hours",
            "initial_positions_enabled",
            "initial_position_cycles",
            "sell_on_stop",
            "status",
            "execution_id",
            "started_at",
            "completed_at",
            "error_message",
            "created_at",
            "updated_at",
            "debug_options",
            "can_resume",
            "action_policy",
        ]
        read_only_fields = [
            "id",
            "user_id",
            "config_id",
            "config_name",
            "config_revision",
            "config_hash",
            "strategy_type",
            "status",
            "execution_id",
            "started_at",
            "completed_at",
            "error_message",
            "created_at",
            "updated_at",
            "can_resume",
            "action_policy",
        ]

    def get_can_resume(self, obj: BacktestTask) -> bool:
        """Check if task can be resumed with state recovery."""
        return obj.can_resume()

    def get_action_policy(self, obj: BacktestTask) -> dict[str, bool]:
        """Return task action permissions."""
        return action_policy_for_task(obj, task_type="backtest").as_dict()


class BacktestTaskListSerializer(BacktestTaskSerializer):
    """Serializer for BacktestTask list view (summary only).

    Inherits all fields from BacktestTaskSerializer but drops
    ``commission_per_trade`` and ``execution_id``, and marks everything
    read-only.
    """

    class Meta(BacktestTaskSerializer.Meta):
        fields = [
            f
            for f in BacktestTaskSerializer.Meta.fields
            if f not in {"commission_per_trade", "execution_id"}
        ]
        read_only_fields = fields


class BacktestBalanceAdjustmentSerializer(serializers.Serializer):
    """Request serializer for changing a resumable backtest execution balance."""

    current_balance = serializers.DecimalField(
        max_digits=20,
        decimal_places=10,
        min_value=Decimal("0"),
        help_text="New current balance for the paused or stopped backtest execution.",
    )
    reason = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=255,
        help_text="Optional audit note for the balance change.",
    )


class BacktestBalanceAdjustmentResponseSerializer(serializers.Serializer):
    """Response serializer for backtest balance changes."""

    task_id = serializers.UUIDField()
    execution_id = serializers.UUIDField()
    previous_balance = serializers.DecimalField(max_digits=20, decimal_places=10)
    current_balance = serializers.DecimalField(max_digits=20, decimal_places=10)
    adjustment = serializers.DecimalField(max_digits=20, decimal_places=10)
    state_version = serializers.IntegerField()


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
            "hedging_enabled",
            "tick_granularity",
            "tick_window_value_mode",
            "drain_duration_hours",
            "market_idle_pre_close_minutes",
            "market_idle_resume_delay_minutes",
            "market_close_enabled",
            "market_close_weekday",
            "market_close_hour_utc",
            "market_open_weekday",
            "market_open_hour_utc",
            "max_tick_gap_hours",
            "initial_positions_enabled",
            "initial_position_cycles",
            "sell_on_stop",
            "debug_options",
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
            "hedging_enabled": {"required": False},
            "tick_granularity": {"required": False},
            "tick_window_value_mode": {"required": False},
            "drain_duration_hours": {"required": False, "min_value": 0},
            "market_idle_pre_close_minutes": {"required": False, "min_value": 0},
            "market_idle_resume_delay_minutes": {"required": False, "min_value": 0},
            "market_close_enabled": {"required": False},
            "market_close_weekday": {
                "required": False,
                "min_value": 0,
                "max_value": 6,
            },
            "market_close_hour_utc": {
                "required": False,
                "min_value": 0,
                "max_value": 23,
            },
            "market_open_weekday": {
                "required": False,
                "min_value": 0,
                "max_value": 6,
            },
            "market_open_hour_utc": {
                "required": False,
                "min_value": 0,
                "max_value": 23,
            },
            "max_tick_gap_hours": {"required": False, "min_value": 1},
            "initial_positions_enabled": {"required": False},
            "initial_position_cycles": {"required": False},
            "sell_on_stop": {"required": False},
            "debug_options": {"required": False},
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

    def validate_name(self, value: str) -> str:
        """Validate task name uniqueness per user."""
        user = self.context["request"].user
        query = BacktestTask.objects.filter(user=user, name=value)
        if self.instance is not None:
            query = query.exclude(pk=self.instance.pk)
        if query.exists():
            raise serializers.ValidationError("A backtest task with this name already exists.")
        return value

    def validate(self, attrs: dict) -> dict:
        """Validate date ranges and configuration."""
        from django.utils import timezone

        start_time = attrs.get("start_time", getattr(self.instance, "start_time", None))
        end_time = attrs.get("end_time", getattr(self.instance, "end_time", None))
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
        tick_granularity = attrs.get(
            "tick_granularity",
            getattr(self.instance, "tick_granularity", BacktestTask.TickGranularity.TICK),
        )
        tick_window_value_mode = attrs.get(
            "tick_window_value_mode",
            getattr(
                self.instance,
                "tick_window_value_mode",
                BacktestTask.TickWindowValueMode.LAST,
            ),
        )

        valid_granularities = {choice for choice, _ in BacktestTask.TickGranularity.choices}
        if tick_granularity not in valid_granularities:
            raise serializers.ValidationError(
                {"tick_granularity": f"Unsupported tick granularity: {tick_granularity}"}
            )

        valid_modes = {choice for choice, _ in BacktestTask.TickWindowValueMode.choices}
        if tick_window_value_mode not in valid_modes:
            raise serializers.ValidationError(
                {
                    "tick_window_value_mode": (
                        f"Unsupported tick window value mode: {tick_window_value_mode}"
                    )
                }
            )

        config = attrs.get("config") or getattr(self.instance, "config", None)
        if not config:
            raise serializers.ValidationError({"config": "Strategy configuration is required"})
        is_valid, error_message = config.validate_parameters()
        if not is_valid:
            raise serializers.ValidationError({"config": error_message})

        initial_positions_enabled = attrs.get(
            "initial_positions_enabled",
            getattr(self.instance, "initial_positions_enabled", False),
        )
        initial_position_cycles = attrs.get(
            "initial_position_cycles",
            getattr(self.instance, "initial_position_cycles", []),
        )
        if initial_positions_enabled:
            from apps.trading.services.backtest_initial_positions import (
                InitialPositionValidationError,
                validate_initial_position_cycles,
            )

            try:
                validate_initial_position_cycles(
                    task=self.instance,
                    config=config,
                    cycles=initial_position_cycles,
                    pip_size=attrs.get("pip_size", getattr(self.instance, "pip_size", None)),
                )
            except InitialPositionValidationError as exc:
                raise serializers.ValidationError(exc.errors) from exc

        # Validate instrument is provided
        instrument = attrs.get("instrument", getattr(self.instance, "instrument", None))
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

        task = BacktestTask.objects.create(**validated_data)
        from apps.trading.services.backtest_initial_positions import (
            BacktestInitialPositionService,
        )

        BacktestInitialPositionService().sync_for_task(task)
        return task

    def update(self, instance: BacktestTask, validated_data: dict) -> BacktestTask:
        """Update backtest task."""
        from apps.trading.services.task_audit import audit_task_update, changed_field_values

        error = task_update_validation_error(
            task=instance,
            changed_fields=set(validated_data),
            task_type="backtest",
        )
        if error is not None:
            raise serializers.ValidationError(error)

        changes = changed_field_values(instance, validated_data)
        replay_settings_changed = any(
            field in validated_data and validated_data[field] != getattr(instance, field)
            for field in ("tick_granularity", "tick_window_value_mode")
        )

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if replay_settings_changed and instance.status != TaskStatus.CREATED:
            # Replay settings affect execution continuity. Existing runs must start fresh.
            instance.status = TaskStatus.CREATED
            if instance.execution_id is not None or instance.started_at or instance.completed_at:
                instance.status = TaskStatus.STOPPED

        instance.save()
        preview_seed_fields = {
            "initial_positions_enabled",
            "initial_position_cycles",
            "config",
            "pip_size",
            "instrument",
            "start_time",
            "initial_balance",
            "account_currency",
            "hedging_enabled",
        }
        if preview_seed_fields & set(validated_data):
            from apps.trading.services.backtest_initial_positions import (
                BacktestInitialPositionService,
            )

            BacktestInitialPositionService().sync_for_task(instance)
        audit_task_update(task=instance, task_type="backtest", changes=changes)
        return instance
