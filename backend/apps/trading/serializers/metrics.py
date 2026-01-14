"""Serializers for execution metrics."""

from rest_framework import serializers

from apps.trading.models import ExecutionMetrics


class ExecutionMetricsSerializer(serializers.ModelSerializer):
    """
    Serializer for execution metrics.

    Provides read-only access to performance metrics for completed executions.
    """

    trade_summary = serializers.SerializerMethodField()

    class Meta:  # pylint: disable=missing-class-docstring,too-few-public-methods
        model = ExecutionMetrics
        fields = [
            "id",
            "execution_id",
            "total_return",
            "total_pnl",
            "realized_pnl",
            "unrealized_pnl",
            "total_trades",
            "winning_trades",
            "losing_trades",
            "win_rate",
            "max_drawdown",
            "sharpe_ratio",
            "profit_factor",
            "average_win",
            "average_loss",
            "equity_curve",
            "trade_log",
            "strategy_events",
            "trade_summary",
            "created_at",
        ]
        read_only_fields = fields

    def get_trade_summary(self, obj: ExecutionMetrics) -> dict:
        """Get trade summary statistics."""
        return obj.get_trade_summary()


class ExecutionMetricsSummarySerializer(serializers.ModelSerializer):
    """Summary serializer for execution metrics.

    Omits heavy list fields that are fetched via dedicated endpoints:
    - equity_curve
    - trade_log
    - strategy_events
    """

    trade_summary = serializers.SerializerMethodField()

    class Meta:  # pylint: disable=missing-class-docstring,too-few-public-methods
        model = ExecutionMetrics
        fields = [
            "id",
            "execution_id",
            "total_return",
            "total_pnl",
            "realized_pnl",
            "unrealized_pnl",
            "total_trades",
            "winning_trades",
            "losing_trades",
            "win_rate",
            "max_drawdown",
            "sharpe_ratio",
            "profit_factor",
            "average_win",
            "average_loss",
            "trade_summary",
            "created_at",
        ]
        read_only_fields = fields

    def get_trade_summary(self, obj: ExecutionMetrics) -> dict:
        return obj.get_trade_summary()
