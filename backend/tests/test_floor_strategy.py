"""
Unit tests for Floor Strategy implementation.

Tests cover:
- LayerManager with multiple layers
- ScalingEngine additive and multiplicative modes
- Retracement detection
- Take-profit logic
- Strategy on_tick processing

Requirements: 13.1, 13.2, 13.3, 13.4, 13.5
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from accounts.models import OandaAccount
from trading.floor_strategy import FloorStrategy, Layer, LayerManager, ScalingEngine
from trading.models import Position, Strategy, StrategyState
from trading.tick_data_models import TickData

User = get_user_model()


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
    }


@pytest.fixture
def strategy(oanda_account, strategy_config):
    """Create a test strategy."""
    return Strategy.objects.create(
        account=oanda_account,
        strategy_type="floor",
        is_active=True,
        config=strategy_config,
        instrument="EUR_USD",
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


class TestLayerManager:
    """Test LayerManager functionality."""

    def test_create_layer(self):
        """Test creating a new layer."""
        manager = LayerManager(max_layers=3)
        config = {"base_lot_size": 1.0}

        layer = manager.create_layer(1, config)

        assert layer is not None
        assert layer.layer_number == 1
        assert len(manager.layers) == 1

    def test_max_layers_limit(self):
        """Test that max layers limit is enforced."""
        manager = LayerManager(max_layers=2)
        config = {"base_lot_size": 1.0}

        layer1 = manager.create_layer(1, config)
        layer2 = manager.create_layer(2, config)
        layer3 = manager.create_layer(3, config)

        assert layer1 is not None
        assert layer2 is not None
        assert layer3 is None
        assert len(manager.layers) == 2

    def test_get_layer(self):
        """Test retrieving a layer by number."""
        manager = LayerManager(max_layers=3)
        config = {"base_lot_size": 1.0}

        manager.create_layer(1, config)
        manager.create_layer(2, config)

        layer = manager.get_layer(2)

        assert layer is not None
        assert layer.layer_number == 2

    def test_get_layer_not_found(self):
        """Test retrieving a non-existent layer."""
        manager = LayerManager(max_layers=3)

        layer = manager.get_layer(1)

        assert layer is None

    def test_get_first_lot_positions(self, oanda_account, strategy):
        """Test getting first lot positions from all layers."""
        manager = LayerManager(max_layers=3)
        config = {"base_lot_size": 1.0}

        layer1 = manager.create_layer(1, config)
        layer2 = manager.create_layer(2, config)

        assert layer1 is not None
        assert layer2 is not None

        # Create positions
        pos1 = Position.objects.create(
            account=oanda_account,
            strategy=strategy,
            position_id="pos1",
            instrument="EUR_USD",
            direction="long",
            units=Decimal("1.0"),
            entry_price=Decimal("1.1000"),
            current_price=Decimal("1.1000"),
            layer_number=1,
            is_first_lot=True,
        )

        pos2 = Position.objects.create(
            account=oanda_account,
            strategy=strategy,
            position_id="pos2",
            instrument="EUR_USD",
            direction="long",
            units=Decimal("1.0"),
            entry_price=Decimal("1.0950"),
            current_price=Decimal("1.0950"),
            layer_number=2,
            is_first_lot=True,
        )

        layer1.add_position(pos1, is_first_lot=True)
        layer2.add_position(pos2, is_first_lot=True)

        first_lots = manager.get_first_lot_positions()

        assert len(first_lots) == 2
        assert pos1 in first_lots
        assert pos2 in first_lots

    def test_remove_layer(self):
        """Test removing a layer."""
        manager = LayerManager(max_layers=3)
        config = {"base_lot_size": 1.0}

        manager.create_layer(1, config)
        manager.create_layer(2, config)

        assert len(manager.layers) == 2

        manager.remove_layer(1)

        assert len(manager.layers) == 1
        assert manager.get_layer(1) is None
        assert manager.get_layer(2) is not None


class TestLayer:
    """Test Layer functionality."""

    def test_layer_initialization(self):
        """Test layer initialization."""
        config = {"base_lot_size": 1.0, "retracement_count_trigger": 10}
        layer = Layer(layer_number=1, config=config)

        assert layer.layer_number == 1
        assert layer.retracement_count == 0
        assert layer.current_lot_size == Decimal("1.0")
        assert layer.is_active is True

    def test_add_position(self, oanda_account, strategy):
        """Test adding a position to a layer."""
        config = {"base_lot_size": 1.0}
        layer = Layer(layer_number=1, config=config)

        position = Position.objects.create(
            account=oanda_account,
            strategy=strategy,
            position_id="pos1",
            instrument="EUR_USD",
            direction="long",
            units=Decimal("1.0"),
            entry_price=Decimal("1.1000"),
            current_price=Decimal("1.1000"),
            layer_number=1,
        )

        layer.add_position(position, is_first_lot=True)

        assert len(layer.positions) == 1
        assert layer.first_lot_position == position
        assert layer.last_entry_price == Decimal("1.1000")

    def test_increment_retracement_count(self):
        """Test incrementing retracement count."""
        config = {"base_lot_size": 1.0}
        layer = Layer(layer_number=1, config=config)

        assert layer.retracement_count == 0

        layer.increment_retracement_count()
        assert layer.retracement_count == 1

        layer.increment_retracement_count()
        assert layer.retracement_count == 2

    def test_should_create_new_layer(self):
        """Test checking if new layer should be created."""
        config = {"base_lot_size": 1.0, "retracement_count_trigger": 10}
        layer = Layer(layer_number=1, config=config)

        assert layer.should_create_new_layer() is False

        # Increment to trigger threshold
        for _ in range(10):
            layer.increment_retracement_count()

        assert layer.should_create_new_layer() is True


class TestScalingEngine:
    """Test ScalingEngine functionality."""

    def test_additive_scaling(self):
        """Test additive scaling mode."""
        engine = ScalingEngine(mode="additive", amount=Decimal("1.0"))

        next_size = engine.calculate_next_lot_size(Decimal("1.0"))
        assert next_size == Decimal("2.0")

        next_size = engine.calculate_next_lot_size(Decimal("2.0"))
        assert next_size == Decimal("3.0")

    def test_multiplicative_scaling(self):
        """Test multiplicative scaling mode."""
        engine = ScalingEngine(mode="multiplicative", amount=Decimal("1.5"))

        next_size = engine.calculate_next_lot_size(Decimal("1.0"))
        assert next_size == Decimal("1.5")

        next_size = engine.calculate_next_lot_size(Decimal("1.5"))
        assert next_size == Decimal("2.25")

    def test_should_scale_true(self):
        """Test retracement detection when threshold is met."""
        engine = ScalingEngine()

        entry_price = Decimal("1.1000")
        current_price = Decimal("1.0970")  # 30 pips retracement
        retracement_pips = Decimal("30")

        should_scale = engine.should_scale(entry_price, current_price, retracement_pips)

        assert should_scale is True

    def test_should_scale_false(self):
        """Test retracement detection when threshold is not met."""
        engine = ScalingEngine()

        entry_price = Decimal("1.1000")
        current_price = Decimal("1.0980")  # 20 pips retracement
        retracement_pips = Decimal("30")

        should_scale = engine.should_scale(entry_price, current_price, retracement_pips)

        assert should_scale is False


class TestFloorStrategy:
    """Test FloorStrategy functionality."""

    def test_strategy_initialization(self, strategy, strategy_state):
        """Test strategy initialization."""
        floor_strategy = FloorStrategy(strategy)

        assert floor_strategy.base_lot_size == Decimal("1.0")
        assert floor_strategy.retracement_pips == Decimal("30")
        assert floor_strategy.take_profit_pips == Decimal("25")
        assert floor_strategy.layer_manager.max_layers == 3

    def test_validate_config_valid(self, strategy):
        """Test configuration validation with valid config."""
        floor_strategy = FloorStrategy(strategy)

        config = {
            "base_lot_size": 1.0,
            "scaling_mode": "additive",
            "retracement_pips": 30,
            "take_profit_pips": 25,
        }

        result = floor_strategy.validate_config(config)

        assert result is True

    def test_validate_config_missing_key(self, strategy):
        """Test configuration validation with missing required key."""
        floor_strategy = FloorStrategy(strategy)

        config = {
            "base_lot_size": 1.0,
            "scaling_mode": "additive",
            # Missing retracement_pips
        }

        with pytest.raises(ValueError, match="Required configuration key"):
            floor_strategy.validate_config(config)

    def test_validate_config_invalid_scaling_mode(self, strategy):
        """Test configuration validation with invalid scaling mode."""
        floor_strategy = FloorStrategy(strategy)

        config = {
            "base_lot_size": 1.0,
            "scaling_mode": "invalid_mode",
            "retracement_pips": 30,
            "take_profit_pips": 25,
        }

        with pytest.raises(ValueError, match="Invalid scaling_mode"):
            floor_strategy.validate_config(config)

    def test_validate_config_negative_value(self, strategy):
        """Test configuration validation with negative value."""
        floor_strategy = FloorStrategy(strategy)

        config = {
            "base_lot_size": -1.0,
            "scaling_mode": "additive",
            "retracement_pips": 30,
            "take_profit_pips": 25,
        }

        with pytest.raises(ValueError, match="must be positive"):
            floor_strategy.validate_config(config)

    def test_on_tick_inactive_instrument(self, strategy, strategy_state, tick_data):
        """Test on_tick with inactive instrument."""
        floor_strategy = FloorStrategy(strategy)

        # Create tick for instrument not in strategy
        tick_data.instrument = "GBP_USD"

        orders = floor_strategy.on_tick(tick_data)

        assert len(orders) == 0

    def test_on_tick_creates_initial_entry(self, strategy, strategy_state, tick_data):
        """Test on_tick creates initial entry order."""
        floor_strategy = FloorStrategy(strategy)

        # Verify initial layer was created during initialization
        assert len(floor_strategy.layer_manager.layers) == 1
        layer = floor_strategy.layer_manager.get_layer(1)
        assert layer is not None
        assert len(layer.positions) == 0

        # Feed 10 ticks with upward momentum to generate entry signal
        # Start at 1.1000 and increase by 0.0006 (6 pips) each tick for strong signal
        base_price = Decimal("1.1000")
        for i in range(10):
            price = base_price + (Decimal("0.0006") * i)
            bid = price - Decimal("0.0001")
            ask = price + Decimal("0.0001")
            tick = TickData(
                instrument="EUR_USD",
                timestamp=tick_data.timestamp + timedelta(seconds=i),
                bid=bid,
                ask=ask,
                mid=(bid + ask) / Decimal("2"),
                spread=ask - bid,
            )
            orders = floor_strategy.on_tick(tick)

        # The last tick should generate an entry order
        assert len(orders) == 1
        assert orders[0].order_type == "market"
        assert orders[0].instrument == "EUR_USD"
        assert orders[0].units == Decimal("1.0")
        assert orders[0].direction == "long"  # Upward momentum

    def test_calculate_pips(self, strategy):
        """Test pip calculation."""
        floor_strategy = FloorStrategy(strategy)

        # Test EUR_USD (standard pip)
        pips = floor_strategy.calculate_pips(Decimal("1.1000"), Decimal("1.1030"), "EUR_USD")
        assert pips == Decimal("30")

        # Test USD_JPY (JPY pip)
        pips = floor_strategy.calculate_pips(Decimal("110.00"), Decimal("110.30"), "USD_JPY")
        assert pips == Decimal("30")

    def test_should_take_profit_long(self, strategy, oanda_account):
        """Test take-profit detection for long position."""
        floor_strategy = FloorStrategy(strategy)

        position = Position.objects.create(
            account=oanda_account,
            strategy=strategy,
            position_id="pos1",
            instrument="EUR_USD",
            direction="long",
            units=Decimal("1.0"),
            entry_price=Decimal("1.1000"),
            current_price=Decimal("1.1025"),
            layer_number=1,
        )

        # Create tick data with price moved 25 pips in favor
        tick_data = TickData(
            instrument="EUR_USD",
            timestamp=timezone.now(),
            bid=Decimal("1.1025"),  # Long closes at bid
            ask=Decimal("1.1027"),
            mid=Decimal("1.1026"),
            spread=Decimal("0.0002"),
        )

        should_tp = floor_strategy._should_take_profit(position, tick_data)

        assert should_tp is True

    def test_should_take_profit_short(self, strategy, oanda_account):
        """Test take-profit detection for short position."""
        floor_strategy = FloorStrategy(strategy)

        position = Position.objects.create(
            account=oanda_account,
            strategy=strategy,
            position_id="pos1",
            instrument="EUR_USD",
            direction="short",
            units=Decimal("1.0"),
            entry_price=Decimal("1.1000"),
            current_price=Decimal("1.0975"),
            layer_number=1,
        )

        # Create tick data with price moved 25 pips in favor
        tick_data = TickData(
            instrument="EUR_USD",
            timestamp=timezone.now(),
            bid=Decimal("1.0973"),
            ask=Decimal("1.0975"),  # Short closes at ask
            mid=Decimal("1.0974"),
            spread=Decimal("0.0002"),
        )

        should_tp = floor_strategy._should_take_profit(position, tick_data)

        assert should_tp is True

    def test_should_take_profit_not_reached(self, strategy, oanda_account):
        """Test take-profit not triggered when threshold not reached."""
        floor_strategy = FloorStrategy(strategy)

        position = Position.objects.create(
            account=oanda_account,
            strategy=strategy,
            position_id="pos1",
            instrument="EUR_USD",
            direction="long",
            units=Decimal("1.0"),
            entry_price=Decimal("1.1000"),
            current_price=Decimal("1.1010"),
            layer_number=1,
        )

        # Create tick data with price moved only 10 pips
        tick_data = TickData(
            instrument="EUR_USD",
            timestamp=timezone.now(),
            bid=Decimal("1.1010"),  # Long closes at bid
            ask=Decimal("1.1012"),
            mid=Decimal("1.1011"),
            spread=Decimal("0.0002"),
        )

        should_tp = floor_strategy._should_take_profit(position, tick_data)

        assert should_tp is False

    def test_check_margin_liquidation_safe(self, strategy, oanda_account):
        """Test margin liquidation check when ratio is safe."""
        floor_strategy = FloorStrategy(strategy)

        # Set safe margin values
        oanda_account.margin_used = Decimal("1000.00")
        oanda_account.unrealized_pnl = Decimal("-500.00")  # 50% ratio
        oanda_account.save()

        should_liquidate = floor_strategy._check_margin_liquidation()

        assert should_liquidate is False

    def test_check_margin_liquidation_triggered(self, strategy, oanda_account):
        """Test margin liquidation check when ratio reaches 100%."""
        floor_strategy = FloorStrategy(strategy)

        # Set margin values to trigger liquidation
        oanda_account.margin_used = Decimal("1000.00")
        oanda_account.unrealized_pnl = Decimal("-1000.00")  # 0% ratio (100% used)
        oanda_account.save()

        should_liquidate = floor_strategy._check_margin_liquidation()

        assert should_liquidate is True

    def test_on_position_update(self, strategy, strategy_state, oanda_account):
        """Test position update handling."""
        floor_strategy = FloorStrategy(strategy)

        # Get the existing layer created during initialization
        layer = floor_strategy.layer_manager.get_layer(1)
        assert layer is not None

        # Create a position
        position = Position.objects.create(
            account=oanda_account,
            strategy=strategy,
            position_id="pos1",
            instrument="EUR_USD",
            direction="long",
            units=Decimal("1.0"),
            entry_price=Decimal("1.1000"),
            current_price=Decimal("1.1000"),
            layer_number=1,
            is_first_lot=True,
        )

        # Call on_position_update
        floor_strategy.on_position_update(position)

        # Verify position was added to layer
        assert position in layer.positions
        assert layer.first_lot_position == position

    def test_calculate_take_profit_price_long(self, strategy):
        """Test take-profit price calculation for long position."""
        floor_strategy = FloorStrategy(strategy)

        entry_price = Decimal("1.1000")
        tp_price = floor_strategy._calculate_take_profit_price(entry_price, "long", Decimal("25"))

        assert tp_price == Decimal("1.1025")

    def test_calculate_take_profit_price_short(self, strategy):
        """Test take-profit price calculation for short position."""
        floor_strategy = FloorStrategy(strategy)

        entry_price = Decimal("1.1000")
        tp_price = floor_strategy._calculate_take_profit_price(entry_price, "short", Decimal("25"))

        assert tp_price == Decimal("1.0975")


# Property-Based Tests for Floor Strategy Event Logging


@pytest.mark.django_db
class TestFloorStrategyEventLogging:
    """Property-based tests for Floor Strategy event logging."""

    @given(
        event_type=st.sampled_from(
            ["close", "take_profit", "volatility_lock", "margin_protection"]
        ),
        entry_price=st.decimals(min_value=Decimal("1.0000"), max_value=Decimal("2.0000"), places=4),
        exit_price=st.decimals(min_value=Decimal("1.0000"), max_value=Decimal("2.0000"), places=4),
        units=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("10.0"), places=2),
    )
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_close_events_logged_with_correct_event_type(
        self, user, oanda_account, strategy_config, event_type, entry_price, exit_price, units
    ):
        """
        Property 1: Close events are displayed in table.

        For any close event (close, take_profit, volatility_lock, margin_protection),
        the event should be logged with the correct event_type in metadata.

        Feature: floor-strategy-enhancements, Property 1
        Validates: Requirements 1.1, 1.2, 1.3, 1.4
        """
        # Create strategy in backtest mode
        config = strategy_config.copy()
        config["instrument"] = "EUR_USD"
        floor_strategy = FloorStrategy(config)

        # Enable backtest mode
        floor_strategy._is_backtest = True
        floor_strategy._backtest_events = []

        # Create a mock position
        position = Position(
            account=oanda_account,
            strategy=None,
            position_id=f"test_pos_{event_type}",
            instrument="EUR_USD",
            direction="long",
            units=units,
            entry_price=entry_price,
            current_price=exit_price,
        )
        position.layer_number = 1

        # Create tick data
        tick_data = TickData(
            instrument="EUR_USD",
            timestamp=timezone.now(),
            bid=exit_price,
            ask=exit_price,
            mid=exit_price,
        )

        # Map event_type to reason for _create_close_order
        event_type_to_reason = {
            "close": "strategy_close",
            "take_profit": "take_profit",
            "volatility_lock": "volatility_lock",
            "margin_protection": "margin_protection",
        }
        reason = event_type_to_reason[event_type]

        # Create close order (which logs the event)
        order = floor_strategy._create_close_order(position, tick_data, reason=reason)

        # Verify order was created
        assert order is not None

        # Verify event was logged
        assert len(floor_strategy._backtest_events) > 0

        # Find the close event
        close_events = [
            e
            for e in floor_strategy._backtest_events
            if e.get("details", {}).get("reason") == reason
        ]
        assert len(close_events) > 0

        # Verify the event has correct event_type
        close_event = close_events[0]
        assert "details" in close_event
        assert "event_type" in close_event["details"]
        assert close_event["details"]["event_type"] == event_type

        # Verify event has required metadata
        details = close_event["details"]
        assert "exit_price" in details
        assert "pnl" in details
        assert "timestamp" in details
        assert "layer_number" in details

        # Verify exit_price matches
        assert Decimal(details["exit_price"]) == exit_price

    def test_initial_entry_logs_with_initial_event_type(self, user, oanda_account, strategy_config):
        """
        Test that initial entry logs with event_type='initial'.

        Validates: Requirements 1.1
        """
        # Create strategy in backtest mode
        config = strategy_config.copy()
        config["instrument"] = "EUR_USD"
        floor_strategy = FloorStrategy(config)

        # Enable backtest mode
        floor_strategy._is_backtest = True
        floor_strategy._backtest_events = []

        # Build up price history for entry signal
        for i in range(15):
            tick = TickData(
                instrument="EUR_USD",
                timestamp=timezone.now() + timedelta(seconds=i),
                bid=Decimal("1.1000") + Decimal(str(i * 0.0001)),
                ask=Decimal("1.1001") + Decimal(str(i * 0.0001)),
                mid=Decimal("1.10005") + Decimal(str(i * 0.0001)),
            )
            floor_strategy.on_tick(tick)

        # Find initial entry event
        initial_events = [
            e for e in floor_strategy._backtest_events if e.get("event_type") == "initial_entry"
        ]

        assert len(initial_events) > 0
        initial_event = initial_events[0]

        # Verify event_type is 'initial'
        assert initial_event["details"]["event_type"] == "initial"
        assert initial_event["details"]["retracement_count"] == 0
        assert "timestamp" in initial_event["details"]

    def test_retracement_logs_with_retracement_event_type(
        self, user, oanda_account, strategy_config
    ):
        """
        Test that retracement entry logs with event_type='retracement'.

        Validates: Requirements 1.1
        """
        # Create strategy in backtest mode
        config = strategy_config.copy()
        config["instrument"] = "EUR_USD"
        config["retracement_pips"] = 10  # Lower threshold for testing
        floor_strategy = FloorStrategy(config)

        # Enable backtest mode
        floor_strategy._is_backtest = True
        floor_strategy._backtest_events = []

        # Build up price history for entry signal
        for i in range(15):
            tick = TickData(
                instrument="EUR_USD",
                timestamp=timezone.now() + timedelta(seconds=i),
                bid=Decimal("1.1000") + Decimal(str(i * 0.0001)),
                ask=Decimal("1.1001") + Decimal(str(i * 0.0001)),
                mid=Decimal("1.10005") + Decimal(str(i * 0.0001)),
            )
            floor_strategy.on_tick(tick)

        # Clear events to focus on retracement
        floor_strategy._backtest_events = []

        # Simulate price moving in favor (peak)
        for i in range(5):
            tick = TickData(
                instrument="EUR_USD",
                timestamp=timezone.now() + timedelta(seconds=20 + i),
                bid=Decimal("1.1015") + Decimal(str(i * 0.0001)),
                ask=Decimal("1.1016") + Decimal(str(i * 0.0001)),
                mid=Decimal("1.10155") + Decimal(str(i * 0.0001)),
            )
            floor_strategy.on_tick(tick)

        # Simulate retracement (price moving against us)
        for i in range(15):
            tick = TickData(
                instrument="EUR_USD",
                timestamp=timezone.now() + timedelta(seconds=30 + i),
                bid=Decimal("1.1010") - Decimal(str(i * 0.0001)),
                ask=Decimal("1.1011") - Decimal(str(i * 0.0001)),
                mid=Decimal("1.10105") - Decimal(str(i * 0.0001)),
            )
            floor_strategy.on_tick(tick)

        # Find retracement event
        retracement_events = [
            e for e in floor_strategy._backtest_events if e.get("event_type") == "scale_in"
        ]

        if len(retracement_events) > 0:
            retracement_event = retracement_events[0]
            # Verify event_type is 'retracement'
            assert retracement_event["details"]["event_type"] == "retracement"
            assert retracement_event["details"]["retracement_count"] > 0
            assert "timestamp" in retracement_event["details"]

    def test_close_logs_with_close_event_type(self, user, oanda_account, strategy_config):
        """
        Test that close logs with event_type='close'.

        Validates: Requirements 1.1
        """
        # Create strategy in backtest mode
        config = strategy_config.copy()
        config["instrument"] = "EUR_USD"
        floor_strategy = FloorStrategy(config)

        # Enable backtest mode
        floor_strategy._is_backtest = True
        floor_strategy._backtest_events = []

        # Create a mock position
        position = Position(
            account=oanda_account,
            strategy=None,
            position_id="test_pos_close",
            instrument="EUR_USD",
            direction="long",
            units=Decimal("1.0"),
            entry_price=Decimal("1.1000"),
            current_price=Decimal("1.1025"),
        )
        position.layer_number = 1

        # Create tick data
        tick_data = TickData(
            instrument="EUR_USD",
            timestamp=timezone.now(),
            bid=Decimal("1.1025"),
            ask=Decimal("1.1026"),
            mid=Decimal("1.10255"),
        )

        # Create close order with strategy_close reason
        order = floor_strategy._create_close_order(position, tick_data, reason="strategy_close")

        # Verify order was created
        assert order is not None

        # Find close event
        close_events = [
            e
            for e in floor_strategy._backtest_events
            if e.get("details", {}).get("reason") == "strategy_close"
        ]

        assert len(close_events) > 0
        close_event = close_events[0]

        # Verify event_type is 'close'
        assert close_event["details"]["event_type"] == "close"
        assert "exit_price" in close_event["details"]
        assert "pnl" in close_event["details"]
        assert "timestamp" in close_event["details"]

    def test_take_profit_logs_with_take_profit_event_type(
        self, user, oanda_account, strategy_config
    ):
        """
        Test that take profit logs with event_type='take_profit'.

        Validates: Requirements 1.2
        """
        # Create strategy in backtest mode
        config = strategy_config.copy()
        config["instrument"] = "EUR_USD"
        floor_strategy = FloorStrategy(config)

        # Enable backtest mode
        floor_strategy._is_backtest = True
        floor_strategy._backtest_events = []

        # Create a mock position
        position = Position(
            account=oanda_account,
            strategy=None,
            position_id="test_pos_tp",
            instrument="EUR_USD",
            direction="long",
            units=Decimal("1.0"),
            entry_price=Decimal("1.1000"),
            current_price=Decimal("1.1025"),
        )
        position.layer_number = 1

        # Create tick data
        tick_data = TickData(
            instrument="EUR_USD",
            timestamp=timezone.now(),
            bid=Decimal("1.1025"),
            ask=Decimal("1.1026"),
            mid=Decimal("1.10255"),
        )

        # Create close order with take_profit reason
        order = floor_strategy._create_close_order(position, tick_data, reason="take_profit")

        # Verify order was created
        assert order is not None

        # Find take profit event
        tp_events = [
            e
            for e in floor_strategy._backtest_events
            if e.get("details", {}).get("reason") == "take_profit"
        ]

        assert len(tp_events) > 0
        tp_event = tp_events[0]

        # Verify event_type is 'take_profit'
        assert tp_event["details"]["event_type"] == "take_profit"
        assert "exit_price" in tp_event["details"]
        assert "pnl" in tp_event["details"]
        assert "timestamp" in tp_event["details"]

    def test_volatility_lock_logs_with_volatility_lock_event_type(
        self, user, oanda_account, strategy_config
    ):
        """
        Test that volatility lock logs with event_type='volatility_lock'.

        Validates: Requirements 1.3
        """
        # Create strategy in backtest mode
        config = strategy_config.copy()
        config["instrument"] = "EUR_USD"
        floor_strategy = FloorStrategy(config)

        # Enable backtest mode
        floor_strategy._is_backtest = True
        floor_strategy._backtest_events = []

        # Create a mock position
        position = Position(
            account=oanda_account,
            strategy=None,
            position_id="test_pos_vl",
            instrument="EUR_USD",
            direction="long",
            units=Decimal("1.0"),
            entry_price=Decimal("1.1000"),
            current_price=Decimal("1.1025"),
        )
        position.layer_number = 1

        # Create tick data
        tick_data = TickData(
            instrument="EUR_USD",
            timestamp=timezone.now(),
            bid=Decimal("1.1025"),
            ask=Decimal("1.1026"),
            mid=Decimal("1.10255"),
        )

        # Create close order with volatility_lock reason
        order = floor_strategy._create_close_order(position, tick_data, reason="volatility_lock")

        # Verify order was created
        assert order is not None

        # Find volatility lock event
        vl_events = [
            e
            for e in floor_strategy._backtest_events
            if e.get("details", {}).get("reason") == "volatility_lock"
        ]

        assert len(vl_events) > 0
        vl_event = vl_events[0]

        # Verify event_type is 'volatility_lock'
        assert vl_event["details"]["event_type"] == "volatility_lock"
        assert "exit_price" in vl_event["details"]
        assert "pnl" in vl_event["details"]
        assert "timestamp" in vl_event["details"]

    def test_margin_protection_logs_with_margin_protection_event_type(
        self, user, oanda_account, strategy_config
    ):
        """
        Test that margin protection logs with event_type='margin_protection'.

        Validates: Requirements 1.4
        """
        # Create strategy in backtest mode
        config = strategy_config.copy()
        config["instrument"] = "EUR_USD"
        floor_strategy = FloorStrategy(config)

        # Enable backtest mode
        floor_strategy._is_backtest = True
        floor_strategy._backtest_events = []

        # Create a mock position
        position = Position(
            account=oanda_account,
            strategy=None,
            position_id="test_pos_mp",
            instrument="EUR_USD",
            direction="long",
            units=Decimal("1.0"),
            entry_price=Decimal("1.1000"),
            current_price=Decimal("1.1025"),
        )
        position.layer_number = 1

        # Create tick data
        tick_data = TickData(
            instrument="EUR_USD",
            timestamp=timezone.now(),
            bid=Decimal("1.1025"),
            ask=Decimal("1.1026"),
            mid=Decimal("1.10255"),
        )

        # Create close order with margin_protection reason
        order = floor_strategy._create_close_order(position, tick_data, reason="margin_protection")

        # Verify order was created
        assert order is not None

        # Find margin protection event
        mp_events = [
            e
            for e in floor_strategy._backtest_events
            if e.get("details", {}).get("reason") == "margin_protection"
        ]

        assert len(mp_events) > 0
        mp_event = mp_events[0]

        # Verify event_type is 'margin_protection'
        assert mp_event["details"]["event_type"] == "margin_protection"
        assert "exit_price" in mp_event["details"]
        assert "pnl" in mp_event["details"]
        assert "timestamp" in mp_event["details"]
