"""
Rate limiting utilities for authentication endpoints.
"""

from datetime import timedelta
from typing import TYPE_CHECKING, Optional, Tuple

from django.core.cache import cache
from django.utils import timezone

from .models import BlockedIP

if TYPE_CHECKING:
    from .models import User as UserType
else:
    from django.contrib.auth import get_user_model

    UserType = get_user_model()  # type: ignore[misc]


class RateLimiter:
    """
    Rate limiter for authentication endpoints.
    """

    MAX_ATTEMPTS = 5
    LOCKOUT_DURATION_MINUTES = 15
    ACCOUNT_LOCK_THRESHOLD = 10

    @staticmethod
    def get_cache_key(ip_address: str) -> str:
        return f"login_attempts:{ip_address}"

    @staticmethod
    def get_failed_attempts(ip_address: str) -> int:
        cache_key = RateLimiter.get_cache_key(ip_address)
        attempts = cache.get(cache_key, 0)
        return int(attempts)

    @staticmethod
    def increment_failed_attempts(ip_address: str) -> int:
        cache_key = RateLimiter.get_cache_key(ip_address)
        attempts = RateLimiter.get_failed_attempts(ip_address)
        attempts += 1
        timeout = RateLimiter.LOCKOUT_DURATION_MINUTES * 60
        cache.set(cache_key, attempts, timeout)
        return attempts

    @staticmethod
    def reset_failed_attempts(ip_address: str) -> None:
        cache_key = RateLimiter.get_cache_key(ip_address)
        cache.delete(cache_key)

    @staticmethod
    def is_ip_blocked(ip_address: str) -> Tuple[bool, Optional[str]]:
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
        return False, None

    @staticmethod
    def block_ip_address(ip_address: str, reason: str = "Excessive failed login attempts") -> None:
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
    def check_account_lock(user: "UserType") -> Tuple[bool, Optional[str]]:
        if user.is_locked:
            return (
                True,
                "Account is locked due to excessive failed login attempts. "
                "Please contact support.",
            )
        if user.failed_login_attempts >= RateLimiter.ACCOUNT_LOCK_THRESHOLD:
            user.lock_account()
            return (
                True,
                "Account has been locked due to excessive failed login attempts. "
                "Please contact support.",
            )
        return False, None
