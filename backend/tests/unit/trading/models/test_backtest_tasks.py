"""Unit tests for BacktestTasks model."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.trading.enums import DataSource, TaskStatus
from apps.trading.models import BacktestTasks, StrategyConfigurations

User = get_user_model()


@pytest.mark.django_db
class TestBacktestTasksModel:
    """Test suite for BacktestTasks model."""

    @pytest.fixture
    def user(self):
        """Create a test user."""
        return User.objects.create_user(  # type: ignore[attr-defined]  # type: ignore[attr-defined]
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

    @pytest.fixture
    def config(self, user):
        """Create a test strategy configuration."""
        return StrategyConfigurations.objects.create(
            user=user,
            name="Test Config",
            strategy_type="floor",
            parameters={"param1": "value1"},
        )

    def test_create_backtest_task_with_valid_data(self, user, config):
        """Test creating BacktestTasks with valid fields."""
        start_time = timezone.now()
        end_time = start_time + timedelta(days=1)

        task = BacktestTasks.objects.create(
            name="Test Backtest",
            description="Test description",
            user=user,
            config=config,
            data_source=DataSource.POSTGRESQL,
            start_time=start_time,
            end_time=end_time,
            initial_balance=Decimal("10000.00"),
            commission_per_trade=Decimal("0.00"),
            instrument="EUR_USD",
        )

        assert task.id is not None  # type: ignore[union-attr]
        assert task.name == "Test Backtest"
        assert task.user == user
        assert task.config == config
        assert task.status == TaskStatus.CREATED
        assert task.created_at is not None

    def test_unique_constraint_on_user_name(self, user, config):
        """Test that (user, name) must be unique."""
        start_time = timezone.now()
        end_time = start_time + timedelta(days=1)

        # Create first task
        BacktestTasks.objects.create(
            name="Test Backtest",
            user=user,
            config=config,
            data_source=DataSource.POSTGRESQL,
            start_time=start_time,
            end_time=end_time,
        )

        # Attempt to create duplicate with same user and name
        with pytest.raises(Exception):  # IntegrityError
            BacktestTasks.objects.create(
                name="Test Backtest",  # Same name
                user=user,  # Same user
                config=config,
                data_source=DataSource.POSTGRESQL,
                start_time=start_time,
                end_time=end_time,
            )

    def test_start_method(self, user, config):
        """Test starting a backtest task."""
        start_time = timezone.now()
        end_time = start_time + timedelta(days=1)

        task = BacktestTasks.objects.create(
            name="Test Backtest",
            user=user,
            config=config,
            data_source=DataSource.POSTGRESQL,
            start_time=start_time,
            end_time=end_time,
        )

        task.start()
        assert task.status == TaskStatus.RUNNING

    def test_stop_method(self, user, config):
        """Test stopping a running backtest task."""
        start_time = timezone.now()
        end_time = start_time + timedelta(days=1)

        task = BacktestTasks.objects.create(
            name="Test Backtest",
            user=user,
            config=config,
            data_source=DataSource.POSTGRESQL,
            start_time=start_time,
            end_time=end_time,
            status=TaskStatus.RUNNING,
        )

        task.stop()
        assert task.status == TaskStatus.STOPPED

    def test_copy_method(self, user, config):
        """Test copying a backtest task."""
        start_time = timezone.now()
        end_time = start_time + timedelta(days=1)

        original = BacktestTasks.objects.create(
            name="Original Task",
            description="Original description",
            user=user,
            config=config,
            data_source=DataSource.POSTGRESQL,
            start_time=start_time,
            end_time=end_time,
        )

        copy = original.copy("Copied Task")

        assert copy.id != original.id  # type: ignore[union-attr]
        assert copy.name == "Copied Task"
        assert copy.description == original.description
        assert copy.user == original.user
        assert copy.config == original.config
        assert copy.status == TaskStatus.CREATED

    def test_manager_for_user(self, user, config):
        """Test manager method for_user."""
        user2 = User.objects.create_user(  # type: ignore[attr-defined]  # type: ignore[attr-defined]
            username="testuser2",
            email="test2@example.com",
            password="testpass123",
        )

        start_time = timezone.now()
        end_time = start_time + timedelta(days=1)

        BacktestTasks.objects.create(
            name="Task 1",
            user=user,
            config=config,
            data_source=DataSource.POSTGRESQL,
            start_time=start_time,
            end_time=end_time,
        )
        BacktestTasks.objects.create(
            name="Task 2",
            user=user2,
            config=config,
            data_source=DataSource.POSTGRESQL,
            start_time=start_time,
            end_time=end_time,
        )

        user_tasks = BacktestTasks.objects.for_user(user)
        assert user_tasks.count() == 1
        assert user_tasks.first().user == user  # type: ignore[union-attr]
