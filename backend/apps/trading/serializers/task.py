"""Task serializers for unified task-centric API."""

from rest_framework import serializers

from apps.trading.models import BacktestTasks, TradingTasks
from apps.trading.models.logs import TaskLog, TaskMetric


class TaskSerializer(serializers.ModelSerializer):
    """
    Serializer for Task models with execution data.

    Provides a unified interface for both BacktestTasks and TradingTasks,
    including execution state, timestamps, error information, and results.
    """

    duration = serializers.SerializerMethodField()
    task_type = serializers.SerializerMethodField()

    class Meta:
        model = BacktestTasks  # Base model, will be overridden in subclasses
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
            "retry_count",
            "max_retries",
            "error_message",
            "error_traceback",
            "result_data",
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
            "result_data",
        ]

    def get_duration(self, obj: BacktestTasks | TradingTasks) -> float | None:
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

    def get_task_type(self, obj: BacktestTasks | TradingTasks) -> str:
        """
        Get the task type.

        Args:
            obj: Task instance

        Returns:
            str: "backtest" or "trading"
        """
        if isinstance(obj, BacktestTasks):
            return "backtest"
        elif isinstance(obj, TradingTasks):
            return "trading"
        return "unknown"


class BacktestTaskSerializer(TaskSerializer):
    """Serializer for BacktestTasks with execution data."""

    class Meta(TaskSerializer.Meta):
        model = BacktestTasks
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
        ]
        read_only_fields = TaskSerializer.Meta.read_only_fields + ["user"]


class TradingTaskSerializer(TaskSerializer):
    """Serializer for TradingTasks with execution data."""

    class Meta(TaskSerializer.Meta):
        model = TradingTasks
        fields = TaskSerializer.Meta.fields + [
            "user",
            "config",
            "oanda_account",
            "sell_on_stop",
            "instrument",
            "trading_mode",
            "strategy_state",
        ]
        read_only_fields = TaskSerializer.Meta.read_only_fields + ["user", "strategy_state"]


class TaskLogSerializer(serializers.ModelSerializer):
    """
    Serializer for TaskLog model.

    Provides access to task execution logs with timestamp, level, and message.
    """

    class Meta:
        model = TaskLog
        fields = [
            "id",
            "task",
            "timestamp",
            "level",
            "message",
        ]
        read_only_fields = ["id", "timestamp"]


class TaskMetricSerializer(serializers.ModelSerializer):
    """
    Serializer for TaskMetric model.

    Provides access to task execution metrics with name, value, timestamp,
    and optional metadata.
    """

    class Meta:
        model = TaskMetric
        fields = [
            "id",
            "task",
            "metric_name",
            "metric_value",
            "timestamp",
            "metadata",
        ]
        read_only_fields = ["id", "timestamp"]
