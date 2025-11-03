"""
Unit tests for Arbitrage Strategy.

This module tests the Arbitrage Strategy implementation including:
- Price difference detection
- Simultaneous order generation
- Spread profit calculation
- Execution delay handling
- Strategy on_tick processing

Requirements: 5.1, 5.3
"""

from datetime import datetime, timezone
from decimal import Decimal

from django.contrib.auth import get_user_model

import pytest

from accounts.models import OandaAccount
from trading.arbitrage_strategy import ArbitrageStrategy, PriceDifferenceDetector
from trading.models import Strategy
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
        margin_used=Decimal("0.00"),
        unrealized_pnl=Decimal("0.00"),
    )


@pytest.fixture
def strategy_config():
    """Create test strategy configuration."""
    return {
        "base_units": 1000,
        "min_spread_pips": 2.0,
        "max_execution_delay_ms": 500,
        "max_slippage_pips": 0.5,
        "profit_target_pips": 1.5,
    }


@pytest.fixture
def strategy_instance(oanda_account, strategy_config):
    """Create a test strategy instance."""
    strategy = Strategy.objects.create(
        account=oanda_account,
        strategy_type="arbitrage",
        config=strategy_config,
        instruments=["EUR_USD", "GBP_USD"],
        is_active=True,
    )
    return ArbitrageStrategy(strategy)


@pytest.fixture
def tick_data():
    """Create test tick data."""
    return TickData(
        account=None,
        instrument="EUR_USD",
        timestamp=datetime.now(timezone.utc),
        bid=Decimal("1.1000"),
        ask=Decimal("1.1002"),
        mid=Decimal("1.1001"),
        spread=Decimal("0.0002"),
    )


class TestPriceDifferenceDetector:
    """Test PriceDifferenceDetector class."""

    def test_initialization(self):
        """Test detector initialization."""
        detector = PriceDifferenceDetector(min_spread_pips=Decimal("2.0"))
        assert detector.min_spread_pips == Decimal("2.0")
        assert detector.broker_prices == {}

    def test_update_price(self):
        """Test price update for a broker."""
        detector = PriceDifferenceDetector()
        detector.update_price("broker1", "EUR_USD", Decimal("1.1000"), Decimal("1.1002"))

        assert "broker1" in detector.broker_prices
        assert "EUR_USD" in detector.broker_prices["broker1"]
        broker_prices = detector.broker_prices["broker1"]["EUR_USD"]
        assert broker_prices["bid"] == Decimal("1.1000")
        assert broker_prices["ask"] == Decimal("1.1002")
        assert broker_prices["mid"] == Decimal("1.1001")

    def test_detect_arbitrage_opportunity_insufficient_brokers(self):
        """Test arbitrage detection with insufficient brokers."""
        detector = PriceDifferenceDetector()
        detector.update_price("broker1", "EUR_USD", Decimal("1.1000"), Decimal("1.1002"))

        pip_value = Decimal("0.0001")
        has_opportunity, buy_broker, sell_broker, spread_pips = (
            detector.detect_arbitrage_opportunity("EUR_USD", pip_value)
        )

        assert has_opportunity is False
        assert buy_broker is None
        assert sell_broker is None
        assert spread_pips is None

    def test_detect_arbitrage_opportunity_no_spread(self):
        """Test arbitrage detection with no profitable spread."""
        detector = PriceDifferenceDetector(min_spread_pips=Decimal("2.0"))

        # Both brokers have same prices
        detector.update_price("broker1", "EUR_USD", Decimal("1.1000"), Decimal("1.1002"))
        detector.update_price("broker2", "EUR_USD", Decimal("1.1000"), Decimal("1.1002"))

        pip_value = Decimal("0.0001")
        has_opportunity, buy_broker, sell_broker, spread_pips = (
            detector.detect_arbitrage_opportunity("EUR_USD", pip_value)
        )

        assert has_opportunity is False

    def test_detect_arbitrage_opportunity_profitable_spread(self):
        """Test arbitrage detection with profitable spread."""
        detector = PriceDifferenceDetector(min_spread_pips=Decimal("2.0"))

        # Broker1 has lower ask, Broker2 has higher bid
        detector.update_price("broker1", "EUR_USD", Decimal("1.1000"), Decimal("1.1002"))
        detector.update_price("broker2", "EUR_USD", Decimal("1.1005"), Decimal("1.1007"))

        pip_value = Decimal("0.0001")
        has_opportunity, buy_broker, sell_broker, spread_pips = (
            detector.detect_arbitrage_opportunity("EUR_USD", pip_value)
        )

        assert has_opportunity is True
        assert buy_broker == "broker1"  # Buy at lower ask
        assert sell_broker == "broker2"  # Sell at higher bid
        assert spread_pips is not None and spread_pips >= Decimal("2.0")


class TestArbitrageStrategy:
    """Test ArbitrageStrategy class."""

    def test_initialization(self, strategy_instance):
        """Test strategy initialization."""
        assert strategy_instance.base_units == Decimal("1000")
        assert strategy_instance.min_spread_pips == Decimal("2.0")
        assert strategy_instance.max_execution_delay_ms == 500
        assert strategy_instance.max_slippage_pips == Decimal("0.5")
        assert strategy_instance.profit_target_pips == Decimal("1.5")
        assert isinstance(strategy_instance.price_detector, PriceDifferenceDetector)

    def test_validate_config_valid(self, strategy_instance, strategy_config):
        """Test configuration validation with valid config."""
        assert strategy_instance.validate_config(strategy_config) is True

    def test_validate_config_invalid_base_units(self, strategy_instance):
        """Test configuration validation with invalid base units."""
        invalid_config = {
            "base_units": -1000,
            "min_spread_pips": 2.0,
        }

        with pytest.raises(ValueError, match="base_units must be positive"):
            strategy_instance.validate_config(invalid_config)

    def test_validate_config_invalid_min_spread(self, strategy_instance):
        """Test configuration validation with invalid min spread."""
        invalid_config = {
            "base_units": 1000,
            "min_spread_pips": -2.0,
        }

        with pytest.raises(ValueError, match="min_spread_pips must be positive"):
            strategy_instance.validate_config(invalid_config)

    def test_validate_config_invalid_execution_delay(self, strategy_instance):
        """Test configuration validation with invalid execution delay."""
        invalid_config = {
            "base_units": 1000,
            "min_spread_pips": 2.0,
            "max_execution_delay_ms": -500,
        }

        with pytest.raises(ValueError, match="max_execution_delay_ms must be positive"):
            strategy_instance.validate_config(invalid_config)

    def test_validate_config_invalid_slippage(self, strategy_instance):
        """Test configuration validation with invalid slippage."""
        invalid_config = {
            "base_units": 1000,
            "min_spread_pips": 2.0,
            "max_slippage_pips": 0,
        }

        with pytest.raises(ValueError, match="max_slippage_pips must be positive"):
            strategy_instance.validate_config(invalid_config)

    def test_validate_config_invalid_profit_target(self, strategy_instance):
        """Test configuration validation with invalid profit target."""
        invalid_config = {
            "base_units": 1000,
            "min_spread_pips": 2.0,
            "profit_target_pips": 0,
        }

        with pytest.raises(ValueError, match="profit_target_pips must be positive"):
            strategy_instance.validate_config(invalid_config)

    def test_on_tick_inactive_instrument(self, strategy_instance, tick_data):
        """Test on_tick with inactive instrument."""
        tick_data.instrument = "USD_JPY"  # Not in strategy instruments
        orders = strategy_instance.on_tick(tick_data)
        assert orders == []

    def test_on_tick_updates_price(self, strategy_instance, tick_data):
        """Test on_tick updates price in detector."""
        strategy_instance.on_tick(tick_data)

        broker_id = str(strategy_instance.account.account_id)
        assert broker_id in strategy_instance.price_detector.broker_prices
        assert "EUR_USD" in strategy_instance.price_detector.broker_prices[broker_id]

    def test_on_tick_no_arbitrage_opportunity(self, strategy_instance, tick_data):
        """Test on_tick with no arbitrage opportunity."""
        # Only one broker, no arbitrage possible
        orders = strategy_instance.on_tick(tick_data)
        assert orders == []

    def test_simultaneous_order_generation(self, strategy_instance, tick_data):
        """Test simultaneous buy/sell order generation."""
        # Simulate two brokers with price difference
        strategy_instance.price_detector.update_price(
            "broker1", "EUR_USD", Decimal("1.1000"), Decimal("1.1002")
        )
        strategy_instance.price_detector.update_price(
            "broker2", "EUR_USD", Decimal("1.1005"), Decimal("1.1007")
        )

        orders = strategy_instance.on_tick(tick_data)

        # Should generate 2 orders (buy and sell)
        assert len(orders) == 2

        # Check buy order
        buy_order = next((o for o in orders if o.direction == "long"), None)
        assert buy_order is not None
        assert buy_order.instrument == "EUR_USD"
        assert buy_order.order_type == "market"
        assert buy_order.units == Decimal("1000")

        # Check sell order
        sell_order = next((o for o in orders if o.direction == "short"), None)
        assert sell_order is not None
        assert sell_order.instrument == "EUR_USD"
        assert sell_order.order_type == "market"
        assert sell_order.units == Decimal("1000")

    def test_spread_profit_calculation(self, strategy_instance):
        """Test spread profit calculation."""
        # Setup price difference
        strategy_instance.price_detector.update_price(
            "broker1", "EUR_USD", Decimal("1.1000"), Decimal("1.1002")
        )
        strategy_instance.price_detector.update_price(
            "broker2", "EUR_USD", Decimal("1.1005"), Decimal("1.1007")
        )

        pip_value = Decimal("0.0001")
        has_opportunity, buy_broker, sell_broker, spread_pips = (
            strategy_instance.price_detector.detect_arbitrage_opportunity("EUR_USD", pip_value)
        )

        assert has_opportunity is True
        # Spread = 1.1005 (best bid) - 1.1002 (best ask) = 0.0003 = 3 pips
        assert spread_pips >= Decimal("2.0")

    def test_execution_delay_handling(self, strategy_instance):
        """Test execution delay configuration."""
        assert strategy_instance.max_execution_delay_ms == 500

        # Test with different delay configuration
        new_config = strategy_instance.config.copy()
        new_config["max_execution_delay_ms"] = 1000

        assert strategy_instance.validate_config(new_config) is True

    def test_on_position_update_tracks_arbitrage_pair(self, strategy_instance, oanda_account):
        """Test position update tracking for arbitrage pairs."""
        from trading.models import Position

        # Create buy position
        buy_position = Position(
            account=oanda_account,
            strategy=strategy_instance.strategy,
            position_id="pos_buy_1",
            instrument="EUR_USD",
            direction="long",
            units=Decimal("1000"),
            entry_price=Decimal("1.1002"),
            current_price=Decimal("1.1002"),
        )

        strategy_instance.on_position_update(buy_position)

        assert "EUR_USD" in strategy_instance.active_arbitrage_pairs
        assert strategy_instance.active_arbitrage_pairs["EUR_USD"]["buy_position"] == buy_position

        # Create sell position
        sell_position = Position(
            account=oanda_account,
            strategy=strategy_instance.strategy,
            position_id="pos_sell_1",
            instrument="EUR_USD",
            direction="short",
            units=Decimal("1000"),
            entry_price=Decimal("1.1005"),
            current_price=Decimal("1.1005"),
        )

        strategy_instance.on_position_update(sell_position)

        assert strategy_instance.active_arbitrage_pairs["EUR_USD"]["sell_position"] == sell_position

    def test_on_position_update_cleans_up_closed_positions(self, strategy_instance, oanda_account):
        """Test position update cleanup when positions are closed."""
        from trading.models import Position

        # Setup active arbitrage pair with both positions
        buy_position = Position(
            account=oanda_account,
            strategy=strategy_instance.strategy,
            position_id="pos_buy_1",
            instrument="EUR_USD",
            direction="long",
            units=Decimal("1000"),
            entry_price=Decimal("1.1002"),
            current_price=Decimal("1.1002"),
        )
        strategy_instance.on_position_update(buy_position)

        sell_position = Position(
            account=oanda_account,
            strategy=strategy_instance.strategy,
            position_id="pos_sell_1",
            instrument="EUR_USD",
            direction="short",
            units=Decimal("1000"),
            entry_price=Decimal("1.1005"),
            current_price=Decimal("1.1005"),
        )
        strategy_instance.on_position_update(sell_position)

        # Verify both positions are tracked
        assert "EUR_USD" in strategy_instance.active_arbitrage_pairs
        assert "buy_position" in strategy_instance.active_arbitrage_pairs["EUR_USD"]
        assert "sell_position" in strategy_instance.active_arbitrage_pairs["EUR_USD"]

        # Close the buy position
        buy_position.closed_at = datetime.now(timezone.utc)
        strategy_instance.on_position_update(buy_position)

        # Should clean up the buy position but keep sell position
        assert "EUR_USD" in strategy_instance.active_arbitrage_pairs
        assert "buy_position" not in strategy_instance.active_arbitrage_pairs["EUR_USD"]
        assert "sell_position" in strategy_instance.active_arbitrage_pairs["EUR_USD"]

        # Close the sell position
        sell_position.closed_at = datetime.now(timezone.utc)
        strategy_instance.on_position_update(sell_position)

        # Should remove the entire pair when both positions are closed
        assert "EUR_USD" not in strategy_instance.active_arbitrage_pairs

    def test_strategy_on_tick_processing(self, strategy_instance, tick_data):
        """Test complete on_tick processing flow."""
        # First tick - just updates price
        orders1 = strategy_instance.on_tick(tick_data)
        assert len(orders1) == 0

        # Simulate second broker with price difference
        strategy_instance.price_detector.update_price(
            "broker2", "EUR_USD", Decimal("1.1005"), Decimal("1.1007")
        )

        # Second tick - should detect arbitrage
        orders2 = strategy_instance.on_tick(tick_data)
        assert len(orders2) == 2

        # Third tick - should not generate new orders (already have active pair)
        strategy_instance.active_arbitrage_pairs["EUR_USD"] = {
            "buy_position": None,
            "sell_position": None,
        }
        orders3 = strategy_instance.on_tick(tick_data)
        assert len(orders3) == 0
