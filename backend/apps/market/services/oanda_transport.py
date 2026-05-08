"""Transport helpers for OANDA API calls."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
import re
from types import SimpleNamespace
from typing import Any

from apps.market.enums import MarketEventSeverity, MarketEventType
from apps.market.services.oanda_retry import OandaRetryPolicy, OandaRetryService


@dataclass(frozen=True, slots=True)
class OandaOrderClientExtensions:
    """Apply OANDA client extension ids to order payloads."""

    max_id_length: int = 128

    def apply(self, order_data: dict[str, Any], client_order_id: str | None) -> str | None:
        """Attach a sanitized client order id to the payload when one is supplied."""
        client_id = self.sanitize(client_order_id)
        if client_id is None:
            return None
        extensions = order_data.setdefault("clientExtensions", {})
        if isinstance(extensions, dict):
            extensions["id"] = client_id
        return client_id

    def from_order_data(self, order_data: dict[str, Any]) -> str | None:
        """Return the client id already attached to an order payload."""
        extensions = order_data.get("clientExtensions")
        if not isinstance(extensions, dict):
            return None
        return self.sanitize(extensions.get("id"))

    def sanitize(self, value: Any) -> str | None:
        """Return an OANDA-safe client id or None for blank input."""
        if value in (None, ""):
            return None
        safe = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value)).strip("-")
        if not safe:
            return None
        return safe[: self.max_id_length]


class OandaRecoveredOrderResponseBuilder:
    """Build order-create shaped responses from recovered OANDA order resources."""

    def build(self, response: Any) -> Any | None:
        """Return a response compatible with order parsing, or None if impossible."""
        order = self._order_from(response)
        if order is None:
            return None

        order_id = str(self._field(order, "id") or "")
        if not order_id:
            return None

        order_type = str(self._field(order, "type") or "MARKET").upper()
        create_time = self._field(order, "createTime")
        fill_time = self._field(order, "filledTime") or create_time
        price = self._field(order, "price")
        state = str(self._field(order, "state") or "").upper()
        create_tx = {
            "id": order_id,
            "time": create_time,
            "type": f"{order_type}_ORDER",
        }
        fill_tx = None
        if state == "FILLED":
            fill_tx = {
                "id": order_id,
                "time": fill_time,
                "price": price,
            }
            trade_id = self._field(order, "tradeOpenedID") or self._field(order, "tradeID")
            if trade_id not in (None, ""):
                fill_tx["tradeOpened"] = {"tradeID": str(trade_id)}

        body = {
            "orderCreateTransaction": create_tx,
            "orderFillTransaction": fill_tx,
            "orderRejectTransaction": None,
            "recoveredOrder": order,
        }
        return SimpleNamespace(
            status=200,
            body=body,
            orderCreateTransaction=create_tx,
            orderFillTransaction=fill_tx,
            orderRejectTransaction=None,
        )

    def _order_from(self, response: Any) -> Any | None:
        body = getattr(response, "body", None)
        if isinstance(body, dict):
            return body.get("order")
        return getattr(response, "order", None)

    def _field(self, value: Any, field_name: str) -> Any:
        if isinstance(value, dict):
            return value.get(field_name)
        return getattr(value, field_name, None)


class OandaOrderRecoveryService:
    """Recover an order by client id after an ambiguous order-create failure."""

    def __init__(
        self,
        *,
        api: Any,
        account: Any,
        retry_service: OandaRetryService,
        logger: Any,
        error_class: type[Exception],
        response_builder: OandaRecoveredOrderResponseBuilder | None = None,
    ) -> None:
        self.api = api
        self.account = account
        self.retry_service = retry_service
        self.logger = logger
        self.error_class = error_class
        self.response_builder = response_builder or OandaRecoveredOrderResponseBuilder()

    def recover(self, client_order_id: str | None) -> Any | None:
        """Fetch an existing OANDA order by client id and adapt it to create response shape."""
        if not client_order_id:
            return None

        def _fetch() -> Any:
            try:
                response = self.api.order.get(self.account.account_id, f"@{client_order_id}")
            except Exception as exc:  # pylint: disable=broad-exception-caught
                raise self.error_class(
                    "Order recovery failed",
                    internal_detail=str(exc),
                ) from exc
            status = getattr(response, "status", None)
            if status != 200:
                raise self.error_class(
                    f"Order recovery failed: status {status}",
                    internal_detail=str(getattr(response, "body", "") or ""),
                )
            return response

        try:
            response = self.retry_service.call(
                _fetch,
                label="Recover OANDA order by client id",
            )
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self.logger.debug(
                "Unable to recover OANDA order by client id %s: %s",
                client_order_id,
                exc,
                exc_info=True,
            )
            return None

        recovered = self.response_builder.build(response)
        if recovered is None:
            self.logger.debug(
                "OANDA order recovery returned an unsupported response for client id %s",
                client_order_id,
            )
            return None
        self.logger.warning(
            "Recovered OANDA order by client id after ambiguous create failure: %s",
            client_order_id,
        )
        return recovered


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
        self.client_extensions = OandaOrderClientExtensions()
        self.recovery_service = OandaOrderRecoveryService(
            api=api,
            account=account,
            retry_service=self.retry_service,
            logger=logger,
            error_class=error_class,
        )

    def execute_order(self, order_data: dict[str, Any]) -> Any:
        """Submit an order to OANDA, retrying transient failures."""
        last_error: str | None = None
        client_order_id = self.client_extensions.from_order_data(order_data)

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

        recovered = self.recovery_service.recover(client_order_id)
        if recovered is not None:
            return recovered

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
