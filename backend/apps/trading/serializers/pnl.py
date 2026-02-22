"""PnL summary serializer."""

from rest_framework import serializers


class PnlSummarySerializer(serializers.Serializer):
    """Serializer for PnL summary response."""

    realized_pnl = serializers.DecimalField(max_digits=20, decimal_places=10)
    unrealized_pnl = serializers.DecimalField(max_digits=20, decimal_places=10)
    total_trades = serializers.IntegerField()
    open_position_count = serializers.IntegerField()
