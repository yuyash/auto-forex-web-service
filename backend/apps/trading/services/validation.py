"""
Validation service for trading system.

This module provides validation for task configurations, account permissions,
and date ranges before task execution.
"""

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Optional, Tuple

from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.market.models import OandaAccounts
from apps.trading.models import BacktestTasks, StrategyConfigurations, TradingTasks

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractBaseUser

    User = AbstractBaseUser
else:
    User = get_user_model()

logger = logging.getLogger(__name__)


class TaskValidator:
    """
    Validator for trading task configurations and permissions.

    Provides validation methods for:
    - Strategy configuration
    - Account permissions
    - Date ranges for backtests
    """

    @staticmethod
    def validate_strategy_configuration(
        config: Optional[StrategyConfigurations],
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate strategy configuration.

        Args:
            config: The strategy configuration to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if config is None:
            return False, "Strategy configuration is required"

        # Check if strategy type is set
        if not config.strategy_type:
            return False, "Strategy type must be specified"

        # Check if parameters are valid JSON
        if not isinstance(config.parameters, dict):
            return False, "Strategy parameters must be a valid dictionary"

        # Validate strategy-specific parameters
        if config.strategy_type == "floor":
            return TaskValidator._validate_floor_strategy_params(config.parameters)
        elif config.strategy_type == "custom":
            return TaskValidator._validate_custom_strategy_params(config.parameters)
        else:
            return False, f"Unknown strategy type: {config.strategy_type}"

    @staticmethod
    def _validate_floor_strategy_params(params: dict) -> Tuple[bool, Optional[str]]:
        """
        Validate Floor strategy parameters.

        Args:
            params: Strategy parameters dictionary

        Returns:
            Tuple of (is_valid, error_message)
        """
        required_params = [
            "initial_units",
            "retracement_threshold",
            "take_profit_threshold",
            "max_layers",
            "volatility_threshold",
        ]

        for param in required_params:
            if param not in params:
                return False, f"Missing required parameter: {param}"

        # Validate parameter types and ranges
        try:
            initial_units = int(params["initial_units"])
            if initial_units <= 0:
                return False, "initial_units must be positive"

            retracement_threshold = float(params["retracement_threshold"])
            if retracement_threshold <= 0:
                return False, "retracement_threshold must be positive"

            take_profit_threshold = float(params["take_profit_threshold"])
            if take_profit_threshold <= 0:
                return False, "take_profit_threshold must be positive"

            max_layers = int(params["max_layers"])
            if max_layers <= 0 or max_layers > 10:
                return False, "max_layers must be between 1 and 10"

            volatility_threshold = float(params["volatility_threshold"])
            if volatility_threshold <= 0:
                return False, "volatility_threshold must be positive"

        except (ValueError, TypeError) as e:
            return False, f"Invalid parameter value: {str(e)}"

        return True, None

    @staticmethod
    def _validate_custom_strategy_params(params: dict) -> Tuple[bool, Optional[str]]:
        """
        Validate custom strategy parameters.

        Args:
            params: Strategy parameters dictionary

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Custom strategies can have any parameters
        # Just ensure it's a valid dictionary
        if not isinstance(params, dict):
            return False, "Custom strategy parameters must be a dictionary"

        return True, None

    @staticmethod
    def validate_account_permissions(user: "User", account_id: int) -> Tuple[bool, Optional[str]]:
        """
        Validate that user has permission to use the account.

        Args:
            user: The user requesting access
            account_id: The OANDA account ID

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            account = OandaAccounts.objects.get(id=account_id)
        except OandaAccounts.DoesNotExist:
            return False, f"Account {account_id} not found"

        # Check if user owns the account
        if account.user_id != user.pk:
            return False, f"You do not have permission to use account {account_id}"

        # Check if account is active
        if not account.is_used:
            return False, f"Account {account_id} is not active"

        return True, None

    @staticmethod
    def validate_backtest_date_range(
        start_time: datetime, end_time: datetime
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate date range for backtest.

        Args:
            start_time: Start time for backtest
            end_time: End time for backtest

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check if dates are provided
        if start_time is None:
            return False, "Start time is required"

        if end_time is None:
            return False, "End time is required"

        # Check if end_time is after start_time
        if end_time <= start_time:
            return False, "End time must be after start time"

        # Check if dates are not in the future
        now = timezone.now()
        if start_time > now:
            return False, "Start time cannot be in the future"

        if end_time > now:
            return False, "End time cannot be in the future"

        # Check if date range is reasonable (not too long)
        max_days = 365 * 2  # 2 years
        duration = end_time - start_time
        if duration.days > max_days:
            return (
                False,
                f"Date range is too long. Maximum allowed is {max_days} days",
            )

        return True, None

    @staticmethod
    def validate_backtest_task(task: BacktestTasks) -> Tuple[bool, Optional[str]]:
        """
        Validate a backtest task before starting.

        Args:
            task: The backtest task to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Validate strategy configuration
        is_valid, error = TaskValidator.validate_strategy_configuration(task.config)
        if not is_valid:
            return False, error

        # Validate date range
        is_valid, error = TaskValidator.validate_backtest_date_range(task.start_time, task.end_time)
        if not is_valid:
            return False, error

        # Validate instrument
        if not task.instrument:
            return False, "Instrument is required"

        return True, None

    @staticmethod
    def validate_trading_task(task: TradingTasks, user: "User") -> Tuple[bool, Optional[str]]:
        """
        Validate a trading task before starting.

        Args:
            task: The trading task to validate
            user: The user starting the task

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Validate strategy configuration
        is_valid, error = TaskValidator.validate_strategy_configuration(task.config)
        if not is_valid:
            return False, error

        # Validate account permissions
        is_valid, error = TaskValidator.validate_account_permissions(user, task.account_id)
        if not is_valid:
            return False, error

        # Validate instrument
        if not task.instrument:
            return False, "Instrument is required"

        return True, None
