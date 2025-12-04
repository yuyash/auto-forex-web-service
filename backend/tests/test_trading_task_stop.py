"""
Tests for trading task stop position closure functionality.

This module tests the stop_trading_task_execution function and position closure
at task stop based on the sell_on_stop flag.

Requirements: 10.2, 10.3, 10.4
"""

from decimal import Decimal
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.utils import timezone

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from accounts.models import OandaAccount
from trading.enums import TaskStatus, TaskType
from trading.execution_models import TaskExecution
from trading.models import Order, Position, Strategy, StrategyConfig
from trading.services.task_executor import stop_trading_task_execution
from trading.tick_data_models import TickData
from trading.trading_task_models import TradingTask

User = get_user_model()

# Test helpers


@pytest.fixture
def test_user(db):
    """Create a test user."""
    return User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123",
    )


@pytest.fixture
def test_account(db, test_user):
    """Create a test OANDA account."""
    return OandaAccount.objects.create(
        user=test_user,
        account_id="001-001-1234567-001",
        api_token="test_api_token",
        api_type="practice",
        is_active=True,
    )


@pytest.fixture
def test_config(db, test_user):
    """Create a test strategy configuration."""
    return StrategyConfig.objects.create(
        user=test_user,
        name="Test Floor Strategy",
        strategy_type="floor",
        parameters={
            "instrument": "USD_JPY",
            "base_lot_size": 1.0,
            "max_layers": 3,
        },
    )


@pytest.fixture
def test_strategy(db, test_account, test_config):
    """Create a test strategy."""
    return Strategy.objects.create(
        account=test_account,
        strategy_type="floor",
        instrument="USD_JPY",
        is_active=True,
    )


def create_random_position(
    account,
    strategy,
    instrument="USD_JPY",
    direction="long",
    units=1.0,
    entry_price=149.50,
):
    """Create a random position for testing."""
    import uuid

    return Position.objects.create(
        account=account,
        strategy=strategy,
        instrument=instrument,
        direction=direction,
        units=Decimal(str(units)),
        entry_price=Decimal(str(entry_price)),
        current_price=Decimal(str(entry_price)),
        position_id=f"POS-{uuid.uuid4().hex[:12].upper()}",
        opened_at=timezone.now(),
        closed_at=None,
    )


def create_sample_tick(account=None):
    """Create sample tick data in the database."""
    tick = TickData.objects.create(
        account=account,
        timestamp=timezone.now(),
        instrument="USD_JPY",
        bid=Decimal("149.50"),
        ask=Decimal("149.52"),
        mid=Decimal("149.51"),
        spread=Decimal("0.02"),
    )
    return tick


# Property-based tests


@pytest.mark.django_db(transaction=True)
@settings(
    max_examples=50, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    num_open_positions=st.integers(min_value=0, max_value=10),
    sell_on_stop=st.booleans(),
)
def test_property_13_task_stop_closes_positions_when_configured(num_open_positions, sell_on_stop):
    """
    Property 13: Task stop closes positions when configured.

    For any real trading task with sell_on_stop enabled, all open Floor Strategy
    positions should be closed at the current market price when the user stops the task.

    Feature: floor-strategy-enhancements, Property 13
    Validates: Requirements 10.2, 10.4
    """
    # Create test user
    test_user = User.objects.create_user(
        username=f"testuser_{timezone.now().timestamp()}",
        email=f"test_{timezone.now().timestamp()}@example.com",
        password="testpass123",
    )

    # Create test account
    test_account = OandaAccount.objects.create(
        user=test_user,
        account_id=f"001-001-{int(timezone.now().timestamp())}-001",
        api_token="test_api_token",
        api_type="practice",
        is_active=True,
    )

    # Create test config
    test_config = StrategyConfig.objects.create(
        user=test_user,
        name="Test Floor Strategy",
        strategy_type="floor",
        parameters={
            "instrument": "USD_JPY",
            "base_lot_size": 1.0,
            "max_layers": 3,
        },
    )

    # Create test strategy
    test_strategy = Strategy.objects.create(
        account=test_account,
        strategy_type="floor",
        instrument="USD_JPY",
        is_active=True,
    )

    # Create trading task
    task = TradingTask.objects.create(
        user=test_user,
        config=test_config,
        oanda_account=test_account,
        name="Test Task",
        description="Test trading task",
        status=TaskStatus.RUNNING,
        sell_on_stop=sell_on_stop,
    )

    # Create task execution
    TaskExecution.objects.create(
        task_type=TaskType.TRADING,
        task_id=task.pk,
        execution_number=1,
        status=TaskStatus.RUNNING,
        started_at=timezone.now(),
    )

    # Create sample tick for closing positions
    if num_open_positions > 0:
        create_sample_tick(account=test_account)

    # Create open positions
    positions = []
    for i in range(num_open_positions):
        position = create_random_position(
            account=test_account,
            strategy=test_strategy,
            direction="long" if i % 2 == 0 else "short",
            units=1.0 + (i * 0.1),
            entry_price=149.50 + (i * 0.01),
        )
        positions.append(position)

    initial_position_count = Position.objects.filter(
        account=test_account,
        strategy=test_strategy,
        closed_at__isnull=True,
    ).count()

    # Mock the order executor to avoid actual API calls
    with patch("trading.order_executor.OrderExecutor") as mock_executor_class:
        mock_executor = Mock()
        mock_executor_class.return_value = mock_executor
        mock_executor.execute_order.return_value = None

        # Stop the task
        result = stop_trading_task_execution(task.pk)

    # Verify the stop was successful
    assert result["success"] is True

    # Count remaining open positions
    final_position_count = Position.objects.filter(
        account=test_account,
        strategy=test_strategy,
        closed_at__isnull=True,
    ).count()

    # Verify behavior based on sell_on_stop flag
    if sell_on_stop:
        # All positions should be closed
        assert final_position_count == 0, (
            f"Expected all positions to be closed when sell_on_stop=True, "
            f"but {final_position_count} positions remain"
        )

        # Verify close orders were created
        close_orders = Order.objects.filter(
            account=test_account,
            strategy=test_strategy,
        )
        assert close_orders.count() == initial_position_count, (
            f"Expected {initial_position_count} close orders, " f"but got {close_orders.count()}"
        )
    else:
        # Positions should remain unchanged
        assert final_position_count == initial_position_count, (
            f"Expected positions to remain unchanged when sell_on_stop=False, "
            f"but count changed from {initial_position_count} to {final_position_count}"
        )


@pytest.mark.django_db(transaction=True)
@settings(
    max_examples=50, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    num_open_positions=st.integers(min_value=1, max_value=20),
    bid_price=st.floats(min_value=140.0, max_value=160.0),
    ask_price=st.floats(min_value=140.0, max_value=160.0),
)
def test_property_14_task_stop_preserves_positions_when_not_configured(
    num_open_positions, bid_price, ask_price
):
    """
    Property 14: Task stop preserves positions when not configured.

    For any real trading task with sell_on_stop disabled, all open Floor Strategy
    positions should remain open without closure when the user stops the task.

    Feature: floor-strategy-enhancements, Property 14
    Validates: Requirements 10.3
    """
    # Ensure ask >= bid
    if ask_price < bid_price:
        bid_price, ask_price = ask_price, bid_price

    # Create test user
    test_user = User.objects.create_user(
        username=f"testuser_{timezone.now().timestamp()}",
        email=f"test_{timezone.now().timestamp()}@example.com",
        password="testpass123",
    )

    # Create test account
    test_account = OandaAccount.objects.create(
        user=test_user,
        account_id=f"001-001-{int(timezone.now().timestamp())}-001",
        api_token="test_api_token",
        api_type="practice",
        is_active=True,
    )

    # Create test config
    test_config = StrategyConfig.objects.create(
        user=test_user,
        name="Test Floor Strategy",
        strategy_type="floor",
        parameters={
            "instrument": "USD_JPY",
            "base_lot_size": 1.0,
            "max_layers": 3,
        },
    )

    # Create test strategy
    test_strategy = Strategy.objects.create(
        account=test_account,
        strategy_type="floor",
        instrument="USD_JPY",
        is_active=True,
    )

    # Create trading task with sell_on_stop=False
    task = TradingTask.objects.create(
        user=test_user,
        config=test_config,
        oanda_account=test_account,
        name="Test Task",
        description="Test trading task",
        status=TaskStatus.RUNNING,
        sell_on_stop=False,
    )

    # Create task execution
    TaskExecution.objects.create(
        task_type=TaskType.TRADING,
        task_id=task.pk,
        execution_number=1,
        status=TaskStatus.RUNNING,
        started_at=timezone.now(),
    )

    # Create tick with random prices (for potential future use)
    TickData.objects.create(
        account=test_account,
        timestamp=timezone.now(),
        instrument="USD_JPY",
        bid=Decimal(str(bid_price)),
        ask=Decimal(str(ask_price)),
        mid=Decimal(str((bid_price + ask_price) / 2)),
        spread=Decimal(str(ask_price - bid_price)),
    )

    # Create open positions
    positions_data = []
    for i in range(num_open_positions):
        # Use Decimal to avoid floating point precision issues
        units = Decimal(str(1.0 + (i * 0.1)))
        entry_price = Decimal(str(149.50 + (i * 0.01)))

        position = create_random_position(
            account=test_account,
            strategy=test_strategy,
            direction="long" if i % 2 == 0 else "short",
            units=float(units),
            entry_price=float(entry_price),
        )
        positions_data.append(
            {
                "instrument": position.instrument,
                "direction": position.direction,
                "units": position.units,
                "entry_price": position.entry_price,
            }
        )

    initial_position_count = Position.objects.filter(
        account=test_account,
        strategy=test_strategy,
        closed_at__isnull=True,
    ).count()

    # Stop the task
    result = stop_trading_task_execution(task.pk)

    # Verify the stop was successful
    assert result["success"] is True

    # Count remaining open positions
    final_position_count = Position.objects.filter(
        account=test_account,
        strategy=test_strategy,
        closed_at__isnull=True,
    ).count()

    # All positions should remain open
    assert final_position_count == initial_position_count, (
        f"Expected all {initial_position_count} positions to remain open, "
        f"but only {final_position_count} positions remain"
    )

    # Verify position data is unchanged
    remaining_positions = Position.objects.filter(
        account=test_account,
        strategy=test_strategy,
        closed_at__isnull=True,
    ).order_by("pk")

    for i, position in enumerate(remaining_positions):
        original = positions_data[i]
        assert position.instrument == original["instrument"]
        assert position.direction == original["direction"]
        # Compare with quantize to handle decimal precision
        assert position.units.quantize(Decimal("0.01")) == original["units"].quantize(
            Decimal("0.01")
        )
        assert position.entry_price.quantize(Decimal("0.00001")) == original[
            "entry_price"
        ].quantize(Decimal("0.00001"))


# Unit tests


@pytest.mark.django_db
class TestTradingTaskStop:
    """Unit tests for trading task stop functionality."""

    def test_positions_closed_when_sell_on_stop_true(
        self, test_user, test_account, test_config, test_strategy
    ):
        """
        Test positions are closed when sell_on_stop=True.

        Requirements: 10.2, 10.4
        """
        # Create sample tick
        create_sample_tick(account=test_account)

        # Create trading task with sell_on_stop=True
        task = TradingTask.objects.create(
            user=test_user,
            config=test_config,
            oanda_account=test_account,
            name="Test Task",
            description="Test trading task",
            status=TaskStatus.RUNNING,
            sell_on_stop=True,
        )

        # Create task execution
        TaskExecution.objects.create(
            task_type=TaskType.TRADING,
            task_id=task.pk,
            execution_number=1,
            status=TaskStatus.RUNNING,
            started_at=timezone.now(),
        )

        # Add some open positions
        for i in range(3):
            create_random_position(
                account=test_account,
                strategy=test_strategy,
                direction="long" if i % 2 == 0 else "short",
                units=1.0 + i,
            )

        # Verify positions exist
        initial_count = Position.objects.filter(
            account=test_account,
            strategy=test_strategy,
            closed_at__isnull=True,
        ).count()
        assert initial_count == 3

        # Mock the order executor
        with patch("trading.order_executor.OrderExecutor") as mock_executor_class:
            mock_executor = Mock()
            mock_executor_class.return_value = mock_executor
            mock_executor.execute_order.return_value = None

            # Stop the task
            result = stop_trading_task_execution(task.pk)

        # Verify success
        assert result["success"] is True

        # All positions should be closed
        final_count = Position.objects.filter(
            account=test_account,
            strategy=test_strategy,
            closed_at__isnull=True,
        ).count()
        assert final_count == 0

    def test_positions_preserved_when_sell_on_stop_false(
        self, test_user, test_account, test_config, test_strategy
    ):
        """
        Test positions are preserved when sell_on_stop=False.

        Requirements: 10.3
        """
        # Create sample tick
        create_sample_tick(account=test_account)

        # Create trading task with sell_on_stop=False
        task = TradingTask.objects.create(
            user=test_user,
            config=test_config,
            oanda_account=test_account,
            name="Test Task",
            description="Test trading task",
            status=TaskStatus.RUNNING,
            sell_on_stop=False,
        )

        # Create task execution
        TaskExecution.objects.create(
            task_type=TaskType.TRADING,
            task_id=task.pk,
            execution_number=1,
            status=TaskStatus.RUNNING,
            started_at=timezone.now(),
        )

        # Add some open positions
        for i in range(3):
            create_random_position(
                account=test_account,
                strategy=test_strategy,
                direction="long" if i % 2 == 0 else "short",
                units=1.0 + i,
            )

        # Verify positions exist
        initial_count = Position.objects.filter(
            account=test_account,
            strategy=test_strategy,
            closed_at__isnull=True,
        ).count()
        assert initial_count == 3

        # Stop the task
        result = stop_trading_task_execution(task.pk)

        # Verify success
        assert result["success"] is True

        # All positions should remain open
        final_count = Position.objects.filter(
            account=test_account,
            strategy=test_strategy,
            closed_at__isnull=True,
        ).count()
        assert final_count == 3

    def test_close_events_are_logged(self, test_user, test_account, test_config, test_strategy):
        """
        Test close events are logged when positions are closed.

        Requirements: 10.4
        """
        # Create sample tick
        create_sample_tick(account=test_account)

        # Create trading task with sell_on_stop=True
        task = TradingTask.objects.create(
            user=test_user,
            config=test_config,
            oanda_account=test_account,
            name="Test Task",
            description="Test trading task",
            status=TaskStatus.RUNNING,
            sell_on_stop=True,
        )

        # Create task execution
        execution = TaskExecution.objects.create(
            task_type=TaskType.TRADING,
            task_id=task.pk,
            execution_number=1,
            status=TaskStatus.RUNNING,
            started_at=timezone.now(),
        )

        # Add some open positions linked to the trading_task
        positions = []
        for i in range(2):
            pos = Position.objects.create(
                account=test_account,
                strategy=test_strategy,
                trading_task=task,
                position_id=f"TEST_POS_{i}_{timezone.now().timestamp()}",
                instrument="EUR_USD",
                direction="long",
                units=Decimal("1000"),
                entry_price=Decimal("1.10000"),
                current_price=Decimal("1.10100"),
            )
            positions.append(pos)

        # Mock the order executor to avoid actual OANDA calls
        # Note: OrderExecutor is imported locally in task_executor, so patch at definition
        with patch("trading.order_executor.OrderExecutor") as mock_executor_class:
            mock_executor = Mock()
            mock_executor_class.return_value = mock_executor
            mock_executor.execute_order.return_value = None

            # Stop the task
            result = stop_trading_task_execution(task.pk)

            # Verify success
            assert result["success"] is True
            assert result["positions_closed"] == 2

            # Verify positions were closed
            for pos in positions:
                pos.refresh_from_db()
                assert pos.closed_at is not None

            # Verify execution has logs about position closures
            execution.refresh_from_db()
            assert execution.logs is not None
            # Check that logs contain position closure info
            log_text = str(execution.logs)
            assert "Closed" in log_text or "position" in log_text.lower()

    def test_no_positions_to_close(self, test_user, test_account, test_config, test_strategy):
        """
        Test stop_trading_task_execution handles case with no open positions.

        Requirements: 10.2
        """
        # Create sample tick
        create_sample_tick(account=test_account)

        # Create trading task with sell_on_stop=True
        task = TradingTask.objects.create(
            user=test_user,
            config=test_config,
            oanda_account=test_account,
            name="Test Task",
            description="Test trading task",
            status=TaskStatus.RUNNING,
            sell_on_stop=True,
        )

        # Create task execution
        TaskExecution.objects.create(
            task_type=TaskType.TRADING,
            task_id=task.pk,
            execution_number=1,
            status=TaskStatus.RUNNING,
            started_at=timezone.now(),
        )

        # No positions added

        # Stop the task - should not raise error
        result = stop_trading_task_execution(task.pk)

        # Verify success
        assert result["success"] is True

        # No positions, no orders
        assert (
            Position.objects.filter(
                account=test_account,
                strategy=test_strategy,
            ).count()
            == 0
        )
        assert (
            Order.objects.filter(
                account=test_account,
                strategy=test_strategy,
            ).count()
            == 0
        )

    def test_mixed_long_and_short_positions(
        self, test_user, test_account, test_config, test_strategy
    ):
        """
        Test closing mixed long and short positions.

        Requirements: 10.2, 10.4
        """
        # Create sample tick
        sample_tick = create_sample_tick(account=test_account)

        # Create trading task with sell_on_stop=True
        task = TradingTask.objects.create(
            user=test_user,
            config=test_config,
            oanda_account=test_account,
            name="Test Task",
            description="Test trading task",
            status=TaskStatus.RUNNING,
            sell_on_stop=True,
        )

        # Create task execution
        TaskExecution.objects.create(
            task_type=TaskType.TRADING,
            task_id=task.pk,
            execution_number=1,
            status=TaskStatus.RUNNING,
            started_at=timezone.now(),
        )

        # Add mixed positions
        create_random_position(
            account=test_account,
            strategy=test_strategy,
            direction="long",
            units=1.0,
        )
        create_random_position(
            account=test_account,
            strategy=test_strategy,
            direction="short",
            units=2.0,
        )

        # Mock the order executor
        with patch("trading.order_executor.OrderExecutor") as mock_executor_class:
            mock_executor = Mock()
            mock_executor_class.return_value = mock_executor
            mock_executor.execute_order.return_value = None

            # Stop the task
            result = stop_trading_task_execution(task.pk)

        # Verify success
        assert result["success"] is True

        # All positions should be closed
        final_count = Position.objects.filter(
            account=test_account,
            strategy=test_strategy,
            closed_at__isnull=True,
        ).count()
        assert final_count == 0

        # Verify correct exit prices were used
        # Long positions exit at bid, short positions exit at ask
        # Note: Position stores exit price in current_price field
        closed_positions = Position.objects.filter(
            account=test_account,
            strategy=test_strategy,
            closed_at__isnull=False,
        )

        for position in closed_positions:
            if position.direction == "long":
                assert position.current_price == sample_tick.bid
            else:
                assert position.current_price == sample_tick.ask
