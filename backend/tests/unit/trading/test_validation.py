"""Unit tests for validation service."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.market.models import OandaAccount
from apps.trading.models import StrategyConfig
from apps.trading.services.validation import TaskValidator

User = get_user_model()


@pytest.mark.django_db
class TestStrategyConfigurationValidation:
    """Test strategy configuration validation."""

    def test_validate_missing_config(self):
        """Test validation fails when config is None."""
        is_valid, error = TaskValidator.validate_strategy_configuration(None)
        assert not is_valid
        assert error is not None
        assert "required" in error.lower()

    def test_validate_missing_strategy_type(self):
        """Test validation fails when strategy type is missing."""
        config = StrategyConfig(strategy_type="", parameters={})
        is_valid, error = TaskValidator.validate_strategy_configuration(config)
        assert not is_valid
        assert error is not None
        assert "strategy type" in error.lower()

    def test_validate_invalid_parameters_type(self):
        """Test validation fails when parameters is not a dict."""
        config = StrategyConfig(strategy_type="floor", parameters="invalid")
        is_valid, error = TaskValidator.validate_strategy_configuration(config)
        assert not is_valid
        assert error is not None
        assert "dictionary" in error.lower()

    def test_validate_unknown_strategy_type(self):
        """Test validation fails for unknown strategy type."""
        config = StrategyConfig(strategy_type="unknown", parameters={})
        is_valid, error = TaskValidator.validate_strategy_configuration(config)
        assert not is_valid
        assert error is not None
        assert "unknown" in error.lower()

    def test_validate_floor_strategy_missing_params(self):
        """Test validation fails when Floor strategy params are missing."""
        config = StrategyConfig(strategy_type="floor", parameters={})
        is_valid, error = TaskValidator.validate_strategy_configuration(config)
        assert not is_valid
        assert error is not None
        assert "missing" in error.lower()

    def test_validate_floor_strategy_invalid_initial_units(self):
        """Test validation fails for invalid initial_units."""
        config = StrategyConfig(
            strategy_type="floor",
            parameters={
                "initial_units": -100,
                "retracement_threshold": 0.5,
                "take_profit_threshold": 1.0,
                "max_layers": 5,
                "volatility_threshold": 0.01,
            },
        )
        is_valid, error = TaskValidator.validate_strategy_configuration(config)
        assert not is_valid
        assert error is not None
        assert "initial_units" in error.lower()

    def test_validate_floor_strategy_invalid_max_layers(self):
        """Test validation fails for invalid max_layers."""
        config = StrategyConfig(
            strategy_type="floor",
            parameters={
                "initial_units": 1000,
                "retracement_threshold": 0.5,
                "take_profit_threshold": 1.0,
                "max_layers": 20,  # Too many
                "volatility_threshold": 0.01,
            },
        )
        is_valid, error = TaskValidator.validate_strategy_configuration(config)
        assert not is_valid
        assert error is not None
        assert "max_layers" in error.lower()

    def test_validate_floor_strategy_valid_params(self):
        """Test validation succeeds for valid Floor strategy params."""
        config = StrategyConfig(
            strategy_type="floor",
            parameters={
                "initial_units": 1000,
                "retracement_threshold": 0.5,
                "take_profit_threshold": 1.0,
                "max_layers": 5,
                "volatility_threshold": 0.01,
            },
        )
        is_valid, error = TaskValidator.validate_strategy_configuration(config)
        assert is_valid
        assert error is None

    def test_validate_custom_strategy_valid(self):
        """Test validation succeeds for custom strategy."""
        config = StrategyConfig(strategy_type="custom", parameters={"any_param": "any_value"})
        is_valid, error = TaskValidator.validate_strategy_configuration(config)
        assert is_valid
        assert error is None


@pytest.mark.django_db
class TestAccountPermissionsValidation:
    """Test account permissions validation."""

    def test_validate_nonexistent_account(self):
        """Test validation fails for nonexistent account."""
        user = User.objects.create_user(username="testuser", password="testpass")  # type: ignore[attr-defined]
        is_valid, error = TaskValidator.validate_account_permissions(user, 99999)
        assert not is_valid
        assert error is not None
        assert "not found" in error.lower()

    def test_validate_account_wrong_user(self):
        """Test validation fails when user doesn't own account."""
        user1 = User.objects.create_user(username="user1", email="user1@test.com", password="pass1")  # type: ignore[attr-defined]
        user2 = User.objects.create_user(username="user2", email="user2@test.com", password="pass2")  # type: ignore[attr-defined]

        account = OandaAccount.objects.create(
            user=user1,
            account_id="001-001-1234567-001",
            api_type="practice",
            is_used=True,
        )

        is_valid, error = TaskValidator.validate_account_permissions(user2, account.id)
        assert not is_valid
        assert error is not None
        assert "permission" in error.lower()

    def test_validate_inactive_account(self):
        """Test validation fails for inactive account."""
        user = User.objects.create_user(username="testuser", password="testpass")  # type: ignore[attr-defined]
        account = OandaAccount.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_type="practice",
            is_used=False,  # Inactive
        )

        is_valid, error = TaskValidator.validate_account_permissions(user, account.id)
        assert not is_valid
        assert error is not None
        assert "not active" in error.lower()

    def test_validate_account_valid(self):
        """Test validation succeeds for valid account."""
        user = User.objects.create_user(username="testuser", password="testpass")  # type: ignore[attr-defined]
        account = OandaAccount.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_type="practice",
            is_used=True,
        )

        is_valid, error = TaskValidator.validate_account_permissions(user, account.id)
        assert is_valid
        assert error is None


@pytest.mark.django_db
class TestDateRangeValidation:
    """Test date range validation for backtests."""

    def test_validate_missing_start_time(self):
        """Test validation fails when start_time is None."""
        end_time = timezone.now()
        is_valid, error = TaskValidator.validate_backtest_date_range(None, end_time)  # type: ignore[arg-type]
        assert not is_valid
        assert error is not None
        assert "start time" in error.lower()

    def test_validate_missing_end_time(self):
        """Test validation fails when end_time is None."""
        start_time = timezone.now()
        is_valid, error = TaskValidator.validate_backtest_date_range(start_time, None)  # type: ignore[arg-type]
        assert not is_valid
        assert error is not None
        assert "end time" in error.lower()

    def test_validate_end_before_start(self):
        """Test validation fails when end_time is before start_time."""
        now = timezone.now()
        start_time = now
        end_time = now - timedelta(days=1)
        is_valid, error = TaskValidator.validate_backtest_date_range(start_time, end_time)
        assert not is_valid
        assert error is not None
        assert "after" in error.lower()

    def test_validate_start_in_future(self):
        """Test validation fails when start_time is in the future."""
        now = timezone.now()
        start_time = now + timedelta(days=1)
        end_time = now + timedelta(days=2)
        is_valid, error = TaskValidator.validate_backtest_date_range(start_time, end_time)
        assert not is_valid
        assert error is not None
        assert "future" in error.lower()

    def test_validate_end_in_future(self):
        """Test validation fails when end_time is in the future."""
        now = timezone.now()
        start_time = now - timedelta(days=1)
        end_time = now + timedelta(days=1)
        is_valid, error = TaskValidator.validate_backtest_date_range(start_time, end_time)
        assert not is_valid
        assert error is not None
        assert "future" in error.lower()

    def test_validate_range_too_long(self):
        """Test validation fails when date range is too long."""
        now = timezone.now()
        start_time = now - timedelta(days=800)  # More than 2 years
        end_time = now
        is_valid, error = TaskValidator.validate_backtest_date_range(start_time, end_time)
        assert not is_valid
        assert error is not None
        assert "too long" in error.lower()

    def test_validate_valid_date_range(self):
        """Test validation succeeds for valid date range."""
        now = timezone.now()
        start_time = now - timedelta(days=30)
        end_time = now - timedelta(days=1)
        is_valid, error = TaskValidator.validate_backtest_date_range(start_time, end_time)
        assert is_valid
        assert error is None
