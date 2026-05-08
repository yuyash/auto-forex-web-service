"""Tests for OANDA retry policy behavior."""

from __future__ import annotations

from apps.market.services.oanda import OandaAPIError
from apps.trading.services.oanda_retry import OandaRetryPolicy, call_with_retry


def test_call_with_retry_stops_immediately_for_non_retryable_error() -> None:
    calls = 0

    def fail_auth() -> None:
        nonlocal calls
        calls += 1
        raise OandaAPIError("Failed to fetch pending orders: status 401")

    try:
        call_with_retry(
            fail_auth,
            policy=OandaRetryPolicy(max_attempts=50, backoff_base_seconds=0),
            label="Fetch pending orders",
            sleep=lambda _: None,
        )
    except RuntimeError as exc:
        assert "non-retryable OANDA error after 1 attempt" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("Expected RuntimeError")

    assert calls == 1


def test_call_with_retry_uses_attempt_count_for_retry_exhaustion() -> None:
    calls = 0
    sleeps: list[float] = []

    def fail_temporarily() -> None:
        nonlocal calls
        calls += 1
        raise OandaAPIError("Failed to fetch trades: status 503")

    try:
        call_with_retry(
            fail_temporarily,
            policy=OandaRetryPolicy(
                max_attempts=3,
                backoff_base_seconds=1,
                backoff_max_seconds=2,
                jitter_ratio=0,
            ),
            label="Fetch open trades",
            sleep=sleeps.append,
        )
    except RuntimeError as exc:
        assert "Fetch open trades failed after 3 attempts" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("Expected RuntimeError")

    assert calls == 3
    assert sleeps == [1, 2]
