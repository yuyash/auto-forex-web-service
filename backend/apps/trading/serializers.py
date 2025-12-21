"""
Serializers for trading data.

This module contains serializers for:
- Tick data retrieval and export
- Strategy configuration and management
"""

from decimal import Decimal

from rest_framework import serializers
from rest_framework.request import Request

from apps.trading.models import BacktestTask
from apps.market.models import OandaAccount, TickData
from apps.trading.models import ExecutionMetrics, TaskExecution, StrategyConfig, TradingTask
from apps.trading.services.registry import registry


class TickDataSerializer(serializers.ModelSerializer):
    """
    Serializer for tick data retrieval.

    Provides read-only access to historical tick data with all fields.
    """

    spread = serializers.SerializerMethodField()

    def get_spread(self, obj: TickData) -> Decimal:
        return obj.spread

    class Meta:  # pylint: disable=missing-class-docstring,too-few-public-methods
        model = TickData
        fields = [
            "id",
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
    """

    spread = serializers.SerializerMethodField()

    def get_spread(self, obj: TickData) -> Decimal:
        return obj.spread

    class Meta:  # pylint: disable=missing-class-docstring,too-few-public-methods
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
    """

    user_id = serializers.IntegerField(source="user.id", read_only=True)
    is_in_use = serializers.SerializerMethodField()

    class Meta:  # pylint: disable=missing-class-docstring,too-few-public-methods
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
    """

    user_id = serializers.IntegerField(source="user.id", read_only=True)
    is_in_use = serializers.SerializerMethodField()

    class Meta:  # pylint: disable=missing-class-docstring,too-few-public-methods
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
    """

    class Meta:  # pylint: disable=missing-class-docstring,too-few-public-methods
        model = StrategyConfig
        fields = [
            "name",
            "strategy_type",
            "parameters",
            "description",
        ]

    def validate_strategy_type(self, value: str) -> str:
        """Validate strategy type exists in registry."""
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

        normalized_parameters = parameters
        if strategy_type == "floor":
            normalized_parameters = self._normalize_floor_parameters(parameters)

        if strategy_type:
            # Create temporary config for validation
            temp_config = StrategyConfig(
                strategy_type=strategy_type,
                parameters=normalized_parameters,
            )

            is_valid, error_message = temp_config.validate_parameters()
            if not is_valid:
                raise serializers.ValidationError({"parameters": error_message})

        attrs["parameters"] = normalized_parameters
        return attrs

    @staticmethod
    def _normalize_floor_parameters(parameters: dict) -> dict:
        """Drop unused floor strategy fields based on progression choices."""
        normalized = dict(parameters)

        # Rename legacy scaling fields to retracement lot fields.

        # retracement_trigger_base is deprecated; always derive from max retracements
        normalized.pop("retracement_trigger_base", None)

        retracement_progression = normalized.get("retracement_trigger_progression", "additive")
        if retracement_progression not in {"additive", "exponential"}:
            normalized.pop("retracement_trigger_increment", None)

        lot_progression = normalized.get("lot_size_progression", "additive")
        if lot_progression not in {"additive", "exponential"}:
            normalized.pop("lot_size_increment", None)

        return normalized

    def create(self, validated_data: dict) -> StrategyConfig:
        """Create strategy configuration with user from context."""
        request: Request = self.context["request"]
        user = request.user
        # Type narrowing: request.user is authenticated in view
        return StrategyConfig.objects.create_for_user(user, **validated_data)

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
    """

    id = serializers.CharField(help_text="Strategy identifier")
    name = serializers.CharField(help_text="Strategy name")
    class_name = serializers.CharField(help_text="Strategy class name")
    description = serializers.CharField(help_text="Strategy description")
    config_schema = serializers.JSONField(help_text="Configuration schema")


class StrategyConfigSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    """
    Serializer for strategy configuration schema.
    """

    strategy_id = serializers.CharField(help_text="Strategy identifier")
    config_schema = serializers.JSONField(help_text="Configuration schema")


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


class TradingTaskSerializer(serializers.ModelSerializer):
    """
    Serializer for TradingTask full details.
    """

    user_id = serializers.IntegerField(source="user.id", read_only=True)
    config_id = serializers.IntegerField(source="config.id", read_only=True)
    config_name = serializers.CharField(source="config.name", read_only=True)
    strategy_type = serializers.CharField(source="config.strategy_type", read_only=True)
    instrument = serializers.SerializerMethodField()
    account_id = serializers.IntegerField(source="oanda_account.id", read_only=True)
    account_name = serializers.CharField(source="oanda_account.account_id", read_only=True)
    account_type = serializers.CharField(source="oanda_account.api_type", read_only=True)
    latest_execution = serializers.SerializerMethodField()
    # State management fields for frontend button logic
    has_strategy_state = serializers.SerializerMethodField()
    can_resume = serializers.SerializerMethodField()

    class Meta:
        model = TradingTask
        fields = [
            "id",
            "user_id",
            "config_id",
            "config_name",
            "strategy_type",
            "instrument",
            "account_id",
            "account_name",
            "account_type",
            "name",
            "description",
            "sell_on_stop",
            "status",
            "latest_execution",
            # State management fields
            "has_strategy_state",
            "can_resume",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "user_id",
            "config_id",
            "config_name",
            "strategy_type",
            "instrument",
            "account_id",
            "account_name",
            "account_type",
            "status",
            "latest_execution",
            "has_strategy_state",
            "can_resume",
            "created_at",
            "updated_at",
        ]

    def get_instrument(self, obj: TradingTask) -> str:
        """Get instrument from configuration parameters."""
        if obj.config and obj.config.parameters:
            instrument = obj.config.parameters.get("instrument")
            if instrument:
                return str(instrument)
        return "EUR_USD"

    def get_has_strategy_state(self, obj: TradingTask) -> bool:
        """Check if task has saved strategy state."""
        return obj.has_strategy_state()

    def get_can_resume(self, obj: TradingTask) -> bool:
        """Check if task can be resumed with state recovery."""
        return obj.can_resume()

    def get_latest_execution(self, obj: TradingTask) -> dict | None:
        """Get summary of latest execution with metrics."""
        execution = obj.get_latest_execution()
        if not execution:
            return None

        result = {
            "id": execution.id,
            "execution_number": execution.execution_number,
            "status": execution.status,
            "started_at": execution.started_at,
            "completed_at": execution.completed_at,
        }

        # Include metrics if available
        if hasattr(execution, "metrics") and execution.metrics:
            metrics = execution.metrics
            result.update(
                {
                    "total_pnl": str(metrics.total_pnl),
                    "realized_pnl": str(metrics.realized_pnl),
                    "unrealized_pnl": str(metrics.unrealized_pnl),
                    "total_trades": metrics.total_trades,
                    "winning_trades": metrics.winning_trades,
                    "losing_trades": metrics.losing_trades,
                    "win_rate": str(metrics.win_rate),
                }
            )
        else:
            # Default values when no metrics exist yet
            result.update(
                {
                    "total_pnl": "0.00",
                    "realized_pnl": "0.00",
                    "unrealized_pnl": "0.00",
                    "total_trades": 0,
                    "winning_trades": 0,
                    "losing_trades": 0,
                    "win_rate": "0.00",
                }
            )

        return result


class TradingTaskListSerializer(serializers.ModelSerializer):
    """
    Serializer for TradingTask list view (summary only).
    """

    user_id = serializers.IntegerField(source="user.id", read_only=True)
    config_id = serializers.IntegerField(source="config.id", read_only=True)
    config_name = serializers.CharField(source="config.name", read_only=True)
    strategy_type = serializers.CharField(source="config.strategy_type", read_only=True)
    instrument = serializers.SerializerMethodField()
    account_id = serializers.IntegerField(source="oanda_account.id", read_only=True)
    account_name = serializers.CharField(source="oanda_account.account_id", read_only=True)
    account_type = serializers.CharField(source="oanda_account.api_type", read_only=True)

    class Meta:
        model = TradingTask
        fields = [
            "id",
            "user_id",
            "config_id",
            "config_name",
            "strategy_type",
            "instrument",
            "account_id",
            "account_name",
            "account_type",
            "name",
            "description",
            "sell_on_stop",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_instrument(self, obj: TradingTask) -> str:
        """Get instrument from configuration parameters."""
        if obj.config and obj.config.parameters:
            instrument = obj.config.parameters.get("instrument")
            if instrument:
                return str(instrument)
        return "EUR_USD"


class TradingTaskCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating and updating TradingTask.

    Includes validation for account ownership and configuration.
    """

    class Meta:
        model = TradingTask
        fields = [
            "config",
            "oanda_account",
            "name",
            "description",
            "sell_on_stop",
        ]
        # Make fields optional for partial updates (PATCH)
        extra_kwargs = {
            "config": {"required": False},
            "oanda_account": {"required": False},
            "name": {"required": False},
            "description": {"required": False},
            "sell_on_stop": {"required": False},
        }

    def validate_config(self, value: StrategyConfig) -> StrategyConfig:
        """Validate that config belongs to the user."""
        user = self.context["request"].user
        if value.user != user:
            raise serializers.ValidationError("Configuration does not belong to the current user")
        return value

    def validate_oanda_account(self, value: OandaAccount) -> OandaAccount:
        """Validate that account belongs to the user and is active."""
        user = self.context["request"].user
        if value.user != user:
            raise serializers.ValidationError("Account does not belong to the current user")
        if not value.is_active:
            raise serializers.ValidationError("Account is not active")
        return value

    def validate(self, attrs: dict) -> dict:
        """Validate configuration parameters."""
        # Validate configuration parameters
        config = attrs.get("config")
        if config:
            is_valid, error_message = config.validate_parameters()
            if not is_valid:
                raise serializers.ValidationError({"config": error_message})

            # Validate configuration has instrument parameter
            if not config.parameters.get("instrument"):
                raise serializers.ValidationError(
                    {"config": "Configuration must have an instrument parameter"}
                )

        return attrs

    def create(self, validated_data: dict) -> TradingTask:
        """Create trading task with user from context."""
        user = self.context["request"].user
        validated_data["user"] = user
        return TradingTask.objects.create(**validated_data)

    def update(self, instance: TradingTask, validated_data: dict) -> TradingTask:
        """Update trading task."""
        # Don't allow updating if task is running
        if instance.status == "running":
            raise serializers.ValidationError("Cannot update a running task. Stop it first.")

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class BacktestTaskSerializer(serializers.ModelSerializer):
    """Serializer for BacktestTask full details."""

    user_id = serializers.IntegerField(source="user.id", read_only=True)
    config_id = serializers.IntegerField(source="config.id", read_only=True)
    config_name = serializers.CharField(source="config.name", read_only=True)
    strategy_type = serializers.CharField(source="config.strategy_type", read_only=True)
    latest_execution = serializers.SerializerMethodField()

    class Meta:
        model = BacktestTask
        fields = [
            "id",
            "user_id",
            "config_id",
            "config_name",
            "strategy_type",
            "name",
            "description",
            "data_source",
            "start_time",
            "end_time",
            "initial_balance",
            "commission_per_trade",
            "instrument",
            "status",
            "latest_execution",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "user_id",
            "config_id",
            "config_name",
            "strategy_type",
            "status",
            "latest_execution",
            "created_at",
            "updated_at",
        ]

    def get_latest_execution(self, obj: BacktestTask) -> dict | None:
        """Get summary of latest execution."""
        execution = obj.get_latest_execution()
        if not execution:
            return None

        return {
            "id": execution.id,
            "execution_number": execution.execution_number,
            "status": execution.status,
            "started_at": execution.started_at,
            "completed_at": execution.completed_at,
        }


class BacktestTaskListSerializer(serializers.ModelSerializer):
    """Serializer for BacktestTask list view (summary only)."""

    user_id = serializers.IntegerField(source="user.id", read_only=True)
    config_id = serializers.IntegerField(source="config.id", read_only=True)
    config_name = serializers.CharField(source="config.name", read_only=True)
    strategy_type = serializers.CharField(source="config.strategy_type", read_only=True)

    class Meta:
        model = BacktestTask
        fields = [
            "id",
            "user_id",
            "config_id",
            "config_name",
            "strategy_type",
            "name",
            "description",
            "data_source",
            "start_time",
            "end_time",
            "initial_balance",
            "instrument",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class BacktestTaskCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating BacktestTask."""

    class Meta:
        model = BacktestTask
        fields = [
            "config",
            "name",
            "description",
            "data_source",
            "start_time",
            "end_time",
            "initial_balance",
            "commission_per_trade",
        ]
        # Make fields optional for partial updates (PATCH)
        extra_kwargs = {
            "config": {"required": False},
            "name": {"required": False},
            "data_source": {"required": False},
            "start_time": {"required": False},
            "end_time": {"required": False},
            "initial_balance": {"required": False},
            "commission_per_trade": {"required": False},
        }

    def validate_config(self, value: StrategyConfig) -> StrategyConfig:
        """Validate that config belongs to the user."""
        user = self.context["request"].user
        if value.user != user:
            raise serializers.ValidationError("Configuration does not belong to the current user")
        return value

    def validate_initial_balance(self, value: Decimal) -> Decimal:
        """Validate initial balance is positive."""
        if value <= 0:
            raise serializers.ValidationError("Initial balance must be positive")
        return value

    def validate(self, attrs: dict) -> dict:
        """Validate date ranges and configuration."""
        from django.utils import timezone

        start_time = attrs.get("start_time")
        end_time = attrs.get("end_time")
        now = timezone.now()

        # Validate date range
        if start_time and end_time and start_time >= end_time:
            raise serializers.ValidationError({"start_time": "start_time must be before end_time"})

        # Validate end_time is not in the future
        if end_time and end_time > now:
            raise serializers.ValidationError(
                {
                    "end_time": (
                        "end_time cannot be in the future. Backtesting requires historical data."
                    )
                }
            )

        # Validate start_time is not in the future
        if start_time and start_time > now:
            raise serializers.ValidationError(
                {
                    "start_time": (
                        "start_time cannot be in the future. Backtesting requires historical data."
                    )
                }
            )

        # Validate configuration parameters
        config = attrs.get("config")
        if config:
            is_valid, error_message = config.validate_parameters()
            if not is_valid:
                raise serializers.ValidationError({"config": error_message})

            # Validate configuration has instrument parameter
            if not config.parameters.get("instrument"):
                raise serializers.ValidationError(
                    {"config": "Configuration must have an instrument parameter"}
                )

        return attrs

    def create(self, validated_data: dict) -> BacktestTask:
        """Create backtest task with user from context."""
        user = self.context["request"].user
        validated_data["user"] = user
        return BacktestTask.objects.create(**validated_data)

    def update(self, instance: BacktestTask, validated_data: dict) -> BacktestTask:
        """Update backtest task."""
        # Don't allow updating if task is running
        if instance.status == "running":
            raise serializers.ValidationError("Cannot update a running task. Stop it first.")

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
