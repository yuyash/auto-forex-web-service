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


@dataclass(frozen=True, slots=True)
class OandaClientOrderFill:
    """A transaction-history fill matched by OANDA client order id."""

    transaction_id: str
    time: Any | None = None
    price: Any | None = None
    trade_id: str | None = None


class OandaClientOrderTransactionFinder:
    """Find filled OANDA market orders through transaction history."""

    def __init__(
        self,
        *,
        api: Any,
        account: Any,
        retry_service: OandaRetryService,
        logger: Any,
        error_class: type[Exception],
        page_size: int = 100,
    ) -> None:
        self.api = api
        self.account = account
        self.retry_service = retry_service
        self.logger = logger
        self.error_class = error_class
        self.page_size = page_size

    def find_fill(self, client_order_id: str | None) -> OandaClientOrderFill | None:
        """Return the newest matching ORDER_FILL transaction, if one is visible."""
        if not client_order_id or not hasattr(self.api, "transaction"):
            return None

        try:
            response = self.retry_service.call(
                self.fetch_recent_fills,
                label="Recover OANDA order fill by client id",
            )
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self.logger.debug(
                "Unable to recover OANDA order fill transaction for client id %s: %s",
                client_order_id,
                exc,
                exc_info=True,
            )
            return None
        return self._match_response(response=response, client_order_id=client_order_id)

    def fetch_recent_fills(self) -> Any:
        """Fetch recent ORDER_FILL transactions from OANDA."""
        try:
            response = self.api.transaction.list(
                self.account.account_id,
                pageSize=self.page_size,
                type="ORDER_FILL",
            )
        except Exception as exc:  # pylint: disable=broad-exception-caught
            raise self.error_class(
                "Order transaction recovery failed",
                internal_detail=str(exc),
            ) from exc
        status = getattr(response, "status", None)
        if status != 200:
            raise self.error_class(
                f"Order transaction recovery failed: status {status}",
                internal_detail=str(getattr(response, "body", "") or ""),
            )
        return response

    def _match_response(
        self, *, response: Any, client_order_id: str
    ) -> OandaClientOrderFill | None:
        transactions = self._transactions_from(response)
        for transaction in reversed(transactions):
            if self._matches_client_order_id(transaction, client_order_id):
                return self._fill_from(transaction)
        return None

    def _transactions_from(self, response: Any) -> list[Any]:
        body = getattr(response, "body", None)
        if isinstance(body, dict):
            transactions = body.get("transactions") or []
            return list(transactions) if isinstance(transactions, list) else []
        transactions = getattr(response, "transactions", None)
        return list(transactions) if isinstance(transactions, list) else []

    def _matches_client_order_id(self, transaction: Any, client_order_id: str) -> bool:
        candidates = [
            self._field(transaction, "clientOrderID"),
            self._nested_field(transaction, "orderClientExtensions", "id"),
            self._nested_field(transaction, "clientExtensions", "id"),
        ]
        return any(str(candidate) == client_order_id for candidate in candidates if candidate)

    def _fill_from(self, transaction: Any) -> OandaClientOrderFill | None:
        transaction_id = self._field(transaction, "id")
        if transaction_id in (None, ""):
            return None
        return OandaClientOrderFill(
            transaction_id=str(transaction_id),
            time=self._field(transaction, "time"),
            price=self._field(transaction, "price"),
            trade_id=self._trade_id_from(transaction),
        )

    def _trade_id_from(self, transaction: Any) -> str | None:
        trade_opened = self._field(transaction, "tradeOpened")
        trade_id = self._field(trade_opened, "tradeID")
        if trade_id not in (None, ""):
            return str(trade_id)
        for field_name in ("tradeOpenedID", "tradeID"):
            trade_id = self._field(transaction, field_name)
            if trade_id not in (None, ""):
                return str(trade_id)
        trades_closed = self._field(transaction, "tradesClosed")
        if isinstance(trades_closed, list) and trades_closed:
            trade_id = self._field(trades_closed[0], "tradeID")
            if trade_id not in (None, ""):
                return str(trade_id)
        return None

    def _nested_field(self, value: Any, parent: str, child: str) -> Any:
        return self._field(self._field(value, parent), child)

    def _field(self, value: Any, field_name: str) -> Any:
        if isinstance(value, dict):
            return value.get(field_name)
        return getattr(value, field_name, None)


class OandaRecoveredOrderResponseBuilder:
    """Build order-create shaped responses from recovered OANDA order resources."""

    def build(
        self,
        response: Any,
        *,
        fill_transaction: OandaClientOrderFill | None = None,
    ) -> Any | None:
        """Return a response compatible with order parsing, or None if impossible."""
        order = self._order_from(response)
        if order is None:
            return None

        order_id = str(self._field(order, "id") or "")
        if not order_id:
            return None

        order_type = str(self._field(order, "type") or "MARKET").upper()
        create_time = self._field(order, "createTime")
        fill_time = self._fill_field(
            fill_transaction=fill_transaction,
            fill_field="time",
            order=order,
            order_field="filledTime",
            fallback=create_time,
        )
        price = self._fill_field(
            fill_transaction=fill_transaction,
            fill_field="price",
            order=order,
            order_field="price",
        )
        state = str(self._field(order, "state") or "").upper()
        create_tx = {
            "id": order_id,
            "time": create_time,
            "type": f"{order_type}_ORDER",
        }
        fill_tx = None
        if state == "FILLED" or fill_transaction is not None:
            fill_tx = {
                "id": fill_transaction.transaction_id if fill_transaction else order_id,
                "time": fill_time,
                "price": price,
            }
            trade_id = (
                fill_transaction.trade_id
                if fill_transaction and fill_transaction.trade_id
                else self._field(order, "tradeOpenedID") or self._field(order, "tradeID")
            )
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

    def _fill_field(
        self,
        *,
        fill_transaction: OandaClientOrderFill | None,
        fill_field: str,
        order: Any,
        order_field: str,
        fallback: Any | None = None,
    ) -> Any:
        if fill_transaction is not None:
            value = getattr(fill_transaction, fill_field)
            if value not in (None, ""):
                return value
        value = self._field(order, order_field)
        return fallback if value in (None, "") else value


class OandaRecoveredOrderFetcher:
    """Fetch an OANDA order by client id."""

    def __init__(
        self,
        *,
        api: Any,
        account: Any,
        error_class: type[Exception],
    ) -> None:
        self.api = api
        self.account = account
        self.error_class = error_class

    def fetch_by_client_id(self, client_order_id: str) -> Any:
        """Fetch an order resource with OANDA's @client-id lookup."""
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
        transaction_finder: OandaClientOrderTransactionFinder | None = None,
        order_fetcher: OandaRecoveredOrderFetcher | None = None,
    ) -> None:
        self.api = api
        self.account = account
        self.retry_service = retry_service
        self.logger = logger
        self.error_class = error_class
        self.response_builder = response_builder or OandaRecoveredOrderResponseBuilder()
        self.order_fetcher = order_fetcher or OandaRecoveredOrderFetcher(
            api=api,
            account=account,
            error_class=error_class,
        )
        self.transaction_finder = transaction_finder or OandaClientOrderTransactionFinder(
            api=api,
            account=account,
            retry_service=retry_service,
            logger=logger,
            error_class=error_class,
        )

    def recover(self, client_order_id: str | None) -> Any | None:
        """Fetch an existing OANDA order by client id and adapt it to create response shape."""
        if not client_order_id:
            return None

        try:
            response = self.retry_service.call(
                self.order_fetcher.fetch_by_client_id,
                client_order_id,
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

        fill_transaction = self.transaction_finder.find_fill(client_order_id)
        recovered = self.response_builder.build(
            response,
            fill_transaction=fill_transaction,
        )
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


class OandaOrderSubmitter:
    """Submit OANDA orders and retain the latest submission error."""

    def __init__(
        self,
        *,
        api: Any,
        account: Any,
        logger: Any,
        error_class: type[Exception],
    ) -> None:
        self.api = api
        self.account = account
        self.logger = logger
        self.error_class = error_class
        self.last_error: str | None = None

    def submit(self, order_data: dict[str, Any]) -> Any:
        """Submit an order once, raising OANDA errors for retry classification."""
        try:
            response = self.api.order.create(self.account.account_id, order=order_data)
            if response.status in (200, 201):
                return response

            error_details = self._response_error_details(response)
            self.logger.warning(
                "Order submission attempt %s failed: status %s%s",
                "retryable",
                response.status,
                error_details,
            )
            self.last_error = f"API returned status {response.status}{error_details}"
            raise self.error_class(
                f"Order submission failed: status {response.status}",
                internal_detail=self.last_error,
            )

        except Exception as exc:  # pylint: disable=broad-exception-caught
            if isinstance(exc, self.error_class):
                raise
            self.logger.warning("Order submission attempt failed: %s", exc)
            self.last_error = str(exc)
            raise self.error_class(
                "Order submission failed",
                internal_detail=str(exc),
            ) from exc

    def _response_error_details(self, response: Any) -> str:
        if hasattr(response, "body") and response.body:
            return f" - {response.body}"
        if hasattr(response, "raw_body"):
            return f" - {response.raw_body}"
        return ""


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
        client_order_id = self.client_extensions.from_order_data(order_data)
        submitter = OandaOrderSubmitter(
            api=self.api,
            account=self.account,
            logger=self.logger,
            error_class=self.error_class,
        )

        try:
            return self.retry_service.call(
                submitter.submit,
                order_data,
                label="Order submission",
            )
        except self.error_class as exc:
            last_error = submitter.last_error or str(exc)

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
