"""Serializers for trading metrics."""

from rest_framework import serializers

from apps.trading.models import TradingMetrics


class TradingMetricsSerializer(serializers.ModelSerializer):
    """Serializer for TradingMetrics model.

    Serializes all fields of the TradingMetrics model including:
    - Execution relationship
    - Sequencing and timing fields
    - PnL metrics (realized, unrealized, total)
    - Position metrics (open positions, total trades)
    - Tick statistics for ask, bid, and mid prices"""

    execution_id = serializers.IntegerField(source="execution.id", read_only=True)

    class Meta:
        model = TradingMetrics
        fields = [
            "id",
            "execution",
            "execution_id",
            "sequence",
            "timestamp",
            # PnL metrics
            "realized_pnl",
            "unrealized_pnl",
            "total_pnl",
            # Position metrics
            "open_positions",
            "total_trades",
            # Tick statistics - Ask
            "tick_ask_min",
            "tick_ask_max",
            "tick_ask_avg",
            # Tick statistics - Bid
            "tick_bid_min",
            "tick_bid_max",
            "tick_bid_avg",
            # Tick statistics - Mid
            "tick_mid_min",
            "tick_mid_max",
            "tick_mid_avg",
            # Timestamps
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "execution_id",
            "created_at",
            "updated_at",
        ]
