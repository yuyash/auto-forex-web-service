"""Unit tests for User, WhitelistedEmail, and UserNotification models."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import User, UserNotification, WhitelistedEmail


@pytest.mark.django_db
class TestWhitelistedEmail:
    """Tests for WhitelistedEmail model."""

    def test_create_whitelisted_email(self) -> None:
        """Test creating a whitelisted email."""
        email = WhitelistedEmail.objects.create(
            email_pattern="test@example.com",
            description="Test email",
            is_active=True,
        )
        assert email.email_pattern == "test@example.com"
        assert email.is_active is True

    def test_is_email_whitelisted_exact_match(self) -> None:
        """Test exact email match."""
        WhitelistedEmail.objects.create(
            email_pattern="test@example.com",
            is_active=True,
        )
        assert WhitelistedEmail.is_email_whitelisted("test@example.com") is True
        assert WhitelistedEmail.is_email_whitelisted("other@example.com") is False

    def test_is_email_whitelisted_domain_wildcard(self) -> None:
        """Test domain wildcard matching."""
        WhitelistedEmail.objects.create(
            email_pattern="*@example.com",
            is_active=True,
        )
        assert WhitelistedEmail.is_email_whitelisted("any@example.com") is True
        assert WhitelistedEmail.is_email_whitelisted("test@example.com") is True
        assert WhitelistedEmail.is_email_whitelisted("user@other.com") is False

    def test_is_email_whitelisted_inactive(self) -> None:
        """Test inactive whitelist entries are ignored."""
        WhitelistedEmail.objects.create(
            email_pattern="test@example.com",
            is_active=False,
        )
        assert WhitelistedEmail.is_email_whitelisted("test@example.com") is False


@pytest.mark.django_db
class TestUser:
    """Tests for User model."""

    def test_create_user(self) -> None:
        """Test creating a user."""
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
        )
        assert user.email == "test@example.com"
        assert user.username == "testuser"
        assert user.check_password("testpass123")

    def test_increment_failed_login(self) -> None:
        """Test incrementing failed login attempts."""
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
        )
        assert user.failed_login_attempts == 0

        user.increment_failed_login()
        assert user.failed_login_attempts == 1
        assert user.last_login_attempt is not None

    def test_reset_failed_login(self) -> None:
        """Test resetting failed login attempts."""
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
        )
        user.failed_login_attempts = 5
        user.save()

        user.reset_failed_login()
        assert user.failed_login_attempts == 0
        assert user.last_login_attempt is None

    def test_lock_account(self) -> None:
        """Test locking user account."""
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
        )
        assert user.is_locked is False

        user.lock_account()
        assert user.is_locked is True

    def test_unlock_account(self) -> None:
        """Test unlocking user account."""
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
        )
        user.is_locked = True
        user.failed_login_attempts = 5
        user.save()

        user.unlock_account()
        assert user.is_locked is False
        assert user.failed_login_attempts == 0

    def test_generate_verification_token(self) -> None:
        """Test generating email verification token."""
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
        )
        token = user.generate_verification_token()
        assert token
        assert user.email_verification_token == token
        assert user.email_verification_sent_at is not None

    def test_verify_email_success(self) -> None:
        """Test successful email verification."""
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
        )
        token = user.generate_verification_token()

        result = user.verify_email(token)
        assert result is True
        assert user.email_verified is True
        assert user.email_verification_token == ""

    def test_verify_email_invalid_token(self) -> None:
        """Test email verification with invalid token."""
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
        )
        user.generate_verification_token()

        result = user.verify_email("invalid_token")
        assert result is False
        assert user.email_verified is False

    def test_verify_email_expired_token(self) -> None:
        """Test email verification with expired token."""
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
        )
        token = user.generate_verification_token()

        # Set sent_at to 25 hours ago (expired)
        user.email_verification_sent_at = timezone.now() - timedelta(hours=25)
        user.save()

        result = user.verify_email(token)
        assert result is False
        assert user.email_verified is False


@pytest.mark.django_db
class TestUserNotification:
    """Tests for UserNotification model."""

    def test_create_notification(self) -> None:
        """Test creating a user notification."""
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
        )
        notification = UserNotification.objects.create(
            user=user,
            notification_type="test",
            title="Test Notification",
            message="Test message",
            severity="info",
        )
        assert notification.user == user
        assert notification.is_read is False

    def test_mark_as_read(self) -> None:
        """Test marking notification as read."""
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
        )
        notification = UserNotification.objects.create(
            user=user,
            notification_type="test",
            title="Test",
            message="Test",
            severity="info",
        )
        assert notification.is_read is False

        notification.mark_as_read()
        assert notification.is_read is True

    def test_mark_as_unread(self) -> None:
        """Test marking notification as unread."""
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
        )
        notification = UserNotification.objects.create(
            user=user,
            notification_type="test",
            title="Test",
            message="Test",
            severity="info",
            is_read=True,
        )
        assert notification.is_read is True

        notification.mark_as_unread()
        assert notification.is_read is False
