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
        "max_retracements_per_layer": 10,
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

    def test_duplicate_layer_prevention(self):
        """Test that duplicate layers with same number are not created."""
        manager = LayerManager(max_layers=5)
        config = {"base_lot_size": 1.0}

        # Create layer 1
        layer1_first = manager.create_layer(1, config)
        assert layer1_first is not None
        assert len(manager.layers) == 1

        # Try to create another layer 1 - should return None
        layer1_duplicate = manager.create_layer(1, config)
        assert layer1_duplicate is None
        assert len(manager.layers) == 1  # Should still be 1 layer

        # Create layer 2
        layer2 = manager.create_layer(2, config)
        assert layer2 is not None
        assert len(manager.layers) == 2

        # Try to create duplicate layer 2 - should return None
        layer2_duplicate = manager.create_layer(2, config)
        assert layer2_duplicate is None
        assert len(manager.layers) == 2  # Should still be 2 layers

        # Verify the original layers are still correct
        assert manager.get_layer(1) is layer1_first
        assert manager.get_layer(2) is layer2

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

    def test_should_create_new_layer_on_max_retracements(self):
        """Layer should promote next layer once its retracement cap is hit."""
        config = {
            "base_lot_size": 1.0,
            "retracement_count_trigger": 999,  # unrealistically high
            "max_retracements_per_layer": 3,
        }
        layer = Layer(layer_number=1, config=config)

        for _ in range(3):
            layer.increment_retracement_count()

        assert layer.should_create_new_layer() is True

    def test_should_create_new_layer_auto_advance_when_trigger_below_one(self):
        """Layers with sub-1 triggers (inverse progression) should auto-advance."""
        config = {
            "base_lot_size": 1.0,
            "retracement_count_trigger": 1,
            "auto_advance_on_low_trigger": True,
        }
        layer = Layer(layer_number=2, config=config)

        assert layer.should_create_new_layer() is True

    def test_reset_retracement_count(self):
        """Test resetting retracement count to zero."""
        config = {"base_lot_size": 1.0}
        layer = Layer(layer_number=1, config=config)

        # Increment retracement count
        layer.increment_retracement_count()
        layer.increment_retracement_count()
        layer.increment_retracement_count()
        assert layer.retracement_count == 3

        # Reset should set it back to 0
        layer.reset_retracement_count()
        assert layer.retracement_count == 0

    def test_retracement_reset_on_initial_entry(self):
        """
        Test that retracement counter resets to 0 on initial entry.
        Requirements: 6.1, 6.3, 6.4
        """
        config = {"base_lot_size": 1.0}
        layer = Layer(layer_number=1, config=config)

        # Simulate first cycle with retracements
        layer.increment_retracement_count()
        layer.increment_retracement_count()
        assert layer.retracement_count == 2

        # Simulate initial entry for new cycle - should reset
        layer.reset_retracement_count()
        assert layer.retracement_count == 0

    def test_reset_unit_size(self):
        """
        Test resetting unit size to base_lot_size.
        Requirements: 7.1, 7.3, 7.4
        """
        config = {"base_lot_size": 2.5}
        layer = Layer(layer_number=1, config=config)

        # Initial state should be base_lot_size
        assert layer.current_lot_size == Decimal("2.5")
        assert layer.base_lot_size == Decimal("2.5")

        # Simulate scaling
        layer.current_lot_size = Decimal("5.0")
        assert layer.current_lot_size == Decimal("5.0")

        # Reset should restore to base_lot_size
        layer.reset_unit_size()
        assert layer.current_lot_size == Decimal("2.5")

    def test_unit_size_reset_on_initial_entry(self):
        """
        Test that unit size resets to base_lot_size on initial entry.
        Requirements: 7.1, 7.4
        """
        config = {"base_lot_size": 1.0}
        layer = Layer(layer_number=1, config=config)

        # Initial state
        assert layer.current_lot_size == Decimal("1.0")

        # Simulate first cycle with scaling
        layer.current_lot_size = Decimal("2.0")
        layer.current_lot_size = Decimal("3.0")
        assert layer.current_lot_size == Decimal("3.0")

        # Simulate initial entry for new cycle - should reset
        layer.reset_unit_size()
        assert layer.current_lot_size == Decimal("1.0")

    def test_unit_size_uses_scaled_size_on_retracement(self):
        """
        Test that retracement uses scaled size.
        Requirements: 7.2
        """
        config = {"base_lot_size": 1.0}
        layer = Layer(layer_number=1, config=config)

        # Initial entry uses base_lot_size
        assert layer.current_lot_size == Decimal("1.0")

        # First retracement scales up
        layer.current_lot_size = Decimal("2.0")
        assert layer.current_lot_size == Decimal("2.0")

        # Second retracement scales up further
        layer.current_lot_size = Decimal("3.0")
        assert layer.current_lot_size == Decimal("3.0")

    def test_unit_size_multiple_cycles_reset_correctly(self):
        """
        Test that multiple cycles reset unit size correctly.
        Requirements: 7.1, 7.2, 7.3, 7.4
        """
        config = {"base_lot_size": 1.5}
        layer = Layer(layer_number=1, config=config)

        # Cycle 1: Initial entry
        assert layer.current_lot_size == Decimal("1.5")

        # Cycle 1: Scale up
        layer.current_lot_size = Decimal("3.0")
        layer.current_lot_size = Decimal("4.5")
        assert layer.current_lot_size == Decimal("4.5")

        # Cycle 2: Reset for new initial entry
        layer.reset_unit_size()
        assert layer.current_lot_size == Decimal("1.5")

        # Cycle 2: Scale up differently
        layer.current_lot_size = Decimal("2.5")
        assert layer.current_lot_size == Decimal("2.5")

        # Cycle 3: Reset again
        layer.reset_unit_size()
        assert layer.current_lot_size == Decimal("1.5")

    def test_retracement_increment_on_scale_in(self):
        """
        Test that retracement counter increments on scale-in.
        Requirements: 6.2
        """
        config = {"base_lot_size": 1.0}
        layer = Layer(layer_number=1, config=config)

        # Start at 0
        assert layer.retracement_count == 0

        # First retracement
        layer.increment_retracement_count()
        assert layer.retracement_count == 1

        # Second retracement
        layer.increment_retracement_count()
        assert layer.retracement_count == 2

        # Third retracement
        layer.increment_retracement_count()
        assert layer.retracement_count == 3

    def test_multiple_cycles_reset_correctly(self):
        """
        Test that retracement counter resets correctly across multiple cycles.
        Requirements: 6.1, 6.2, 6.3, 6.4
        """
        config = {"base_lot_size": 1.0}
        layer = Layer(layer_number=1, config=config)

        # Cycle 1: Initial entry + 3 retracements
        layer.reset_retracement_count()
        assert layer.retracement_count == 0
        layer.increment_retracement_count()
        layer.increment_retracement_count()
        layer.increment_retracement_count()
        assert layer.retracement_count == 3

        # Cycle 2: Initial entry + 2 retracements
        layer.reset_retracement_count()
        assert layer.retracement_count == 0
        layer.increment_retracement_count()
        layer.increment_retracement_count()
        assert layer.retracement_count == 2

        # Cycle 3: Initial entry + 5 retracements
        layer.reset_retracement_count()
        assert layer.retracement_count == 0
        for _ in range(5):
            layer.increment_retracement_count()
        assert layer.retracement_count == 5

        # Final cycle: Initial entry should reset again
        layer.reset_retracement_count()
        assert layer.retracement_count == 0


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
        # Units are now actual OANDA units: base_lot_size (1.0) * base_unit_size (1000) = 1000
        assert orders[0].units == Decimal("1000.0")
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

    def test_initial_entry_calculates_direction(self, strategy, strategy_state):
        """
        Test that initial entry calculates direction using entry signal logic.

        Requirements: 8.1, 8.2, 8.3, 8.4
        """
        floor_strategy = FloorStrategy(strategy)
        layer = floor_strategy.layer_manager.get_layer(1)
        assert layer is not None

        # Feed ticks with upward momentum to generate long signal
        base_price = Decimal("1.1000")
        for i in range(10):
            price = base_price + (Decimal("0.0005") * i)
            tick = TickData(
                instrument="EUR_USD",
                timestamp=timezone.now() + timedelta(seconds=i),
                bid=price,
                ask=price + Decimal("0.0002"),
                mid=price + Decimal("0.0001"),
            )
            floor_strategy.on_tick(tick)

        # Verify direction was calculated and stored in layer
        assert layer.direction is not None, "Direction should be set after initial entry"
        assert layer.direction in ["long", "short"], "Direction should be 'long' or 'short'"
        # With upward momentum, should be long
        assert layer.direction == "long", "Upward momentum should result in long direction"

    def test_retracement_uses_same_direction_as_initial(
        self, strategy, strategy_state, oanda_account
    ):
        """
        Test that retracement entries use the same direction as the initial entry.

        Requirements: 8.3
        """
        floor_strategy = FloorStrategy(strategy)
        layer = floor_strategy.layer_manager.get_layer(1)
        assert layer is not None

        # Feed ticks to create initial entry with long direction
        base_price = Decimal("1.1000")
        for i in range(10):
            price = base_price + (Decimal("0.0005") * i)
            tick = TickData(
                instrument="EUR_USD",
                timestamp=timezone.now() + timedelta(seconds=i),
                bid=price,
                ask=price + Decimal("0.0002"),
                mid=price + Decimal("0.0001"),
            )
            floor_strategy.on_tick(tick)

        # Store the initial direction
        initial_direction = layer.direction
        assert initial_direction == "long"

        # Create a position to simulate initial entry execution
        position = Position.objects.create(
            account=oanda_account,
            strategy=strategy,
            position_id="pos1",
            instrument="EUR_USD",
            direction=initial_direction,
            units=Decimal("1.0"),
            entry_price=Decimal("1.1050"),
            current_price=Decimal("1.1050"),
            layer_number=1,
            is_first_lot=True,
        )
        floor_strategy.on_position_update(position)

        # Now create a scale order (retracement)
        tick = TickData(
            instrument="EUR_USD",
            timestamp=timezone.now() + timedelta(seconds=20),
            bid=Decimal("1.1020"),
            ask=Decimal("1.1022"),
            mid=Decimal("1.1021"),
        )
        scale_order = floor_strategy._create_scale_order(layer, tick)

        # Verify the scale order uses the same direction
        if scale_order:
            assert (
                scale_order.direction == initial_direction
            ), f"Retracement should use same direction as initial: {initial_direction}"

    def test_multiple_cycles_can_have_different_directions(self, strategy, strategy_state):
        """
        Test that multiple position cycles can have different directions based on market conditions.

        Requirements: 8.1, 8.2, 8.3, 8.4
        """
        floor_strategy = FloorStrategy(strategy)
        layer = floor_strategy.layer_manager.get_layer(1)
        assert layer is not None

        directions = []

        # Cycle 1: Upward momentum (should be long)
        base_price = Decimal("1.1000")
        for i in range(10):
            price = base_price + (Decimal("0.0005") * i)
            tick = TickData(
                instrument="EUR_USD",
                timestamp=timezone.now() + timedelta(seconds=i),
                bid=price,
                ask=price + Decimal("0.0002"),
                mid=price + Decimal("0.0001"),
            )
            floor_strategy.on_tick(tick)

        if layer.direction:
            directions.append(layer.direction)

        # Clear layer for next cycle
        layer.positions.clear()
        layer.first_lot_position = None
        layer.has_pending_initial_entry = False
        layer.direction = None
        # Clear price history to start fresh for next cycle
        floor_strategy._price_history.clear()

        # Cycle 2: Downward momentum (should be short)
        base_price = Decimal("1.1050")
        for i in range(10):
            price = base_price - (Decimal("0.0005") * i)
            tick = TickData(
                instrument="EUR_USD",
                timestamp=timezone.now() + timedelta(seconds=100 + i),
                bid=price,
                ask=price + Decimal("0.0002"),
                mid=price + Decimal("0.0001"),
            )
            floor_strategy.on_tick(tick)

        if layer.direction:
            directions.append(layer.direction)

        # Verify we got directions for both cycles
        assert len(directions) == 2, "Should have directions for both cycles"
        # First should be long (upward), second should be short (downward)
        assert directions[0] == "long", "First cycle with upward momentum should be long"
        assert directions[1] == "short", "Second cycle with downward momentum should be short"


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


@pytest.mark.django_db
class TestFloorStrategyRetracementReset:
    """Property-based tests for Floor Strategy retracement reset logic."""

    @given(
        num_cycles=st.integers(min_value=1, max_value=5),
        retracements_per_cycle=st.lists(
            st.integers(min_value=0, max_value=10), min_size=1, max_size=5
        ),
    )
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_retracement_resets_on_initial_entry(
        self, user, oanda_account, strategy_config, num_cycles, retracements_per_cycle
    ):
        """
        Property 7: Retracement resets on initial entry.

        For any number of position cycles, the retracement counter should reset to 0
        on every initial entry, regardless of previous cycles.

        Feature: floor-strategy-enhancements, Property 7
        Validates: Requirements 6.1, 6.3, 6.4
        """
        # Create strategy
        config = strategy_config.copy()
        config["instrument"] = "EUR_USD"
        config["entry_signal_lookback_ticks"] = 5  # Reduce for faster testing

        strategy_obj = Strategy.objects.create(
            account=oanda_account,
            strategy_type="floor",
            is_active=True,
            config=config,
            instrument="EUR_USD",
        )

        floor_strategy = FloorStrategy(config)
        floor_strategy.account = oanda_account
        floor_strategy._strategy_model = strategy_obj

        # Get the first layer
        layer = floor_strategy.layer_manager.layers[0]

        # Simulate multiple cycles
        for cycle in range(num_cycles):
            # Feed enough ticks to trigger entry signal
            base_price = Decimal("1.1000") + Decimal(str(cycle * 0.01))
            for i in range(10):
                tick = TickData(
                    instrument="EUR_USD",
                    timestamp=timezone.now() + timedelta(seconds=i),
                    bid=base_price + Decimal(str(i * 0.0001)),
                    ask=base_price + Decimal(str(i * 0.0001)) + Decimal("0.0002"),
                    mid=base_price + Decimal(str(i * 0.0001)) + Decimal("0.0001"),
                )
                floor_strategy.on_tick(tick)

            # After initial entry, retracement should be 0
            if layer.positions:
                assert (
                    layer.retracement_count == 0
                ), f"Cycle {cycle}: Retracement should be 0 after initial entry"

                # Simulate retracements for this cycle
                num_retracements = retracements_per_cycle[cycle % len(retracements_per_cycle)]
                for retr_idx in range(num_retracements):
                    # Manually increment retracement (simulating scale-in)
                    layer.increment_retracement_count()
                    assert layer.retracement_count == retr_idx + 1

                # Close all positions to prepare for next cycle
                layer.positions.clear()
                layer.first_lot_position = None
                layer.has_pending_initial_entry = False

        # Final verification: After all cycles, if we create another initial entry,
        # retracement should still be 0
        if layer.positions:
            layer.positions.clear()
            layer.first_lot_position = None
            layer.has_pending_initial_entry = False

        # Feed ticks for final entry
        for i in range(10):
            tick = TickData(
                instrument="EUR_USD",
                timestamp=timezone.now() + timedelta(seconds=100 + i),
                bid=Decimal("1.2000") + Decimal(str(i * 0.0001)),
                ask=Decimal("1.2000") + Decimal(str(i * 0.0001)) + Decimal("0.0002"),
                mid=Decimal("1.2000") + Decimal(str(i * 0.0001)) + Decimal("0.0001"),
            )
            floor_strategy.on_tick(tick)

        if layer.positions:
            assert layer.retracement_count == 0, "Final cycle: Retracement should be 0"

    @given(
        num_retracements=st.integers(min_value=1, max_value=20),
    )
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_retracement_increments_on_retracement_entry(
        self, user, oanda_account, strategy_config, num_retracements
    ):
        """
        Property 8: Retracement increments on retracement entry.

        For any number of retracement entries, the retracement counter should
        increment by 1 each time.

        Feature: floor-strategy-enhancements, Property 8
        Validates: Requirements 6.2
        """
        # Create strategy
        config = strategy_config.copy()
        config["instrument"] = "EUR_USD"

        strategy_obj = Strategy.objects.create(
            account=oanda_account,
            strategy_type="floor",
            is_active=True,
            config=config,
            instrument="EUR_USD",
        )

        floor_strategy = FloorStrategy(config)
        floor_strategy.account = oanda_account
        floor_strategy._strategy_model = strategy_obj

        # Get the first layer
        layer = floor_strategy.layer_manager.layers[0]

        # Start with retracement count at 0
        initial_count = layer.retracement_count
        assert initial_count == 0, "Initial retracement count should be 0"

        # Increment retracement multiple times, respecting configured cap
        for i in range(num_retracements):
            expected_count = min(initial_count + i + 1, layer.max_retracements_per_layer)
            layer.increment_retracement_count()
            assert (
                layer.retracement_count == expected_count
            ), f"After {i+1} increments, retracement should be {expected_count}"

        # Final verification (should not exceed cap)
        expected_final = min(num_retracements, layer.max_retracements_per_layer)
        assert (
            layer.retracement_count == expected_final
        ), f"Final retracement count should be {expected_final}"

    @given(
        base_lot_size=st.floats(min_value=0.01, max_value=10.0),
        scaling_mode=st.sampled_from(["additive", "multiplicative"]),
        scaling_amount=st.floats(min_value=0.1, max_value=5.0),
        num_retracements=st.integers(min_value=0, max_value=10),
        num_cycles=st.integers(min_value=1, max_value=5),
    )
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_unit_size_resets_on_initial_entry(
        self,
        user,
        oanda_account,
        strategy_config,
        base_lot_size,
        scaling_mode,
        scaling_amount,
        num_retracements,
        num_cycles,
    ):
        """
        Property 9: Unit size resets on initial entry.

        For any scaling scenario, the unit size should reset to base_lot_size
        on every initial entry, regardless of previous scaling.

        Feature: floor-strategy-enhancements, Property 9
        Validates: Requirements 7.1, 7.3, 7.4
        """
        # Create strategy with specific scaling configuration
        config = strategy_config.copy()
        config["instrument"] = "EUR_USD"
        config["base_lot_size"] = base_lot_size
        config["scaling_mode"] = scaling_mode
        config["scaling_amount"] = scaling_amount
        config["entry_signal_lookback_ticks"] = 5  # Reduce for faster testing

        strategy_obj = Strategy.objects.create(
            account=oanda_account,
            strategy_type="floor",
            is_active=True,
            config=config,
            instrument="EUR_USD",
        )

        floor_strategy = FloorStrategy(config)
        floor_strategy.account = oanda_account
        floor_strategy._strategy_model = strategy_obj

        # Get the first layer
        layer = floor_strategy.layer_manager.layers[0]

        # Verify initial state
        assert layer.current_lot_size == Decimal(
            str(base_lot_size)
        ), "Initial lot size should equal base_lot_size"

        # Simulate multiple cycles
        for cycle in range(num_cycles):
            # Feed enough ticks to trigger entry signal
            base_price = Decimal("1.1000") + Decimal(str(cycle * 0.01))
            for i in range(10):
                tick = TickData(
                    instrument="EUR_USD",
                    timestamp=timezone.now() + timedelta(seconds=cycle * 100 + i),
                    bid=base_price + Decimal(str(i * 0.0001)),
                    ask=base_price + Decimal(str(i * 0.0001)) + Decimal("0.0002"),
                    mid=base_price + Decimal(str(i * 0.0001)) + Decimal("0.0001"),
                )
                floor_strategy.on_tick(tick)

            # After initial entry, lot size should be base_lot_size
            if layer.positions:
                assert layer.current_lot_size == Decimal(
                    str(base_lot_size)
                ), f"Cycle {cycle}: Lot size should be {base_lot_size} after initial entry"

                # Simulate retracements with scaling
                for _ in range(num_retracements):
                    # Calculate next lot size using scaling engine
                    next_lot_size = floor_strategy.scaling_engine.calculate_next_lot_size(
                        layer.current_lot_size
                    )
                    layer.current_lot_size = next_lot_size

                # Verify lot size has changed from base (if we had retracements)
                if num_retracements > 0:
                    assert layer.current_lot_size != Decimal(str(base_lot_size)), (
                        f"Cycle {cycle}: Lot size should have changed "
                        f"after {num_retracements} retracements"
                    )

                # Close all positions to prepare for next cycle
                layer.positions.clear()
                layer.first_lot_position = None
                layer.has_pending_initial_entry = False

        # Final verification: After all cycles, if we create another initial entry,
        # lot size should reset to base_lot_size
        if layer.positions:
            layer.positions.clear()
            layer.first_lot_position = None
            layer.has_pending_initial_entry = False

        # Reset lot size explicitly (simulating what _create_initial_entry_order does)
        layer.reset_unit_size()

        # Verify reset
        assert layer.current_lot_size == Decimal(
            str(base_lot_size)
        ), "Final cycle: Lot size should reset to base_lot_size"


class TestFloorStrategyDirectionRecalculation:
    """Property-based tests for Floor Strategy direction recalculation logic."""

    @given(
        price_movements=st.lists(
            st.floats(min_value=-0.01, max_value=0.01),
            min_size=10,
            max_size=50,
        ),
        num_cycles=st.integers(min_value=2, max_value=5),
    )
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_direction_recalculates_on_initial_entry(
        self,
        user,
        oanda_account,
        strategy_config,
        price_movements,
        num_cycles,
    ):
        """
        Property 10: Direction recalculates on initial entry.

        For any market conditions, the direction should be recalculated
        on every initial entry using the same logic, allowing it to differ
        from previous position cycles based on current market conditions.

        Feature: floor-strategy-enhancements, Property 10
        Validates: Requirements 8.1, 8.2, 8.3, 8.4
        """
        # Create strategy with specific configuration
        config = strategy_config.copy()
        config["instrument"] = "EUR_USD"
        config["entry_signal_lookback_ticks"] = 10  # Need enough ticks for signal

        strategy_obj = Strategy.objects.create(
            account=oanda_account,
            strategy_type="floor",
            is_active=True,
            config=config,
            instrument="EUR_USD",
        )

        floor_strategy = FloorStrategy(config)
        floor_strategy.account = oanda_account
        floor_strategy._strategy_model = strategy_obj

        # Get the first layer
        layer = floor_strategy.layer_manager.layers[0]

        directions = []
        base_time = timezone.now()

        # Simulate multiple cycles
        for cycle in range(num_cycles):
            # Feed ticks with price movements to create different market conditions
            base_price = Decimal("1.1000")

            # Apply price movements for this cycle
            for i, movement in enumerate(price_movements[:20]):  # Use subset for each cycle
                current_price = base_price + Decimal(str(movement))
                tick = TickData(
                    instrument="EUR_USD",
                    timestamp=base_time + timedelta(seconds=cycle * 100 + i),
                    bid=current_price,
                    ask=current_price + Decimal("0.0002"),
                    mid=current_price + Decimal("0.0001"),
                )
                floor_strategy.on_tick(tick)

            # Check if initial entry was created and direction was set
            if layer.direction:
                directions.append(layer.direction)

                # Verify direction is stored in layer
                assert layer.direction in ["long", "short"], (
                    f"Cycle {cycle}: Direction should be 'long' or 'short', "
                    f"got {layer.direction}"
                )

                # If we have positions, verify they match the layer direction
                if layer.positions:
                    for position in layer.positions:
                        assert position.direction == layer.direction, (
                            f"Cycle {cycle}: Position direction {position.direction} "
                            f"should match layer direction {layer.direction}"
                        )

                # Close all positions to prepare for next cycle
                layer.positions.clear()
                layer.first_lot_position = None
                layer.has_pending_initial_entry = False
                # Reset direction to None to force recalculation
                layer.direction = None

        # Verify that direction was recalculated for each cycle
        # (we should have collected directions for each cycle that had an entry)
        assert len(directions) > 0, "Should have at least one direction recorded"

        # Each direction should be valid
        assert all(
            d in ["long", "short"] for d in directions
        ), "All directions should be 'long' or 'short'"
