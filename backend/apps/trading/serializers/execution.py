"""Execution history serializers."""

from rest_framework import serializers


class TaskExecutionMetricsSerializer(serializers.Serializer):
    """Serializer for execution-level aggregate metrics."""

    total_return = serializers.DecimalField(max_digits=20, decimal_places=10, required=False)
    total_pnl = serializers.DecimalField(max_digits=20, decimal_places=10, required=False)
    unrealized_pnl = serializers.DecimalField(max_digits=20, decimal_places=10, required=False)
    total_pnl_quote = serializers.DecimalField(max_digits=20, decimal_places=10, required=False)
    realized_pnl_quote = serializers.DecimalField(max_digits=20, decimal_places=10, required=False)
    unrealized_pnl_quote = serializers.DecimalField(
        max_digits=20, decimal_places=10, required=False
    )
    total_trades = serializers.IntegerField(required=False)
    winning_trades = serializers.IntegerField(required=False)
    losing_trades = serializers.IntegerField(required=False)
    win_rate = serializers.DecimalField(max_digits=10, decimal_places=4, required=False)
    pnl_currency = serializers.CharField(required=False)
    quote_currency = serializers.CharField(required=False)


class TaskExecutionSerializer(serializers.Serializer):
    """Serializer for task execution history rows."""

    id = serializers.CharField(help_text="Execution identifier (UUID).")
    task_type = serializers.CharField()
    task_id = serializers.UUIDField()
    execution_number = serializers.CharField(help_text="Execution ID (UUID).")
    status = serializers.CharField()
    progress = serializers.IntegerField()
    started_at = serializers.DateTimeField(allow_null=True)
    completed_at = serializers.DateTimeField(allow_null=True, required=False)
    error_message = serializers.CharField(allow_null=True, required=False)
    error_code = serializers.CharField(allow_null=True, required=False)
    duration = serializers.FloatField(allow_null=True, required=False)
    created_at = serializers.DateTimeField()
    notes = serializers.CharField(allow_blank=True, required=False, default="")
    configuration_revision = serializers.IntegerField(allow_null=True, required=False)
    configuration_hash = serializers.CharField(allow_null=True, required=False)
    metrics = TaskExecutionMetricsSerializer(required=False)
    task_config = serializers.DictField(required=False, allow_null=True)
    strategy_config = serializers.DictField(required=False, allow_null=True)
