"""Unit tests for accounts models."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.utils import timezone

from apps.accounts.models import (
    AccountSecurityEvent,
    BlockedIP,
    UserSession,
    UserSettings,
    WhitelistedEmail,
)

User = get_user_model()


@pytest.mark.django_db
class TestUserModel:
    """Test User model."""

    def test_create_user_with_valid_data(self):
        """Test creating a user with valid data."""
        user = User.objects.create_user(  # type: ignore[attr-defined]
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.check_password("testpass123")
        assert user.is_active
        assert not user.is_staff
        assert not user.is_superuser

    def test_create_superuser(self):
        """Test creating a superuser."""
        user = User.objects.create_superuser(  # type: ignore[attr-defined]
            username="admin",
            email="admin@example.com",
            password="adminpass123",
        )
        assert user.is_staff
        assert user.is_superuser
        assert user.is_active

    def test_username_unique_constraint(self):
        """Test username must be unique."""
        User.objects.create_user(  # type: ignore[attr-defined]
            username="testuser",
            email="test1@example.com",
            password="testpass123",
        )
        with pytest.raises(IntegrityError):
            User.objects.create_user(  # type: ignore[attr-defined]
                username="testuser",
                email="test2@example.com",
                password="testpass123",
            )

    def test_email_unique_constraint(self):
        """Test email must be unique."""
        User.objects.create_user(  # type: ignore[attr-defined]
            username="testuser1",
            email="test@example.com",
            password="testpass123",
        )
        with pytest.raises(IntegrityError):
            User.objects.create_user(  # type: ignore[attr-defined]
                username="testuser2",
                email="test@example.com",
                password="testpass123",
            )


@pytest.mark.django_db
class TestUserSettingsModel:
    """Test UserSettings model."""

    def test_create_user_settings_on_user_creation(self):
        """Test UserSettings is created automatically when user is created."""
        user = User.objects.create_user(  # type: ignore[attr-defined]
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        assert hasattr(user, "settings")
        assert isinstance(user.settings, UserSettings)

    def test_default_notification_settings(self):
        """Test default notification settings."""
        user = User.objects.create_user(  # type: ignore[attr-defined]
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        settings = user.settings
        assert settings.notification_enabled is True
        assert settings.notification_email is True
        assert settings.notification_browser is True


@pytest.mark.django_db
class TestUserSessionModel:
    """Test UserSession model."""

    def test_create_user_session(self):
        """Test creating a user session."""
        user = User.objects.create_user(  # type: ignore[attr-defined]
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        session = UserSession.objects.create(
            user=user,
            session_key="test_session_key",
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
        )
        assert session.user == user
        assert session.session_key == "test_session_key"
        assert session.ip_address == "192.168.1.1"
        assert session.is_active

    def test_session_expiry(self):
        """Test session expiry logic."""
        user = User.objects.create_user(  # type: ignore[attr-defined]
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        session = UserSession.objects.create(
            user=user,
            session_key="test_session_key",
            ip_address="192.168.1.1",
        )
        # Session should not be expired immediately
        assert session.last_activity is not None


@pytest.mark.django_db
class TestBlockedIPModel:
    """Test BlockedIP model."""

    def test_create_blocked_ip(self):
        """Test creating a blocked IP."""
        blocked_until = timezone.now() + timedelta(hours=24)
        blocked_ip = BlockedIP.objects.create(
            ip_address="192.168.1.100",
            reason="Suspicious activity",
            blocked_until=blocked_until,
        )
        assert blocked_ip.ip_address == "192.168.1.100"
        assert blocked_ip.reason == "Suspicious activity"
        assert blocked_ip.is_active()

    def test_blocked_ip_unique_constraint(self):
        """Test IP address must be unique."""
        blocked_until = timezone.now() + timedelta(hours=24)
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


@pytest.mark.django_db
class TestWhitelistedEmailModel:
    """Test WhitelistedEmail model."""

    def test_create_whitelisted_email(self):
        """Test creating a whitelisted email."""
        email = WhitelistedEmail.objects.create(
            email_pattern="test@example.com",
            description="Test email",
        )
        assert email.email_pattern == "test@example.com"
        assert email.description == "Test email"
        assert email.is_active

    def test_whitelisted_email_unique_constraint(self):
        """Test email pattern must be unique."""
        WhitelistedEmail.objects.create(
            email_pattern="test@example.com",
        )
        with pytest.raises(IntegrityError):
            WhitelistedEmail.objects.create(
                email_pattern="test@example.com",
            )


@pytest.mark.django_db
class TestAccountSecurityEventModel:
    """Test AccountSecurityEvent model."""

    def test_create_security_event(self):
        """Test creating a security event."""
        user = User.objects.create_user(  # type: ignore[attr-defined]
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        event = AccountSecurityEvent.objects.create(
            user=user,
            event_type="login_success",
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
        )
        assert event.user == user
        assert event.event_type == "login_success"
        assert event.ip_address == "192.168.1.1"

    def test_security_event_cascade_delete(self):
        """Test security events are deleted when user is deleted."""
        user = User.objects.create_user(  # type: ignore[attr-defined]
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        AccountSecurityEvent.objects.create(
            user=user,
            event_type="login_success",
            ip_address="192.168.1.1",
        )
        user_id = user.id
        user.delete()
        assert not AccountSecurityEvent.objects.filter(user_id=user_id).exists()
