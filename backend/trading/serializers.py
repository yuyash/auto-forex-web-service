"""
Serializers for trading data.

This module contains serializers for:
- Tick data retrieval and export
- Strategy configuration and management

Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 7.1, 7.2, 12.1
"""

from decimal import Decimal

from rest_framework import serializers

from .backtest_models import Backtest, BacktestResult
from .event_models import Event
from .execution_models import ExecutionMetrics, TaskExecution
from .models import Order, Position, Strategy, StrategyConfig, StrategyState
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


class StrategyConfigDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for strategy configuration full details.

    Requirements: 1.1, 1.2, 8.1, 8.7
    """

    user_id = serializers.IntegerField(source="user.id", read_only=True)
    is_in_use = serializers.SerializerMethodField()

    class Meta:
        model = StrategyConfig
        fields = [
            "id",
            "user_id",
            "name",
            "strategy_type",
            "parameters",
            "description",
            "is_in_use",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "user_id", "is_in_use", "created_at", "updated_at"]

    def get_is_in_use(self, obj: StrategyConfig) -> bool:
        """Get whether configuration is in use by active tasks."""
        return obj.is_in_use()


class StrategyConfigListSerializer(serializers.ModelSerializer):
    """
    Serializer for strategy configuration list view (summary only).

    Requirements: 1.1, 1.2, 8.1
    """

    user_id = serializers.IntegerField(source="user.id", read_only=True)
    is_in_use = serializers.SerializerMethodField()

    class Meta:
        model = StrategyConfig
        fields = [
            "id",
            "user_id",
            "name",
            "strategy_type",
            "description",
            "is_in_use",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_is_in_use(self, obj: StrategyConfig) -> bool:
        """Get whether configuration is in use by active tasks."""
        return obj.is_in_use()


class StrategyConfigCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating and updating strategy configurations.

    Includes validation against strategy registry.

    Requirements: 1.1, 1.2, 8.7
    """

    class Meta:
        model = StrategyConfig
        fields = [
            "name",
            "strategy_type",
            "parameters",
            "description",
        ]

    def validate_strategy_type(self, value: str) -> str:
        """Validate strategy type exists in registry."""
        from .strategy_registry import registry

        if not registry.is_registered(value):
            available = ", ".join(registry.list_strategies())
            raise serializers.ValidationError(
                f"Strategy type '{value}' is not registered. " f"Available strategies: {available}"
            )
        return value

    def validate_parameters(self, value: dict) -> dict:
        """Validate parameters is a dictionary."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Parameters must be a JSON object")
        return value

    def validate(self, attrs: dict) -> dict:
        """Validate parameters against strategy schema."""
        strategy_type = attrs.get("strategy_type")
        parameters = attrs.get("parameters", {})

        if strategy_type:
            # Create temporary config for validation
            temp_config = StrategyConfig(
                strategy_type=strategy_type,
                parameters=parameters,
            )

            is_valid, error_message = temp_config.validate_parameters()
            if not is_valid:
                raise serializers.ValidationError({"parameters": error_message})

        return attrs

    def create(self, validated_data: dict) -> StrategyConfig:
        """Create strategy configuration with user from context."""
        user = self.context["request"].user
        validated_data["user"] = user
        return StrategyConfig.objects.create(**validated_data)

    def update(self, instance: StrategyConfig, validated_data: dict) -> StrategyConfig:
        """Update strategy configuration."""
        # Don't allow updating strategy_type if config is in use
        if (
            "strategy_type" in validated_data
            and instance.is_in_use()
            and validated_data["strategy_type"] != instance.strategy_type
        ):
            raise serializers.ValidationError(
                {
                    "strategy_type": "Cannot change strategy type for configuration "
                    "that is in use by active tasks"
                }
            )

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


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

    Requirements: 5.1, 5.2, 5.3, 8.1
    """

    account_id = serializers.IntegerField(source="account.id", read_only=True)
    state = StrategyStateSerializer(read_only=True)
    enable_position_differentiation = serializers.BooleanField(
        source="get_position_diff_enabled",
        read_only=True,
        help_text=("Whether position differentiation is enabled for this strategy"),
    )
    position_diff_increment = serializers.IntegerField(
        source="get_position_diff_increment",
        read_only=True,
        help_text="Position differentiation increment amount",
    )
    position_diff_pattern = serializers.CharField(
        source="get_position_diff_pattern",
        read_only=True,
        help_text="Position differentiation pattern",
    )

    class Meta:
        model = Strategy
        fields = [
            "id",
            "account_id",
            "strategy_type",
            "is_active",
            "config",
            "instrument",
            "started_at",
            "stopped_at",
            "created_at",
            "updated_at",
            "state",
            "enable_position_differentiation",
            "position_diff_increment",
            "position_diff_pattern",
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
            "enable_position_differentiation",
            "position_diff_increment",
            "position_diff_pattern",
        ]


class StrategyStartSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    """
    Serializer for starting a strategy.

    Requirements: 5.2, 5.3, 5.4, 8.1
    """

    strategy_type = serializers.CharField(
        required=True,
        help_text="Type of strategy (e.g., 'floor', 'trend_following')",
    )
    config = serializers.JSONField(
        required=True,
        help_text=(
            "Strategy configuration parameters " "(can include position differentiation settings)"
        ),
    )
    instrument = serializers.CharField(
        required=True,
        max_length=10,
        help_text="Currency pair to trade (e.g., 'USD_JPY', 'EUR_USD')",
    )

    def validate_instrument(self, value: str) -> str:
        """Validate instrument is not empty."""
        if not value or not value.strip():
            raise serializers.ValidationError("Instrument cannot be empty")
        return value

    def validate_config(self, value: dict) -> dict:
        """
        Validate strategy configuration.

        Includes position differentiation settings validation.
        """
        # Validate position differentiation settings if present
        if "enable_position_differentiation" in value and not isinstance(
            value["enable_position_differentiation"], bool
        ):
            raise serializers.ValidationError("enable_position_differentiation must be a boolean")

        if "position_diff_increment" in value:
            increment = value["position_diff_increment"]
            if not isinstance(increment, int) or increment < 1 or increment > 100:
                raise serializers.ValidationError(
                    "position_diff_increment must be between 1 and 100"
                )

        if "position_diff_pattern" in value:
            pattern = value["position_diff_pattern"]
            valid_patterns = ["increment", "decrement", "alternating"]
            if pattern not in valid_patterns:
                raise serializers.ValidationError(
                    f"position_diff_pattern must be one of: " f"{', '.join(valid_patterns)}"
                )

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


class BacktestResultSerializer(serializers.ModelSerializer):
    """
    Serializer for backtest result details.

    Requirements: 12.4
    """

    class Meta:
        model = BacktestResult
        fields = [
            "id",
            "final_balance",
            "total_return",
            "total_pnl",
            "max_drawdown",
            "max_drawdown_amount",
            "sharpe_ratio",
            "total_trades",
            "winning_trades",
            "losing_trades",
            "win_rate",
            "average_win",
            "average_loss",
            "largest_win",
            "largest_loss",
            "profit_factor",
            "average_trade_duration",
            "equity_curve",
            "trade_log",
            "created_at",
        ]
        read_only_fields = fields


class BacktestSerializer(serializers.ModelSerializer):
    """
    Serializer for backtest details.

    Requirements: 12.1, 12.4
    """

    result = BacktestResultSerializer(read_only=True, allow_null=True)
    duration = serializers.CharField(read_only=True)
    is_running = serializers.BooleanField(read_only=True)
    is_completed = serializers.BooleanField(read_only=True)

    class Meta:
        model = Backtest
        fields = [
            "id",
            "strategy_type",
            "config",
            "instrument",
            "start_date",
            "end_date",
            "initial_balance",
            "commission_per_trade",
            "status",
            "progress",
            "error_message",
            "started_at",
            "completed_at",
            "created_at",
            "updated_at",
            "peak_memory_mb",
            "memory_limit_mb",
            "cpu_limit_cores",
            "total_trades",
            "winning_trades",
            "losing_trades",
            "total_return",
            "win_rate",
            "final_balance",
            "equity_curve",
            "trade_log",
            "duration",
            "is_running",
            "is_completed",
            "result",
        ]
        read_only_fields = [
            "id",
            "status",
            "progress",
            "error_message",
            "started_at",
            "completed_at",
            "created_at",
            "updated_at",
            "peak_memory_mb",
            "total_trades",
            "winning_trades",
            "losing_trades",
            "total_return",
            "win_rate",
            "final_balance",
            "equity_curve",
            "trade_log",
            "duration",
            "is_running",
            "is_completed",
            "result",
        ]


class BacktestListSerializer(serializers.ModelSerializer):
    """
    Serializer for backtest list view (summary only).

    Requirements: 12.1, 12.4
    """

    duration = serializers.CharField(read_only=True)
    is_running = serializers.BooleanField(read_only=True)
    is_completed = serializers.BooleanField(read_only=True)

    class Meta:
        model = Backtest
        fields = [
            "id",
            "strategy_type",
            "instrument",
            "start_date",
            "end_date",
            "initial_balance",
            "status",
            "progress",
            "total_trades",
            "total_return",
            "win_rate",
            "final_balance",
            "created_at",
            "completed_at",
            "duration",
            "is_running",
            "is_completed",
        ]
        read_only_fields = fields


class BacktestCreateSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    """
    Serializer for creating backtests.

    Requirements: 12.1, 12.2
    """

    strategy_type = serializers.CharField(
        required=True,
        max_length=50,
        help_text="Type of strategy to backtest (e.g., 'floor', 'trend_following')",
    )
    config = serializers.JSONField(
        required=True,
        help_text="Strategy configuration parameters",
    )
    instrument = serializers.CharField(
        required=True,
        max_length=10,
        help_text="Currency pair to backtest (e.g., 'USD_JPY', 'EUR_USD')",
    )
    start_date = serializers.DateTimeField(
        required=True,
        help_text="Start date for backtest period (ISO format)",
    )
    end_date = serializers.DateTimeField(
        required=True,
        help_text="End date for backtest period (ISO format)",
    )
    initial_balance = serializers.DecimalField(
        required=False,
        max_digits=15,
        decimal_places=2,
        default=Decimal("10000"),
        help_text="Initial account balance for backtest (default: 10000)",
    )
    commission_per_trade = serializers.DecimalField(
        required=False,
        max_digits=10,
        decimal_places=2,
        default=Decimal("0"),
        help_text="Commission to apply per trade (default: 0, bid/ask spread already in tick data)",
    )
    memory_limit_mb = serializers.DecimalField(
        required=False,
        max_digits=10,
        decimal_places=2,
        default=Decimal("2048"),
        help_text="Memory limit in MB (default: 2048)",
    )
    cpu_limit_cores = serializers.IntegerField(
        required=False,
        default=1,
        min_value=1,
        max_value=4,
        help_text="CPU cores limit (default: 1, max: 4)",
    )

    def validate_instrument(self, value: str) -> str:
        """Validate instrument is not empty."""
        if not value or not value.strip():
            raise serializers.ValidationError("Instrument cannot be empty")
        return value

    def validate(self, attrs: dict) -> dict:  # pylint: disable=arguments-renamed
        """Validate backtest configuration."""
        start_date = attrs.get("start_date")
        end_date = attrs.get("end_date")

        if start_date and end_date and start_date >= end_date:
            raise serializers.ValidationError("start_date must be before end_date")

        return attrs


class BacktestStatusSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    """
    Serializer for backtest status.

    Requirements: 12.2
    """

    id = serializers.IntegerField(help_text="Backtest ID")
    status = serializers.CharField(help_text="Backtest status")
    progress = serializers.IntegerField(help_text="Progress percentage (0-100)")
    error_message = serializers.CharField(
        allow_null=True, help_text="Error message if backtest failed"
    )
    started_at = serializers.DateTimeField(
        allow_null=True, help_text="Timestamp when backtest started"
    )
    completed_at = serializers.DateTimeField(
        allow_null=True, help_text="Timestamp when backtest completed"
    )
    duration = serializers.CharField(help_text="Backtest duration")
    is_running = serializers.BooleanField(help_text="Whether backtest is currently running")
    is_completed = serializers.BooleanField(help_text="Whether backtest has completed")


class ExecutionMetricsSerializer(serializers.ModelSerializer):
    """
    Serializer for execution metrics.

    Provides read-only access to performance metrics for completed executions.

    Requirements: 7.1, 7.6, 8.7
    """

    trade_summary = serializers.SerializerMethodField()

    class Meta:
        model = ExecutionMetrics
        fields = [
            "id",
            "execution_id",
            "total_return",
            "total_pnl",
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
            "trade_summary",
            "created_at",
        ]
        read_only_fields = fields

    def get_trade_summary(self, obj: ExecutionMetrics) -> dict:
        """Get trade summary statistics."""
        return obj.get_trade_summary()


class TaskExecutionSerializer(serializers.ModelSerializer):
    """
    Serializer for task execution.

    Provides access to execution tracking information including status,
    timing, and error details.

    Requirements: 7.1, 7.6, 8.7
    """

    duration = serializers.SerializerMethodField()
    metrics = ExecutionMetricsSerializer(read_only=True, allow_null=True)

    class Meta:
        model = TaskExecution
        fields = [
            "id",
            "task_type",
            "task_id",
            "execution_number",
            "status",
            "started_at",
            "completed_at",
            "error_message",
            "error_traceback",
            "duration",
            "metrics",
            "created_at",
        ]
        read_only_fields = fields

    def get_duration(self, obj: TaskExecution) -> str | None:
        """Get formatted execution duration."""
        return obj.get_duration()


class TaskExecutionDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for detailed task execution view with nested metrics.

    Requirements: 7.1, 7.6, 8.7
    """

    duration = serializers.SerializerMethodField()
    metrics = ExecutionMetricsSerializer(read_only=True, allow_null=True)
    has_metrics = serializers.SerializerMethodField()

    class Meta:
        model = TaskExecution
        fields = [
            "id",
            "task_type",
            "task_id",
            "execution_number",
            "status",
            "started_at",
            "completed_at",
            "error_message",
            "error_traceback",
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
