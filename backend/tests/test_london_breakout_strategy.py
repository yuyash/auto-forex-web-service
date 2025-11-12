"""
Unit tests for London Breakout Strategy.

Requirements: 5.1, 5.3
"""

from datetime import datetime
from datetime import timezone as dt_timezone
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone

import pytest

from accounts.models import OandaAccount
from trading.london_breakout_strategy import (
    LondonBreakoutStrategy,
    LondonSessionDetector,
    RangeDetector,
)
from trading.models import Position, Strategy
from trading.tick_data_models import TickData


@pytest.fixture
def mock_oanda_account(db):
    """Create a mock OANDA account for testing."""
    User = get_user_model()
    user = User.objects.create_user(
        username="testuser", email="test@example.com", password="testpass123"
    )

    account = OandaAccount.objects.create(
        user=user,
        account_id="001-001-1234567-001",
        api_token="test_token_12345",
        api_type="practice",
        balance=10000.00,
        is_active=True,
    )
    return account


@pytest.fixture
def mock_strategy(db, mock_oanda_account):
    """Create a mock Strategy instance for testing."""
    strategy = Strategy.objects.create(
        account=mock_oanda_account,
        strategy_type="london_breakout",
        config={
            "base_units": 1000,
            "stop_loss_pips": 20,
            "take_profit_pips": 40,
            "min_range_pips": 10,
        },
        instrument="EUR_USD",
        is_active=True,
    )
    return strategy


@pytest.fixture
def london_strategy(mock_strategy):
    """Create a LondonBreakoutStrategy instance for testing."""
    return LondonBreakoutStrategy(mock_strategy)


class TestLondonSessionDetector:
    """Test London session detection."""

    def test_range_detection_period(self):
        """Test London session time detection for range period (8:00-9:00 GMT)."""
        detector = LondonSessionDetector()

        # Test within range detection period
        dt_in_range = datetime(2025, 1, 15, 8, 30, 0, tzinfo=dt_timezone.utc)
        assert detector.is_range_detection_period(dt_in_range) is True

        # Test at start of range
        dt_start = datetime(2025, 1, 15, 8, 0, 0, tzinfo=dt_timezone.utc)
        assert detector.is_range_detection_period(dt_start) is True

        # Test just before end of range
        dt_before_end = datetime(2025, 1, 15, 8, 59, 59, tzinfo=dt_timezone.utc)
        assert detector.is_range_detection_period(dt_before_end) is True

        # Test at end of range (should be False)
        dt_end = datetime(2025, 1, 15, 9, 0, 0, tzinfo=dt_timezone.utc)
        assert detector.is_range_detection_period(dt_end) is False

        # Test outside range detection period
        dt_outside = datetime(2025, 1, 15, 10, 0, 0, tzinfo=dt_timezone.utc)
        assert detector.is_range_detection_period(dt_outside) is False

        # Test before range
        dt_before = datetime(2025, 1, 15, 7, 0, 0, tzinfo=dt_timezone.utc)
        assert detector.is_range_detection_period(dt_before) is False

    def test_london_session(self):
        """Test London session detection (8:00-16:00 GMT)."""
        detector = LondonSessionDetector()

        # Test within session
        dt_in_session = datetime(2025, 1, 15, 12, 0, 0, tzinfo=dt_timezone.utc)
        assert detector.is_london_session(dt_in_session) is True

        # Test at start of session
        dt_start = datetime(2025, 1, 15, 8, 0, 0, tzinfo=dt_timezone.utc)
        assert detector.is_london_session(dt_start) is True

        # Test just before end
        dt_before_end = datetime(2025, 1, 15, 15, 59, 59, tzinfo=dt_timezone.utc)
        assert detector.is_london_session(dt_before_end) is True

        # Test at end (should be False)
        dt_end = datetime(2025, 1, 15, 16, 0, 0, tzinfo=dt_timezone.utc)
        assert detector.is_london_session(dt_end) is False

        # Test outside session
        dt_outside = datetime(2025, 1, 15, 18, 0, 0, tzinfo=dt_timezone.utc)
        assert detector.is_london_session(dt_outside) is False

    def test_session_end(self):
        """Test session end detection."""
        detector = LondonSessionDetector()

        # Test at session end
        dt_end = datetime(2025, 1, 15, 16, 0, 0, tzinfo=dt_timezone.utc)
        assert detector.is_session_end(dt_end) is True

        # Test after session end
        dt_after = datetime(2025, 1, 15, 17, 0, 0, tzinfo=dt_timezone.utc)
        assert detector.is_session_end(dt_after) is True

        # Test before session end
        dt_before = datetime(2025, 1, 15, 15, 59, 59, tzinfo=dt_timezone.utc)
        assert detector.is_session_end(dt_before) is False


class TestRangeDetector:
    """Test range high/low detection."""

    def test_range_high_low_calculation(self):
        """Test range high/low calculation during detection period."""
        detector = RangeDetector()
        dt = datetime(2025, 1, 15, 8, 30, 0, tzinfo=dt_timezone.utc)

        # Update with prices
        detector.update_range(Decimal("1.1000"), dt)
        assert detector.range_high == Decimal("1.1000")
        assert detector.range_low == Decimal("1.1000")

        detector.update_range(Decimal("1.1050"), dt)
        assert detector.range_high == Decimal("1.1050")
        assert detector.range_low == Decimal("1.1000")

        detector.update_range(Decimal("1.0980"), dt)
        assert detector.range_high == Decimal("1.1050")
        assert detector.range_low == Decimal("1.0980")

        detector.update_range(Decimal("1.1020"), dt)
        assert detector.range_high == Decimal("1.1050")
        assert detector.range_low == Decimal("1.0980")

    def test_range_finalization(self):
        """Test range finalization after detection period."""
        detector = RangeDetector()
        dt = datetime(2025, 1, 15, 8, 30, 0, tzinfo=dt_timezone.utc)

        # Update range
        detector.update_range(Decimal("1.1000"), dt)
        detector.update_range(Decimal("1.1050"), dt)
        detector.update_range(Decimal("1.0980"), dt)

        # Range should not be established yet
        assert detector.range_established is False

        # Finalize range
        detector.finalize_range()
        assert detector.range_established is True

    def test_range_reset_on_new_day(self):
        """Test range reset when new day starts."""
        detector = RangeDetector()
        dt1 = datetime(2025, 1, 15, 8, 30, 0, tzinfo=dt_timezone.utc)
        dt2 = datetime(2025, 1, 16, 8, 30, 0, tzinfo=dt_timezone.utc)

        # Set range for day 1
        detector.update_range(Decimal("1.1000"), dt1)
        detector.update_range(Decimal("1.1050"), dt1)
        detector.finalize_range()

        assert detector.range_high == Decimal("1.1050")
        assert detector.range_low == Decimal("1.1000")
        assert detector.range_established is True

        # Update with new day - should reset
        detector.update_range(Decimal("1.2000"), dt2)

        assert detector.range_high == Decimal("1.2000")
        assert detector.range_low == Decimal("1.2000")
        assert detector.range_established is False

    def test_breakout_above_detection(self):
        """Test breakout above range detection."""
        detector = RangeDetector()
        dt = datetime(2025, 1, 15, 8, 30, 0, tzinfo=dt_timezone.utc)

        # Set range
        detector.update_range(Decimal("1.1000"), dt)
        detector.update_range(Decimal("1.1050"), dt)
        detector.finalize_range()

        # Test breakout above
        assert detector.is_breakout_above(Decimal("1.1060")) is True
        assert detector.is_breakout_above(Decimal("1.1050")) is False
        assert detector.is_breakout_above(Decimal("1.1040")) is False

    def test_breakout_below_detection(self):
        """Test breakout below range detection."""
        detector = RangeDetector()
        dt = datetime(2025, 1, 15, 8, 30, 0, tzinfo=dt_timezone.utc)

        # Set range
        detector.update_range(Decimal("1.1000"), dt)
        detector.update_range(Decimal("1.1050"), dt)
        detector.finalize_range()

        # Test breakout below
        assert detector.is_breakout_below(Decimal("1.0990")) is True
        assert detector.is_breakout_below(Decimal("1.1000")) is False
        assert detector.is_breakout_below(Decimal("1.1010")) is False

    def test_range_size_pips_calculation(self):
        """Test range size calculation in pips."""
        detector = RangeDetector()
        dt = datetime(2025, 1, 15, 8, 30, 0, tzinfo=dt_timezone.utc)

        # Set range for EUR_USD
        detector.update_range(Decimal("1.1000"), dt)
        detector.update_range(Decimal("1.1050"), dt)

        range_size = detector.get_range_size_pips("EUR_USD")
        assert range_size == Decimal("50")  # 50 pips

        # Test with JPY pair
        detector2 = RangeDetector()
        detector2.update_range(Decimal("110.00"), dt)
        detector2.update_range(Decimal("110.50"), dt)

        range_size_jpy = detector2.get_range_size_pips("USD_JPY")
        assert range_size_jpy == Decimal("50")  # 50 pips for JPY


class TestLondonBreakoutStrategy:
    """Test London Breakout Strategy implementation."""

    def test_strategy_initialization(self, london_strategy):
        """Test strategy initialization with configuration."""
        assert london_strategy.base_units == Decimal("1000")
        assert london_strategy.stop_loss_pips == Decimal("20")
        assert london_strategy.take_profit_pips == Decimal("40")
        assert london_strategy.min_range_pips == Decimal("10")
        assert "EUR_USD" in london_strategy.range_detectors
        assert len(london_strategy.range_detectors) == 1

    def test_range_detection_during_first_hour(self, london_strategy, mock_oanda_account):
        """Test range detection during London first hour."""
        # Create ticks during range detection period
        dt1 = datetime(2025, 1, 15, 8, 10, 0, tzinfo=dt_timezone.utc)
        tick1 = TickData.objects.create(
            account=mock_oanda_account,
            instrument="EUR_USD",
            timestamp=dt1,
            bid=Decimal("1.0995"),
            ask=Decimal("1.1005"),
            mid=Decimal("1.1000"),
        )

        dt2 = datetime(2025, 1, 15, 8, 30, 0, tzinfo=dt_timezone.utc)
        tick2 = TickData.objects.create(
            account=mock_oanda_account,
            instrument="EUR_USD",
            timestamp=dt2,
            bid=Decimal("1.1045"),
            ask=Decimal("1.1055"),
            mid=Decimal("1.1050"),
        )

        dt3 = datetime(2025, 1, 15, 8, 50, 0, tzinfo=dt_timezone.utc)
        tick3 = TickData.objects.create(
            account=mock_oanda_account,
            instrument="EUR_USD",
            timestamp=dt3,
            bid=Decimal("1.0975"),
            ask=Decimal("1.0985"),
            mid=Decimal("1.0980"),
        )

        # Process ticks
        london_strategy.on_tick(tick1)
        london_strategy.on_tick(tick2)
        london_strategy.on_tick(tick3)

        # Check range was updated
        range_detector = london_strategy.range_detectors["EUR_USD"]
        assert range_detector.range_high == Decimal("1.1050")
        assert range_detector.range_low == Decimal("1.0980")

    def test_breakout_signal_generation_above(self, london_strategy, mock_oanda_account):
        """Test breakout signal generation when price breaks above range."""
        # Set up range first
        dt_range = datetime(2025, 1, 15, 8, 30, 0, tzinfo=dt_timezone.utc)
        range_detector = london_strategy.range_detectors["EUR_USD"]
        range_detector.update_range(Decimal("1.1000"), dt_range)
        range_detector.update_range(Decimal("1.1050"), dt_range)
        range_detector.finalize_range()

        # Create breakout tick
        dt_breakout = datetime(2025, 1, 15, 10, 0, 0, tzinfo=dt_timezone.utc)
        tick_breakout = TickData.objects.create(
            account=mock_oanda_account,
            instrument="EUR_USD",
            timestamp=dt_breakout,
            bid=Decimal("1.1055"),
            ask=Decimal("1.1065"),
            mid=Decimal("1.1060"),
        )

        # Process breakout tick
        orders = london_strategy.on_tick(tick_breakout)

        # Should generate long entry order
        assert len(orders) == 1
        order = orders[0]
        assert order.direction == "long"
        assert order.units == Decimal("1000")
        assert order.instrument == "EUR_USD"
        assert order.stop_loss is not None
        assert order.take_profit is not None

    def test_breakout_signal_generation_below(self, london_strategy, mock_oanda_account):
        """Test breakout signal generation when price breaks below range."""
        # Set up range first
        dt_range = datetime(2025, 1, 15, 8, 30, 0, tzinfo=dt_timezone.utc)
        range_detector = london_strategy.range_detectors["EUR_USD"]
        range_detector.update_range(Decimal("1.1000"), dt_range)
        range_detector.update_range(Decimal("1.1050"), dt_range)
        range_detector.finalize_range()

        # Create breakout tick
        dt_breakout = datetime(2025, 1, 15, 10, 0, 0, tzinfo=dt_timezone.utc)
        tick_breakout = TickData.objects.create(
            account=mock_oanda_account,
            instrument="EUR_USD",
            timestamp=dt_breakout,
            bid=Decimal("1.0985"),
            ask=Decimal("1.0995"),
            mid=Decimal("1.0990"),
        )

        # Process breakout tick
        orders = london_strategy.on_tick(tick_breakout)

        # Should generate short entry order
        assert len(orders) == 1
        order = orders[0]
        assert order.direction == "short"
        assert order.units == Decimal("1000")
        assert order.instrument == "EUR_USD"
        assert order.stop_loss is not None
        assert order.take_profit is not None

    def test_time_based_exit_logic(self, london_strategy, mock_oanda_account, mock_strategy):
        """Test time-based exit at end of London session."""
        # Set up range and create position
        dt_range = datetime(2025, 1, 15, 8, 30, 0, tzinfo=dt_timezone.utc)
        range_detector = london_strategy.range_detectors["EUR_USD"]
        range_detector.update_range(Decimal("1.1000"), dt_range)
        range_detector.update_range(Decimal("1.1050"), dt_range)
        range_detector.finalize_range()

        # Create open position
        Position.objects.create(
            account=mock_oanda_account,
            strategy=mock_strategy,
            position_id="test_position_1",
            instrument="EUR_USD",
            direction="long",
            units=Decimal("1000"),
            entry_price=Decimal("1.1060"),
            current_price=Decimal("1.1060"),
            opened_at=timezone.now(),
        )

        # Create tick at session end
        dt_end = datetime(2025, 1, 15, 16, 0, 0, tzinfo=dt_timezone.utc)
        tick_end = TickData.objects.create(
            account=mock_oanda_account,
            instrument="EUR_USD",
            timestamp=dt_end,
            bid=Decimal("1.1075"),
            ask=Decimal("1.1085"),
            mid=Decimal("1.1080"),
        )

        # Process session end tick
        orders = london_strategy.on_tick(tick_end)

        # Should generate close order
        assert len(orders) == 1
        order = orders[0]
        assert order.direction == "short"  # Opposite of position
        assert order.units == Decimal("1000")
        assert order.instrument == "EUR_USD"

    def test_strategy_on_tick_processing(self, london_strategy, mock_oanda_account):
        """Test complete strategy on_tick processing flow."""
        # Test 1: During range detection - establish a range
        dt1 = datetime(2025, 1, 15, 8, 10, 0, tzinfo=dt_timezone.utc)
        tick1 = TickData.objects.create(
            account=mock_oanda_account,
            instrument="EUR_USD",
            timestamp=dt1,
            bid=Decimal("1.0995"),
            ask=Decimal("1.1005"),
            mid=Decimal("1.1000"),
        )
        orders1 = london_strategy.on_tick(tick1)
        assert len(orders1) == 0  # No orders during range detection

        # Add more ticks to establish range high and low
        dt1b = datetime(2025, 1, 15, 8, 30, 0, tzinfo=dt_timezone.utc)
        tick1b = TickData.objects.create(
            account=mock_oanda_account,
            instrument="EUR_USD",
            timestamp=dt1b,
            bid=Decimal("1.1045"),
            ask=Decimal("1.1055"),
            mid=Decimal("1.1050"),
        )
        london_strategy.on_tick(tick1b)

        dt1c = datetime(2025, 1, 15, 8, 50, 0, tzinfo=dt_timezone.utc)
        tick1c = TickData.objects.create(
            account=mock_oanda_account,
            instrument="EUR_USD",
            timestamp=dt1c,
            bid=Decimal("1.0975"),
            ask=Decimal("1.0985"),
            mid=Decimal("1.0980"),
        )
        london_strategy.on_tick(tick1c)

        # Test 2: After range established, no breakout
        dt2 = datetime(2025, 1, 15, 9, 30, 0, tzinfo=dt_timezone.utc)
        range_detector = london_strategy.range_detectors["EUR_USD"]
        range_detector.finalize_range()

        tick2 = TickData.objects.create(
            account=mock_oanda_account,
            instrument="EUR_USD",
            timestamp=dt2,
            bid=Decimal("1.1015"),
            ask=Decimal("1.1025"),
            mid=Decimal("1.1020"),
        )
        orders2 = london_strategy.on_tick(tick2)
        assert len(orders2) == 0  # No orders, price within range

        # Test 3: Breakout above range
        dt3 = datetime(2025, 1, 15, 10, 0, 0, tzinfo=dt_timezone.utc)
        tick3 = TickData.objects.create(
            account=mock_oanda_account,
            instrument="EUR_USD",
            timestamp=dt3,
            bid=Decimal("1.1055"),
            ask=Decimal("1.1065"),
            mid=Decimal("1.1060"),
        )
        orders3 = london_strategy.on_tick(tick3)
        assert len(orders3) == 1  # Entry order generated
        assert orders3[0].direction == "long"

    def test_min_range_size_filter(self, london_strategy, mock_oanda_account):
        """Test that strategy doesn't trade if range is too small."""
        # Set up small range (less than min_range_pips)
        dt_range = datetime(2025, 1, 15, 8, 30, 0, tzinfo=dt_timezone.utc)
        range_detector = london_strategy.range_detectors["EUR_USD"]
        range_detector.update_range(Decimal("1.1000"), dt_range)
        range_detector.update_range(Decimal("1.1005"), dt_range)  # Only 5 pips
        range_detector.finalize_range()

        # Create breakout tick
        dt_breakout = datetime(2025, 1, 15, 10, 0, 0, tzinfo=dt_timezone.utc)
        tick_breakout = TickData.objects.create(
            account=mock_oanda_account,
            instrument="EUR_USD",
            timestamp=dt_breakout,
            bid=Decimal("1.1010"),
            ask=Decimal("1.1020"),
            mid=Decimal("1.1015"),
        )

        # Process breakout tick
        orders = london_strategy.on_tick(tick_breakout)

        # Should not generate orders (range too small)
        assert len(orders) == 0

    def test_validate_config_valid(self, london_strategy):
        """Test configuration validation with valid config."""
        valid_config = {
            "base_units": 1000,
            "stop_loss_pips": 20,
            "take_profit_pips": 40,
            "min_range_pips": 10,
        }

        result = london_strategy.validate_config(valid_config)
        assert result is True

    def test_validate_config_invalid_base_units(self, london_strategy):
        """Test configuration validation with invalid base units."""
        invalid_config = {
            "base_units": -1000,
            "stop_loss_pips": 20,
            "take_profit_pips": 40,
            "min_range_pips": 10,
        }

        with pytest.raises(ValueError, match="base_units must be positive"):
            london_strategy.validate_config(invalid_config)

    def test_validate_config_invalid_stop_loss(self, london_strategy):
        """Test configuration validation with invalid stop loss."""
        invalid_config = {
            "base_units": 1000,
            "stop_loss_pips": 0,
            "take_profit_pips": 40,
            "min_range_pips": 10,
        }

        with pytest.raises(ValueError, match="stop_loss_pips must be positive"):
            london_strategy.validate_config(invalid_config)

    def test_validate_config_invalid_take_profit(self, london_strategy):
        """Test configuration validation with invalid take profit."""
        invalid_config = {
            "base_units": 1000,
            "stop_loss_pips": 20,
            "take_profit_pips": -40,
            "min_range_pips": 10,
        }

        with pytest.raises(ValueError, match="take_profit_pips must be positive"):
            london_strategy.validate_config(invalid_config)

    def test_validate_config_invalid_min_range(self, london_strategy):
        """Test configuration validation with invalid min range."""
        invalid_config = {
            "base_units": 1000,
            "stop_loss_pips": 20,
            "take_profit_pips": 40,
            "min_range_pips": 0,
        }

        with pytest.raises(ValueError, match="min_range_pips must be positive"):
            london_strategy.validate_config(invalid_config)
