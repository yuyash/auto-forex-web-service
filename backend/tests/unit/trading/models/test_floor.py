"""Unit tests for trading floor models."""

import pytest
from django.contrib.auth import get_user_model

from apps.trading.models import (
    FloorSide,
    FloorStrategyLayerState,
    FloorStrategyTaskState,
    TradingTasks,
)

User = get_user_model()


@pytest.mark.django_db
class TestFloorStrategyTaskStateModel:
    """Test FloorStrategyTaskState model."""

    def test_create_floor_strategy_task_state(self):
        """Test creating floor strategy task state."""
        user = User.objects.create_user(    # type: ignore[attr-defined]
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

        from apps.market.enums import ApiType
        from apps.market.models import OandaAccounts
        from apps.trading.models import StrategyConfigurations

        config = StrategyConfigurations.objects.create(
            user=user,
            name="Test Config",
            strategy_type="floor",
            parameters={},
        )

        account = OandaAccounts.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_token="encrypted_token",
            api_type=ApiType.PRACTICE,
        )

        task = TradingTasks.objects.create(
            user=user,
            name="Test Task",
            config=config,
            oanda_account=account,
            instrument="EUR_USD",
        )

        state = FloorStrategyTaskState.objects.create(
            trading_task=task,
        )

        assert state.trading_task == task

    def test_one_to_one_relationship_with_task(self):
        """Test one-to-one relationship with task."""
        user = User.objects.create_user(    # type: ignore[attr-defined]
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

        from apps.market.enums import ApiType
        from apps.market.models import OandaAccounts
        from apps.trading.models import StrategyConfigurations

        config = StrategyConfigurations.objects.create(
            user=user,
            name="Test Config",
            strategy_type="floor",
            parameters={},
        )

        account = OandaAccounts.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_token="encrypted_token",
            api_type=ApiType.PRACTICE,
        )

        task = TradingTasks.objects.create(
            user=user,
            name="Test Task",
            config=config,
            oanda_account=account,
            instrument="EUR_USD",
        )

        state = FloorStrategyTaskState.objects.create(
            trading_task=task,
        )

        # Should be able to access state from task
        assert task.floor_state == state  # type: ignore[attr-defined]


@pytest.mark.django_db
class TestFloorStrategyLayerStateModel:
    """Test FloorStrategyLayerState model."""

    def test_create_floor_strategy_layer_state(self):
        """Test creating floor strategy layer state."""
        user = User.objects.create_user(    # type: ignore[attr-defined]
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

        from apps.market.enums import ApiType
        from apps.market.models import OandaAccounts
        from apps.trading.models import StrategyConfigurations

        config = StrategyConfigurations.objects.create(
            user=user,
            name="Test Config",
            strategy_type="floor",
            parameters={},
        )

        account = OandaAccounts.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_token="encrypted_token",
            api_type=ApiType.PRACTICE,
        )

        task = TradingTasks.objects.create(
            user=user,
            name="Test Task",
            config=config,
            oanda_account=account,
            instrument="EUR_USD",
        )

        task_state = FloorStrategyTaskState.objects.create(
            trading_task=task,
        )

        layer_state = FloorStrategyLayerState.objects.create(
            floor_state=task_state,
            layer_index=0,
        )

        assert layer_state.floor_state == task_state
        assert layer_state.layer_index == 0


@pytest.mark.django_db
class TestFloorSideEnum:
    """Test FloorSide enum."""

    def test_floor_side_values(self):
        """Test FloorSide has expected values."""
        assert FloorSide.LONG == "long"
        assert FloorSide.SHORT == "short"

    def test_floor_side_choices(self):
        """Test FloorSide choices."""
        choices = FloorSide.choices
        assert len(choices) == 2
