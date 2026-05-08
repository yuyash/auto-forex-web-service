"""Retry policy for OANDA API calls.

OANDA broker APIs are public internet endpoints and occasionally return
transient errors (connection resets, 5xx, short windows of unavailability).
The strategy itself is resilient to those, but the reconciliation step that
loads positions/orders from the broker cannot proceed without a reply.

This module encapsulates a small, configurable retry policy used by the
reconciliation service.  Keeping the policy in one place means tasks can
override the defaults without duplicating sleep/backoff logic across every
call site.
"""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass
from logging import Logger, getLogger
from typing import Any, Callable, TypeVar

from apps.market.services.oanda import OandaAPIError

logger: Logger = getLogger(name=__name__)

_T = TypeVar("_T")


@dataclass(frozen=True, slots=True)
class OandaRetryPolicy:
    """Controls how OANDA API calls recover from transient failures."""

    max_attempts: int = 50
    backoff_base_seconds: float = 1.0
    backoff_max_seconds: float = 60.0
    jitter_ratio: float = 0.2

    @classmethod
    def default(cls) -> "OandaRetryPolicy":
        return cls()

    @classmethod
    def from_task(cls, task: Any) -> "OandaRetryPolicy":
        """Build a policy from a TradingTask (or any object exposing the same fields).

        Falls back to defaults when attributes are missing or invalid.
        """
        default = cls()
        max_attempts = cls._coerce_int(
            getattr(task, "api_retry_max_attempts", None),
            default.max_attempts,
            minimum=1,
        )
        base = cls._coerce_float(
            getattr(task, "api_retry_backoff_base_seconds", None),
            default.backoff_base_seconds,
            minimum=0.0,
        )
        cap = cls._coerce_float(
            getattr(task, "api_retry_backoff_max_seconds", None),
            default.backoff_max_seconds,
            minimum=max(base, 0.0),
        )
        return cls(
            max_attempts=max_attempts,
            backoff_base_seconds=base,
            backoff_max_seconds=cap,
            jitter_ratio=cls._coerce_float(
                getattr(task, "api_retry_jitter_ratio", None),
                default.jitter_ratio,
                minimum=0.0,
            ),
        )

    def delay_for_attempt(self, attempt: int) -> float:
        """Return the delay (in seconds) to wait before *attempt*.

        ``attempt`` is 1-indexed and represents the next retry (so the delay
        before the 2nd attempt uses attempt=1).  Uses exponential backoff
        capped at ``backoff_max_seconds``.
        """
        if attempt < 1:
            return 0.0
        exponent = attempt - 1
        # Avoid overflow for very large attempt counts by clamping the exponent
        # before multiplication.  Any value above ~2^40 already saturates the
        # cap in practice.
        if exponent > 40:
            return self.backoff_max_seconds
        delay = self.backoff_base_seconds * (2**exponent)
        if delay > self.backoff_max_seconds:
            return self.backoff_max_seconds
        return delay

    def apply_jitter(self, delay: float) -> float:
        if delay <= 0 or self.jitter_ratio <= 0:
            return delay
        jitter_max = int(delay * self.jitter_ratio * 10_000)
        if jitter_max <= 0:
            return delay
        jitter = secrets.randbelow(jitter_max + 1) / 10_000
        return min(self.backoff_max_seconds, delay + jitter)

    @staticmethod
    def _coerce_int(value: Any, default: int, *, minimum: int) -> int:
        try:
            result = int(value)  # handles Decimal, str, int
        except (TypeError, ValueError):
            return default
        return max(minimum, result)

    @staticmethod
    def _coerce_float(value: Any, default: float, *, minimum: float) -> float:
        try:
            result = float(value)
        except (TypeError, ValueError):
            return default
        if result < minimum:
            return minimum
        return result


def call_with_retry(
    fn: Callable[..., _T],
    *args: Any,
    policy: OandaRetryPolicy,
    label: str = "OANDA API call",
    sleep: Callable[[float], None] | None = None,
    **kwargs: Any,
) -> _T:
    """Call *fn* retrying OandaAPIError with the given ``policy``.

    Raises ``RuntimeError`` when the retry budget is exhausted, preserving
    the last underlying ``OandaAPIError`` as ``__cause__``.
    """
    last_exc: OandaAPIError | None = None
    max_attempts = max(1, policy.max_attempts)
    # Resolve the sleep function on every call so tests that monkey-patch
    # ``apps.trading.services.oanda_retry.time.sleep`` can intercept waits
    # without having to pass ``sleep=`` explicitly.
    sleep_fn = sleep if sleep is not None else time.sleep

    attempts_used = 0
    for attempt in range(1, max_attempts + 1):
        attempts_used = attempt
        try:
            return fn(*args, **kwargs)
        except OandaAPIError as exc:
            last_exc = exc
            if not is_retryable_oanda_error(exc):
                logger.error(
                    "%s failed with non-retryable OANDA error on attempt %d/%d: %s",
                    label,
                    attempt,
                    max_attempts,
                    exc,
                )
                raise RuntimeError(
                    f"{label} failed with non-retryable OANDA error "
                    f"after {attempt} attempt{'s' if attempt != 1 else ''}: {last_exc}"
                ) from last_exc
            if attempt < max_attempts:
                delay = policy.apply_jitter(policy.delay_for_attempt(attempt))
                logger.warning(
                    "%s failed (attempt %d/%d): %s — retrying in %.2fs",
                    label,
                    attempt,
                    max_attempts,
                    exc,
                    delay,
                )
                if delay > 0:
                    sleep_fn(delay)
            else:
                logger.error(
                    "%s failed after %d attempts: %s",
                    label,
                    max_attempts,
                    exc,
                )

    raise RuntimeError(f"{label} failed after {attempts_used} attempts: {last_exc}") from last_exc


def is_retryable_oanda_error(exc: OandaAPIError) -> bool:
    """Return True when the OANDA failure looks transient and safe to retry."""
    haystack = " ".join(
        part.strip().lower() for part in [str(exc), getattr(exc, "internal_detail", "")] if part
    )
    if not haystack:
        return False

    retryable_markers = (
        "status 429",
        "status 500",
        "status 502",
        "status 503",
        "status 504",
        "timed out",
        "timeout",
        "temporarily unavailable",
        "connection reset",
        "connection aborted",
        "connection refused",
        "connection error",
        "service unavailable",
        "broken pipe",
        "remote end closed connection",
        "eof occurred in violation of protocol",
        "temporary failure",
    )
    non_retryable_markers = (
        "status 400",
        "status 401",
        "status 403",
        "status 404",
        "status 405",
        "status 409",
        "status 422",
        "market order rejected",
        "account required",
        "api client not initialized",
        "insufficient authorization",
    )
    if any(marker in haystack for marker in non_retryable_markers):
        return False
    return any(marker in haystack for marker in retryable_markers)
