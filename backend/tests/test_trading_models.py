"""
Unit tests for trading models.

Tests cover:
- Strategy model config JSON field
- StrategyState model state persistence
- Order model field validation and choices
- Position model P&L calculations
- Trade model completed trade records

Requirements: 5.1, 8.1, 9.1
"""

from decimal import Decimal

import pytest
from accounts.models import OandaAccount, User
from django.utils import timezone
from trading.models import Order, Position, Strategy, StrategyState, Trade


@pytest.mark.django_db
class TestStrategyModel:
    """Test Strategy model functionality."""

    def test_strategy_creation(self):
        """Test creating a strategy with config JSON field."""
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
        )
        account = OandaAccount.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_type="practice",
        )
        account.set_api_token("test_token_12345")
        account.save()

        strategy = Strategy.objects.create(
            account=account,
            strategy_type="floor",
            config={
                "lot_size": 1.0,
                "scaling_mode": "additive",
                "retracement_pips": 30,
                "take_profit_pips": 25,
            },
            instruments=["EUR_USD", "GBP_USD"],
        )

        assert strategy.strategy_type == "floor"
        assert strategy.config["lot_size"] == 1.0
        assert strategy.config["scaling_mode"] == "additive"
        assert "EUR_USD" in strategy.instruments
        assert strategy.is_active is False

    def test_strategy_start_stop(self):
        """Test starting and stopping a strategy."""
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
        )
        account = OandaAccount.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_type="practice",
        )
        account.set_api_token("test_token_12345")
        account.save()

        strategy = Strategy.objects.create(
            account=account,
            strategy_type="floor",
            config={},
            instruments=["EUR_USD"],
        )

        # Start strategy
        strategy.start()
        assert strategy.is_active is True
        assert strategy.started_at is not None
        assert strategy.stopped_at is None

        # Stop strategy
        strategy.stop()
        assert strategy.is_active is False
        assert strategy.stopped_at is not None

    def test_strategy_update_config(self):
        """Test updating strategy configuration."""
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
        )
        account = OandaAccount.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_type="practice",
        )
        account.set_api_token("test_token_12345")
        account.save()

        strategy = Strategy.objects.create(
            account=account,
            strategy_type="floor",
            config={"lot_size": 1.0},
            instruments=["EUR_USD"],
        )

        new_config = {"lot_size": 2.0, "scaling_mode": "multiplicative"}
        strategy.update_config(new_config)

        strategy.refresh_from_db()
        assert strategy.config["lot_size"] == 2.0
        assert strategy.config["scaling_mode"] == "multiplicative"


@pytest.mark.django_db
class TestStrategyStateModel:
    """Test StrategyState model functionality."""

    def test_strategy_state_creation(self):
        """Test creating strategy state with layer states."""
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
        )
        account = OandaAccount.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_type="practice",
        )
        account.set_api_token("test_token_12345")
        account.save()

        strategy = Strategy.objects.create(
            account=account,
            strategy_type="floor",
            config={},
            instruments=["EUR_USD"],
        )

        state = StrategyState.objects.create(
            strategy=strategy,
            current_layer=1,
            layer_states={
                "1": {"position_count": 3, "entry_price": "1.1000"},
                "2": {"position_count": 0, "entry_price": None},
            },
            atr_values={"EUR_USD": "0.00050"},
            normal_atr=Decimal("0.00045"),
        )

        assert state.current_layer == 1
        assert state.layer_states["1"]["position_count"] == 3
        assert state.atr_values["EUR_USD"] == "0.00050"
        assert state.normal_atr == Decimal("0.00045")

    def test_update_layer_state(self):
        """Test updating layer state."""
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
        )
        account = OandaAccount.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_type="practice",
        )
        account.set_api_token("test_token_12345")
        account.save()

        strategy = Strategy.objects.create(
            account=account,
            strategy_type="floor",
            config={},
            instruments=["EUR_USD"],
        )

        state = StrategyState.objects.create(
            strategy=strategy,
            current_layer=1,
            layer_states={},
        )

        state.update_layer_state(1, {"position_count": 5, "entry_price": "1.1050"})

        state.refresh_from_db()
        assert state.layer_states["1"]["position_count"] == 5
        assert state.layer_states["1"]["entry_price"] == "1.1050"

    def test_update_atr(self):
        """Test updating ATR values."""
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
        )
        account = OandaAccount.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_type="practice",
        )
        account.set_api_token("test_token_12345")
        account.save()

        strategy = Strategy.objects.create(
            account=account,
            strategy_type="floor",
            config={},
            instruments=["EUR_USD"],
        )

        state = StrategyState.objects.create(
            strategy=strategy,
            current_layer=1,
            atr_values={},
        )

        state.update_atr("EUR_USD", Decimal("0.00055"))

        state.refresh_from_db()
        assert state.atr_values["EUR_USD"] == "0.00055"


@pytest.mark.django_db
class TestOrderModel:
    """Test Order model functionality."""

    def test_order_creation_with_choices(self):
        """Test creating orders with different types and directions."""
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
        )
        account = OandaAccount.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_type="practice",
        )
        account.set_api_token("test_token_12345")
        account.save()

        # Test market order
        market_order = Order.objects.create(
            account=account,
            order_id="ORDER-001",
            instrument="EUR_USD",
            order_type="market",
            direction="long",
            units=Decimal("10000.00"),
        )

        assert market_order.order_type == "market"
        assert market_order.direction == "long"
        assert market_order.status == "pending"

        # Test limit order
        limit_order = Order.objects.create(
            account=account,
            order_id="ORDER-002",
            instrument="GBP_USD",
            order_type="limit",
            direction="short",
            units=Decimal("5000.00"),
            price=Decimal("1.2500"),
        )

        assert limit_order.order_type == "limit"
        assert limit_order.direction == "short"
        assert limit_order.price == Decimal("1.2500")

    def test_order_status_transitions(self):
        """Test order status transitions."""
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
        )
        account = OandaAccount.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_type="practice",
        )
        account.set_api_token("test_token_12345")
        account.save()

        order = Order.objects.create(
            account=account,
            order_id="ORDER-001",
            instrument="EUR_USD",
            order_type="market",
            direction="long",
            units=Decimal("10000.00"),
        )

        # Mark as filled
        order.mark_filled()
        assert order.status == "filled"
        assert order.filled_at is not None

        # Create another order and cancel it
        order2 = Order.objects.create(
            account=account,
            order_id="ORDER-002",
            instrument="EUR_USD",
            order_type="limit",
            direction="long",
            units=Decimal("10000.00"),
            price=Decimal("1.1000"),
        )

        order2.mark_cancelled()
        assert order2.status == "cancelled"

        # Create another order and reject it
        order3 = Order.objects.create(
            account=account,
            order_id="ORDER-003",
            instrument="EUR_USD",
            order_type="market",
            direction="long",
            units=Decimal("10000.00"),
        )

        order3.mark_rejected()
        assert order3.status == "rejected"


@pytest.mark.django_db
class TestPositionModel:
    """Test Position model functionality."""

    def test_position_creation(self):
        """Test creating a position."""
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
        )
        account = OandaAccount.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_type="practice",
        )
        account.set_api_token("test_token_12345")
        account.save()

        position = Position.objects.create(
            account=account,
            position_id="POS-001",
            instrument="EUR_USD",
            direction="long",
            units=Decimal("10000.00"),
            entry_price=Decimal("1.1000"),
            current_price=Decimal("1.1000"),
        )

        assert position.direction == "long"
        assert position.units == Decimal("10000.00")
        assert position.entry_price == Decimal("1.1000")
        assert position.unrealized_pnl == Decimal("0")

    def test_calculate_unrealized_pnl_long(self):
        """Test calculating unrealized P&L for long positions."""
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
        )
        account = OandaAccount.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_type="practice",
        )
        account.set_api_token("test_token_12345")
        account.save()

        position = Position.objects.create(
            account=account,
            position_id="POS-001",
            instrument="EUR_USD",
            direction="long",
            units=Decimal("10000.00"),
            entry_price=Decimal("1.1000"),
            current_price=Decimal("1.1000"),
        )

        # Price goes up - profit
        pnl = position.calculate_unrealized_pnl(Decimal("1.1050"))
        # (1.1050 - 1.1000) * 10000 = 0.0050 * 10000 = 50
        assert pnl == Decimal("50.000000")

        # Price goes down - loss
        pnl = position.calculate_unrealized_pnl(Decimal("1.0950"))
        # (1.0950 - 1.1000) * 10000 = -0.0050 * 10000 = -50
        assert pnl == Decimal("-50.000000")

    def test_calculate_unrealized_pnl_short(self):
        """Test calculating unrealized P&L for short positions."""
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
        )
        account = OandaAccount.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_type="practice",
        )
        account.set_api_token("test_token_12345")
        account.save()

        position = Position.objects.create(
            account=account,
            position_id="POS-001",
            instrument="EUR_USD",
            direction="short",
            units=Decimal("10000.00"),
            entry_price=Decimal("1.1000"),
            current_price=Decimal("1.1000"),
        )

        # Price goes down - profit
        pnl = position.calculate_unrealized_pnl(Decimal("1.0950"))
        # -(1.0950 - 1.1000) * 10000 = -(-0.0050 * 10000) = 50
        assert pnl == Decimal("50.000000")

        # Price goes up - loss
        pnl = position.calculate_unrealized_pnl(Decimal("1.1050"))
        # -(1.1050 - 1.1000) * 10000 = -(0.0050 * 10000) = -50
        assert pnl == Decimal("-50.000000")

    def test_update_price(self):
        """Test updating position price and P&L."""
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
        )
        account = OandaAccount.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_type="practice",
        )
        account.set_api_token("test_token_12345")
        account.save()

        position = Position.objects.create(
            account=account,
            position_id="POS-001",
            instrument="EUR_USD",
            direction="long",
            units=Decimal("10000.00"),
            entry_price=Decimal("1.1000"),
            current_price=Decimal("1.1000"),
        )

        position.update_price(Decimal("1.1050"))

        position.refresh_from_db()
        assert position.current_price == Decimal("1.1050")
        # 0.0050 * 10000 = 50
        assert position.unrealized_pnl == Decimal("50.00")

    def test_close_position(self):
        """Test closing a position and calculating realized P&L."""
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
        )
        account = OandaAccount.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_type="practice",
        )
        account.set_api_token("test_token_12345")
        account.save()

        position = Position.objects.create(
            account=account,
            position_id="POS-001",
            instrument="EUR_USD",
            direction="long",
            units=Decimal("10000.00"),
            entry_price=Decimal("1.1000"),
            current_price=Decimal("1.1000"),
        )

        realized_pnl = position.close(Decimal("1.1050"))

        # 0.0050 * 10000 = 50
        assert realized_pnl == Decimal("50.000000")
        assert position.realized_pnl == Decimal("50.000000")
        assert position.closed_at is not None
        assert position.current_price == Decimal("1.1050")


@pytest.mark.django_db
class TestTradeModel:
    """Test Trade model functionality."""

    def test_trade_creation(self):
        """Test creating a completed trade record."""
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
        )
        account = OandaAccount.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_type="practice",
        )
        account.set_api_token("test_token_12345")
        account.save()

        opened_at = timezone.now()
        closed_at = timezone.now()

        trade = Trade.objects.create(
            account=account,
            instrument="EUR_USD",
            direction="long",
            units=Decimal("10000.00"),
            entry_price=Decimal("1.1000"),
            exit_price=Decimal("1.1050"),
            pnl=Decimal("500.00"),
            commission=Decimal("2.50"),
            opened_at=opened_at,
            closed_at=closed_at,
        )

        assert trade.instrument == "EUR_USD"
        assert trade.direction == "long"
        assert trade.pnl == Decimal("500.00")
        assert trade.commission == Decimal("2.50")

    def test_trade_net_pnl(self):
        """Test calculating net P&L after commission."""
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
        )
        account = OandaAccount.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_type="practice",
        )
        account.set_api_token("test_token_12345")
        account.save()

        opened_at = timezone.now()
        closed_at = timezone.now()

        trade = Trade.objects.create(
            account=account,
            instrument="EUR_USD",
            direction="long",
            units=Decimal("10000.00"),
            entry_price=Decimal("1.1000"),
            exit_price=Decimal("1.1050"),
            pnl=Decimal("500.00"),
            commission=Decimal("2.50"),
            opened_at=opened_at,
            closed_at=closed_at,
        )

        assert trade.net_pnl == Decimal("497.50")  # 500.00 - 2.50

    def test_trade_duration(self):
        """Test calculating trade duration."""
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
        )
        account = OandaAccount.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_type="practice",
        )
        account.set_api_token("test_token_12345")
        account.save()

        opened_at = timezone.now()
        closed_at = opened_at + timezone.timedelta(hours=2, minutes=30)

        trade = Trade.objects.create(
            account=account,
            instrument="EUR_USD",
            direction="long",
            units=Decimal("10000.00"),
            entry_price=Decimal("1.1000"),
            exit_price=Decimal("1.1050"),
            pnl=Decimal("500.00"),
            commission=Decimal("2.50"),
            opened_at=opened_at,
            closed_at=closed_at,
        )

        duration = trade.duration
        assert "2.5h" in duration or "2.5" in duration
