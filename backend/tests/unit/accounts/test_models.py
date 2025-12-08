"""
Unit tests for accounts models.

Tests cover:
- User model field validation
- UserSettings model defaults
- UserSession creation and expiry
- BlockedIP model constraints
- WhitelistedEmail model and email checking
"""

from datetime import timedelta

from django.utils import timezone

import pytest

from apps.accounts.models import BlockedIP, User, UserSession, UserSettings, WhitelistedEmail


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

    def test_user_str_representation(self) -> None:
        """Test user string representation."""
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="pass123",
        )
        assert str(user) == "test@example.com (testuser)"

    def test_user_generate_verification_token(self) -> None:
        """Test generating email verification token."""
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="pass123",
        )
        assert user.email_verification_token is None
        assert user.email_verification_sent_at is None

        token = user.generate_verification_token()
        user.refresh_from_db()

        assert token is not None
        assert len(token) > 0
        assert user.email_verification_token == token
        assert user.email_verification_sent_at is not None

    def test_user_verify_email_success(self) -> None:
        """Test successful email verification."""
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="pass123",
        )
        token = user.generate_verification_token()

        result = user.verify_email(token)
        user.refresh_from_db()

        assert result is True
        assert user.email_verified is True
        assert user.email_verification_token is None
        assert user.email_verification_sent_at is None

    def test_user_verify_email_invalid_token(self) -> None:
        """Test email verification with invalid token."""
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="pass123",
        )
        user.generate_verification_token()

        result = user.verify_email("invalid_token")
        user.refresh_from_db()

        assert result is False
        assert user.email_verified is False

    def test_user_verify_email_no_token(self) -> None:
        """Test email verification when no token exists."""
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="pass123",
        )

        result = user.verify_email("any_token")

        assert result is False
        assert user.email_verified is False

    def test_user_verify_email_expired_token(self) -> None:
        """Test email verification with expired token."""
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="pass123",
        )
        token = user.generate_verification_token()

        # Set token sent time to 25 hours ago (expired)
        user.email_verification_sent_at = timezone.now() - timedelta(hours=25)
        user.save()

        result = user.verify_email(token)
        user.refresh_from_db()

        assert result is False
        assert user.email_verified is False


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
        # UserSettings is auto-created by signal, so get it instead of creating
        settings = UserSettings.objects.get(user=user)

        assert settings.user == user
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
        # UserSettings is auto-created by signal, so update it instead of creating
        settings = UserSettings.objects.get(user=user)
        settings.notification_enabled = False
        settings.notification_email = False
        settings.notification_browser = False
        settings.save()

        assert settings.notification_enabled is False
        assert settings.notification_email is False
        assert settings.notification_browser is False

    def test_user_settings_one_to_one_relationship(self) -> None:
        """Test that each user can have only one settings object."""
        from django.db import IntegrityError

        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="pass123",
        )
        # UserSettings is auto-created by signal, verify it exists
        assert UserSettings.objects.filter(user=user).count() == 1

        # Try to create another one manually
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
        # UserSettings is auto-created by signal, so update it instead of creating
        settings = UserSettings.objects.get(user=user)
        settings.settings_json = custom_settings
        settings.save()

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
class TestWhitelistedEmailModel:
    """Test cases for WhitelistedEmail model."""

    def test_whitelisted_email_creation(self) -> None:
        """Test creating a whitelisted email entry."""
        admin_user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="pass123",
            is_staff=True,
        )
        whitelist = WhitelistedEmail.objects.create(
            email_pattern="user@example.com",
            description="Test user email",
            created_by=admin_user,
        )

        assert whitelist.email_pattern == "user@example.com"
        assert whitelist.description == "Test user email"
        assert whitelist.is_active is True
        assert whitelist.created_by == admin_user
        assert whitelist.created_at is not None
        assert whitelist.updated_at is not None

    def test_whitelisted_email_str_active(self) -> None:
        """Test whitelisted email string representation when active."""
        whitelist = WhitelistedEmail.objects.create(
            email_pattern="user@example.com",
            is_active=True,
        )
        assert str(whitelist) == "user@example.com (Active)"

    def test_whitelisted_email_str_inactive(self) -> None:
        """Test whitelisted email string representation when inactive."""
        whitelist = WhitelistedEmail.objects.create(
            email_pattern="user@example.com",
            is_active=False,
        )
        assert str(whitelist) == "user@example.com (Inactive)"

    def test_whitelisted_email_unique_constraint(self) -> None:
        """Test that email_pattern must be unique."""
        from django.db import IntegrityError

        WhitelistedEmail.objects.create(email_pattern="user@example.com")

        with pytest.raises(IntegrityError):
            WhitelistedEmail.objects.create(email_pattern="user@example.com")

    def test_is_email_whitelisted_exact_match(self) -> None:
        """Test exact email match in whitelist."""
        WhitelistedEmail.objects.create(
            email_pattern="user@example.com",
            is_active=True,
        )

        assert WhitelistedEmail.is_email_whitelisted("user@example.com") is True
        assert WhitelistedEmail.is_email_whitelisted("USER@EXAMPLE.COM") is True
        assert WhitelistedEmail.is_email_whitelisted("other@example.com") is False

    def test_is_email_whitelisted_domain_wildcard_asterisk(self) -> None:
        """Test domain wildcard matching with asterisk pattern."""
        WhitelistedEmail.objects.create(
            email_pattern="*@example.com",
            is_active=True,
        )

        assert WhitelistedEmail.is_email_whitelisted("user@example.com") is True
        assert WhitelistedEmail.is_email_whitelisted("admin@example.com") is True
        assert WhitelistedEmail.is_email_whitelisted("user@other.com") is False

    def test_is_email_whitelisted_domain_wildcard_at_symbol(self) -> None:
        """Test domain wildcard matching with @ pattern."""
        WhitelistedEmail.objects.create(
            email_pattern="@example.com",
            is_active=True,
        )

        assert WhitelistedEmail.is_email_whitelisted("user@example.com") is True
        assert WhitelistedEmail.is_email_whitelisted("admin@example.com") is True
        assert WhitelistedEmail.is_email_whitelisted("user@other.com") is False

    def test_is_email_whitelisted_inactive_entry(self) -> None:
        """Test that inactive whitelist entries are not matched."""
        WhitelistedEmail.objects.create(
            email_pattern="user@example.com",
            is_active=False,
        )

        assert WhitelistedEmail.is_email_whitelisted("user@example.com") is False

    def test_is_email_whitelisted_invalid_email(self) -> None:
        """Test whitelist check with invalid email format."""
        WhitelistedEmail.objects.create(
            email_pattern="*@example.com",
            is_active=True,
        )

        assert WhitelistedEmail.is_email_whitelisted("invalid-email") is False

    def test_is_email_whitelisted_case_insensitive(self) -> None:
        """Test that email matching is case insensitive."""
        WhitelistedEmail.objects.create(
            email_pattern="User@Example.COM",
            is_active=True,
        )

        assert WhitelistedEmail.is_email_whitelisted("user@example.com") is True
        assert WhitelistedEmail.is_email_whitelisted("USER@EXAMPLE.COM") is True

    def test_is_email_whitelisted_with_whitespace(self) -> None:
        """Test that email with whitespace is trimmed."""
        WhitelistedEmail.objects.create(
            email_pattern="user@example.com",
            is_active=True,
        )

        assert WhitelistedEmail.is_email_whitelisted("  user@example.com  ") is True

    def test_whitelisted_email_defaults(self) -> None:
        """Test whitelisted email default values."""
        whitelist = WhitelistedEmail.objects.create(
            email_pattern="test@example.com",
        )

        assert whitelist.description == ""
        assert whitelist.is_active is True
        assert whitelist.created_by is None
