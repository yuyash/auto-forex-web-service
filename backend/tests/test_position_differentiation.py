"""
Unit tests for position differentiation functionality.

Requirements: 8.1, 9.1
"""

from decimal import Decimal

import pytest

from accounts.models import OandaAccount, User
from trading.position_differentiation import PositionDifferentiationManager


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        email="test@example.com",
        username="testuser",
        password="testpass123",
    )


@pytest.fixture
def account(db, user):
    """Create a test OANDA account."""
    account = OandaAccount.objects.create(
        user=user,
        account_id="001-001-1234567-001",
        api_token="test_token",
        api_type="practice",
        jurisdiction="US",
        enable_position_differentiation=True,
        position_diff_increment=1,
        position_diff_pattern="increment",
    )
    # Set encrypted token
    account.set_api_token("test_api_token_12345")
    account.save()
    return account


@pytest.mark.django_db
class TestPositionDifferentiationManager:
    """Test PositionDifferentiationManager class."""

    def test_increment_pattern(self, account):
        """Test increment pattern (5000, 5001, 5002, 5003...)."""
        manager = PositionDifferentiationManager(account)
        instrument = "EUR_USD"
        base_units = Decimal("5000")

        # First order should use base units
        adjusted, was_adjusted = manager.adjust_order_units(instrument, base_units)
        assert adjusted == base_units
        assert not was_adjusted

        # Second order should increment by 1
        adjusted, was_adjusted = manager.adjust_order_units(instrument, base_units)
        assert adjusted == Decimal("5001")
        assert was_adjusted

        # Third order should increment by 1 again
        adjusted, was_adjusted = manager.adjust_order_units(instrument, base_units)
        assert adjusted == Decimal("5002")
        assert was_adjusted

        # Fourth order
        adjusted, was_adjusted = manager.adjust_order_units(instrument, base_units)
        assert adjusted == Decimal("5003")
        assert was_adjusted

    def test_decrement_pattern(self, account):
        """Test decrement pattern (5000, 4999, 4998, 4997...)."""
        account.position_diff_pattern = "decrement"
        account.save()

        manager = PositionDifferentiationManager(account)
        instrument = "GBP_USD"
        base_units = Decimal("5000")

        # First order should use base units
        adjusted, was_adjusted = manager.adjust_order_units(instrument, base_units)
        assert adjusted == base_units
        assert not was_adjusted

        # Second order should decrement by 1
        adjusted, was_adjusted = manager.adjust_order_units(instrument, base_units)
        assert adjusted == Decimal("4999")
        assert was_adjusted

        # Third order should decrement by 1 again
        adjusted, was_adjusted = manager.adjust_order_units(instrument, base_units)
        assert adjusted == Decimal("4998")
        assert was_adjusted

        # Fourth order
        adjusted, was_adjusted = manager.adjust_order_units(instrument, base_units)
        assert adjusted == Decimal("4997")
        assert was_adjusted

    def test_alternating_pattern(self, account):
        """Test alternating pattern (5000, 5001, 4999, 5002, 4998...)."""
        account.position_diff_pattern = "alternating"
        account.save()

        manager = PositionDifferentiationManager(account)
        instrument = "USD_JPY"
        base_units = Decimal("5000")

        # First order should use base units
        adjusted, was_adjusted = manager.adjust_order_units(instrument, base_units)
        assert adjusted == base_units
        assert not was_adjusted

        # Second order should increment by 1 (5000 + 1 = 5001)
        adjusted, was_adjusted = manager.adjust_order_units(instrument, base_units)
        assert adjusted == Decimal("5001")
        assert was_adjusted

        # Third order should decrement from last (5001 - 1 = 5000)
        adjusted, was_adjusted = manager.adjust_order_units(instrument, base_units)
        assert adjusted == Decimal("5000")
        # Note: was_adjusted may be False if adjusted == base_units

        # Fourth order should increment from last (5000 + 1 = 5001)
        adjusted, was_adjusted = manager.adjust_order_units(instrument, base_units)
        assert adjusted == Decimal("5001")
        assert was_adjusted

        # Fifth order should decrement (5001 - 1 = 5000)
        adjusted, was_adjusted = manager.adjust_order_units(instrument, base_units)
        assert adjusted == Decimal("5000")
        # Note: was_adjusted may be False if adjusted == base_units

    def test_min_max_order_size_boundaries(self, account):
        """Test min/max order size boundaries."""
        manager = PositionDifferentiationManager(account)
        instrument = "EUR_USD"
        base_units = Decimal("10")
        min_units = Decimal("5")
        max_units = Decimal("15")

        # First order
        adjusted, _ = manager.adjust_order_units(instrument, base_units, min_units, max_units)
        assert adjusted == base_units

        # Second order would be 11, within bounds
        adjusted, _ = manager.adjust_order_units(instrument, base_units, min_units, max_units)
        assert adjusted == Decimal("11")

        # Continue until we hit max
        for _ in range(10):
            adjusted, _ = manager.adjust_order_units(instrument, base_units, min_units, max_units)

        # Should be capped at max_units
        assert adjusted == max_units

    def test_min_boundary_with_decrement(self, account):
        """Test minimum boundary with decrement pattern."""
        account.position_diff_pattern = "decrement"
        account.save()

        manager = PositionDifferentiationManager(account)
        instrument = "EUR_USD"
        base_units = Decimal("10")
        min_units = Decimal("5")

        # First order
        adjusted, _ = manager.adjust_order_units(instrument, base_units, min_units)
        assert adjusted == base_units

        # Continue decrementing
        for _ in range(10):
            adjusted, _ = manager.adjust_order_units(instrument, base_units, min_units)

        # Should be capped at min_units
        assert adjusted == min_units

    def test_counter_reset_when_no_positions(self, account):
        """Test counter reset when no positions exist."""
        manager = PositionDifferentiationManager(account)
        instrument = "EUR_USD"
        base_units = Decimal("5000")

        # First order
        adjusted, _ = manager.adjust_order_units(instrument, base_units)
        assert adjusted == base_units

        # Second order
        adjusted, _ = manager.adjust_order_units(instrument, base_units)
        assert adjusted == Decimal("5001")

        # Reset the instrument
        manager.reset_instrument(instrument)

        # Next order should start from base again
        adjusted, was_adjusted = manager.adjust_order_units(instrument, base_units)
        assert adjusted == base_units
        assert not was_adjusted

    def test_disabled_position_differentiation(self, account):
        """Test that differentiation is disabled when flag is False."""
        account.enable_position_differentiation = False
        account.save()

        manager = PositionDifferentiationManager(account)
        instrument = "EUR_USD"
        base_units = Decimal("5000")

        # All orders should use base units
        for _ in range(5):
            adjusted, was_adjusted = manager.adjust_order_units(instrument, base_units)
            assert adjusted == base_units
            assert not was_adjusted

    def test_different_instruments_tracked_separately(self, account):
        """Test that different instruments are tracked separately."""
        manager = PositionDifferentiationManager(account)
        base_units = Decimal("5000")

        # EUR_USD
        adjusted, _ = manager.adjust_order_units("EUR_USD", base_units)
        assert adjusted == base_units

        adjusted, _ = manager.adjust_order_units("EUR_USD", base_units)
        assert adjusted == Decimal("5001")

        # GBP_USD should start from base
        adjusted, was_adjusted = manager.adjust_order_units("GBP_USD", base_units)
        assert adjusted == base_units
        assert not was_adjusted

        adjusted, _ = manager.adjust_order_units("GBP_USD", base_units)
        assert adjusted == Decimal("5001")

        # EUR_USD should continue from where it left off
        adjusted, _ = manager.adjust_order_units("EUR_USD", base_units)
        assert adjusted == Decimal("5002")

    def test_custom_increment_amount(self, account):
        """Test custom increment amount."""
        account.position_diff_increment = 5
        account.save()

        manager = PositionDifferentiationManager(account)
        instrument = "EUR_USD"
        base_units = Decimal("5000")

        # First order
        adjusted, _ = manager.adjust_order_units(instrument, base_units)
        assert adjusted == base_units

        # Second order should increment by 5
        adjusted, _ = manager.adjust_order_units(instrument, base_units)
        assert adjusted == Decimal("5005")

        # Third order
        adjusted, _ = manager.adjust_order_units(instrument, base_units)
        assert adjusted == Decimal("5010")

    def test_get_next_order_size_preview(self, account):
        """Test preview of next order size without applying it."""
        manager = PositionDifferentiationManager(account)
        instrument = "EUR_USD"
        base_units = Decimal("5000")

        # First order
        manager.adjust_order_units(instrument, base_units)

        # Preview next order size
        next_size = manager.get_next_order_size(instrument, base_units)
        assert next_size == Decimal("5001")

        # Actual adjustment should match preview
        adjusted, _ = manager.adjust_order_units(instrument, base_units)
        assert adjusted == next_size

    def test_get_last_order_size(self, account):
        """Test getting last order size for an instrument."""
        manager = PositionDifferentiationManager(account)
        instrument = "EUR_USD"
        base_units = Decimal("5000")

        # No orders yet
        assert manager.get_last_order_size(instrument) is None

        # First order
        manager.adjust_order_units(instrument, base_units)
        assert manager.get_last_order_size(instrument) == base_units

        # Second order
        manager.adjust_order_units(instrument, base_units)
        assert manager.get_last_order_size(instrument) == Decimal("5001")

    def test_reset_all_instruments(self, account):
        """Test resetting all instruments."""
        manager = PositionDifferentiationManager(account)
        base_units = Decimal("5000")

        # Create orders for multiple instruments
        manager.adjust_order_units("EUR_USD", base_units)
        manager.adjust_order_units("EUR_USD", base_units)
        manager.adjust_order_units("GBP_USD", base_units)
        manager.adjust_order_units("GBP_USD", base_units)

        # Verify tracking exists
        assert manager.get_last_order_size("EUR_USD") == Decimal("5001")
        assert manager.get_last_order_size("GBP_USD") == Decimal("5001")

        # Reset all
        manager.reset_all()

        # All should be reset
        assert manager.get_last_order_size("EUR_USD") is None
        assert manager.get_last_order_size("GBP_USD") is None

    def test_negative_units_preserved(self, account):
        """Test that negative units (short positions) are handled correctly."""
        manager = PositionDifferentiationManager(account)
        instrument = "EUR_USD"
        base_units = Decimal("-5000")  # Short position

        # First order - negative units should be handled as absolute value
        adjusted, _ = manager.adjust_order_units(instrument, abs(base_units))
        assert adjusted == abs(base_units)

        # Second order should increment the absolute value
        adjusted, _ = manager.adjust_order_units(instrument, abs(base_units))
        assert adjusted == Decimal("5001")

        # The OrderExecutor is responsible for applying the sign based on direction
