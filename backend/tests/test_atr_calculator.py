"""
Unit tests for ATR (Average True Range) Calculator.

This module tests:
- 14-period ATR calculation with sample data
- Normal ATR baseline storage
- ATR calculation with insufficient data

Requirements: 10.1, 10.4
"""

from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone

import pytest

from accounts.models import OandaAccount
from trading.atr_calculator import ATRCalculator, Candle
from trading.models import Strategy, StrategyState

User = get_user_model()


@pytest.fixture
def user(db):  # pylint: disable=unused-argument
    """Create a test user."""
    return User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123",
    )


@pytest.fixture
def oanda_account(user):
    """Create a test OANDA account."""
    return OandaAccount.objects.create(
        user=user,
        account_id="001-001-1234567-001",
        api_token="test_token_12345",
        api_type="practice",
        balance=Decimal("10000.00"),
    )


@pytest.fixture
def strategy(oanda_account):
    """Create a test strategy."""
    return Strategy.objects.create(
        account=oanda_account,
        strategy_type="floor",
        config={"lot_size": 1000},
        instrument="EUR_USD",
    )


@pytest.fixture
def strategy_state(strategy):
    """Create a test strategy state."""
    return StrategyState.objects.create(
        strategy=strategy,
        current_layer=1,
        layer_states={},
        atr_values={},
    )


@pytest.fixture
def sample_candles():
    """
    Create sample candle data for testing.

    This creates 20 candles with realistic price movements
    to test ATR calculation.
    """
    base_time = timezone.now() - timedelta(hours=20)
    candles = []

    # Starting price
    price = Decimal("1.1000")

    for i in range(20):
        # Simulate price movement
        open_price = price
        high_price = price + Decimal("0.0010")
        low_price = price - Decimal("0.0008")
        close_price = price + Decimal("0.0002")

        candle = Candle(
            time=base_time + timedelta(hours=i),
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=1000,
        )
        candles.append(candle)

        # Update price for next candle
        price = close_price

    return candles


@pytest.mark.django_db
class TestATRCalculator:
    """Test suite for ATRCalculator class."""

    def test_initialization(self):
        """Test ATRCalculator initialization with default period."""
        calculator = ATRCalculator()
        assert calculator.period == 14

    def test_initialization_custom_period(self):
        """Test ATRCalculator initialization with custom period."""
        calculator = ATRCalculator(period=20)
        assert calculator.period == 20

    def test_calculate_true_range_without_previous(self):
        """Test True Range calculation without previous candle."""
        calculator = ATRCalculator()

        candle = Candle(
            time=timezone.now(),
            open=Decimal("1.1000"),
            high=Decimal("1.1020"),
            low=Decimal("1.0980"),
            close=Decimal("1.1010"),
            volume=1000,
        )

        true_range = calculator.calculate_true_range(candle)

        # True Range should be High - Low
        expected = Decimal("1.1020") - Decimal("1.0980")
        assert true_range == expected
        assert true_range == Decimal("0.0040")

    def test_calculate_true_range_with_previous(self):
        """Test True Range calculation with previous candle."""
        calculator = ATRCalculator()

        previous_candle = Candle(
            time=timezone.now() - timedelta(hours=1),
            open=Decimal("1.0990"),
            high=Decimal("1.1010"),
            low=Decimal("1.0970"),
            close=Decimal("1.1000"),
            volume=1000,
        )

        current_candle = Candle(
            time=timezone.now(),
            open=Decimal("1.1005"),
            high=Decimal("1.1025"),
            low=Decimal("1.0985"),
            close=Decimal("1.1015"),
            volume=1000,
        )

        true_range = calculator.calculate_true_range(current_candle, previous_candle)

        # True Range should be max of:
        # - High - Low = 1.1025 - 1.0985 = 0.0040
        # - abs(High - Prev Close) = abs(1.1025 - 1.1000) = 0.0025
        # - abs(Low - Prev Close) = abs(1.0985 - 1.1000) = 0.0015
        expected = Decimal("0.0040")
        assert true_range == expected

    def test_calculate_true_range_gap_up(self):
        """Test True Range calculation with gap up."""
        calculator = ATRCalculator()

        previous_candle = Candle(
            time=timezone.now() - timedelta(hours=1),
            open=Decimal("1.0990"),
            high=Decimal("1.1000"),
            low=Decimal("1.0980"),
            close=Decimal("1.0995"),
            volume=1000,
        )

        # Gap up: opens above previous close
        current_candle = Candle(
            time=timezone.now(),
            open=Decimal("1.1050"),
            high=Decimal("1.1060"),
            low=Decimal("1.1040"),
            close=Decimal("1.1055"),
            volume=1000,
        )

        true_range = calculator.calculate_true_range(current_candle, previous_candle)

        # True Range should be max of:
        # - High - Low = 1.1060 - 1.1040 = 0.0020
        # - abs(High - Prev Close) = abs(1.1060 - 1.0995) = 0.0065
        # - abs(Low - Prev Close) = abs(1.1040 - 1.0995) = 0.0045
        expected = Decimal("0.0065")
        assert true_range == expected

    def test_calculate_atr_with_sufficient_data(self, sample_candles):
        """Test ATR calculation with sufficient candle data."""
        calculator = ATRCalculator(period=14)

        atr = calculator.calculate_atr(sample_candles)

        assert atr is not None
        assert isinstance(atr, Decimal)
        assert atr > Decimal("0")

        # ATR should be reasonable for the sample data
        # With our sample data, ATR should be around 0.0018
        assert Decimal("0.0010") < atr < Decimal("0.0030")

    def test_calculate_atr_with_insufficient_data(self):
        """Test ATR calculation with insufficient candle data."""
        calculator = ATRCalculator(period=14)

        # Create only 10 candles (need 15 for 14-period ATR)
        base_time = timezone.now()
        candles = []
        for i in range(10):
            candle = Candle(
                time=base_time + timedelta(hours=i),
                open=Decimal("1.1000"),
                high=Decimal("1.1010"),
                low=Decimal("1.0990"),
                close=Decimal("1.1005"),
                volume=1000,
            )
            candles.append(candle)

        atr = calculator.calculate_atr(candles)

        # Should return None due to insufficient data
        assert atr is None

    def test_calculate_atr_exact_minimum_data(self):
        """Test ATR calculation with exact minimum candles (period + 1)."""
        calculator = ATRCalculator(period=14)

        # Create exactly 15 candles (14 + 1)
        base_time = timezone.now()
        candles = []
        price = Decimal("1.1000")

        for i in range(15):
            candle = Candle(
                time=base_time + timedelta(hours=i),
                open=price,
                high=price + Decimal("0.0010"),
                low=price - Decimal("0.0010"),
                close=price + Decimal("0.0002"),
                volume=1000,
            )
            candles.append(candle)
            price = candle.close

        atr = calculator.calculate_atr(candles)

        assert atr is not None
        assert isinstance(atr, Decimal)
        assert atr > Decimal("0")

    def test_calculate_atr_with_varying_volatility(self):
        """Test ATR calculation with varying volatility."""
        calculator = ATRCalculator(period=14)

        base_time = timezone.now()
        candles = []
        price = Decimal("1.1000")

        # First 10 candles: low volatility
        for i in range(10):
            candle = Candle(
                time=base_time + timedelta(hours=i),
                open=price,
                high=price + Decimal("0.0005"),
                low=price - Decimal("0.0005"),
                close=price + Decimal("0.0001"),
                volume=1000,
            )
            candles.append(candle)
            price = candle.close

        # Next 10 candles: high volatility
        for i in range(10, 20):
            candle = Candle(
                time=base_time + timedelta(hours=i),
                open=price,
                high=price + Decimal("0.0030"),
                low=price - Decimal("0.0030"),
                close=price + Decimal("0.0005"),
                volume=1000,
            )
            candles.append(candle)
            price = candle.close

        atr = calculator.calculate_atr(candles)

        assert atr is not None
        # ATR should reflect the higher volatility in recent candles
        assert atr > Decimal("0.0020")

    def test_parse_timestamp(self):
        """Test timestamp parsing from OANDA format."""
        calculator = ATRCalculator()

        # Test RFC3339 format with Z
        time_str = "2024-01-15T10:30:45.123456789Z"
        dt = calculator._parse_timestamp(time_str)  # pylint: disable=protected-access

        assert isinstance(dt, datetime)
        assert dt.tzinfo is not None  # Should be timezone-aware
        assert dt.year == 2024
        assert dt.month == 1
        assert dt.day == 15
        assert dt.hour == 10
        assert dt.minute == 30
        assert dt.second == 45

    def test_parse_timestamp_with_timezone(self):
        """Test timestamp parsing with explicit timezone."""
        calculator = ATRCalculator()

        # Test with explicit timezone offset
        time_str = "2024-01-15T10:30:45+00:00"
        dt = calculator._parse_timestamp(time_str)  # pylint: disable=protected-access

        assert isinstance(dt, datetime)
        assert dt.tzinfo is not None
        assert dt.year == 2024

    def test_parse_timestamp_invalid(self):
        """Test timestamp parsing with invalid format."""
        calculator = ATRCalculator()

        # Test with invalid format (should fallback to current time)
        time_str = "invalid-timestamp"
        dt = calculator._parse_timestamp(time_str)  # pylint: disable=protected-access

        assert isinstance(dt, datetime)
        assert dt.tzinfo is not None
        # Should be close to current time (within 1 second)
        assert abs((timezone.now() - dt).total_seconds()) < 1

    def test_strategy_state_update_atr(self, strategy_state):
        """Test updating ATR value in StrategyState."""
        atr_value = Decimal("0.0025")
        instrument = "EUR_USD"

        strategy_state.update_atr(instrument, atr_value)

        # Refresh from database
        strategy_state.refresh_from_db()

        assert instrument in strategy_state.atr_values
        assert Decimal(strategy_state.atr_values[instrument]) == atr_value

    def test_strategy_state_update_instrument(self, strategy_state):
        """Test updating ATR values for single instrument."""
        instrument_atr = {
            "EUR_USD": Decimal("0.0025"),
            "GBP_USD": Decimal("0.0030"),
            "USD_JPY": Decimal("0.0020"),
        }

        for instrument, atr_value in instrument_atr.items():
            strategy_state.update_atr(instrument, atr_value)

        # Refresh from database
        strategy_state.refresh_from_db()

        for instrument, expected_atr in instrument_atr.items():
            assert instrument in strategy_state.atr_values
            assert Decimal(strategy_state.atr_values[instrument]) == expected_atr

    def test_strategy_state_normal_atr_storage(self, strategy_state):
        """Test storing normal ATR baseline in StrategyState."""
        normal_atr = Decimal("0.0022")

        strategy_state.normal_atr = normal_atr
        strategy_state.save()

        # Refresh from database
        strategy_state.refresh_from_db()

        assert strategy_state.normal_atr == normal_atr

    def test_strategy_state_normal_atr_null(self, strategy_state):
        """Test that normal_atr can be null."""
        assert strategy_state.normal_atr is None

        # Set and then clear
        strategy_state.normal_atr = Decimal("0.0022")
        strategy_state.save()

        strategy_state.normal_atr = None
        strategy_state.save()

        strategy_state.refresh_from_db()
        assert strategy_state.normal_atr is None

    def test_atr_calculation_precision(self, sample_candles):
        """Test that ATR calculation maintains decimal precision."""
        calculator = ATRCalculator(period=14)

        atr = calculator.calculate_atr(sample_candles)

        assert atr is not None
        # Check that we have at least 4 decimal places
        # (Decimal precision may vary based on calculation)
        atr_str = str(atr)
        if "." in atr_str:
            decimal_places = len(atr_str.split(".")[1])
            assert decimal_places >= 4

    def test_true_range_with_zero_volatility(self):
        """Test True Range calculation with zero volatility (flat price)."""
        calculator = ATRCalculator()

        previous_candle = Candle(
            time=timezone.now() - timedelta(hours=1),
            open=Decimal("1.1000"),
            high=Decimal("1.1000"),
            low=Decimal("1.1000"),
            close=Decimal("1.1000"),
            volume=1000,
        )

        current_candle = Candle(
            time=timezone.now(),
            open=Decimal("1.1000"),
            high=Decimal("1.1000"),
            low=Decimal("1.1000"),
            close=Decimal("1.1000"),
            volume=1000,
        )

        true_range = calculator.calculate_true_range(current_candle, previous_candle)

        # True Range should be zero
        assert true_range == Decimal("0")

    def test_atr_with_zero_volatility_candles(self):
        """Test ATR calculation with zero volatility candles."""
        calculator = ATRCalculator(period=14)

        base_time = timezone.now()
        candles = []

        # Create 20 candles with no price movement
        for i in range(20):
            candle = Candle(
                time=base_time + timedelta(hours=i),
                open=Decimal("1.1000"),
                high=Decimal("1.1000"),
                low=Decimal("1.1000"),
                close=Decimal("1.1000"),
                volume=1000,
            )
            candles.append(candle)

        atr = calculator.calculate_atr(candles)

        assert atr is not None
        # ATR should be zero with no volatility
        assert atr == Decimal("0")
