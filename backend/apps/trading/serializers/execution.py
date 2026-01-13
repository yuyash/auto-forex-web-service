"""Serializers for task execution."""

from rest_framework import serializers

from apps.trading.models import TaskExecution

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
