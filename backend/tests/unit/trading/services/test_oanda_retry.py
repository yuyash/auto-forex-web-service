"""Tests for OANDA retry policy behavior."""

from __future__ import annotations

from uuid import uuid4

import pytest

from apps.market.services.oanda import OandaAPIError
from apps.market.services.oanda_retry import (
    OandaRetryClassifier,
    OandaRetryMetricRecorder,
    OandaRetryPolicy,
    OandaRetryService,
    OandaRetryTelemetry,
)


class InMemoryCache:
    """Minimal cache backend for retry metric tests."""

    def __init__(self) -> None:
        self.values: dict[str, int] = {}

    def add(self, key: str, value: int, timeout: int | None = None) -> bool:
        _ = timeout
        if key in self.values:
            return False
        self.values[key] = value
        return True

    def incr(self, key: str) -> int:
        self.values[key] = self.values.get(key, 0) + 1
        return self.values[key]

    def get(self, key: str, default: int = 0) -> int:
        return self.values.get(key, default)

    def set(self, key: str, value: int, timeout: int | None = None) -> None:
        _ = timeout
        self.values[key] = value

    def delete(self, key: str) -> None:
        self.values.pop(key, None)


class OandaRetryCallable:
    """Callable test double for retry scenarios."""

    def __init__(
        self,
        *,
        error_message: str,
        internal_detail: str = "",
        succeed_on_call: int | None = None,
    ) -> None:
        self.error_message = error_message
        self.internal_detail = internal_detail
        self.succeed_on_call = succeed_on_call
        self.calls = 0

    def __call__(self) -> str:
        self.calls += 1
        if self.succeed_on_call is not None and self.calls >= self.succeed_on_call:
            return "orders"
        raise OandaAPIError(self.error_message, internal_detail=self.internal_detail)


@pytest.mark.django_db
class TestOandaRetryService:
    """Verify OANDA retry policy behavior."""

    def test_stops_immediately_for_non_retryable_error(self) -> None:
        scenario = OandaRetryCallable(error_message="Failed to fetch pending orders: status 400")

        try:
            OandaRetryService(
                policy=OandaRetryPolicy(max_attempts=50, backoff_base_seconds=0)
            ).call(
                scenario,
                label="Fetch pending orders",
            )
        except RuntimeError as exc:
            assert "non-retryable OANDA error after 1 attempt" in str(exc)
        else:  # pragma: no cover - defensive assertion
            raise AssertionError("Expected RuntimeError")

        assert scenario.calls == 1

    def test_retries_bare_unauthorized_status(self) -> None:
        scenario = OandaRetryCallable(
            error_message="Failed to fetch pending orders: status 401",
            succeed_on_call=3,
        )
        sleeps: list[float] = []

        result = OandaRetryService(
            policy=OandaRetryPolicy(
                max_attempts=50,
                backoff_base_seconds=1,
                backoff_max_seconds=2,
                jitter_ratio=0,
            ),
            sleep=sleeps.append,
        ).call(
            scenario,
            label="Fetch pending orders",
        )

        assert result == "orders"
        assert scenario.calls == 3
        assert sleeps == [1, 2]

    def test_retries_oanda_insufficient_authorization_401(self) -> None:
        scenario = OandaRetryCallable(
            error_message="Failed to fetch pending orders: status 401",
            internal_detail="Insufficient authorization to perform request.",
            succeed_on_call=2,
        )

        result = OandaRetryService(
            policy=OandaRetryPolicy(max_attempts=3, backoff_base_seconds=0, jitter_ratio=0),
        ).call(
            scenario,
            label="Fetch pending orders",
        )

        assert result == "orders"
        assert scenario.calls == 2

    def test_classifier_rejects_invalid_token_failure(self) -> None:
        classifier = OandaRetryClassifier()
        error = OandaAPIError(
            "Failed to fetch pending orders: status 401",
            internal_detail="Invalid token.",
        )

        assert classifier.is_retryable(error) is False

    def test_uses_attempt_count_for_retry_exhaustion(self) -> None:
        scenario = OandaRetryCallable(error_message="Failed to fetch trades: status 503")
        sleeps: list[float] = []

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
                scenario,
                label="Fetch open trades",
            )
        except RuntimeError as exc:
            assert "Fetch open trades failed after 3 attempts" in str(exc)
        else:  # pragma: no cover - defensive assertion
            raise AssertionError("Expected RuntimeError")

        assert scenario.calls == 3
        assert sleeps == [1, 2]

    def test_records_retry_recovery_counters(self) -> None:
        recorder = OandaRetryMetricRecorder(key_prefix=f"test:oanda-retry:{uuid4()}")
        recorder.reset()
        scenario = OandaRetryCallable(
            error_message="Failed to fetch pending orders: status 401",
            succeed_on_call=3,
        )

        result = OandaRetryService(
            policy=OandaRetryPolicy(
                max_attempts=5,
                backoff_base_seconds=0,
                backoff_max_seconds=0,
                jitter_ratio=0,
            ),
            sleep=lambda _delay: None,
            telemetry=OandaRetryTelemetry(recorder=recorder),
        ).call(scenario, label="Fetch pending orders")

        snapshot = recorder.snapshot()
        assert result == "orders"
        assert snapshot.retry_scheduled == 2
        assert snapshot.recovered == 1

    def test_persists_retry_counters_over_time(self) -> None:
        namespace = f"test:oanda-retry:{uuid4()}"
        recorder = OandaRetryMetricRecorder(
            cache_backend=InMemoryCache(),
            key_prefix=namespace,
        )
        recorder.reset()

        recorder.record_retry_scheduled(label="Fetch pending orders")
        recorder.record_recovered(label="Fetch pending orders", attempts_used=3)

        cold_recorder = OandaRetryMetricRecorder(
            cache_backend=InMemoryCache(),
            key_prefix=namespace,
        )
        snapshot = cold_recorder.snapshot()

        assert snapshot.retry_scheduled == 1
        assert snapshot.recovered == 1
        assert snapshot.terminal == 0
        assert snapshot.exhausted == 0
        cold_recorder.reset()


@pytest.mark.django_db
class TestOandaRetryClassifierTransientFailures:
    """Regression tests covering DNS / SDK transport failures.

    These were previously misclassified as terminal because the v20 SDK and
    ``requests`` raise high-level wrappers (``V20ConnectionError``,
    ``ConnectionError``) whose ``str()`` does not contain any of the
    transient markers used by :class:`OandaRetryClassifier`. The classifier
    now also inspects ``internal_detail``, which the request executor
    populates with the full ``__cause__`` / ``__context__`` chain so DNS
    blips are retryable end-to-end.
    """

    def test_classifies_dns_failure_chain_as_retryable(self) -> None:
        classifier = OandaRetryClassifier()
        # Mirrors the production failure observed for trading task
        # a22ce941-62f5-4932-9ad2-fc685cb8f728: gaierror -> NameResolutionError
        # -> MaxRetryError -> requests.ConnectionError -> V20ConnectionError.
        internal_detail = (
            "V20ConnectionError: Connection to v20 REST server at "
            "https://api-fxpractice.oanda.com:443/v3/accounts/123/pendingOrders failed | "
            "ConnectionError: HTTPSConnectionPool(host='api-fxpractice.oanda.com', port=443): "
            "Max retries exceeded with url: /v3/accounts/123/pendingOrders | "
            "MaxRetryError: HTTPSConnectionPool(host='api-fxpractice.oanda.com', port=443): "
            "Max retries exceeded ... | "
            "NameResolutionError: HTTPSConnection(host='api-fxpractice.oanda.com', port=443): "
            "Failed to resolve 'api-fxpractice.oanda.com' "
            "([Errno -3] Temporary failure in name resolution) | "
            "gaierror: [Errno -3] Temporary failure in name resolution"
        )
        error = OandaAPIError(
            "Error fetching pending orders",
            internal_detail=internal_detail,
        )

        assert classifier.is_retryable(error) is True

    def test_classifies_v20_connection_wrapper_as_retryable(self) -> None:
        """Even the bare wrapper text alone must look retryable now."""
        classifier = OandaRetryClassifier()
        error = OandaAPIError(
            "Error fetching pending orders",
            internal_detail=(
                "Connection to v20 REST server at "
                "https://api-fxpractice.oanda.com:443/v3/accounts/123/pendingOrders failed"
            ),
        )

        assert classifier.is_retryable(error) is True


@pytest.mark.django_db
class TestRequestExecutorExceptionChain:
    """Validate the executor surfaces the full cause chain to the classifier."""

    def test_internal_detail_contains_root_cause(self) -> None:
        from apps.market.services.oanda_retry import OandaApiRequestExecutor

        # Build the same chain the v20 SDK + requests raises for a DNS blip.
        try:
            try:
                try:
                    raise OSError("[Errno -3] Temporary failure in name resolution")
                except OSError as gai:
                    raise ConnectionError(
                        "HTTPSConnectionPool(host='api-fxpractice.oanda.com', port=443): "
                        "Max retries exceeded with url: /v3/accounts/123/pendingOrders"
                    ) from gai
            except ConnectionError as conn:
                raise RuntimeError(
                    "Connection to v20 REST server at "
                    "https://api-fxpractice.oanda.com:443/v3/accounts/123/pendingOrders failed"
                ) from conn
        except RuntimeError as v20_error:
            captured: Exception = v20_error

        executor = OandaApiRequestExecutor(
            retry_service=OandaRetryService(
                policy=OandaRetryPolicy(max_attempts=1, backoff_base_seconds=0),
                raise_runtime_error=False,
            ),
        )

        def _failing_call() -> None:
            raise captured

        try:
            executor.request(
                _failing_call,
                label="Fetch pending orders",
                exception_message="Error fetching pending orders",
            )
        except OandaAPIError as exc:
            detail = exc.internal_detail
            assert "Temporary failure in name resolution" in detail
            assert "v20 REST server" in detail
            assert OandaRetryClassifier().is_retryable(exc) is True
        else:  # pragma: no cover - defensive assertion
            raise AssertionError("Expected OandaAPIError")
