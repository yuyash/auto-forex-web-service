"""Unit tests for security-related models."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import AccountSecurityEvent, BlockedIP, User, UserSession


@pytest.mark.django_db
class TestUserSession:
    """Tests for UserSession model."""

    def test_create_session(self) -> None:
        """Test creating a user session."""
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
        )
        session = UserSession.objects.create(
            user=user,
            session_key="test_session_key",
            ip_address="127.0.0.1",
            user_agent="Test Agent",
        )
        assert session.user == user
        assert session.is_active is True

    def test_terminate_session(self) -> None:
        """Test terminating a session."""
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
        )
        session = UserSession.objects.create(
            user=user,
            session_key="test_session_key",
            ip_address="127.0.0.1",
        )
        assert session.is_active is True

        session.terminate()
        assert session.is_active is False
        assert session.logout_time is not None

    def test_is_expired_active_session(self) -> None:
        """Test checking if active session is expired."""
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
        )
        session = UserSession.objects.create(
            user=user,
            session_key="test_session_key",
            ip_address="127.0.0.1",
        )
        assert session.is_expired() is False

    def test_is_expired_old_session(self) -> None:
        """Test checking if old session is expired."""
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
        )
        session = UserSession.objects.create(
            user=user,
            session_key="test_session_key",
            ip_address="127.0.0.1",
        )
        # Set login time to 25 hours ago
        session.login_time = timezone.now() - timedelta(hours=25)
        session.save()

        assert session.is_expired() is True


@pytest.mark.django_db
class TestBlockedIP:
    """Tests for BlockedIP model."""

    def test_create_blocked_ip(self) -> None:
        """Test creating a blocked IP."""
        blocked_until = timezone.now() + timedelta(hours=1)
        blocked_ip = BlockedIP.objects.create(
            ip_address="192.168.1.1",
            reason="Test block",
            failed_attempts=5,
            blocked_until=blocked_until,
        )
        assert blocked_ip.ip_address == "192.168.1.1"
        assert blocked_ip.is_permanent is False

    def test_is_active_temporary_block(self) -> None:
        """Test checking if temporary block is active."""
        blocked_until = timezone.now() + timedelta(hours=1)
        blocked_ip = BlockedIP.objects.create(
            ip_address="192.168.1.1",
            reason="Test block",
            blocked_until=blocked_until,
        )
        assert blocked_ip.is_active() is True

    def test_is_active_expired_block(self) -> None:
        """Test checking if expired block is active."""
        blocked_until = timezone.now() - timedelta(hours=1)
        blocked_ip = BlockedIP.objects.create(
            ip_address="192.168.1.1",
            reason="Test block",
            blocked_until=blocked_until,
        )
        assert blocked_ip.is_active() is False

    def test_is_active_permanent_block(self) -> None:
        """Test checking if permanent block is active."""
        blocked_until = timezone.now() - timedelta(hours=1)
        blocked_ip = BlockedIP.objects.create(
            ip_address="192.168.1.1",
            reason="Test block",
            blocked_until=blocked_until,
            is_permanent=True,
        )
        assert blocked_ip.is_active() is True

    def test_unblock(self) -> None:
        """Test unblocking an IP."""
        blocked_until = timezone.now() + timedelta(hours=1)
        blocked_ip = BlockedIP.objects.create(
            ip_address="192.168.1.1",
            reason="Test block",
            blocked_until=blocked_until,
        )
        assert blocked_ip.is_active() is True

        blocked_ip.unblock()
        assert blocked_ip.is_active() is False


@pytest.mark.django_db
class TestAccountSecurityEvent:
    """Tests for AccountSecurityEvent model."""

    def test_create_security_event(self) -> None:
        """Test creating a security event."""
        event = AccountSecurityEvent.objects.create(
            event_type="login_success",
            description="User logged in",
            severity="info",
        )
        assert event.event_type == "login_success"
        assert event.category == "security"

    def test_create_security_event_with_user(self) -> None:
        """Test creating a security event with user."""
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
        )
        event = AccountSecurityEvent.objects.create(
            event_type="login_success",
            description="User logged in",
            severity="info",
            user=user,
            ip_address="127.0.0.1",
        )
        assert event.user == user
        assert event.ip_address == "127.0.0.1"
