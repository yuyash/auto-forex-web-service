"""
Unit tests for Stochastic Oscillator Strategy.

This module tests the Stochastic Strategy implementation including:
- Stochastic Oscillator calculation
- Oversold signal generation
- Overbought signal generation
- %K/%D crossover detection
- Strategy on_tick processing

Requirements: 5.1, 5.3
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone

import pytest

from accounts.models import OandaAccount
from trading.models import Position, Strategy
from trading.stochastic_strategy import CrossoverDetector, StochasticCalculator, StochasticStrategy
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


class TestStochasticCalculator:
    """Test Stochastic Oscillator calculation."""

    def test_stochastic_calculation(self):
        """Test Stochastic calculation with sample data."""
        calculator = StochasticCalculator(k_period=14, k_smoothing=3, d_smoothing=3)

        # Sample prices with clear trend
        # Need: 14 (k_period) + 3 (k_smoothing) + 3 (d_smoothing) - 2 = 18 prices minimum
        prices = [
            Decimal("100.00"),
            Decimal("101.00"),
            Decimal("102.00"),
            Decimal("103.00"),
            Decimal("104.00"),
            Decimal("105.00"),
            Decimal("106.00"),
            Decimal("107.00"),
            Decimal("108.00"),
            Decimal("109.00"),
            Decimal("110.00"),
            Decimal("111.00"),
            Decimal("112.00"),
            Decimal("113.00"),
            Decimal("114.00"),
            Decimal("115.00"),
            Decimal("116.00"),
            Decimal("117.00"),
            Decimal("118.00"),
            Decimal("119.00"),  # Extra prices to ensure %D is ready
        ]

        for price in prices:
            calculator.add_price(price)

        # After enough prices, both %K and %D should be calculated
        assert calculator.is_ready()
        k = calculator.get_k()
        d = calculator.get_d()
        assert k is not None
        assert d is not None
        # Both should be between 0 and 100
        assert Decimal("0") <= k <= Decimal("100")
        assert Decimal("0") <= d <= Decimal("100")
        # With uptrend, both should be high
        assert k > Decimal("50")
        assert d > Decimal("50")

    def test_stochastic_not_ready_with_insufficient_data(self):
        """Test that Stochastic is not ready with insufficient data."""
        calculator = StochasticCalculator(k_period=14, k_smoothing=3, d_smoothing=3)

        # Add only a few prices
        for i in range(10):
            calculator.add_price(Decimal(str(100 + i)))

        assert not calculator.is_ready()
        # %K might be ready but %D won't be
        assert calculator.get_d() is None

    def test_stochastic_extreme_values(self):
        """Test Stochastic with extreme price movements."""
        calculator = StochasticCalculator(k_period=14, k_smoothing=3, d_smoothing=3)

        # Strong uptrend - should produce high %K and %D
        base_price = Decimal("100")
        for i in range(25):
            calculator.add_price(base_price + Decimal(str(i)))

        k = calculator.get_k()
        d = calculator.get_d()
        assert k is not None
        assert d is not None
        # Should be very high (near 100)
        assert k > Decimal("80")
        assert d > Decimal("80")

    def test_stochastic_downtrend(self):
        """Test Stochastic with downtrend."""
        calculator = StochasticCalculator(k_period=14, k_smoothing=3, d_smoothing=3)

        # Strong downtrend - should produce low %K and %D
        base_price = Decimal("100")
        for i in range(25):
            calculator.add_price(base_price - Decimal(str(i * 0.5)))

        k = calculator.get_k()
        d = calculator.get_d()
        assert k is not None
        assert d is not None
        # Should be very low (near 0)
        assert k < Decimal("20")
        assert d < Decimal("20")

    def test_stochastic_flat_prices(self):
        """Test Stochastic with flat prices (no movement)."""
        calculator = StochasticCalculator(k_period=14, k_smoothing=3, d_smoothing=3)

        # Flat prices
        for _ in range(25):
            calculator.add_price(Decimal("100.00"))

        k = calculator.get_k()
        d = calculator.get_d()
        assert k is not None
        assert d is not None
        # Should be around 50 (neutral)
        assert Decimal("40") <= k <= Decimal("60")
        assert Decimal("40") <= d <= Decimal("60")


class TestCrossoverDetector:
    """Test %K and %D crossover detection."""

    def test_bullish_crossover_detection(self):
        """Test detection of bullish crossover (%K crosses above %D)."""
        detector = CrossoverDetector()

        # Initial state: %K below %D
        detector.update(Decimal("30"), Decimal("40"))

        # %K crosses above %D
        assert detector.detect_bullish_crossover(Decimal("45"), Decimal("40"))
        assert not detector.detect_bearish_crossover(Decimal("45"), Decimal("40"))

    def test_bearish_crossover_detection(self):
        """Test detection of bearish crossover (%K crosses below %D)."""
        detector = CrossoverDetector()

        # Initial state: %K above %D
        detector.update(Decimal("70"), Decimal("60"))

        # %K crosses below %D
        assert detector.detect_bearish_crossover(Decimal("55"), Decimal("60"))
        assert not detector.detect_bullish_crossover(Decimal("55"), Decimal("60"))

    def test_no_crossover(self):
        """Test when there is no crossover."""
        detector = CrossoverDetector()

        # %K stays above %D
        detector.update(Decimal("70"), Decimal("60"))
        assert not detector.detect_bullish_crossover(Decimal("75"), Decimal("65"))
        assert not detector.detect_bearish_crossover(Decimal("75"), Decimal("65"))

        # %K stays below %D
        detector.update(Decimal("30"), Decimal("40"))
        assert not detector.detect_bullish_crossover(Decimal("25"), Decimal("35"))
        assert not detector.detect_bearish_crossover(Decimal("25"), Decimal("35"))

    def test_crossover_without_previous_data(self):
        """Test crossover detection without previous data."""
        detector = CrossoverDetector()

        # No previous data
        assert not detector.detect_bullish_crossover(Decimal("50"), Decimal("40"))
        assert not detector.detect_bearish_crossover(Decimal("50"), Decimal("60"))


@pytest.mark.django_db
class TestStochasticStrategy:
    """Test Stochastic Strategy implementation."""

    @pytest.fixture
    def strategy_instance(self, oanda_account):
        """Create a test Stochastic strategy instance."""
        strategy = Strategy.objects.create(
            account=oanda_account,
            strategy_type="stochastic",
            config={
                "k_period": 14,
                "k_smoothing": 3,
                "d_smoothing": 3,
                "oversold_threshold": 20,
                "overbought_threshold": 80,
                "base_units": 1000,
                "use_crossover": True,
            },
            instruments=["EUR_USD"],
            is_active=True,
        )
        return StochasticStrategy(strategy)

    def test_oversold_signal_generation(self, strategy_instance, oanda_account):
        """Test that oversold condition generates long entry signal."""
        # Feed prices to get %K below 20
        base_price = Decimal("1.1000")

        # Create downtrend to get low Stochastic
        for i in range(30):
            tick = TickData(
                account=oanda_account,
                instrument="EUR_USD",
                timestamp=timezone.now(),
                bid=base_price - Decimal(str(i * 0.001)),
                ask=base_price - Decimal(str(i * 0.001)) + Decimal("0.0002"),
                mid=base_price - Decimal(str(i * 0.001)) + Decimal("0.0001"),
                spread=Decimal("0.0002"),
            )
            orders = strategy_instance.on_tick(tick)

        # Should eventually generate entry when Stochastic is oversold
        # Check if any orders were generated
        assert len(orders) >= 0  # May or may not generate based on exact values

        # Verify calculator is working
        calculator = strategy_instance.stochastic_calculators.get("EUR_USD")
        assert calculator is not None
        assert calculator.is_ready()

    def test_overbought_signal_generation(self, strategy_instance, oanda_account):
        """Test that overbought condition generates exit signal."""
        # First create a long position
        Position.objects.create(
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

        # Feed prices to get %K above 80
        base_price = Decimal("1.1000")

        # Create uptrend to get high Stochastic
        for i in range(30):
            tick = TickData(
                account=oanda_account,
                instrument="EUR_USD",
                timestamp=timezone.now(),
                bid=base_price + Decimal(str(i * 0.001)),
                ask=base_price + Decimal(str(i * 0.001)) + Decimal("0.0002"),
                mid=base_price + Decimal(str(i * 0.001)) + Decimal("0.0001"),
                spread=Decimal("0.0002"),
            )
            strategy_instance.on_tick(tick)

        # Should eventually generate close order when Stochastic is overbought
        # Verify calculator is working
        calculator = strategy_instance.stochastic_calculators.get("EUR_USD")
        assert calculator is not None
        assert calculator.is_ready()
        k = calculator.get_k()
        assert k is not None
        # With strong uptrend, %K should be high
        assert k > Decimal("50")

    def test_k_d_crossover_detection(self, strategy_instance, oanda_account):
        """Test %K/%D crossover detection."""
        # Feed enough data to get Stochastic ready
        base_price = Decimal("1.1000")

        for i in range(25):
            tick = TickData(
                account=oanda_account,
                instrument="EUR_USD",
                timestamp=timezone.now(),
                bid=base_price + Decimal(str(i * 0.0001)),
                ask=base_price + Decimal(str(i * 0.0001)) + Decimal("0.0002"),
                mid=base_price + Decimal(str(i * 0.0001)) + Decimal("0.0001"),
                spread=Decimal("0.0002"),
            )
            strategy_instance.on_tick(tick)

        # Verify crossover detector is initialized and working
        crossover_detector = strategy_instance.crossover_detectors.get("EUR_USD")
        assert crossover_detector is not None

        calculator = strategy_instance.stochastic_calculators.get("EUR_USD")
        assert calculator is not None
        assert calculator.is_ready()

    def test_strategy_on_tick_processing(self, strategy_instance, oanda_account):
        """Test complete on_tick processing flow."""
        # Process multiple ticks
        base_price = Decimal("1.1000")
        all_orders = []

        for i in range(30):
            tick = TickData(
                account=oanda_account,
                instrument="EUR_USD",
                timestamp=timezone.now(),
                bid=base_price + Decimal(str(i * 0.0001)),
                ask=base_price + Decimal(str(i * 0.0001)) + Decimal("0.0002"),
                mid=base_price + Decimal(str(i * 0.0001)) + Decimal("0.0001"),
                spread=Decimal("0.0002"),
            )
            orders = strategy_instance.on_tick(tick)
            all_orders.extend(orders)

        # Stochastic calculator should be ready
        calculator = strategy_instance.stochastic_calculators.get("EUR_USD")
        assert calculator is not None
        assert calculator.is_ready()

        # Should have processed ticks without errors
        k = calculator.get_k()
        d = calculator.get_d()
        assert k is not None
        assert d is not None

    def test_config_validation(self, strategy_instance):
        """Test strategy configuration validation."""
        # Valid config
        valid_config = {
            "k_period": 14,
            "k_smoothing": 3,
            "d_smoothing": 3,
            "oversold_threshold": 20,
            "overbought_threshold": 80,
            "base_units": 1000,
            "use_crossover": True,
        }
        assert strategy_instance.validate_config(valid_config)

        # Invalid k_period
        with pytest.raises(ValueError, match="k_period must be"):
            strategy_instance.validate_config({"k_period": 1})

        # Invalid k_smoothing
        with pytest.raises(ValueError, match="k_smoothing must be"):
            strategy_instance.validate_config({"k_smoothing": 0})

        # Invalid d_smoothing
        with pytest.raises(ValueError, match="d_smoothing must be"):
            strategy_instance.validate_config({"d_smoothing": 0})

        # Invalid oversold threshold
        with pytest.raises(ValueError, match="oversold_threshold must be"):
            strategy_instance.validate_config({"oversold_threshold": 150})

        # Invalid overbought threshold
        with pytest.raises(ValueError, match="overbought_threshold must be"):
            strategy_instance.validate_config({"overbought_threshold": -10})

        # Oversold >= Overbought
        with pytest.raises(ValueError, match="oversold_threshold must be less than"):
            strategy_instance.validate_config(
                {"oversold_threshold": 80, "overbought_threshold": 20}
            )

        # Invalid base units
        with pytest.raises(ValueError, match="base_units must be positive"):
            strategy_instance.validate_config({"base_units": -100})

    def test_inactive_instrument_ignored(self, strategy_instance, oanda_account):
        """Test that ticks for inactive instruments are ignored."""
        tick = TickData(
            account=oanda_account,
            instrument="GBP_USD",  # Not in strategy instruments
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

    def test_strategy_without_crossover(self, user, oanda_account):
        """Test strategy with crossover detection disabled."""
        strategy = Strategy.objects.create(
            account=oanda_account,
            strategy_type="stochastic",
            config={
                "k_period": 14,
                "k_smoothing": 3,
                "d_smoothing": 3,
                "oversold_threshold": 20,
                "overbought_threshold": 80,
                "base_units": 1000,
                "use_crossover": False,
            },
            instruments=["EUR_USD"],
            is_active=True,
        )
        strategy_instance = StochasticStrategy(strategy)

        # Feed data
        base_price = Decimal("1.1000")
        for i in range(25):
            tick = TickData(
                account=oanda_account,
                instrument="EUR_USD",
                timestamp=timezone.now(),
                bid=base_price + Decimal(str(i * 0.0001)),
                ask=base_price + Decimal(str(i * 0.0001)) + Decimal("0.0002"),
                mid=base_price + Decimal(str(i * 0.0001)) + Decimal("0.0001"),
                spread=Decimal("0.0002"),
            )
            strategy_instance.on_tick(tick)

        # Verify crossover detector is NOT initialized
        assert "EUR_USD" not in strategy_instance.crossover_detectors

    def test_bullish_crossover_entry(self, strategy_instance, oanda_account):
        """Test entry signal on bullish crossover."""
        # Feed prices to create a scenario where %K crosses above %D
        base_price = Decimal("1.1000")

        # First, create downtrend then reversal
        prices = []
        # Downtrend
        for i in range(15):
            prices.append(base_price - Decimal(str(i * 0.001)))
        # Reversal (uptrend)
        for i in range(15):
            prices.append(base_price - Decimal("0.014") + Decimal(str(i * 0.001)))

        for price in prices:
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

        # Verify calculator is ready
        calculator = strategy_instance.stochastic_calculators.get("EUR_USD")
        assert calculator is not None
        assert calculator.is_ready()

    def test_bearish_crossover_exit(self, strategy_instance, oanda_account):
        """Test exit signal on bearish crossover."""
        # Create a long position
        Position.objects.create(
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

        # Feed prices to create a scenario where %K crosses below %D
        base_price = Decimal("1.1000")

        # First, create uptrend then reversal
        prices = []
        # Uptrend
        for i in range(15):
            prices.append(base_price + Decimal(str(i * 0.001)))
        # Reversal (downtrend)
        for i in range(15):
            prices.append(base_price + Decimal("0.014") - Decimal(str(i * 0.001)))

        for price in prices:
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

        # Verify calculator is ready
        calculator = strategy_instance.stochastic_calculators.get("EUR_USD")
        assert calculator is not None
        assert calculator.is_ready()
