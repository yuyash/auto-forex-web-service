"""Task summary serializer."""

from rest_framework import serializers


class TickInfoSerializer(serializers.Serializer):
    """Serializer for tick information."""

    timestamp = serializers.CharField(allow_null=True)
    bid = serializers.DecimalField(max_digits=20, decimal_places=10, allow_null=True)
    ask = serializers.DecimalField(max_digits=20, decimal_places=10, allow_null=True)
    mid = serializers.DecimalField(max_digits=20, decimal_places=10, allow_null=True)


class PnlInfoSerializer(serializers.Serializer):
    """Serializer for PnL information."""

    realized = serializers.DecimalField(max_digits=20, decimal_places=10)
    unrealized = serializers.DecimalField(max_digits=20, decimal_places=10)


class CountsInfoSerializer(serializers.Serializer):
    """Serializer for trade/position counts."""

    total_trades = serializers.IntegerField()
    open_positions = serializers.IntegerField()
    closed_positions = serializers.IntegerField()


class ExecutionInfoSerializer(serializers.Serializer):
    """Serializer for execution state."""

    current_balance = serializers.DecimalField(max_digits=20, decimal_places=10, allow_null=True)
    ticks_processed = serializers.IntegerField()


class TaskInfoSerializer(serializers.Serializer):
    """Serializer for task status information."""

    status = serializers.CharField()
    started_at = serializers.CharField(allow_null=True)
    completed_at = serializers.CharField(allow_null=True)
    error_message = serializers.CharField(allow_null=True)
    progress = serializers.IntegerField()


class TaskSummarySerializer(serializers.Serializer):
    """Serializer for structured task summary response.

    Returns comprehensive task summary grouped into logical sections:
    - timestamp: Common timestamp from the last tick
    - pnl: Realized and unrealized PnL
    - counts: Trade and position counts
    - execution: Balance and ticks processed
    - tick: Last tick prices (bid, ask, mid)
    - task: Status, timing, and progress
    """

    timestamp = serializers.CharField(allow_null=True)
    pnl = PnlInfoSerializer()
    counts = CountsInfoSerializer()
    execution = ExecutionInfoSerializer()
    tick = TickInfoSerializer()
    task = TaskInfoSerializer()
