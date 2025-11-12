"""
Unit tests for Asian Range Strategy.

Requirements: 5.1, 5.3
"""

from datetime import datetime
from datetime import timezone as dt_timezone
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone

import pytest

from accounts.models import OandaAccount
from trading.asian_range_strategy import (
    AsianRangeDetector,
    AsianRangeStrategy,
    AsianSessionDetector,
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
        strategy_type="asian_range",
        config={
            "base_units": 1000,
            "support_tolerance_pips": 5,
            "resistance_tolerance_pips": 5,
            "stop_loss_pips": 15,
            "take_profit_pips": 30,
            "min_range_pips": 15,
        },
        instrument="EUR_USD",
        is_active=True,
    )
    return strategy


@pytest.fixture
def asian_strategy(mock_strategy):
    """Create an AsianRangeStrategy instance for testing."""
    return AsianRangeStrategy(mock_strategy)


class TestAsianSessionDetector:
    """Test Asian session detection."""

    def test_asian_session_time_detection(self):
        """Test Asian session time detection (Tokyo: 00:00-09:00 GMT)."""
        detector = AsianSessionDetector()

        # Test within Asian session
        dt_in_session = datetime(2025, 1, 15, 4, 30, 0, tzinfo=dt_timezone.utc)
        assert detector.is_asian_session(dt_in_session) is True

        # Test at start of session
        dt_start = datetime(2025, 1, 15, 0, 0, 0, tzinfo=dt_timezone.utc)
        assert detector.is_asian_session(dt_start) is True

        # Test just before end of session
        dt_before_end = datetime(2025, 1, 15, 8, 59, 59, tzinfo=dt_timezone.utc)
        assert detector.is_asian_session(dt_before_end) is True

        # Test at end of session (should be False)
        dt_end = datetime(2025, 1, 15, 9, 0, 0, tzinfo=dt_timezone.utc)
        assert detector.is_asian_session(dt_end) is False

        # Test outside session
        dt_outside = datetime(2025, 1, 15, 12, 0, 0, tzinfo=dt_timezone.utc)
        assert detector.is_asian_session(dt_outside) is False

        # Test before session
        dt_before = datetime(2025, 1, 14, 23, 30, 0, tzinfo=dt_timezone.utc)
        assert detector.is_asian_session(dt_before) is False


class TestAsianRangeDetector:
    """Test range high/low detection."""

    def test_range_high_low_calculation(self):
        """Test range high/low calculation during Asian session."""
        detector = AsianRangeDetector()
        dt = datetime(2025, 1, 15, 4, 30, 0, tzinfo=dt_timezone.utc)

        # Update with prices
        detector.update_range(Decimal("1.1000"), dt)
        assert detector.range_high == Decimal("1.1000")
        assert detector.range_low == Decimal("1.1000")
        assert detector.range_established is True

        detector.update_range(Decimal("1.1050"), dt)
        assert detector.range_high == Decimal("1.1050")
        assert detector.range_low == Decimal("1.1000")

        detector.update_range(Decimal("1.0980"), dt)
        assert detector.range_high == Decimal("1.1050")
        assert detector.range_low == Decimal("1.0980")

        detector.update_range(Decimal("1.1020"), dt)
        assert detector.range_high == Decimal("1.1050")
        assert detector.range_low == Decimal("1.0980")

    def test_range_reset_on_new_day(self):
        """Test range reset when new day starts."""
        detector = AsianRangeDetector()
        dt1 = datetime(2025, 1, 15, 4, 30, 0, tzinfo=dt_timezone.utc)
        dt2 = datetime(2025, 1, 16, 4, 30, 0, tzinfo=dt_timezone.utc)

        # Set range for day 1
        detector.update_range(Decimal("1.1000"), dt1)
        detector.update_range(Decimal("1.1050"), dt1)

        assert detector.range_high == Decimal("1.1050")
        assert detector.range_low == Decimal("1.1000")
        assert detector.range_established is True

        # Update with new day - should reset
        detector.update_range(Decimal("1.2000"), dt2)

        assert detector.range_high == Decimal("1.2000")
        assert detector.range_low == Decimal("1.2000")
        assert detector.range_established is True

    def test_breakout_above_detection(self):
        """Test breakout above range detection."""
        detector = AsianRangeDetector()
        dt = datetime(2025, 1, 15, 4, 30, 0, tzinfo=dt_timezone.utc)

        # Set range
        detector.update_range(Decimal("1.1000"), dt)
        detector.update_range(Decimal("1.1050"), dt)

        # Test breakout above
        assert detector.is_breakout_above(Decimal("1.1060")) is True
        assert detector.is_breakout_above(Decimal("1.1050")) is False
        assert detector.is_breakout_above(Decimal("1.1040")) is False

    def test_breakout_below_detection(self):
        """Test breakout below range detection."""
        detector = AsianRangeDetector()
        dt = datetime(2025, 1, 15, 4, 30, 0, tzinfo=dt_timezone.utc)

        # Set range
        detector.update_range(Decimal("1.1000"), dt)
        detector.update_range(Decimal("1.1050"), dt)

        # Test breakout below
        assert detector.is_breakout_below(Decimal("1.0990")) is True
        assert detector.is_breakout_below(Decimal("1.1000")) is False
        assert detector.is_breakout_below(Decimal("1.1010")) is False

    def test_near_support_detection(self):
        """Test detection of price near support level."""
        detector = AsianRangeDetector()
        dt = datetime(2025, 1, 15, 4, 30, 0, tzinfo=dt_timezone.utc)

        # Set range
        detector.update_range(Decimal("1.1000"), dt)
        detector.update_range(Decimal("1.1050"), dt)

        # Test near support (within 5 pips)
        assert detector.is_near_support(Decimal("1.1000"), Decimal("5"), "EUR_USD") is True
        assert detector.is_near_support(Decimal("1.1005"), Decimal("5"), "EUR_USD") is True
        assert detector.is_near_support(Decimal("1.0995"), Decimal("5"), "EUR_USD") is True

        # Test not near support
        assert detector.is_near_support(Decimal("1.1010"), Decimal("5"), "EUR_USD") is False
        assert detector.is_near_support(Decimal("1.1050"), Decimal("5"), "EUR_USD") is False

    def test_near_resistance_detection(self):
        """Test detection of price near resistance level."""
        detector = AsianRangeDetector()
        dt = datetime(2025, 1, 15, 4, 30, 0, tzinfo=dt_timezone.utc)

        # Set range
        detector.update_range(Decimal("1.1000"), dt)
        detector.update_range(Decimal("1.1050"), dt)

        # Test near resistance (within 5 pips)
        assert detector.is_near_resistance(Decimal("1.1050"), Decimal("5"), "EUR_USD") is True
        assert detector.is_near_resistance(Decimal("1.1055"), Decimal("5"), "EUR_USD") is True
        assert detector.is_near_resistance(Decimal("1.1045"), Decimal("5"), "EUR_USD") is True

        # Test not near resistance
        assert detector.is_near_resistance(Decimal("1.1040"), Decimal("5"), "EUR_USD") is False
        assert detector.is_near_resistance(Decimal("1.1000"), Decimal("5"), "EUR_USD") is False

    def test_range_size_pips_calculation(self):
        """Test range size calculation in pips."""
        detector = AsianRangeDetector()
        dt = datetime(2025, 1, 15, 4, 30, 0, tzinfo=dt_timezone.utc)

        # Set range for EUR_USD
        detector.update_range(Decimal("1.1000"), dt)
        detector.update_range(Decimal("1.1050"), dt)

        range_size = detector.get_range_size_pips("EUR_USD")
        assert range_size == Decimal("50")  # 50 pips

        # Test with JPY pair
        detector2 = AsianRangeDetector()
        detector2.update_range(Decimal("110.00"), dt)
        detector2.update_range(Decimal("110.50"), dt)

        range_size_jpy = detector2.get_range_size_pips("USD_JPY")
        assert range_size_jpy == Decimal("50")  # 50 pips for JPY


class TestAsianRangeStrategy:
    """Test Asian Range Strategy implementation."""

    def test_strategy_initialization(self, asian_strategy):
        """Test strategy initialization with configuration."""
        assert asian_strategy.base_units == Decimal("1000")
        assert asian_strategy.support_tolerance_pips == Decimal("5")
        assert asian_strategy.resistance_tolerance_pips == Decimal("5")
        assert asian_strategy.stop_loss_pips == Decimal("15")
        assert asian_strategy.take_profit_pips == Decimal("30")
        assert asian_strategy.min_range_pips == Decimal("15")
        assert "EUR_USD" in asian_strategy.range_detectors
        assert len(asian_strategy.range_detectors) == 1

    def test_range_detection_during_asian_session(self, asian_strategy, mock_oanda_account):
        """Test range detection during Asian session."""
        # Create ticks during Asian session
        dt1 = datetime(2025, 1, 15, 2, 0, 0, tzinfo=dt_timezone.utc)
        tick1 = TickData.objects.create(
            account=mock_oanda_account,
            instrument="EUR_USD",
            timestamp=dt1,
            bid=Decimal("1.0995"),
            ask=Decimal("1.1005"),
            mid=Decimal("1.1000"),
        )

        dt2 = datetime(2025, 1, 15, 4, 0, 0, tzinfo=dt_timezone.utc)
        tick2 = TickData.objects.create(
            account=mock_oanda_account,
            instrument="EUR_USD",
            timestamp=dt2,
            bid=Decimal("1.1045"),
            ask=Decimal("1.1055"),
            mid=Decimal("1.1050"),
        )

        dt3 = datetime(2025, 1, 15, 6, 0, 0, tzinfo=dt_timezone.utc)
        tick3 = TickData.objects.create(
            account=mock_oanda_account,
            instrument="EUR_USD",
            timestamp=dt3,
            bid=Decimal("1.0975"),
            ask=Decimal("1.0985"),
            mid=Decimal("1.0980"),
        )

        # Process ticks
        asian_strategy.on_tick(tick1)
        asian_strategy.on_tick(tick2)
        asian_strategy.on_tick(tick3)

        # Check range was updated
        range_detector = asian_strategy.range_detectors["EUR_USD"]
        assert range_detector.range_high == Decimal("1.1050")
        assert range_detector.range_low == Decimal("1.0980")
        assert range_detector.range_established is True

    def test_range_bound_entry_at_support(self, asian_strategy, mock_oanda_account):
        """Test range-bound entry signal when price is near support."""
        # Set up range first
        dt_range = datetime(2025, 1, 15, 4, 0, 0, tzinfo=dt_timezone.utc)
        range_detector = asian_strategy.range_detectors["EUR_USD"]
        range_detector.update_range(Decimal("1.1000"), dt_range)
        range_detector.update_range(Decimal("1.1050"), dt_range)

        # Create tick near support (outside Asian session)
        dt_support = datetime(2025, 1, 15, 10, 0, 0, tzinfo=dt_timezone.utc)
        tick_support = TickData.objects.create(
            account=mock_oanda_account,
            instrument="EUR_USD",
            timestamp=dt_support,
            bid=Decimal("1.0995"),
            ask=Decimal("1.1005"),
            mid=Decimal("1.1000"),
        )

        # Process tick
        orders = asian_strategy.on_tick(tick_support)

        # Should generate long entry order
        assert len(orders) == 1
        order = orders[0]
        assert order.direction == "long"
        assert order.units == Decimal("1000")
        assert order.instrument == "EUR_USD"
        assert order.stop_loss is not None
        assert order.take_profit is not None

    def test_range_bound_entry_at_resistance(self, asian_strategy, mock_oanda_account):
        """Test range-bound entry signal when price is near resistance."""
        # Set up range first
        dt_range = datetime(2025, 1, 15, 4, 0, 0, tzinfo=dt_timezone.utc)
        range_detector = asian_strategy.range_detectors["EUR_USD"]
        range_detector.update_range(Decimal("1.1000"), dt_range)
        range_detector.update_range(Decimal("1.1050"), dt_range)

        # Create tick near resistance (outside Asian session)
        dt_resistance = datetime(2025, 1, 15, 10, 0, 0, tzinfo=dt_timezone.utc)
        tick_resistance = TickData.objects.create(
            account=mock_oanda_account,
            instrument="EUR_USD",
            timestamp=dt_resistance,
            bid=Decimal("1.1045"),
            ask=Decimal("1.1055"),
            mid=Decimal("1.1050"),
        )

        # Process tick
        orders = asian_strategy.on_tick(tick_resistance)

        # Should generate short entry order
        assert len(orders) == 1
        order = orders[0]
        assert order.direction == "short"
        assert order.units == Decimal("1000")
        assert order.instrument == "EUR_USD"
        assert order.stop_loss is not None
        assert order.take_profit is not None

    def test_breakout_detection_and_exit(self, asian_strategy, mock_oanda_account, mock_strategy):
        """Test breakout detection and position exit."""
        # Set up range
        dt_range = datetime(2025, 1, 15, 4, 0, 0, tzinfo=dt_timezone.utc)
        range_detector = asian_strategy.range_detectors["EUR_USD"]
        range_detector.update_range(Decimal("1.1000"), dt_range)
        range_detector.update_range(Decimal("1.1050"), dt_range)

        # Create open position
        Position.objects.create(
            account=mock_oanda_account,
            strategy=mock_strategy,
            position_id="test_position_1",
            instrument="EUR_USD",
            direction="long",
            units=Decimal("1000"),
            entry_price=Decimal("1.1000"),
            current_price=Decimal("1.1000"),
            opened_at=timezone.now(),
        )

        # Create breakout tick above range
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
        orders = asian_strategy.on_tick(tick_breakout)

        # Should generate close order
        assert len(orders) == 1
        order = orders[0]
        assert order.direction == "short"  # Opposite of position
        assert order.units == Decimal("1000")
        assert order.instrument == "EUR_USD"

        # Range should be reset after breakout
        assert range_detector.range_established is False

    def test_strategy_on_tick_processing(self, asian_strategy, mock_oanda_account):
        """Test complete strategy on_tick processing flow."""
        # Test 1: During Asian session - establish a range
        dt1 = datetime(2025, 1, 15, 2, 0, 0, tzinfo=dt_timezone.utc)
        tick1 = TickData.objects.create(
            account=mock_oanda_account,
            instrument="EUR_USD",
            timestamp=dt1,
            bid=Decimal("1.0995"),
            ask=Decimal("1.1005"),
            mid=Decimal("1.1000"),
        )
        orders1 = asian_strategy.on_tick(tick1)
        assert len(orders1) == 0  # No orders during range establishment

        # Add more ticks to establish range
        dt2 = datetime(2025, 1, 15, 4, 0, 0, tzinfo=dt_timezone.utc)
        tick2 = TickData.objects.create(
            account=mock_oanda_account,
            instrument="EUR_USD",
            timestamp=dt2,
            bid=Decimal("1.1045"),
            ask=Decimal("1.1055"),
            mid=Decimal("1.1050"),
        )
        asian_strategy.on_tick(tick2)

        dt3 = datetime(2025, 1, 15, 6, 0, 0, tzinfo=dt_timezone.utc)
        tick3 = TickData.objects.create(
            account=mock_oanda_account,
            instrument="EUR_USD",
            timestamp=dt3,
            bid=Decimal("1.0975"),
            ask=Decimal("1.0985"),
            mid=Decimal("1.0980"),
        )
        asian_strategy.on_tick(tick3)

        # Test 2: After range established, price in middle
        dt4 = datetime(2025, 1, 15, 10, 0, 0, tzinfo=dt_timezone.utc)
        tick4 = TickData.objects.create(
            account=mock_oanda_account,
            instrument="EUR_USD",
            timestamp=dt4,
            bid=Decimal("1.1020"),
            ask=Decimal("1.1030"),
            mid=Decimal("1.1025"),
        )
        orders4 = asian_strategy.on_tick(tick4)
        assert len(orders4) == 0  # No orders, price in middle of range

        # Test 3: Price near support
        dt5 = datetime(2025, 1, 15, 11, 0, 0, tzinfo=dt_timezone.utc)
        tick5 = TickData.objects.create(
            account=mock_oanda_account,
            instrument="EUR_USD",
            timestamp=dt5,
            bid=Decimal("1.0975"),
            ask=Decimal("1.0985"),
            mid=Decimal("1.0980"),
        )
        orders5 = asian_strategy.on_tick(tick5)
        assert len(orders5) == 1  # Entry order generated
        assert orders5[0].direction == "long"

    def test_min_range_size_filter(self, asian_strategy, mock_oanda_account):
        """Test that strategy doesn't trade if range is too small."""
        # Set up small range (less than min_range_pips)
        dt_range = datetime(2025, 1, 15, 4, 0, 0, tzinfo=dt_timezone.utc)
        range_detector = asian_strategy.range_detectors["EUR_USD"]
        range_detector.update_range(Decimal("1.1000"), dt_range)
        range_detector.update_range(Decimal("1.1010"), dt_range)  # Only 10 pips

        # Create tick near support
        dt_support = datetime(2025, 1, 15, 10, 0, 0, tzinfo=dt_timezone.utc)
        tick_support = TickData.objects.create(
            account=mock_oanda_account,
            instrument="EUR_USD",
            timestamp=dt_support,
            bid=Decimal("1.0995"),
            ask=Decimal("1.1005"),
            mid=Decimal("1.1000"),
        )

        # Process tick
        orders = asian_strategy.on_tick(tick_support)

        # Should not generate orders (range too small)
        assert len(orders) == 0

    def test_validate_config_valid(self, asian_strategy):
        """Test configuration validation with valid config."""
        valid_config = {
            "base_units": 1000,
            "support_tolerance_pips": 5,
            "resistance_tolerance_pips": 5,
            "stop_loss_pips": 15,
            "take_profit_pips": 30,
            "min_range_pips": 15,
        }

        result = asian_strategy.validate_config(valid_config)
        assert result is True

    def test_validate_config_invalid_base_units(self, asian_strategy):
        """Test configuration validation with invalid base units."""
        invalid_config = {
            "base_units": -1000,
            "support_tolerance_pips": 5,
            "resistance_tolerance_pips": 5,
            "stop_loss_pips": 15,
            "take_profit_pips": 30,
            "min_range_pips": 15,
        }

        with pytest.raises(ValueError, match="base_units must be positive"):
            asian_strategy.validate_config(invalid_config)

    def test_validate_config_invalid_support_tolerance(self, asian_strategy):
        """Test configuration validation with invalid support tolerance."""
        invalid_config = {
            "base_units": 1000,
            "support_tolerance_pips": 0,
            "resistance_tolerance_pips": 5,
            "stop_loss_pips": 15,
            "take_profit_pips": 30,
            "min_range_pips": 15,
        }

        with pytest.raises(ValueError, match="support_tolerance_pips must be positive"):
            asian_strategy.validate_config(invalid_config)

    def test_validate_config_invalid_resistance_tolerance(self, asian_strategy):
        """Test configuration validation with invalid resistance tolerance."""
        invalid_config = {
            "base_units": 1000,
            "support_tolerance_pips": 5,
            "resistance_tolerance_pips": -5,
            "stop_loss_pips": 15,
            "take_profit_pips": 30,
            "min_range_pips": 15,
        }

        with pytest.raises(ValueError, match="resistance_tolerance_pips must be positive"):
            asian_strategy.validate_config(invalid_config)

    def test_validate_config_invalid_stop_loss(self, asian_strategy):
        """Test configuration validation with invalid stop loss."""
        invalid_config = {
            "base_units": 1000,
            "support_tolerance_pips": 5,
            "resistance_tolerance_pips": 5,
            "stop_loss_pips": 0,
            "take_profit_pips": 30,
            "min_range_pips": 15,
        }

        with pytest.raises(ValueError, match="stop_loss_pips must be positive"):
            asian_strategy.validate_config(invalid_config)

    def test_validate_config_invalid_take_profit(self, asian_strategy):
        """Test configuration validation with invalid take profit."""
        invalid_config = {
            "base_units": 1000,
            "support_tolerance_pips": 5,
            "resistance_tolerance_pips": 5,
            "stop_loss_pips": 15,
            "take_profit_pips": -30,
            "min_range_pips": 15,
        }

        with pytest.raises(ValueError, match="take_profit_pips must be positive"):
            asian_strategy.validate_config(invalid_config)

    def test_validate_config_invalid_min_range(self, asian_strategy):
        """Test configuration validation with invalid min range."""
        invalid_config = {
            "base_units": 1000,
            "support_tolerance_pips": 5,
            "resistance_tolerance_pips": 5,
            "stop_loss_pips": 15,
            "take_profit_pips": 30,
            "min_range_pips": 0,
        }

        with pytest.raises(ValueError, match="min_range_pips must be positive"):
            asian_strategy.validate_config(invalid_config)
