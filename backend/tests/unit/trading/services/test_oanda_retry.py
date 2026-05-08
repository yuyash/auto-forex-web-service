"""Tests for OANDA retry policy behavior."""

from __future__ import annotations

from apps.market.services.oanda import OandaAPIError
from apps.market.services.oanda_retry import (
    OandaRetryClassifier,
    OandaRetryPolicy,
    OandaRetryService,
)


def test_retry_service_stops_immediately_for_non_retryable_error() -> None:
    calls = 0

    def fail_bad_request() -> None:
        nonlocal calls
        calls += 1
        raise OandaAPIError("Failed to fetch pending orders: status 400")

    try:
        OandaRetryService(policy=OandaRetryPolicy(max_attempts=50, backoff_base_seconds=0)).call(
            fail_bad_request,
            label="Fetch pending orders",
        )
    except RuntimeError as exc:
        assert "non-retryable OANDA error after 1 attempt" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("Expected RuntimeError")

    assert calls == 1


def test_retry_service_retries_bare_unauthorized_status() -> None:
    calls = 0
    sleeps: list[float] = []

    def fail_then_succeed() -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise OandaAPIError("Failed to fetch pending orders: status 401")
        return "orders"

    result = OandaRetryService(
        policy=OandaRetryPolicy(
            max_attempts=50,
            backoff_base_seconds=1,
            backoff_max_seconds=2,
            jitter_ratio=0,
        ),
        sleep=sleeps.append,
    ).call(
        fail_then_succeed,
        label="Fetch pending orders",
    )

    assert result == "orders"
    assert calls == 3
    assert sleeps == [1, 2]


def test_retry_classifier_rejects_explicit_authorization_failure() -> None:
    classifier = OandaRetryClassifier()
    error = OandaAPIError(
        "Failed to fetch pending orders: status 401",
        internal_detail="Insufficient authorization to perform request.",
    )

    assert classifier.is_retryable(error) is False


def test_retry_service_uses_attempt_count_for_retry_exhaustion() -> None:
    calls = 0
    sleeps: list[float] = []

    def fail_temporarily() -> None:
        nonlocal calls
        calls += 1
        raise OandaAPIError("Failed to fetch trades: status 503")

    try:
        OandaRetryService(
            policy=OandaRetryPolicy(
                max_attempts=3,
                backoff_base_seconds=1,
                backoff_max_seconds=2,
                jitter_ratio=0,
            ),
            sleep=sleeps.append,
        ).call(
            fail_temporarily,
            label="Fetch open trades",
        )
    except RuntimeError as exc:
        assert "Fetch open trades failed after 3 attempts" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("Expected RuntimeError")

    assert calls == 3
    assert sleeps == [1, 2]
