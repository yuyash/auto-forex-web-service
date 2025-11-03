"""
Unit tests for P&L calculation.

Tests cover:
- Unrealized P&L calculation for long positions
- Unrealized P&L calculation for short positions
- Realized P&L calculation on position close
- P&L with different lot sizes
- Batch P&L calculations
- Pip calculations
- Break-even price calculations

Requirements: 9.1, 9.2
"""

from decimal import Decimal

import pytest

from accounts.models import OandaAccount, User
from trading.models import Position
from trading.pnl_calculator import PnLCalculator


@pytest.mark.django_db
class TestPnLCalculator:
    """Test PnLCalculator functionality."""

    def test_calculate_unrealized_pnl_long_profit(self) -> None:
        """Test unrealized P&L calculation for long position with profit."""
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
        current_price = Decimal("1.1050")
        pnl = PnLCalculator.calculate_unrealized_pnl(position, current_price)

        # (1.1050 - 1.1000) * 10000 = 0.0050 * 10000 = 50
        assert pnl == Decimal("50.000000")

    def test_calculate_unrealized_pnl_long_loss(self) -> None:
        """Test unrealized P&L calculation for long position with loss."""
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

        # Price goes down - loss
        current_price = Decimal("1.0950")
        pnl = PnLCalculator.calculate_unrealized_pnl(position, current_price)

        # (1.0950 - 1.1000) * 10000 = -0.0050 * 10000 = -50
        assert pnl == Decimal("-50.000000")

    def test_calculate_unrealized_pnl_short_profit(self) -> None:
        """Test unrealized P&L calculation for short position with profit."""
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
        current_price = Decimal("1.0950")
        pnl = PnLCalculator.calculate_unrealized_pnl(position, current_price)

        # -(1.0950 - 1.1000) * 10000 = -(-0.0050 * 10000) = 50
        assert pnl == Decimal("50.000000")

    def test_calculate_unrealized_pnl_short_loss(self) -> None:
        """Test unrealized P&L calculation for short position with loss."""
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

        # Price goes up - loss
        current_price = Decimal("1.1050")
        pnl = PnLCalculator.calculate_unrealized_pnl(position, current_price)

        # -(1.1050 - 1.1000) * 10000 = -(0.0050 * 10000) = -50
        assert pnl == Decimal("-50.000000")

    def test_calculate_realized_pnl_long(self) -> None:
        """Test realized P&L calculation for long position on close."""
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

        exit_price = Decimal("1.1075")
        realized_pnl = PnLCalculator.calculate_realized_pnl(position, exit_price)

        # (1.1075 - 1.1000) * 10000 = 0.0075 * 10000 = 75
        assert realized_pnl == Decimal("75.000000")

    def test_calculate_realized_pnl_short(self) -> None:
        """Test realized P&L calculation for short position on close."""
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

        exit_price = Decimal("1.0925")
        realized_pnl = PnLCalculator.calculate_realized_pnl(position, exit_price)

        # -(1.0925 - 1.1000) * 10000 = -(-0.0075 * 10000) = 75
        assert realized_pnl == Decimal("75.000000")

    def test_calculate_pnl_with_different_lot_sizes(self) -> None:
        """Test P&L calculation with different lot sizes."""
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

        # Small lot size
        position_small = Position.objects.create(
            account=account,
            position_id="POS-001",
            instrument="EUR_USD",
            direction="long",
            units=Decimal("1000.00"),
            entry_price=Decimal("1.1000"),
            current_price=Decimal("1.1000"),
        )

        pnl_small = PnLCalculator.calculate_unrealized_pnl(position_small, Decimal("1.1050"))
        # 0.0050 * 1000 = 5
        assert pnl_small == Decimal("5.000000")

        # Large lot size
        position_large = Position.objects.create(
            account=account,
            position_id="POS-002",
            instrument="EUR_USD",
            direction="long",
            units=Decimal("100000.00"),
            entry_price=Decimal("1.1000"),
            current_price=Decimal("1.1000"),
        )

        pnl_large = PnLCalculator.calculate_unrealized_pnl(position_large, Decimal("1.1050"))
        # 0.0050 * 100000 = 500
        assert pnl_large == Decimal("500.000000")

    def test_calculate_batch_unrealized_pnl(self) -> None:
        """Test batch P&L calculation for multiple positions."""
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

        position1 = Position.objects.create(
            account=account,
            position_id="POS-001",
            instrument="EUR_USD",
            direction="long",
            units=Decimal("10000.00"),
            entry_price=Decimal("1.1000"),
            current_price=Decimal("1.1000"),
        )

        position2 = Position.objects.create(
            account=account,
            position_id="POS-002",
            instrument="GBP_USD",
            direction="short",
            units=Decimal("5000.00"),
            entry_price=Decimal("1.3000"),
            current_price=Decimal("1.3000"),
        )

        positions = [position1, position2]
        prices = {
            "EUR_USD": Decimal("1.1050"),
            "GBP_USD": Decimal("1.2950"),
        }

        pnl_results = PnLCalculator.calculate_batch_unrealized_pnl(positions, prices)

        # EUR_USD: (1.1050 - 1.1000) * 10000 = 50
        assert pnl_results["POS-001"] == Decimal("50.000000")

        # GBP_USD: -(1.2950 - 1.3000) * 5000 = 25
        assert pnl_results["POS-002"] == Decimal("25.000000")

    def test_calculate_total_unrealized_pnl(self) -> None:
        """Test total P&L calculation for multiple positions."""
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

        position1 = Position.objects.create(
            account=account,
            position_id="POS-001",
            instrument="EUR_USD",
            direction="long",
            units=Decimal("10000.00"),
            entry_price=Decimal("1.1000"),
            current_price=Decimal("1.1000"),
        )

        position2 = Position.objects.create(
            account=account,
            position_id="POS-002",
            instrument="GBP_USD",
            direction="short",
            units=Decimal("5000.00"),
            entry_price=Decimal("1.3000"),
            current_price=Decimal("1.3000"),
        )

        positions = [position1, position2]
        prices = {
            "EUR_USD": Decimal("1.1050"),
            "GBP_USD": Decimal("1.2950"),
        }

        total_pnl = PnLCalculator.calculate_total_unrealized_pnl(positions, prices)

        # EUR_USD: 50, GBP_USD: 25, Total: 75
        assert total_pnl == Decimal("75.000000")

    def test_calculate_pips_profit_long(self) -> None:
        """Test pips profit calculation for long position."""
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

        current_price = Decimal("1.1050")
        pips = PnLCalculator.calculate_pips_profit(position, current_price)

        # 0.0050 * 10000 (pip multiplier) = 50 pips
        assert pips == Decimal("50.0000")

    def test_calculate_pips_profit_short(self) -> None:
        """Test pips profit calculation for short position."""
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

        current_price = Decimal("1.0950")
        pips = PnLCalculator.calculate_pips_profit(position, current_price)

        # -(1.0950 - 1.1000) * 10000 = 50 pips
        assert pips == Decimal("50.0000")

    def test_calculate_break_even_price_long(self) -> None:
        """Test break-even price calculation for long position."""
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

        commission = Decimal("10.00")
        break_even = PnLCalculator.calculate_break_even_price(position, commission)

        # 1.1000 + (10.00 / 10000) = 1.1000 + 0.0010 = 1.1010
        assert break_even == Decimal("1.1010")

    def test_calculate_break_even_price_short(self) -> None:
        """Test break-even price calculation for short position."""
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

        commission = Decimal("10.00")
        break_even = PnLCalculator.calculate_break_even_price(position, commission)

        # 1.1000 - (10.00 / 10000) = 1.1000 - 0.0010 = 1.0990
        assert break_even == Decimal("1.0990")
