"""Rate limiter for authentication endpoints."""

from datetime import timedelta
from logging import Logger, getLogger

from django.core.cache import cache
from django.db import DatabaseError
from django.utils import timezone

from apps.accounts.models import BlockedIP, User

logger: Logger = getLogger(name=__name__)


class RateLimiter:
    """Rate limiter for authentication endpoints."""

    MAX_ATTEMPTS = 5
    LOCKOUT_DURATION_MINUTES = 15
    ACCOUNT_LOCK_THRESHOLD = 10

    @staticmethod
    def get_cache_key(ip_address: str) -> str:
        """Get cache key for IP address."""
        return f"login_attempts:{ip_address}"

    @staticmethod
    def get_failed_attempts(ip_address: str) -> int:
        """Get number of failed attempts for IP address."""
        cache_key = RateLimiter.get_cache_key(ip_address)
        try:
            attempts = cache.get(cache_key, 0)
            return int(attempts)
        except Exception:  # pylint: disable=broad-exception-caught
            logger.exception("RateLimiter cache.get failed; allowing request (ip=%s)", ip_address)
            return 0

    @staticmethod
    def increment_failed_attempts(ip_address: str) -> int:
        """Increment failed attempts counter for IP address."""
        cache_key = RateLimiter.get_cache_key(ip_address)
        attempts = RateLimiter.get_failed_attempts(ip_address)
        attempts += 1
        timeout = RateLimiter.LOCKOUT_DURATION_MINUTES * 60
        try:
            cache.set(cache_key, attempts, timeout)
        except Exception:  # pylint: disable=broad-exception-caught
            logger.exception("RateLimiter cache.set failed (ip=%s)", ip_address)
        return attempts

    @staticmethod
    def reset_failed_attempts(ip_address: str) -> None:
        """Reset failed attempts counter for IP address."""
        cache_key = RateLimiter.get_cache_key(ip_address)
        try:
            cache.delete(cache_key)
        except Exception:  # pylint: disable=broad-exception-caught
            logger.exception("RateLimiter cache.delete failed (ip=%s)", ip_address)

    @staticmethod
    def is_ip_blocked(ip_address: str) -> tuple[bool, str | None]:
        """Check if IP address is blocked."""
        attempts = RateLimiter.get_failed_attempts(ip_address)
        if attempts >= RateLimiter.MAX_ATTEMPTS:
            return (
                True,
                f"Too many failed login attempts. "
                f"Try again in {RateLimiter.LOCKOUT_DURATION_MINUTES} minutes.",
            )
        try:
            blocked_ip = BlockedIP.objects.get(ip_address=ip_address)
            if blocked_ip.is_active():
                return True, blocked_ip.reason
        except BlockedIP.DoesNotExist:
            pass
        except DatabaseError:
            logger.exception("BlockedIP lookup failed; allowing request (ip=%s)", ip_address)
        return False, None

    @staticmethod
    def block_ip_address(ip_address: str, reason: str = "Excessive failed login attempts") -> None:
        """Block IP address."""
        blocked_until = timezone.now() + timedelta(hours=1)
        blocked_ip, created = BlockedIP.objects.get_or_create(
            ip_address=ip_address,
            defaults={
                "reason": reason,
                "failed_attempts": RateLimiter.get_failed_attempts(ip_address),
                "blocked_until": blocked_until,
                "is_permanent": False,
            },
        )
        if not created:
            blocked_ip.failed_attempts = RateLimiter.get_failed_attempts(ip_address)
            blocked_ip.blocked_until = blocked_until
            blocked_ip.reason = reason
            blocked_ip.save()

    @staticmethod
    def check_account_lock(user: User) -> tuple[bool, str | None]:
        """Check if user account should be locked."""
        if user.is_locked:
            return (
                True,
                "Account is locked due to excessive failed login attempts. Please contact support.",
            )
        if user.failed_login_attempts >= RateLimiter.ACCOUNT_LOCK_THRESHOLD:
            user.lock_account()
            return (
                True,
                "Account has been locked due to excessive failed login attempts. "
                "Please contact support.",
            )
        return False, None
