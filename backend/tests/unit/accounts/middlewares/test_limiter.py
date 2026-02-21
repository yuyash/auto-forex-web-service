"""Unit tests for RateLimiter (logic only, mocked cache)."""

from unittest.mock import MagicMock, patch

from apps.accounts.middlewares.limiter import RateLimiter
from apps.accounts.models import BlockedIP


class TestRateLimiterMethods:
    """Unit tests for RateLimiter static methods."""

    def test_get_cache_key(self) -> None:
        """Test cache key generation."""
        key = RateLimiter.get_cache_key("192.168.1.1")
        assert key == "login_attempts:192.168.1.1"

    def test_get_failed_attempts_with_cache(self) -> None:
        """Test getting failed attempts from cache."""
        with patch("apps.accounts.middlewares.limiter.cache") as mock_cache:
            mock_cache.get.return_value = 3

            attempts = RateLimiter.get_failed_attempts("192.168.1.1")

        assert attempts == 3

    def test_get_failed_attempts_cache_failure(self) -> None:
        """Test getting failed attempts when cache fails."""
        with patch("apps.accounts.middlewares.limiter.cache") as mock_cache:
            mock_cache.get.side_effect = Exception("Cache error")

            attempts = RateLimiter.get_failed_attempts("192.168.1.1")

        # Should fail open and return 0
        assert attempts == 0

    def test_increment_failed_attempts(self) -> None:
        """Test incrementing failed attempts."""
        with patch("apps.accounts.middlewares.limiter.cache") as mock_cache:
            mock_cache.get.return_value = 2

            attempts = RateLimiter.increment_failed_attempts("192.168.1.1")

        assert attempts == 3
        mock_cache.set.assert_called_once()

    def test_reset_failed_attempts(self) -> None:
        """Test resetting failed attempts."""
        with patch("apps.accounts.middlewares.limiter.cache") as mock_cache:
            RateLimiter.reset_failed_attempts("192.168.1.1")

        mock_cache.delete.assert_called_once()

    def test_is_ip_blocked_by_attempts(self) -> None:
        """Test IP blocked by failed attempts."""
        with patch("apps.accounts.middlewares.limiter.cache") as mock_cache:
            mock_cache.get.return_value = RateLimiter.MAX_ATTEMPTS

            is_blocked, reason = RateLimiter.is_ip_blocked("192.168.1.1")

        assert is_blocked is True
        assert reason is not None

    def test_is_ip_blocked_not_blocked(self) -> None:
        """Test IP not blocked."""
        with patch("apps.accounts.middlewares.limiter.cache") as mock_cache:
            mock_cache.get.return_value = 2

            with patch("apps.accounts.middlewares.limiter.BlockedIP.objects.get") as mock_get:
                mock_get.side_effect = BlockedIP.DoesNotExist()

                is_blocked, reason = RateLimiter.is_ip_blocked("192.168.1.1")

        assert is_blocked is False
        assert reason is None

    def test_check_account_lock_not_locked(self) -> None:
        """Test checking account lock when not locked."""
        mock_user = MagicMock()
        mock_user.is_locked = False
        mock_user.failed_login_attempts = 5

        is_locked, reason = RateLimiter.check_account_lock(mock_user)

        assert is_locked is False
        assert reason is None

    def test_check_account_lock_already_locked(self) -> None:
        """Test checking account lock when already locked."""
        mock_user = MagicMock()
        mock_user.is_locked = True

        is_locked, reason = RateLimiter.check_account_lock(mock_user)

        assert is_locked is True
        assert reason is not None

    def test_check_account_lock_threshold_reached(self) -> None:
        """Test checking account lock when threshold is reached."""
        mock_user = MagicMock()
        mock_user.is_locked = False
        mock_user.failed_login_attempts = RateLimiter.ACCOUNT_LOCK_THRESHOLD

        is_locked, reason = RateLimiter.check_account_lock(mock_user)

        assert is_locked is True
        mock_user.lock_account.assert_called_once()
