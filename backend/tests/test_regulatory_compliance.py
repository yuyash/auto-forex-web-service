"""
Unit tests for regulatory compliance module.

Tests:
- US FIFO position closing logic
- US hedging prevention
- Leverage limit enforcement for all jurisdictions
- Compliance validation in order submission
- Jurisdiction-specific rule application
- Error messages for compliance violations

Requirements: 8.1, 8.2, 9.1
"""

from decimal import Decimal

from django.contrib.auth import get_user_model

import pytest

from accounts.models import OandaAccount
from trading.models import Position
from trading.regulatory_compliance import RegulatoryComplianceManager

User = get_user_model()


def create_position(
    account,
    instrument="EUR_USD",
    direction="long",
    units=1000,
    entry_price=1.1000,
    current_price=None,
    position_id=None,
    opened_at="2024-01-01T10:00:00Z",
):
    """Helper function to create a position with all required fields."""
    if current_price is None:
        current_price = entry_price
    if position_id is None:
        import uuid

        position_id = f"POS-{uuid.uuid4().hex[:8]}"

    return Position.objects.create(
        account=account,
        position_id=position_id,
        instrument=instrument,
        direction=direction,
        units=Decimal(str(units)),
        entry_price=Decimal(str(entry_price)),
        current_price=Decimal(str(current_price)),
        opened_at=opened_at,
    )


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        email="test@example.com",
        username="testuser",
        password="testpass123",
    )


@pytest.fixture
def us_account(user):
    """Create a US jurisdiction OANDA account."""
    account = OandaAccount.objects.create(
        user=user,
        account_id="001-001-1234567-001",
        api_type="practice",
        jurisdiction="US",
        balance=Decimal("10000.00"),
        margin_available=Decimal("5000.00"),
        margin_used=Decimal("1000.00"),
    )
    account.set_api_token("test_token_123")
    account.save()
    return account


@pytest.fixture
def jp_account(user):
    """Create a Japan jurisdiction OANDA account."""
    account = OandaAccount.objects.create(
        user=user,
        account_id="001-001-1234567-002",
        api_type="practice",
        jurisdiction="JP",
        balance=Decimal("10000.00"),
        margin_available=Decimal("5000.00"),
        margin_used=Decimal("1000.00"),
    )
    account.set_api_token("test_token_123")
    account.save()
    return account


@pytest.fixture
def eu_account(user):
    """Create an EU jurisdiction OANDA account."""
    account = OandaAccount.objects.create(
        user=user,
        account_id="001-001-1234567-003",
        api_type="practice",
        jurisdiction="EU",
        balance=Decimal("10000.00"),
        margin_available=Decimal("5000.00"),
        margin_used=Decimal("1000.00"),
    )
    account.set_api_token("test_token_123")
    account.save()
    return account


@pytest.mark.django_db
class TestUSComplianceRules:
    """Test US NFA/CFTC compliance rules."""

    def test_us_hedging_prevention(self, us_account):
        """Test that US accounts cannot create hedge positions."""
        # Create an existing long position
        create_position(account=us_account, direction="long", units=1000)

        compliance_mgr = RegulatoryComplianceManager(us_account)

        # Try to create a short position (hedge)
        order_request = {
            "instrument": "EUR_USD",
            "units": -1000,  # Short
            "order_type": "market",
        }

        is_valid, error_message = compliance_mgr.validate_order(order_request)

        assert not is_valid
        assert error_message is not None
        assert "Hedging is not allowed" in error_message
        assert error_message is not None
        assert "NFA Rule 2-43b" in error_message

    def test_us_hedging_allowed_same_direction(self, us_account):
        """Test that US accounts can add to existing positions in same direction."""
        # Create an existing long position
        create_position(account=us_account, direction="long", units=1000)

        compliance_mgr = RegulatoryComplianceManager(us_account)

        # Try to create another long position (same direction)
        order_request = {
            "instrument": "EUR_USD",
            "units": 1000,  # Long
            "order_type": "market",
        }

        is_valid, error_message = compliance_mgr.validate_order(order_request)

        assert is_valid
        assert error_message is None

    def test_us_fifo_position_closing(self, us_account):
        """Test FIFO position closing logic for US accounts."""
        # Create multiple positions with different timestamps
        pos1 = create_position(
            account=us_account,
            direction="long",
            units=1000,
            entry_price=1.1000,
            opened_at="2024-01-01T10:00:00Z",
        )
        create_position(
            account=us_account,
            direction="long",
            units=1000,
            entry_price=1.1050,
            opened_at="2024-01-01T11:00:00Z",
        )

        compliance_mgr = RegulatoryComplianceManager(us_account)

        # Get FIFO position to close
        fifo_position = compliance_mgr.get_fifo_position_to_close("EUR_USD", 1000)

        assert fifo_position is not None
        assert fifo_position.id == pos1.id  # Should return oldest position

    def test_us_leverage_limits_major_pairs(self, us_account):
        """Test US leverage limits for major pairs (50:1)."""
        compliance_mgr = RegulatoryComplianceManager(us_account)

        # Order that exceeds available margin
        order_request = {
            "instrument": "EUR_USD",  # Major pair
            "units": 300000,  # Would require 6000 margin at 50:1
            "order_type": "market",
        }

        is_valid, error_message = compliance_mgr.validate_order(order_request)

        assert not is_valid
        assert error_message is not None
        assert "leverage limits" in error_message.lower()
        assert error_message is not None
        assert "50:1" in error_message

    def test_us_leverage_limits_minor_pairs(self, us_account):
        """Test US leverage limits for minor pairs (20:1)."""
        compliance_mgr = RegulatoryComplianceManager(us_account)

        # Order that exceeds available margin
        order_request = {
            "instrument": "EUR_GBP",  # Minor pair
            "units": 150000,  # Would require 7500 margin at 20:1
            "order_type": "market",
        }

        is_valid, error_message = compliance_mgr.validate_order(order_request)

        assert not is_valid
        assert error_message is not None
        assert "leverage limits" in error_message.lower()
        assert error_message is not None
        assert "20:1" in error_message

    def test_us_should_reduce_position_instead(self, us_account):
        """Test that opposing orders should reduce positions for US accounts."""
        # Create an existing long position
        create_position(account=us_account, direction="long", units=2000)

        compliance_mgr = RegulatoryComplianceManager(us_account)

        # Check if short order should reduce position
        should_reduce, units_to_reduce = compliance_mgr.should_reduce_position_instead(
            "EUR_USD", -1000
        )

        assert should_reduce is True
        assert units_to_reduce == 1000


@pytest.mark.django_db
class TestJapanComplianceRules:
    """Test Japan FSA compliance rules."""

    def test_jp_hedging_allowed(self, jp_account):
        """Test that Japan accounts can create hedge positions."""
        # Create an existing long position
        create_position(account=jp_account, direction="long", units=1000)

        compliance_mgr = RegulatoryComplianceManager(jp_account)

        # Try to create a short position (hedge) - should be allowed
        order_request = {
            "instrument": "EUR_USD",
            "units": -1000,  # Short
            "order_type": "market",
        }

        is_valid, error_message = compliance_mgr.validate_order(order_request)

        assert is_valid
        assert error_message is None

    def test_jp_leverage_limits(self, jp_account):
        """Test Japan leverage limits (25:1)."""
        compliance_mgr = RegulatoryComplianceManager(jp_account)

        # Order that exceeds available margin
        order_request = {
            "instrument": "EUR_USD",
            "units": 150000,  # Would require 6000 margin at 25:1
            "order_type": "market",
        }

        is_valid, error_message = compliance_mgr.validate_order(order_request)

        assert not is_valid
        assert error_message is not None
        assert "leverage limit" in error_message.lower()
        assert error_message is not None
        assert "25:1" in error_message

    def test_jp_position_size_limits(self, jp_account):
        """Test Japan position size limits based on account equity."""
        # Set high margin available to pass leverage check
        jp_account.margin_available = Decimal("20000.00")
        jp_account.save()

        compliance_mgr = RegulatoryComplianceManager(jp_account)

        # Order that exceeds position size limit (balance * 25)
        order_request = {
            "instrument": "EUR_USD",
            "units": 300000,  # Exceeds 10000 * 25 = 250000
            "order_type": "market",
        }

        is_valid, error_message = compliance_mgr.validate_order(order_request)

        assert not is_valid
        assert error_message is not None
        assert "position size" in error_message.lower()


@pytest.mark.django_db
class TestEUComplianceRules:
    """Test EU ESMA compliance rules."""

    def test_eu_leverage_limits_major_pairs(self, eu_account):
        """Test EU leverage limits for major pairs (30:1)."""
        compliance_mgr = RegulatoryComplianceManager(eu_account)

        # Order that exceeds available margin
        order_request = {
            "instrument": "EUR_USD",  # Major pair
            "units": 180000,  # Would require 6000 margin at 30:1
            "order_type": "market",
        }

        is_valid, error_message = compliance_mgr.validate_order(order_request)

        assert not is_valid
        assert error_message is not None
        assert "leverage limit" in error_message.lower()
        assert error_message is not None
        assert "30:1" in error_message

    def test_eu_leverage_limits_minor_pairs(self, eu_account):
        """Test EU leverage limits for minor pairs (20:1)."""
        compliance_mgr = RegulatoryComplianceManager(eu_account)

        # Order that exceeds available margin
        order_request = {
            "instrument": "EUR_GBP",  # Minor pair
            "units": 120000,  # Would require 6000 margin at 20:1
            "order_type": "market",
        }

        is_valid, error_message = compliance_mgr.validate_order(order_request)

        assert not is_valid
        assert error_message is not None
        assert "leverage limit" in error_message.lower()
        assert error_message is not None
        assert "20:1" in error_message

    def test_eu_negative_balance_protection(self, eu_account):
        """Test EU negative balance protection."""
        # Set account balance to negative
        eu_account.balance = Decimal("-100.00")
        eu_account.unrealized_pnl = Decimal("0.00")
        eu_account.save()

        compliance_mgr = RegulatoryComplianceManager(eu_account)

        order_request = {
            "instrument": "EUR_USD",
            "units": 1000,
            "order_type": "market",
        }

        is_valid, error_message = compliance_mgr.validate_order(order_request)

        assert not is_valid
        assert error_message is not None
        assert "negative balance protection" in error_message.lower()

    def test_eu_margin_closeout_trigger(self, eu_account):
        """Test EU margin close-out at 50% level."""
        # Set margin level to 40% (below 50% threshold)
        eu_account.margin_used = Decimal("1000.00")
        eu_account.unrealized_pnl = Decimal("-600.00")  # 400 / 1000 = 40%
        eu_account.save()

        compliance_mgr = RegulatoryComplianceManager(eu_account)

        should_trigger = compliance_mgr.should_trigger_margin_closeout()

        assert should_trigger is True


@pytest.mark.django_db
class TestComplianceValidation:
    """Test general compliance validation."""

    def test_compliance_validation_with_valid_order(self, us_account):
        """Test compliance validation with a valid order."""
        compliance_mgr = RegulatoryComplianceManager(us_account)

        order_request = {
            "instrument": "EUR_USD",
            "units": 1000,
            "order_type": "market",
        }

        is_valid, error_message = compliance_mgr.validate_order(order_request)

        assert is_valid
        assert error_message is None

    def test_jurisdiction_info(self, us_account):
        """Test getting jurisdiction information."""
        compliance_mgr = RegulatoryComplianceManager(us_account)

        info = compliance_mgr.get_jurisdiction_info()

        assert info["jurisdiction"] == "US"
        assert info["hedging_allowed"] is False
        assert info["fifo_required"] is True
        assert "leverage_limits" in info

    def test_error_messages_are_clear(self, us_account):
        """Test that error messages are clear and informative."""
        # Create an existing long position
        create_position(account=us_account, direction="long", units=1000)

        compliance_mgr = RegulatoryComplianceManager(us_account)

        # Try to create a hedge
        order_request = {
            "instrument": "EUR_USD",
            "units": -1000,
            "order_type": "market",
        }

        is_valid, error_message = compliance_mgr.validate_order(order_request)

        assert not is_valid
        assert error_message is not None
        assert len(error_message) > 20  # Should be descriptive
        assert error_message is not None
        assert "NFA" in error_message or "hedging" in error_message.lower()


@pytest.mark.django_db
class TestMultipleJurisdictions:
    """Test behavior across different jurisdictions."""

    def test_different_jurisdictions_different_rules(self, us_account, jp_account):
        """Test that different jurisdictions apply different rules."""
        # Create long positions for both accounts
        create_position(account=us_account, direction="long", units=1000)
        create_position(account=jp_account, direction="long", units=1000)

        us_compliance = RegulatoryComplianceManager(us_account)
        jp_compliance = RegulatoryComplianceManager(jp_account)

        # Try to create short positions (hedge)
        order_request = {
            "instrument": "EUR_USD",
            "units": -1000,
            "order_type": "market",
        }

        us_valid, us_error = us_compliance.validate_order(order_request)
        jp_valid, jp_error = jp_compliance.validate_order(order_request)

        # US should reject, Japan should allow
        assert not us_valid
        assert jp_valid
        assert us_error is not None
        assert jp_error is None
