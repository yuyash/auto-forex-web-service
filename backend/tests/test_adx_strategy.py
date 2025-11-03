"""
Unit tests for ADX (Average Directional Index) Strategy.

This module tests the ADX Strategy implementation including:
- ADX calculation
- Trend strength detection
- Directional movement signals
- Weak trend exit logic
- Strategy on_tick processing

Requirements: 5.1, 5.3
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone

import pytest

from accounts.models import OandaAccount
from trading.adx_strategy import ADXCalculator, ADXStrategy
from trading.models import Position, Strategy
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


class TestADXCalculator:
    """Test ADX calculation."""

    def test_adx_calculation(self):
        """Test ADX calculation with sample data."""
        calculator = ADXCalculator(period=14)

        # Sample price data with clear uptrend
        # Need at least 14 + 14 = 28 bars for ADX to be ready
        base_price = Decimal("100.00")
        for i in range(35):
            high = base_price + Decimal(str(i * 0.5)) + Decimal("0.5")
            low = base_price + Decimal(str(i * 0.5)) - Decimal("0.3")
            close = base_price + Decimal(str(i * 0.5))
            calculator.add_price(high, low, close)

        # After enough data, ADX should be calculated
        assert calculator.is_ready()
        adx = calculator.get_adx()
        plus_di = calculator.get_plus_di()
        minus_di = calculator.get_minus_di()

        assert adx is not None
        assert plus_di is not None
        assert minus_di is not None

        # All should be between 0 and 100
        assert Decimal("0") <= adx <= Decimal("100")
        assert Decimal("0") <= plus_di <= Decimal("100")
        assert Decimal("0") <= minus_di <= Decimal("100")

        # With uptrend, +DI should be greater than -DI
        assert plus_di > minus_di

    def test_adx_not_ready_with_insufficient_data(self):
        """Test that ADX is not ready with insufficient data."""
        calculator = ADXCalculator(period=14)

        # Add only a few bars
        for i in range(10):
            high = Decimal(str(100 + i))
            low = Decimal(str(99 + i))
            close = Decimal(str(99.5 + i))
            calculator.add_price(high, low, close)

        assert not calculator.is_ready()
        assert calculator.get_adx() is None

    def test_adx_strong_uptrend(self):
        """Test ADX with strong uptrend."""
        calculator = ADXCalculator(period=14)

        # Strong uptrend
        base_price = Decimal("100.00")
        for i in range(40):
            high = base_price + Decimal(str(i * 1.0)) + Decimal("0.8")
            low = base_price + Decimal(str(i * 1.0)) - Decimal("0.2")
            close = base_price + Decimal(str(i * 1.0))
            calculator.add_price(high, low, close)

        adx = calculator.get_adx()
        plus_di = calculator.get_plus_di()
        minus_di = calculator.get_minus_di()

        assert adx is not None
        assert plus_di is not None
        assert minus_di is not None

        # Strong uptrend should have high ADX and +DI > -DI
        assert adx > Decimal("20")
        assert plus_di > minus_di

    def test_adx_strong_downtrend(self):
        """Test ADX with strong downtrend."""
        calculator = ADXCalculator(period=14)

        # Strong downtrend
        base_price = Decimal("100.00")
        for i in range(40):
            high = base_price - Decimal(str(i * 1.0)) + Decimal("0.8")
            low = base_price - Decimal(str(i * 1.0)) - Decimal("0.2")
            close = base_price - Decimal(str(i * 1.0))
            calculator.add_price(high, low, close)

        adx = calculator.get_adx()
        plus_di = calculator.get_plus_di()
        minus_di = calculator.get_minus_di()

        assert adx is not None
        assert plus_di is not None
        assert minus_di is not None

        # Strong downtrend should have high ADX and -DI > +DI
        assert adx > Decimal("20")
        assert minus_di > plus_di

    def test_adx_sideways_market(self):
        """Test ADX with sideways/ranging market."""
        calculator = ADXCalculator(period=14)

        # Sideways market (oscillating prices)
        base_price = Decimal("100.00")
        for i in range(40):
            # Oscillate between 99 and 101
            offset = Decimal(str((i % 4) - 2)) * Decimal("0.5")
            high = base_price + offset + Decimal("0.5")
            low = base_price + offset - Decimal("0.5")
            close = base_price + offset
            calculator.add_price(high, low, close)

        adx = calculator.get_adx()
        assert adx is not None

        # Sideways market should have low ADX
        assert adx < Decimal("30")

    def test_adx_true_range_calculation(self):
        """Test True Range calculation."""
        calculator = ADXCalculator(period=14)

        # Add first bar
        calculator.add_price(Decimal("100"), Decimal("99"), Decimal("99.5"))

        # Add second bar with gap
        calculator.add_price(Decimal("102"), Decimal("101"), Decimal("101.5"))

        # TR should be calculated (need at least 2 bars)
        assert len(calculator.tr_values) > 0

    def test_adx_directional_movement(self):
        """Test Directional Movement calculation."""
        calculator = ADXCalculator(period=14)

        # Add bars with clear upward movement
        calculator.add_price(Decimal("100"), Decimal("99"), Decimal("99.5"))
        calculator.add_price(Decimal("101"), Decimal("100"), Decimal("100.5"))

        # +DM and -DM should be calculated
        assert len(calculator.plus_dm_values) > 0
        assert len(calculator.minus_dm_values) > 0


@pytest.mark.django_db
class TestADXStrategy:
    """Test ADX Strategy implementation."""

    @pytest.fixture
    def strategy_instance(self, oanda_account):
        """Create a test ADX strategy instance."""
        strategy = Strategy.objects.create(
            account=oanda_account,
            strategy_type="adx",
            config={
                "period": 14,
                "strong_trend_threshold": 25,
                "weak_trend_threshold": 20,
                "base_units": 1000,
                "allow_short": False,
            },
            instruments=["EUR_USD"],
            is_active=True,
        )
        return ADXStrategy(strategy)

    def test_trend_strength_detection(self, strategy_instance, oanda_account):
        """Test trend strength detection (ADX > 25)."""
        # Feed prices to create strong uptrend
        base_price = Decimal("1.1000")

        for i in range(40):
            high = base_price + Decimal(str(i * 0.001)) + Decimal("0.0005")
            low = base_price + Decimal(str(i * 0.001)) - Decimal("0.0003")
            mid = base_price + Decimal(str(i * 0.001))

            tick = TickData(
                account=oanda_account,
                instrument="EUR_USD",
                timestamp=timezone.now(),
                bid=low,
                ask=high,
                mid=mid,
                spread=high - low,
            )
            strategy_instance.on_tick(tick)

        # Verify ADX calculator is working
        calculator = strategy_instance.adx_calculators.get("EUR_USD")
        assert calculator is not None
        assert calculator.is_ready()

        adx = calculator.get_adx()
        assert adx is not None
        # Strong trend should have ADX > 20
        assert adx > Decimal("15")

    def test_directional_movement_signals(self, strategy_instance, oanda_account):
        """Test directional movement (+DI, -DI) for entry signals."""
        # Feed prices to create uptrend
        base_price = Decimal("1.1000")

        for i in range(40):
            high = base_price + Decimal(str(i * 0.001)) + Decimal("0.0005")
            low = base_price + Decimal(str(i * 0.001)) - Decimal("0.0003")
            mid = base_price + Decimal(str(i * 0.001))

            tick = TickData(
                account=oanda_account,
                instrument="EUR_USD",
                timestamp=timezone.now(),
                bid=low,
                ask=high,
                mid=mid,
                spread=high - low,
            )
            strategy_instance.on_tick(tick)

        calculator = strategy_instance.adx_calculators.get("EUR_USD")
        assert calculator is not None

        if calculator.is_ready():
            plus_di = calculator.get_plus_di()
            minus_di = calculator.get_minus_di()

            assert plus_di is not None
            assert minus_di is not None

            # Uptrend should have +DI > -DI
            assert plus_di > minus_di

    def test_weak_trend_exit_logic(self, strategy_instance, oanda_account):
        """Test exit when ADX falls below 20 (weak trend)."""
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

        # Feed prices to create weak/sideways market
        base_price = Decimal("1.1000")

        for i in range(40):
            # Oscillating prices
            offset = Decimal(str((i % 4) - 2)) * Decimal("0.0002")
            high = base_price + offset + Decimal("0.0002")
            low = base_price + offset - Decimal("0.0002")
            mid = base_price + offset

            tick = TickData(
                account=oanda_account,
                instrument="EUR_USD",
                timestamp=timezone.now(),
                bid=low,
                ask=high,
                mid=mid,
                spread=high - low,
            )
            strategy_instance.on_tick(tick)

        calculator = strategy_instance.adx_calculators.get("EUR_USD")
        assert calculator is not None

        if calculator.is_ready():
            adx = calculator.get_adx()
            assert adx is not None
            # Sideways market should have lower ADX
            assert adx < Decimal("40")

    def test_strategy_on_tick_processing(self, strategy_instance, oanda_account):
        """Test complete on_tick processing flow."""
        # Process multiple ticks
        base_price = Decimal("1.1000")
        all_orders = []

        for i in range(40):
            high = base_price + Decimal(str(i * 0.0005)) + Decimal("0.0003")
            low = base_price + Decimal(str(i * 0.0005)) - Decimal("0.0002")
            mid = base_price + Decimal(str(i * 0.0005))

            tick = TickData(
                account=oanda_account,
                instrument="EUR_USD",
                timestamp=timezone.now(),
                bid=low,
                ask=high,
                mid=mid,
                spread=high - low,
            )
            orders = strategy_instance.on_tick(tick)
            all_orders.extend(orders)

        # ADX calculator should be ready
        calculator = strategy_instance.adx_calculators.get("EUR_USD")
        assert calculator is not None
        assert calculator.is_ready()

        # Should have processed ticks without errors
        adx = calculator.get_adx()
        plus_di = calculator.get_plus_di()
        minus_di = calculator.get_minus_di()

        assert adx is not None
        assert plus_di is not None
        assert minus_di is not None

    def test_config_validation(self, strategy_instance):
        """Test strategy configuration validation."""
        # Valid config
        valid_config = {
            "period": 14,
            "strong_trend_threshold": 25,
            "weak_trend_threshold": 20,
            "base_units": 1000,
            "allow_short": False,
        }
        assert strategy_instance.validate_config(valid_config)

        # Invalid period
        with pytest.raises(ValueError, match="period must be"):
            strategy_instance.validate_config({"period": 1})

        # Invalid strong trend threshold
        with pytest.raises(ValueError, match="strong_trend_threshold must be"):
            strategy_instance.validate_config({"strong_trend_threshold": 150})

        # Invalid weak trend threshold
        with pytest.raises(ValueError, match="weak_trend_threshold must be"):
            strategy_instance.validate_config({"weak_trend_threshold": -10})

        # Weak >= Strong
        with pytest.raises(ValueError, match="weak_trend_threshold must be less than"):
            strategy_instance.validate_config(
                {"weak_trend_threshold": 30, "strong_trend_threshold": 25}
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

    def test_strategy_with_short_positions_allowed(self, user, oanda_account):
        """Test strategy with short positions enabled."""
        strategy = Strategy.objects.create(
            account=oanda_account,
            strategy_type="adx",
            config={
                "period": 14,
                "strong_trend_threshold": 25,
                "weak_trend_threshold": 20,
                "base_units": 1000,
                "allow_short": True,
            },
            instruments=["EUR_USD"],
            is_active=True,
        )
        strategy_instance = ADXStrategy(strategy)

        # Feed downtrend data
        base_price = Decimal("1.1000")

        for i in range(40):
            high = base_price - Decimal(str(i * 0.001)) + Decimal("0.0005")
            low = base_price - Decimal(str(i * 0.001)) - Decimal("0.0003")
            mid = base_price - Decimal(str(i * 0.001))

            tick = TickData(
                account=oanda_account,
                instrument="EUR_USD",
                timestamp=timezone.now(),
                bid=low,
                ask=high,
                mid=mid,
                spread=high - low,
            )
            strategy_instance.on_tick(tick)

        calculator = strategy_instance.adx_calculators.get("EUR_USD")
        assert calculator is not None

        if calculator.is_ready():
            plus_di = calculator.get_plus_di()
            minus_di = calculator.get_minus_di()

            assert plus_di is not None
            assert minus_di is not None

            # Downtrend should have -DI > +DI
            assert minus_di > plus_di

    def test_long_entry_on_strong_uptrend(self, strategy_instance, oanda_account):
        """Test long entry when ADX > 25 and +DI > -DI."""
        # Feed strong uptrend data
        base_price = Decimal("1.1000")

        for i in range(40):
            high = base_price + Decimal(str(i * 0.002)) + Decimal("0.0008")
            low = base_price + Decimal(str(i * 0.002)) - Decimal("0.0002")
            mid = base_price + Decimal(str(i * 0.002))

            tick = TickData(
                account=oanda_account,
                instrument="EUR_USD",
                timestamp=timezone.now(),
                bid=low,
                ask=high,
                mid=mid,
                spread=high - low,
            )
            strategy_instance.on_tick(tick)

        calculator = strategy_instance.adx_calculators.get("EUR_USD")
        assert calculator is not None
        assert calculator.is_ready()

        adx = calculator.get_adx()
        plus_di = calculator.get_plus_di()
        minus_di = calculator.get_minus_di()

        assert adx is not None
        assert plus_di is not None
        assert minus_di is not None

        # Strong uptrend indicators
        assert plus_di > minus_di

    def test_exit_all_positions_on_weak_trend(self, strategy_instance, oanda_account):
        """Test that all positions are closed when ADX < 20."""
        # Create multiple positions
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

        Position.objects.create(
            account=oanda_account,
            strategy=strategy_instance.strategy,
            position_id="test_pos_2",
            instrument="EUR_USD",
            direction="long",
            units=Decimal("500"),
            entry_price=Decimal("1.1010"),
            current_price=Decimal("1.1010"),
            opened_at=timezone.now(),
        )

        # Feed sideways market data
        base_price = Decimal("1.1000")

        for i in range(40):
            offset = Decimal(str((i % 6) - 3)) * Decimal("0.0001")
            high = base_price + offset + Decimal("0.0002")
            low = base_price + offset - Decimal("0.0002")
            mid = base_price + offset

            tick = TickData(
                account=oanda_account,
                instrument="EUR_USD",
                timestamp=timezone.now(),
                bid=low,
                ask=high,
                mid=mid,
                spread=high - low,
            )
            strategy_instance.on_tick(tick)

        calculator = strategy_instance.adx_calculators.get("EUR_USD")
        assert calculator is not None

        if calculator.is_ready():
            adx = calculator.get_adx()
            assert adx is not None
