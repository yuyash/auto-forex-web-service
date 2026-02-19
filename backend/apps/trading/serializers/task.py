"""Task serializers for unified task-centric API."""

from rest_framework import serializers

from apps.trading.models import BacktestTask, TradingTask
from apps.trading.models.logs import TaskLog


class TaskSerializer(serializers.ModelSerializer):
    """
    Serializer for Task models with execution data.

    Provides a unified interface for both BacktestTask and TradingTask,
    including execution state, timestamps, error information, and results.
    """

    duration = serializers.SerializerMethodField()
    task_type = serializers.SerializerMethodField()

    class Meta:
        model = BacktestTask  # Base model, will be overridden in subclasses
        fields = [
            "id",
            "name",
            "description",
            "task_type",
            "status",
            "created_at",
            "updated_at",
            "started_at",
            "completed_at",
            "duration",
            "celery_task_id",
            "error_message",
            "error_traceback",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "celery_task_id",
            "status",
            "started_at",
            "completed_at",
            "error_message",
            "error_traceback",
        ]

    def get_duration(self, obj: BacktestTask | TradingTask) -> float | None:
        """
        Calculate task execution duration in seconds.

        Args:
            obj: Task instance

        Returns:
            float | None: Duration in seconds if both started_at and completed_at are set,
                         None otherwise
        """
        if obj.duration:
            return obj.duration.total_seconds()
        return None

    def get_task_type(self, obj: BacktestTask | TradingTask) -> str:
        """
        Get the task type.

        Args:
            obj: Task instance

        Returns:
            str: "backtest" or "trading"
        """
        if isinstance(obj, BacktestTask):
            return "backtest"
        elif isinstance(obj, TradingTask):
            return "trading"
        return "unknown"


class BacktestTaskSerializer(TaskSerializer):
    """Serializer for BacktestTask with execution data."""

    progress = serializers.SerializerMethodField()
    current_tick = serializers.SerializerMethodField()

    class Meta(TaskSerializer.Meta):
        model = BacktestTask
        fields = TaskSerializer.Meta.fields + [
            "user",
            "config",
            "data_source",
            "start_time",
            "end_time",
            "initial_balance",
            "commission_per_trade",
            "instrument",
            "trading_mode",
            "progress",
            "current_tick",
        ]
        read_only_fields = TaskSerializer.Meta.read_only_fields + ["user"]

    def get_progress(self, obj: BacktestTask) -> int:
        """
        Calculate backtest progress percentage based on current tick timestamp.

        Progress is calculated as:
        (current_tick_timestamp - start_time) / (end_time - start_time) * 100

        Args:
            obj: BacktestTask instance

        Returns:
            int: Progress percentage (0-100)
        """
        from apps.trading.models.state import ExecutionState

        # Only calculate progress for running tasks
        if obj.status != "running":
            return 0

        # Get the execution state for the current celery task
        try:
            # Filter by celery_task_id to get state for current execution only
            if not obj.celery_task_id:
                return 0

            execution_state = ExecutionState.objects.filter(
                task_type="backtest",
                task_id=obj.pk,
                celery_task_id=obj.celery_task_id,
            ).first()

            if not execution_state or not execution_state.last_tick_timestamp:
                return 0

            # Calculate progress based on time
            total_duration = (obj.end_time - obj.start_time).total_seconds()
            if total_duration <= 0:
                return 0

            elapsed = (execution_state.last_tick_timestamp - obj.start_time).total_seconds()
            progress = int((elapsed / total_duration) * 100)

            # Clamp between 0 and 100
            return max(0, min(100, progress))

        except Exception:
            # If anything goes wrong, return 0
            return 0

    def get_current_tick(self, obj: BacktestTask) -> dict | None:
        """Return the current tick position and price for running tasks.

        Returns:
            dict with 'timestamp' (ISO string) and 'price' (string), or None
        """
        from apps.trading.enums import TaskStatus
        from apps.trading.models.state import ExecutionState

        if obj.status != TaskStatus.RUNNING or not obj.celery_task_id:
            return None

        try:
            state = ExecutionState.objects.filter(
                task_type="backtest",
                task_id=obj.pk,
                celery_task_id=obj.celery_task_id,
            ).first()

            if not state or not state.last_tick_timestamp:
                return None

            return {
                "timestamp": state.last_tick_timestamp.isoformat(),
                "price": str(state.last_tick_price) if state.last_tick_price is not None else None,
            }
        except Exception:
            return None


class TradingTaskSerializer(TaskSerializer):
    """Serializer for TradingTask with execution data."""

    current_tick = serializers.SerializerMethodField()

    class Meta(TaskSerializer.Meta):
        model = TradingTask
        fields = TaskSerializer.Meta.fields + [
            "user",
            "config",
            "oanda_account",
            "sell_on_stop",
            "instrument",
            "trading_mode",
            "strategy_state",
            "current_tick",
        ]
        read_only_fields = TaskSerializer.Meta.read_only_fields + ["user", "strategy_state"]

    def get_current_tick(self, obj: TradingTask) -> dict | None:
        """Return the current tick position and price for running tasks.

        Returns:
            dict with 'timestamp' (ISO string) and 'price' (string), or None
        """
        from apps.trading.enums import TaskStatus
        from apps.trading.models.state import ExecutionState

        if obj.status != TaskStatus.RUNNING or not obj.celery_task_id:
            return None

        try:
            state = ExecutionState.objects.filter(
                task_type="trading",
                task_id=obj.pk,
                celery_task_id=obj.celery_task_id,
            ).first()

            if not state or not state.last_tick_timestamp:
                return None

            return {
                "timestamp": state.last_tick_timestamp.isoformat(),
                "price": str(state.last_tick_price) if state.last_tick_price is not None else None,
            }
        except Exception:
            return None


class TaskLogSerializer(serializers.ModelSerializer):
    """
    Serializer for TaskLog model.

    Provides access to task execution logs with timestamp, level, and message.
    """

    class Meta:
        model = TaskLog
        fields = [
            "id",
            "task_type",
            "task_id",
            "celery_task_id",
            "timestamp",
            "level",
            "component",
            "message",
            "details",
        ]
        read_only_fields = ["id", "timestamp"]
