"""
Unit tests for serializers.

Tests the BacktestSerializer and TradingTaskSerializer to ensure
new fields (sell_at_completion, sell_on_stop) are properly included
in API responses and can be serialized/deserialized correctly.

Requirements: 9.1, 9.5, 10.1, 10.5
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone

import pytest

from accounts.models import OandaAccount
from trading.backtest_models import Backtest
from trading.models import StrategyConfig
from trading.serializers import BacktestCreateSerializer, BacktestListSerializer, BacktestSerializer
from trading.trading_task_models import TradingTask
from trading.trading_task_serializers import (
    TradingTaskCreateSerializer,
    TradingTaskListSerializer,
    TradingTaskSerializer,
)

User = get_user_model()


@pytest.fixture
def user(db):
    """Create test user."""
    return User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123",
    )


@pytest.fixture
def strategy_config(db, user):
    """Create test strategy configuration."""
    return StrategyConfig.objects.create(
        user=user,
        name="Test Strategy",
        strategy_type="floor",
        parameters={
            "base_lot_size": 1.0,
            "scaling_mode": "additive",
            "scaling_amount": 1.0,
            "retracement_pips": 30,
            "take_profit_pips": 25,
            "max_layers": 3,
            "volatility_lock_multiplier": 5.0,
            "layer_configs": [
                {"retracement_count_trigger": 10, "base_lot_size": 1.0},
                {"retracement_count_trigger": 20, "base_lot_size": 1.0},
                {"retracement_count_trigger": 30, "base_lot_size": 1.0},
            ],
        },
    )


@pytest.fixture
def oanda_account(db, user):
    """Create test OANDA account."""
    return OandaAccount.objects.create(
        user=user,
        account_id="001-001-1234567-001",
        api_type="practice",
        is_active=True,
    )


@pytest.mark.django_db
class TestBacktestSerializer:
    """Test BacktestSerializer includes sell_at_completion field."""

    def test_serializer_includes_sell_at_completion(self, user):
        """
        Test that BacktestSerializer includes sell_at_completion in fields.

        Requirements: 9.1, 9.5
        """
        backtest = Backtest.objects.create(
            user=user,
            strategy_type="floor",
            config={"lot_size": 1.0},
            instrument="EUR_USD",
            start_date=timezone.now() - timedelta(days=7),
            end_date=timezone.now() - timedelta(days=1),
            initial_balance=Decimal("10000.00"),
            sell_at_completion=True,
        )

        serializer = BacktestSerializer(backtest)
        data = serializer.data

        # Verify sell_at_completion is in serialized data
        assert "sell_at_completion" in data
        assert data["sell_at_completion"] is True

    def test_serializer_default_sell_at_completion(self, user):
        """
        Test that sell_at_completion defaults to False when not specified.

        Requirements: 9.1, 9.5
        """
        backtest = Backtest.objects.create(
            user=user,
            strategy_type="floor",
            config={"lot_size": 1.0},
            instrument="EUR_USD",
            start_date=timezone.now() - timedelta(days=7),
            end_date=timezone.now() - timedelta(days=1),
            initial_balance=Decimal("10000.00"),
        )

        serializer = BacktestSerializer(backtest)
        data = serializer.data

        # Verify sell_at_completion defaults to False
        assert "sell_at_completion" in data
        assert data["sell_at_completion"] is False

    def test_list_serializer_includes_sell_at_completion(self, user):
        """
        Test that BacktestListSerializer includes sell_at_completion.

        Requirements: 9.1, 9.5
        """
        backtest = Backtest.objects.create(
            user=user,
            strategy_type="floor",
            config={"lot_size": 1.0},
            instrument="EUR_USD",
            start_date=timezone.now() - timedelta(days=7),
            end_date=timezone.now() - timedelta(days=1),
            initial_balance=Decimal("10000.00"),
            sell_at_completion=True,
        )

        serializer = BacktestListSerializer(backtest)
        data = serializer.data

        # Verify sell_at_completion is in serialized data
        assert "sell_at_completion" in data
        assert data["sell_at_completion"] is True

    def test_create_serializer_accepts_sell_at_completion(self, user):
        """
        Test that BacktestCreateSerializer accepts sell_at_completion.

        Requirements: 9.1, 9.5
        """
        data = {
            "strategy_type": "floor",
            "config": {"lot_size": 1.0},
            "instrument": "EUR_USD",
            "start_date": timezone.now() - timedelta(days=7),
            "end_date": timezone.now() - timedelta(days=1),
            "initial_balance": Decimal("10000.00"),
            "commission_per_trade": Decimal("5.00"),
            "sell_at_completion": True,
        }

        serializer = BacktestCreateSerializer(data=data)

        # Verify serializer is valid
        assert serializer.is_valid(), serializer.errors

        # Verify sell_at_completion is in validated data
        assert serializer.validated_data["sell_at_completion"] is True

    def test_create_serializer_sell_at_completion_optional(self, user):
        """
        Test that sell_at_completion is optional in create serializer.

        Requirements: 9.1, 9.5
        """
        data = {
            "strategy_type": "floor",
            "config": {"lot_size": 1.0},
            "instrument": "EUR_USD",
            "start_date": timezone.now() - timedelta(days=7),
            "end_date": timezone.now() - timedelta(days=1),
            "initial_balance": Decimal("10000.00"),
            "commission_per_trade": Decimal("5.00"),
            # sell_at_completion not provided
        }

        serializer = BacktestCreateSerializer(data=data)

        # Verify serializer is valid
        assert serializer.is_valid(), serializer.errors

        # Verify sell_at_completion defaults to False
        assert serializer.validated_data["sell_at_completion"] is False


@pytest.mark.django_db
class TestTradingTaskSerializer:
    """Test TradingTaskSerializer includes sell_on_stop field."""

    def test_serializer_includes_sell_on_stop(self, user, strategy_config, oanda_account):
        """
        Test that TradingTaskSerializer includes sell_on_stop in fields.

        Requirements: 10.1, 10.5
        """
        trading_task = TradingTask.objects.create(
            user=user,
            config=strategy_config,
            oanda_account=oanda_account,
            name="Test Trading Task",
            description="Test trading task",
            sell_on_stop=True,
        )

        serializer = TradingTaskSerializer(trading_task)
        data = serializer.data

        # Verify sell_on_stop is in serialized data
        assert "sell_on_stop" in data
        assert data["sell_on_stop"] is True

    def test_serializer_default_sell_on_stop(self, user, strategy_config, oanda_account):
        """
        Test that sell_on_stop defaults to False when not specified.

        Requirements: 10.1, 10.5
        """
        trading_task = TradingTask.objects.create(
            user=user,
            config=strategy_config,
            oanda_account=oanda_account,
            name="Test Trading Task",
            description="Test trading task",
        )

        serializer = TradingTaskSerializer(trading_task)
        data = serializer.data

        # Verify sell_on_stop defaults to False
        assert "sell_on_stop" in data
        assert data["sell_on_stop"] is False

    def test_list_serializer_includes_sell_on_stop(self, user, strategy_config, oanda_account):
        """
        Test that TradingTaskListSerializer includes sell_on_stop.

        Requirements: 10.1, 10.5
        """
        trading_task = TradingTask.objects.create(
            user=user,
            config=strategy_config,
            oanda_account=oanda_account,
            name="Test Trading Task",
            description="Test trading task",
            sell_on_stop=True,
        )

        serializer = TradingTaskListSerializer(trading_task)
        data = serializer.data

        # Verify sell_on_stop is in serialized data
        assert "sell_on_stop" in data
        assert data["sell_on_stop"] is True

    def test_create_serializer_accepts_sell_on_stop(self, user, strategy_config, oanda_account):
        """
        Test that TradingTaskCreateSerializer accepts sell_on_stop.

        Requirements: 10.1, 10.5
        """
        data = {
            "config": strategy_config.id,
            "oanda_account": oanda_account.id,
            "name": "Test Trading Task",
            "description": "Test trading task",
            "sell_on_stop": True,
        }

        # Create mock request with user
        class MockRequest:
            def __init__(self, user):
                self.user = user

        serializer = TradingTaskCreateSerializer(data=data, context={"request": MockRequest(user)})

        # Verify serializer is valid
        assert serializer.is_valid(), serializer.errors

        # Create the instance
        trading_task = serializer.save()

        # Verify sell_on_stop was saved
        assert trading_task.sell_on_stop is True

    def test_create_serializer_sell_on_stop_optional(self, user, strategy_config, oanda_account):
        """
        Test that sell_on_stop is optional in create serializer.

        Requirements: 10.1, 10.5
        """
        data = {
            "config": strategy_config.id,
            "oanda_account": oanda_account.id,
            "name": "Test Trading Task",
            "description": "Test trading task",
            # sell_on_stop not provided
        }

        # Create mock request with user
        class MockRequest:
            def __init__(self, user):
                self.user = user

        serializer = TradingTaskCreateSerializer(data=data, context={"request": MockRequest(user)})

        # Verify serializer is valid
        assert serializer.is_valid(), serializer.errors

        # Create the instance
        trading_task = serializer.save()

        # Verify sell_on_stop defaults to False
        assert trading_task.sell_on_stop is False
