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
            "execution_id",
            "created_at",
            "updated_at",
            "started_at",
            "completed_at",
            "duration",
            "error_message",
            "error_traceback",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "execution_id",
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

    config_id = serializers.UUIDField(source="config.id", read_only=True)
    config_name = serializers.CharField(source="config.name", read_only=True)
    strategy_type = serializers.CharField(source="config.strategy_type", read_only=True)

    class Meta(TaskSerializer.Meta):
        model = BacktestTask
        fields = TaskSerializer.Meta.fields + [
            "user",
            "config_id",
            "config_name",
            "strategy_type",
            "data_source",
            "start_time",
            "end_time",
            "initial_balance",
            "commission_per_trade",
            "pip_size",
            "instrument",
        ]
        read_only_fields = TaskSerializer.Meta.read_only_fields + ["user"]


class TradingTaskSerializer(TaskSerializer):
    """Serializer for TradingTask with execution data."""

    config_id = serializers.UUIDField(source="config.id", read_only=True)
    config_name = serializers.CharField(source="config.name", read_only=True)
    strategy_type = serializers.CharField(source="config.strategy_type", read_only=True)
    account_name = serializers.CharField(source="oanda_account.account_id", read_only=True)
    account_type = serializers.CharField(source="oanda_account.api_type", read_only=True)

    class Meta(TaskSerializer.Meta):
        model = TradingTask
        fields = TaskSerializer.Meta.fields + [
            "user",
            "config_id",
            "config_name",
            "strategy_type",
            "oanda_account",
            "account_name",
            "account_type",
            "sell_on_stop",
            "dry_run",
            "pip_size",
            "instrument",
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
            "task_type",
            "task_id",
            "execution_id",
            "timestamp",
            "level",
            "component",
            "message",
            "details",
        ]
        read_only_fields = ["id", "timestamp"]
