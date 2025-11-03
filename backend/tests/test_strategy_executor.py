"""
Unit tests for StrategyExecutor implementation.

Tests cover:
- StrategyExecutor initialization
- Tick data processing
- Order generation from strategy signals
- Strategy state updates
- Error handling
- Validation

Requirements: 5.3
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone

import pytest

from accounts.models import OandaAccount
from trading.base_strategy import BaseStrategy
from trading.models import Order, Strategy, StrategyState
from trading.strategy_executor import StrategyExecutor
from trading.strategy_registry import registry
from trading.tick_data_models import TickData

User = get_user_model()


# Mock strategy for testing
class MockStrategy(BaseStrategy):
    """Mock strategy for testing purposes."""

    def __init__(self, strategy: Strategy) -> None:
        super().__init__(strategy)
        self.on_tick_called = False
        self.on_position_update_called = False
        self.orders_to_return: list[Order] = []

    def on_tick(self, tick_data: TickData) -> list[Order]:
        """Mock on_tick implementation."""
        self.on_tick_called = True
        return self.orders_to_return

    def on_position_update(self, position) -> None:
        """Mock on_position_update implementation."""
        self.on_position_update_called = True

    def validate_config(self, config: dict) -> bool:
        """Mock validate_config implementation."""
        return True


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        username="testuser", email="test@example.com", password="testpass123"
    )


@pytest.fixture
def oanda_account(user):
    """Create a test OANDA account."""
    return OandaAccount.objects.create(
        user=user,
        account_id="001-001-1234567-001",
        api_token="test_token",
        api_type="practice",
        balance=Decimal("10000.00"),
        margin_used=Decimal("1000.00"),
        unrealized_pnl=Decimal("0.00"),
    )


@pytest.fixture
def strategy_config():
    """Create a test strategy configuration."""
    return {
        "base_lot_size": 1.0,
        "retracement_pips": 30,
        "take_profit_pips": 25,
    }


@pytest.fixture
def strategy(oanda_account, strategy_config):
    """Create a test strategy."""
    return Strategy.objects.create(
        account=oanda_account,
        strategy_type="mock",
        is_active=True,
        config=strategy_config,
        instruments=["EUR_USD", "GBP_USD"],
    )


@pytest.fixture
def strategy_state(strategy):
    """Create a test strategy state."""
    return StrategyState.objects.create(
        strategy=strategy,
        current_layer=1,
        layer_states={},
        atr_values={"EUR_USD": "0.0010"},
        normal_atr=Decimal("0.0010"),
    )


@pytest.fixture
def tick_data():
    """Create test tick data."""
    return TickData(
        instrument="EUR_USD",
        timestamp=timezone.now(),
        bid=Decimal("1.1000"),
        ask=Decimal("1.1002"),
        mid=Decimal("1.1001"),
        spread=Decimal("0.0002"),
    )


@pytest.fixture
def mock_strategy_registered():
    """Register mock strategy for testing."""
    # Register the mock strategy
    registry.register("mock", MockStrategy)
    yield
    # Clean up after test
    if registry.is_registered("mock"):
        registry.unregister("mock")


class TestStrategyExecutorInitialization:
    """Test StrategyExecutor initialization."""

    def test_initialization_success(self, strategy, strategy_state, mock_strategy_registered):
        """Test successful executor initialization."""
        executor = StrategyExecutor(strategy)

        assert executor.strategy_model == strategy
        assert executor.account == strategy.account
        assert isinstance(executor.strategy_instance, MockStrategy)

    def test_initialization_unregistered_strategy(self, strategy, strategy_state):
        """Test initialization with unregistered strategy type."""
        strategy.strategy_type = "nonexistent"
        strategy.save()

        with pytest.raises(ValueError, match="is not registered"):
            StrategyExecutor(strategy)


class TestTickProcessing:
    """Test tick data processing."""

    def test_process_tick_success(
        self, strategy, strategy_state, tick_data, mock_strategy_registered
    ):
        """Test successful tick processing."""
        executor = StrategyExecutor(strategy)

        orders = executor.process_tick(tick_data)

        assert isinstance(orders, list)
        assert executor.strategy_instance.on_tick_called is True  # type: ignore[attr-defined]

    def test_process_tick_inactive_strategy(
        self, strategy, strategy_state, tick_data, mock_strategy_registered
    ):
        """Test tick processing with inactive strategy."""
        strategy.is_active = False
        strategy.save()

        executor = StrategyExecutor(strategy)
        orders = executor.process_tick(tick_data)

        assert len(orders) == 0
        assert executor.strategy_instance.on_tick_called is False  # type: ignore[attr-defined]

    def test_process_tick_inactive_instrument(
        self, strategy, strategy_state, tick_data, mock_strategy_registered
    ):
        """Test tick processing with instrument not in strategy's list."""
        tick_data.instrument = "USD_JPY"  # Not in strategy.instruments

        executor = StrategyExecutor(strategy)
        orders = executor.process_tick(tick_data)

        assert len(orders) == 0
        assert executor.strategy_instance.on_tick_called is False  # type: ignore[attr-defined]

    def test_process_tick_invalid_tick_data(
        self, strategy, strategy_state, tick_data, mock_strategy_registered
    ):
        """Test tick processing with invalid tick data."""
        tick_data.bid = None  # Invalid tick data

        executor = StrategyExecutor(strategy)
        orders = executor.process_tick(tick_data)

        assert len(orders) == 0

    def test_process_tick_negative_prices(
        self, strategy, strategy_state, tick_data, mock_strategy_registered
    ):
        """Test tick processing with negative prices."""
        tick_data.bid = Decimal("-1.0")
        tick_data.ask = Decimal("-0.5")

        executor = StrategyExecutor(strategy)
        orders = executor.process_tick(tick_data)

        assert len(orders) == 0

    def test_process_tick_bid_greater_than_ask(
        self, strategy, strategy_state, tick_data, mock_strategy_registered
    ):
        """Test tick processing with bid > ask."""
        tick_data.bid = Decimal("1.1002")
        tick_data.ask = Decimal("1.1000")

        executor = StrategyExecutor(strategy)
        orders = executor.process_tick(tick_data)

        assert len(orders) == 0

    def test_process_tick_with_exception(
        self, strategy, strategy_state, tick_data, mock_strategy_registered
    ):
        """Test tick processing when strategy raises exception."""
        executor = StrategyExecutor(strategy)

        # Make on_tick raise an exception
        def mock_on_tick_error(tick):  # noqa: ARG001
            raise RuntimeError("Test exception")

        executor.strategy_instance.on_tick = mock_on_tick_error  # type: ignore[method-assign]

        orders = executor.process_tick(tick_data)

        assert len(orders) == 0


class TestOrderGeneration:
    """Test order generation from strategy signals."""

    def test_generate_orders_empty_list(
        self, strategy, strategy_state, tick_data, mock_strategy_registered
    ):
        """Test order generation with empty order list."""
        executor = StrategyExecutor(strategy)
        executor.strategy_instance.orders_to_return = []  # type: ignore[attr-defined]

        orders = executor.process_tick(tick_data)

        assert len(orders) == 0

    def test_generate_orders_single_order(
        self, strategy, strategy_state, tick_data, mock_strategy_registered
    ):
        """Test order generation with single order."""
        executor = StrategyExecutor(strategy)

        # Create order signal
        order = Order(
            instrument="EUR_USD",
            order_type="market",
            direction="long",
            units=Decimal("1.0"),
        )
        executor.strategy_instance.orders_to_return = [order]  # type: ignore[attr-defined]

        orders = executor.process_tick(tick_data)

        assert len(orders) == 1
        assert orders[0].account == strategy.account
        assert orders[0].strategy == strategy
        assert orders[0].order_id is not None
        assert orders[0].status == "pending"

    def test_generate_orders_multiple_orders(
        self, strategy, strategy_state, tick_data, mock_strategy_registered
    ):
        """Test order generation with multiple orders."""
        executor = StrategyExecutor(strategy)

        # Create multiple order signals
        order1 = Order(
            instrument="EUR_USD",
            order_type="market",
            direction="long",
            units=Decimal("1.0"),
        )
        order2 = Order(
            instrument="EUR_USD",
            order_type="limit",
            direction="short",
            units=Decimal("2.0"),
            price=Decimal("1.1050"),
        )
        executor.strategy_instance.orders_to_return = [order1, order2]  # type: ignore[attr-defined]

        orders = executor.process_tick(tick_data)

        assert len(orders) == 2
        assert all(o.account == strategy.account for o in orders)
        assert all(o.strategy == strategy for o in orders)
        assert all(o.order_id is not None for o in orders)

    def test_generate_order_with_existing_order_id(
        self, strategy, strategy_state, tick_data, mock_strategy_registered
    ):
        """Test order generation when order already has an ID."""
        executor = StrategyExecutor(strategy)

        # Create order with existing ID
        order = Order(
            order_id="EXISTING-ID-123",
            instrument="EUR_USD",
            order_type="market",
            direction="long",
            units=Decimal("1.0"),
        )
        executor.strategy_instance.orders_to_return = [order]  # type: ignore[attr-defined]

        orders = executor.process_tick(tick_data)

        assert len(orders) == 1
        assert orders[0].order_id == "EXISTING-ID-123"

    def test_generate_order_id_format(
        self, strategy, strategy_state, tick_data, mock_strategy_registered
    ):
        """Test generated order ID format."""
        executor = StrategyExecutor(strategy)

        # Create order without ID
        order = Order(
            instrument="EUR_USD",
            order_type="market",
            direction="long",
            units=Decimal("1.0"),
        )
        executor.strategy_instance.orders_to_return = [order]  # type: ignore[attr-defined]

        orders = executor.process_tick(tick_data)

        assert len(orders) == 1
        assert orders[0].order_id.startswith("ORD-")
        assert len(orders[0].order_id) == 16  # ORD- + 12 hex chars


class TestStrategyStateUpdate:
    """Test strategy state updates."""

    def test_update_strategy_state_success(
        self, strategy, strategy_state, tick_data, mock_strategy_registered
    ):
        """Test successful strategy state update."""
        executor = StrategyExecutor(strategy)

        _ = executor.process_tick(tick_data)

        # Refresh strategy state from database
        strategy_state.refresh_from_db()

        assert strategy_state.last_tick_time is not None
        # Check that last_tick_time is close to tick timestamp (within 1 second)
        time_diff = abs((strategy_state.last_tick_time - tick_data.timestamp).total_seconds())
        assert time_diff < 1.0

    def test_update_strategy_state_creates_state_if_missing(
        self, strategy, tick_data, mock_strategy_registered
    ):
        """Test state creation if it doesn't exist."""
        # Don't create strategy_state fixture
        executor = StrategyExecutor(strategy)

        _ = executor.process_tick(tick_data)

        # State should be created
        assert hasattr(strategy, "state")
        strategy.refresh_from_db()
        assert hasattr(strategy, "state")


class TestValidation:
    """Test tick data validation."""

    def test_validate_tick_valid(
        self, strategy, strategy_state, tick_data, mock_strategy_registered
    ):
        """Test validation with valid tick data."""
        executor = StrategyExecutor(strategy)

        is_valid = executor._validate_tick(tick_data)

        assert is_valid is True

    def test_validate_tick_none_bid(
        self, strategy, strategy_state, tick_data, mock_strategy_registered
    ):
        """Test validation with None bid."""
        executor = StrategyExecutor(strategy)
        tick_data.bid = None

        is_valid = executor._validate_tick(tick_data)

        assert is_valid is False

    def test_validate_tick_none_ask(
        self, strategy, strategy_state, tick_data, mock_strategy_registered
    ):
        """Test validation with None ask."""
        executor = StrategyExecutor(strategy)
        tick_data.ask = None

        is_valid = executor._validate_tick(tick_data)

        assert is_valid is False

    def test_validate_tick_zero_bid(
        self, strategy, strategy_state, tick_data, mock_strategy_registered
    ):
        """Test validation with zero bid."""
        executor = StrategyExecutor(strategy)
        tick_data.bid = Decimal("0")

        is_valid = executor._validate_tick(tick_data)

        assert is_valid is False

    def test_validate_tick_zero_ask(
        self, strategy, strategy_state, tick_data, mock_strategy_registered
    ):
        """Test validation with zero ask."""
        executor = StrategyExecutor(strategy)
        tick_data.ask = Decimal("0")

        is_valid = executor._validate_tick(tick_data)

        assert is_valid is False

    def test_validate_tick_bid_greater_than_ask(
        self, strategy, strategy_state, tick_data, mock_strategy_registered
    ):
        """Test validation with bid >= ask."""
        executor = StrategyExecutor(strategy)
        tick_data.bid = Decimal("1.1002")
        tick_data.ask = Decimal("1.1000")

        is_valid = executor._validate_tick(tick_data)

        assert is_valid is False


class TestExecutorControl:
    """Test executor control methods."""

    def test_stop_executor(self, strategy, strategy_state, mock_strategy_registered):
        """Test stopping the executor."""
        executor = StrategyExecutor(strategy)

        assert strategy.is_active is True

        executor.stop()

        strategy.refresh_from_db()
        assert strategy.is_active is False
        assert strategy.stopped_at is not None

    def test_get_status(self, strategy, strategy_state, mock_strategy_registered):
        """Test getting executor status."""
        executor = StrategyExecutor(strategy)

        status = executor.get_status()

        assert status["strategy_id"] == strategy.id
        assert status["strategy_type"] == "mock"
        assert status["account_id"] == strategy.account.account_id
        assert status["is_active"] is True
        assert status["instruments"] == ["EUR_USD", "GBP_USD"]
        assert "state" in status

    def test_get_status_with_started_at(self, strategy, strategy_state, mock_strategy_registered):
        """Test getting status when strategy has started_at."""
        strategy.started_at = timezone.now()
        strategy.save()

        executor = StrategyExecutor(strategy)
        status = executor.get_status()

        assert status["started_at"] is not None
        assert isinstance(status["started_at"], str)

    def test_repr(self, strategy, strategy_state, mock_strategy_registered):
        """Test executor string representation."""
        executor = StrategyExecutor(strategy)

        repr_str = repr(executor)

        assert "StrategyExecutor" in repr_str
        assert str(strategy.id) in repr_str
        assert "mock" in repr_str
        assert strategy.account.account_id in repr_str


class TestEventLogging:
    """Test event logging functionality."""

    def test_log_execution(self, strategy, strategy_state, tick_data, mock_strategy_registered):
        """Test execution logging."""
        executor = StrategyExecutor(strategy)

        # Create order to generate
        order = Order(
            instrument="EUR_USD",
            order_type="market",
            direction="long",
            units=Decimal("1.0"),
        )
        executor.strategy_instance.orders_to_return = [order]  # type: ignore[attr-defined]

        _ = executor.process_tick(tick_data)

        # Check that event was logged
        from trading.event_models import Event

        events = Event.objects.filter(
            category="trading",
            event_type="tick_processed",
        )

        assert events.exists()
        event = events.first()
        assert event is not None
        assert event.account == strategy.account
        assert "EUR_USD" in event.description
        assert "1 orders" in event.description

    def test_log_error(self, strategy, strategy_state, tick_data, mock_strategy_registered):
        """Test error logging."""
        executor = StrategyExecutor(strategy)

        # Make on_tick raise an exception
        def raise_exception(tick):
            raise RuntimeError("Test exception")

        def mock_on_tick(tick):  # noqa: ARG001
            raise RuntimeError("Test exception")

        executor.strategy_instance.on_tick = mock_on_tick  # type: ignore[method-assign]

        _ = executor.process_tick(tick_data)

        # Check that error event was logged
        from trading.event_models import Event

        events = Event.objects.filter(
            category="trading",
            event_type="tick_processing_error",
        )

        assert events.exists()
        event = events.first()
        assert event is not None
        assert event.account == strategy.account
        assert "Error processing tick" in event.description
        assert "Test exception" in event.description


class TestIntegration:
    """Integration tests for StrategyExecutor."""

    def test_full_tick_processing_flow(
        self, strategy, strategy_state, tick_data, mock_strategy_registered
    ):
        """Test complete tick processing flow."""
        executor = StrategyExecutor(strategy)

        # Setup strategy to return an order
        order = Order(
            instrument="EUR_USD",
            order_type="market",
            direction="long",
            units=Decimal("1.0"),
        )
        executor.strategy_instance.orders_to_return = [order]  # type: ignore[attr-defined]

        # Process tick
        orders = executor.process_tick(tick_data)

        # Verify results
        assert len(orders) == 1
        assert orders[0].account == strategy.account
        assert orders[0].strategy == strategy
        assert orders[0].order_id is not None
        assert orders[0].status == "pending"

        # Verify state was updated
        strategy_state.refresh_from_db()
        # Check that last_tick_time is close to tick timestamp (within 1 second)
        time_diff = abs((strategy_state.last_tick_time - tick_data.timestamp).total_seconds())
        assert time_diff < 1.0

        # Verify event was logged
        from trading.event_models import Event

        events = Event.objects.filter(
            category="trading",
            event_type="tick_processed",
        )
        assert events.exists()

    def test_multiple_ticks_processing(self, strategy, strategy_state, mock_strategy_registered):
        """Test processing multiple ticks in sequence."""
        executor = StrategyExecutor(strategy)

        # Process multiple ticks
        for i in range(5):
            tick = TickData(
                instrument="EUR_USD",
                timestamp=timezone.now(),
                bid=Decimal("1.1000") + Decimal(str(i * 0.0001)),
                ask=Decimal("1.1002") + Decimal(str(i * 0.0001)),
                mid=Decimal("1.1001") + Decimal(str(i * 0.0001)),
                spread=Decimal("0.0002"),
            )

            _ = executor.process_tick(tick)

        # Verify state was updated with last tick
        strategy_state.refresh_from_db()
        assert strategy_state.last_tick_time is not None
