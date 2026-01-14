"""Serializers for task execution."""

from rest_framework import serializers

from apps.trading.models import TaskExecution

from .events import StrategyEventSerializer, StructuredLogSerializer
from .metrics import ExecutionMetricsSerializer


class TaskExecutionSerializer(serializers.ModelSerializer):
    """Serializer for TaskExecution summary views."""

    duration = serializers.SerializerMethodField()

    class Meta:  # pylint: disable=missing-class-docstring,too-few-public-methods
        model = TaskExecution
        fields = [
            "id",
            "task_type",
            "task_id",
            "execution_number",
            "status",
            "progress",
            "started_at",
            "completed_at",
            "error_message",
            "logs",
            "duration",
            "created_at",
        ]
        read_only_fields = fields

    def get_duration(self, obj: TaskExecution) -> str | None:
        return obj.get_duration()


class TaskExecutionListSerializer(serializers.ModelSerializer):
    """Serializer for execution list endpoints.

    Per API contract, this omits heavy fields like logs and nested metrics.
    """

    duration = serializers.SerializerMethodField()

    class Meta:  # pylint: disable=missing-class-docstring,too-few-public-methods
        model = TaskExecution
        fields = [
            "id",
            "task_type",
            "task_id",
            "execution_number",
            "status",
            "progress",
            "started_at",
            "completed_at",
            "error_message",
            "duration",
            "created_at",
        ]
        read_only_fields = fields

    def get_duration(self, obj: TaskExecution) -> str | None:
        return obj.get_duration()


class TaskExecutionDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for detailed task execution view with nested metrics.
    """

    duration = serializers.SerializerMethodField()
    metrics = ExecutionMetricsSerializer(read_only=True, allow_null=True)
    has_metrics = serializers.SerializerMethodField()

    class Meta:  # pylint: disable=missing-class-docstring,too-few-public-methods
        model = TaskExecution
        fields = [
            "id",
            "task_type",
            "task_id",
            "execution_number",
            "status",
            "progress",
            "started_at",
            "completed_at",
            "error_message",
            "error_traceback",
            "logs",
            "duration",
            "has_metrics",
            "metrics",
            "created_at",
        ]
        read_only_fields = fields

    def get_duration(self, obj: TaskExecution) -> str | None:
        """Get formatted execution duration."""
        return obj.get_duration()

    def get_has_metrics(self, obj: TaskExecution) -> bool:
        """Check if execution has associated metrics."""
        return obj.get_metrics() is not None


class TaskExecutionWithStructuredDataSerializer(serializers.ModelSerializer):
    """Enhanced serializer with structured events, logs, and latest metrics.

    This serializer provides:
    - Structured strategy events with parsed fields
    - Structured logs with log_type categorization
    - Latest metrics checkpoint
    - All standard execution fields

    Requirements: 11.1, 11.2
    """

    duration = serializers.SerializerMethodField()
    metrics = ExecutionMetricsSerializer(read_only=True, allow_null=True)
    has_metrics = serializers.SerializerMethodField()
    structured_events = serializers.SerializerMethodField()
    structured_logs = serializers.SerializerMethodField()
    latest_metrics_checkpoint = serializers.SerializerMethodField()

    class Meta:  # pylint: disable=missing-class-docstring,too-few-public-methods
        model = TaskExecution
        fields = [
            "id",
            "task_type",
            "task_id",
            "execution_number",
            "status",
            "progress",
            "started_at",
            "completed_at",
            "error_message",
            "error_traceback",
            "logs",
            "duration",
            "has_metrics",
            "metrics",
            "created_at",
            # Enhanced structured fields
            "structured_events",
            "structured_logs",
            "latest_metrics_checkpoint",
        ]
        read_only_fields = fields

    def get_duration(self, obj: TaskExecution) -> str | None:
        """Get formatted execution duration."""
        return obj.get_duration()

    def get_has_metrics(self, obj: TaskExecution) -> bool:
        """Check if execution has associated metrics."""
        return obj.get_metrics() is not None

    def get_structured_events(self, obj: TaskExecution) -> list[dict]:
        """Get structured strategy events.

        Returns a limited number of recent events with structured parsing.
        For full event access, use the ExecutionEventsView endpoint.
        """
        # Limit to most recent 100 events to avoid payload bloat
        events = obj.strategy_event_rows.order_by("-sequence", "-id")[:100]

        # Reverse to get chronological order
        events = list(reversed(events))

        serializer = StrategyEventSerializer(events, many=True)
        return serializer.data  # type: ignore[return-value]

    def get_structured_logs(self, obj: TaskExecution) -> list[dict]:
        """Get structured logs with log_type categorization.

        Transforms raw log entries into structured format with:
        - log_type: system, strategy_event, trade, error
        - Extracted data from log messages
        """
        if not obj.logs or not isinstance(obj.logs, list):
            return []

        # Limit to most recent 100 logs to avoid payload bloat
        logs = obj.logs[-100:] if len(obj.logs) > 100 else obj.logs

        serializer = StructuredLogSerializer(logs, many=True)
        return serializer.data  # type: ignore[return-value]

    def get_latest_metrics_checkpoint(self, obj: TaskExecution) -> dict | None:
        """Get the latest metrics checkpoint.

        Returns the most recent ExecutionMetricsCheckpoint with all metrics.
        """
        checkpoint = obj.metrics_checkpoints.order_by("-created_at", "-id").first()

        if not checkpoint:
            return None

        return {
            "id": checkpoint.pk,
            "processed": checkpoint.processed,
            "total_return": str(checkpoint.total_return),
            "total_pnl": str(checkpoint.total_pnl),
            "realized_pnl": str(checkpoint.realized_pnl),
            "unrealized_pnl": str(checkpoint.unrealized_pnl),
            "total_trades": checkpoint.total_trades,
            "winning_trades": checkpoint.winning_trades,
            "losing_trades": checkpoint.losing_trades,
            "win_rate": str(checkpoint.win_rate),
            "max_drawdown": str(checkpoint.max_drawdown),
            "sharpe_ratio": (
                str(checkpoint.sharpe_ratio) if checkpoint.sharpe_ratio is not None else None
            ),
            "profit_factor": (
                str(checkpoint.profit_factor) if checkpoint.profit_factor is not None else None
            ),
            "average_win": str(checkpoint.average_win),
            "average_loss": str(checkpoint.average_loss),
            "created_at": checkpoint.created_at.isoformat(),
        }
