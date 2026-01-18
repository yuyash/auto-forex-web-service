"""Unit tests for TradingTasks model."""

import pytest
from django.contrib.auth import get_user_model

from apps.market.models import OandaAccounts
from apps.trading.enums import TaskStatus
from apps.trading.models import StrategyConfigurations, TradingTasks

User = get_user_model()


@pytest.mark.django_db
class TestTradingTasksModel:
    """Test suite for TradingTasks model."""

    @pytest.fixture
    def user(self):
        """Create a test user."""
        return User.objects.create_user(
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

        assert task.id is not None
        assert task.name == "Test Trading Task"
        assert task.user == user
        assert task.config == config
        assert task.oanda_account == oanda_account
        assert task.status == TaskStatus.CREATED
        assert task.created_at is not None

    def test_unique_constraint_on_user_name(self, user, config, oanda_account):
        """Test that (user, name) must be unique."""
        # Create first task
        TradingTasks.objects.create(
            name="Test Task",
            user=user,
            config=config,
            oanda_account=oanda_account,
        )

        # Attempt to create duplicate with same user and name
        with pytest.raises(Exception):  # IntegrityError
            TradingTasks.objects.create(
                name="Test Task",  # Same name
                user=user,  # Same user
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

        task.resume()
        assert task.status == TaskStatus.RUNNING

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

        assert copy.id != original.id
        assert copy.name == "Copied Task"
        assert copy.description == original.description
        assert copy.user == original.user
        assert copy.config == original.config
        assert copy.oanda_account == original.oanda_account
        assert copy.status == TaskStatus.CREATED

    def test_manager_for_user(self, user, config, oanda_account):
        """Test manager method for_user."""
        user2 = User.objects.create_user(
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
        assert user_tasks.first().user == user

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
        assert account_tasks.first().oanda_account == oanda_account
