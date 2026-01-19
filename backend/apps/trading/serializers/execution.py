"""Serializers for task execution."""

from rest_framework import serializers

from apps.trading.models import Executions

from .events import StrategyEventsSerializer, StructuredLogSerializer


class ExecutionsSerializer(serializers.ModelSerializer):
    """Serializer for Executions summary views."""

    duration = serializers.SerializerMethodField()

    class Meta:  # pylint: disable=missing-class-docstring,too-few-public-methods
        model = Executions
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

    def get_duration(self, obj: Executions) -> str | None:
        return obj.get_duration()


class ExecutionsListSerializer(serializers.ModelSerializer):
    """Serializer for execution list endpoints.

    Per API contract, this omits heavy fields like logs and nested metrics.
    """

    duration = serializers.SerializerMethodField()

    class Meta:  # pylint: disable=missing-class-docstring,too-few-public-methods
        model = Executions
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

    def get_duration(self, obj: Executions) -> str | None:
        return obj.get_duration()


class ExecutionsDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for detailed execution view with nested metrics.
    """

    duration = serializers.SerializerMethodField()
    has_metrics = serializers.SerializerMethodField()

    class Meta:  # pylint: disable=missing-class-docstring,too-few-public-methods
        model = Executions
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
            "created_at",
        ]
        read_only_fields = fields

    def get_duration(self, obj: Executions) -> str | None:
        """Get formatted execution duration."""
        return obj.get_duration()

    def get_has_metrics(self, obj: Executions) -> bool:
        """Check if execution has associated metrics."""
        return obj.trading_metrics.exists()  # type: ignore[attr-defined]


class ExecutionsWithStructuredDataSerializer(serializers.ModelSerializer):
    """Enhanced serializer with structured events, logs, and latest metrics.

    This serializer provides:
    - Structured strategy events with parsed fields
    - Structured logs with log_type categorization
    - Latest metrics checkpoint
    - All standard execution fields"""

    duration = serializers.SerializerMethodField()
    has_metrics = serializers.SerializerMethodField()
    structured_events = serializers.SerializerMethodField()
    structured_logs = serializers.SerializerMethodField()
    latest_metrics_checkpoint = serializers.SerializerMethodField()

    class Meta:  # pylint: disable=missing-class-docstring,too-few-public-methods
        model = Executions
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
            "created_at",
            # Enhanced structured fields
            "structured_events",
            "structured_logs",
            "latest_metrics_checkpoint",
        ]
        read_only_fields = fields

    def get_duration(self, obj: Executions) -> str | None:
        """Get formatted execution duration."""
        return obj.get_duration()

    def get_has_metrics(self, obj: Executions) -> bool:
        """Check if execution has associated metrics."""
        return obj.trading_metrics.exists()  # type: ignore[attr-defined]

    def get_structured_events(self, obj: Executions) -> list[dict]:
        """Get structured strategy events.

        Returns a limited number of recent events with structured parsing.
        For full event access, use the ExecutionEventsView endpoint.
        """
        # Limit to most recent 100 events to avoid payload bloat
        events = obj.strategy_events.order_by("-sequence", "-id")[:100]

        # Reverse to get chronological order
        events = list(reversed(events))

        serializer = StrategyEventsSerializer(events, many=True)
        return serializer.data  # type: ignore[return-value]

    def get_structured_logs(self, obj: Executions) -> list[dict]:
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

    def get_latest_metrics_checkpoint(self, obj: Executions) -> dict | None:
        """Get the latest metrics checkpoint.

        Returns the most recent TradingMetrics snapshot.
        """
        latest_metric = obj.trading_metrics.order_by("-sequence").first()  # type: ignore[attr-defined]
        if not latest_metric:
            return None

        from .metrics import TradingMetricsSerializer

        serializer = TradingMetricsSerializer(latest_metric)
        return serializer.data  # type: ignore[return-value]
