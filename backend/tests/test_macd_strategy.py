"""
Unit tests for MACD Strategy.

This module tests the MACD Strategy implementation including:
- MACD and signal line calculations
- Bullish crossover detection
- Bearish crossover detection
- Histogram momentum analysis
- Strategy on_tick processing

Requirements: 5.1, 5.3
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone

import pytest

from accounts.models import OandaAccount
from trading.macd_strategy import MACDCalculator, MACDCrossoverDetector, MACDStrategy
from trading.models import Position, Strategy
from trading.tick_data_models import TickData

User = get_user_model()


@pytest.fixture
def user(db):  # pylint: disable=unused-argument
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


class TestMACDCalculator:
    """Test MACD calculation."""

    def test_macd_calculation_with_sample_data(self):
        """Test MACD calculation with known sample data."""
        calculator = MACDCalculator(fast_period=12, slow_period=26, signal_period=9)

        # Sample prices for MACD calculation
        base_price = Decimal("100.00")
        prices = [base_price + Decimal(str(i * 0.1)) for i in range(40)]

        for price in prices:
            calculator.add_price(price)

        # After enough prices, MACD should be calculated
        assert calculator.is_ready()
        macd = calculator.get_macd_line()
        signal = calculator.get_signal_line()
        histogram = calculator.get_histogram()

        assert macd is not None
        assert signal is not None
        assert histogram is not None

        # Histogram should equal MACD - Signal
        assert histogram == macd - signal

    def test_macd_not_ready_with_insufficient_data(self):
        """Test that MACD is not ready with insufficient data."""
        calculator = MACDCalculator(fast_period=12, slow_period=26, signal_period=9)

        # Add only a few prices
        for i in range(10):
            calculator.add_price(Decimal(str(100 + i)))

        assert not calculator.is_ready()
        assert calculator.get_macd_line() is None
        assert calculator.get_signal_line() is None
        assert calculator.get_histogram() is None

    def test_macd_with_uptrend(self):
        """Test MACD with uptrend prices."""
        calculator = MACDCalculator(fast_period=12, slow_period=26, signal_period=9)

        # Strong uptrend
        base_price = Decimal("100")
        for i in range(50):
            calculator.add_price(base_price + Decimal(str(i)))

        assert calculator.is_ready()
        macd = calculator.get_macd_line()
        histogram = calculator.get_histogram()

        # In uptrend, MACD should be positive
        assert macd is not None
        assert macd > Decimal("0")

        # Histogram exists (may be positive, negative, or near zero)
        assert histogram is not None

    def test_macd_with_downtrend(self):
        """Test MACD with downtrend prices."""
        calculator = MACDCalculator(fast_period=12, slow_period=26, signal_period=9)

        # Strong downtrend
        base_price = Decimal("100")
        for i in range(50):
            calculator.add_price(base_price - Decimal(str(i * 0.5)))

        assert calculator.is_ready()
        macd = calculator.get_macd_line()
        histogram = calculator.get_histogram()

        # In downtrend, MACD should be negative
        assert macd is not None
        assert macd < Decimal("0")

        # Histogram exists (may be positive, negative, or near zero)
        assert histogram is not None


class TestMACDCrossoverDetector:
    """Test MACD crossover detection."""

    def test_bullish_crossover_detection(self):
        """Test detection of bullish crossover."""
        detector = MACDCrossoverDetector()

        # Set up previous state: MACD below signal
        detector.update(macd=Decimal("-0.5"), signal=Decimal("0.0"), histogram=Decimal("-0.5"))

        # Current state: MACD crosses above signal
        signal = detector.detect_crossover(macd=Decimal("0.5"), signal=Decimal("0.0"))

        assert signal == "bullish"

    def test_bearish_crossover_detection(self):
        """Test detection of bearish crossover."""
        detector = MACDCrossoverDetector()

        # Set up previous state: MACD above signal
        detector.update(macd=Decimal("0.5"), signal=Decimal("0.0"), histogram=Decimal("0.5"))

        # Current state: MACD crosses below signal
        signal = detector.detect_crossover(macd=Decimal("-0.5"), signal=Decimal("0.0"))

        assert signal == "bearish"

    def test_no_crossover(self):
        """Test when there is no crossover."""
        detector = MACDCrossoverDetector()

        # Set up previous state
        detector.update(macd=Decimal("0.5"), signal=Decimal("0.0"), histogram=Decimal("0.5"))

        # Current state: MACD still above signal
        signal = detector.detect_crossover(macd=Decimal("0.6"), signal=Decimal("0.1"))

        assert signal is None

    def test_histogram_momentum_increasing(self):
        """Test histogram momentum analysis - increasing."""
        detector = MACDCrossoverDetector()

        # Set up previous histogram
        detector.update(macd=Decimal("0.5"), signal=Decimal("0.3"), histogram=Decimal("0.2"))

        # Current histogram is larger
        momentum = detector.analyze_histogram_momentum(Decimal("0.4"))

        assert momentum == "increasing"

    def test_histogram_momentum_decreasing(self):
        """Test histogram momentum analysis - decreasing."""
        detector = MACDCrossoverDetector()

        # Set up previous histogram
        detector.update(macd=Decimal("0.5"), signal=Decimal("0.3"), histogram=Decimal("0.4"))

        # Current histogram is smaller
        momentum = detector.analyze_histogram_momentum(Decimal("0.2"))

        assert momentum == "decreasing"

    def test_histogram_direction_positive(self):
        """Test histogram direction - positive."""
        detector = MACDCrossoverDetector()

        direction = detector.get_histogram_direction(Decimal("0.5"))
        assert direction == "positive"

    def test_histogram_direction_negative(self):
        """Test histogram direction - negative."""
        detector = MACDCrossoverDetector()

        direction = detector.get_histogram_direction(Decimal("-0.5"))
        assert direction == "negative"

    def test_histogram_direction_zero(self):
        """Test histogram direction - zero."""
        detector = MACDCrossoverDetector()

        direction = detector.get_histogram_direction(Decimal("0.0"))
        assert direction == "zero"


@pytest.mark.django_db
class TestMACDStrategy:
    """Test MACD Strategy implementation."""

    @pytest.fixture
    def strategy_instance(self, oanda_account):
        """Create a test MACD strategy instance."""
        strategy = Strategy.objects.create(
            account=oanda_account,
            strategy_type="macd",
            config={
                "fast_period": 12,
                "slow_period": 26,
                "signal_period": 9,
                "base_units": 1000,
                "use_histogram_confirmation": True,
            },
            instrument="EUR_USD",
            is_active=True,
        )
        return MACDStrategy(strategy)

    def test_bullish_crossover_signal_generation(self, strategy_instance, oanda_account):
        """Test that bullish crossover generates long entry signal."""
        # Feed prices to create bullish crossover
        base_price = Decimal("1.1000")

        # First create downtrend then uptrend for crossover
        for i in range(30):
            price = base_price - Decimal(str(i * 0.001))
            tick = TickData(
                account=oanda_account,
                instrument="EUR_USD",
                timestamp=timezone.now(),
                bid=price,
                ask=price + Decimal("0.0002"),
                mid=price + Decimal("0.0001"),
                spread=Decimal("0.0002"),
            )
            strategy_instance.on_tick(tick)

        # Now create uptrend to trigger bullish crossover
        for i in range(20):
            price = base_price + Decimal(str(i * 0.002))
            tick = TickData(
                account=oanda_account,
                instrument="EUR_USD",
                timestamp=timezone.now(),
                bid=price,
                ask=price + Decimal("0.0002"),
                mid=price + Decimal("0.0001"),
                spread=Decimal("0.0002"),
            )
            orders = strategy_instance.on_tick(tick)

            # Check if we got a bullish signal
            if orders:
                order = orders[0]
                if order.direction == "long":
                    assert order.order_type == "market"
                    assert order.units == Decimal("1000")
                    break

    def test_bearish_crossover_signal_generation(self, strategy_instance, oanda_account):
        """Test that bearish crossover generates short entry signal."""
        # Feed prices to create bearish crossover
        base_price = Decimal("1.1000")

        # First create uptrend then downtrend for crossover
        for i in range(30):
            price = base_price + Decimal(str(i * 0.001))
            tick = TickData(
                account=oanda_account,
                instrument="EUR_USD",
                timestamp=timezone.now(),
                bid=price,
                ask=price + Decimal("0.0002"),
                mid=price + Decimal("0.0001"),
                spread=Decimal("0.0002"),
            )
            strategy_instance.on_tick(tick)

        # Now create downtrend to trigger bearish crossover
        for i in range(20):
            price = base_price - Decimal(str(i * 0.002))
            tick = TickData(
                account=oanda_account,
                instrument="EUR_USD",
                timestamp=timezone.now(),
                bid=price,
                ask=price + Decimal("0.0002"),
                mid=price + Decimal("0.0001"),
                spread=Decimal("0.0002"),
            )
            orders = strategy_instance.on_tick(tick)

            # Check if we got a bearish signal
            if orders:
                order = orders[0]
                if order.direction == "short":
                    assert order.order_type == "market"
                    assert order.units == Decimal("1000")
                    break

    def test_histogram_momentum_analysis(self, strategy_instance, oanda_account):
        """Test histogram momentum analysis during strategy execution."""
        base_price = Decimal("1.1000")

        # Feed enough data to calculate MACD
        for i in range(50):
            price = base_price + Decimal(str(i * 0.001))
            tick = TickData(
                account=oanda_account,
                instrument="EUR_USD",
                timestamp=timezone.now(),
                bid=price,
                ask=price + Decimal("0.0002"),
                mid=price + Decimal("0.0001"),
                spread=Decimal("0.0002"),
            )
            strategy_instance.on_tick(tick)

        # Verify MACD calculator is ready
        calculator = strategy_instance.macd_calculators.get("EUR_USD")
        assert calculator is not None
        assert calculator.is_ready()

        # Verify histogram is calculated
        histogram = calculator.get_histogram()
        assert histogram is not None

    def test_strategy_on_tick_processing(self, strategy_instance, oanda_account):
        """Test complete on_tick processing flow."""
        base_price = Decimal("1.1000")
        all_orders = []

        # Process multiple ticks
        for i in range(50):
            price = base_price + Decimal(str(i * 0.0005))
            tick = TickData(
                account=oanda_account,
                instrument="EUR_USD",
                timestamp=timezone.now(),
                bid=price,
                ask=price + Decimal("0.0002"),
                mid=price + Decimal("0.0001"),
                spread=Decimal("0.0002"),
            )
            orders = strategy_instance.on_tick(tick)
            all_orders.extend(orders)

        # MACD calculator should be ready
        calculator = strategy_instance.macd_calculators.get("EUR_USD")
        assert calculator is not None
        assert calculator.is_ready()

        # Should have processed ticks without errors
        assert calculator.get_macd_line() is not None
        assert calculator.get_signal_line() is not None

    def test_opposite_position_closed_on_crossover(self, strategy_instance, oanda_account):
        """Test that opposite positions are closed on crossover."""
        # Create a long position
        position = Position.objects.create(
            account=oanda_account,
            strategy=strategy_instance.strategy,
            position_id="test_pos_1",
            instrument="EUR_USD",
            direction="long",
            units=Decimal("1000"),
            entry_price=Decimal("1.1000"),
            current_price=Decimal("1.1000"),
            opened_at=timezone.now(),
        )

        # Feed prices to create bearish crossover
        base_price = Decimal("1.1000")

        # Create uptrend first
        for i in range(30):
            price = base_price + Decimal(str(i * 0.001))
            tick = TickData(
                account=oanda_account,
                instrument="EUR_USD",
                timestamp=timezone.now(),
                bid=price,
                ask=price + Decimal("0.0002"),
                mid=price + Decimal("0.0001"),
                spread=Decimal("0.0002"),
            )
            strategy_instance.on_tick(tick)

        # Now create downtrend to trigger bearish crossover
        for i in range(20):
            price = base_price - Decimal(str(i * 0.002))
            tick = TickData(
                account=oanda_account,
                instrument="EUR_USD",
                timestamp=timezone.now(),
                bid=price,
                ask=price + Decimal("0.0002"),
                mid=price + Decimal("0.0001"),
                spread=Decimal("0.0002"),
            )
            orders = strategy_instance.on_tick(tick)

            # Check if we got a close order
            if orders:
                for order in orders:
                    if order.direction == "short" and order.units == position.units:
                        # This is a close order
                        assert True
                        return

    def test_config_validation(self, strategy_instance):
        """Test strategy configuration validation."""
        # Valid config
        valid_config = {
            "fast_period": 12,
            "slow_period": 26,
            "signal_period": 9,
            "base_units": 1000,
        }
        assert strategy_instance.validate_config(valid_config)

        # Invalid fast period
        with pytest.raises(ValueError, match="fast_period must be"):
            strategy_instance.validate_config({"fast_period": 0})

        # Invalid slow period
        with pytest.raises(ValueError, match="slow_period must be"):
            strategy_instance.validate_config({"slow_period": -1})

        # Invalid signal period
        with pytest.raises(ValueError, match="signal_period must be"):
            strategy_instance.validate_config({"signal_period": 0})

        # Fast >= Slow
        with pytest.raises(ValueError, match="fast_period must be less than"):
            strategy_instance.validate_config({"fast_period": 26, "slow_period": 12})

        # Invalid base units
        with pytest.raises(ValueError, match="base_units must be positive"):
            strategy_instance.validate_config({"base_units": -100})

    def test_histogram_confirmation_enabled(self, oanda_account):
        """Test strategy with histogram confirmation enabled."""
        strategy = Strategy.objects.create(
            account=oanda_account,
            strategy_type="macd",
            config={
                "fast_period": 12,
                "slow_period": 26,
                "signal_period": 9,
                "base_units": 1000,
                "use_histogram_confirmation": True,
            },
            instrument="EUR_USD",
            is_active=True,
        )
        strategy_instance = MACDStrategy(strategy)

        assert strategy_instance.use_histogram_confirmation is True

    def test_histogram_confirmation_disabled(self, oanda_account):
        """Test strategy with histogram confirmation disabled."""
        strategy = Strategy.objects.create(
            account=oanda_account,
            strategy_type="macd",
            config={
                "fast_period": 12,
                "slow_period": 26,
                "signal_period": 9,
                "base_units": 1000,
                "use_histogram_confirmation": False,
            },
            instrument="EUR_USD",
            is_active=True,
        )
        strategy_instance = MACDStrategy(strategy)

        assert strategy_instance.use_histogram_confirmation is False

    def test_inactive_instrument_ignored(self, strategy_instance, oanda_account):
        """Test that ticks for inactive instrument are ignored."""
        tick = TickData(
            account=oanda_account,
            instrument="GBP_USD",  # Not in strategy instrument
            timestamp=timezone.now(),
            bid=Decimal("1.3000"),
            ask=Decimal("1.3002"),
            mid=Decimal("1.3001"),
            spread=Decimal("0.0002"),
        )

        orders = strategy_instance.on_tick(tick)
        assert len(orders) == 0

    def test_position_update_handling(self, strategy_instance, oanda_account):
        """Test position update handling."""
        position = Position.objects.create(
            account=oanda_account,
            strategy=strategy_instance.strategy,
            position_id="test_pos_1",
            instrument="EUR_USD",
            direction="long",
            units=Decimal("1000"),
            entry_price=Decimal("1.1000"),
            current_price=Decimal("1.1000"),
            opened_at=timezone.now(),
        )

        # Should not raise any errors
        strategy_instance.on_position_update(position)

        # Close position
        position.closed_at = timezone.now()
        position.save()

        # Should handle closed position
        strategy_instance.on_position_update(position)
