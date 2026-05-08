"""Transport helpers for OANDA API calls."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from apps.market.enums import MarketEventSeverity, MarketEventType
from apps.market.services.oanda_retry import OandaRetryPolicy, OandaRetryService


class OandaOrderTransport:
    """Execute OANDA order submissions with retry and event logging."""

    def __init__(
        self,
        *,
        api,
        account,
        event_service,
        logger,
        error_class: type[Exception],
        retry_service: OandaRetryService | None = None,
        max_retries: int = 3,
        retry_delay: float = 0.5,
        max_retry_delay: float = 5.0,
        sleep_func: Callable[[float], None] = time.sleep,
        randbelow_func: Callable[[int], int] | None = None,
    ) -> None:
        _ = randbelow_func
        self.api = api
        self.account = account
        self.event_service = event_service
        self.logger = logger
        self.retry_service = retry_service or OandaRetryService(
            policy=OandaRetryPolicy(
                max_attempts=max_retries,
                backoff_base_seconds=retry_delay,
                backoff_max_seconds=max_retry_delay,
            ),
            sleep=sleep_func,
            raise_runtime_error=False,
        )
        self.error_class = error_class

    def execute_order(self, order_data: dict[str, Any]) -> Any:
        """Submit an order to OANDA, retrying transient failures."""
        last_error: str | None = None

        def _submit() -> Any:
            nonlocal last_error
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
                    "retryable",
                    response.status,
                    error_details,
                )
                last_error = f"API returned status {response.status}{error_details}"
                raise self.error_class(
                    f"Order submission failed: status {response.status}",
                    internal_detail=last_error,
                )

            except Exception as exc:  # pylint: disable=broad-exception-caught
                if isinstance(exc, self.error_class):
                    raise
                self.logger.warning("Order submission attempt failed: %s", exc)
                last_error = str(exc)
                raise self.error_class(
                    "Order submission failed",
                    internal_detail=str(exc),
                ) from exc

        try:
            return self.retry_service.call(_submit, label="Order submission")
        except self.error_class as exc:
            last_error = str(exc)

        self._log_failure(order_data, last_error)
        attempts = self.retry_service.policy.max_attempts
        error_msg = f"Order submission failed after {attempts} attempts: {last_error}"
        raise self.error_class(error_msg)

    def _log_failure(self, order_data: dict[str, Any], last_error: str | None) -> None:
        self.logger.error(
            "Order submission failed after %s attempts: %s",
            self.retry_service.policy.max_attempts,
            last_error,
        )
        self.event_service.log_trading_event(
            event_type=MarketEventType.ORDER_FAILED,
            description=f"Order submission failed after {self.retry_service.policy.max_attempts} attempts",
            severity=MarketEventSeverity.ERROR,
            user=self.account.user,
            account=self.account,
            instrument=str(order_data.get("instrument") or "") or None,
            details={
                "order_data": order_data,
                "error": last_error,
                "attempts": self.retry_service.policy.max_attempts,
            },
        )
