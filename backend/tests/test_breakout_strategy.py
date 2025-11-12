"""
Unit tests for Breakout Strategy.

This module tests the Breakout Strategy implementation including:
- Support/resistance level detection
- Breakout signal generation
- Volume confirmation logic
- Stop-loss placement
- Strategy on_tick processing

Requirements: 5.1, 5.3
"""

from decimal import Decimal

from django.utils import timezone

import pytest

from trading.breakout_strategy import (
    BREAKOUT_STRATEGY_CONFIG_SCHEMA,
    BreakoutStrategy,
    SupportResistanceDetector,
    VolumeConfirmation,
)
from trading.models import Strategy
from trading.tick_data_models import TickData


@pytest.mark.django_db
class TestSupportResistanceDetector:
    """Test support/resistance level detection."""

    def test_detector_initialization(self):
        """Test detector initializes correctly."""
        detector = SupportResistanceDetector(lookback_period=50, threshold_pips=Decimal("10"))

        assert detector.lookback_period == 50
        assert detector.threshold_pips == Decimal("10")
        assert len(detector.prices) == 0
        assert not detector.is_ready()

    def test_add_price(self):
        """Test adding prices to detector."""
        detector = SupportResistanceDetector(lookback_period=50)

        detector.add_price(Decimal("1.1000"), Decimal("1.0950"), Decimal("1.0975"))

        assert len(detector.prices) == 1
        assert len(detector.highs) == 1
        assert len(detector.lows) == 1
        assert detector.prices[0] == Decimal("1.0975")
        assert detector.highs[0] == Decimal("1.1000")
        assert detector.lows[0] == Decimal("1.0950")

    def test_resistance_detection(self):
        """Test resistance level detection."""
        detector = SupportResistanceDetector(lookback_period=50, threshold_pips=Decimal("5"))

        # Add prices with clear resistance around 1.1000
        for i in range(30):
            if i % 5 == 0:
                # Create swing highs around 1.1000
                detector.add_price(Decimal("1.1000"), Decimal("1.0950"), Decimal("1.0975"))
            else:
                detector.add_price(Decimal("1.0980"), Decimal("1.0950"), Decimal("1.0965"))

        resistance = detector.get_resistance_level()

        assert resistance is not None
        assert Decimal("1.0980") <= resistance <= Decimal("1.1000")

    def test_support_detection(self):
        """Test support level detection."""
        detector = SupportResistanceDetector(lookback_period=50, threshold_pips=Decimal("5"))

        # Add prices with clear support around 1.0950
        for i in range(30):
            if i % 5 == 0:
                # Create swing lows around 1.0950
                detector.add_price(Decimal("1.1000"), Decimal("1.0950"), Decimal("1.0975"))
            else:
                detector.add_price(Decimal("1.1000"), Decimal("1.0970"), Decimal("1.0985"))

        support = detector.get_support_level()

        assert support is not None
        assert Decimal("1.0950") <= support <= Decimal("1.0970")

    def test_not_ready_with_insufficient_data(self):
        """Test detector is not ready with insufficient data."""
        detector = SupportResistanceDetector(lookback_period=50)

        # Add only a few prices
        for _ in range(10):
            detector.add_price(Decimal("1.1000"), Decimal("1.0950"), Decimal("1.0975"))

        assert not detector.is_ready()
        assert detector.get_resistance_level() is None
        assert detector.get_support_level() is None


@pytest.mark.django_db
class TestVolumeConfirmation:
    """Test volume confirmation logic."""

    def test_volume_confirmation_initialization(self):
        """Test volume confirmation initializes correctly."""
        volume_conf = VolumeConfirmation(lookback_period=20, volume_multiplier=Decimal("1.5"))

        assert volume_conf.lookback_period == 20
        assert volume_conf.volume_multiplier == Decimal("1.5")
        assert len(volume_conf.volumes) == 0
        assert not volume_conf.is_ready()

    def test_add_volume(self):
        """Test adding volume data."""
        volume_conf = VolumeConfirmation(lookback_period=20)

        volume_conf.add_volume(Decimal("1000"))

        assert len(volume_conf.volumes) == 1
        assert volume_conf.volumes[0] == Decimal("1000")

    def test_volume_confirmed_with_high_volume(self):
        """Test volume confirmation with high volume."""
        volume_conf = VolumeConfirmation(lookback_period=20, volume_multiplier=Decimal("1.5"))

        # Add average volumes
        for _ in range(15):
            volume_conf.add_volume(Decimal("1000"))

        # Test with high volume (above threshold)
        assert volume_conf.is_volume_confirmed(Decimal("1600"))

    def test_volume_not_confirmed_with_low_volume(self):
        """Test volume not confirmed with low volume."""
        volume_conf = VolumeConfirmation(lookback_period=20, volume_multiplier=Decimal("1.5"))

        # Add average volumes
        for _ in range(15):
            volume_conf.add_volume(Decimal("1000"))

        # Test with low volume (below threshold)
        assert not volume_conf.is_volume_confirmed(Decimal("1400"))

    def test_volume_confirmed_with_insufficient_data(self):
        """Test volume confirmation returns True with insufficient data."""
        volume_conf = VolumeConfirmation(lookback_period=20)

        # Add only a few volumes
        for _ in range(5):
            volume_conf.add_volume(Decimal("1000"))

        # Should return True (assume confirmed) with insufficient data
        assert volume_conf.is_volume_confirmed(Decimal("500"))


@pytest.mark.django_db
class TestBreakoutStrategy:
    """Test Breakout Strategy implementation."""

    @pytest.fixture
    def account(self, django_user_model):
        """Create test OANDA account."""
        # pylint: disable=import-outside-toplevel
        from accounts.models import OandaAccount

        user = django_user_model.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

        return OandaAccount.objects.create(
            user=user,
            account_id="001-001-0000001-001",
            api_token="test_token",
            api_type="practice",
            balance=Decimal("10000.00"),
        )

    @pytest.fixture
    def strategy(self, account):
        """Create test strategy instance."""
        config = {
            "lookback_period": 50,
            "threshold_pips": 10,
            "base_units": 1000,
            "use_volume_confirmation": False,
            "stop_loss_buffer_pips": 5,
        }

        return Strategy.objects.create(
            account=account,
            strategy_type="breakout",
            config=config,
            instrument="EUR_USD",
            is_active=True,
        )

    @pytest.fixture
    def breakout_strategy(self, strategy):
        """Create BreakoutStrategy instance."""
        return BreakoutStrategy(strategy)

    def test_strategy_initialization(self, breakout_strategy):
        """Test strategy initializes correctly."""
        assert breakout_strategy.lookback_period == 50
        assert breakout_strategy.threshold_pips == Decimal("10")
        assert breakout_strategy.base_units == Decimal("1000")
        assert not breakout_strategy.use_volume_confirmation
        assert breakout_strategy.stop_loss_buffer_pips == Decimal("5")
        assert "EUR_USD" in breakout_strategy.sr_detectors

    def test_resistance_breakout_signal(self, breakout_strategy):
        """Test resistance breakout signal generation."""
        # Build up price history with clear resistance pattern at 1.1000
        # Create swing highs around 1.1000
        prices = []
        for i in range(50):
            if i in [5, 10, 15, 20, 25, 30, 35, 40, 45]:
                # Swing highs at resistance
                prices.append((Decimal("1.0998"), Decimal("1.1002"), Decimal("1.1000")))
            elif i in [7, 12, 17, 22, 27, 32, 37, 42, 47]:
                # Swing lows
                prices.append((Decimal("1.0950"), Decimal("1.0954"), Decimal("1.0952")))
            else:
                # Normal prices between support and resistance
                prices.append((Decimal("1.0970"), Decimal("1.0974"), Decimal("1.0972")))

        for high, low, mid in prices:
            tick = TickData(
                instrument="EUR_USD",
                timestamp=timezone.now(),
                bid=low,
                ask=high,
                mid=mid,
            )
            breakout_strategy.on_tick(tick)

        # Create breakout above resistance
        breakout_tick = TickData(
            instrument="EUR_USD",
            timestamp=timezone.now(),
            bid=Decimal("1.1005"),
            ask=Decimal("1.1009"),
            mid=Decimal("1.1007"),
        )

        orders = breakout_strategy.on_tick(breakout_tick)

        # Should generate long entry order
        assert len(orders) >= 1
        entry_order = orders[0]
        assert entry_order.direction == "long"
        assert entry_order.instrument == "EUR_USD"
        assert entry_order.units == Decimal("1000")
        assert entry_order.stop_loss is not None
        assert entry_order.stop_loss < Decimal("1.1005")

    def test_support_breakout_signal(self, breakout_strategy):
        """Test support breakout signal generation."""
        # Build up price history with clear support pattern at 1.0950
        # Create swing lows around 1.0950
        prices = []
        for i in range(50):
            if i in [5, 10, 15, 20, 25, 30, 35, 40, 45]:
                # Swing lows at support
                prices.append((Decimal("1.0948"), Decimal("1.0952"), Decimal("1.0950")))
            elif i in [7, 12, 17, 22, 27, 32, 37, 42, 47]:
                # Swing highs
                prices.append((Decimal("1.0998"), Decimal("1.1002"), Decimal("1.1000")))
            else:
                # Normal prices between support and resistance
                prices.append((Decimal("1.0970"), Decimal("1.0974"), Decimal("1.0972")))

        for high, low, mid in prices:
            tick = TickData(
                instrument="EUR_USD",
                timestamp=timezone.now(),
                bid=low,
                ask=high,
                mid=mid,
            )
            breakout_strategy.on_tick(tick)

        # Create breakout below support
        breakout_tick = TickData(
            instrument="EUR_USD",
            timestamp=timezone.now(),
            bid=Decimal("1.0943"),
            ask=Decimal("1.0947"),
            mid=Decimal("1.0945"),
        )

        orders = breakout_strategy.on_tick(breakout_tick)

        # Should generate short entry order
        assert len(orders) >= 1
        entry_order = orders[0]
        assert entry_order.direction == "short"
        assert entry_order.instrument == "EUR_USD"
        assert entry_order.units == Decimal("1000")
        assert entry_order.stop_loss is not None
        assert entry_order.stop_loss > Decimal("1.0945")

    def test_stop_loss_placement(self, breakout_strategy):
        """Test stop-loss placement at previous support/resistance."""
        # Build up price history with clear resistance
        prices = []
        for i in range(50):
            if i in [5, 10, 15, 20, 25, 30, 35, 40, 45]:
                # Swing highs at resistance around 1.1000
                prices.append((Decimal("1.0998"), Decimal("1.1002"), Decimal("1.1000")))
            elif i in [7, 12, 17, 22, 27, 32, 37, 42, 47]:
                # Swing lows
                prices.append((Decimal("1.0950"), Decimal("1.0954"), Decimal("1.0952")))
            else:
                # Normal prices
                prices.append((Decimal("1.0970"), Decimal("1.0974"), Decimal("1.0972")))

        for high, low, mid in prices:
            tick = TickData(
                instrument="EUR_USD",
                timestamp=timezone.now(),
                bid=low,
                ask=high,
                mid=mid,
            )
            breakout_strategy.on_tick(tick)

        # Create resistance breakout
        breakout_tick = TickData(
            instrument="EUR_USD",
            timestamp=timezone.now(),
            bid=Decimal("1.1005"),
            ask=Decimal("1.1009"),
            mid=Decimal("1.1007"),
        )

        orders = breakout_strategy.on_tick(breakout_tick)

        assert len(orders) >= 1
        entry_order = orders[0]

        # Stop loss should be below resistance with buffer
        # Buffer is 5 pips (0.0005)
        assert entry_order.stop_loss is not None
        # Stop should be below the breakout level
        assert entry_order.stop_loss < Decimal("1.1000")

    def test_no_signal_with_insufficient_data(self, breakout_strategy):
        """Test no signal generated with insufficient data."""
        # Add only a few ticks
        for _ in range(10):
            tick = TickData(
                instrument="EUR_USD",
                timestamp=timezone.now(),
                bid=Decimal("1.0970"),
                ask=Decimal("1.0972"),
                mid=Decimal("1.0971"),
            )
            orders = breakout_strategy.on_tick(tick)
            assert len(orders) == 0

    def test_volume_confirmation_enabled(self, strategy):
        """Test volume confirmation logic when enabled."""
        # Update config to enable volume confirmation
        strategy.config["use_volume_confirmation"] = True
        strategy.save()

        breakout_strategy = BreakoutStrategy(strategy)

        assert breakout_strategy.use_volume_confirmation
        assert "EUR_USD" in breakout_strategy.volume_confirmations

    def test_validate_config_valid(self, breakout_strategy):
        """Test config validation with valid configuration."""
        config = {
            "lookback_period": 50,
            "threshold_pips": 10,
            "base_units": 1000,
            "use_volume_confirmation": False,
            "stop_loss_buffer_pips": 5,
        }

        assert breakout_strategy.validate_config(config)

    def test_validate_config_invalid_lookback_period(self, breakout_strategy):
        """Test config validation with invalid lookback period."""
        config = {
            "lookback_period": 5,  # Too small
            "threshold_pips": 10,
            "base_units": 1000,
        }

        with pytest.raises(ValueError, match="lookback_period must be an integer >= 10"):
            breakout_strategy.validate_config(config)

    def test_validate_config_invalid_threshold_pips(self, breakout_strategy):
        """Test config validation with invalid threshold pips."""
        config = {
            "lookback_period": 50,
            "threshold_pips": -5,  # Negative
            "base_units": 1000,
        }

        with pytest.raises(ValueError, match="threshold_pips must be positive"):
            breakout_strategy.validate_config(config)

    def test_validate_config_invalid_base_units(self, breakout_strategy):
        """Test config validation with invalid base units."""
        config = {
            "lookback_period": 50,
            "threshold_pips": 10,
            "base_units": 0,  # Zero
        }

        with pytest.raises(ValueError, match="base_units must be positive"):
            breakout_strategy.validate_config(config)

    def test_validate_config_invalid_volume_multiplier(self, breakout_strategy):
        """Test config validation with invalid volume multiplier."""
        config = {
            "lookback_period": 50,
            "threshold_pips": 10,
            "base_units": 1000,
            "use_volume_confirmation": True,
            "volume_multiplier": -1.5,  # Negative
        }

        with pytest.raises(ValueError, match="volume_multiplier must be positive"):
            breakout_strategy.validate_config(config)

    def test_on_position_update(self, breakout_strategy):
        """Test position update handling."""
        # pylint: disable=import-outside-toplevel
        from trading.models import Position

        position = Position(
            account=breakout_strategy.account,
            strategy=breakout_strategy.strategy,
            position_id="test_position",
            instrument="EUR_USD",
            direction="long",
            units=Decimal("1000"),
            entry_price=Decimal("1.1000"),
            current_price=Decimal("1.1000"),
            opened_at=timezone.now(),
        )

        # Set breakout tracking
        breakout_strategy.last_breakout["EUR_USD"] = "resistance"

        # Close position
        position.closed_at = timezone.now()
        breakout_strategy.on_position_update(position)

        # Breakout tracking should be reset
        assert breakout_strategy.last_breakout["EUR_USD"] is None

    def test_config_schema_exists(self):
        """Test that config schema is properly defined."""
        assert BREAKOUT_STRATEGY_CONFIG_SCHEMA is not None
        assert BREAKOUT_STRATEGY_CONFIG_SCHEMA["type"] == "object"
        assert "properties" in BREAKOUT_STRATEGY_CONFIG_SCHEMA
        assert "lookback_period" in BREAKOUT_STRATEGY_CONFIG_SCHEMA["properties"]
        assert "threshold_pips" in BREAKOUT_STRATEGY_CONFIG_SCHEMA["properties"]
        assert "base_units" in BREAKOUT_STRATEGY_CONFIG_SCHEMA["properties"]
        assert "use_volume_confirmation" in BREAKOUT_STRATEGY_CONFIG_SCHEMA["properties"]
        assert "stop_loss_buffer_pips" in BREAKOUT_STRATEGY_CONFIG_SCHEMA["properties"]

    def test_strategy_registered(self):
        """Test that strategy is registered in the registry."""
        # pylint: disable=import-outside-toplevel
        from trading.strategy_registry import registry

        strategy_class = registry.get_strategy_class("breakout")
        assert strategy_class is not None
        assert strategy_class == BreakoutStrategy
