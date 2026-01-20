"""
OANDA API direct client for fetching orders, positions, and account details.

This module provides direct API calls to OANDA without database caching,
replacing the sync-based approach with real-time API queries.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from logging import Logger, getLogger
from typing import Any
from urllib.parse import parse_qs, urlparse

import v20
from django.conf import settings
from v20.transaction import StopLossDetails, TakeProfitDetails

from apps.market.enums import MarketEventSeverity, MarketEventType
from apps.market.models import OandaAccounts, TickData
from apps.market.services.compliance import ComplianceService, ComplianceViolationError
from apps.market.services.events import MarketEventService

logger: Logger = getLogger(name=__name__)


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    OCO = "oco"


class OrderDirection(str, Enum):
    LONG = "long"
    SHORT = "short"


class StreamMessageType(str, Enum):
    PRICE = "PRICE"
    HEARTBEAT = "HEARTBEAT"


@dataclass(frozen=True, slots=True)
class MarketOrderRequest:
    instrument: str
    units: Decimal  # signed (+ long, - short)
    take_profit: Decimal | None = None
    stop_loss: Decimal | None = None


@dataclass(frozen=True, slots=True)
class LimitOrderRequest:
    instrument: str
    units: Decimal  # signed (+ long, - short)
    price: Decimal
    take_profit: Decimal | None = None
    stop_loss: Decimal | None = None


@dataclass(frozen=True, slots=True)
class StopOrderRequest:
    instrument: str
    units: Decimal  # signed (+ long, - short)
    price: Decimal
    take_profit: Decimal | None = None
    stop_loss: Decimal | None = None


@dataclass(frozen=True, slots=True)
class OcoOrderRequest:
    instrument: str
    units: Decimal  # signed (+ long, - short)
    limit_price: Decimal
    stop_price: Decimal


class OrderState(str, Enum):
    PENDING = "PENDING"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    TRIGGERED = "TRIGGERED"
    UNKNOWN = "UNKNOWN"

    @classmethod
    def from_raw(cls, value: Any) -> OrderState:
        if not value:
            return cls.UNKNOWN
        value_str = str(value).upper()
        for member in cls:
            if member.value == value_str:
                return member
        return cls.UNKNOWN


@dataclass(frozen=True, slots=True)
class AccountDetails:
    account_id: str
    currency: str
    balance: Decimal
    nav: Decimal
    unrealized_pl: Decimal
    margin_used: Decimal
    margin_available: Decimal
    position_value: Decimal
    open_trade_count: int
    open_position_count: int
    pending_order_count: int
    last_transaction_id: str


@dataclass(frozen=True, slots=True)
class Position:
    instrument: str
    direction: OrderDirection
    units: Decimal  # absolute
    average_price: Decimal
    unrealized_pnl: Decimal
    trade_ids: list[str]
    account_id: str


@dataclass(frozen=True, slots=True)
class OpenTrade:
    trade_id: str
    instrument: str
    direction: OrderDirection
    units: Decimal  # absolute
    entry_price: Decimal
    unrealized_pnl: Decimal
    open_time: datetime | None
    state: str
    account_id: str


@dataclass(frozen=True, slots=True)
class Order:
    order_id: str
    instrument: str
    order_type: OrderType
    direction: OrderDirection
    units: Decimal  # absolute
    price: Decimal | None
    state: OrderState
    time_in_force: str | None
    create_time: datetime | None
    fill_time: datetime | None = None
    cancel_time: datetime | None = None


@dataclass(frozen=True, slots=True)
class MarketOrder(Order):
    pass


@dataclass(frozen=True, slots=True)
class LimitOrder(Order):
    pass


@dataclass(frozen=True, slots=True)
class StopOrder(Order):
    pass


@dataclass(frozen=True, slots=True)
class PendingOrder(Order):
    pass


@dataclass(frozen=True, slots=True)
class CancelledOrder(Order):
    transaction_id: str | None = None


@dataclass(frozen=True, slots=True)
class OcoOrder(Order):
    limit_order: LimitOrder | None = None
    stop_order: StopOrder | None = None


@dataclass(frozen=True, slots=True)
class Transaction:
    transaction_id: str
    time: datetime | None
    type: str
    instrument: str | None = None
    units: Decimal | None = None
    price: Decimal | None = None
    pl: Decimal | None = None
    account_balance: Decimal | None = None


class OandaAPIError(Exception):
    """Exception raised when OANDA API call fails."""


class OandaService:
    """
    Direct client for OANDA v20 API.

    Provides methods to fetch orders, positions, and account details
    directly from OANDA without database caching.
    """

    def __init__(self, account: OandaAccounts):
        """
        Initialize OANDA API client.

        Args:
            account: OandaAccounts instance with API credentials
        """
        self.account = account
        rest_hostname = str(account.api_hostname)
        stream_hostname = self._to_stream_hostname(rest_hostname)

        self.api = v20.Context(
            hostname=rest_hostname,
            token=account.get_api_token(),
            poll_timeout=10,
        )

        # v20 Context uses a single hostname for both REST and streaming.
        # OANDA streams live on a different hostname (stream-*) than REST (api-*).
        # If we use the REST host for pricing.stream, OANDA returns 404.
        self.stream_hostname = stream_hostname
        self.stream_api = v20.Context(
            hostname=stream_hostname,
            token=account.get_api_token(),
            stream_timeout=int(getattr(settings, "OANDA_STREAM_TIMEOUT", 30)),
            poll_timeout=10,
        )

        self.max_retries = 3
        self.retry_delay = 0.5  # seconds
        self.compliance_manager = ComplianceService(account)
        self.event_service = MarketEventService()
        self._account_resource_cache: dict[str, Any] | None = None

        logger.info(
            "OANDA service initialized (account_id=%s, api_hostname=%s, stream_hostname=%s)",
            str(getattr(account, "account_id", "")),
            rest_hostname,
            stream_hostname,
        )

    @staticmethod
    def _to_stream_hostname(hostname: str) -> str:
        host = (hostname or "").strip()
        if not host:
            return host
        if host.startswith("stream-"):
            return host
        if host.startswith("api-"):
            return "stream-" + host[len("api-") :]
        return host

    @staticmethod
    def _make_jsonable(value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value

        if isinstance(value, Decimal):
            return str(value)

        if isinstance(value, datetime):
            return value.isoformat()

        if isinstance(value, dict):
            return {str(k): OandaService._make_jsonable(v) for k, v in value.items()}

        if isinstance(value, (list, tuple, set)):
            return [OandaService._make_jsonable(v) for v in value]

        return str(value)

    @staticmethod
    def make_jsonable(value: Any) -> Any:
        return OandaService._make_jsonable(value)

    @staticmethod
    def _account_object_to_dict(account_data: Any) -> dict[str, Any]:
        if account_data is None:
            return {}

        if isinstance(account_data, dict):
            return account_data

        properties = getattr(account_data, "_properties", None)
        if isinstance(properties, dict):
            return dict(properties)

        as_dict = getattr(account_data, "dict", None)
        if callable(as_dict):
            try:
                maybe_dict = as_dict()
                if isinstance(maybe_dict, dict):
                    return maybe_dict
            except Exception as exc:  # nosec B110
                # Log conversion failure but continue with fallback
                import logging

                logger = logging.getLogger(__name__)
                logger.debug("Failed to convert account data using .dict(): %s", exc)

        try:
            return dict(vars(account_data))
        except Exception:
            return {"value": str(account_data)}

    def get_account_resource(self, *, refresh: bool = False) -> dict[str, Any]:
        """Fetch the raw OANDA account resource as a dict.

        This is used to expose broker flags/parameters (e.g. `hedgingEnabled`) and
        to avoid repeated network calls by caching within this service instance.
        """

        if not refresh and self._account_resource_cache is not None:
            return self._account_resource_cache

        try:
            response = self.api.account.get(self.account.account_id)
            if response.status != 200:
                raise OandaAPIError(f"Failed to fetch account resource: status {response.status}")

            body = getattr(response, "body", {})
            if hasattr(body, "get"):
                account_data = body.get("account")
            else:
                account_data = getattr(body, "account", None)

            account_resource = self._account_object_to_dict(account_data)
            self._account_resource_cache = account_resource
            return account_resource
        except Exception as e:
            logger.error(
                "Error fetching account resource for %s: %s",
                self.account.account_id,
                str(e),
                exc_info=True,
            )
            raise OandaAPIError(f"Error fetching account resource: {str(e)}") from e

    def cancel_order(self, order: Order) -> CancelledOrder:
        try:
            response = self.api.order.cancel(self.account.account_id, order.order_id)
            if response.status not in (200, 201):
                raise OandaAPIError(
                    f"Failed to cancel order {order.order_id}: status {response.status}"
                )

            cancel_tx = getattr(response, "orderCancelTransaction", None)
            tx_id = getattr(cancel_tx, "id", None) if cancel_tx else None
            cancel_time = self._parse_iso_datetime(
                getattr(cancel_tx, "time", None) if cancel_tx else None
            )

            self.event_service.log_trading_event(
                event_type=MarketEventType.ORDER_CANCELLED,
                description=f"Order cancelled: {order.order_id}",
                severity=MarketEventSeverity.INFO,
                user=self.account.user,
                account=self.account,
                instrument=order.instrument,
                details={"order_id": order.order_id, "transaction_id": tx_id},
            )

            return CancelledOrder(
                order_id=order.order_id,
                instrument=order.instrument,
                order_type=order.order_type,
                direction=order.direction,
                units=order.units,
                price=order.price,
                state=OrderState.CANCELLED,
                time_in_force=order.time_in_force,
                create_time=order.create_time,
                fill_time=order.fill_time,
                cancel_time=cancel_time,
                transaction_id=str(tx_id) if tx_id is not None else None,
            )

        except Exception as e:
            logger.error(
                "Error cancelling order %s for %s: %s",
                order.order_id,
                self.account.account_id,
                str(e),
                exc_info=True,
            )
            raise OandaAPIError(f"Error cancelling order: {str(e)}") from e

    def close_trade(self, trade: OpenTrade, units: Decimal | None = None) -> MarketOrder:
        try:
            kwargs: dict[str, Any] = {"units": str(units) if units else "ALL"}
            response = self.api.trade.close(self.account.account_id, trade.trade_id, **kwargs)

            if response.status not in (200, 201):
                raise OandaAPIError(
                    f"Failed to close trade {trade.trade_id}: status {response.status}"
                )

            fill_tx = getattr(response, "orderFillTransaction", None)
            if not fill_tx and isinstance(getattr(response, "body", None), dict):
                fill_tx = response.body.get("orderFillTransaction")

            fill_time = self._parse_iso_datetime(
                getattr(fill_tx, "time", None) if fill_tx else None
            )
            fill_price = self._to_decimal(getattr(fill_tx, "price", None) if fill_tx else None)
            order_id = str(getattr(fill_tx, "id", "")) if fill_tx else ""

            # Closing a trade is effectively a filled market order.
            return MarketOrder(
                order_id=order_id,
                instrument=trade.instrument,
                order_type=OrderType.MARKET,
                direction=trade.direction,
                units=trade.units if units is None else abs(units),
                price=fill_price,
                state=OrderState.FILLED,
                time_in_force="FOK",
                create_time=fill_time,
                fill_time=fill_time,
            )

        except Exception as e:
            logger.error(
                "Error closing trade %s for %s: %s",
                trade.trade_id,
                self.account.account_id,
                str(e),
                exc_info=True,
            )
            raise OandaAPIError(f"Error closing trade: {str(e)}") from e

    def close_position(self, position: Position, units: Decimal | None = None) -> MarketOrder:
        """
        Close an open position for an instrument.

        OANDA positions are aggregated by instrument. This uses the
        `/v3/accounts/{accountID}/positions/{instrument}/close` endpoint under the hood.

        Args:
            position: A Position returned by get_open_positions().
            units: Optional number of units to close (positive Decimal). If omitted, closes ALL.

        Returns:
            MarketOrder representing the closeout fill.
        """

        try:
            if units is not None:
                if units <= 0:
                    raise ValueError("units must be positive")
                if units > position.units:
                    raise ValueError("units cannot exceed open position units")

            if position.direction == OrderDirection.LONG:
                kwargs: dict[str, Any] = {
                    "longUnits": str(abs(units)) if units is not None else "ALL",
                    "shortUnits": "NONE",
                }
            else:
                kwargs = {
                    "longUnits": "NONE",
                    "shortUnits": str(abs(units)) if units is not None else "ALL",
                }

            response = self.api.position.close(
                self.account.account_id,
                position.instrument,
                **kwargs,
            )

            if response.status not in (200, 201):
                raise OandaAPIError(
                    f"Failed to close position {position.instrument}: status {response.status}"
                )

            fill_tx = None
            if position.direction == OrderDirection.LONG:
                fill_tx = getattr(response, "longOrderFillTransaction", None)
            else:
                fill_tx = getattr(response, "shortOrderFillTransaction", None)

            if not fill_tx and isinstance(getattr(response, "body", None), dict):
                body = response.body
                if position.direction == OrderDirection.LONG:
                    fill_tx = body.get("longOrderFillTransaction")
                else:
                    fill_tx = body.get("shortOrderFillTransaction")

            fill_time = self._parse_iso_datetime(
                getattr(fill_tx, "time", None) if fill_tx else None
            )
            fill_price = self._to_decimal(getattr(fill_tx, "price", None) if fill_tx else None)
            order_id = str(getattr(fill_tx, "id", "")) if fill_tx else ""

            return MarketOrder(
                order_id=order_id,
                instrument=position.instrument,
                order_type=OrderType.MARKET,
                direction=position.direction,
                units=position.units if units is None else abs(units),
                price=fill_price,
                state=OrderState.FILLED,
                time_in_force="FOK",
                create_time=fill_time,
                fill_time=fill_time,
            )

        except Exception as e:
            logger.error(
                "Error closing position %s for %s: %s",
                position.instrument,
                self.account.account_id,
                str(e),
                exc_info=True,
            )
            raise OandaAPIError(f"Error closing position: {str(e)}") from e

    def create_limit_order(self, request: LimitOrderRequest) -> LimitOrder:
        direction = OrderDirection.LONG if request.units > 0 else OrderDirection.SHORT
        abs_units = abs(request.units)

        order_request = {
            "instrument": request.instrument,
            "units": int(request.units),
            "order_type": OrderType.LIMIT.value,
            "price": float(request.price),
        }
        self._validate_compliance(order_request)

        order_data: dict[str, Any] = {
            "instrument": request.instrument,
            "units": str(int(request.units)),
            "price": str(request.price),
            "type": "LIMIT",
            "timeInForce": "GTC",
        }
        if request.take_profit is not None:
            order_data["takeProfitOnFill"] = TakeProfitDetails(
                price=str(request.take_profit)
            ).__dict__
        if request.stop_loss is not None:
            order_data["stopLossOnFill"] = StopLossDetails(price=str(request.stop_loss)).__dict__

        response = self._execute_with_retry(order_data)
        create_tx = getattr(response, "orderCreateTransaction", None)
        order_id = getattr(create_tx, "id", "")
        created_time = self._parse_iso_datetime(getattr(create_tx, "time", None))

        self.event_service.log_trading_event(
            event_type=MarketEventType.ORDER_SUBMITTED,
            description=(
                f"Limit order submitted: {direction.value} {abs_units} {request.instrument} "
                f"@ {request.price}"
            ),
            severity=MarketEventSeverity.INFO,
            user=self.account.user,
            account=self.account,
            instrument=request.instrument,
            details={
                "order_id": order_id,
                "instrument": request.instrument,
                "order_type": OrderType.LIMIT.value,
                "direction": direction.value,
                "units": str(abs_units),
                "price": str(request.price),
                "take_profit": str(request.take_profit) if request.take_profit else None,
                "stop_loss": str(request.stop_loss) if request.stop_loss else None,
                "status": "pending",
            },
        )

        return LimitOrder(
            order_id=str(order_id),
            instrument=str(request.instrument),
            order_type=OrderType.LIMIT,
            direction=direction,
            units=abs_units,
            price=request.price,
            state=OrderState.PENDING,
            time_in_force="GTC",
            create_time=created_time,
        )

    def create_market_order(self, request: MarketOrderRequest) -> MarketOrder:
        direction = OrderDirection.LONG if request.units > 0 else OrderDirection.SHORT
        abs_units = abs(request.units)

        order_request = {
            "instrument": request.instrument,
            "units": int(request.units),
            "order_type": OrderType.MARKET.value,
        }
        self._validate_compliance(order_request)

        order_data: dict[str, Any] = {
            "instrument": request.instrument,
            "units": str(int(request.units)),
            "type": "MARKET",
            "timeInForce": "FOK",
        }
        if request.take_profit is not None:
            order_data["takeProfitOnFill"] = TakeProfitDetails(
                price=str(request.take_profit)
            ).__dict__
        if request.stop_loss is not None:
            order_data["stopLossOnFill"] = StopLossDetails(price=str(request.stop_loss)).__dict__

        response = self._execute_with_retry(order_data)

        fill_tx = getattr(response, "orderFillTransaction", None)
        create_tx = getattr(response, "orderCreateTransaction", None)
        reject_tx = getattr(response, "orderRejectTransaction", None)

        if fill_tx:
            order_id = getattr(fill_tx, "id", None) or getattr(create_tx, "id", "")
            fill_price_raw = getattr(fill_tx, "price", None)
            fill_price = Decimal(str(fill_price_raw)) if fill_price_raw is not None else None
            fill_time = self._parse_iso_datetime(getattr(fill_tx, "time", None))

            self.event_service.log_trading_event(
                event_type=MarketEventType.ORDER_SUBMITTED,
                description=(
                    f"Market order submitted: {direction.value} {abs_units} {request.instrument}"
                ),
                severity=MarketEventSeverity.INFO,
                user=self.account.user,
                account=self.account,
                instrument=request.instrument,
                details={
                    "order_id": order_id,
                    "instrument": request.instrument,
                    "order_type": OrderType.MARKET.value,
                    "direction": direction.value,
                    "units": str(abs_units),
                    "take_profit": str(request.take_profit) if request.take_profit else None,
                    "stop_loss": str(request.stop_loss) if request.stop_loss else None,
                    "status": "filled",
                    "fill_price": str(fill_price) if fill_price is not None else None,
                },
            )

            return MarketOrder(
                order_id=str(order_id),
                instrument=str(request.instrument),
                order_type=OrderType.MARKET,
                direction=direction,
                units=abs_units,
                price=fill_price,
                state=OrderState.FILLED,
                time_in_force="FOK",
                create_time=fill_time,
                fill_time=fill_time,
            )

        reject_reason = getattr(reject_tx, "rejectReason", None) if reject_tx else None
        if not reject_reason and hasattr(response, "body") and isinstance(response.body, dict):
            reject_reason = response.body.get("errorMessage") or response.body.get("rejectReason")
        reject_reason_str = str(reject_reason) if reject_reason else "Unknown rejection reason"

        self.event_service.log_trading_event(
            event_type=MarketEventType.ORDER_REJECTED,
            description=(
                f"Market order rejected: {direction.value} {abs_units} {request.instrument}"
            ),
            severity=MarketEventSeverity.ERROR,
            user=self.account.user,
            account=self.account,
            instrument=request.instrument,
            details={
                "instrument": request.instrument,
                "order_type": OrderType.MARKET.value,
                "direction": direction.value,
                "units": str(abs_units),
                "reject_reason": reject_reason_str,
            },
        )

        raise OandaAPIError(f"Market order rejected: {reject_reason_str}")

    def create_stop_order(self, request: StopOrderRequest) -> StopOrder:
        direction = OrderDirection.LONG if request.units > 0 else OrderDirection.SHORT
        abs_units = abs(request.units)

        order_request = {
            "instrument": request.instrument,
            "units": int(request.units),
            "order_type": OrderType.STOP.value,
            "price": float(request.price),
        }
        self._validate_compliance(order_request)

        order_data: dict[str, Any] = {
            "instrument": request.instrument,
            "units": str(int(request.units)),
            "price": str(request.price),
            "type": "STOP",
            "timeInForce": "GTC",
        }
        if request.take_profit is not None:
            order_data["takeProfitOnFill"] = TakeProfitDetails(
                price=str(request.take_profit)
            ).__dict__
        if request.stop_loss is not None:
            order_data["stopLossOnFill"] = StopLossDetails(price=str(request.stop_loss)).__dict__

        response = self._execute_with_retry(order_data)
        create_tx = getattr(response, "orderCreateTransaction", None)
        order_id = getattr(create_tx, "id", "")
        created_time = self._parse_iso_datetime(getattr(create_tx, "time", None))

        self.event_service.log_trading_event(
            event_type=MarketEventType.ORDER_SUBMITTED,
            description=(
                f"Stop order submitted: {direction.value} {abs_units} {request.instrument} "
                f"@ {request.price}"
            ),
            severity=MarketEventSeverity.INFO,
            user=self.account.user,
            account=self.account,
            instrument=request.instrument,
            details={
                "order_id": order_id,
                "instrument": request.instrument,
                "order_type": OrderType.STOP.value,
                "direction": direction.value,
                "units": str(abs_units),
                "price": str(request.price),
                "take_profit": str(request.take_profit) if request.take_profit else None,
                "stop_loss": str(request.stop_loss) if request.stop_loss else None,
                "status": "pending",
            },
        )

        return StopOrder(
            order_id=str(order_id),
            instrument=str(request.instrument),
            order_type=OrderType.STOP,
            direction=direction,
            units=abs_units,
            price=request.price,
            state=OrderState.PENDING,
            time_in_force="GTC",
            create_time=created_time,
        )

    def create_oco_order(self, request: OcoOrderRequest) -> OcoOrder:
        limit_result = self.create_limit_order(
            LimitOrderRequest(
                instrument=request.instrument,
                units=request.units,
                price=request.limit_price,
            )
        )
        stop_result = self.create_stop_order(
            StopOrderRequest(
                instrument=request.instrument,
                units=request.units,
                price=request.stop_price,
            )
        )
        oco_id = f"OCO-{limit_result.order_id}-{stop_result.order_id}"
        return OcoOrder(
            order_id=oco_id,
            instrument=str(request.instrument),
            order_type=OrderType.OCO,
            direction=OrderDirection.LONG if request.units > 0 else OrderDirection.SHORT,
            units=abs(request.units),
            price=None,
            state=OrderState.PENDING,
            time_in_force=None,
            create_time=limit_result.create_time,
            limit_order=limit_result,
            stop_order=stop_result,
        )

    def get_account_details(self) -> AccountDetails:
        """
        Fetch account details from OANDA API.

        Returns:
            Dictionary with account details including balance, margin, etc.

        Raises:
            OandaAPIError: If API call fails
        """
        try:
            account_data = self.get_account_resource()

            def _read(key: str, default: Any) -> Any:
                value = account_data.get(key, default)
                return default if value is None else value

            return AccountDetails(
                account_id=str(self.account.account_id),
                currency=str(_read("currency", "USD")),
                balance=Decimal(str(_read("balance", "0"))),
                unrealized_pl=Decimal(str(_read("unrealizedPL", "0"))),
                nav=Decimal(str(_read("NAV", "0"))),
                margin_used=Decimal(str(_read("marginUsed", "0"))),
                margin_available=Decimal(str(_read("marginAvailable", "0"))),
                position_value=Decimal(str(_read("positionValue", "0"))),
                open_trade_count=int(_read("openTradeCount", 0) or 0),
                open_position_count=int(_read("openPositionCount", 0) or 0),
                pending_order_count=int(_read("pendingOrderCount", 0) or 0),
                last_transaction_id=str(_read("lastTransactionID", "")),
            )
        except Exception as e:
            logger.error(
                "Error fetching account details for %s: %s",
                self.account.account_id,
                str(e),
                exc_info=True,
            )
            raise OandaAPIError(f"Error fetching account details: {str(e)}") from e

    def get_account_hedging_enabled(self) -> bool:
        """Return whether the OANDA account has hedging enabled.

        OANDA v20 exposes this as the boolean field `hedgingEnabled` on the
        account resource. In common OANDA configurations:
        - `True`  => hedging mode (multiple trades can exist per instrument)
        - `False` => netting mode (positions are effectively aggregated per instrument)

        Raises:
            OandaAPIError: If the API call fails
        """

        try:
            account_data = self.get_account_resource()
            return bool(account_data.get("hedgingEnabled", False))
        except Exception as e:
            logger.error(
                "Error fetching account hedging mode for %s: %s",
                self.account.account_id,
                str(e),
                exc_info=True,
            )
            raise OandaAPIError(f"Error fetching account configuration: {str(e)}") from e

    def get_account_position_mode(self) -> str:
        """Return `hedging` or `netting` based on the account configuration."""

        return "hedging" if self.get_account_hedging_enabled() else "netting"

    def get_open_positions(self, instrument: str | None = None) -> list[Position]:
        """
        Fetch open positions from OANDA API.

        Args:
            instrument: Optional filter by instrument (e.g., 'EUR_USD')

        Returns:
            List of position dictionaries

        Raises:
            OandaAPIError: If API call fails
        """
        try:
            response = self.api.position.list_open(self.account.account_id)

            if response.status != 200:
                raise OandaAPIError(f"Failed to fetch positions: status {response.status}")

            positions: list[Position] = []
            oanda_positions = response.body.get("positions", [])

            for pos in oanda_positions:
                # OANDA returns positions with long and short sub-objects
                pos_instrument = pos.get("instrument", "")

                if instrument and pos_instrument != instrument:
                    continue

                # Process long position if exists
                long_data = pos.get("long", {})
                if long_data.get("units") and Decimal(str(long_data["units"])) > 0:
                    positions.append(
                        self._format_position(pos_instrument, OrderDirection.LONG, long_data)
                    )

                # Process short position if exists
                short_data = pos.get("short", {})
                if short_data.get("units") and Decimal(str(short_data["units"])) < 0:
                    positions.append(
                        self._format_position(pos_instrument, OrderDirection.SHORT, short_data)
                    )

            logger.info(
                "Fetched %d open positions from OANDA for account %s",
                len(positions),
                self.account.account_id,
            )
            return positions
        except Exception as e:
            logger.error(
                "Error fetching positions for %s: %s",
                self.account.account_id,
                str(e),
                exc_info=True,
            )
            raise OandaAPIError(f"Error fetching positions: {str(e)}") from e

    def get_open_trades(self, instrument: str | None = None) -> list[OpenTrade]:
        """
        Fetch open trades from OANDA API.

        Trades are individual position entries, while positions are aggregated.

        Args:
            instrument: Optional filter by instrument

        Returns:
            List of trade dictionaries

        Raises:
            OandaAPIError: If API call fails
        """
        try:
            response = self.api.trade.list_open(self.account.account_id)

            if response.status != 200:
                raise OandaAPIError(f"Failed to fetch trades: status {response.status}")

            trades: list[OpenTrade] = []
            oanda_trades = response.body.get("trades", [])

            for trade in oanda_trades:
                trade_instrument = trade.get("instrument", "")

                if instrument and trade_instrument != instrument:
                    continue

                units = Decimal(str(trade.get("currentUnits", "0")))

                direction = OrderDirection.LONG if units > 0 else OrderDirection.SHORT

                trades.append(
                    OpenTrade(
                        trade_id=str(trade.get("id", "")),
                        instrument=str(trade_instrument),
                        direction=direction,
                        units=abs(units),
                        entry_price=Decimal(str(trade.get("price", "0"))),
                        unrealized_pnl=Decimal(str(trade.get("unrealizedPL", "0"))),
                        open_time=self._parse_iso_datetime(trade.get("openTime")),
                        state=str(trade.get("state", "")),
                        account_id=str(self.account.account_id),
                    )
                )
            logger.info(
                "Fetched %d open trades from OANDA for account %s",
                len(trades),
                self.account.account_id,
            )
            return trades
        except Exception as e:
            logger.error(
                "Error fetching trades for %s: %s",
                self.account.account_id,
                str(e),
                exc_info=True,
            )
            raise OandaAPIError(f"Error fetching trades: {str(e)}") from e

    def get_pending_orders(self, instrument: str | None = None) -> list[PendingOrder]:
        try:
            response = self.api.order.list_pending(self.account.account_id)
            if response.status != 200:
                raise OandaAPIError(f"Failed to fetch pending orders: status {response.status}")

            orders: list[PendingOrder] = []
            for order_data in response.body.get("orders", []):
                if instrument and order_data.get("instrument", "") != instrument:
                    continue
                order_obj = self._parse_order(order_data)
                orders.append(self._as_pending_order(order_obj))
            return orders

        except Exception as e:
            logger.error(
                "Error fetching pending orders for %s: %s",
                self.account.account_id,
                str(e),
                exc_info=True,
            )
            raise OandaAPIError(f"Error fetching pending orders: {str(e)}") from e

    def get_order_history(
        self, instrument: str | None = None, count: int = 50, state: str = "ALL"
    ) -> list[Order]:
        try:
            kwargs: dict[str, Any] = {"count": count, "state": state}
            if instrument:
                kwargs["instrument"] = instrument

            response = self.api.order.list(self.account.account_id, **kwargs)
            if response.status != 200:
                raise OandaAPIError(f"Failed to fetch order history: status {response.status}")

            orders: list[Order] = []
            for order_data in response.body.get("orders", []):
                orders.append(self._parse_order(order_data))
            return orders

        except Exception as e:
            logger.error(
                "Error fetching order history for %s: %s",
                self.account.account_id,
                str(e),
                exc_info=True,
            )
            raise OandaAPIError(f"Error fetching order history: {str(e)}") from e

    def get_order(self, order_id: str) -> Order:
        try:
            response = self.api.order.get(self.account.account_id, order_id)
            if response.status != 200:
                raise OandaAPIError(f"Failed to fetch order {order_id}: status {response.status}")
            order_data = response.body.get("order") or {}
            return self._parse_order(order_data)
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(
                "OANDA API error fetching order %s for %s: %s",
                order_id,
                self.account.account_id,
                str(e),
            )
            raise OandaAPIError(f"OANDA API error: {str(e)}") from e

    def get_transaction_history(
        self,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
        page_size: int = 100,
        transaction_type: str | None = None,
    ) -> list[Transaction]:
        try:
            kwargs: dict[str, Any] = {"pageSize": page_size}
            if from_time:
                kwargs["from"] = from_time.isoformat()
            if to_time:
                kwargs["to"] = to_time.isoformat()
            if transaction_type:
                kwargs["type"] = transaction_type

            response = self.api.transaction.list(self.account.account_id, **kwargs)
            if response.status != 200:
                raise OandaAPIError(f"Failed to fetch transactions: status {response.status}")

            transactions: list[Transaction] = []

            body = response.body or {}
            if isinstance(body, dict) and body.get("transactions"):
                for txn in body.get("transactions", []):
                    if isinstance(txn, dict):
                        transactions.append(self._parse_transaction(txn))
                return transactions

            pages = body.get("pages", []) if isinstance(body, dict) else []
            # Best-effort: fetch a few pages by parsing from/to transaction IDs out of URLs.
            for page_url in pages[:5]:
                try:
                    parsed = urlparse(str(page_url))
                    qs = parse_qs(parsed.query)
                    from_list = qs.get("from")
                    to_list = qs.get("to")
                    from_id = from_list[0] if from_list else None
                    to_id = to_list[0] if to_list else None
                    if not from_id or not to_id:
                        continue
                    page_response = self.api.transaction.range(
                        self.account.account_id,
                        **{"from": str(from_id), "to": str(to_id)},
                    )
                    if page_response.status == 200 and isinstance(page_response.body, dict):
                        for txn in page_response.body.get("transactions", []):
                            if isinstance(txn, dict):
                                transactions.append(self._parse_transaction(txn))
                except Exception as exc:  # pylint: disable=broad-exception-caught  # nosec B112
                    # Log parsing error but continue with next page
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.warning("Failed to parse transaction page: %s", exc)
                    continue
            return transactions
        except Exception as e:
            logger.error(
                "Error fetching transactions for %s: %s",
                self.account.account_id,
                str(e),
                exc_info=True,
            )
            raise OandaAPIError(f"Error fetching transactions: {str(e)}") from e

    def stream_pricing_ticks(
        self,
        instruments: list[str] | str,
        *,
        snapshot: bool = True,
        include_heartbeats: bool = False,
    ) -> Iterator[TickData]:
        instruments_param = instruments if isinstance(instruments, str) else ",".join(instruments)

        response = self.stream_api.pricing.stream(
            self.account.account_id,
            snapshot=snapshot,
            instruments=instruments_param,
        )

        # For non-200 responses, v20 returns a Response with a status code
        # but no stream lines.
        if getattr(response, "status", 200) != 200:
            body = getattr(response, "body", None)
            body_preview: object | None = None
            try:
                if isinstance(body, (dict, list)):
                    body_preview = body
                elif body is not None:
                    body_preview = str(body)[:500]
            except Exception:  # pylint: disable=broad-exception-caught
                body_preview = None

            raise OandaAPIError(
                "Failed to start pricing stream: "
                f"status {getattr(response, 'status', None)} "
                f"(account_id={self.account.account_id}, "
                f"stream_hostname={self.stream_hostname or 'n/a'}, "
                f"instruments={instruments_param}) "
                + (f" body={body_preview}" if body_preview is not None else "")
            )

        # v20 returns a Response object for streams; the stream messages are
        # yielded via response.parts() as (type, obj) tuples.
        parts_iter = getattr(response, "parts", None)
        # Use parts() if available, otherwise fall back to iterating response directly
        stream_iter = parts_iter() or [] if callable(parts_iter) else response

        for part in stream_iter:
            # v20: ("pricing.ClientPrice", ClientPrice(...)) or ("pricing.PricingHeartbeat", ...)
            msg = None
            msg_type = None
            if isinstance(part, tuple) and len(part) == 2:
                msg_type, msg = part
            else:
                msg = part

            # Heartbeats: skip (this generator yields only price ticks).
            if (
                (isinstance(msg_type, str) and "Heartbeat" in msg_type)
                or getattr(msg, "type", None) == "HEARTBEAT"
                or (isinstance(msg, dict) and msg.get("type") == "HEARTBEAT")
            ):
                _ = include_heartbeats
                continue

            # Dict-style messages (older mocks).
            if isinstance(msg, dict):
                if msg.get("type") != "PRICE":
                    continue

                instrument = str(msg.get("instrument", ""))
                time_value = self._parse_iso_datetime(msg.get("time"))
                if not time_value:
                    continue

                bids = msg.get("bids") or []
                asks = msg.get("asks") or []
                if not bids or not asks:
                    continue

                bid = Decimal(str(bids[0].get("price")))
                ask = Decimal(str(asks[0].get("price")))
                mid = (bid + ask) / Decimal("2")
                yield TickData(
                    instrument=instrument,
                    timestamp=time_value,
                    bid=bid,
                    ask=ask,
                    mid=mid,
                )
                continue

            # v20 ClientPrice object messages.
            instrument = str(getattr(msg, "instrument", "") or "")
            if not instrument:
                continue

            time_raw = getattr(msg, "time", None)
            if isinstance(time_raw, datetime):
                time_value = time_raw
                if time_value.tzinfo is None:
                    time_value = time_value.replace(tzinfo=UTC)
            else:
                time_value = self._parse_iso_datetime(time_raw)
                if not time_value:
                    continue

            bids = getattr(msg, "bids", None) or []
            asks = getattr(msg, "asks", None) or []
            if not bids or not asks:
                continue

            bid_price = getattr(bids[0], "price", None)
            ask_price = getattr(asks[0], "price", None)
            if bid_price is None or ask_price is None:
                continue

            bid = Decimal(str(bid_price))
            ask = Decimal(str(ask_price))
            mid = (bid + ask) / Decimal("2")
            yield TickData(
                instrument=instrument,
                timestamp=time_value,
                bid=bid,
                ask=ask,
                mid=mid,
            )

    @staticmethod
    def _as_pending_order(order: Order) -> PendingOrder:
        return PendingOrder(
            order_id=order.order_id,
            instrument=order.instrument,
            order_type=order.order_type,
            direction=order.direction,
            units=order.units,
            price=order.price,
            state=OrderState.PENDING,
            time_in_force=order.time_in_force,
            create_time=order.create_time,
            fill_time=order.fill_time,
            cancel_time=order.cancel_time,
        )

    def _execute_with_retry(self, order_data: dict[str, Any]) -> Any:
        last_error: str | None = None

        for attempt in range(self.max_retries):
            try:
                response = self.api.order.create(self.account.account_id, order=order_data)

                if response.status in (200, 201):
                    return response

                error_details = ""
                if hasattr(response, "body") and response.body:
                    error_details = f" - {response.body}"
                elif hasattr(response, "raw_body"):
                    error_details = f" - {response.raw_body}"

                logger.warning(
                    "Order submission attempt %s failed: status %s%s",
                    attempt + 1,
                    response.status,
                    error_details,
                )
                last_error = f"API returned status {response.status}{error_details}"

            except Exception as exc:  # pylint: disable=broad-exception-caught
                logger.warning("Order submission attempt %s failed: %s", attempt + 1, exc)
                last_error = str(exc)

            if attempt < self.max_retries - 1:
                time.sleep(self.retry_delay)

        error_msg = f"Order submission failed after {self.max_retries} attempts: {last_error}"
        logger.error("Order submission failed after %s attempts: %s", self.max_retries, last_error)

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

        raise OandaAPIError(error_msg)

    def _format_position(
        self, instrument: str, direction: OrderDirection, pos_data: dict[str, Any]
    ) -> Position:
        """
        Format OANDA position data to standard format.

        Args:
            instrument: Currency pair
            direction: 'long' or 'short'
            pos_data: OANDA position data

        Returns:
            Formatted position dictionary
        """
        units = Decimal(str(pos_data.get("units", "0")))
        avg_price = Decimal(str(pos_data.get("averagePrice", "0")))
        unrealized_pl = Decimal(str(pos_data.get("unrealizedPL", "0")))

        # Get trade IDs for this position
        trade_ids = pos_data.get("tradeIDs", [])

        return Position(
            instrument=instrument,
            direction=direction,
            units=abs(units),
            average_price=avg_price,
            unrealized_pnl=unrealized_pl,
            trade_ids=[str(t) for t in trade_ids],
            account_id=str(self.account.account_id),
        )

    def _parse_iso_datetime(self, value: Any) -> datetime | None:
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        value_str = str(value)
        # OANDA timestamps commonly end with 'Z'
        if value_str.endswith("Z"):
            value_str = value_str[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(value_str)
        except ValueError:
            return None

    def _parse_order(self, order: dict[str, Any]) -> Order:
        raw_type = str(order.get("type", "")).upper()
        order_type = {
            "MARKET": OrderType.MARKET,
            "LIMIT": OrderType.LIMIT,
            "STOP": OrderType.STOP,
        }.get(raw_type, OrderType.MARKET)

        units_signed = self._to_decimal(order.get("units")) or Decimal("0")
        direction = (
            OrderDirection.LONG
            if units_signed > 0
            else OrderDirection.SHORT
            if units_signed < 0
            else OrderDirection.LONG
        )
        units_abs = abs(units_signed)
        price = self._to_decimal(order.get("price"))

        create_time = self._parse_iso_datetime(order.get("createTime"))
        fill_time = self._parse_iso_datetime(order.get("filledTime"))
        cancel_time = self._parse_iso_datetime(order.get("cancelledTime"))
        state = OrderState.from_raw(order.get("state"))
        time_in_force = str(order.get("timeInForce")) if order.get("timeInForce") else None

        order_id = str(order.get("id", ""))
        instrument = str(order.get("instrument", ""))

        if order_type == OrderType.LIMIT:
            return LimitOrder(
                order_id=order_id,
                instrument=instrument,
                order_type=order_type,
                direction=direction,
                units=units_abs,
                price=price,
                state=state,
                time_in_force=time_in_force,
                create_time=create_time,
                fill_time=fill_time,
                cancel_time=cancel_time,
            )
        if order_type == OrderType.STOP:
            return StopOrder(
                order_id=order_id,
                instrument=instrument,
                order_type=order_type,
                direction=direction,
                units=units_abs,
                price=price,
                state=state,
                time_in_force=time_in_force,
                create_time=create_time,
                fill_time=fill_time,
                cancel_time=cancel_time,
            )
        return MarketOrder(
            order_id=order_id,
            instrument=instrument,
            order_type=order_type,
            direction=direction,
            units=units_abs,
            price=price,
            state=state,
            time_in_force=time_in_force,
            create_time=create_time,
            fill_time=fill_time,
            cancel_time=cancel_time,
        )

    def _parse_transaction(self, txn: dict[str, Any]) -> Transaction:
        return Transaction(
            transaction_id=str(txn.get("id", "")),
            time=self._parse_iso_datetime(txn.get("time")),
            type=str(txn.get("type", "")),
            instrument=str(txn.get("instrument")) if txn.get("instrument") else None,
            units=self._to_decimal(txn.get("units")),
            price=self._to_decimal(txn.get("price")),
            pl=self._to_decimal(txn.get("pl")),
            account_balance=self._to_decimal(txn.get("accountBalance")),
        )

    def _to_decimal(self, value: Any) -> Decimal | None:
        if value is None:
            return None
        value_str = str(value)
        if value_str == "":
            return None
        try:
            return Decimal(value_str)
        except Exception:  # pylint: disable=broad-exception-caught
            return None

    def _validate_compliance(self, order_request: dict[str, Any]) -> None:
        is_valid, error_message = self.compliance_manager.validate_order(order_request)

        if not is_valid:
            self.event_service.log_security_event(
                event_type=MarketEventType.COMPLIANCE_VIOLATION,
                description=f"Order rejected: {error_message}",
                severity=MarketEventSeverity.WARNING,
                user=self.account.user,
                account=self.account,
                instrument=str(order_request.get("instrument") or "") or None,
                details={
                    "account_id": self.account.account_id,
                    "order_request": order_request,
                    "violation_reason": error_message,
                    "jurisdiction": self.account.jurisdiction,
                },
            )

            raise ComplianceViolationError(error_message)
