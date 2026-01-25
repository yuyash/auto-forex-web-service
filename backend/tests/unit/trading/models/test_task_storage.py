"""Tests for Task model external storage methods."""

import pytest
from django.utils import timezone

from apps.trading.enums import TaskStatus
from apps.trading.models import BacktestTasks, TradingTasks


@pytest.mark.django_db
class TestBacktestTasksStorage:
    """Tests for BacktestTasks external storage methods."""

    @pytest.fixture
    def user(self):
        """Create a test user."""
        from apps.accounts.models import User

        return User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

    @pytest.fixture
    def strategy_config(self, user):
        """Create a test strategy configuration."""
        from apps.trading.models import StrategyConfigurations

        return StrategyConfigurations.objects.create(
            user=user,
            name="Test Strategy",
            strategy_type="floor",
            parameters={},
        )

    @pytest.fixture
    def backtest_task(self, user, strategy_config):
        """Create a test backtest task."""
        return BacktestTasks.objects.create(
            user=user,
            config=strategy_config,
            name="Test Backtest",
            start_time=timezone.now(),
            end_time=timezone.now(),
        )

    def test_set_result_data_small(self, backtest_task):
        """Test setting small result data (stored inline)."""
        small_data = {"result": "success", "value": 42}

        backtest_task.set_result_data(small_data)

        # Verify data is stored inline
        assert backtest_task.result_data == small_data
        assert backtest_task.result_data_external_ref is None

    def test_set_result_data_large(self, backtest_task):
        """Test setting large result data (stored externally)."""
        # Create data larger than 1MB
        large_data = {"data": "x" * (1024 * 1024 + 1)}

        backtest_task.set_result_data(large_data)

        # Verify data is stored externally
        assert backtest_task.result_data is None
        assert backtest_task.result_data_external_ref is not None
        assert backtest_task.result_data_external_ref.startswith("fs://")

    def test_get_result_data_inline(self, backtest_task):
        """Test getting inline result data."""
        small_data = {"result": "success", "value": 42}

        backtest_task.set_result_data(small_data)
        retrieved_data = backtest_task.get_result_data()

        assert retrieved_data == small_data

    def test_get_result_data_external(self, backtest_task):
        """Test getting external result data."""
        # Create data larger than 1MB
        large_data = {"data": "x" * (1024 * 1024 + 1)}

        backtest_task.set_result_data(large_data)
        retrieved_data = backtest_task.get_result_data()

        assert retrieved_data == large_data

    def test_get_result_data_none(self, backtest_task):
        """Test getting None result data."""
        retrieved_data = backtest_task.get_result_data()

        assert retrieved_data is None

    def test_clear_result_data_inline(self, backtest_task):
        """Test clearing inline result data."""
        small_data = {"result": "success", "value": 42}

        backtest_task.set_result_data(small_data)
        backtest_task.clear_result_data()

        # Verify data is cleared
        assert backtest_task.result_data is None
        assert backtest_task.result_data_external_ref is None

    def test_clear_result_data_external(self, backtest_task):
        """Test clearing external result data."""
        # Create data larger than 1MB
        large_data = {"data": "x" * (1024 * 1024 + 1)}

        backtest_task.set_result_data(large_data)
        external_ref = backtest_task.result_data_external_ref

        backtest_task.clear_result_data()

        # Verify data is cleared
        assert backtest_task.result_data is None
        assert backtest_task.result_data_external_ref is None

        # Verify external file is deleted
        from apps.trading.services.storage import ExternalStorageService

        service = ExternalStorageService()
        with pytest.raises(FileNotFoundError):
            service.retrieve_data(None, external_ref)

    def test_restart_clears_external_storage(self, backtest_task):
        """Test that restart clears external storage."""
        # Create data larger than 1MB
        large_data = {"data": "x" * (1024 * 1024 + 1)}

        backtest_task.set_result_data(large_data)
        backtest_task.status = TaskStatus.COMPLETED
        backtest_task.save()

        external_ref = backtest_task.result_data_external_ref

        # Restart task
        backtest_task.restart()

        # Verify data is cleared
        assert backtest_task.result_data is None
        assert backtest_task.result_data_external_ref is None

        # Verify external file is deleted
        from apps.trading.services.storage import ExternalStorageService

        service = ExternalStorageService()
        with pytest.raises(FileNotFoundError):
            service.retrieve_data(None, external_ref)


@pytest.mark.django_db
class TestTradingTasksStorage:
    """Tests for TradingTasks external storage methods."""

    @pytest.fixture
    def user(self):
        """Create a test user."""
        from apps.accounts.models import User

        return User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

    @pytest.fixture
    def strategy_config(self, user):
        """Create a test strategy configuration."""
        from apps.trading.models import StrategyConfigurations

        return StrategyConfigurations.objects.create(
            user=user,
            name="Test Strategy",
            strategy_type="floor",
            parameters={},
        )

    @pytest.fixture
    def oanda_account(self, user):
        """Create a test OANDA account."""
        from apps.market.models import OandaAccounts

        return OandaAccounts.objects.create(
            user=user,
            account_id="test-account-id",
            api_type="practice",
        )

    @pytest.fixture
    def trading_task(self, user, strategy_config, oanda_account):
        """Create a test trading task."""
        return TradingTasks.objects.create(
            user=user,
            config=strategy_config,
            oanda_account=oanda_account,
            name="Test Trading",
        )

    def test_set_result_data_small(self, trading_task):
        """Test setting small result data (stored inline)."""
        small_data = {"result": "success", "value": 42}

        trading_task.set_result_data(small_data)

        # Verify data is stored inline
        assert trading_task.result_data == small_data
        assert trading_task.result_data_external_ref is None

    def test_set_result_data_large(self, trading_task):
        """Test setting large result data (stored externally)."""
        # Create data larger than 1MB
        large_data = {"data": "x" * (1024 * 1024 + 1)}

        trading_task.set_result_data(large_data)

        # Verify data is stored externally
        assert trading_task.result_data is None
        assert trading_task.result_data_external_ref is not None
        assert trading_task.result_data_external_ref.startswith("fs://")

    def test_get_result_data_inline(self, trading_task):
        """Test getting inline result data."""
        small_data = {"result": "success", "value": 42}

        trading_task.set_result_data(small_data)
        retrieved_data = trading_task.get_result_data()

        assert retrieved_data == small_data

    def test_get_result_data_external(self, trading_task):
        """Test getting external result data."""
        # Create data larger than 1MB
        large_data = {"data": "x" * (1024 * 1024 + 1)}

        trading_task.set_result_data(large_data)
        retrieved_data = trading_task.get_result_data()

        assert retrieved_data == large_data

    def test_restart_clears_external_storage(self, trading_task):
        """Test that restart clears external storage."""
        # Create data larger than 1MB
        large_data = {"data": "x" * (1024 * 1024 + 1)}

        trading_task.set_result_data(large_data)
        trading_task.status = TaskStatus.COMPLETED
        trading_task.save()

        external_ref = trading_task.result_data_external_ref

        # Restart task
        trading_task.restart()

        # Verify data is cleared
        assert trading_task.result_data is None
        assert trading_task.result_data_external_ref is None

        # Verify external file is deleted
        from apps.trading.services.storage import ExternalStorageService

        service = ExternalStorageService()
        with pytest.raises(FileNotFoundError):
            service.retrieve_data(None, external_ref)
