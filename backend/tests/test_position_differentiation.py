"""
Unit tests for smart position differentiation logic.

Tests cover:
- Detection of multiple positions in same instrument
- Automatic suggestion for enabling position differentiation
- Optimal increment calculation to avoid collisions
- Edge cases (reaching min/max order sizes)
- Counter reset when no open positions exist

Requirements: 8.1, 9.1
"""

from decimal import Decimal

from django.contrib.auth import get_user_model

import pytest

from accounts.models import OandaAccount
from trading.models import Position, Strategy
from trading.position_differentiation import PositionDifferentiationManager

User = get_user_model()


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        username="testuser",
        email="test@example.com",
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
        currency="USD",
        balance=Decimal("10000.00"),
        enable_position_differentiation=False,
        position_diff_increment=1,
        position_diff_pattern="increment",
    )
    # Encrypt the token
    account.set_api_token("test_token_plain")
    account.save()
    return account


@pytest.fixture
def strategy(db, account):
    """Create a test strategy."""
    return Strategy.objects.create(
        account=account,
        strategy_type="test_strategy",
        is_active=True,
        config={},
        instrument="EUR_USD",
    )


@pytest.mark.django_db
class TestPositionDifferentiationManager:
    """Test suite for PositionDifferentiationManager."""

    def test_should_suggest_differentiation_no_positions(self, account):
        """Test that suggestion is not made when no positions exist."""
        manager = PositionDifferentiationManager(account)
        assert not manager.should_suggest_differentiation("EUR_USD")

    def test_should_suggest_differentiation_single_position(self, account, strategy):
        """Test that suggestion is not made with only one position."""
        Position.objects.create(
            account=account,
            strategy=strategy,
            position_id="1",
            instrument="EUR_USD",
            direction="long",
            units=Decimal("5000"),
            entry_price=Decimal("1.1000"),
            current_price=Decimal("1.1000"),
        )

        manager = PositionDifferentiationManager(account)
        assert not manager.should_suggest_differentiation("EUR_USD")

    def test_should_suggest_differentiation_multiple_positions(self, account, strategy):
        """Test that suggestion is made with multiple positions."""
        for i in range(3):
            Position.objects.create(
                account=account,
                strategy=strategy,
                position_id=str(i + 1),
                instrument="EUR_USD",
                direction="long",
                units=Decimal("5000"),
                entry_price=Decimal("1.1000"),
                current_price=Decimal("1.1000"),
            )

        manager = PositionDifferentiationManager(account)
        assert manager.should_suggest_differentiation("EUR_USD")

    def test_should_not_suggest_when_already_enabled(self, account, strategy):
        """Test that suggestion is not made when differentiation is already enabled."""
        account.enable_position_differentiation = True
        account.save()

        for i in range(3):
            Position.objects.create(
                account=account,
                strategy=strategy,
                position_id=str(i + 1),
                instrument="EUR_USD",
                direction="long",
                units=Decimal("5000"),
                entry_price=Decimal("1.1000"),
                current_price=Decimal("1.1000"),
            )

        manager = PositionDifferentiationManager(account)
        assert not manager.should_suggest_differentiation("EUR_USD")

    def test_detect_position_collisions(self, account, strategy):
        """Test detection of positions with identical unit sizes."""
        # Create positions with collisions
        Position.objects.create(
            account=account,
            strategy=strategy,
            position_id="1",
            instrument="EUR_USD",
            direction="long",
            units=Decimal("5000"),
            entry_price=Decimal("1.1000"),
            current_price=Decimal("1.1000"),
        )
        Position.objects.create(
            account=account,
            strategy=strategy,
            position_id="2",
            instrument="EUR_USD",
            direction="long",
            units=Decimal("5000"),  # Collision
            entry_price=Decimal("1.1000"),
            current_price=Decimal("1.1000"),
        )
        Position.objects.create(
            account=account,
            strategy=strategy,
            position_id="3",
            instrument="EUR_USD",
            direction="long",
            units=Decimal("6000"),  # Different size
            entry_price=Decimal("1.1000"),
            current_price=Decimal("1.1000"),
        )

        manager = PositionDifferentiationManager(account)
        collisions = manager.detect_position_collisions("EUR_USD")

        assert len(collisions) == 1
        assert Decimal("5000") in collisions

    def test_calculate_optimal_increment_no_positions(self, account):
        """Test optimal increment calculation with no existing positions."""
        manager = PositionDifferentiationManager(account)
        increment = manager.calculate_optimal_increment("EUR_USD", Decimal("5000"))
        assert increment == 1  # Default increment

    def test_calculate_optimal_increment_with_collisions(self, account, strategy):
        """Test optimal increment calculation to avoid collisions."""
        # The algorithm checks if the next 10 positions would collide
        # Create positions with some collisions
        for i in range(5):
            Position.objects.create(
                account=account,
                strategy=strategy,
                position_id=str(i + 1),
                instrument="EUR_USD",
                direction="long",
                units=Decimal(5000 + i),  # 5000, 5001, 5002, 5003, 5004
                entry_price=Decimal("1.1000"),
                current_price=Decimal("1.1000"),
            )

        manager = PositionDifferentiationManager(account)
        increment = manager.calculate_optimal_increment("EUR_USD", Decimal("5000"))

        # The algorithm should return a valid increment (1-100)
        assert 1 <= increment <= 100

        # The algorithm tries to find the smallest increment that avoids collisions
        # With positions 5000-5004, increment=1 would give us 5005-5014 which don't collide
        # So increment=1 is valid and optimal
        assert increment == 1

    def test_get_next_order_size_disabled(self, account):
        """Test next order size when differentiation is disabled."""
        manager = PositionDifferentiationManager(account)
        next_size, was_adjusted = manager.get_next_order_size("EUR_USD", Decimal("5000"))

        assert next_size == Decimal("5000")
        assert not was_adjusted

    def test_get_next_order_size_no_positions(self, account):
        """Test next order size with no open positions (counter reset)."""
        account.enable_position_differentiation = True
        account.save()

        manager = PositionDifferentiationManager(account)
        next_size, was_adjusted = manager.get_next_order_size("EUR_USD", Decimal("5000"))

        assert next_size == Decimal("5000")
        assert not was_adjusted  # No adjustment needed when no positions

    def test_get_next_order_size_increment_pattern(self, account, strategy):
        """Test next order size with increment pattern."""
        account.enable_position_differentiation = True
        account.position_diff_increment = 10
        account.position_diff_pattern = "increment"
        account.save()

        # Create 2 positions
        for i in range(2):
            Position.objects.create(
                account=account,
                strategy=strategy,
                position_id=str(i + 1),
                instrument="EUR_USD",
                direction="long",
                units=Decimal("5000"),
                entry_price=Decimal("1.1000"),
                current_price=Decimal("1.1000"),
            )

        manager = PositionDifferentiationManager(account)
        next_size, was_adjusted = manager.get_next_order_size("EUR_USD", Decimal("5000"))

        # With 2 positions, next should be 5000 + (10 * 2) = 5020
        assert next_size == Decimal("5020")
        assert was_adjusted

    def test_get_next_order_size_decrement_pattern(self, account, strategy):
        """Test next order size with decrement pattern."""
        account.enable_position_differentiation = True
        account.position_diff_increment = 10
        account.position_diff_pattern = "decrement"
        account.save()

        # Create 2 positions
        for i in range(2):
            Position.objects.create(
                account=account,
                strategy=strategy,
                position_id=str(i + 1),
                instrument="EUR_USD",
                direction="long",
                units=Decimal("5000"),
                entry_price=Decimal("1.1000"),
                current_price=Decimal("1.1000"),
            )

        manager = PositionDifferentiationManager(account)
        next_size, was_adjusted = manager.get_next_order_size("EUR_USD", Decimal("5000"))

        # With 2 positions, next should be 5000 - (10 * 2) = 4980
        assert next_size == Decimal("4980")
        assert was_adjusted

    def test_get_next_order_size_alternating_pattern(self, account, strategy):
        """Test next order size with alternating pattern."""
        account.enable_position_differentiation = True
        account.position_diff_increment = 10
        account.position_diff_pattern = "alternating"
        account.save()

        manager = PositionDifferentiationManager(account)

        # Test odd position count (should add)
        Position.objects.create(
            account=account,
            strategy=strategy,
            position_id="1",
            instrument="EUR_USD",
            direction="long",
            units=Decimal("5000"),
            entry_price=Decimal("1.1000"),
            current_price=Decimal("1.1000"),
        )

        next_size, was_adjusted = manager.get_next_order_size("EUR_USD", Decimal("5000"))
        assert next_size == Decimal("5010")  # 5000 + 10
        assert was_adjusted

        # Test even position count (should subtract)
        Position.objects.create(
            account=account,
            strategy=strategy,
            position_id="2",
            instrument="EUR_USD",
            direction="long",
            units=Decimal("5010"),
            entry_price=Decimal("1.1000"),
            current_price=Decimal("1.1000"),
        )

        next_size, was_adjusted = manager.get_next_order_size("EUR_USD", Decimal("5000"))
        assert next_size == Decimal("4990")  # 5000 - 10
        assert was_adjusted

    def test_get_next_order_size_min_boundary(self, account, strategy):
        """Test next order size respects minimum boundary."""
        account.enable_position_differentiation = True
        account.position_diff_increment = 100
        account.position_diff_pattern = "decrement"
        account.save()

        # Create enough positions to hit minimum
        for i in range(10):
            Position.objects.create(
                account=account,
                strategy=strategy,
                position_id=str(i + 1),
                instrument="EUR_USD",
                direction="long",
                units=Decimal("100"),
                entry_price=Decimal("1.1000"),
                current_price=Decimal("1.1000"),
            )

        manager = PositionDifferentiationManager(account)
        next_size, was_adjusted = manager.get_next_order_size("EUR_USD", Decimal("100"))

        # Should not go below minimum
        assert next_size >= Decimal(manager.MIN_ORDER_SIZE)

    def test_get_next_order_size_max_boundary(self, account, strategy):
        """Test next order size respects maximum boundary."""
        account.enable_position_differentiation = True
        account.position_diff_increment = 10000000
        account.position_diff_pattern = "increment"
        account.save()

        # Create enough positions to approach maximum
        for i in range(10):
            Position.objects.create(
                account=account,
                strategy=strategy,
                position_id=str(i + 1),
                instrument="EUR_USD",
                direction="long",
                units=Decimal("90000000"),
                entry_price=Decimal("1.1000"),
                current_price=Decimal("1.1000"),
            )

        manager = PositionDifferentiationManager(account)
        next_size, was_adjusted = manager.get_next_order_size("EUR_USD", Decimal("90000000"))

        # Should not exceed maximum
        assert next_size <= Decimal(manager.MAX_ORDER_SIZE)

    def test_check_boundary_reached_min_warning(self, account, strategy):
        """Test boundary warning when approaching minimum."""
        account.enable_position_differentiation = True
        account.position_diff_increment = 10
        account.position_diff_pattern = "decrement"
        account.save()

        # Create positions to approach minimum
        for i in range(5):
            Position.objects.create(
                account=account,
                strategy=strategy,
                position_id=str(i + 1),
                instrument="EUR_USD",
                direction="long",
                units=Decimal("50"),
                entry_price=Decimal("1.1000"),
                current_price=Decimal("1.1000"),
            )

        manager = PositionDifferentiationManager(account)
        warning = manager.check_boundary_reached("EUR_USD", Decimal("50"))

        assert warning is not None
        assert "minimum" in warning.lower()

    def test_check_boundary_reached_max_warning(self, account, strategy):
        """Test boundary warning when approaching maximum."""
        account.enable_position_differentiation = True
        account.position_diff_increment = 5000000
        account.position_diff_pattern = "increment"
        account.save()

        # Create positions to approach maximum
        for i in range(5):
            Position.objects.create(
                account=account,
                strategy=strategy,
                position_id=str(i + 1),
                instrument="EUR_USD",
                direction="long",
                units=Decimal("90000000"),
                entry_price=Decimal("1.1000"),
                current_price=Decimal("1.1000"),
            )

        manager = PositionDifferentiationManager(account)
        warning = manager.check_boundary_reached("EUR_USD", Decimal("90000000"))

        assert warning is not None
        assert "maximum" in warning.lower()

    def test_reset_counter_if_needed(self, account, strategy):
        """Test counter reset when no open positions exist."""
        # Create and then close a position
        position = Position.objects.create(
            account=account,
            strategy=strategy,
            position_id="1",
            instrument="EUR_USD",
            direction="long",
            units=Decimal("5000"),
            entry_price=Decimal("1.1000"),
            current_price=Decimal("1.1000"),
        )
        position.close(Decimal("1.1050"))

        manager = PositionDifferentiationManager(account)
        was_reset = manager.reset_counter_if_needed("EUR_USD")

        assert was_reset  # No open positions, counter should reset

    def test_get_differentiation_suggestion(self, account, strategy):
        """Test getting a complete differentiation suggestion."""
        # Create multiple positions with collisions
        for i in range(3):
            Position.objects.create(
                account=account,
                strategy=strategy,
                position_id=str(i + 1),
                instrument="EUR_USD",
                direction="long",
                units=Decimal("5000"),  # All same size (collisions)
                entry_price=Decimal("1.1000"),
                current_price=Decimal("1.1000"),
            )

        manager = PositionDifferentiationManager(account)
        suggestion = manager.get_differentiation_suggestion("EUR_USD", Decimal("5000"))

        assert suggestion is not None
        assert suggestion["instrument"] == "EUR_USD"
        assert suggestion["position_count"] == 3
        assert suggestion["has_collisions"] is True
        assert len(suggestion["collision_sizes"]) > 0
        assert suggestion["suggested_increment"] >= 1
        assert "message" in suggestion

    def test_get_statistics(self, account, strategy):
        """Test getting position differentiation statistics."""
        # Create positions in single instrument
        Position.objects.create(
            account=account,
            strategy=strategy,
            position_id="1",
            instrument="EUR_USD",
            direction="long",
            units=Decimal("5000"),
            entry_price=Decimal("1.1000"),
            current_price=Decimal("1.1000"),
        )
        Position.objects.create(
            account=account,
            strategy=strategy,
            position_id="2",
            instrument="EUR_USD",
            direction="long",
            units=Decimal("5000"),  # Collision
            entry_price=Decimal("1.1000"),
            current_price=Decimal("1.1000"),
        )
        Position.objects.create(
            account=account,
            strategy=strategy,
            position_id="3",
            instrument="GBP_USD",
            direction="long",
            units=Decimal("3000"),
            entry_price=Decimal("1.2500"),
            current_price=Decimal("1.2500"),
        )

        manager = PositionDifferentiationManager(account)
        stats = manager.get_statistics()

        assert stats["enabled"] is False
        assert stats["increment"] == 1
        assert stats["pattern"] == "increment"
        assert stats["total_open_positions"] == 3
        assert len(stats["positions_by_instrument"]) == 2
        assert len(stats["instrument_with_collisions"]) == 1
        assert stats["instrument_with_collisions"][0]["instrument"] == "EUR_USD"
