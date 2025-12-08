"""
Unit tests for rate limiter module.

Tests cover:
- Cache key generation
- Failed attempts tracking
- IP blocking logic
- Account locking logic
"""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.utils import timezone

import pytest

from apps.accounts.rate_limiter import RateLimiter


class TestRateLimiterCacheKey:
    """Test cases for cache key generation."""

    def test_get_cache_key_format(self) -> None:
        """Test cache key format is correct."""
        key = RateLimiter.get_cache_key("192.168.1.1")
        assert key == "login_attempts:192.168.1.1"

    def test_get_cache_key_ipv6(self) -> None:
        """Test cache key with IPv6 address."""
        key = RateLimiter.get_cache_key("::1")
        assert key == "login_attempts:::1"

    def test_get_cache_key_full_ipv6(self) -> None:
        """Test cache key with full IPv6 address."""
        key = RateLimiter.get_cache_key("2001:0db8:85a3:0000:0000:8a2e:0370:7334")
        assert "2001:0db8:85a3:0000:0000:8a2e:0370:7334" in key


class TestRateLimiterFailedAttempts:
    """Test cases for failed attempts tracking."""

    @patch("apps.accounts.rate_limiter.cache")
    def test_get_failed_attempts_no_cache(self, mock_cache: MagicMock) -> None:
        """Test get_failed_attempts returns 0 when no cache entry."""
        mock_cache.get.return_value = 0

        result = RateLimiter.get_failed_attempts("192.168.1.1")

        assert result == 0
        mock_cache.get.assert_called_once()

    @patch("apps.accounts.rate_limiter.cache")
    def test_get_failed_attempts_with_cache(self, mock_cache: MagicMock) -> None:
        """Test get_failed_attempts returns cached value."""
        mock_cache.get.return_value = 3

        result = RateLimiter.get_failed_attempts("192.168.1.1")

        assert result == 3

    @patch("apps.accounts.rate_limiter.cache")
    def test_increment_failed_attempts(self, mock_cache: MagicMock) -> None:
        """Test increment_failed_attempts increases count."""
        mock_cache.get.return_value = 2

        result = RateLimiter.increment_failed_attempts("192.168.1.1")

        assert result == 3
        mock_cache.set.assert_called_once()
        # Verify timeout is set correctly (LOCKOUT_DURATION_MINUTES * 60)
        call_args = mock_cache.set.call_args
        assert call_args[0][1] == 3  # New count
        assert call_args[0][2] == RateLimiter.LOCKOUT_DURATION_MINUTES * 60

    @patch("apps.accounts.rate_limiter.cache")
    def test_increment_failed_attempts_from_zero(self, mock_cache: MagicMock) -> None:
        """Test increment_failed_attempts from zero."""
        mock_cache.get.return_value = 0

        result = RateLimiter.increment_failed_attempts("192.168.1.1")

        assert result == 1

    @patch("apps.accounts.rate_limiter.cache")
    def test_reset_failed_attempts(self, mock_cache: MagicMock) -> None:
        """Test reset_failed_attempts deletes cache entry."""
        RateLimiter.reset_failed_attempts("192.168.1.1")

        mock_cache.delete.assert_called_once_with("login_attempts:192.168.1.1")


class TestRateLimiterIPBlocking:
    """Test cases for IP blocking logic."""

    @patch("apps.accounts.rate_limiter.cache")
    @patch("apps.accounts.rate_limiter.BlockedIP")
    def test_is_ip_blocked_by_attempts(
        self, mock_blocked_ip: MagicMock, mock_cache: MagicMock
    ) -> None:
        """Test IP is blocked after max attempts exceeded."""
        mock_cache.get.return_value = RateLimiter.MAX_ATTEMPTS

        is_blocked, message = RateLimiter.is_ip_blocked("192.168.1.1")

        assert is_blocked is True
        assert "Too many failed login attempts" in message
        assert str(RateLimiter.LOCKOUT_DURATION_MINUTES) in message

    @patch("apps.accounts.rate_limiter.cache")
    @pytest.mark.django_db
    def test_is_ip_not_blocked_under_max(self, mock_cache: MagicMock) -> None:
        """Test IP is not blocked when under max attempts."""
        mock_cache.get.return_value = RateLimiter.MAX_ATTEMPTS - 1

        is_blocked, message = RateLimiter.is_ip_blocked("192.168.1.1")

        assert is_blocked is False
        assert message is None

    @patch("apps.accounts.rate_limiter.cache")
    @patch("apps.accounts.rate_limiter.BlockedIP")
    def test_is_ip_blocked_by_database_entry(
        self, mock_blocked_ip: MagicMock, mock_cache: MagicMock
    ) -> None:
        """Test IP is blocked by database entry."""
        mock_cache.get.return_value = 0

        blocked_entry = MagicMock()
        blocked_entry.is_active.return_value = True
        blocked_entry.reason = "Manually blocked"
        mock_blocked_ip.objects.get.return_value = blocked_entry

        is_blocked, message = RateLimiter.is_ip_blocked("192.168.1.1")

        assert is_blocked is True
        assert message == "Manually blocked"

    @patch("apps.accounts.rate_limiter.cache")
    @patch("apps.accounts.rate_limiter.BlockedIP")
    def test_is_ip_not_blocked_when_db_entry_inactive(
        self, mock_blocked_ip: MagicMock, mock_cache: MagicMock
    ) -> None:
        """Test IP is not blocked when database entry is inactive."""
        mock_cache.get.return_value = 0

        blocked_entry = MagicMock()
        blocked_entry.is_active.return_value = False
        mock_blocked_ip.objects.get.return_value = blocked_entry

        is_blocked, message = RateLimiter.is_ip_blocked("192.168.1.1")

        assert is_blocked is False
        assert message is None


class TestRateLimiterBlockIPAddress:
    """Test cases for block_ip_address function."""

    @patch("apps.accounts.rate_limiter.timezone")
    @patch("apps.accounts.rate_limiter.cache")
    @patch("apps.accounts.rate_limiter.BlockedIP")
    def test_block_ip_creates_new_entry(
        self, mock_blocked_ip: MagicMock, mock_cache: MagicMock, mock_tz: MagicMock
    ) -> None:
        """Test block_ip_address creates new BlockedIP entry."""
        mock_tz.now.return_value = timezone.now()
        mock_cache.get.return_value = 5
        mock_blocked_ip.objects.get_or_create.return_value = (MagicMock(), True)

        RateLimiter.block_ip_address("192.168.1.1", "Test reason")

        mock_blocked_ip.objects.get_or_create.assert_called_once()
        call_kwargs = mock_blocked_ip.objects.get_or_create.call_args[1]
        assert call_kwargs["defaults"]["reason"] == "Test reason"
        assert call_kwargs["defaults"]["is_permanent"] is False

    @patch("apps.accounts.rate_limiter.timezone")
    @patch("apps.accounts.rate_limiter.cache")
    @patch("apps.accounts.rate_limiter.BlockedIP")
    def test_block_ip_updates_existing_entry(
        self, mock_blocked_ip: MagicMock, mock_cache: MagicMock, mock_tz: MagicMock
    ) -> None:
        """Test block_ip_address updates existing BlockedIP entry."""
        mock_tz.now.return_value = timezone.now()
        mock_cache.get.return_value = 5

        existing_entry = MagicMock()
        mock_blocked_ip.objects.get_or_create.return_value = (existing_entry, False)

        RateLimiter.block_ip_address("192.168.1.1", "Updated reason")

        assert existing_entry.reason == "Updated reason"
        existing_entry.save.assert_called_once()

    @patch("apps.accounts.rate_limiter.timezone")
    @patch("apps.accounts.rate_limiter.cache")
    @patch("apps.accounts.rate_limiter.BlockedIP")
    def test_block_ip_uses_default_reason(
        self, mock_blocked_ip: MagicMock, mock_cache: MagicMock, mock_tz: MagicMock
    ) -> None:
        """Test block_ip_address uses default reason."""
        mock_tz.now.return_value = timezone.now()
        mock_cache.get.return_value = 5
        mock_blocked_ip.objects.get_or_create.return_value = (MagicMock(), True)

        RateLimiter.block_ip_address("192.168.1.1")

        call_kwargs = mock_blocked_ip.objects.get_or_create.call_args[1]
        assert "failed login attempts" in call_kwargs["defaults"]["reason"].lower()


class TestRateLimiterAccountLock:
    """Test cases for account locking logic."""

    def test_check_account_lock_when_locked(self) -> None:
        """Test check_account_lock returns True when account is locked."""
        mock_user = MagicMock()
        mock_user.is_locked = True

        is_locked, message = RateLimiter.check_account_lock(mock_user)

        assert is_locked is True
        assert "locked" in message.lower()
        assert "contact support" in message.lower()

    def test_check_account_lock_exceeds_threshold(self) -> None:
        """Test check_account_lock locks account when threshold exceeded."""
        mock_user = MagicMock()
        mock_user.is_locked = False
        mock_user.failed_login_attempts = RateLimiter.ACCOUNT_LOCK_THRESHOLD

        is_locked, message = RateLimiter.check_account_lock(mock_user)

        assert is_locked is True
        mock_user.lock_account.assert_called_once()
        assert "locked" in message.lower()

    def test_check_account_lock_not_locked(self) -> None:
        """Test check_account_lock returns False when not locked."""
        mock_user = MagicMock()
        mock_user.is_locked = False
        mock_user.failed_login_attempts = RateLimiter.ACCOUNT_LOCK_THRESHOLD - 1

        is_locked, message = RateLimiter.check_account_lock(mock_user)

        assert is_locked is False
        assert message is None

    def test_check_account_lock_zero_attempts(self) -> None:
        """Test check_account_lock with zero failed attempts."""
        mock_user = MagicMock()
        mock_user.is_locked = False
        mock_user.failed_login_attempts = 0

        is_locked, message = RateLimiter.check_account_lock(mock_user)

        assert is_locked is False
        assert message is None


class TestRateLimiterConstants:
    """Test cases for RateLimiter constants."""

    def test_max_attempts_is_reasonable(self) -> None:
        """Test MAX_ATTEMPTS is a reasonable value."""
        assert RateLimiter.MAX_ATTEMPTS > 0
        assert RateLimiter.MAX_ATTEMPTS <= 20

    def test_lockout_duration_is_reasonable(self) -> None:
        """Test LOCKOUT_DURATION_MINUTES is a reasonable value."""
        assert RateLimiter.LOCKOUT_DURATION_MINUTES > 0
        assert RateLimiter.LOCKOUT_DURATION_MINUTES <= 60

    def test_account_lock_threshold_greater_than_max_attempts(self) -> None:
        """Test ACCOUNT_LOCK_THRESHOLD is greater than MAX_ATTEMPTS."""
        assert RateLimiter.ACCOUNT_LOCK_THRESHOLD >= RateLimiter.MAX_ATTEMPTS


@pytest.mark.django_db
class TestRateLimiterIntegration:
    """Integration tests for RateLimiter with real database."""

    def test_block_ip_creates_database_entry(self) -> None:
        """Test block_ip_address creates real database entry."""
        from apps.accounts.models import BlockedIP

        # Ensure no existing entry
        BlockedIP.objects.filter(ip_address="10.0.0.99").delete()

        RateLimiter.block_ip_address("10.0.0.99", "Integration test")

        blocked = BlockedIP.objects.get(ip_address="10.0.0.99")
        assert blocked.reason == "Integration test"
        assert blocked.is_permanent is False

    def test_is_ip_blocked_with_real_database(self) -> None:
        """Test is_ip_blocked checks real database."""
        from apps.accounts.models import BlockedIP

        # Create a blocked IP
        BlockedIP.objects.filter(ip_address="10.0.0.100").delete()
        BlockedIP.objects.create(
            ip_address="10.0.0.100",
            reason="Test block",
            blocked_until=timezone.now() + timedelta(hours=1),
            is_permanent=False,
        )

        is_blocked, message = RateLimiter.is_ip_blocked("10.0.0.100")

        assert is_blocked is True
        assert message == "Test block"

    def test_check_account_lock_with_real_user(self) -> None:
        """Test check_account_lock with real user."""
        from apps.accounts.models import User

        user = User.objects.create_user(
            username="locktest",
            email="locktest@example.com",
            password="testpass123",
        )

        # Set failed attempts to threshold
        user.failed_login_attempts = RateLimiter.ACCOUNT_LOCK_THRESHOLD
        user.save()

        is_locked, message = RateLimiter.check_account_lock(user)

        assert is_locked is True
        user.refresh_from_db()
        assert user.is_locked is True
