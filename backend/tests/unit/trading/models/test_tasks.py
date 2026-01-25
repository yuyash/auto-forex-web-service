"""Unit tests for tasks.py module (BacktestTasks and TradingTasks models)."""

from datetime import timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.market.models import OandaAccounts
from apps.trading.enums import DataSource, TaskStatus
from apps.trading.models import BacktestTasks, StrategyConfigurations, TradingTasks

User = get_user_model()


@pytest.mark.django_db
class TestBacktestTasksModel:
    """Test suite for BacktestTasks model."""

    @pytest.fixture
    def user(self):
        """Create a test user."""
        return User.objects.create_user(  # type: ignore[attr-defined]
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

    def test_create_with_uuid_primary_key(self, user, config):
        """Test that BacktestTasks uses UUID as primary key."""
        start_time = timezone.now()
        end_time = start_time + timedelta(days=1)

        task = BacktestTasks.objects.create(
            name="UUID Test",
            user=user,
            config=config,
            data_source=DataSource.POSTGRESQL,
            start_time=start_time,
            end_time=end_time,
        )

        # Verify ID is UUID
        assert isinstance(task.id, UUID)
        assert task.id.version == 4

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

        assert task.id is not None
        assert task.name == "Test Backtest"
        assert task.user == user
        assert task.config == config
        assert task.status == TaskStatus.CREATED
        assert task.created_at is not None
        assert task.updated_at is not None

    def test_unique_constraint_on_user_name(self, user, config):
        """Test that (user, name) must be unique."""
        start_time = timezone.now()
        end_time = start_time + timedelta(days=1)

        BacktestTasks.objects.create(
            name="Test Backtest",
            user=user,
            config=config,
            data_source=DataSource.POSTGRESQL,
            start_time=start_time,
            end_time=end_time,
        )

        with pytest.raises(Exception):
            BacktestTasks.objects.create(
                name="Test Backtest",
                user=user,
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

    def test_pause_method(self, user, config):
        """Test pausing a running backtest task."""
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

        task.pause()
        assert task.status == TaskStatus.PAUSED

    def test_restart_method(self, user, config):
        """Test restarting a completed backtest task."""
        start_time = timezone.now()
        end_time = start_time + timedelta(days=1)

        task = BacktestTasks.objects.create(
            name="Test Backtest",
            user=user,
            config=config,
            data_source=DataSource.POSTGRESQL,
            start_time=start_time,
            end_time=end_time,
            status=TaskStatus.COMPLETED,
            result_data={"test": "data"},
        )

        result = task.restart()
        assert result is True
        assert task.status == TaskStatus.CREATED
        assert task.result_data is None

    def test_resume_method(self, user, config):
        """Test resuming a paused backtest task."""
        start_time = timezone.now()
        end_time = start_time + timedelta(days=1)

        task = BacktestTasks.objects.create(
            name="Test Backtest",
            user=user,
            config=config,
            data_source=DataSource.POSTGRESQL,
            start_time=start_time,
            end_time=end_time,
            status=TaskStatus.PAUSED,
        )

        result = task.resume()
        assert result is True
        assert task.status == TaskStatus.RUNNING

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

        assert copy.id != original.id
        assert copy.name == "Copied Task"
        assert copy.description == original.description
        assert copy.user == original.user
        assert copy.config == original.config
        assert copy.status == TaskStatus.CREATED

    def test_duration_property(self, user, config):
        """Test duration property calculation."""
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

        # No duration when not started
        assert task.duration is None

        # Set started and completed times
        task.started_at = timezone.now()
        task.completed_at = task.started_at + timedelta(hours=2)
        task.save()

        # Duration should be 2 hours
        assert task.duration is not None
        assert task.duration.total_seconds() == pytest.approx(7200, rel=1)

    def test_pip_size_property(self, user, config):
        """Test pip_size property with default and custom values."""
        start_time = timezone.now()
        end_time = start_time + timedelta(days=1)

        # Test default pip_size
        task1 = BacktestTasks.objects.create(
            name="Test 1",
            user=user,
            config=config,
            data_source=DataSource.POSTGRESQL,
            start_time=start_time,
            end_time=end_time,
        )
        assert task1.pip_size == Decimal("0.01")

        # Test custom pip_size
        task2 = BacktestTasks.objects.create(
            name="Test 2",
            user=user,
            config=config,
            data_source=DataSource.POSTGRESQL,
            start_time=start_time,
            end_time=end_time,
            _pip_size=Decimal("0.0001"),
        )
        assert task2.pip_size == Decimal("0.0001")

    def test_validate_configuration_invalid_time_range(self, user, config):
        """Test configuration validation with invalid time range."""
        start_time = timezone.now()
        end_time = start_time - timedelta(days=1)  # End before start

        task = BacktestTasks.objects.create(
            name="Test Backtest",
            user=user,
            config=config,
            data_source=DataSource.POSTGRESQL,
            start_time=start_time,
            end_time=end_time,
        )

        is_valid, error_message = task.validate_configuration()
        assert is_valid is False
        assert error_message is not None
        assert "End time must be after start time" in error_message

    def test_manager_for_user(self, user, config):
        """Test manager method for_user."""
        user2 = User.objects.create_user(  # type: ignore[attr-defined]
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

    def test_manager_running(self, user, config):
        """Test manager method running."""
        start_time = timezone.now()
        end_time = start_time + timedelta(days=1)

        BacktestTasks.objects.create(
            name="Running Task",
            user=user,
            config=config,
            data_source=DataSource.POSTGRESQL,
            start_time=start_time,
            end_time=end_time,
            status=TaskStatus.RUNNING,
        )
        BacktestTasks.objects.create(
            name="Completed Task",
            user=user,
            config=config,
            data_source=DataSource.POSTGRESQL,
            start_time=start_time,
            end_time=end_time,
            status=TaskStatus.COMPLETED,
        )

        running_tasks = BacktestTasks.objects.running()
        assert running_tasks.count() == 1
        assert running_tasks.first().status == TaskStatus.RUNNING  # type: ignore[union-attr]

    def test_manager_completed(self, user, config):
        """Test manager method completed."""
        start_time = timezone.now()
        end_time = start_time + timedelta(days=1)

        BacktestTasks.objects.create(
            name="Running Task",
            user=user,
            config=config,
            data_source=DataSource.POSTGRESQL,
            start_time=start_time,
            end_time=end_time,
            status=TaskStatus.RUNNING,
        )
        BacktestTasks.objects.create(
            name="Completed Task",
            user=user,
            config=config,
            data_source=DataSource.POSTGRESQL,
            start_time=start_time,
            end_time=end_time,
            status=TaskStatus.COMPLETED,
        )

        completed_tasks = BacktestTasks.objects.completed()
        assert completed_tasks.count() == 1
        assert completed_tasks.first().status == TaskStatus.COMPLETED  # type: ignore[union-attr]


@pytest.mark.django_db
class TestTradingTasksModel:
    """Test suite for TradingTasks model."""

    @pytest.fixture
    def user(self):
        """Create a test user."""
        return User.objects.create_user(  # type: ignore[attr-defined]
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

    @pytest.fixture
    def oanda_account(self, user):
        """Create a test OANDA account."""
        return OandaAccounts.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_type="practice",
            is_active=True,
        )

    def test_create_trading_task_with_valid_data(self, user, config, oanda_account):
        """Test creating TradingTasks with valid fields."""
        task = TradingTasks.objects.create(
            name="Test Trading Task",
            description="Test description",
            user=user,
            config=config,
            oanda_account=oanda_account,
            instrument="EUR_USD",
        )

        assert task.pk is not None
        assert task.name == "Test Trading Task"
        assert task.user == user
        assert task.config == config
        assert task.oanda_account == oanda_account
        assert task.status == TaskStatus.CREATED
        assert task.created_at is not None

    def test_unique_constraint_on_user_name(self, user, config, oanda_account):
        """Test that (user, name) must be unique."""
        TradingTasks.objects.create(
            name="Test Task",
            user=user,
            config=config,
            oanda_account=oanda_account,
        )

        with pytest.raises(Exception):
            TradingTasks.objects.create(
                name="Test Task",
                user=user,
                config=config,
                oanda_account=oanda_account,
            )

    def test_start_method(self, user, config, oanda_account):
        """Test starting a trading task."""
        task = TradingTasks.objects.create(
            name="Test Task",
            user=user,
            config=config,
            oanda_account=oanda_account,
        )

        task.start()
        assert task.status == TaskStatus.RUNNING

    def test_stop_method(self, user, config, oanda_account):
        """Test stopping a running trading task."""
        task = TradingTasks.objects.create(
            name="Test Task",
            user=user,
            config=config,
            oanda_account=oanda_account,
            status=TaskStatus.RUNNING,
        )

        task.stop()
        assert task.status == TaskStatus.STOPPED

    def test_resume_method(self, user, config, oanda_account):
        """Test resuming a stopped trading task."""
        task = TradingTasks.objects.create(
            name="Test Task",
            user=user,
            config=config,
            oanda_account=oanda_account,
            status=TaskStatus.STOPPED,
        )

        result = task.resume()
        assert result is True
        assert task.status == TaskStatus.CREATED

    def test_restart_method(self, user, config, oanda_account):
        """Test restarting a completed trading task."""
        task = TradingTasks.objects.create(
            name="Test Task",
            user=user,
            config=config,
            oanda_account=oanda_account,
            status=TaskStatus.COMPLETED,
            result_data={"test": "data"},
            strategy_state={"state": "data"},
        )

        result = task.restart()
        assert result is True
        assert task.status == TaskStatus.CREATED
        assert task.result_data is None
        assert task.strategy_state == {}

    def test_copy_method(self, user, config, oanda_account):
        """Test copying a trading task."""
        original = TradingTasks.objects.create(
            name="Original Task",
            description="Original description",
            user=user,
            config=config,
            oanda_account=oanda_account,
        )

        copy = original.copy("Copied Task")

        assert copy.pk != original.pk
        assert copy.name == "Copied Task"
        assert copy.description == original.description
        assert copy.user == original.user
        assert copy.config == original.config
        assert copy.oanda_account == original.oanda_account
        assert copy.status == TaskStatus.CREATED

    def test_duration_property(self, user, config, oanda_account):
        """Test duration property calculation."""
        task = TradingTasks.objects.create(
            name="Test Task",
            user=user,
            config=config,
            oanda_account=oanda_account,
        )

        # No duration when not started
        assert task.duration is None

        # Set started and completed times
        task.started_at = timezone.now()
        task.completed_at = task.started_at + timedelta(hours=3)
        task.save()

        # Duration should be 3 hours
        assert task.duration is not None
        assert task.duration.total_seconds() == pytest.approx(10800, rel=1)

    def test_pip_size_property(self, user, config, oanda_account):
        """Test pip_size property with default and custom values."""
        # Test default pip_size
        task1 = TradingTasks.objects.create(
            name="Test 1",
            user=user,
            config=config,
            oanda_account=oanda_account,
        )
        assert task1.pip_size == Decimal("0.01")

        # Test custom pip_size
        task2 = TradingTasks.objects.create(
            name="Test 2",
            user=user,
            config=config,
            oanda_account=oanda_account,
            _pip_size=Decimal("0.0001"),
        )
        assert task2.pip_size == Decimal("0.0001")

    def test_has_strategy_state(self, user, config, oanda_account):
        """Test has_strategy_state method."""
        task = TradingTasks.objects.create(
            name="Test Task",
            user=user,
            config=config,
            oanda_account=oanda_account,
        )

        # Empty state
        assert task.has_strategy_state() is False

        # With state
        task.strategy_state = {"key": "value"}
        task.save()
        assert task.has_strategy_state() is True

    def test_can_resume(self, user, config, oanda_account):
        """Test can_resume method."""
        task = TradingTasks.objects.create(
            name="Test Task",
            user=user,
            config=config,
            oanda_account=oanda_account,
            status=TaskStatus.STOPPED,
            strategy_state={"key": "value"},
        )

        # Can resume when stopped with state
        assert task.can_resume() is True

        # Cannot resume when running
        task.status = TaskStatus.RUNNING
        task.save()
        assert task.can_resume() is False

        # Cannot resume without state
        task.status = TaskStatus.STOPPED
        task.strategy_state = {}
        task.save()
        assert task.can_resume() is False

    def test_validate_configuration_invalid_account(self, user, config, oanda_account):
        """Test configuration validation with invalid account."""
        user2 = User.objects.create_user(  # type: ignore[attr-defined]
            username="testuser2",
            email="test2@example.com",
            password="testpass123",
        )

        task = TradingTasks.objects.create(
            name="Test Task",
            user=user2,  # Different user
            config=config,
            oanda_account=oanda_account,  # Account belongs to user1
        )

        is_valid, error_message = task.validate_configuration()
        assert is_valid is False
        assert error_message is not None
        assert "Account does not belong to the user" in error_message

    def test_validate_configuration_inactive_account(self, user, config, oanda_account):
        """Test configuration validation with inactive account."""
        oanda_account.is_active = False
        oanda_account.save()

        task = TradingTasks.objects.create(
            name="Test Task",
            user=user,
            config=config,
            oanda_account=oanda_account,
        )

        is_valid, error_message = task.validate_configuration()
        assert is_valid is False
        assert error_message is not None
        assert "Account is not active" in error_message

    def test_manager_for_user(self, user, config, oanda_account):
        """Test manager method for_user."""
        user2 = User.objects.create_user(  # type: ignore[attr-defined]
            username="testuser2",
            email="test2@example.com",
            password="testpass123",
        )

        TradingTasks.objects.create(
            name="Task 1",
            user=user,
            config=config,
            oanda_account=oanda_account,
        )
        TradingTasks.objects.create(
            name="Task 2",
            user=user2,
            config=config,
            oanda_account=oanda_account,
        )

        user_tasks = TradingTasks.objects.for_user(user)
        assert user_tasks.count() == 1
        assert user_tasks.first().user == user  # type: ignore[union-attr]

    def test_manager_for_account(self, user, config, oanda_account):
        """Test manager method for_account."""
        account2 = OandaAccounts.objects.create(
            user=user,
            account_id="001-001-7654321-001",
            api_type="practice",
            is_active=True,
        )

        TradingTasks.objects.create(
            name="Task 1",
            user=user,
            config=config,
            oanda_account=oanda_account,
        )
        TradingTasks.objects.create(
            name="Task 2",
            user=user,
            config=config,
            oanda_account=account2,
        )

        account_tasks = TradingTasks.objects.for_account(oanda_account)
        assert account_tasks.count() == 1
        assert account_tasks.first().oanda_account == oanda_account  # type: ignore[union-attr]

    def test_manager_active(self, user, config, oanda_account):
        """Test manager method active (alias for running)."""
        TradingTasks.objects.create(
            name="Running Task",
            user=user,
            config=config,
            oanda_account=oanda_account,
            status=TaskStatus.RUNNING,
        )
        TradingTasks.objects.create(
            name="Stopped Task",
            user=user,
            config=config,
            oanda_account=oanda_account,
            status=TaskStatus.STOPPED,
        )

        active_tasks = TradingTasks.objects.active()
        assert active_tasks.count() == 1
        assert active_tasks.first().status == TaskStatus.RUNNING  # type: ignore[union-attr]
