"""
Unit tests for Mean Reversion Strategy.

This module tests the Mean Reversion Strategy implementation including:
- Bollinger Bands calculation
- Oversold entry signal generation
- Exit signal generation
- Stop-loss placement
- Strategy on_tick processing

Requirements: 5.1, 5.3
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone

import pytest

from accounts.models import OandaAccount
from trading.mean_reversion_strategy import BollingerBandsCalculator, MeanReversionStrategy
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


class TestBollingerBandsCalculator:
    """Test Bollinger Bands calculation."""

    def test_bollinger_bands_calculation(self):
        """Test Bollinger Bands calculation with known sample data."""
        calculator = BollingerBandsCalculator(period=20, std_dev_multiplier=Decimal("2.0"))

        # Add 20 prices with known values
        base_price = Decimal("100.00")
        prices = [base_price + Decimal(str(i * 0.5)) for i in range(20)]

        for price in prices:
            calculator.add_price(price)

        # After 20 prices, bands should be calculated
        assert calculator.is_ready()
        upper, middle, lower = calculator.get_bands()

        assert upper is not None
        assert middle is not None
        assert lower is not None

        # Middle band should be the average
        expected_middle = sum(prices) / Decimal("20")
        assert abs(middle - expected_middle) < Decimal("0.01")

        # Upper band should be above middle
        assert upper > middle

        # Lower band should be below middle
        assert lower < middle

        # Bands should be symmetric around middle
        assert abs((upper - middle) - (middle - lower)) < Decimal("0.01")

    def test_bollinger_bands_not_ready_with_insufficient_data(self):
        """Test that Bollinger Bands are not ready with insufficient data."""
        calculator = BollingerBandsCalculator(period=20)

        # Add only a few prices
        for i in range(10):
            calculator.add_price(Decimal(str(100 + i)))

        assert not calculator.is_ready()
        upper, middle, lower = calculator.get_bands()
        assert upper is None
        assert middle is None
        assert lower is None

    def test_bollinger_bands_with_volatile_prices(self):
        """Test Bollinger Bands with volatile price movements."""
        calculator = BollingerBandsCalculator(period=20, std_dev_multiplier=Decimal("2.0"))

        # Add prices with high volatility
        base_price = Decimal("100.00")
        for i in range(20):
            # Alternate between high and low prices
            if i % 2 == 0:
                calculator.add_price(base_price + Decimal("5.0"))
            else:
                calculator.add_price(base_price - Decimal("5.0"))

        assert calculator.is_ready()
        upper, middle, lower = calculator.get_bands()
        assert upper is not None and lower is not None

        # With high volatility, bands should be wider
        band_width = upper - lower
        assert band_width > Decimal("10.0")

    def test_bollinger_bands_with_stable_prices(self):
        """Test Bollinger Bands with stable price movements."""
        calculator = BollingerBandsCalculator(period=20, std_dev_multiplier=Decimal("2.0"))

        # Add prices with low volatility
        base_price = Decimal("100.00")
        for i in range(20):
            # Small variations
            calculator.add_price(base_price + Decimal(str(i * 0.01)))

        assert calculator.is_ready()
        upper, middle, lower = calculator.get_bands()
        assert upper is not None and lower is not None

        # With low volatility, bands should be narrower
        band_width = upper - lower
        assert band_width < Decimal("1.0")


@pytest.mark.django_db
class TestMeanReversionStrategy:
    """Test Mean Reversion Strategy implementation."""

    @pytest.fixture
    def strategy_instance(self, oanda_account):
        """Create a test Mean Reversion strategy instance."""
        strategy = Strategy.objects.create(
            account=oanda_account,
            strategy_type="mean_reversion",
            config={
                "bb_period": 20,
                "bb_std_dev": 2.0,
                "base_units": 1000,
                "stop_loss_pips": 10,
                "exit_at_middle": True,
            },
            instruments=["EUR_USD"],
            is_active=True,
        )
        return MeanReversionStrategy(strategy)

    def test_oversold_entry_signal_generation(self, strategy_instance, oanda_account):
        """Test that price at lower band generates long entry signal."""
        # Feed prices to establish Bollinger Bands
        base_price = Decimal("1.1000")

        # Add 20 prices to establish bands
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

        # Get current bands
        calculator = strategy_instance.bb_calculators["EUR_USD"]
        upper, middle, lower = calculator.get_bands()
        assert lower is not None

        # Send tick at lower band
        tick = TickData(
            account=oanda_account,
            instrument="EUR_USD",
            timestamp=timezone.now(),
            bid=lower - Decimal("0.0001"),
            ask=lower + Decimal("0.0001"),
            mid=lower,
            spread=Decimal("0.0002"),
        )
        orders = strategy_instance.on_tick(tick)

        # Should generate entry order
        assert len(orders) > 0
        order = orders[0]
        assert order.direction == "long"
        assert order.order_type == "market"
        assert order.units == Decimal("1000")

    def test_exit_at_middle_band(self, strategy_instance, oanda_account):
        """Test exit signal when price reaches middle band."""
        # First establish bands with stable prices
        base_price = Decimal("1.1000")

        # Use stable prices to establish bands
        for _ in range(20):
            tick = TickData(
                account=oanda_account,
                instrument="EUR_USD",
                timestamp=timezone.now(),
                bid=base_price,
                ask=base_price + Decimal("0.0002"),
                mid=base_price + Decimal("0.0001"),
                spread=Decimal("0.0002"),
            )
            strategy_instance.on_tick(tick)

        # Create a long position
        calculator = strategy_instance.bb_calculators["EUR_USD"]
        upper, middle, lower = calculator.get_bands()

        # Store entry lower band for stop-loss calculation
        strategy_instance.entry_lower_bands["EUR_USD"] = lower

        position = Position.objects.create(
            account=oanda_account,
            strategy=strategy_instance.strategy,
            position_id="test_pos_1",
            instrument="EUR_USD",
            direction="long",
            units=Decimal("1000"),
            entry_price=lower,
            current_price=lower,
            opened_at=timezone.now(),
        )

        # Send tick well above middle band to trigger exit
        # Use a price significantly higher to ensure it's above middle even after recalculation
        exit_price = middle + Decimal("0.0010")
        tick = TickData(
            account=oanda_account,
            instrument="EUR_USD",
            timestamp=timezone.now(),
            bid=exit_price - Decimal("0.0001"),
            ask=exit_price + Decimal("0.0001"),
            mid=exit_price,
            spread=Decimal("0.0002"),
        )
        orders = strategy_instance.on_tick(tick)

        # Should generate close order
        assert len(orders) > 0
        order = orders[0]
        assert order.direction == "short"  # Opposite to close long
        assert order.units == position.units

    def test_exit_at_upper_band(self, strategy_instance, oanda_account):
        """Test exit signal when price reaches upper band."""
        # Establish bands and create a position
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

        # Create a long position
        calculator = strategy_instance.bb_calculators["EUR_USD"]
        upper, middle, lower = calculator.get_bands()

        position = Position.objects.create(
            account=oanda_account,
            strategy=strategy_instance.strategy,
            position_id="test_pos_1",
            instrument="EUR_USD",
            direction="long",
            units=Decimal("1000"),
            entry_price=lower,
            current_price=lower,
            opened_at=timezone.now(),
        )

        # Send tick at upper band
        tick = TickData(
            account=oanda_account,
            instrument="EUR_USD",
            timestamp=timezone.now(),
            bid=upper - Decimal("0.0001"),
            ask=upper + Decimal("0.0001"),
            mid=upper,
            spread=Decimal("0.0002"),
        )
        orders = strategy_instance.on_tick(tick)

        # Should generate close order
        assert len(orders) > 0
        order = orders[0]
        assert order.direction == "short"
        assert order.units == position.units

    def test_stop_loss_placement(self, strategy_instance, oanda_account):
        """Test stop-loss trigger below lower band."""
        # Establish bands
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

        # Get bands and create position
        calculator = strategy_instance.bb_calculators["EUR_USD"]
        upper, middle, lower = calculator.get_bands()

        # Store entry lower band
        strategy_instance.entry_lower_bands["EUR_USD"] = lower

        position = Position.objects.create(
            account=oanda_account,
            strategy=strategy_instance.strategy,
            position_id="test_pos_1",
            instrument="EUR_USD",
            direction="long",
            units=Decimal("1000"),
            entry_price=lower,
            current_price=lower,
            opened_at=timezone.now(),
        )

        # Calculate stop-loss price (10 pips below lower band)
        stop_loss_price = lower - (Decimal("10") * Decimal("0.0001"))

        # Send tick below stop-loss
        tick = TickData(
            account=oanda_account,
            instrument="EUR_USD",
            timestamp=timezone.now(),
            bid=stop_loss_price - Decimal("0.0002"),
            ask=stop_loss_price,
            mid=stop_loss_price - Decimal("0.0001"),
            spread=Decimal("0.0002"),
        )
        orders = strategy_instance.on_tick(tick)

        # Should generate stop-loss order
        assert len(orders) > 0
        order = orders[0]
        assert order.direction == "short"
        assert order.units == position.units

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

        # Bollinger Bands calculator should be ready
        calculator = strategy_instance.bb_calculators.get("EUR_USD")
        assert calculator is not None
        assert calculator.is_ready()

        # Should have processed ticks without errors
        upper, middle, lower = calculator.get_bands()
        assert upper is not None
        assert middle is not None
        assert lower is not None

    def test_config_validation(self, strategy_instance):
        """Test strategy configuration validation."""
        # Valid config
        valid_config = {
            "bb_period": 20,
            "bb_std_dev": 2.0,
            "base_units": 1000,
            "stop_loss_pips": 10,
            "exit_at_middle": True,
        }
        assert strategy_instance.validate_config(valid_config)

        # Invalid BB period
        with pytest.raises(ValueError, match="bb_period must be"):
            strategy_instance.validate_config({"bb_period": 1})

        # Invalid standard deviation
        with pytest.raises(ValueError, match="bb_std_dev must be positive"):
            strategy_instance.validate_config({"bb_std_dev": -1.0})

        # Invalid base units
        with pytest.raises(ValueError, match="base_units must be positive"):
            strategy_instance.validate_config({"base_units": -100})

        # Invalid stop-loss pips
        with pytest.raises(ValueError, match="stop_loss_pips must be positive"):
            strategy_instance.validate_config({"stop_loss_pips": 0})

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
        # Store entry lower band
        strategy_instance.entry_lower_bands["EUR_USD"] = Decimal("1.1000")

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

        # Should handle closed position and clean up entry lower band
        strategy_instance.on_position_update(position)
        assert "EUR_USD" not in strategy_instance.entry_lower_bands

    def test_no_entry_with_open_position(self, strategy_instance, oanda_account):
        """Test that no entry signal is generated when position is already open."""
        # Establish bands
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

        # Create existing position
        calculator = strategy_instance.bb_calculators["EUR_USD"]
        upper, middle, lower = calculator.get_bands()

        Position.objects.create(
            account=oanda_account,
            strategy=strategy_instance.strategy,
            position_id="test_pos_1",
            instrument="EUR_USD",
            direction="long",
            units=Decimal("1000"),
            entry_price=lower,
            current_price=lower,
            opened_at=timezone.now(),
        )

        # Send tick at lower band (would normally trigger entry)
        tick = TickData(
            account=oanda_account,
            instrument="EUR_USD",
            timestamp=timezone.now(),
            bid=lower - Decimal("0.0001"),
            ask=lower + Decimal("0.0001"),
            mid=lower,
            spread=Decimal("0.0002"),
        )
        orders = strategy_instance.on_tick(tick)

        # Should not generate entry order (position already exists)
        # May generate exit order if conditions are met, but not entry
        for order in orders:
            assert order.direction != "long"

    def test_exit_at_middle_disabled(self, user, oanda_account):
        """Test that exit at middle band can be disabled."""
        strategy = Strategy.objects.create(
            account=oanda_account,
            strategy_type="mean_reversion",
            config={
                "bb_period": 20,
                "bb_std_dev": 2.0,
                "base_units": 1000,
                "stop_loss_pips": 10,
                "exit_at_middle": False,  # Disabled
            },
            instruments=["EUR_USD"],
            is_active=True,
        )
        strategy_instance = MeanReversionStrategy(strategy)

        # Establish bands
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

        # Create position
        calculator = strategy_instance.bb_calculators["EUR_USD"]
        upper, middle, lower = calculator.get_bands()
        assert upper is not None and middle is not None and lower is not None

        Position.objects.create(
            account=oanda_account,
            strategy=strategy_instance.strategy,
            position_id="test_pos_1",
            instrument="EUR_USD",
            direction="long",
            units=Decimal("1000"),
            entry_price=lower,
            current_price=lower,
            opened_at=timezone.now(),
        )

        # Send tick at middle band
        tick = TickData(
            account=oanda_account,
            instrument="EUR_USD",
            timestamp=timezone.now(),
            bid=middle - Decimal("0.0001"),
            ask=middle + Decimal("0.0001"),
            mid=middle,
            spread=Decimal("0.0002"),
        )
        orders = strategy_instance.on_tick(tick)

        # Should NOT generate exit order at middle band
        assert len(orders) == 0
