"""
Serializers for trading data.

This module contains serializers for:
- Tick data retrieval and export
- Strategy configuration and management

Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 7.1, 7.2, 12.1
"""

from rest_framework import serializers

from .event_models import Event
from .models import Order, Position, Strategy, StrategyState
from .tick_data_models import TickData


class TickDataSerializer(serializers.ModelSerializer):
    """
    Serializer for tick data retrieval.

    Provides read-only access to historical tick data with all fields.

    Requirements: 7.1, 7.2, 12.1
    """

    account_id = serializers.IntegerField(source="account.id", read_only=True)
    account_name = serializers.CharField(source="account.account_id", read_only=True)

    class Meta:
        model = TickData
        fields = [
            "id",
            "account_id",
            "account_name",
            "instrument",
            "timestamp",
            "bid",
            "ask",
            "mid",
            "spread",
            "created_at",
        ]
        read_only_fields = fields


class TickDataCSVSerializer(serializers.ModelSerializer):
    """
    Serializer for tick data CSV export.

    Provides a simplified format optimized for backtesting and analysis.

    Requirements: 7.1, 7.2, 12.1
    """

    class Meta:
        model = TickData
        fields = [
            "timestamp",
            "instrument",
            "bid",
            "ask",
            "mid",
            "spread",
        ]
        read_only_fields = fields


class StrategyListSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    """
    Serializer for listing available strategies.

    Requirements: 5.1
    """

    id = serializers.CharField(help_text="Strategy identifier")
    name = serializers.CharField(help_text="Strategy name")
    class_name = serializers.CharField(help_text="Strategy class name")
    description = serializers.CharField(help_text="Strategy description")
    config_schema = serializers.JSONField(help_text="Configuration schema")


class StrategyConfigSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    """
    Serializer for strategy configuration schema.

    Requirements: 5.1
    """

    strategy_id = serializers.CharField(help_text="Strategy identifier")
    config_schema = serializers.JSONField(help_text="Configuration schema")


class StrategyStateSerializer(serializers.ModelSerializer):
    """
    Serializer for strategy state.

    Requirements: 5.1, 5.2
    """

    class Meta:
        model = StrategyState
        fields = [
            "current_layer",
            "layer_states",
            "atr_values",
            "normal_atr",
            "last_tick_time",
            "updated_at",
        ]
        read_only_fields = fields


class StrategySerializer(serializers.ModelSerializer):
    """
    Serializer for strategy details.

    Requirements: 5.1, 5.2, 5.3
    """

    account_id = serializers.IntegerField(source="account.id", read_only=True)
    state = StrategyStateSerializer(read_only=True)

    class Meta:
        model = Strategy
        fields = [
            "id",
            "account_id",
            "strategy_type",
            "is_active",
            "config",
            "instruments",
            "started_at",
            "stopped_at",
            "created_at",
            "updated_at",
            "state",
        ]
        read_only_fields = [
            "id",
            "account_id",
            "is_active",
            "started_at",
            "stopped_at",
            "created_at",
            "updated_at",
            "state",
        ]


class StrategyStartSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    """
    Serializer for starting a strategy.

    Requirements: 5.2, 5.3, 5.4
    """

    strategy_type = serializers.CharField(
        required=True,
        help_text="Type of strategy (e.g., 'floor', 'trend_following')",
    )
    config = serializers.JSONField(
        required=True,
        help_text="Strategy configuration parameters",
    )
    instruments = serializers.ListField(
        child=serializers.CharField(),
        required=True,
        help_text="List of currency pairs to trade (e.g., ['EUR_USD', 'GBP_USD'])",
    )

    def validate_instruments(self, value: list[str]) -> list[str]:
        """Validate instruments list is not empty."""
        if not value:
            raise serializers.ValidationError("Instruments list cannot be empty")
        return value


class StrategyStatusSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    """
    Serializer for strategy status.

    Requirements: 5.5
    """

    account_id = serializers.IntegerField(help_text="OANDA account ID")
    has_active_strategy = serializers.BooleanField(
        help_text="Whether account has an active strategy"
    )
    status = serializers.CharField(help_text="Strategy status (idle, trading, paused, error)")
    strategy = StrategySerializer(allow_null=True, help_text="Strategy details if active")
    strategy_state = StrategyStateSerializer(allow_null=True, help_text="Strategy state if active")


class OrderSerializer(serializers.ModelSerializer):
    """
    Serializer for order details.

    Requirements: 8.1, 8.2
    """

    account_id = serializers.IntegerField(source="account.id", read_only=True)
    account_name = serializers.CharField(source="account.account_id", read_only=True)
    strategy_id = serializers.IntegerField(source="strategy.id", read_only=True, allow_null=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "account_id",
            "account_name",
            "strategy_id",
            "order_id",
            "instrument",
            "order_type",
            "direction",
            "units",
            "price",
            "take_profit",
            "stop_loss",
            "status",
            "filled_at",
            "created_at",
        ]
        read_only_fields = fields


class OrderCreateSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    """
    Serializer for creating orders.

    Requirements: 8.1, 8.2
    """

    instrument = serializers.CharField(
        required=True,
        max_length=10,
        help_text="Currency pair (e.g., 'EUR_USD')",
    )
    order_type = serializers.ChoiceField(
        required=True,
        choices=["market", "limit", "stop", "oco"],
        help_text="Type of order",
    )
    direction = serializers.ChoiceField(
        required=True,
        choices=["long", "short"],
        help_text="Trade direction",
    )
    units = serializers.DecimalField(
        required=True,
        max_digits=15,
        decimal_places=2,
        min_value=0.01,
        help_text="Number of units to trade",
    )
    price = serializers.DecimalField(
        required=False,
        allow_null=True,
        max_digits=10,
        decimal_places=5,
        help_text="Order price (required for limit/stop orders)",
    )
    take_profit = serializers.DecimalField(
        required=False,
        allow_null=True,
        max_digits=10,
        decimal_places=5,
        help_text="Take-profit price",
    )
    stop_loss = serializers.DecimalField(
        required=False,
        allow_null=True,
        max_digits=10,
        decimal_places=5,
        help_text="Stop-loss price",
    )
    limit_price = serializers.DecimalField(
        required=False,
        allow_null=True,
        max_digits=10,
        decimal_places=5,
        help_text="Limit price (for OCO orders)",
    )
    stop_price = serializers.DecimalField(
        required=False,
        allow_null=True,
        max_digits=10,
        decimal_places=5,
        help_text="Stop price (for OCO orders)",
    )

    def validate(self, attrs: dict) -> dict:  # pylint: disable=arguments-renamed
        """Validate order data based on order type."""
        order_type = attrs.get("order_type")

        if order_type in ["limit", "stop"] and not attrs.get("price"):
            raise serializers.ValidationError(f"Price is required for {order_type} orders")

        if order_type == "oco" and (not attrs.get("limit_price") or not attrs.get("stop_price")):
            raise serializers.ValidationError(
                "Both limit_price and stop_price are required for OCO orders"
            )

        return attrs


class PositionSerializer(serializers.ModelSerializer):
    """
    Serializer for position details.

    Requirements: 9.1, 9.2
    """

    account_id = serializers.IntegerField(source="account.id", read_only=True)
    account_name = serializers.CharField(source="account.account_id", read_only=True)
    strategy_id = serializers.IntegerField(source="strategy.id", read_only=True, allow_null=True)
    strategy_type = serializers.CharField(
        source="strategy.strategy_type", read_only=True, allow_null=True
    )

    class Meta:
        model = Position
        fields = [
            "id",
            "account_id",
            "account_name",
            "strategy_id",
            "strategy_type",
            "position_id",
            "instrument",
            "direction",
            "units",
            "entry_price",
            "current_price",
            "unrealized_pnl",
            "realized_pnl",
            "layer_number",
            "is_first_lot",
            "opened_at",
            "closed_at",
        ]
        read_only_fields = fields


class EventSerializer(serializers.ModelSerializer):
    """
    Serializer for event data.

    Provides read-only access to event logs with all fields.

    Requirements: 27.1, 27.2, 27.3, 27.4
    """

    username = serializers.CharField(source="user.username", read_only=True, allow_null=True)
    account_id = serializers.CharField(source="account.account_id", read_only=True, allow_null=True)

    class Meta:
        model = Event
        fields = [
            "id",
            "timestamp",
            "category",
            "event_type",
            "severity",
            "username",
            "account_id",
            "description",
            "details",
            "ip_address",
            "user_agent",
        ]
        read_only_fields = fields
