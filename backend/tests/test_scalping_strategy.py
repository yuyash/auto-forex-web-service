"""
Unit tests for Scalping Strategy.

This module tests the Scalping Strategy implementation including:
- Momentum detection
- Quick entry signal generation
- Tight stop-loss placement
- Maximum holding time enforcement
- Strategy on_tick processing

Requirements: 5.1, 5.3
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone

import pytest

from trading.models import Position, Strategy
from trading.scalping_strategy import MomentumDetector, ScalpingStrategy
from trading.tick_data_models import TickData

User = get_user_model()


@pytest.fixture
def user(db):  # pylint: disable=unused-argument,invalid-name
    """Create a test user."""
    return User.objects.create_user(
        username="testuser", email="test@example.com", password="testpass"
    )


@pytest.fixture
def oanda_account(db, user):  # pylint: disable=unused-argument
    """Create a test OANDA account."""
    # pylint: disable=import-outside-toplevel
    from accounts.models import OandaAccount

    return OandaAccount.objects.create(
        user=user,
        account_id="001-001-1234567-001",
        api_token="test_token",
        api_type="practice",
        balance=Decimal("10000.00"),
    )


@pytest.fixture
def strategy_instance(db, oanda_account):  # pylint: disable=unused-argument
    """Create a test strategy instance."""
    return Strategy.objects.create(
        account=oanda_account,
        strategy_type="scalping",
        config={
            "base_units": 1000,
            "momentum_lookback_seconds": 60,
            "min_momentum_pips": 3,
            "stop_loss_pips": 4,
            "take_profit_pips": 7,
            "max_holding_minutes": 10,
        },
        instruments=["EUR_USD"],
        is_active=True,
    )


@pytest.fixture
def scalping_strategy(strategy_instance):
    """Create a ScalpingStrategy instance."""
    return ScalpingStrategy(strategy_instance)


class TestMomentumDetector:
    """Test MomentumDetector class."""

    def test_add_price(self):
        """Test adding prices to history."""
        detector = MomentumDetector(lookback_seconds=60)
        now = timezone.now()

        detector.add_price("EUR_USD", now, Decimal("1.1000"))
        detector.add_price("EUR_USD", now + timedelta(seconds=30), Decimal("1.1010"))

        assert "EUR_USD" in detector.price_history
        assert len(detector.price_history["EUR_USD"]) == 2

    def test_detect_bullish_momentum(self):
        """Test detecting bullish momentum."""
        detector = MomentumDetector(lookback_seconds=60)
        now = timezone.now()

        # Add prices showing upward movement
        detector.add_price("EUR_USD", now, Decimal("1.1000"))
        detector.add_price("EUR_USD", now + timedelta(seconds=30), Decimal("1.1005"))
        detector.add_price("EUR_USD", now + timedelta(seconds=60), Decimal("1.1010"))

        direction, strength = detector.detect_momentum("EUR_USD", now + timedelta(seconds=60))

        assert direction == "bullish"
        assert strength > Decimal("0")

    def test_detect_bearish_momentum(self):
        """Test detecting bearish momentum."""
        detector = MomentumDetector(lookback_seconds=60)
        now = timezone.now()

        # Add prices showing downward movement
        detector.add_price("EUR_USD", now, Decimal("1.1010"))
        detector.add_price("EUR_USD", now + timedelta(seconds=30), Decimal("1.1005"))
        detector.add_price("EUR_USD", now + timedelta(seconds=60), Decimal("1.1000"))

        direction, strength = detector.detect_momentum("EUR_USD", now + timedelta(seconds=60))

        assert direction == "bearish"
        assert strength > Decimal("0")

    def test_no_momentum_insufficient_data(self):
        """Test no momentum with insufficient data."""
        detector = MomentumDetector(lookback_seconds=60)
        now = timezone.now()

        detector.add_price("EUR_USD", now, Decimal("1.1000"))

        direction, strength = detector.detect_momentum("EUR_USD", now)

        assert direction is None
        assert strength == Decimal("0")

    def test_clean_old_prices(self):
        """Test cleaning old prices from history."""
        detector = MomentumDetector(lookback_seconds=60)
        now = timezone.now()

        # Add old price
        detector.add_price("EUR_USD", now - timedelta(seconds=200), Decimal("1.1000"))
        # Add recent price
        detector.add_price("EUR_USD", now, Decimal("1.1010"))

        # Old price should be cleaned
        assert len(detector.price_history["EUR_USD"]) == 1


class TestScalpingStrategy:
    """Test ScalpingStrategy class."""

    def test_initialization(self, scalping_strategy):
        """Test strategy initialization."""
        assert scalping_strategy.base_units == Decimal("1000")
        assert scalping_strategy.momentum_lookback_seconds == 60
        assert scalping_strategy.min_momentum_pips == Decimal("3")
        assert scalping_strategy.stop_loss_pips == Decimal("4")
        assert scalping_strategy.take_profit_pips == Decimal("7")
        assert scalping_strategy.max_holding_minutes == 10

    def test_on_tick_no_momentum(
        self, scalping_strategy, oanda_account
    ):  # pylint: disable=unused-argument
        """Test on_tick with no momentum."""
        now = timezone.now()

        # Single tick - no momentum
        tick = TickData.objects.create(
            account=oanda_account,
            instrument="EUR_USD",
            timestamp=now,
            bid=Decimal("1.1000"),
            ask=Decimal("1.1002"),
            mid=Decimal("1.1001"),
        )

        orders = scalping_strategy.on_tick(tick)
        assert len(orders) == 0

    def test_on_tick_bullish_momentum_entry(
        self, scalping_strategy, oanda_account
    ):  # pylint: disable=unused-argument
        """Test on_tick with bullish momentum generates long entry."""
        now = timezone.now()

        # Create momentum with multiple ticks
        for i in range(5):
            tick = TickData.objects.create(
                account=oanda_account,
                instrument="EUR_USD",
                timestamp=now + timedelta(seconds=i * 15),
                bid=Decimal("1.1000") + Decimal(str(i * 0.0005)),
                ask=Decimal("1.1002") + Decimal(str(i * 0.0005)),
                mid=Decimal("1.1001") + Decimal(str(i * 0.0005)),
            )

            if i < 4:
                scalping_strategy.on_tick(tick)

        # Last tick should generate entry
        orders = scalping_strategy.on_tick(tick)

        assert len(orders) == 1
        order = orders[0]
        assert order.direction == "long"
        assert order.units == Decimal("1000")
        assert order.stop_loss is not None
        assert order.take_profit is not None

    def test_on_tick_bearish_momentum_entry(
        self, scalping_strategy, oanda_account
    ):  # pylint: disable=unused-argument
        """Test on_tick with bearish momentum generates short entry."""
        now = timezone.now()

        # Create momentum with multiple ticks
        for i in range(5):
            tick = TickData.objects.create(
                account=oanda_account,
                instrument="EUR_USD",
                timestamp=now + timedelta(seconds=i * 15),
                bid=Decimal("1.1010") - Decimal(str(i * 0.0005)),
                ask=Decimal("1.1012") - Decimal(str(i * 0.0005)),
                mid=Decimal("1.1011") - Decimal(str(i * 0.0005)),
            )

            if i < 4:
                scalping_strategy.on_tick(tick)

        # Last tick should generate entry
        orders = scalping_strategy.on_tick(tick)

        assert len(orders) == 1
        order = orders[0]
        assert order.direction == "short"
        assert order.units == Decimal("1000")
        assert order.stop_loss is not None
        assert order.take_profit is not None

    def test_stop_loss_placement_long(
        self, scalping_strategy, oanda_account
    ):  # pylint: disable=unused-argument
        """Test tight stop-loss placement for long position."""
        now = timezone.now()

        # Create bullish momentum
        for i in range(5):
            tick = TickData.objects.create(
                account=oanda_account,
                instrument="EUR_USD",
                timestamp=now + timedelta(seconds=i * 15),
                bid=Decimal("1.1000") + Decimal(str(i * 0.0005)),
                ask=Decimal("1.1002") + Decimal(str(i * 0.0005)),
                mid=Decimal("1.1001") + Decimal(str(i * 0.0005)),
            )

            if i < 4:
                scalping_strategy.on_tick(tick)

        orders = scalping_strategy.on_tick(tick)
        order = orders[0]

        # Stop loss should be 4 pips below entry
        expected_stop = tick.mid - (Decimal("4") * Decimal("0.0001"))
        assert order.stop_loss == expected_stop

    def test_take_profit_placement_short(
        self, scalping_strategy, oanda_account
    ):  # pylint: disable=unused-argument
        """Test quick take-profit placement for short position."""
        now = timezone.now()

        # Create bearish momentum
        for i in range(5):
            tick = TickData.objects.create(
                account=oanda_account,
                instrument="EUR_USD",
                timestamp=now + timedelta(seconds=i * 15),
                bid=Decimal("1.1010") - Decimal(str(i * 0.0005)),
                ask=Decimal("1.1012") - Decimal(str(i * 0.0005)),
                mid=Decimal("1.1011") - Decimal(str(i * 0.0005)),
            )

            if i < 4:
                scalping_strategy.on_tick(tick)

        orders = scalping_strategy.on_tick(tick)
        order = orders[0]

        # Take profit should be 7 pips below entry for short
        expected_tp = tick.mid - (Decimal("7") * Decimal("0.0001"))
        assert order.take_profit == expected_tp

    def test_max_holding_time_enforcement(
        self, scalping_strategy, oanda_account
    ):  # pylint: disable=unused-argument
        """Test maximum holding time enforcement."""
        now = timezone.now()

        # Create a position
        position = Position.objects.create(
            account=oanda_account,
            strategy=scalping_strategy.strategy,
            position_id="test_position_1",
            instrument="EUR_USD",
            direction="long",
            units=Decimal("1000"),
            entry_price=Decimal("1.1000"),
            current_price=Decimal("1.1005"),
            opened_at=now,
        )

        # Track entry time
        scalping_strategy.position_entry_times[position.position_id] = now

        # Create tick after max holding time
        tick = TickData.objects.create(
            account=oanda_account,
            instrument="EUR_USD",
            timestamp=now + timedelta(minutes=11),
            bid=Decimal("1.1004"),
            ask=Decimal("1.1006"),
            mid=Decimal("1.1005"),
        )

        orders = scalping_strategy.on_tick(tick)

        # Should generate close order
        assert len(orders) == 1
        order = orders[0]
        assert order.direction == "short"  # Opposite of position
        assert order.units == position.units

    def test_no_entry_with_existing_position(
        self, scalping_strategy, oanda_account
    ):  # pylint: disable=unused-argument
        """Test no new entry when position already exists."""
        now = timezone.now()

        # Create existing position
        Position.objects.create(
            account=oanda_account,
            strategy=scalping_strategy.strategy,
            position_id="test_position_1",
            instrument="EUR_USD",
            direction="long",
            units=Decimal("1000"),
            entry_price=Decimal("1.1000"),
            current_price=Decimal("1.1005"),
            opened_at=now,
        )

        # Create bullish momentum
        for i in range(5):
            tick = TickData.objects.create(
                account=oanda_account,
                instrument="EUR_USD",
                timestamp=now + timedelta(seconds=i * 15),
                bid=Decimal("1.1000") + Decimal(str(i * 0.0005)),
                ask=Decimal("1.1002") + Decimal(str(i * 0.0005)),
                mid=Decimal("1.1001") + Decimal(str(i * 0.0005)),
            )

            if i < 4:
                scalping_strategy.on_tick(tick)

        orders = scalping_strategy.on_tick(tick)

        # Should not generate new entry
        assert len(orders) == 0

    def test_on_position_update_cleanup(
        self, scalping_strategy, oanda_account
    ):  # pylint: disable=unused-argument
        """Test position update cleanup."""
        now = timezone.now()

        position = Position.objects.create(
            account=oanda_account,
            strategy=scalping_strategy.strategy,
            position_id="test_position_1",
            instrument="EUR_USD",
            direction="long",
            units=Decimal("1000"),
            entry_price=Decimal("1.1000"),
            current_price=Decimal("1.1005"),
            opened_at=now,
            closed_at=now + timedelta(minutes=5),
        )

        # Add to tracking
        scalping_strategy.position_entry_times[position.position_id] = now

        # Call on_position_update
        scalping_strategy.on_position_update(position)

        # Should clean up tracking
        assert position.position_id not in (scalping_strategy.position_entry_times)

    def test_validate_config_valid(self, scalping_strategy):
        """Test config validation with valid config."""
        config = {
            "base_units": 1000,
            "momentum_lookback_seconds": 60,
            "min_momentum_pips": 3,
            "stop_loss_pips": 4,
            "take_profit_pips": 7,
            "max_holding_minutes": 10,
        }

        assert scalping_strategy.validate_config(config) is True

    def test_validate_config_invalid_base_units(self, scalping_strategy):
        """Test config validation with invalid base units."""
        config = {
            "base_units": -1000,
            "momentum_lookback_seconds": 60,
            "min_momentum_pips": 3,
            "stop_loss_pips": 4,
            "take_profit_pips": 7,
            "max_holding_minutes": 10,
        }

        with pytest.raises(ValueError, match="base_units must be positive"):
            scalping_strategy.validate_config(config)

    def test_validate_config_invalid_lookback(self, scalping_strategy):
        """Test config validation with invalid lookback seconds."""
        config = {
            "base_units": 1000,
            "momentum_lookback_seconds": -60,
            "min_momentum_pips": 3,
            "stop_loss_pips": 4,
            "take_profit_pips": 7,
            "max_holding_minutes": 10,
        }

        with pytest.raises(ValueError, match="momentum_lookback_seconds must be positive"):
            scalping_strategy.validate_config(config)

    def test_validate_config_invalid_stop_loss(self, scalping_strategy):
        """Test config validation with invalid stop loss."""
        config = {
            "base_units": 1000,
            "momentum_lookback_seconds": 60,
            "min_momentum_pips": 3,
            "stop_loss_pips": 0,
            "take_profit_pips": 7,
            "max_holding_minutes": 10,
        }

        with pytest.raises(ValueError, match="stop_loss_pips must be positive"):
            scalping_strategy.validate_config(config)

    def test_jpy_pair_pip_calculation(
        self, scalping_strategy, oanda_account
    ):  # pylint: disable=unused-argument
        """Test pip calculation for JPY pairs."""
        now = timezone.now()

        # Update strategy to trade USD_JPY
        scalping_strategy.instruments = ["USD_JPY"]

        # Create bullish momentum for JPY pair
        for i in range(5):
            tick = TickData.objects.create(
                account=oanda_account,
                instrument="USD_JPY",
                timestamp=now + timedelta(seconds=i * 15),
                bid=Decimal("110.00") + Decimal(str(i * 0.05)),
                ask=Decimal("110.02") + Decimal(str(i * 0.05)),
                mid=Decimal("110.01") + Decimal(str(i * 0.05)),
            )

            if i < 4:
                scalping_strategy.on_tick(tick)

        orders = scalping_strategy.on_tick(tick)

        if orders:
            order = orders[0]
            # For JPY pairs, pip value is 0.01
            expected_stop = tick.mid - (Decimal("4") * Decimal("0.01"))
            assert order.stop_loss == expected_stop
