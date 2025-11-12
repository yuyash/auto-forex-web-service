"""
Unit tests for Risk Management System.

This module tests:
- ATRMonitor volatility spike detection
- Volatility lock mechanism
- Margin-liquidation ratio calculation
- Margin protection liquidation
- Integration with strategy execution

Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 11.1, 11.2, 11.3, 11.4, 11.5
"""

from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model

import pytest

from accounts.models import OandaAccount
from trading.event_models import Event
from trading.models import Position, Strategy, StrategyState
from trading.risk_manager import ATRMonitor, RiskManager

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
        margin_used=Decimal("1000.00"),
        margin_available=Decimal("9000.00"),
    )


@pytest.fixture
def strategy(oanda_account):
    """Create a test strategy."""
    return Strategy.objects.create(
        account=oanda_account,
        strategy_type="floor",
        config={"lot_size": 1000},
        instrument="EUR_USD",
        is_active=True,
    )


@pytest.fixture
def strategy_state(strategy):
    """Create a test strategy state."""
    return StrategyState.objects.create(
        strategy=strategy,
        current_layer=1,
        layer_states={},
        atr_values={
            "EUR_USD": "0.0010",
            "EUR_USD_normal": "0.0008",
            "GBP_USD": "0.0012",
            "GBP_USD_normal": "0.0010",
        },
        normal_atr=Decimal("0.0008"),
    )


@pytest.fixture
def open_positions(oanda_account, strategy):
    """Create test open positions."""
    positions = []

    # Layer 1 positions
    for i in range(3):
        position = Position.objects.create(
            account=oanda_account,
            strategy=strategy,
            position_id=f"pos_layer1_{i}",
            instrument="EUR_USD",
            direction="long",
            units=Decimal("1000"),
            entry_price=Decimal("1.1000"),
            current_price=Decimal("1.1050"),
            unrealized_pnl=Decimal("50.00"),
            layer_number=1,
            is_first_lot=(i == 0),
        )
        positions.append(position)

    # Layer 2 positions
    for i in range(2):
        position = Position.objects.create(
            account=oanda_account,
            strategy=strategy,
            position_id=f"pos_layer2_{i}",
            instrument="EUR_USD",
            direction="long",
            units=Decimal("1000"),
            entry_price=Decimal("1.0950"),
            current_price=Decimal("1.1050"),
            unrealized_pnl=Decimal("100.00"),
            layer_number=2,
            is_first_lot=(i == 0),
        )
        positions.append(position)

    return positions


@pytest.mark.django_db
class TestATRMonitor:
    """Test ATRMonitor class."""

    def test_check_volatility_spike_detected(self):
        """Test volatility spike detection when ATR >= 5x normal."""
        monitor = ATRMonitor()

        current_atr = Decimal("0.0040")
        normal_atr = Decimal("0.0008")

        # 0.0040 >= 5 * 0.0008 = 0.0040 (exactly at threshold)
        is_spike = monitor.check_volatility_spike(current_atr, normal_atr)

        assert is_spike is True

    def test_check_volatility_spike_not_detected(self):
        """Test no volatility spike when ATR < 5x normal."""
        monitor = ATRMonitor()

        current_atr = Decimal("0.0030")
        normal_atr = Decimal("0.0008")

        # 0.0030 < 5 * 0.0008 = 0.0040
        is_spike = monitor.check_volatility_spike(current_atr, normal_atr)

        assert is_spike is False

    def test_check_volatility_spike_custom_threshold(self):
        """Test volatility spike with custom threshold multiplier."""
        monitor = ATRMonitor()

        current_atr = Decimal("0.0024")
        normal_atr = Decimal("0.0008")
        threshold_multiplier = Decimal("3.0")

        # 0.0024 >= 3 * 0.0008 = 0.0024 (exactly at threshold)
        is_spike = monitor.check_volatility_spike(
            current_atr,
            normal_atr,
            threshold_multiplier,
        )

        assert is_spike is True

    def test_check_volatility_spike_zero_normal_atr(self):
        """Test volatility spike with zero normal ATR."""
        monitor = ATRMonitor()

        current_atr = Decimal("0.0040")
        normal_atr = Decimal("0.0000")

        # Should return False when normal_atr is zero
        is_spike = monitor.check_volatility_spike(current_atr, normal_atr)

        assert is_spike is False

    @patch("trading.risk_manager.ATRCalculator.get_latest_atr")
    def test_get_current_atr_success(self, mock_get_latest_atr, oanda_account):
        """Test getting current ATR successfully."""
        monitor = ATRMonitor()
        mock_get_latest_atr.return_value = Decimal("0.0010")

        atr = monitor.get_current_atr(oanda_account, "EUR_USD")

        assert atr == Decimal("0.0010")
        mock_get_latest_atr.assert_called_once_with(oanda_account, "EUR_USD")

    @patch("trading.risk_manager.ATRCalculator.get_latest_atr")
    def test_get_current_atr_failure(self, mock_get_latest_atr, oanda_account):
        """Test getting current ATR when calculation fails."""
        monitor = ATRMonitor()
        mock_get_latest_atr.side_effect = Exception("API error")

        atr = monitor.get_current_atr(oanda_account, "EUR_USD")

        assert atr is None

    def test_get_normal_atr_from_strategy_state(self, strategy_state):
        """Test getting normal ATR from strategy state."""
        monitor = ATRMonitor()

        # Test getting from normal_atr field
        normal_atr = monitor.get_normal_atr(strategy_state, "EUR_USD")
        assert normal_atr == Decimal("0.0008")

    def test_get_normal_atr_instrument_specific(self, strategy_state):
        """Test getting instrument-specific normal ATR."""
        monitor = ATRMonitor()

        # Clear normal_atr field to test instrument-specific lookup
        strategy_state.normal_atr = None
        strategy_state.save()

        normal_atr = monitor.get_normal_atr(strategy_state, "EUR_USD")
        assert normal_atr == Decimal("0.0008")

    def test_get_normal_atr_not_set(self, strategy):
        """Test getting normal ATR when not set."""
        monitor = ATRMonitor()

        # Create strategy state without normal ATR
        state = StrategyState.objects.create(
            strategy=strategy,
            current_layer=1,
            layer_states={},
            atr_values={},
        )

        normal_atr = monitor.get_normal_atr(state, "EUR_USD")
        assert normal_atr is None

    @patch("trading.risk_manager.ATRMonitor.get_current_atr")
    @patch("trading.risk_manager.ATRMonitor.get_normal_atr")
    def test_monitor_instrument_with_spike(
        self,
        mock_get_normal_atr,
        mock_get_current_atr,
        oanda_account,
        strategy,
        strategy_state,  # pylint: disable=unused-argument
    ):
        """Test monitoring instrument with volatility spike."""
        monitor = ATRMonitor()

        # Mock ATR values - spike detected
        mock_get_current_atr.return_value = Decimal("0.0040")
        mock_get_normal_atr.return_value = Decimal("0.0008")

        results = monitor.monitor_instrument(
            oanda_account,
            strategy,
            "EUR_USD",
        )

        assert results == {"EUR_USD": True}

    @patch("trading.risk_manager.ATRMonitor.get_current_atr")
    @patch("trading.risk_manager.ATRMonitor.get_normal_atr")
    def test_monitor_instrument_no_spike(
        self,
        mock_get_normal_atr,
        mock_get_current_atr,
        oanda_account,
        strategy,
        strategy_state,  # pylint: disable=unused-argument
    ):
        """Test monitoring instrument without volatility spike."""
        monitor = ATRMonitor()

        # Mock ATR values - no spike
        mock_get_current_atr.return_value = Decimal("0.0010")
        mock_get_normal_atr.return_value = Decimal("0.0008")

        results = monitor.monitor_instrument(
            oanda_account,
            strategy,
            "EUR_USD",
        )

        assert results == {"EUR_USD": False}


@pytest.mark.django_db
class TestRiskManagerVolatilityLock:
    """Test RiskManager volatility lock mechanism."""

    def test_execute_volatility_lock_success(
        self,
        oanda_account,
        strategy,
        open_positions,  # pylint: disable=unused-argument
    ):
        """Test successful volatility lock execution."""
        risk_manager = RiskManager()

        # Execute volatility lock
        success = risk_manager.execute_volatility_lock(
            account=oanda_account,
            strategy=strategy,
            instrument="EUR_USD",
            current_atr=Decimal("0.0040"),
            normal_atr=Decimal("0.0008"),
        )

        assert success is True

        # Verify strategy is stopped
        strategy.refresh_from_db()
        assert strategy.is_active is False

        # Verify all positions are closed
        open_count = Position.objects.filter(
            account=oanda_account,
            closed_at__isnull=True,
        ).count()
        assert open_count == 0

        # Verify event was logged
        event = Event.objects.filter(
            event_type="volatility_lock",
            account=oanda_account,
        ).first()
        assert event is not None
        assert event.severity == "critical"
        assert "EUR_USD" in event.description

    def test_execute_volatility_lock_closes_at_breakeven(
        self,
        oanda_account,
        strategy,
        open_positions,
    ):
        """Test that volatility lock closes positions at break-even prices."""
        risk_manager = RiskManager()

        # Execute volatility lock
        risk_manager.execute_volatility_lock(
            account=oanda_account,
            strategy=strategy,
            instrument="EUR_USD",
            current_atr=Decimal("0.0040"),
            normal_atr=Decimal("0.0008"),
        )

        # Verify positions were closed at entry price (break-even)
        for position in open_positions:
            position.refresh_from_db()
            assert position.closed_at is not None
            assert position.current_price == position.entry_price
            assert position.realized_pnl == Decimal("0.00")


@pytest.mark.django_db
class TestRiskManagerMarginProtection:
    """Test RiskManager margin protection mechanism."""

    def test_calculate_margin_liquidation_ratio(
        self,
        oanda_account,
        open_positions,  # pylint: disable=unused-argument
    ):
        """Test margin-liquidation ratio calculation."""
        risk_manager = RiskManager()

        # Total unrealized P&L = 3 * 50 + 2 * 100 = 350
        # Margin used = 1000
        # Ratio = (1000 + 350) / 1000 = 1.35
        ratio = risk_manager.calculate_margin_liquidation_ratio(oanda_account)

        assert ratio is not None
        assert ratio == Decimal("1.35")

    def test_calculate_margin_liquidation_ratio_zero_margin(self, oanda_account):
        """Test margin ratio calculation with zero margin."""
        risk_manager = RiskManager()

        # Set margin to zero
        oanda_account.margin_used = Decimal("0.00")
        oanda_account.save()

        ratio = risk_manager.calculate_margin_liquidation_ratio(oanda_account)

        assert ratio is None

    def test_check_margin_threshold_exceeded(
        self,
        oanda_account,
        open_positions,  # pylint: disable=unused-argument
    ):
        """Test margin threshold check when exceeded."""
        risk_manager = RiskManager()

        # Ratio = 1.35, threshold = 1.0
        exceeds = risk_manager.check_margin_threshold(oanda_account, Decimal("1.0"))

        assert exceeds is True

    def test_check_margin_threshold_not_exceeded(
        self,
        oanda_account,
        open_positions,  # pylint: disable=unused-argument
    ):
        """Test margin threshold check when not exceeded."""
        risk_manager = RiskManager()

        # Ratio = 1.35, threshold = 1.5
        exceeds = risk_manager.check_margin_threshold(oanda_account, Decimal("1.5"))

        assert exceeds is False

    def test_execute_margin_protection_first_layer(
        self,
        oanda_account,
        open_positions,
    ):
        """Test margin protection liquidates first lot of first layer."""
        risk_manager = RiskManager()

        # Execute margin protection
        success = risk_manager.execute_margin_protection(oanda_account)

        assert success is True

        # Verify first position of layer 1 was closed
        first_position = open_positions[0]
        first_position.refresh_from_db()
        assert first_position.closed_at is not None
        assert first_position.layer_number == 1

        # Verify other positions are still open
        open_count = Position.objects.filter(
            account=oanda_account,
            closed_at__isnull=True,
        ).count()
        assert open_count == 4  # 2 remaining in layer 1, 2 in layer 2

        # Verify event was logged
        event = Event.objects.filter(
            event_type="margin_protection",
            account=oanda_account,
        ).first()
        assert event is not None
        assert event.severity == "critical"

    def test_execute_margin_protection_second_layer(
        self,
        oanda_account,
        open_positions,
    ):
        """Test margin protection moves to second layer after first is liquidated."""
        risk_manager = RiskManager()

        # Close all layer 1 positions first
        for position in open_positions[:3]:
            position.close(position.current_price)

        # Execute margin protection
        success = risk_manager.execute_margin_protection(oanda_account)

        assert success is True

        # Verify first position of layer 2 was closed
        first_layer2_position = open_positions[3]
        first_layer2_position.refresh_from_db()
        assert first_layer2_position.closed_at is not None
        assert first_layer2_position.layer_number == 2

    def test_execute_margin_protection_no_positions(self, oanda_account):
        """Test margin protection with no open positions."""
        risk_manager = RiskManager()

        # Execute margin protection with no positions
        success = risk_manager.execute_margin_protection(oanda_account)

        assert success is False


@pytest.mark.django_db
class TestRiskManagerIntegration:
    """Test RiskManager integration with strategy execution."""

    @patch("trading.risk_manager.ATRMonitor.monitor_instrument")
    def test_check_and_execute_risk_management_volatility_lock(
        self,
        mock_monitor_instrument,
        oanda_account,
        strategy,
        strategy_state,  # pylint: disable=unused-argument
        open_positions,  # pylint: disable=unused-argument
    ):
        """Test risk management with volatility lock triggered."""
        risk_manager = RiskManager()

        # Mock volatility spike detected
        mock_monitor_instrument.return_value = {"EUR_USD": True}

        # Mock ATR values
        with (
            patch.object(
                risk_manager.atr_monitor,
                "get_current_atr",
                return_value=Decimal("0.0040"),
            ),
            patch.object(
                risk_manager.atr_monitor,
                "get_normal_atr",
                return_value=Decimal("0.0008"),
            ),
        ):
            results = risk_manager.check_and_execute_risk_management(
                oanda_account,
                strategy,
            )

        assert results["volatility_locked"] is True
        instrument = results["instrument_monitored"]
        assert isinstance(instrument, str)
        assert instrument == "EUR_USD"

        # Verify strategy was stopped
        strategy.refresh_from_db()
        assert strategy.is_active is False

    @patch("trading.risk_manager.ATRMonitor.monitor_instrument")
    def test_check_and_execute_risk_management_margin_protection(
        self,
        mock_monitor_instrument,
        oanda_account,
        strategy,
        strategy_state,  # pylint: disable=unused-argument
        open_positions,  # pylint: disable=unused-argument
    ):
        """Test risk management with margin protection triggered."""
        risk_manager = RiskManager()

        # Mock no volatility spike
        mock_monitor_instrument.return_value = {"EUR_USD": False}

        # Margin ratio = 1.35, threshold = 1.0 (will trigger)
        results = risk_manager.check_and_execute_risk_management(
            oanda_account,
            strategy,
        )

        assert results["margin_protected"] is True
        assert results["volatility_locked"] is False

        # Verify one position was closed
        closed_count = Position.objects.filter(
            account=oanda_account,
            closed_at__isnull=False,
        ).count()
        assert closed_count == 1

    @patch("trading.risk_manager.ATRMonitor.monitor_instrument")
    def test_check_and_execute_risk_management_no_action(
        self,
        mock_monitor_instrument,
        oanda_account,
        strategy,
        strategy_state,  # pylint: disable=unused-argument
    ):
        """Test risk management with no action needed."""
        risk_manager = RiskManager()

        # Mock no volatility spike
        mock_monitor_instrument.return_value = {"EUR_USD": False}

        # Set low margin usage to avoid margin protection
        oanda_account.margin_used = Decimal("100.00")
        oanda_account.save()

        results = risk_manager.check_and_execute_risk_management(
            oanda_account,
            strategy,
        )

        assert results["margin_protected"] is False
        assert results["volatility_locked"] is False
        instrument = results["instrument_monitored"]
        assert isinstance(instrument, str)
        assert instrument == "EUR_USD"
