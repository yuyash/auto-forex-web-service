"""
Unit tests for Swing Trading Strategy.

This module tests the Swing Trading Strategy implementation including:
- Multi-day trend detection
- Pullback entry signal generation
- Stop-loss placement
- Profit target calculation
- Strategy on_tick processing

Requirements: 5.1, 5.3
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone

import pytest

from trading.models import Position, Strategy
from trading.swing_trading_strategy import (
    PullbackDetector,
    SwingDetector,
    SwingTradingStrategy,
    TrendDetector,
)
from trading.tick_data_models import TickData

User = get_user_model()


@pytest.fixture
def user(db):  # pylint: disable=unused-argument,invalid-name
    """Create a test user."""
    return User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass",
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
def swing_strategy_config() -> dict:
    """Fixture for swing trading strategy configuration."""
    return {
        "base_units": 1000,
        "short_ma_period": 20,
        "long_ma_period": 50,
        "pullback_pips": 30,
        "stop_loss_pips": 75,
        "swing_lookback_days": 10,
    }


@pytest.fixture
def strategy_instance(db, oanda_account, swing_strategy_config):  # pylint: disable=unused-argument
    """Create a test strategy instance."""
    return Strategy.objects.create(
        account=oanda_account,
        strategy_type="swing_trading",
        config=swing_strategy_config,
        instruments=["EUR_USD"],
        is_active=True,
    )


@pytest.fixture
def swing_strategy(strategy_instance) -> SwingTradingStrategy:
    """Fixture for swing trading strategy instance."""
    return SwingTradingStrategy(strategy_instance)


@pytest.fixture
def test_position(db, oanda_account, strategy_instance):
    """Create a test position."""
    return Position.objects.create(
        account=oanda_account,
        strategy=strategy_instance,
        position_id="test_position_1",
        instrument="EUR_USD",
        direction="long",
        units=Decimal("1000"),
        entry_price=Decimal("1.1000"),
        current_price=Decimal("1.1010"),
        unrealized_pnl=Decimal("10.00"),
    )


class TestTrendDetector:
    """Test TrendDetector class."""

    def test_trend_detector_initialization(self) -> None:
        """Test trend detector initialization."""
        detector = TrendDetector(short_period=20, long_period=50)
        assert detector.short_period == 20
        assert detector.long_period == 50
        assert detector.price_history == {}

    def test_add_price(self) -> None:
        """Test adding price to history."""
        detector = TrendDetector()
        now = timezone.now()
        detector.add_price("EUR_USD", now, Decimal("1.1000"))

        assert "EUR_USD" in detector.price_history
        assert len(detector.price_history["EUR_USD"]) == 1
        assert detector.price_history["EUR_USD"][0] == (
            now,
            Decimal("1.1000"),
        )

    def test_calculate_ma_insufficient_data(self) -> None:
        """Test MA calculation with insufficient data."""
        detector = TrendDetector(short_period=20, long_period=50)
        now = timezone.now()

        # Add only 10 days of data
        for i in range(10):
            date = now - timedelta(days=10 - i)
            detector.add_price("EUR_USD", date, Decimal("1.1000"))

        ma = detector.calculate_ma("EUR_USD", 20, now)
        assert ma is None

    def test_calculate_ma_sufficient_data(self) -> None:
        """Test MA calculation with sufficient data."""
        detector = TrendDetector(short_period=5, long_period=10)
        now = timezone.now()

        # Add 10 days of data with different prices each day
        for i in range(10):
            date = now - timedelta(days=9 - i)
            # Add one price per day at noon
            price = Decimal("1.1000") + Decimal(str(i * 0.0001))
            detector.add_price(
                "EUR_USD",
                date.replace(hour=12, minute=0, second=0, microsecond=0),
                price,
            )

        ma = detector.calculate_ma("EUR_USD", 5, now)
        assert ma is not None
        assert isinstance(ma, Decimal)

    def test_detect_trend_bullish(self) -> None:
        """Test bullish trend detection."""
        detector = TrendDetector(short_period=5, long_period=10)
        now = timezone.now()

        # Create uptrend: prices increasing over time
        for i in range(15):
            date = now - timedelta(days=14 - i)
            price = Decimal("1.1000") + Decimal(str(i * 0.001))
            detector.add_price(
                "EUR_USD",
                date.replace(hour=12, minute=0, second=0, microsecond=0),
                price,
            )

        trend = detector.detect_trend("EUR_USD", now)
        assert trend == "bullish"

    def test_detect_trend_bearish(self) -> None:
        """Test bearish trend detection."""
        detector = TrendDetector(short_period=5, long_period=10)
        now = timezone.now()

        # Create downtrend: prices decreasing over time
        for i in range(15):
            date = now - timedelta(days=14 - i)
            price = Decimal("1.1000") - Decimal(str(i * 0.001))
            detector.add_price(
                "EUR_USD",
                date.replace(hour=12, minute=0, second=0, microsecond=0),
                price,
            )

        trend = detector.detect_trend("EUR_USD", now)
        assert trend == "bearish"

    def test_detect_trend_insufficient_data(self) -> None:
        """Test trend detection with insufficient data."""
        detector = TrendDetector(short_period=20, long_period=50)
        now = timezone.now()

        # Add only 10 days
        for i in range(10):
            date = now - timedelta(days=10 - i)
            detector.add_price("EUR_USD", date, Decimal("1.1000"))

        trend = detector.detect_trend("EUR_USD", now)
        assert trend is None


class TestSwingDetector:
    """Test SwingDetector class."""

    def test_swing_detector_initialization(self) -> None:
        """Test swing detector initialization."""
        detector = SwingDetector(lookback_days=10)
        assert detector.lookback_days == 10
        assert detector.price_history == {}

    def test_add_price(self) -> None:
        """Test adding price to history."""
        detector = SwingDetector()
        now = timezone.now()
        detector.add_price("EUR_USD", now, Decimal("1.1000"))

        assert "EUR_USD" in detector.price_history
        assert len(detector.price_history["EUR_USD"]) == 1

    def test_get_swing_high(self) -> None:
        """Test getting swing high."""
        detector = SwingDetector(lookback_days=5)
        now = timezone.now()

        # Add prices over 5 days
        prices = [
            Decimal("1.1000"),
            Decimal("1.1050"),
            Decimal("1.1100"),
            Decimal("1.1075"),
            Decimal("1.1025"),
        ]

        for i, price in enumerate(prices):
            date = now - timedelta(days=5 - i)
            detector.add_price("EUR_USD", date, price)

        swing_high = detector.get_swing_high("EUR_USD", now)
        assert swing_high == Decimal("1.1100")

    def test_get_swing_low(self) -> None:
        """Test getting swing low."""
        detector = SwingDetector(lookback_days=5)
        now = timezone.now()

        # Add prices over 5 days
        prices = [
            Decimal("1.1000"),
            Decimal("1.1050"),
            Decimal("1.1100"),
            Decimal("1.1075"),
            Decimal("1.1025"),
        ]

        for i, price in enumerate(prices):
            date = now - timedelta(days=5 - i)
            detector.add_price("EUR_USD", date, price)

        swing_low = detector.get_swing_low("EUR_USD", now)
        assert swing_low == Decimal("1.1000")

    def test_get_swing_no_data(self) -> None:
        """Test getting swing with no data."""
        detector = SwingDetector()
        now = timezone.now()

        swing_high = detector.get_swing_high("EUR_USD", now)
        assert swing_high is None

        swing_low = detector.get_swing_low("EUR_USD", now)
        assert swing_low is None


class TestPullbackDetector:
    """Test PullbackDetector class."""

    def test_pullback_detector_initialization(self) -> None:
        """Test pullback detector initialization."""
        detector = PullbackDetector(pullback_pips=Decimal("30"))
        assert detector.pullback_pips == Decimal("30")
        assert detector.recent_high == {}
        assert detector.recent_low == {}

    def test_update_extremes(self) -> None:
        """Test updating recent high and low."""
        detector = PullbackDetector()

        detector.update_extremes("EUR_USD", Decimal("1.1000"))
        assert detector.recent_high["EUR_USD"] == Decimal("1.1000")
        assert detector.recent_low["EUR_USD"] == Decimal("1.1000")

        detector.update_extremes("EUR_USD", Decimal("1.1050"))
        assert detector.recent_high["EUR_USD"] == Decimal("1.1050")
        assert detector.recent_low["EUR_USD"] == Decimal("1.1000")

        detector.update_extremes("EUR_USD", Decimal("1.0950"))
        assert detector.recent_high["EUR_USD"] == Decimal("1.1050")
        assert detector.recent_low["EUR_USD"] == Decimal("1.0950")

    def test_is_bullish_pullback(self) -> None:
        """Test bullish pullback detection."""
        detector = PullbackDetector(pullback_pips=Decimal("30"))

        # Set recent high
        detector.update_extremes("EUR_USD", Decimal("1.1000"))
        detector.update_extremes("EUR_USD", Decimal("1.1050"))

        # Price pulls back 30 pips (0.0030)
        current_price = Decimal("1.1020")
        is_pullback = detector.is_bullish_pullback("EUR_USD", current_price)
        assert is_pullback is True

        # Price pulls back only 10 pips
        current_price = Decimal("1.1040")
        is_pullback = detector.is_bullish_pullback("EUR_USD", current_price)
        assert is_pullback is False

    def test_is_bearish_pullback(self) -> None:
        """Test bearish pullback detection."""
        detector = PullbackDetector(pullback_pips=Decimal("30"))

        # Set recent low
        detector.update_extremes("EUR_USD", Decimal("1.1000"))
        detector.update_extremes("EUR_USD", Decimal("1.0950"))

        # Price pulls back 30 pips (0.0030)
        current_price = Decimal("1.0980")
        is_pullback = detector.is_bearish_pullback("EUR_USD", current_price)
        assert is_pullback is True

        # Price pulls back only 10 pips
        current_price = Decimal("1.0960")
        is_pullback = detector.is_bearish_pullback("EUR_USD", current_price)
        assert is_pullback is False

    def test_reset_extremes(self) -> None:
        """Test resetting extremes."""
        detector = PullbackDetector()

        detector.update_extremes("EUR_USD", Decimal("1.1000"))
        assert "EUR_USD" in detector.recent_high
        assert "EUR_USD" in detector.recent_low

        detector.reset_extremes("EUR_USD")
        assert "EUR_USD" not in detector.recent_high
        assert "EUR_USD" not in detector.recent_low


class TestSwingTradingStrategy:
    """Test SwingTradingStrategy class."""

    def test_strategy_initialization(self, swing_strategy: SwingTradingStrategy) -> None:
        """Test strategy initialization."""
        assert swing_strategy.base_units == Decimal("1000")
        assert swing_strategy.short_ma_period == 20
        assert swing_strategy.long_ma_period == 50
        assert swing_strategy.pullback_pips == Decimal("30")
        assert swing_strategy.stop_loss_pips == Decimal("75")
        assert swing_strategy.swing_lookback_days == 10

    def test_on_tick_no_trend(self, swing_strategy: SwingTradingStrategy) -> None:
        """Test on_tick with no trend detected."""
        now = timezone.now()
        tick = TickData(
            account=swing_strategy.account,
            instrument="EUR_USD",
            timestamp=now,
            bid=Decimal("1.1000"),
            ask=Decimal("1.1002"),
            mid=Decimal("1.1001"),
            spread=Decimal("0.0002"),
        )

        orders = swing_strategy.on_tick(tick)
        assert len(orders) == 0

    def test_on_tick_bullish_pullback_entry(self, swing_strategy: SwingTradingStrategy) -> None:
        """Test on_tick with bullish pullback entry."""
        now = timezone.now()

        # Build trend history (bullish)
        for i in range(60):
            date = now - timedelta(days=59 - i)
            price = Decimal("1.0800") + Decimal(str(i * 0.001))
            tick_time = date.replace(hour=12, minute=0, second=0, microsecond=0)
            swing_strategy.trend_detector.add_price("EUR_USD", tick_time, price)
            swing_strategy.swing_detector.add_price("EUR_USD", tick_time, price)

        # Set up pullback scenario
        swing_strategy.pullback_detector.update_extremes("EUR_USD", Decimal("1.1400"))

        # Current price is pulled back 30+ pips
        tick = TickData(
            account=swing_strategy.account,
            instrument="EUR_USD",
            timestamp=now,
            bid=Decimal("1.1368"),
            ask=Decimal("1.1370"),
            mid=Decimal("1.1369"),
            spread=Decimal("0.0002"),
        )

        orders = swing_strategy.on_tick(tick)
        assert len(orders) == 1
        assert orders[0].direction == "long"
        assert orders[0].units == Decimal("1000")

    def test_on_tick_bearish_pullback_entry(self, swing_strategy: SwingTradingStrategy) -> None:
        """Test on_tick with bearish pullback entry."""
        now = timezone.now()

        # Build trend history (bearish)
        for i in range(60):
            date = now - timedelta(days=59 - i)
            price = Decimal("1.1400") - Decimal(str(i * 0.001))
            tick_time = date.replace(hour=12, minute=0, second=0, microsecond=0)
            swing_strategy.trend_detector.add_price("EUR_USD", tick_time, price)
            swing_strategy.swing_detector.add_price("EUR_USD", tick_time, price)

        # Set up pullback scenario
        swing_strategy.pullback_detector.update_extremes("EUR_USD", Decimal("1.0800"))

        # Current price is pulled back 30+ pips
        tick = TickData(
            account=swing_strategy.account,
            instrument="EUR_USD",
            timestamp=now,
            bid=Decimal("1.0830"),
            ask=Decimal("1.0832"),
            mid=Decimal("1.0831"),
            spread=Decimal("0.0002"),
        )

        orders = swing_strategy.on_tick(tick)
        assert len(orders) == 1
        assert orders[0].direction == "short"
        assert orders[0].units == Decimal("1000")

    def test_on_tick_with_existing_position(
        self,
        swing_strategy: SwingTradingStrategy,
        test_position: Position,
    ) -> None:
        """Test on_tick with existing position."""
        test_position.strategy = swing_strategy.strategy
        test_position.closed_at = None
        test_position.save()

        now = timezone.now()
        tick = TickData(
            account=swing_strategy.account,
            instrument="EUR_USD",
            timestamp=now,
            bid=Decimal("1.1000"),
            ask=Decimal("1.1002"),
            mid=Decimal("1.1001"),
            spread=Decimal("0.0002"),
        )

        orders = swing_strategy.on_tick(tick)
        assert len(orders) == 0

    def test_stop_loss_placement(self, swing_strategy: SwingTradingStrategy) -> None:
        """Test stop-loss placement."""
        now = timezone.now()

        # Build bullish trend
        for i in range(60):
            date = now - timedelta(days=59 - i)
            price = Decimal("1.0800") + Decimal(str(i * 0.001))
            tick_time = date.replace(hour=12, minute=0, second=0, microsecond=0)
            swing_strategy.trend_detector.add_price("EUR_USD", tick_time, price)
            swing_strategy.swing_detector.add_price("EUR_USD", tick_time, price)

        swing_strategy.pullback_detector.update_extremes("EUR_USD", Decimal("1.1400"))

        tick = TickData(
            account=swing_strategy.account,
            instrument="EUR_USD",
            timestamp=now,
            bid=Decimal("1.1368"),
            ask=Decimal("1.1370"),
            mid=Decimal("1.1369"),
            spread=Decimal("0.0002"),
        )

        orders = swing_strategy.on_tick(tick)
        assert len(orders) == 1

        order = orders[0]
        assert order.stop_loss is not None

        # Stop loss should be 75 pips below entry for long
        expected_stop = tick.mid - (Decimal("75") * Decimal("0.0001"))
        assert order.stop_loss == expected_stop

    def test_profit_target_calculation(self, swing_strategy: SwingTradingStrategy) -> None:
        """Test profit target calculation."""
        now = timezone.now()

        # Build bullish trend with swing high
        for i in range(60):
            date = now - timedelta(days=59 - i)
            price = Decimal("1.0800") + Decimal(str(i * 0.001))
            tick_time = date.replace(hour=12, minute=0, second=0, microsecond=0)
            swing_strategy.trend_detector.add_price("EUR_USD", tick_time, price)
            swing_strategy.swing_detector.add_price("EUR_USD", tick_time, price)

        # Add a clear swing high
        swing_high_date = now - timedelta(days=5)
        swing_strategy.swing_detector.add_price("EUR_USD", swing_high_date, Decimal("1.1500"))

        swing_strategy.pullback_detector.update_extremes("EUR_USD", Decimal("1.1400"))

        tick = TickData(
            account=swing_strategy.account,
            instrument="EUR_USD",
            timestamp=now,
            bid=Decimal("1.1368"),
            ask=Decimal("1.1370"),
            mid=Decimal("1.1369"),
            spread=Decimal("0.0002"),
        )

        orders = swing_strategy.on_tick(tick)
        assert len(orders) == 1

        order = orders[0]
        assert order.take_profit is not None
        # Should target swing high
        assert order.take_profit == Decimal("1.1500")

    def test_on_position_update(
        self,
        swing_strategy: SwingTradingStrategy,
        test_position: Position,
    ) -> None:
        """Test on_position_update."""
        test_position.closed_at = timezone.now()
        swing_strategy.on_position_update(test_position)
        # Should not raise any errors

    def test_validate_config_valid(self, swing_strategy_config: dict) -> None:
        """Test validate_config with valid configuration."""
        strategy = SwingTradingStrategy.__new__(SwingTradingStrategy)
        result = strategy.validate_config(swing_strategy_config)
        assert result is True

    def test_validate_config_invalid_base_units(self) -> None:
        """Test validate_config with invalid base units."""
        strategy = SwingTradingStrategy.__new__(SwingTradingStrategy)
        config = {"base_units": -1000}

        with pytest.raises(ValueError, match="base_units must be positive"):
            strategy.validate_config(config)

    def test_validate_config_invalid_ma_periods(self) -> None:
        """Test validate_config with invalid MA periods."""
        strategy = SwingTradingStrategy.__new__(SwingTradingStrategy)

        # Long MA not greater than short MA
        config = {"short_ma_period": 50, "long_ma_period": 20}

        with pytest.raises(
            ValueError,
            match="long_ma_period must be greater than short_ma_period",
        ):
            strategy.validate_config(config)

    def test_validate_config_invalid_stop_loss(self) -> None:
        """Test validate_config with invalid stop loss."""
        strategy = SwingTradingStrategy.__new__(SwingTradingStrategy)

        # Stop loss too small for swing trading
        config = {"stop_loss_pips": 30}

        with pytest.raises(
            ValueError,
            match="stop_loss_pips must be at least 50",
        ):
            strategy.validate_config(config)

    def test_validate_config_invalid_pullback_pips(self) -> None:
        """Test validate_config with invalid pullback pips."""
        strategy = SwingTradingStrategy.__new__(SwingTradingStrategy)
        config = {"pullback_pips": -10}

        with pytest.raises(ValueError, match="pullback_pips must be positive"):
            strategy.validate_config(config)

    def test_validate_config_invalid_swing_lookback(self) -> None:
        """Test validate_config with invalid swing lookback."""
        strategy = SwingTradingStrategy.__new__(SwingTradingStrategy)
        config = {"swing_lookback_days": 0}

        with pytest.raises(ValueError, match="swing_lookback_days must be positive"):
            strategy.validate_config(config)
