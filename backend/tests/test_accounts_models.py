"""
Unit tests for accounts models.

Tests cover:
- User model field validation
- UserSettings model defaults
- UserSession creation and expiry
- BlockedIP model constraints

Requirements: 1.1, 1.2, 2.1, 2.2
"""

from datetime import timedelta

from django.utils import timezone

import pytest

from accounts.models import BlockedIP, User, UserSession, UserSettings


@pytest.mark.django_db
class TestUserModel:
    """Test cases for User model."""

    def test_user_creation_with_email(self) -> None:
        """Test creating a user with email."""
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        assert user.email == "test@example.com"
        assert user.username == "testuser"
        assert user.check_password("testpass123")
        assert user.timezone == "UTC"
        assert user.language == "en"
        assert not user.is_locked
        assert user.failed_login_attempts == 0

    def test_user_email_unique_constraint(self) -> None:
        """Test that email must be unique."""
        from django.db import IntegrityError

        User.objects.create_user(
            username="user1",
            email="test@example.com",
            password="pass123",
        )
        with pytest.raises(IntegrityError):
            User.objects.create_user(
                username="user2",
                email="test@example.com",
                password="pass456",
            )

    def test_user_timezone_field(self) -> None:
        """Test user timezone field."""
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="pass123",
            timezone="America/New_York",
        )
        assert user.timezone == "America/New_York"

    def test_user_language_choices(self) -> None:
        """Test user language field with valid choices."""
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="pass123",
            language="ja",
        )
        assert user.language == "ja"

    def test_user_increment_failed_login(self) -> None:
        """Test incrementing failed login attempts."""
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="pass123",
        )
        assert user.failed_login_attempts == 0

        user.increment_failed_login()
        user.refresh_from_db()
        assert user.failed_login_attempts == 1
        assert user.last_login_attempt is not None

    def test_user_reset_failed_login(self) -> None:
        """Test resetting failed login attempts."""
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="pass123",
        )
        user.failed_login_attempts = 5
        user.last_login_attempt = timezone.now()
        user.save()

        user.reset_failed_login()
        user.refresh_from_db()
        assert user.failed_login_attempts == 0
        assert user.last_login_attempt is None

    def test_user_lock_account(self) -> None:
        """Test locking user account."""
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="pass123",
        )
        assert not user.is_locked

        user.lock_account()
        user.refresh_from_db()
        assert user.is_locked

    def test_user_unlock_account(self) -> None:
        """Test unlocking user account."""
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="pass123",
        )
        user.is_locked = True
        user.failed_login_attempts = 10
        user.save()

        user.unlock_account()
        user.refresh_from_db()
        assert not user.is_locked
        assert user.failed_login_attempts == 0


@pytest.mark.django_db
class TestUserSettingsModel:
    """Test cases for UserSettings model."""

    def test_user_settings_creation_with_defaults(self) -> None:
        """Test creating user settings with default values."""
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="pass123",
        )
        settings = UserSettings.objects.create(user=user)

        assert settings.user == user
        assert settings.default_lot_size == 1.0
        assert settings.default_scaling_mode == "additive"
        assert settings.default_retracement_pips == 30
        assert settings.default_take_profit_pips == 25
        assert settings.notification_enabled is True
        assert settings.notification_email is True
        assert settings.notification_browser is True
        assert settings.settings_json == {}

    def test_user_settings_custom_values(self) -> None:
        """Test creating user settings with custom values."""
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="pass123",
        )
        settings = UserSettings.objects.create(
            user=user,
            default_lot_size=2.5,
            default_scaling_mode="multiplicative",
            default_retracement_pips=50,
            default_take_profit_pips=40,
            notification_enabled=False,
        )

        assert settings.default_lot_size == 2.5
        assert settings.default_scaling_mode == "multiplicative"
        assert settings.default_retracement_pips == 50
        assert settings.default_take_profit_pips == 40
        assert settings.notification_enabled is False

    def test_user_settings_one_to_one_relationship(self) -> None:
        """Test that each user can have only one settings object."""
        from django.db import IntegrityError

        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="pass123",
        )
        UserSettings.objects.create(user=user)

        with pytest.raises(IntegrityError):
            UserSettings.objects.create(user=user)

    def test_user_settings_json_field(self) -> None:
        """Test storing additional settings in JSON field."""
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="pass123",
        )
        custom_settings = {
            "theme": "dark",
            "chart_type": "candlestick",
            "indicators": ["ATR", "MA"],
        }
        settings = UserSettings.objects.create(
            user=user,
            settings_json=custom_settings,
        )

        assert settings.settings_json == custom_settings
        assert settings.settings_json["theme"] == "dark"


@pytest.mark.django_db
class TestUserSessionModel:
    """Test cases for UserSession model."""

    def test_user_session_creation(self) -> None:
        """Test creating a user session."""
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="pass123",
        )
        session = UserSession.objects.create(
            user=user,
            session_key="test_session_key_123",
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
        )

        assert session.user == user
        assert session.session_key == "test_session_key_123"
        assert session.ip_address == "192.168.1.1"
        assert session.user_agent == "Mozilla/5.0"
        assert session.is_active is True
        assert session.logout_time is None

    def test_user_session_unique_session_key(self) -> None:
        """Test that session_key must be unique."""
        from django.db import IntegrityError

        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="pass123",
        )
        UserSession.objects.create(
            user=user,
            session_key="unique_key",
            ip_address="192.168.1.1",
        )

        with pytest.raises(IntegrityError):
            UserSession.objects.create(
                user=user,
                session_key="unique_key",
                ip_address="192.168.1.2",
            )

    def test_user_session_terminate(self) -> None:
        """Test terminating a user session."""
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="pass123",
        )
        session = UserSession.objects.create(
            user=user,
            session_key="test_key",
            ip_address="192.168.1.1",
        )
        assert session.is_active is True

        session.terminate()
        session.refresh_from_db()
        assert session.is_active is False
        assert session.logout_time is not None

    def test_user_session_is_expired(self) -> None:
        """Test checking if session is expired."""
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="pass123",
        )

        # Create an old session
        old_session = UserSession.objects.create(
            user=user,
            session_key="old_key",
            ip_address="192.168.1.1",
        )
        old_session.login_time = timezone.now() - timedelta(hours=25)
        old_session.save()

        assert old_session.is_expired(expiry_hours=24) is True

        # Create a recent session
        new_session = UserSession.objects.create(
            user=user,
            session_key="new_key",
            ip_address="192.168.1.2",
        )
        assert new_session.is_expired(expiry_hours=24) is False

    def test_user_session_multiple_per_user(self) -> None:
        """Test that a user can have multiple sessions."""
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="pass123",
        )
        session1 = UserSession.objects.create(
            user=user,
            session_key="key1",
            ip_address="192.168.1.1",
        )
        session2 = UserSession.objects.create(
            user=user,
            session_key="key2",
            ip_address="192.168.1.2",
        )

        assert user.sessions.count() == 2
        assert session1 in user.sessions.all()
        assert session2 in user.sessions.all()


@pytest.mark.django_db
class TestBlockedIPModel:
    """Test cases for BlockedIP model."""

    def test_blocked_ip_creation(self) -> None:
        """Test creating a blocked IP entry."""
        blocked_until = timezone.now() + timedelta(hours=1)
        blocked_ip = BlockedIP.objects.create(
            ip_address="192.168.1.100",
            reason="Too many failed login attempts",
            failed_attempts=5,
            blocked_until=blocked_until,
        )

        assert blocked_ip.ip_address == "192.168.1.100"
        assert blocked_ip.reason == "Too many failed login attempts"
        assert blocked_ip.failed_attempts == 5
        assert blocked_ip.blocked_until == blocked_until
        assert blocked_ip.is_permanent is False

    def test_blocked_ip_unique_constraint(self) -> None:
        """Test that IP address must be unique."""
        from django.db import IntegrityError

        blocked_until = timezone.now() + timedelta(hours=1)
        BlockedIP.objects.create(
            ip_address="192.168.1.100",
            reason="Test",
            blocked_until=blocked_until,
        )

        with pytest.raises(IntegrityError):
            BlockedIP.objects.create(
                ip_address="192.168.1.100",
                reason="Another test",
                blocked_until=blocked_until,
            )

    def test_blocked_ip_is_active_temporary(self) -> None:
        """Test checking if temporary block is active."""
        # Active block
        active_block = BlockedIP.objects.create(
            ip_address="192.168.1.100",
            reason="Test",
            blocked_until=timezone.now() + timedelta(hours=1),
        )
        assert active_block.is_active() is True

        # Expired block
        expired_block = BlockedIP.objects.create(
            ip_address="192.168.1.101",
            reason="Test",
            blocked_until=timezone.now() - timedelta(hours=1),
        )
        assert expired_block.is_active() is False

    def test_blocked_ip_is_active_permanent(self) -> None:
        """Test that permanent blocks are always active."""
        permanent_block = BlockedIP.objects.create(
            ip_address="192.168.1.100",
            reason="Malicious activity",
            blocked_until=timezone.now() - timedelta(hours=1),
            is_permanent=True,
        )
        assert permanent_block.is_active() is True

    def test_blocked_ip_unblock(self) -> None:
        """Test unblocking an IP address."""
        blocked_ip = BlockedIP.objects.create(
            ip_address="192.168.1.100",
            reason="Test",
            blocked_until=timezone.now() + timedelta(hours=1),
        )
        assert blocked_ip.is_active() is True

        blocked_ip.unblock()
        blocked_ip.refresh_from_db()
        assert blocked_ip.is_active() is False

    def test_blocked_ip_permanent_cannot_unblock(self) -> None:
        """Test that permanent blocks cannot be unblocked with unblock method."""
        permanent_block = BlockedIP.objects.create(
            ip_address="192.168.1.100",
            reason="Malicious activity",
            blocked_until=timezone.now() + timedelta(hours=1),
            is_permanent=True,
        )

        permanent_block.unblock()
        permanent_block.refresh_from_db()
        # Permanent blocks remain active even after unblock() is called
        assert permanent_block.is_active() is True

    def test_blocked_ip_with_admin_user(self) -> None:
        """Test creating a blocked IP with admin user reference."""
        admin_user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="pass123",
            is_staff=True,
        )
        blocked_ip = BlockedIP.objects.create(
            ip_address="192.168.1.100",
            reason="Manual block by admin",
            blocked_until=timezone.now() + timedelta(hours=1),
            created_by=admin_user,
        )

        assert blocked_ip.created_by == admin_user


@pytest.mark.django_db
class TestOandaAccountModel:
    """Test cases for OandaAccount model.

    Requirements: 4.1, 4.2, 4.4
    """

    def test_oanda_account_creation(self) -> None:
        """Test creating an OANDA account."""
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="pass123",
        )

        from accounts.models import OandaAccount

        account = OandaAccount.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_type="practice",
            currency="USD",
        )
        # Set token using encryption method
        account.set_api_token("test_api_token_12345")
        account.save()

        assert account.user == user
        assert account.account_id == "001-001-1234567-001"
        assert account.api_type == "practice"
        assert account.currency == "USD"
        assert account.balance == 0
        assert account.margin_used == 0
        assert account.margin_available == 0
        assert account.unrealized_pnl == 0
        assert account.is_active is True
        assert account.status == "idle"

    def test_oanda_account_api_token_encryption(self) -> None:
        """Test API token encryption and decryption."""
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="pass123",
        )

        from accounts.models import OandaAccount

        account = OandaAccount.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_type="practice",
        )

        original_token = "my_secret_api_token_12345"
        account.set_api_token(original_token)
        account.save()

        # Verify token is encrypted in database
        account.refresh_from_db()
        assert account.api_token != original_token

        # Verify token can be decrypted
        decrypted_token = account.get_api_token()
        assert decrypted_token == original_token

    def test_oanda_account_api_token_decryption(self) -> None:
        """Test that encrypted token can be decrypted correctly."""
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="pass123",
        )

        from accounts.models import OandaAccount

        account = OandaAccount.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_type="live",
        )

        test_token = "live_api_token_abcdef123456"
        account.set_api_token(test_token)
        account.save()

        # Retrieve from database and decrypt
        account_from_db = OandaAccount.objects.get(id=account.id)
        retrieved_token = account_from_db.get_api_token()

        assert retrieved_token == test_token

    def test_oanda_account_unique_constraint(self) -> None:
        """Test unique constraint on user + account_id."""
        from django.db import IntegrityError

        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="pass123",
        )

        from accounts.models import OandaAccount

        account1 = OandaAccount.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_type="practice",
        )
        account1.set_api_token("token1")
        account1.save()

        # Try to create another account with same user + account_id
        with pytest.raises(IntegrityError):
            account2 = OandaAccount.objects.create(
                user=user,
                account_id="001-001-1234567-001",
                api_type="live",
            )
            account2.set_api_token("token2")
            account2.save()

    def test_oanda_account_different_users_same_account_id(self) -> None:
        """Test that different users can have the same account_id."""
        user1 = User.objects.create_user(
            username="user1",
            email="user1@example.com",
            password="pass123",
        )
        user2 = User.objects.create_user(
            username="user2",
            email="user2@example.com",
            password="pass123",
        )

        from accounts.models import OandaAccount

        account1 = OandaAccount.objects.create(
            user=user1,
            account_id="001-001-1234567-001",
            api_type="practice",
        )
        account1.set_api_token("token1")
        account1.save()

        # Different user can have same account_id
        account2 = OandaAccount.objects.create(
            user=user2,
            account_id="001-001-1234567-001",
            api_type="practice",
        )
        account2.set_api_token("token2")
        account2.save()

        assert account1.account_id == account2.account_id
        assert account1.user != account2.user

    def test_oanda_account_balance_validation(self) -> None:
        """Test balance and margin field validation."""
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="pass123",
        )

        from decimal import Decimal

        from accounts.models import OandaAccount

        account = OandaAccount.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_type="practice",
            balance=Decimal("10000.50"),
            margin_used=Decimal("2500.25"),
            margin_available=Decimal("7500.25"),
            unrealized_pnl=Decimal("-150.75"),
        )
        account.set_api_token("token")
        account.save()

        assert account.balance == Decimal("10000.50")
        assert account.margin_used == Decimal("2500.25")
        assert account.margin_available == Decimal("7500.25")
        assert account.unrealized_pnl == Decimal("-150.75")

    def test_oanda_account_api_type_choices(self) -> None:
        """Test api_type choices (practice/live)."""
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="pass123",
        )

        from accounts.models import OandaAccount

        # Test practice account
        practice_account = OandaAccount.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_type="practice",
        )
        practice_account.set_api_token("practice_token")
        practice_account.save()
        assert practice_account.api_type == "practice"

        # Test live account
        live_account = OandaAccount.objects.create(
            user=user,
            account_id="001-001-1234567-002",
            api_type="live",
        )
        live_account.set_api_token("live_token")
        live_account.save()
        assert live_account.api_type == "live"

    def test_oanda_account_api_hostname_property(self) -> None:
        """Test api_hostname property returns correct URL."""
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="pass123",
        )

        from django.conf import settings

        from accounts.models import OandaAccount

        # Practice account
        practice_account = OandaAccount.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_type="practice",
        )
        practice_account.set_api_token("token")
        practice_account.save()
        assert practice_account.api_hostname == settings.OANDA_PRACTICE_API

        # Live account
        live_account = OandaAccount.objects.create(
            user=user,
            account_id="001-001-1234567-002",
            api_type="live",
        )
        live_account.set_api_token("token")
        live_account.save()
        assert live_account.api_hostname == settings.OANDA_LIVE_API

    def test_oanda_account_update_balance(self) -> None:
        """Test updating account balance and margin."""
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="pass123",
        )

        from accounts.models import OandaAccount

        account = OandaAccount.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_type="practice",
        )
        account.set_api_token("token")
        account.save()

        # Update balance
        account.update_balance(
            balance=15000.00,
            margin_used=3000.00,
            margin_available=12000.00,
            unrealized_pnl=250.50,
        )

        account.refresh_from_db()
        assert float(account.balance) == 15000.00
        assert float(account.margin_used) == 3000.00
        assert float(account.margin_available) == 12000.00
        assert float(account.unrealized_pnl) == 250.50

    def test_oanda_account_set_status(self) -> None:
        """Test setting account status."""
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="pass123",
        )

        from accounts.models import OandaAccount

        account = OandaAccount.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_type="practice",
        )
        account.set_api_token("token")
        account.save()

        assert account.status == "idle"

        # Test status changes
        account.set_status("trading")
        account.refresh_from_db()
        assert account.status == "trading"

        account.set_status("paused")
        account.refresh_from_db()
        assert account.status == "paused"

        account.set_status("error")
        account.refresh_from_db()
        assert account.status == "error"

    def test_oanda_account_activate_deactivate(self) -> None:
        """Test activating and deactivating account."""
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="pass123",
        )

        from accounts.models import OandaAccount

        account = OandaAccount.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_type="practice",
        )
        account.set_api_token("token")
        account.save()

        assert account.is_active is True

        # Deactivate
        account.deactivate()
        account.refresh_from_db()
        assert account.is_active is False
        assert account.status == "idle"

        # Activate
        account.activate()
        account.refresh_from_db()
        assert account.is_active is True

    def test_oanda_account_multiple_accounts_per_user(self) -> None:
        """Test that a user can have multiple OANDA accounts."""
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="pass123",
        )

        from accounts.models import OandaAccount

        account1 = OandaAccount.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_type="practice",
        )
        account1.set_api_token("token1")
        account1.save()

        account2 = OandaAccount.objects.create(
            user=user,
            account_id="001-001-1234567-002",
            api_type="live",
        )
        account2.set_api_token("token2")
        account2.save()

        assert user.oanda_accounts.count() == 2
        assert account1 in user.oanda_accounts.all()
        assert account2 in user.oanda_accounts.all()
