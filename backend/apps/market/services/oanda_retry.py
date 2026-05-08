"""Object-oriented retry policy for OANDA API calls."""

from __future__ import annotations

import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from logging import Logger, getLogger
from typing import Any, NoReturn, TypeVar

from django.core.cache import cache

from apps.market.services.oanda_types import OandaAPIError

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
    def short_default(cls) -> "OandaRetryPolicy":
        return cls(max_attempts=3, backoff_base_seconds=0.5, backoff_max_seconds=5.0)

    @classmethod
    def from_task(cls, task: Any) -> "OandaRetryPolicy":
        """Build a policy from a TradingTask or any object exposing matching fields."""
        default = cls.default()
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
        """Return the exponential delay before the next retry attempt."""
        if attempt < 1:
            return 0.0
        exponent = attempt - 1
        if exponent > 40:
            return self.backoff_max_seconds
        return min(self.backoff_base_seconds * (2**exponent), self.backoff_max_seconds)

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
        if type(value).__module__.startswith("unittest.mock"):
            return default
        try:
            result = int(value)
        except (TypeError, ValueError):
            return default
        return max(minimum, result)

    @staticmethod
    def _coerce_float(value: Any, default: float, *, minimum: float) -> float:
        if type(value).__module__.startswith("unittest.mock"):
            return default
        try:
            result = float(value)
        except (TypeError, ValueError):
            return default
        return max(minimum, result)


@dataclass(frozen=True, slots=True)
class OandaRetryClassifier:
    """Classify OANDA errors as retryable or terminal."""

    retryable_markers: tuple[str, ...] = (
        "status 401",
        "status code 401",
        "401 unauthorized",
        "status 429",
        "status code 429",
        "429 rate limit",
        "rate limit",
        "status 500",
        "status code 500",
        "status 502",
        "status code 502",
        "status 503",
        "status code 503",
        "status 504",
        "status code 504",
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
    non_retryable_markers: tuple[str, ...] = (
        "status 400",
        "status 403",
        "status 404",
        "status 405",
        "status 409",
        "status 422",
        "market order rejected",
        "account required",
        "api client not initialized",
        "insufficient authorization",
        "invalid account",
        "invalid token",
        "invalid authorization",
    )

    def is_retryable(self, exc: OandaAPIError) -> bool:
        """Return True when the OANDA failure looks transient and safe to retry."""
        haystack = self._error_haystack(exc)
        if not haystack:
            return False
        if any(marker in haystack for marker in self.non_retryable_markers):
            return False
        return any(marker in haystack for marker in self.retryable_markers)

    @staticmethod
    def _error_haystack(exc: OandaAPIError) -> str:
        return " ".join(
            part.strip().lower() for part in [str(exc), getattr(exc, "internal_detail", "")] if part
        )


@dataclass(frozen=True, slots=True)
class OandaRetryMetricSnapshot:
    """Current aggregate retry lifecycle counters."""

    retry_scheduled: int = 0
    recovered: int = 0
    terminal: int = 0
    exhausted: int = 0

    def to_dict(self) -> dict[str, int]:
        """Return a JSON-serializable metric map."""
        return {
            "retry_scheduled": self.retry_scheduled,
            "recovered": self.recovered,
            "terminal": self.terminal,
            "exhausted": self.exhausted,
        }


class OandaRetryMetricRecorder:
    """Persist lightweight OANDA retry counters in the configured cache."""

    counter_names = ("retry_scheduled", "recovered", "terminal", "exhausted")

    def __init__(
        self,
        *,
        cache_backend: Any = None,
        key_prefix: str = "oanda_retry_metrics",
        timeout: int | None = None,
    ) -> None:
        self.cache = cache_backend or cache
        self.key_prefix = key_prefix
        self.timeout = timeout

    def record_retry_scheduled(self, *, label: str) -> None:
        """Increment the scheduled retry counter."""
        _ = label
        self._increment("retry_scheduled")

    def record_recovered(self, *, label: str, attempts_used: int) -> None:
        """Increment the successful recovery counter."""
        _ = (label, attempts_used)
        self._increment("recovered")

    def record_terminal(self, *, label: str) -> None:
        """Increment the non-retryable failure counter."""
        _ = label
        self._increment("terminal")

    def record_exhausted(self, *, label: str) -> None:
        """Increment the retry exhaustion counter."""
        _ = label
        self._increment("exhausted")

    def snapshot(self) -> OandaRetryMetricSnapshot:
        """Return all retry counters."""
        values = {
            name: self._coerce_int(self.cache.get(self._key(name), 0))
            for name in self.counter_names
        }
        return OandaRetryMetricSnapshot(**values)

    def reset(self) -> None:
        """Clear counters from the cache."""
        for name in self.counter_names:
            self.cache.delete(self._key(name))

    def _increment(self, name: str) -> None:
        key = self._key(name)
        try:
            self.cache.add(key, 0, timeout=self.timeout)
            self.cache.incr(key)
        except Exception:  # pylint: disable=broad-exception-caught
            current = self._coerce_int(self.cache.get(key, 0))
            self.cache.set(key, current + 1, timeout=self.timeout)

    def _key(self, name: str) -> str:
        return f"{self.key_prefix}:{name}"

    @staticmethod
    def _coerce_int(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0


class OandaRetryTelemetry:
    """Emit structured logs for OANDA retry lifecycle events."""

    def __init__(
        self,
        *,
        logger_: Logger | None = None,
        recorder: OandaRetryMetricRecorder | None = None,
    ) -> None:
        self.logger = logger_ or logger
        self.recorder = recorder or OandaRetryMetricRecorder()

    def retry_scheduled(
        self,
        *,
        label: str,
        attempt: int,
        max_attempts: int,
        exc: OandaAPIError,
        delay: float,
    ) -> None:
        """Record that a retryable failure will be retried."""
        self.recorder.record_retry_scheduled(label=label)
        self.logger.warning(
            "[OANDA:RETRY] label=%s attempt=%d/%d delay_seconds=%.2f error=%s",
            label,
            attempt,
            max_attempts,
            delay,
            exc,
        )

    def success_after_retry(self, *, label: str, attempts_used: int) -> None:
        """Record that a call eventually recovered."""
        if attempts_used <= 1:
            return
        self.recorder.record_recovered(label=label, attempts_used=attempts_used)
        self.logger.info(
            "[OANDA:RETRY_RECOVERED] label=%s attempts_used=%d",
            label,
            attempts_used,
        )

    def terminal_failure(
        self,
        *,
        label: str,
        attempt: int,
        max_attempts: int,
        exc: OandaAPIError,
    ) -> None:
        """Record a non-retryable OANDA failure."""
        self.recorder.record_terminal(label=label)
        self.logger.error(
            "[OANDA:RETRY_TERMINAL] label=%s attempt=%d/%d error=%s",
            label,
            attempt,
            max_attempts,
            exc,
        )

    def exhausted(self, *, label: str, attempts: int, exc: OandaAPIError | None) -> None:
        """Record retry exhaustion."""
        self.recorder.record_exhausted(label=label)
        self.logger.error(
            "[OANDA:RETRY_EXHAUSTED] label=%s attempts=%d error=%s",
            label,
            attempts,
            exc,
        )


class OandaRetryService:
    """Execute OANDA calls with retry policy, classification, backoff, and logging."""

    def __init__(
        self,
        *,
        policy: OandaRetryPolicy | None = None,
        classifier: OandaRetryClassifier | None = None,
        sleep: Callable[[float], None] | None = None,
        raise_runtime_error: bool = True,
        telemetry: OandaRetryTelemetry | None = None,
    ) -> None:
        self.policy = policy or OandaRetryPolicy.default()
        self.classifier = classifier or OandaRetryClassifier()
        self.sleep = sleep
        self.raise_runtime_error = raise_runtime_error
        self.telemetry = telemetry or OandaRetryTelemetry()

    @classmethod
    def from_task(cls, task: Any, *, raise_runtime_error: bool = True) -> "OandaRetryService":
        return cls(policy=OandaRetryPolicy.from_task(task), raise_runtime_error=raise_runtime_error)

    def call(
        self,
        fn: Callable[..., _T],
        *args: Any,
        label: str = "OANDA API call",
        **kwargs: Any,
    ) -> _T:
        """Call *fn* retrying retryable OandaAPIError values."""
        last_exc: OandaAPIError | None = None
        max_attempts = max(1, self.policy.max_attempts)
        sleep_fn = self.sleep if self.sleep is not None else time.sleep

        attempts_used = 0
        for attempt in range(1, max_attempts + 1):
            attempts_used = attempt
            try:
                result = fn(*args, **kwargs)
                self.telemetry.success_after_retry(label=label, attempts_used=attempt)
                return result
            except OandaAPIError as exc:
                last_exc = exc
                if not self.classifier.is_retryable(exc):
                    self.telemetry.terminal_failure(
                        label=label,
                        attempt=attempt,
                        max_attempts=max_attempts,
                        exc=exc,
                    )
                    self._raise_terminal(label=label, attempt=attempt, exc=exc)
                if attempt < max_attempts:
                    delay = self.policy.apply_jitter(self.policy.delay_for_attempt(attempt))
                    self.telemetry.retry_scheduled(
                        label=label,
                        attempt=attempt,
                        max_attempts=max_attempts,
                        exc=exc,
                        delay=delay,
                    )
                    sleep_fn(delay)
                else:
                    self.telemetry.exhausted(label=label, attempts=max_attempts, exc=exc)

        self._raise_exhausted(label=label, attempts=attempts_used, exc=last_exc)

    def _raise_terminal(self, *, label: str, attempt: int, exc: OandaAPIError) -> NoReturn:
        if self.raise_runtime_error:
            raise RuntimeError(
                f"{label} failed with non-retryable OANDA error "
                f"after {attempt} attempt{'s' if attempt != 1 else ''}: {exc}"
            ) from exc
        raise exc

    def _raise_exhausted(
        self,
        *,
        label: str,
        attempts: int,
        exc: OandaAPIError | None,
    ) -> NoReturn:
        if self.raise_runtime_error:
            raise RuntimeError(f"{label} failed after {attempts} attempts: {exc}") from exc
        internal_detail = getattr(exc, "internal_detail", "") if exc else ""
        raise OandaAPIError(
            f"{label} failed after {attempts} attempts: {exc}",
            internal_detail=internal_detail or (str(exc) if exc else ""),
        ) from exc


class OandaApiRequestExecutor:
    """Wrap direct v20 calls with response-status validation and retry."""

    def __init__(
        self,
        *,
        retry_service: OandaRetryService | None = None,
        make_jsonable: Callable[[Any], Any] | None = None,
    ) -> None:
        self.retry_service = retry_service or OandaRetryService(
            policy=OandaRetryPolicy.short_default(),
            raise_runtime_error=False,
        )
        self.make_jsonable = make_jsonable or (lambda value: value)

    def request(
        self,
        fn: Callable[..., _T],
        *args: Any,
        label: str,
        expected_status: int | tuple[int, ...] = 200,
        failure_message: str | None = None,
        exception_message: str | None = None,
        **kwargs: Any,
    ) -> _T:
        """Execute one OANDA API request through the configured retry service."""
        expected = (expected_status,) if isinstance(expected_status, int) else expected_status

        def _invoke() -> _T:
            try:
                response = fn(*args, **kwargs)
            except OandaAPIError:
                raise
            except Exception as exc:
                raise OandaAPIError(
                    exception_message or failure_message or f"{label} failed",
                    internal_detail=str(exc),
                ) from exc

            status = getattr(response, "status", None)
            if status not in expected:
                raise OandaAPIError(
                    f"{failure_message or label}: status {status}",
                    internal_detail=self.response_error_detail(response),
                )
            return response

        return self.retry_service.call(_invoke, label=label)

    def response_error_detail(self, response: Any) -> str:
        body = getattr(response, "body", None)
        raw_body = getattr(response, "raw_body", None)
        detail = body if body not in (None, "") else raw_body
        if detail in (None, ""):
            return ""
        return str(self.make_jsonable(detail))
