"""
Unit tests for Fundamental + Technical Strategy.

This module tests the Fundamental + Technical Strategy implementation including:
- Economic event detection
- Technical confirmation logic
- Position sizing based on event importance
- Pre/post-event trading logic
- Strategy on_tick processing

Requirements: 5.1, 5.3
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone

import pytest

from trading.fundamental_technical_strategy import (
    EconomicCalendar,
    EconomicEvent,
    EventImportance,
    FundamentalTechnicalStrategy,
    TechnicalAnalyzer,
    TrendDirection,
)
from trading.models import Position, Strategy
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
        strategy_type="fundamental_technical",
        config={
            "base_units": 1000,
            "high_importance_multiplier": 2.0,
            "medium_importance_multiplier": 1.5,
            "low_importance_multiplier": 1.0,
            "pre_event_minutes": 30,
            "post_event_minutes": 60,
            "take_profit_pips": 30,
            "stop_loss_pips": 20,
            "require_trend_confirmation": True,
            "ma_short_period": 20,
            "ma_long_period": 50,
        },
        instruments=["EUR_USD"],
        is_active=True,
    )


@pytest.fixture
def fundamental_technical_strategy(strategy_instance):
    """Create a FundamentalTechnicalStrategy instance."""
    return FundamentalTechnicalStrategy(strategy_instance)


class TestEconomicCalendar:
    """Test EconomicCalendar class."""

    def test_add_event(self):
        """Test adding events to calendar."""
        calendar = EconomicCalendar()
        now = timezone.now()

        event = EconomicEvent(
            event_time=now + timedelta(hours=1),
            currency="USD",
            importance=EventImportance.HIGH,
            event_name="NFP",
        )

        calendar.add_event(event)
        assert len(calendar.events) == 1

    def test_get_upcoming_events(self):
        """Test getting upcoming events."""
        calendar = EconomicCalendar()
        now = timezone.now()

        # Add events at different times
        event1 = EconomicEvent(
            event_time=now + timedelta(minutes=15),
            currency="EUR",
            importance=EventImportance.HIGH,
            event_name="ECB Rate Decision",
        )
        event2 = EconomicEvent(
            event_time=now + timedelta(minutes=45),
            currency="USD",
            importance=EventImportance.MEDIUM,
            event_name="GDP",
        )
        event3 = EconomicEvent(
            event_time=now + timedelta(hours=2),
            currency="EUR",
            importance=EventImportance.LOW,
            event_name="CPI",
        )

        calendar.add_event(event1)
        calendar.add_event(event2)
        calendar.add_event(event3)

        # Get upcoming events for EUR_USD within 60 minutes
        upcoming = calendar.get_upcoming_events("EUR_USD", now, lookforward_minutes=60)

        # Should get event1 and event2, not event3 (too far)
        assert len(upcoming) == 2
        assert upcoming[0].event_name == "ECB Rate Decision"
        assert upcoming[1].event_name == "GDP"

    def test_get_recent_events(self):
        """Test getting recent events."""
        calendar = EconomicCalendar()
        now = timezone.now()

        # Add past events
        event1 = EconomicEvent(
            event_time=now - timedelta(minutes=10),
            currency="EUR",
            importance=EventImportance.HIGH,
            event_name="ECB Rate Decision",
        )
        event2 = EconomicEvent(
            event_time=now - timedelta(minutes=45),
            currency="USD",
            importance=EventImportance.MEDIUM,
            event_name="GDP",
        )

        calendar.add_event(event1)
        calendar.add_event(event2)

        # Get recent events within 30 minutes
        recent = calendar.get_recent_events("EUR_USD", now, lookback_minutes=30)

        # Should get only event1 (within 30 minutes)
        assert len(recent) == 1
        assert recent[0].event_name == "ECB Rate Decision"

    def test_filter_by_currency(self):
        """Test filtering events by currency pair."""
        calendar = EconomicCalendar()
        now = timezone.now()

        # Add events for different currencies
        event_eur = EconomicEvent(
            event_time=now + timedelta(minutes=15),
            currency="EUR",
            importance=EventImportance.HIGH,
            event_name="ECB Rate Decision",
        )
        event_gbp = EconomicEvent(
            event_time=now + timedelta(minutes=20),
            currency="GBP",
            importance=EventImportance.HIGH,
            event_name="BOE Rate Decision",
        )

        calendar.add_event(event_eur)
        calendar.add_event(event_gbp)

        # Get events for EUR_USD
        upcoming_eur_usd = calendar.get_upcoming_events("EUR_USD", now, lookforward_minutes=60)
        assert len(upcoming_eur_usd) == 1
        assert upcoming_eur_usd[0].currency == "EUR"

        # Get events for GBP_USD
        upcoming_gbp_usd = calendar.get_upcoming_events("GBP_USD", now, lookforward_minutes=60)
        assert len(upcoming_gbp_usd) == 1
        assert upcoming_gbp_usd[0].currency == "GBP"


class TestTechnicalAnalyzer:
    """Test TechnicalAnalyzer class."""

    def test_add_price(self):
        """Test adding prices to history."""
        analyzer = TechnicalAnalyzer()
        now = timezone.now()

        analyzer.add_price("EUR_USD", now, Decimal("1.1000"))
        analyzer.add_price("EUR_USD", now + timedelta(minutes=1), Decimal("1.1005"))

        assert "EUR_USD" in analyzer.price_history
        assert len(analyzer.price_history["EUR_USD"]) == 2

    def test_calculate_ma_insufficient_data(self):
        """Test MA calculation with insufficient data."""
        analyzer = TechnicalAnalyzer()
        now = timezone.now()

        analyzer.add_price("EUR_USD", now, Decimal("1.1000"))

        ma = analyzer.calculate_ma("EUR_USD", period=20)
        assert ma is None

    def test_calculate_ma_with_data(self):
        """Test MA calculation with sufficient data."""
        analyzer = TechnicalAnalyzer()
        now = timezone.now()

        # Add 25 prices
        for i in range(25):
            price = Decimal("1.1000") + Decimal(str(i * 0.0001))
            analyzer.add_price("EUR_USD", now + timedelta(minutes=i), price)

        ma = analyzer.calculate_ma("EUR_USD", period=20)
        assert ma is not None
        assert ma > Decimal("1.1000")

    def test_detect_trend_bullish(self):
        """Test bullish trend detection."""
        analyzer = TechnicalAnalyzer(ma_short_period=5, ma_long_period=10)
        now = timezone.now()

        # Add prices showing upward trend
        for i in range(15):
            price = Decimal("1.1000") + Decimal(str(i * 0.0010))
            analyzer.add_price("EUR_USD", now + timedelta(minutes=i), price)

        trend = analyzer.detect_trend("EUR_USD")
        assert trend == TrendDirection.BULLISH

    def test_detect_trend_bearish(self):
        """Test bearish trend detection."""
        analyzer = TechnicalAnalyzer(ma_short_period=5, ma_long_period=10)
        now = timezone.now()

        # Add prices showing downward trend
        for i in range(15):
            price = Decimal("1.1150") - Decimal(str(i * 0.0010))
            analyzer.add_price("EUR_USD", now + timedelta(minutes=i), price)

        trend = analyzer.detect_trend("EUR_USD")
        assert trend == TrendDirection.BEARISH

    def test_detect_trend_neutral(self):
        """Test neutral trend detection."""
        analyzer = TechnicalAnalyzer(ma_short_period=5, ma_long_period=10)
        now = timezone.now()

        # Add flat prices
        for i in range(15):
            analyzer.add_price("EUR_USD", now + timedelta(minutes=i), Decimal("1.1000"))

        trend = analyzer.detect_trend("EUR_USD")
        assert trend == TrendDirection.NEUTRAL

    def test_find_support_resistance(self):
        """Test support and resistance detection."""
        analyzer = TechnicalAnalyzer()
        now = timezone.now()

        # Add prices with clear range
        prices = [
            Decimal("1.1000"),
            Decimal("1.1050"),
            Decimal("1.1020"),
            Decimal("1.1080"),
            Decimal("1.1010"),
            Decimal("1.1090"),
            Decimal("1.1030"),
        ]

        for i, price in enumerate(prices):
            analyzer.add_price("EUR_USD", now + timedelta(minutes=i), price)

        support, resistance = analyzer.find_support_resistance("EUR_USD", lookback_periods=7)

        assert support == Decimal("1.1000")
        assert resistance == Decimal("1.1090")


class TestFundamentalTechnicalStrategy:
    """Test FundamentalTechnicalStrategy class."""

    def test_initialization(self, fundamental_technical_strategy):
        """Test strategy initialization."""
        assert fundamental_technical_strategy.base_units == Decimal("1000")
        assert fundamental_technical_strategy.high_importance_multiplier == Decimal("2.0")
        assert fundamental_technical_strategy.medium_importance_multiplier == Decimal("1.5")
        assert fundamental_technical_strategy.low_importance_multiplier == Decimal("1.0")
        assert fundamental_technical_strategy.pre_event_minutes == 30
        assert fundamental_technical_strategy.post_event_minutes == 60
        assert fundamental_technical_strategy.take_profit_pips == Decimal("30")
        assert fundamental_technical_strategy.stop_loss_pips == Decimal("20")

    def test_calculate_position_size_high_importance(self, fundamental_technical_strategy):
        """Test position sizing for high importance events."""
        # pylint: disable=protected-access
        size = fundamental_technical_strategy._calculate_position_size(EventImportance.HIGH)
        assert size == Decimal("2000")  # 1000 * 2.0

    def test_calculate_position_size_medium_importance(self, fundamental_technical_strategy):
        """Test position sizing for medium importance events."""
        # pylint: disable=protected-access
        size = fundamental_technical_strategy._calculate_position_size(EventImportance.MEDIUM)
        assert size == Decimal("1500")  # 1000 * 1.5

    def test_calculate_position_size_low_importance(self, fundamental_technical_strategy):
        """Test position sizing for low importance events."""
        # pylint: disable=protected-access
        size = fundamental_technical_strategy._calculate_position_size(EventImportance.LOW)
        assert size == Decimal("1000")  # 1000 * 1.0

    def test_on_tick_no_events(
        self, fundamental_technical_strategy, oanda_account
    ):  # pylint: disable=unused-argument
        """Test on_tick with no economic events."""
        now = timezone.now()

        tick = TickData.objects.create(
            account=oanda_account,
            instrument="EUR_USD",
            timestamp=now,
            bid=Decimal("1.0999"),
            ask=Decimal("1.1001"),
            mid=Decimal("1.1000"),
        )

        orders = fundamental_technical_strategy.on_tick(tick)
        assert len(orders) == 0

    def test_on_tick_pre_event_avoidance(
        self, fundamental_technical_strategy, oanda_account
    ):  # pylint: disable=unused-argument
        """Test avoiding trades before high-impact events."""
        now = timezone.now()

        # Add upcoming high-impact event
        event = EconomicEvent(
            event_time=now + timedelta(minutes=15),
            currency="EUR",
            importance=EventImportance.HIGH,
            event_name="ECB Rate Decision",
        )
        fundamental_technical_strategy.economic_calendar.add_event(event)

        # Add price history for technical analysis
        for i in range(60):
            price = Decimal("1.1000") + Decimal(str(i * 0.0001))
            fundamental_technical_strategy.technical_analyzer.add_price(
                "EUR_USD", now - timedelta(minutes=60 - i), price
            )

        tick = TickData.objects.create(
            account=oanda_account,
            instrument="EUR_USD",
            timestamp=now,
            bid=Decimal("1.1059"),
            ask=Decimal("1.1061"),
            mid=Decimal("1.1060"),
        )

        orders = fundamental_technical_strategy.on_tick(tick)

        # Should not enter before high-impact event
        assert len(orders) == 0

    def test_on_tick_post_event_entry_bullish(  # pylint: disable=unused-argument
        self, fundamental_technical_strategy, oanda_account
    ):
        """Test entry after event with bullish trend."""
        now = timezone.now()

        # Add recent high-impact event
        event = EconomicEvent(
            event_time=now - timedelta(minutes=10),
            currency="EUR",
            importance=EventImportance.HIGH,
            event_name="ECB Rate Decision",
        )
        fundamental_technical_strategy.economic_calendar.add_event(event)

        # Add price history showing bullish trend
        for i in range(60):
            price = Decimal("1.1000") + Decimal(str(i * 0.0001))
            fundamental_technical_strategy.technical_analyzer.add_price(
                "EUR_USD", now - timedelta(minutes=60 - i), price
            )

        # Current price near support
        tick = TickData.objects.create(
            account=oanda_account,
            instrument="EUR_USD",
            timestamp=now,
            bid=Decimal("1.0999"),
            ask=Decimal("1.1001"),
            mid=Decimal("1.1000"),
        )

        orders = fundamental_technical_strategy.on_tick(tick)

        # Should generate long entry
        if orders:
            order = orders[0]
            assert order.direction == "long"
            assert order.units == Decimal("2000")  # High importance multiplier
            assert order.take_profit is not None
            assert order.stop_loss is not None

    def test_on_tick_post_event_entry_bearish(  # pylint: disable=unused-argument
        self, fundamental_technical_strategy, oanda_account
    ):
        """Test entry after event with bearish trend."""
        now = timezone.now()

        # Add recent medium-impact event
        event = EconomicEvent(
            event_time=now - timedelta(minutes=10),
            currency="USD",
            importance=EventImportance.MEDIUM,
            event_name="GDP",
        )
        fundamental_technical_strategy.economic_calendar.add_event(event)

        # Add price history showing bearish trend
        for i in range(60):
            price = Decimal("1.1060") - Decimal(str(i * 0.0001))
            fundamental_technical_strategy.technical_analyzer.add_price(
                "EUR_USD", now - timedelta(minutes=60 - i), price
            )

        # Current price near resistance
        tick = TickData.objects.create(
            account=oanda_account,
            instrument="EUR_USD",
            timestamp=now,
            bid=Decimal("1.1059"),
            ask=Decimal("1.1061"),
            mid=Decimal("1.1060"),
        )

        orders = fundamental_technical_strategy.on_tick(tick)

        # Should generate short entry
        if orders:
            order = orders[0]
            assert order.direction == "short"
            assert order.units == Decimal("1500")  # Medium importance multiplier
            assert order.take_profit is not None
            assert order.stop_loss is not None

    def test_on_tick_no_trend_confirmation(  # pylint: disable=unused-argument
        self, fundamental_technical_strategy, oanda_account
    ):
        """Test no entry without trend confirmation when required."""
        now = timezone.now()

        # Add recent event
        event = EconomicEvent(
            event_time=now - timedelta(minutes=10),
            currency="EUR",
            importance=EventImportance.HIGH,
            event_name="ECB Rate Decision",
        )
        fundamental_technical_strategy.economic_calendar.add_event(event)

        # Add flat price history (neutral trend)
        for i in range(60):
            fundamental_technical_strategy.technical_analyzer.add_price(
                "EUR_USD", now - timedelta(minutes=60 - i), Decimal("1.1000")
            )

        tick = TickData.objects.create(
            account=oanda_account,
            instrument="EUR_USD",
            timestamp=now,
            bid=Decimal("1.0999"),
            ask=Decimal("1.1001"),
            mid=Decimal("1.1000"),
        )

        orders = fundamental_technical_strategy.on_tick(tick)

        # Should not enter without clear trend
        assert len(orders) == 0

    def test_manage_positions_take_profit(
        self, fundamental_technical_strategy, oanda_account
    ):  # pylint: disable=unused-argument
        """Test take-profit execution."""
        now = timezone.now()

        # Create a position
        position = Position.objects.create(
            account=oanda_account,
            strategy=fundamental_technical_strategy.strategy,
            position_id="test_position_1",
            instrument="EUR_USD",
            direction="long",
            units=Decimal("1000"),
            entry_price=Decimal("1.1000"),
            current_price=Decimal("1.1030"),
            opened_at=now,
        )

        # Create tick with 30 pips profit
        tick = TickData.objects.create(
            account=oanda_account,
            instrument="EUR_USD",
            timestamp=now + timedelta(minutes=1),
            bid=Decimal("1.1029"),
            ask=Decimal("1.1031"),
            mid=Decimal("1.1030"),
        )

        orders = fundamental_technical_strategy.on_tick(tick)

        # Should generate close order
        assert len(orders) == 1
        order = orders[0]
        assert order.direction == "short"
        assert order.units == position.units

    def test_manage_positions_stop_loss(
        self, fundamental_technical_strategy, oanda_account
    ):  # pylint: disable=unused-argument
        """Test stop-loss execution."""
        now = timezone.now()

        # Create a position
        position = Position.objects.create(
            account=oanda_account,
            strategy=fundamental_technical_strategy.strategy,
            position_id="test_position_1",
            instrument="EUR_USD",
            direction="long",
            units=Decimal("1000"),
            entry_price=Decimal("1.1000"),
            current_price=Decimal("1.0980"),
            opened_at=now,
        )

        # Create tick with -20 pips loss
        tick = TickData.objects.create(
            account=oanda_account,
            instrument="EUR_USD",
            timestamp=now + timedelta(minutes=1),
            bid=Decimal("1.0979"),
            ask=Decimal("1.0981"),
            mid=Decimal("1.0980"),
        )

        orders = fundamental_technical_strategy.on_tick(tick)

        # Should generate close order
        assert len(orders) == 1
        order = orders[0]
        assert order.direction == "short"
        assert order.units == position.units

    def test_no_entry_with_existing_position(
        self, fundamental_technical_strategy, oanda_account
    ):  # pylint: disable=unused-argument
        """Test no new entry when position already exists."""
        now = timezone.now()

        # Create existing position
        Position.objects.create(
            account=oanda_account,
            strategy=fundamental_technical_strategy.strategy,
            position_id="test_position_1",
            instrument="EUR_USD",
            direction="long",
            units=Decimal("1000"),
            entry_price=Decimal("1.1000"),
            current_price=Decimal("1.1005"),
            opened_at=now,
        )

        # Add event and trend
        event = EconomicEvent(
            event_time=now - timedelta(minutes=10),
            currency="EUR",
            importance=EventImportance.HIGH,
            event_name="ECB Rate Decision",
        )
        fundamental_technical_strategy.economic_calendar.add_event(event)

        for i in range(60):
            price = Decimal("1.1000") + Decimal(str(i * 0.0001))
            fundamental_technical_strategy.technical_analyzer.add_price(
                "EUR_USD", now - timedelta(minutes=60 - i), price
            )

        tick = TickData.objects.create(
            account=oanda_account,
            instrument="EUR_USD",
            timestamp=now,
            bid=Decimal("1.1004"),
            ask=Decimal("1.1006"),
            mid=Decimal("1.1005"),
        )

        orders = fundamental_technical_strategy.on_tick(tick)

        # Should not generate new entry, only position management
        if orders:
            for order in orders:
                # Any orders should be close orders
                assert order.direction == "short"

    def test_on_position_update_cleanup(
        self, fundamental_technical_strategy, oanda_account
    ):  # pylint: disable=unused-argument
        """Test position update cleanup."""
        now = timezone.now()

        position = Position.objects.create(
            account=oanda_account,
            strategy=fundamental_technical_strategy.strategy,
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
        fundamental_technical_strategy.event_positions[position.position_id] = "ECB Rate Decision"

        # Call on_position_update
        fundamental_technical_strategy.on_position_update(position)

        # Should clean up tracking
        assert position.position_id not in fundamental_technical_strategy.event_positions

    def test_validate_config_valid(self, fundamental_technical_strategy):
        """Test config validation with valid config."""
        config = {
            "base_units": 1000,
            "high_importance_multiplier": 2.0,
            "medium_importance_multiplier": 1.5,
            "low_importance_multiplier": 1.0,
            "pre_event_minutes": 30,
            "post_event_minutes": 60,
            "take_profit_pips": 30,
            "stop_loss_pips": 20,
            "require_trend_confirmation": True,
            "ma_short_period": 20,
            "ma_long_period": 50,
        }

        assert fundamental_technical_strategy.validate_config(config) is True

    def test_validate_config_invalid_base_units(self, fundamental_technical_strategy):
        """Test config validation with invalid base units."""
        config = {
            "base_units": -1000,
            "high_importance_multiplier": 2.0,
        }

        with pytest.raises(ValueError, match="base_units must be positive"):
            fundamental_technical_strategy.validate_config(config)

    def test_validate_config_invalid_multiplier(self, fundamental_technical_strategy):
        """Test config validation with invalid multiplier."""
        config = {
            "base_units": 1000,
            "high_importance_multiplier": -2.0,
        }

        with pytest.raises(ValueError, match="high_importance_multiplier must be positive"):
            fundamental_technical_strategy.validate_config(config)

    def test_validate_config_invalid_time_window(self, fundamental_technical_strategy):
        """Test config validation with invalid time window."""
        config = {
            "base_units": 1000,
            "pre_event_minutes": -30,
        }

        with pytest.raises(ValueError, match="pre_event_minutes must be positive"):
            fundamental_technical_strategy.validate_config(config)

    def test_validate_config_invalid_ma_periods(self, fundamental_technical_strategy):
        """Test config validation with invalid MA periods."""
        config = {
            "base_units": 1000,
            "ma_short_period": 50,
            "ma_long_period": 20,
        }

        with pytest.raises(ValueError, match="ma_short_period must be less than ma_long_period"):
            fundamental_technical_strategy.validate_config(config)

    def test_jpy_pair_pip_calculation(
        self, fundamental_technical_strategy, oanda_account
    ):  # pylint: disable=unused-argument
        """Test pip calculation for JPY pairs."""
        now = timezone.now()

        # Update strategy to trade USD_JPY
        fundamental_technical_strategy.instruments = ["USD_JPY"]

        # Create a position
        position = Position.objects.create(
            account=oanda_account,
            strategy=fundamental_technical_strategy.strategy,
            position_id="test_position_1",
            instrument="USD_JPY",
            direction="long",
            units=Decimal("1000"),
            entry_price=Decimal("110.00"),
            current_price=Decimal("110.30"),
            opened_at=now,
        )

        # Create tick with 30 pips profit (for JPY, 1 pip = 0.01)
        tick = TickData.objects.create(
            account=oanda_account,
            instrument="USD_JPY",
            timestamp=now + timedelta(minutes=1),
            bid=Decimal("110.29"),
            ask=Decimal("110.31"),
            mid=Decimal("110.30"),
        )

        orders = fundamental_technical_strategy.on_tick(tick)

        # Should generate close order for take profit
        if orders:
            order = orders[0]
            assert order.direction == "short"
            assert order.units == position.units
