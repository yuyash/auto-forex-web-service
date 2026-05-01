"""Rate limiter for authentication endpoints."""

from datetime import timedelta
from logging import Logger, getLogger

from django.conf import settings
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

    @classmethod
    def max_attempts(cls) -> int:
        """Return the configured number of failed attempts before IP lockout."""
        return int(getattr(settings, "MAX_LOGIN_ATTEMPTS", cls.MAX_ATTEMPTS))

    @classmethod
    def lockout_seconds(cls) -> int:
        """Return the configured IP lockout window in seconds."""
        return int(getattr(settings, "LOCKOUT_DURATION", cls.LOCKOUT_DURATION_MINUTES * 60))

    @classmethod
    def lockout_minutes(cls) -> int:
        """Return the configured lockout window rounded up to minutes."""
        seconds = cls.lockout_seconds()
        return max(1, (seconds + 59) // 60)

    @classmethod
    def account_lock_threshold(cls) -> int:
        """Return the configured account lock threshold."""
        return int(getattr(settings, "ACCOUNT_LOCK_THRESHOLD", cls.ACCOUNT_LOCK_THRESHOLD))

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
        timeout = RateLimiter.lockout_seconds()
        try:
            if cache.add(cache_key, 1, timeout):
                return 1

            attempts = int(cache.incr(cache_key))
            try:
                cache.touch(cache_key, timeout)
            except Exception:  # pylint: disable=broad-exception-caught
                logger.debug("RateLimiter cache.touch failed (ip=%s)", ip_address)
            return attempts
        except ValueError:
            # The key may have expired between add() and incr(). Start a new window.
            try:
                cache.set(cache_key, 1, timeout)
            except Exception:  # pylint: disable=broad-exception-caught
                logger.exception("RateLimiter cache.set failed (ip=%s)", ip_address)
            return 1
        except Exception:  # pylint: disable=broad-exception-caught
            logger.exception("RateLimiter cache.incr failed; allowing request (ip=%s)", ip_address)
            return RateLimiter.get_failed_attempts(ip_address)

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
        if attempts >= RateLimiter.max_attempts():
            return (
                True,
                f"Too many failed login attempts. "
                f"Try again in {RateLimiter.lockout_minutes()} minutes.",
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
        blocked_until = timezone.now() + timedelta(seconds=RateLimiter.lockout_seconds())
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
        if user.failed_login_attempts >= RateLimiter.account_lock_threshold():
            user.lock_account()
            return (
                True,
                "Account has been locked due to excessive failed login attempts. "
                "Please contact support.",
            )
        return False, None
