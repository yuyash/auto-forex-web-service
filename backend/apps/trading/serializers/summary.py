"""Task summary serializer."""

from rest_framework import serializers


class TaskSummarySerializer(serializers.Serializer):
    """Serializer for task summary response.

    Returns comprehensive task summary including PnL, counts,
    execution state, and task status information.
    """

    # PnL
    realized_pnl = serializers.DecimalField(max_digits=20, decimal_places=10)
    unrealized_pnl = serializers.DecimalField(max_digits=20, decimal_places=10)
    # Counts
    total_trades = serializers.IntegerField()
    open_position_count = serializers.IntegerField()
    closed_position_count = serializers.IntegerField()
    # Execution state
    current_balance = serializers.DecimalField(max_digits=20, decimal_places=10, allow_null=True)
    ticks_processed = serializers.IntegerField()
    last_tick_time = serializers.CharField(allow_null=True)
    last_tick_price = serializers.DecimalField(max_digits=20, decimal_places=10, allow_null=True)
    # Task info
    status = serializers.CharField()
    started_at = serializers.CharField(allow_null=True)
    completed_at = serializers.CharField(allow_null=True)
    error_message = serializers.CharField(allow_null=True)
    # Progress (backtest: 0-100, trading: always 0)
    progress = serializers.IntegerField()
