"""Integration tests for trading serializers with real DB.

Tests BacktestTaskSerializer, BacktestTaskCreateSerializer,
TradingTaskSerializer, TradingTaskCreateSerializer, and
serializer method fields (get_progress).
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from rest_framework.test import APIRequestFactory

from apps.market.models import TickData
from apps.trading.enums import TaskStatus, TaskType
from apps.trading.models import ExecutionState
from apps.trading.serializers.backtest import (
    BacktestTaskCreateSerializer,
    BacktestTaskSerializer,
)
from apps.trading.serializers.trading import (
    TradingTaskCreateSerializer,
    TradingTaskSerializer,
)
from tests.integration.factories import (
    BacktestTaskFactory,
    OandaAccountFactory,
    StrategyConfigurationFactory,
    TradingTaskFactory,
    UserFactory,
)

factory = APIRequestFactory()


def _fake_request(user):
    """Create a fake DRF request with an authenticated user."""
    request = factory.get("/fake/")
    request.user = user
    return request


@pytest.mark.django_db
class TestBacktestTaskSerializer:
    """Tests for BacktestTaskSerializer with real BacktestTask."""

    def test_serializes_all_fields(self):
        task = BacktestTaskFactory()
        serializer = BacktestTaskSerializer(task)
        data = serializer.data

        assert data["id"] == str(task.pk)
        assert data["user_id"] == task.user.pk
        assert data["config_id"] == str(task.config.pk)
        assert data["config_name"] == task.config.name
        assert data["strategy_type"] == task.config.strategy_type
        assert data["name"] == task.name
        assert data["instrument"] == task.instrument
        assert data["status"] == task.status
        assert "initial_balance" in data
        assert "start_time" in data
        assert "end_time" in data
        assert "created_at" in data
        # progress and current_tick are now served via /summary/ endpoint
        assert "progress" not in data
        assert "current_tick" not in data
        assert "account_currency" not in data


@pytest.mark.django_db
class TestBacktestTaskCreateSerializer:
    """Tests for BacktestTaskCreateSerializer."""

    def test_create_with_valid_data(self):
        user = UserFactory()
        config = StrategyConfigurationFactory(user=user)
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=30)
        end = now - timedelta(days=1)

        # Create tick data so validation passes
        TickData.objects.create(
            instrument="USD_JPY",
            timestamp=start - timedelta(hours=1),
            bid=Decimal("150.000"),
            ask=Decimal("150.005"),
            mid=Decimal("150.0025"),
        )
        TickData.objects.create(
            instrument="USD_JPY",
            timestamp=end + timedelta(hours=1),
            bid=Decimal("151.000"),
            ask=Decimal("151.005"),
            mid=Decimal("151.0025"),
        )

        request = _fake_request(user)
        data = {
            "config": str(config.pk),
            "name": "Test Backtest",
            "data_source": "postgresql",
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
            "initial_balance": "50000.00",
            "instrument": "USD_JPY",
        }

        serializer = BacktestTaskCreateSerializer(data=data, context={"request": request})
        assert serializer.is_valid(), serializer.errors
        task = serializer.save()
        assert task.user == user
        assert task.config == config
        assert task.name == "Test Backtest"

    def test_validation_error_wrong_user_config(self):
        user1 = UserFactory()
        user2 = UserFactory()
        config = StrategyConfigurationFactory(user=user2)
        now = datetime.now(timezone.utc)

        request = _fake_request(user1)
        data = {
            "config": str(config.pk),
            "name": "Bad Backtest",
            "start_time": (now - timedelta(days=30)).isoformat(),
            "end_time": (now - timedelta(days=1)).isoformat(),
            "initial_balance": "10000.00",
            "instrument": "USD_JPY",
        }

        serializer = BacktestTaskCreateSerializer(data=data, context={"request": request})
        assert not serializer.is_valid()
        assert "config" in serializer.errors

    def test_validation_error_negative_balance(self):
        user = UserFactory()
        config = StrategyConfigurationFactory(user=user)
        now = datetime.now(timezone.utc)

        request = _fake_request(user)
        data = {
            "config": str(config.pk),
            "name": "Negative Balance",
            "start_time": (now - timedelta(days=30)).isoformat(),
            "end_time": (now - timedelta(days=1)).isoformat(),
            "initial_balance": "-100.00",
            "instrument": "USD_JPY",
        }

        serializer = BacktestTaskCreateSerializer(data=data, context={"request": request})
        assert not serializer.is_valid()
        assert "initial_balance" in serializer.errors


@pytest.mark.django_db
class TestTradingTaskSerializer:
    """Tests for TradingTaskSerializer with real TradingTask."""

    def test_serializes_all_fields(self):
        task = TradingTaskFactory()
        serializer = TradingTaskSerializer(task)
        data = serializer.data

        assert data["id"] == str(task.pk)
        assert data["user_id"] == task.user.pk
        assert data["config_id"] == str(task.config.pk)
        assert data["config_name"] == task.config.name
        assert data["strategy_type"] == task.config.strategy_type
        assert data["account_id"] == task.oanda_account.pk
        assert data["account_name"] == task.oanda_account.account_id
        assert data["name"] == task.name
        assert data["status"] == task.status
        assert "has_strategy_state" in data
        assert "can_resume" in data
        # current_tick is now served via /summary/ endpoint only
        assert "current_tick" not in data

    def test_instrument_from_config(self):
        user = UserFactory()
        config = StrategyConfigurationFactory(
            user=user,
            parameters={
                "instrument": "EUR_USD",
                "base_lot_size": 1.0,
                "retracement_pips": 30.0,
                "take_profit_pips": 25.0,
                "max_layers": 3,
                "max_retracements_per_layer": 10,
            },
        )
        account = OandaAccountFactory(user=user)
        task = TradingTaskFactory(user=user, config=config, oanda_account=account)
        serializer = TradingTaskSerializer(task)
        assert serializer.data["instrument"] == "EUR_USD"


@pytest.mark.django_db
class TestTradingTaskCreateSerializer:
    """Tests for TradingTaskCreateSerializer."""

    def test_create_with_valid_data(self):
        user = UserFactory()
        config = StrategyConfigurationFactory(user=user)
        account = OandaAccountFactory(user=user)

        request = _fake_request(user)
        data = {
            "config_id": str(config.pk),
            "account_id": account.pk,
            "name": "Live Trading Task",
        }

        serializer = TradingTaskCreateSerializer(data=data, context={"request": request})
        assert serializer.is_valid(), serializer.errors
        task = serializer.save()
        assert task.user == user
        assert task.config == config
        assert task.oanda_account == account

    def test_validation_wrong_user_config(self):
        user1 = UserFactory()
        user2 = UserFactory()
        config = StrategyConfigurationFactory(user=user2)
        account = OandaAccountFactory(user=user1)

        request = _fake_request(user1)
        data = {
            "config_id": str(config.pk),
            "account_id": account.pk,
            "name": "Bad Task",
        }

        serializer = TradingTaskCreateSerializer(data=data, context={"request": request})
        assert not serializer.is_valid()
        assert "config_id" in serializer.errors

    def test_validation_inactive_account(self):
        user = UserFactory()
        config = StrategyConfigurationFactory(user=user)
        account = OandaAccountFactory(user=user, is_active=False)

        request = _fake_request(user)
        data = {
            "config_id": str(config.pk),
            "account_id": account.pk,
            "name": "Inactive Account Task",
        }

        serializer = TradingTaskCreateSerializer(data=data, context={"request": request})
        assert not serializer.is_valid()
        assert "account_id" in serializer.errors

    def test_validation_missing_required_fields(self):
        user = UserFactory()
        request = _fake_request(user)
        data = {"name": "No Config or Account"}

        serializer = TradingTaskCreateSerializer(data=data, context={"request": request})
        assert not serializer.is_valid()


@pytest.mark.django_db
class TestBacktestTaskSerializerProgress:
    """Tests for progress via summary service (moved from serializer)."""

    def test_progress_via_summary_service(self):
        from apps.trading.services.summary import compute_task_summary

        now = datetime.now(timezone.utc)
        start = now - timedelta(days=10)
        end = now - timedelta(days=1)
        midpoint = start + (end - start) / 2

        task = BacktestTaskFactory(
            status=TaskStatus.RUNNING,
            start_time=start,
            end_time=end,
        )
        task.celery_task_id = "celery-progress-test"
        task.save()

        ExecutionState.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=task.pk,
            celery_task_id="celery-progress-test",
            strategy_state={},
            current_balance=Decimal("10000"),
            ticks_processed=500,
            last_tick_timestamp=midpoint,
        )

        result = compute_task_summary(
            task_type="backtest",
            task_id=str(task.pk),
            celery_task_id="celery-progress-test",
        )
        # Midpoint should be ~50%
        assert 45 <= result.progress <= 55

    def test_progress_no_state(self):
        from apps.trading.services.summary import compute_task_summary

        task = BacktestTaskFactory(status=TaskStatus.RUNNING)
        task.celery_task_id = "celery-no-state"
        task.save()

        result = compute_task_summary(
            task_type="backtest",
            task_id=str(task.pk),
            celery_task_id="celery-no-state",
        )
        assert result.progress == 0
