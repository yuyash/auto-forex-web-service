"""
Unit tests for Trend Following Strategy implementation.

Tests cover:
- Trend detection with moving averages
- Entry signal generation
- Trailing stop-loss updates
- Position sizing calculations
- Strategy on_tick processing

Requirements: 5.1, 5.3
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone

import pytest

from accounts.models import OandaAccount
from trading.models import Position, Strategy, StrategyState
from trading.tick_data_models import TickData
from trading.trend_following_strategy import (
    MovingAverageCalculator,
    TrailingStopLoss,
    TrendDetector,
    TrendFollowingStrategy,
)

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
        "fast_period": 20,
        "slow_period": 50,
        "atr_multiplier": 2.0,
        "base_units": 1000,
        "risk_per_trade": 0.02,
    }


@pytest.fixture
def strategy(oanda_account, strategy_config):
    """Create a test strategy."""
    return Strategy.objects.create(
        account=oanda_account,
        strategy_type="trend_following",
        is_active=True,
        config=strategy_config,
        instruments=["EUR_USD"],
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


class TestMovingAverageCalculator:
    """Test MovingAverageCalculator functionality."""

    def test_initialization(self):
        """Test EMA calculator initialization."""
        calc = MovingAverageCalculator(period=20)

        assert calc.period == 20
        assert calc.ema is None
        assert calc.is_ready() is False

    def test_add_price_initializes_sma(self):
        """Test that EMA is initialized with SMA after enough data."""
        calc = MovingAverageCalculator(period=5)

        # Add 5 prices
        prices = [
            Decimal("1.1000"),
            Decimal("1.1010"),
            Decimal("1.1020"),
            Decimal("1.1030"),
            Decimal("1.1040"),
        ]
        for price in prices:
            calc.add_price(price)

        # EMA should be initialized with SMA
        assert calc.is_ready() is True
        expected_sma = sum(prices) / Decimal(5)
        assert calc.get_ema() == expected_sma

    def test_ema_calculation(self):
        """Test EMA calculation after initialization."""
        calc = MovingAverageCalculator(period=3)

        # Initialize with 3 prices
        calc.add_price(Decimal("1.1000"))
        calc.add_price(Decimal("1.1010"))
        calc.add_price(Decimal("1.1020"))

        # EMA should be SMA of first 3 prices
        initial_ema = calc.get_ema()
        assert initial_ema == Decimal("1.1010")

        # Add another price and check EMA updates
        calc.add_price(Decimal("1.1030"))
        new_ema = calc.get_ema()

        # New EMA should be different from initial
        assert new_ema != initial_ema
        assert new_ema is not None

    def test_get_ema_before_ready(self):
        """Test getting EMA before enough data."""
        calc = MovingAverageCalculator(period=5)

        calc.add_price(Decimal("1.1000"))
        calc.add_price(Decimal("1.1010"))

        assert calc.get_ema() is None
        assert calc.is_ready() is False


class TestTrendDetector:
    """Test TrendDetector functionality."""

    def test_initialization(self):
        """Test trend detector initialization."""
        detector = TrendDetector(fast_period=20, slow_period=50)

        assert detector.fast_ema.period == 20
        assert detector.slow_ema.period == 50
        assert detector.is_ready() is False

    def test_bullish_trend_detection(self):
        """Test detection of bullish trend (fast > slow)."""
        detector = TrendDetector(fast_period=3, slow_period=5)

        # Add prices that create uptrend
        # Fast EMA will rise faster than slow EMA
        for i in range(10):
            price = Decimal("1.1000") + Decimal(str(i * 0.001))
            detector.add_price(price)

        assert detector.is_ready() is True

        trend = detector.get_trend()
        assert trend == "bullish"

    def test_bearish_trend_detection(self):
        """Test detection of bearish trend (fast < slow)."""
        detector = TrendDetector(fast_period=3, slow_period=5)

        # Add prices that create downtrend
        for i in range(10):
            price = Decimal("1.1100") - Decimal(str(i * 0.001))
            detector.add_price(price)

        assert detector.is_ready() is True

        trend = detector.get_trend()
        assert trend == "bearish"

    def test_trend_confirmation_on_crossover(self):
        """Test that trend confirmation detects crossovers."""
        detector = TrendDetector(fast_period=3, slow_period=5)

        # Create initial uptrend
        for i in range(10):  # noqa: B007
            price = Decimal("1.1000") + Decimal(str(i * 0.001))
            detector.add_price(price)

        # First check - no confirmation yet (no previous trend)
        assert detector.is_trend_confirmed() is False

        # Add more prices to maintain trend
        detector.add_price(Decimal("1.1100"))
        assert detector.is_trend_confirmed() is False  # Same trend, no crossover

        # Create downtrend to trigger crossover
        for i in range(10):
            price = Decimal("1.1100") - Decimal(str(i * 0.002))
            detector.add_price(price)

        # Should detect trend change
        assert detector.is_trend_confirmed() is True

    def test_not_ready_before_enough_data(self):
        """Test that detector is not ready before enough data."""
        detector = TrendDetector(fast_period=20, slow_period=50)

        for _ in range(30):
            detector.add_price(Decimal("1.1000"))

        # Should not be ready yet (need 50 prices for slow EMA)
        assert detector.is_ready() is False


class TestTrailingStopLoss:
    """Test TrailingStopLoss functionality."""

    def test_initialization(self):
        """Test trailing stop-loss initialization."""
        trailing_stop = TrailingStopLoss(atr_multiplier=Decimal("2.0"))

        assert trailing_stop.atr_multiplier == Decimal("2.0")
        assert len(trailing_stop.stop_prices) == 0

    def test_initialize_stop_long(self):
        """Test initializing stop for long position."""
        trailing_stop = TrailingStopLoss(atr_multiplier=Decimal("2.0"))

        entry_price = Decimal("1.1000")
        atr = Decimal("0.0010")
        stop_price = trailing_stop.initialize_stop("pos1", entry_price, "long", atr)

        # Stop should be entry - (atr * multiplier)
        expected_stop = entry_price - (atr * Decimal("2.0"))
        assert stop_price == expected_stop
        assert trailing_stop.stop_prices["pos1"] == expected_stop

    def test_initialize_stop_short(self):
        """Test initializing stop for short position."""
        trailing_stop = TrailingStopLoss(atr_multiplier=Decimal("2.0"))

        entry_price = Decimal("1.1000")
        atr = Decimal("0.0010")
        stop_price = trailing_stop.initialize_stop("pos1", entry_price, "short", atr)

        # Stop should be entry + (atr * multiplier)
        expected_stop = entry_price + (atr * Decimal("2.0"))
        assert stop_price == expected_stop

    def test_update_stop_long_moves_up(self):
        """Test that stop moves up for profitable long position."""
        trailing_stop = TrailingStopLoss(atr_multiplier=Decimal("2.0"))

        entry_price = Decimal("1.1000")
        atr = Decimal("0.0010")
        trailing_stop.initialize_stop("pos1", entry_price, "long", atr)

        # Price moves up
        new_price = Decimal("1.1050")
        new_stop = trailing_stop.update_stop("pos1", new_price, "long", atr)

        # Stop should move up
        expected_stop = new_price - (atr * Decimal("2.0"))
        assert new_stop == expected_stop
        assert new_stop > entry_price - (atr * Decimal("2.0"))

    def test_update_stop_long_does_not_move_down(self):
        """Test that stop does not move down for long position."""
        trailing_stop = TrailingStopLoss(atr_multiplier=Decimal("2.0"))

        entry_price = Decimal("1.1000")
        atr = Decimal("0.0010")
        initial_stop = trailing_stop.initialize_stop("pos1", entry_price, "long", atr)

        # Price moves down
        new_price = Decimal("1.0950")
        new_stop = trailing_stop.update_stop("pos1", new_price, "long", atr)

        # Stop should not move down
        assert new_stop == initial_stop

    def test_update_stop_short_moves_down(self):
        """Test that stop moves down for profitable short position."""
        trailing_stop = TrailingStopLoss(atr_multiplier=Decimal("2.0"))

        entry_price = Decimal("1.1000")
        atr = Decimal("0.0010")
        trailing_stop.initialize_stop("pos1", entry_price, "short", atr)

        # Price moves down
        new_price = Decimal("1.0950")
        new_stop = trailing_stop.update_stop("pos1", new_price, "short", atr)

        # Stop should move down
        expected_stop = new_price + (atr * Decimal("2.0"))
        assert new_stop == expected_stop
        assert new_stop < entry_price + (atr * Decimal("2.0"))

    def test_should_stop_out_long(self):
        """Test stop-out detection for long position."""
        trailing_stop = TrailingStopLoss(atr_multiplier=Decimal("2.0"))

        entry_price = Decimal("1.1000")
        atr = Decimal("0.0010")
        stop_price = trailing_stop.initialize_stop("pos1", entry_price, "long", atr)

        # Price above stop - should not stop out
        assert (
            trailing_stop.should_stop_out("pos1", stop_price + Decimal("0.0001"), "long") is False
        )

        # Price at or below stop - should stop out
        assert trailing_stop.should_stop_out("pos1", stop_price, "long") is True
        assert trailing_stop.should_stop_out("pos1", stop_price - Decimal("0.0001"), "long") is True

    def test_should_stop_out_short(self):
        """Test stop-out detection for short position."""
        trailing_stop = TrailingStopLoss(atr_multiplier=Decimal("2.0"))

        entry_price = Decimal("1.1000")
        atr = Decimal("0.0010")
        stop_price = trailing_stop.initialize_stop("pos1", entry_price, "short", atr)

        # Price below stop - should not stop out
        assert (
            trailing_stop.should_stop_out("pos1", stop_price - Decimal("0.0001"), "short") is False
        )

        # Price at or above stop - should stop out
        assert trailing_stop.should_stop_out("pos1", stop_price, "short") is True
        assert (
            trailing_stop.should_stop_out("pos1", stop_price + Decimal("0.0001"), "short") is True
        )

    def test_remove_stop(self):
        """Test removing stop for closed position."""
        trailing_stop = TrailingStopLoss(atr_multiplier=Decimal("2.0"))

        trailing_stop.initialize_stop("pos1", Decimal("1.1000"), "long", Decimal("0.0010"))
        assert "pos1" in trailing_stop.stop_prices

        trailing_stop.remove_stop("pos1")
        assert "pos1" not in trailing_stop.stop_prices


class TestTrendFollowingStrategy:
    """Test TrendFollowingStrategy functionality."""

    def test_strategy_initialization(self, strategy, strategy_state):
        """Test strategy initialization."""
        trend_strategy = TrendFollowingStrategy(strategy)

        assert trend_strategy.fast_period == 20
        assert trend_strategy.slow_period == 50
        assert trend_strategy.atr_multiplier == Decimal("2.0")
        assert trend_strategy.base_units == Decimal("1000")
        assert "EUR_USD" in trend_strategy.trend_detectors

    def test_validate_config_valid(self, strategy):
        """Test configuration validation with valid config."""
        trend_strategy = TrendFollowingStrategy(strategy)

        config = {
            "fast_period": 20,
            "slow_period": 50,
            "atr_multiplier": 2.0,
            "base_units": 1000,
            "risk_per_trade": 0.02,
        }

        result = trend_strategy.validate_config(config)
        assert result is True

    def test_validate_config_invalid_periods(self, strategy):
        """Test configuration validation with invalid periods."""
        trend_strategy = TrendFollowingStrategy(strategy)

        config = {
            "fast_period": 50,  # Fast >= slow is invalid
            "slow_period": 50,
            "atr_multiplier": 2.0,
            "base_units": 1000,
            "risk_per_trade": 0.02,
        }

        with pytest.raises(ValueError, match="fast_period must be less than slow_period"):
            trend_strategy.validate_config(config)

    def test_validate_config_negative_atr_multiplier(self, strategy):
        """Test configuration validation with negative ATR multiplier."""
        trend_strategy = TrendFollowingStrategy(strategy)

        config = {
            "fast_period": 20,
            "slow_period": 50,
            "atr_multiplier": -1.0,
            "base_units": 1000,
            "risk_per_trade": 0.02,
        }

        with pytest.raises(ValueError, match="atr_multiplier must be positive"):
            trend_strategy.validate_config(config)

    def test_validate_config_invalid_risk(self, strategy):
        """Test configuration validation with invalid risk per trade."""
        trend_strategy = TrendFollowingStrategy(strategy)

        config = {
            "fast_period": 20,
            "slow_period": 50,
            "atr_multiplier": 2.0,
            "base_units": 1000,
            "risk_per_trade": 1.5,  # > 1.0 is invalid
        }

        with pytest.raises(ValueError, match="risk_per_trade must be between 0 and 1"):
            trend_strategy.validate_config(config)

    def test_calculate_position_size(self, strategy, strategy_state):
        """Test position sizing based on ATR."""
        trend_strategy = TrendFollowingStrategy(strategy)

        atr = Decimal("0.0010")
        position_size = trend_strategy._calculate_position_size(atr)

        # Expected: (10000 * 0.02) / (0.0010 * 2.0) = 200 / 0.002 = 100000
        assert position_size > Decimal("0")

    def test_on_tick_inactive_instrument(self, strategy, strategy_state, tick_data):
        """Test on_tick with inactive instrument."""
        trend_strategy = TrendFollowingStrategy(strategy)

        # Use instrument not in strategy
        tick_data.instrument = "GBP_USD"

        orders = trend_strategy.on_tick(tick_data)
        assert len(orders) == 0

    def test_on_tick_not_enough_data(self, strategy, strategy_state, tick_data):
        """Test on_tick when not enough data for EMAs."""
        trend_strategy = TrendFollowingStrategy(strategy)

        # Add just a few ticks (not enough for EMAs)
        for _ in range(5):
            orders = trend_strategy.on_tick(tick_data)
            assert len(orders) == 0

    def test_on_position_update_removes_stop(self, strategy, strategy_state, oanda_account):
        """Test that closing position removes trailing stop."""
        trend_strategy = TrendFollowingStrategy(strategy)

        # Create a position
        position = Position.objects.create(
            account=oanda_account,
            strategy=strategy,
            position_id="pos1",
            instrument="EUR_USD",
            direction="long",
            units=Decimal("1000"),
            entry_price=Decimal("1.1000"),
            current_price=Decimal("1.1000"),
            closed_at=None,
        )

        # Add stop for position
        trend_strategy.trailing_stops.stop_prices["pos1"] = Decimal("1.0980")

        # Close position
        position.closed_at = timezone.now()
        position.save()

        # Call on_position_update
        trend_strategy.on_position_update(position)

        # Stop should be removed
        assert "pos1" not in trend_strategy.trailing_stops.stop_prices

    def test_get_atr_from_state(self, strategy, strategy_state):
        """Test getting ATR value from strategy state."""
        trend_strategy = TrendFollowingStrategy(strategy)

        atr = trend_strategy._get_atr("EUR_USD")
        assert atr == Decimal("0.0010")

    def test_get_atr_not_available(self, strategy, strategy_state):
        """Test getting ATR when not available."""
        trend_strategy = TrendFollowingStrategy(strategy)

        atr = trend_strategy._get_atr("GBP_USD")
        assert atr is None

    def test_create_entry_order_bullish(self, strategy, strategy_state, tick_data):
        """Test creating entry order for bullish trend."""
        trend_strategy = TrendFollowingStrategy(strategy)

        atr = Decimal("0.0010")
        order = trend_strategy._create_entry_order(tick_data, "bullish", atr)

        assert order is not None
        assert order.direction == "long"
        assert order.instrument == "EUR_USD"
        assert order.stop_loss is not None
        assert order.stop_loss < tick_data.mid

    def test_create_entry_order_bearish(self, strategy, strategy_state, tick_data):
        """Test creating entry order for bearish trend."""
        trend_strategy = TrendFollowingStrategy(strategy)

        atr = Decimal("0.0010")
        order = trend_strategy._create_entry_order(tick_data, "bearish", atr)

        assert order is not None
        assert order.direction == "short"
        assert order.instrument == "EUR_USD"
        assert order.stop_loss is not None
        assert order.stop_loss > tick_data.mid

    def test_create_close_order(self, strategy, strategy_state, oanda_account, tick_data):
        """Test creating close order for position."""
        trend_strategy = TrendFollowingStrategy(strategy)

        position = Position.objects.create(
            account=oanda_account,
            strategy=strategy,
            position_id="pos1",
            instrument="EUR_USD",
            direction="long",
            units=Decimal("1000"),
            entry_price=Decimal("1.1000"),
            current_price=Decimal("1.1050"),
        )

        # Add stop for position
        trend_strategy.trailing_stops.stop_prices["pos1"] = Decimal("1.0980")

        order = trend_strategy._create_close_order(position, tick_data, "stop_loss")

        assert order is not None
        assert order.direction == "short"  # Opposite of position
        assert order.units == position.units
        assert "pos1" not in trend_strategy.trailing_stops.stop_prices  # Stop removed
