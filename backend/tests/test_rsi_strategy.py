"""
Unit tests for RSI Strategy.

This module tests the RSI Strategy implementation including:
- RSI calculation with sample data
- Oversold signal generation
- Overbought signal generation
- Divergence detection
- Strategy on_tick processing

Requirements: 5.1, 5.3
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone

import pytest

from accounts.models import OandaAccount
from trading.models import Position, Strategy
from trading.rsi_strategy import DivergenceDetector, RSICalculator, RSIStrategy
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


class TestRSICalculator:
    """Test RSI calculation."""

    def test_rsi_calculation_with_sample_data(self):
        """Test RSI calculation with known sample data."""
        calculator = RSICalculator(period=14)

        # Sample prices that should produce predictable RSI
        # Using a simple uptrend followed by downtrend
        prices = [
            Decimal("44.00"),
            Decimal("44.34"),
            Decimal("44.09"),
            Decimal("43.61"),
            Decimal("44.33"),
            Decimal("44.83"),
            Decimal("45.10"),
            Decimal("45.42"),
            Decimal("45.84"),
            Decimal("46.08"),
            Decimal("45.89"),
            Decimal("46.03"),
            Decimal("45.61"),
            Decimal("46.28"),
            Decimal("46.28"),  # 15th price to complete first RSI
        ]

        for price in prices:
            calculator.add_price(price)

        # After 15 prices, RSI should be calculated
        assert calculator.is_ready()
        rsi = calculator.get_rsi()
        assert rsi is not None
        # RSI should be between 0 and 100
        assert Decimal("0") <= rsi <= Decimal("100")
        # With mostly gains, RSI should be above 50
        assert rsi > Decimal("50")

    def test_rsi_not_ready_with_insufficient_data(self):
        """Test that RSI is not ready with insufficient data."""
        calculator = RSICalculator(period=14)

        # Add only a few prices
        for i in range(5):
            calculator.add_price(Decimal(str(100 + i)))

        assert not calculator.is_ready()
        assert calculator.get_rsi() is None

    def test_rsi_extreme_values(self):
        """Test RSI with extreme price movements."""
        calculator = RSICalculator(period=14)

        # All gains - RSI should approach 100
        base_price = Decimal("100")
        for i in range(20):
            calculator.add_price(base_price + Decimal(str(i)))

        rsi = calculator.get_rsi()
        assert rsi is not None
        assert rsi > Decimal("90")  # Should be very high

        # Reset and test all losses
        calculator = RSICalculator(period=14)
        for i in range(20):
            calculator.add_price(base_price - Decimal(str(i)))

        rsi = calculator.get_rsi()
        assert rsi is not None
        assert rsi < Decimal("10")  # Should be very low


class TestDivergenceDetector:
    """Test divergence detection."""

    def test_bullish_divergence_detection(self):
        """Test detection of bullish divergence."""
        detector = DivergenceDetector(lookback_period=5)

        # Price making lower lows, RSI making higher lows
        prices = [
            Decimal("100"),
            Decimal("99"),
            Decimal("98"),
            Decimal("97"),
            Decimal("96"),
        ]
        rsis = [
            Decimal("30"),
            Decimal("32"),
            Decimal("34"),
            Decimal("36"),
            Decimal("38"),
        ]

        for price, rsi in zip(prices, rsis):
            detector.add_data(price, rsi)

        assert detector.is_ready()
        assert detector.detect_bullish_divergence()
        assert not detector.detect_bearish_divergence()

    def test_bearish_divergence_detection(self):
        """Test detection of bearish divergence."""
        detector = DivergenceDetector(lookback_period=5)

        # Price making higher highs, RSI making lower highs
        prices = [
            Decimal("100"),
            Decimal("101"),
            Decimal("102"),
            Decimal("103"),
            Decimal("104"),
        ]
        rsis = [
            Decimal("70"),
            Decimal("68"),
            Decimal("66"),
            Decimal("64"),
            Decimal("62"),
        ]

        for price, rsi in zip(prices, rsis):
            detector.add_data(price, rsi)

        assert detector.is_ready()
        assert detector.detect_bearish_divergence()
        assert not detector.detect_bullish_divergence()

    def test_no_divergence(self):
        """Test when there is no divergence."""
        detector = DivergenceDetector(lookback_period=5)

        # Both price and RSI moving in same direction
        prices = [
            Decimal("100"),
            Decimal("101"),
            Decimal("102"),
            Decimal("103"),
            Decimal("104"),
        ]
        rsis = [
            Decimal("50"),
            Decimal("52"),
            Decimal("54"),
            Decimal("56"),
            Decimal("58"),
        ]

        for price, rsi in zip(prices, rsis):
            detector.add_data(price, rsi)

        assert detector.is_ready()
        assert not detector.detect_bullish_divergence()
        assert not detector.detect_bearish_divergence()


@pytest.mark.django_db
class TestRSIStrategy:
    """Test RSI Strategy implementation."""

    @pytest.fixture
    def strategy_instance(self, oanda_account):
        """Create a test RSI strategy instance."""
        strategy = Strategy.objects.create(
            account=oanda_account,
            strategy_type="rsi",
            config={
                "rsi_period": 14,
                "oversold_threshold": 30,
                "overbought_threshold": 70,
                "base_units": 1000,
                "use_divergence": False,
            },
            instrument="EUR_USD",
            is_active=True,
        )
        return RSIStrategy(strategy)

    def test_oversold_signal_generation(self, strategy_instance, oanda_account):
        """Test that oversold condition generates long entry signal."""
        # Feed prices to get RSI below 30
        base_price = Decimal("1.1000")

        # Create downtrend to get low RSI
        for i in range(20):
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

        # Last tick should generate entry when RSI is oversold
        assert len(orders) > 0
        order = orders[0]
        assert order.direction == "long"
        assert order.order_type == "market"
        assert order.units == Decimal("1000")

    def test_overbought_signal_generation(self, strategy_instance, oanda_account):
        """Test that overbought condition generates exit signal."""
        # First create a long position
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

        # Feed prices to get RSI above 70
        base_price = Decimal("1.1000")

        # Create uptrend to get high RSI
        for i in range(20):
            tick = TickData(
                account=oanda_account,
                instrument="EUR_USD",
                timestamp=timezone.now(),
                bid=base_price + Decimal(str(i * 0.001)),
                ask=base_price + Decimal(str(i * 0.001)) + Decimal("0.0002"),
                mid=base_price + Decimal(str(i * 0.001)) + Decimal("0.0001"),
                spread=Decimal("0.0002"),
            )
            orders = strategy_instance.on_tick(tick)

        # Should generate close order when RSI is overbought
        assert len(orders) > 0
        order = orders[0]
        assert order.direction == "short"  # Opposite to close long
        assert order.units == position.units

    def test_divergence_detection_with_strategy(self, user, oanda_account):
        """Test strategy with divergence detection enabled."""
        strategy = Strategy.objects.create(
            account=oanda_account,
            strategy_type="rsi",
            config={
                "rsi_period": 14,
                "oversold_threshold": 30,
                "overbought_threshold": 70,
                "base_units": 1000,
                "use_divergence": True,
                "divergence_lookback": 5,
            },
            instrument="EUR_USD",
            is_active=True,
        )
        strategy_instance = RSIStrategy(strategy)

        # Feed enough data to calculate RSI
        base_price = Decimal("1.1000")
        for i in range(20):
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

        # Verify divergence detector is initialized
        assert "EUR_USD" in strategy_instance.divergence_detectors

    def test_strategy_on_tick_processing(self, strategy_instance, oanda_account):
        """Test complete on_tick processing flow."""
        # Process multiple ticks
        base_price = Decimal("1.1000")
        all_orders = []

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
            orders = strategy_instance.on_tick(tick)
            all_orders.extend(orders)

        # RSI calculator should be ready
        calculator = strategy_instance.rsi_calculators.get("EUR_USD")
        assert calculator is not None
        assert calculator.is_ready()

        # Should have processed ticks without errors
        assert calculator.get_rsi() is not None

    def test_config_validation(self, strategy_instance):
        """Test strategy configuration validation."""
        # Valid config
        valid_config = {
            "rsi_period": 14,
            "oversold_threshold": 30,
            "overbought_threshold": 70,
            "base_units": 1000,
        }
        assert strategy_instance.validate_config(valid_config)

        # Invalid RSI period
        with pytest.raises(ValueError, match="rsi_period must be"):
            strategy_instance.validate_config({"rsi_period": 1})

        # Invalid oversold threshold
        with pytest.raises(ValueError, match="oversold_threshold must be"):
            strategy_instance.validate_config({"oversold_threshold": 150})

        # Invalid overbought threshold
        with pytest.raises(ValueError, match="overbought_threshold must be"):
            strategy_instance.validate_config({"overbought_threshold": -10})

        # Oversold >= Overbought
        with pytest.raises(ValueError, match="oversold_threshold must be less than"):
            strategy_instance.validate_config(
                {"oversold_threshold": 70, "overbought_threshold": 30}
            )

        # Invalid base units
        with pytest.raises(ValueError, match="base_units must be positive"):
            strategy_instance.validate_config({"base_units": -100})

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
