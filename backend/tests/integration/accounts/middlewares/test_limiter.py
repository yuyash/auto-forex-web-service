"""Unit tests for RateLimiter."""

from datetime import datetime, timedelta

import pytest
from django.core.cache import cache

from apps.accounts.middlewares import RateLimiter
from apps.accounts.models import BlockedIP, User


@pytest.mark.django_db
class TestRateLimiter:
    """Tests for RateLimiter class."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        cache.clear()

    def test_get_failed_attempts_no_attempts(self) -> None:
        """Test getting failed attempts when none exist."""
        attempts = RateLimiter.get_failed_attempts("192.168.1.1")
        assert attempts == 0

    def test_increment_failed_attempts(self) -> None:
        """Test incrementing failed attempts."""
        ip = "192.168.1.1"
        attempts = RateLimiter.increment_failed_attempts(ip)
        assert attempts == 1

        attempts = RateLimiter.increment_failed_attempts(ip)
        assert attempts == 2

    def test_reset_failed_attempts(self) -> None:
        """Test resetting failed attempts."""
        ip = "192.168.1.1"
        RateLimiter.increment_failed_attempts(ip)
        RateLimiter.increment_failed_attempts(ip)

        RateLimiter.reset_failed_attempts(ip)
        attempts = RateLimiter.get_failed_attempts(ip)
        assert attempts == 0

    def test_is_ip_blocked_not_blocked(self) -> None:
        """Test checking if IP is blocked when it's not."""
        is_blocked, reason = RateLimiter.is_ip_blocked("192.168.1.1")
        assert is_blocked is False
        assert reason is None

    def test_is_ip_blocked_by_attempts(self) -> None:
        """Test checking if IP is blocked by failed attempts."""
        ip = "192.168.1.1"
        for _ in range(RateLimiter.MAX_ATTEMPTS):
            RateLimiter.increment_failed_attempts(ip)

        is_blocked, reason = RateLimiter.is_ip_blocked(ip)
        assert is_blocked is True
        assert reason is not None

    def test_is_ip_blocked_by_database(self) -> None:
        """Test checking if IP is blocked in database."""
        ip = "192.168.1.1"
        blocked_until = datetime.now() + timedelta(hours=1)
        BlockedIP.objects.create(
            ip_address=ip,
            reason="Test block",
            blocked_until=blocked_until,
        )

        is_blocked, reason = RateLimiter.is_ip_blocked(ip)
        assert is_blocked is True
        assert reason == "Test block"

    def test_block_ip_address(self) -> None:
        """Test blocking an IP address."""
        ip = "192.168.1.1"
        RateLimiter.block_ip_address(ip)

        blocked_ip = BlockedIP.objects.get(ip_address=ip)
        assert blocked_ip.ip_address == ip
        assert blocked_ip.is_permanent is False

    def test_check_account_lock_not_locked(self) -> None:
        """Test checking account lock when not locked."""
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
        )
        is_locked, reason = RateLimiter.check_account_lock(user)
        assert is_locked is False
        assert reason is None

    def test_check_account_lock_already_locked(self) -> None:
        """Test checking account lock when already locked."""
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
        )
        user.is_locked = True
        user.save()

        is_locked, reason = RateLimiter.check_account_lock(user)
        assert is_locked is True
        assert reason is not None

    def test_check_account_lock_threshold_reached(self) -> None:
        """Test checking account lock when threshold is reached."""
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
        )
        user.failed_login_attempts = RateLimiter.ACCOUNT_LOCK_THRESHOLD
        user.save()

        is_locked, reason = RateLimiter.check_account_lock(user)
        assert is_locked is True
        user.refresh_from_db()
        assert user.is_locked is True
