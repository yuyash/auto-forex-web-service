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
    progress = serializers.SerializerMethodField()
    current_tick = serializers.SerializerMethodField()

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
            "progress",
            "current_tick",
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
            "progress",
            "current_tick",
            "started_at",
            "completed_at",
            "error_message",
            "created_at",
            "updated_at",
        ]

    def get_progress(self, obj: BacktestTask) -> int:
        """Calculate progress percentage based on current tick timestamp.

        Returns:
            int: Progress percentage (0-100)
        """
        from apps.trading.enums import TaskStatus, TaskType
        from apps.trading.models.state import ExecutionState

        # Only calculate progress for running tasks
        # For completed tasks, return 100; for failed/stopped, return last known progress
        if obj.status == TaskStatus.COMPLETED:
            return 100
        elif obj.status != TaskStatus.RUNNING:
            # For FAILED, STOPPED, etc., return 0 to avoid showing stale progress
            return 0

        # Get the execution state for the current celery task only
        try:
            # Filter by celery_task_id to get state for current execution only
            if not obj.celery_task_id:
                logger.debug(f"[BacktestTaskSerializer] No celery_task_id for task {obj.pk}")
                return 0

            state = ExecutionState.objects.filter(
                task_type=TaskType.BACKTEST.value,
                task_id=obj.pk,
                celery_task_id=obj.celery_task_id,
            ).first()

            if not state:
                logger.debug(f"[BacktestTaskSerializer] No ExecutionState found for task {obj.pk}")
                return 0

            if not state.last_tick_timestamp:
                logger.debug(
                    f"[BacktestTaskSerializer] ExecutionState exists but last_tick_timestamp is None "
                    f"for task {obj.pk}, ticks_processed={state.ticks_processed}"
                )
                return 0

            # Calculate progress based on tick timestamp vs backtest time range
            total_duration = (obj.end_time - obj.start_time).total_seconds()
            if total_duration <= 0:
                logger.warning(
                    f"[BacktestTaskSerializer] Invalid time range for task {obj.pk}: "
                    f"start={obj.start_time}, end={obj.end_time}"
                )
                return 0

            elapsed = (state.last_tick_timestamp - obj.start_time).total_seconds()
            progress = int((elapsed / total_duration) * 100)

            logger.debug(
                f"[BacktestTaskSerializer] Progress for task {obj.pk}: {progress}% "
                f"(elapsed={elapsed}s, total={total_duration}s, last_tick={state.last_tick_timestamp})"
            )

            # Clamp between 0 and 99 (never show 100% until completed)
            return max(0, min(progress, 99))

        except Exception as e:
            logger.error(
                f"[BacktestTaskSerializer] Error calculating progress for task {obj.pk}: {e}",
                exc_info=True,
            )
            return 0

    def get_current_tick(self, obj: BacktestTask) -> dict | None:
        """Return the current tick position and price.

        For running tasks this returns the live tick from ExecutionState.
        For stopped/completed tasks it returns the last recorded tick so
        that Unrealized PnL can still be displayed.

        Returns:
            dict with 'timestamp' (ISO string) and 'price' (string), or None
        """
        from apps.trading.enums import TaskType
        from apps.trading.models.state import ExecutionState

        if not obj.celery_task_id:
            return None

        try:
            state = ExecutionState.objects.filter(
                task_type=TaskType.BACKTEST.value,
                task_id=obj.pk,
                celery_task_id=obj.celery_task_id,
            ).first()

            if not state or not state.last_tick_timestamp:
                return None

            return {
                "timestamp": state.last_tick_timestamp.isoformat(),
                "price": str(state.last_tick_price) if state.last_tick_price is not None else None,
            }
        except Exception as e:
            logger.error(
                f"[BacktestTaskSerializer] Error getting current_tick for task {obj.pk}: {e}",
                exc_info=True,
            )
            return None


class BacktestTaskListSerializer(serializers.ModelSerializer):
    """Serializer for BacktestTask list view (summary only)."""

    user_id = serializers.IntegerField(source="user.id", read_only=True)
    config_id = serializers.UUIDField(source="config.id", read_only=True)
    config_name = serializers.CharField(source="config.name", read_only=True)
    strategy_type = serializers.CharField(source="config.strategy_type", read_only=True)
    progress = serializers.SerializerMethodField()

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
            "progress",
            "started_at",
            "completed_at",
            "error_message",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_progress(self, obj: BacktestTask) -> int:
        """Calculate progress percentage based on current tick timestamp.

        Returns:
            int: Progress percentage (0-100)
        """
        from apps.trading.enums import TaskStatus, TaskType
        from apps.trading.models.state import ExecutionState

        # Only calculate progress for running tasks
        if obj.status != TaskStatus.RUNNING:
            return 0

        # Get the execution state for the current celery task only
        try:
            # Filter by celery_task_id to get state for current execution only
            if not obj.celery_task_id:
                logger.debug(f"[BacktestTaskListSerializer] No celery_task_id for task {obj.pk}")
                return 0

            state = ExecutionState.objects.filter(
                task_type=TaskType.BACKTEST.value,
                task_id=obj.pk,
                celery_task_id=obj.celery_task_id,
            ).first()

            if not state:
                logger.debug(
                    f"[BacktestTaskListSerializer] No ExecutionState found for task {obj.pk}"
                )
                return 0

            if not state.last_tick_timestamp:
                logger.debug(
                    f"[BacktestTaskListSerializer] ExecutionState exists but last_tick_timestamp is None "
                    f"for task {obj.pk}, ticks_processed={state.ticks_processed}"
                )
                return 0

            # Calculate progress based on tick timestamp vs backtest time range
            total_duration = (obj.end_time - obj.start_time).total_seconds()
            if total_duration <= 0:
                logger.warning(
                    f"[BacktestTaskListSerializer] Invalid time range for task {obj.pk}: "
                    f"start={obj.start_time}, end={obj.end_time}"
                )
                return 0

            elapsed = (state.last_tick_timestamp - obj.start_time).total_seconds()
            progress = int((elapsed / total_duration) * 100)

            logger.debug(
                f"[BacktestTaskListSerializer] Progress for task {obj.pk}: {progress}% "
                f"(elapsed={elapsed}s, total={total_duration}s, last_tick={state.last_tick_timestamp})"
            )

            # Clamp between 0 and 99 (never show 100% until completed)
            return max(0, min(progress, 99))

        except Exception as e:
            logger.error(
                f"[BacktestTaskListSerializer] Error calculating progress for task {obj.pk}: {e}",
                exc_info=True,
            )
            return 0


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
