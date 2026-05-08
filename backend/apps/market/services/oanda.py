"""
OANDA API direct client for fetching orders, positions, and account details.

This module provides direct API calls to OANDA without database caching,
replacing the sync-based approach with real-time API queries.
"""

from __future__ import annotations

import secrets
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from logging import Logger, getLogger
from typing import Any
from urllib.parse import parse_qs, urlparse

import v20
from django.conf import settings
from v20.transaction import StopLossDetails, TakeProfitDetails

from apps.market.enums import MarketEventSeverity, MarketEventType
from apps.market.models import OandaAccounts, TickData
from apps.market.services.broker_order_guard import BrokerOrderGuard, BrokerOrderGuardError
from apps.market.services.compliance import ComplianceService, ComplianceViolationError
from apps.market.services.events import MarketEventService
from apps.market.services.oanda_clients import (
    OandaAccountClient,
    OandaContextFactory,
    OandaOrderClient,
    OandaPositionClient,
    OandaPricingStreamClient,
    OandaTradeClient,
    OandaTransactionClient,
)
from apps.market.services.oanda_dry_run import OandaDryRunSimulator
from apps.market.services import oanda_parsing
from apps.market.services.oanda_transport import OandaOrderTransport
from apps.market.services.oanda_types import (
    AccountDetails,
    CancelledOrder,
    LimitOrder,
    LimitOrderRequest,
    MarketOrder,
    MarketOrderRequest,
    OandaAPIError,
    OcoOrder,
    OcoOrderRequest,
    OpenTrade,
    Order,
    OrderDirection,
    OrderState,
    OrderType,
    PendingOrder,
    Position,
    StopOrder,
    StopOrderRequest,
    StreamMessageType,
    Transaction,
)

logger: Logger = getLogger(name=__name__)

__all__ = [
    "AccountDetails",
    "CancelledOrder",
    "LimitOrder",
    "LimitOrderRequest",
    "MarketOrder",
    "MarketOrderRequest",
    "OandaAPIError",
    "OandaService",
    "OcoOrder",
    "OcoOrderRequest",
    "OpenTrade",
    "Order",
    "OrderDirection",
    "OrderState",
    "OrderType",
    "PendingOrder",
    "Position",
    "StopOrder",
    "StopOrderRequest",
    "StreamMessageType",
    "Transaction",
]


class OandaService:
    """
    Direct client for OANDA v20 API.

    Provides methods to fetch orders, positions, and account details
    directly from OANDA without database caching.

    Supports dry-run mode for backtesting and simulation.
    """

    def __init__(self, account: OandaAccounts | None = None, dry_run: bool = False):
        """
        Initialize OANDA API client.

        Args:
            account: OandaAccounts instance with API credentials (optional for dry_run mode)
            dry_run: If True, simulate API calls without making actual requests
        """
        self.account = account
        self.dry_run = dry_run
        self.max_retries = 3
        self.retry_delay = 0.5  # seconds
        self.max_retry_delay = 5.0  # seconds
        self.event_service = MarketEventService()
        self.order_guard = BrokerOrderGuard()
        self.response_parser = oanda_parsing.OandaResponseParser()
        self._account_resource_cache: dict[str, Any] | None = None
        self.context_factory = OandaContextFactory(v20_module=v20, settings_module=settings)
        self.account_client = OandaAccountClient(self)
        self.order_client = OandaOrderClient(self)
        self.trade_client = OandaTradeClient(self)
        self.position_client = OandaPositionClient(self)
        self.transaction_client = OandaTransactionClient(self)
        self.pricing_stream_client = OandaPricingStreamClient(self)

        self._dry_run_simulator = OandaDryRunSimulator(account)
        # Backward-compatible attribute used by older tests and debug tools.
        self._dry_run_positions = self._dry_run_simulator.positions

        # Only initialize API connections if we have an account
        # In dry-run mode without an account, we skip all API calls
        if account is not None:
            rest_hostname = str(account.api_hostname)
            stream_hostname = self.context_factory.stream_hostname(rest_hostname)

            self.api = self.context_factory.create_rest_context(account)

            # v20 Context uses a single hostname for both REST and streaming.
            # OANDA streams live on a different hostname (stream-*) than REST (api-*).
            # If we use the REST host for pricing.stream, OANDA returns 404.
            self.stream_hostname = stream_hostname
            self.stream_api = self.context_factory.create_stream_context(account)

            self.compliance_manager = ComplianceService(account)

            logger.info(
                "OANDA service initialized (account_id=%s, api_hostname=%s, stream_hostname=%s, dry_run=%s)",
                str(getattr(account, "account_id", "")),
                rest_hostname,
                stream_hostname,
                dry_run,
            )
        else:
            # No account - dry-run only mode
            self.api = None
            self.stream_api = None
            self.stream_hostname = None
            self.compliance_manager = None

            logger.info(
                "OANDA service initialized in dry-run mode without account (simulation only)"
            )

    @staticmethod
    def _to_stream_hostname(hostname: str) -> str:
        return OandaContextFactory.stream_hostname(hostname)

    @staticmethod
    def _make_jsonable(value: Any) -> Any:
        return oanda_parsing.OANDA_RESPONSE_PARSER.make_jsonable(value)

    @staticmethod
    def make_jsonable(value: Any) -> Any:
        return OandaService._make_jsonable(value)

    @staticmethod
    def _response_field(response: Any, field_name: str) -> Any:
        return oanda_parsing.OANDA_RESPONSE_PARSER.response_field(response, field_name)

    @staticmethod
    def _object_field(value: Any, field_name: str) -> Any:
        return oanda_parsing.OANDA_RESPONSE_PARSER.object_field(value, field_name)

    @staticmethod
    def _account_object_to_dict(account_data: Any) -> dict[str, Any]:
        return oanda_parsing.OANDA_RESPONSE_PARSER.account_object_to_dict(account_data)

    def get_account_resource(self, *, refresh: bool = False) -> dict[str, Any]:
        """Fetch the raw OANDA account resource as a dict.

        This is used to expose broker flags/parameters (e.g. `hedgingEnabled`) and
        to avoid repeated network calls by caching within this service instance.
        """
        return self.account_client.get_resource(refresh=refresh)

    def cancel_order(self, order: Order) -> CancelledOrder:
        return self.order_client.cancel_order(order)

    def _cancel_order_impl(self, order: Order) -> CancelledOrder:
        assert self.api is not None, "API client not initialized"
        assert self.account is not None, "Account not initialized"

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

        except OandaAPIError:
            raise
        except Exception as e:
            account_id = self.account.account_id if self.account else "unknown"
            logger.error(
                "Error cancelling order %s for %s: %s",
                order.order_id,
                account_id,
                str(e),
                exc_info=True,
            )
            raise OandaAPIError(
                "Error cancelling order",
                internal_detail=str(e),
            ) from e

    def close_trade(self, trade: OpenTrade, units: Decimal | None = None) -> MarketOrder:
        return self.trade_client.close_trade(trade=trade, units=units)

    def _close_trade_impl(self, trade: OpenTrade, units: Decimal | None = None) -> MarketOrder:
        assert self.api is not None, "API client not initialized"
        assert self.account is not None, "Account not initialized"

        try:
            self._validate_broker_order_guard(
                instrument=trade.instrument,
                units=trade.units if units is None else units,
            )
            kwargs: dict[str, Any] = {"units": str(units) if units else "ALL"}
            response = self.api.trade.close(self.account.account_id, trade.trade_id, **kwargs)

            if response.status not in (200, 201):
                raise OandaAPIError(
                    f"Failed to close trade {trade.trade_id}: status {response.status}"
                )

            fill_tx = self._response_field(response, "orderFillTransaction")

            fill_time = self._parse_iso_datetime(self._object_field(fill_tx, "time"))
            fill_price = self._to_decimal(self._object_field(fill_tx, "price"))
            order_id_raw = self._object_field(fill_tx, "id")
            order_id = str(order_id_raw) if order_id_raw is not None else ""

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

        except OandaAPIError:
            raise
        except Exception as e:
            account_id = self.account.account_id if self.account else "unknown"
            logger.error(
                "Error closing trade %s for %s: %s",
                trade.trade_id,
                account_id,
                str(e),
                exc_info=True,
            )
            raise OandaAPIError(
                "Error closing trade",
                internal_detail=str(e),
            ) from e

    def close_position(
        self,
        position: Position,
        units: Decimal | None = None,
        override_price: Decimal | None = None,
    ) -> MarketOrder:
        return self.position_client.close_position(
            position=position,
            units=units,
            override_price=override_price,
        )

    def _close_position_impl(
        self,
        position: Position,
        units: Decimal | None = None,
        override_price: Decimal | None = None,
    ) -> MarketOrder:
        """
        Close an open position for an instrument.

        OANDA positions are aggregated by instrument. This uses the
        `/v3/accounts/{accountID}/positions/{instrument}/close` endpoint under the hood.

        Args:
            position: A Position returned by get_open_positions().
            units: Optional number of units to close (positive Decimal). If omitted, closes ALL.
            override_price: Optional price to use for dry-run close instead of latest tick data.

        Returns:
            MarketOrder representing the closeout fill.
        """
        # Dry-run mode: simulate position close
        if self.dry_run:
            return self._dry_run_simulator.simulate_position_close(
                position,
                units,
                override_price=override_price,
            )

        # Require account for live trading
        if self.account is None:
            raise OandaAPIError("Account required for live trading")
        if self.api is None:
            raise OandaAPIError("API client not initialized")

        try:
            if units is not None:
                if units <= 0:
                    raise ValueError("units must be positive")
                if units > position.units:
                    raise ValueError("units cannot exceed open position units")
            self._validate_broker_order_guard(
                instrument=position.instrument,
                units=position.units if units is None else units,
            )

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

            if position.direction == OrderDirection.LONG:
                fill_tx = self._response_field(response, "longOrderFillTransaction")
            else:
                fill_tx = self._response_field(response, "shortOrderFillTransaction")

            fill_time = self._parse_iso_datetime(self._object_field(fill_tx, "time"))
            fill_price = self._to_decimal(self._object_field(fill_tx, "price"))
            order_id_raw = self._object_field(fill_tx, "id")
            order_id = str(order_id_raw) if order_id_raw is not None else ""

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

        except OandaAPIError:
            raise
        except Exception as e:
            logger.error(
                "Error closing position %s for %s: %s",
                position.instrument,
                self.account.account_id,
                str(e),
                exc_info=True,
            )
            raise OandaAPIError(
                "Error closing position",
                internal_detail=str(e),
            ) from e

    def _simulate_position_close(
        self,
        position: Position,
        units: Decimal | None = None,
        override_price: Decimal | None = None,
    ) -> MarketOrder:
        """Backward-compatible wrapper around the dry-run simulator."""
        return self._dry_run_simulator.simulate_position_close(
            position,
            units,
            override_price=override_price,
        )

    def create_limit_order(self, request: LimitOrderRequest) -> LimitOrder:
        return self.order_client.create_limit_order(request)

    def _create_limit_order_impl(self, request: LimitOrderRequest) -> LimitOrder:
        assert self.account is not None, "Account not initialized"

        direction = OrderDirection.LONG if request.units > 0 else OrderDirection.SHORT
        abs_units = abs(request.units)
        self._validate_broker_order_guard(
            instrument=request.instrument,
            units=request.units,
        )

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
        create_tx = self._response_field(response, "orderCreateTransaction")
        order_id_raw = self._object_field(create_tx, "id")
        order_id = str(order_id_raw) if order_id_raw is not None else ""
        created_time = self._parse_iso_datetime(self._object_field(create_tx, "time"))

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

    def create_market_order(
        self,
        request: MarketOrderRequest,
        override_price: Decimal | None = None,
    ) -> MarketOrder:
        return self.order_client.create_market_order(
            request,
            override_price=override_price,
        )

    def _create_market_order_impl(
        self,
        request: MarketOrderRequest,
        override_price: Decimal | None = None,
    ) -> MarketOrder:
        direction = OrderDirection.LONG if request.units > 0 else OrderDirection.SHORT
        abs_units = abs(request.units)

        # Dry-run mode: simulate order execution
        if self.dry_run:
            return self._dry_run_simulator.simulate_market_order(
                request, direction, abs_units, override_price=override_price
            )

        # Require account for live trading
        if self.account is None:
            raise OandaAPIError("Account required for live trading")
        self._validate_broker_order_guard(
            instrument=request.instrument,
            units=request.units,
        )

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

        fill_tx = self._response_field(response, "orderFillTransaction")
        create_tx = self._response_field(response, "orderCreateTransaction")
        reject_tx = self._response_field(response, "orderRejectTransaction")

        if fill_tx:
            order_id = (
                self._object_field(fill_tx, "id") or self._object_field(create_tx, "id") or ""
            )
            fill_price_raw = self._object_field(fill_tx, "price")
            fill_price = Decimal(str(fill_price_raw)) if fill_price_raw is not None else None
            fill_time = self._parse_iso_datetime(self._object_field(fill_tx, "time"))

            # Extract OANDA trade ID from the fill transaction
            trade_id: str | None = None
            trade_opened = self._object_field(fill_tx, "tradeOpened")
            if trade_opened:
                trade_id_raw = self._object_field(trade_opened, "tradeID")
                trade_id = str(trade_id_raw) if trade_id_raw not in (None, "") else None

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
                    "trade_id": trade_id,
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
                trade_id=trade_id,
            )

        reject_reason = self._object_field(reject_tx, "rejectReason")
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
        return self.order_client.create_stop_order(request)

    def _create_stop_order_impl(self, request: StopOrderRequest) -> StopOrder:
        assert self.account is not None, "Account not initialized"

        direction = OrderDirection.LONG if request.units > 0 else OrderDirection.SHORT
        abs_units = abs(request.units)
        self._validate_broker_order_guard(
            instrument=request.instrument,
            units=request.units,
        )

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
        create_tx = self._response_field(response, "orderCreateTransaction")
        order_id_raw = self._object_field(create_tx, "id")
        order_id = str(order_id_raw) if order_id_raw is not None else ""
        created_time = self._parse_iso_datetime(self._object_field(create_tx, "time"))

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
        return self.order_client.create_oco_order(request)

    def _create_oco_order_impl(self, request: OcoOrderRequest) -> OcoOrder:
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
        return self.account_client.get_details()

    def _get_account_details_impl(self) -> AccountDetails:
        """
        Fetch account details from OANDA API.

        Returns:
            Dictionary with account details including balance, margin, etc.

        Raises:
            OandaAPIError: If API call fails
        """
        assert self.account is not None, "Account not initialized"

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
        except OandaAPIError:
            raise
        except Exception as e:
            logger.error(
                "Error fetching account details for %s: %s",
                self.account.account_id,
                str(e),
                exc_info=True,
            )
            raise OandaAPIError(
                "Error fetching account details",
                internal_detail=str(e),
            ) from e

    def get_account_hedging_enabled(self) -> bool:
        return self.account_client.get_hedging_enabled()

    def _get_account_hedging_enabled_impl(self) -> bool:
        """Return whether the OANDA account has hedging enabled.

        OANDA v20 exposes this as the boolean field `hedgingEnabled` on the
        account resource. In common OANDA configurations:
        - `True`  => hedging mode (multiple trades can exist per instrument)
        - `False` => netting mode (positions are effectively aggregated per instrument)

        Raises:
            OandaAPIError: If the API call fails
        """
        assert self.account is not None, "Account not initialized"

        try:
            account_data = self.get_account_resource()
            return bool(account_data.get("hedgingEnabled", False))
        except OandaAPIError:
            raise
        except Exception as e:
            account_id = self.account.account_id if self.account else "unknown"
            logger.error(
                "Error fetching account hedging mode for %s: %s",
                account_id,
                str(e),
                exc_info=True,
            )
            raise OandaAPIError(
                "Error fetching account configuration",
                internal_detail=str(e),
            ) from e

    def get_account_position_mode(self) -> str:
        return self.account_client.get_position_mode()

    def _get_account_position_mode_impl(self) -> str:
        """Return `hedging` or `netting` based on the account configuration."""

        return "hedging" if self.get_account_hedging_enabled() else "netting"

    def get_open_positions(self, instrument: str | None = None) -> list[Position]:
        return self.position_client.get_open_positions(instrument=instrument)

    def _get_open_positions_impl(self, instrument: str | None = None) -> list[Position]:
        """
        Fetch open positions from OANDA API.

        Args:
            instrument: Optional filter by instrument (e.g., 'EUR_USD')

        Returns:
            List of position dictionaries

        Raises:
            OandaAPIError: If API call fails
        """
        assert self.api is not None, "API client not initialized"
        assert self.account is not None, "Account not initialized"

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
        except OandaAPIError:
            raise
        except Exception as e:
            logger.error(
                "Error fetching positions for %s: %s",
                self.account.account_id,
                str(e),
                exc_info=True,
            )
            raise OandaAPIError(
                "Error fetching positions",
                internal_detail=str(e),
            ) from e

    def get_trades(
        self,
        instrument: str | None = None,
        *,
        state: str = "OPEN",
        count: int = 500,
    ) -> list[OpenTrade]:
        return self.trade_client.get_trades(
            instrument=instrument,
            state=state,
            count=count,
        )

    def _get_trades_impl(
        self,
        instrument: str | None = None,
        *,
        state: str = "OPEN",
        count: int = 500,
    ) -> list[OpenTrade]:
        """
        Fetch trades from OANDA API.

        Trades are individual position entries, while positions are aggregated.

        Args:
            instrument: Optional filter by instrument
            state: Trade state filter to send to OANDA.
            count: Maximum number of trades to request when using history.

        Returns:
            List of trade dictionaries

        Raises:
            OandaAPIError: If API call fails
        """
        assert self.api is not None, "API client not initialized"
        assert self.account is not None, "Account not initialized"

        try:
            normalized_state = state.strip().upper() if state else "OPEN"
            if normalized_state == "OPEN":
                response = self.api.trade.list_open(self.account.account_id)
            else:
                response = self.api.trade.list(
                    self.account.account_id,
                    state=normalized_state,
                    count=count,
                )

            if response.status != 200:
                raise OandaAPIError(f"Failed to fetch trades: status {response.status}")

            trades: list[OpenTrade] = []
            oanda_trades = response.body.get("trades", [])

            for trade in oanda_trades:
                trade_instrument = self._object_field(trade, "instrument") or ""

                if instrument and trade_instrument != instrument:
                    continue

                units = Decimal(str(self._object_field(trade, "currentUnits") or "0"))

                direction = OrderDirection.LONG if units > 0 else OrderDirection.SHORT

                trades.append(
                    OpenTrade(
                        trade_id=str(self._object_field(trade, "id") or ""),
                        instrument=str(trade_instrument),
                        direction=direction,
                        units=abs(units),
                        entry_price=Decimal(str(self._object_field(trade, "price") or "0")),
                        unrealized_pnl=Decimal(
                            str(self._object_field(trade, "unrealizedPL") or "0")
                        ),
                        open_time=self._parse_iso_datetime(self._object_field(trade, "openTime")),
                        state=str(self._object_field(trade, "state") or ""),
                        account_id=str(self.account.account_id),
                        close_time=self._parse_iso_datetime(self._object_field(trade, "closeTime")),
                        realized_pnl=self._to_decimal(self._object_field(trade, "realizedPL")),
                    )
                )
            logger.info(
                "Fetched %d trades from OANDA for account %s (state=%s)",
                len(trades),
                self.account.account_id,
                normalized_state,
            )
            return trades
        except OandaAPIError:
            raise
        except Exception as e:
            logger.error(
                "Error fetching trades for %s: %s",
                self.account.account_id,
                str(e),
                exc_info=True,
            )
            raise OandaAPIError(
                "Error fetching trades",
                internal_detail=str(e),
            ) from e

    def get_open_trades(self, instrument: str | None = None) -> list[OpenTrade]:
        return self.trade_client.get_open_trades(instrument=instrument)

    def _get_open_trades_impl(self, instrument: str | None = None) -> list[OpenTrade]:
        return self.get_trades(instrument=instrument, state="OPEN")

    def get_pending_orders(self, instrument: str | None = None) -> list[PendingOrder]:
        return self.order_client.get_pending_orders(instrument=instrument)

    def _get_pending_orders_impl(self, instrument: str | None = None) -> list[PendingOrder]:
        assert self.api is not None, "API client not initialized"
        assert self.account is not None, "Account not initialized"

        try:
            response = self.api.order.list_pending(self.account.account_id)
            if response.status != 200:
                raise OandaAPIError(f"Failed to fetch pending orders: status {response.status}")

            orders: list[PendingOrder] = []
            for order_data in response.body.get("orders", []):
                if instrument and self._object_field(order_data, "instrument") != instrument:
                    continue
                order_obj = self._parse_order(order_data)
                orders.append(self._as_pending_order(order_obj))
            return orders

        except OandaAPIError:
            raise
        except Exception as e:
            logger.error(
                "Error fetching pending orders for %s: %s",
                self.account.account_id,
                str(e),
                exc_info=True,
            )
            raise OandaAPIError(
                "Error fetching pending orders",
                internal_detail=str(e),
            ) from e

    def get_order_history(
        self, instrument: str | None = None, count: int = 50, state: str = "ALL"
    ) -> list[Order]:
        return self.order_client.get_order_history(
            instrument=instrument,
            count=count,
            state=state,
        )

    def _get_order_history_impl(
        self, instrument: str | None = None, count: int = 50, state: str = "ALL"
    ) -> list[Order]:
        assert self.api is not None, "API client not initialized"
        assert self.account is not None, "Account not initialized"

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

        except OandaAPIError:
            raise
        except Exception as e:
            logger.error(
                "Error fetching order history for %s: %s",
                self.account.account_id,
                str(e),
                exc_info=True,
            )
            raise OandaAPIError(
                "Error fetching order history",
                internal_detail=str(e),
            ) from e

    def get_order(self, order_id: str) -> Order:
        return self.order_client.get_order(order_id)

    def _get_order_impl(self, order_id: str) -> Order:
        assert self.api is not None, "API client not initialized"
        assert self.account is not None, "Account not initialized"

        try:
            response = self.api.order.get(self.account.account_id, order_id)
            if response.status != 200:
                raise OandaAPIError(f"Failed to fetch order {order_id}: status {response.status}")
            order_data = response.body.get("order") or {}
            return self._parse_order(order_data)
        except OandaAPIError:
            raise
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(
                "OANDA API error fetching order %s for %s: %s",
                order_id,
                self.account.account_id,
                str(e),
            )
            raise OandaAPIError(
                "OANDA API error",
                internal_detail=str(e),
            ) from e

    def get_transaction_history(
        self,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
        page_size: int = 100,
        transaction_type: str | None = None,
    ) -> list[Transaction]:
        return self.transaction_client.get_transaction_history(
            from_time=from_time,
            to_time=to_time,
            page_size=page_size,
            transaction_type=transaction_type,
        )

    def _get_transaction_history_impl(
        self,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
        page_size: int = 100,
        transaction_type: str | None = None,
    ) -> list[Transaction]:
        assert self.api is not None, "API client not initialized"
        assert self.account is not None, "Account not initialized"

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
        except OandaAPIError:
            raise
        except Exception as e:
            account_id = self.account.account_id if self.account else "unknown"
            logger.error(
                "Error fetching transactions for %s: %s",
                account_id,
                str(e),
                exc_info=True,
            )
            raise OandaAPIError(
                "Error fetching transactions",
                internal_detail=str(e),
            ) from e

    def stream_pricing_ticks(
        self,
        instruments: list[str] | str,
        *,
        snapshot: bool = True,
        include_heartbeats: bool = False,
    ) -> Iterator[TickData]:
        return self.pricing_stream_client.stream_pricing_ticks(
            instruments,
            snapshot=snapshot,
            include_heartbeats=include_heartbeats,
        )

    def _stream_pricing_ticks_impl(
        self,
        instruments: list[str] | str,
        *,
        snapshot: bool = True,
        include_heartbeats: bool = False,
    ) -> Iterator[TickData]:
        assert self.stream_api is not None, "Stream API client not initialized"
        assert self.account is not None, "Account not initialized"

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
        return oanda_parsing.OANDA_RESPONSE_PARSER.as_pending_order(order)

    def _execute_with_retry(self, order_data: dict[str, Any]) -> Any:
        assert self.api is not None, "API client not initialized"
        assert self.account is not None, "Account not initialized"
        transport = OandaOrderTransport(
            api=self.api,
            account=self.account,
            event_service=self.event_service,
            logger=logger,
            max_retries=self.max_retries,
            retry_delay=self.retry_delay,
            max_retry_delay=self.max_retry_delay,
            error_class=OandaAPIError,
            sleep_func=time.sleep,
            randbelow_func=secrets.randbelow,
        )
        return transport.execute_order(order_data)

    def _format_position(
        self, instrument: str, direction: OrderDirection, pos_data: dict[str, Any]
    ) -> Position:
        return self.response_parser.format_position(
            instrument=instrument,
            direction=direction,
            pos_data=pos_data,
            account_id=str(self.account.account_id) if self.account else "",
        )

    def _parse_iso_datetime(self, value: Any) -> datetime | None:
        return self.response_parser.parse_iso_datetime(value)

    def _parse_order(self, order: Any) -> Order:
        return self.response_parser.parse_order(order)

    def _parse_transaction(self, txn: dict[str, Any]) -> Transaction:
        return self.response_parser.parse_transaction(txn)

    def _to_decimal(self, value: Any) -> Decimal | None:
        return self.response_parser.to_decimal(value)

    def _validate_compliance(self, order_request: dict[str, Any]) -> None:
        # Skip compliance checks if no account (dry-run only mode)
        if self.account is None or self.compliance_manager is None:
            return

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

    def _validate_broker_order_guard(self, *, instrument: str, units: Decimal) -> None:
        try:
            self.order_guard.validate_order(
                account=self.account,
                dry_run=self.dry_run,
                instrument=instrument,
                units=units,
            )
        except BrokerOrderGuardError as exc:
            self._log_order_guard_rejection(instrument=instrument, units=units, reason=str(exc))
            raise OandaAPIError(str(exc), internal_detail=str(exc)) from exc

    def _log_order_guard_rejection(
        self,
        *,
        instrument: str,
        units: Decimal,
        reason: str,
    ) -> None:
        if self.account is None:
            return

        try:
            self.event_service.log_security_event(
                event_type=MarketEventType.COMPLIANCE_VIOLATION,
                description=f"Broker order blocked by safety guardrails: {reason}",
                severity=MarketEventSeverity.WARNING,
                user=self.account.user,
                account=self.account,
                instrument=instrument,
                details={
                    "account_id": self.account.account_id,
                    "instrument": instrument,
                    "units": str(units),
                    "violation_reason": reason,
                },
            )
        except Exception:  # pragma: no cover - best-effort audit logging
            logger.warning(
                "Failed to log broker order guard rejection for account %s",
                getattr(self.account, "account_id", "unknown"),
                exc_info=True,
            )
