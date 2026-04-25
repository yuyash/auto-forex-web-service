"""Transport helpers for OANDA API calls."""

from __future__ import annotations

import secrets
import time
from collections.abc import Callable
from typing import Any

from apps.market.enums import MarketEventSeverity, MarketEventType


class OandaOrderTransport:
    """Execute OANDA order submissions with retry and event logging."""

    def __init__(
        self,
        *,
        api,
        account,
        event_service,
        logger,
        max_retries: int,
        retry_delay: float,
        max_retry_delay: float,
        error_class: type[Exception],
        sleep_func: Callable[[float], None] = time.sleep,
        randbelow_func: Callable[[int], int] = secrets.randbelow,
    ) -> None:
        self.api = api
        self.account = account
        self.event_service = event_service
        self.logger = logger
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.max_retry_delay = max_retry_delay
        self.error_class = error_class
        self.sleep_func = sleep_func
        self.randbelow_func = randbelow_func

    def execute_order(self, order_data: dict[str, Any]) -> Any:
        """Submit an order to OANDA, retrying transient failures."""
        last_error: str | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.api.order.create(self.account.account_id, order=order_data)

                if response.status in (200, 201):
                    return response

                error_details = ""
                if hasattr(response, "body") and response.body:
                    error_details = f" - {response.body}"
                elif hasattr(response, "raw_body"):
                    error_details = f" - {response.raw_body}"

                self.logger.warning(
                    "Order submission attempt %s failed: status %s%s",
                    attempt,
                    response.status,
                    error_details,
                )
                last_error = f"API returned status {response.status}{error_details}"

                retryable_status = response.status == 429 or 500 <= int(response.status) <= 599
                if not retryable_status:
                    break

            except Exception as exc:  # pylint: disable=broad-exception-caught
                self.logger.warning("Order submission attempt %s failed: %s", attempt, exc)
                last_error = str(exc)
                retryable_exception = isinstance(exc, (ConnectionError, TimeoutError, OSError))
                if not retryable_exception:
                    break

            if attempt < self.max_retries:
                base_delay = min(self.retry_delay * (2 ** (attempt - 1)), self.max_retry_delay)
                jitter = (self.randbelow_func(10_000) / 10_000) * (base_delay * 0.2)
                self.sleep_func(base_delay + jitter)

        self._log_failure(order_data, last_error)
        error_msg = f"Order submission failed after {self.max_retries} attempts: {last_error}"
        raise self.error_class(error_msg)

    def _log_failure(self, order_data: dict[str, Any], last_error: str | None) -> None:
        self.logger.error(
            "Order submission failed after %s attempts: %s",
            self.max_retries,
            last_error,
        )
        self.event_service.log_trading_event(
            event_type=MarketEventType.ORDER_FAILED,
            description=f"Order submission failed after {self.max_retries} attempts",
            severity=MarketEventSeverity.ERROR,
            user=self.account.user,
            account=self.account,
            instrument=str(order_data.get("instrument") or "") or None,
            details={
                "order_data": order_data,
                "error": last_error,
                "attempts": self.max_retries,
            },
        )
