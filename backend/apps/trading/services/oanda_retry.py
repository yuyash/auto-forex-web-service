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

    for attempt in range(1, max_attempts + 1):
        try:
            return fn(*args, **kwargs)
        except OandaAPIError as exc:
            last_exc = exc
            if attempt < max_attempts:
                delay = policy.delay_for_attempt(attempt)
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

    raise RuntimeError(f"{label} failed after {max_attempts} retries: {last_exc}") from last_exc
