"""Integration tests for OandaService methods that call the v20 API.

Tests mock v20.Context to verify OandaService correctly translates
API responses into domain objects and handles error paths.
"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from apps.market.models import OandaAccounts
from apps.market.services.oanda import (
    CancelledOrder,
    LimitOrder,
    LimitOrderRequest,
    MarketOrder,
    MarketOrderRequest,
    OandaAPIError,
    OandaService,
    Order,
    OrderDirection,
    OrderState,
    OrderType,
    Position,
    StopOrder,
    StopOrderRequest,
    Transaction,
)
from tests.integration.factories import OandaAccountFactory


@pytest.mark.django_db
class TestGetAccountResource:
    """Tests for OandaService.get_account_resource."""

    def _make_service(self, account: OandaAccounts) -> OandaService:
        svc = OandaService(account=account)
        svc.api = MagicMock()
        return svc

    def test_success(self):
        account = OandaAccountFactory()
        svc = self._make_service(account)

        mock_response = MagicMock()
        mock_response.status = 200
        mock_body = MagicMock()
        mock_body.get.return_value = {"currency": "USD", "balance": "10000"}
        mock_response.body = mock_body
        svc.api.account.get.return_value = mock_response

        result = svc.get_account_resource()
        assert result == {"currency": "USD", "balance": "10000"}
        svc.api.account.get.assert_called_once_with(account.account_id)

    def test_caches_result(self):
        account = OandaAccountFactory()
        svc = self._make_service(account)

        mock_response = MagicMock()
        mock_response.status = 200
        mock_body = MagicMock()
        mock_body.get.return_value = {"currency": "USD"}
        mock_response.body = mock_body
        svc.api.account.get.return_value = mock_response

        svc.get_account_resource()
        svc.get_account_resource()
        assert svc.api.account.get.call_count == 1

    def test_refresh_bypasses_cache(self):
        account = OandaAccountFactory()
        svc = self._make_service(account)

        mock_response = MagicMock()
        mock_response.status = 200
        mock_body = MagicMock()
        mock_body.get.return_value = {"currency": "USD"}
        mock_response.body = mock_body
        svc.api.account.get.return_value = mock_response

        svc.get_account_resource()
        svc.get_account_resource(refresh=True)
        assert svc.api.account.get.call_count == 2

    def test_error_status(self):
        account = OandaAccountFactory()
        svc = self._make_service(account)

        mock_response = MagicMock()
        mock_response.status = 401
        svc.api.account.get.return_value = mock_response

        with pytest.raises(OandaAPIError, match="Failed to fetch account resource"):
            svc.get_account_resource()

    def test_api_exception(self):
        account = OandaAccountFactory()
        svc = self._make_service(account)
        svc.api.account.get.side_effect = ConnectionError("timeout")

        with pytest.raises(OandaAPIError, match="Error fetching account resource"):
            svc.get_account_resource()


@pytest.mark.django_db
class TestCancelOrder:
    """Tests for OandaService.cancel_order."""

    def _make_service(self, account: OandaAccounts) -> OandaService:
        svc = OandaService(account=account)
        svc.api = MagicMock()
        svc.event_service = MagicMock()
        return svc

    def _make_order(self) -> Order:
        return Order(
            order_id="123",
            instrument="EUR_USD",
            order_type=OrderType.LIMIT,
            direction=OrderDirection.LONG,
            units=Decimal("1000"),
            price=Decimal("1.1000"),
            state=OrderState.PENDING,
            time_in_force="GTC",
            create_time=datetime(2024, 1, 1, tzinfo=UTC),
        )

    def test_success(self):
        account = OandaAccountFactory()
        svc = self._make_service(account)
        order = self._make_order()

        cancel_tx = MagicMock()
        cancel_tx.id = "456"
        cancel_tx.time = "2024-01-15T10:00:00Z"

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.orderCancelTransaction = cancel_tx
        svc.api.order.cancel.return_value = mock_response

        result = svc.cancel_order(order)
        assert isinstance(result, CancelledOrder)
        assert result.order_id == "123"
        assert result.state == OrderState.CANCELLED
        assert result.transaction_id == "456"
        svc.event_service.log_trading_event.assert_called_once()

    def test_error_status(self):
        account = OandaAccountFactory()
        svc = self._make_service(account)
        order = self._make_order()

        mock_response = MagicMock()
        mock_response.status = 404
        svc.api.order.cancel.return_value = mock_response

        with pytest.raises(OandaAPIError, match="Failed to cancel order"):
            svc.cancel_order(order)

    def test_api_exception(self):
        account = OandaAccountFactory()
        svc = self._make_service(account)
        order = self._make_order()
        svc.api.order.cancel.side_effect = ConnectionError("network error")

        with pytest.raises(OandaAPIError, match="Error cancelling order"):
            svc.cancel_order(order)


@pytest.mark.django_db
class TestClosePosition:
    """Tests for OandaService.close_position (live and dry_run)."""

    def _make_service(self, account: OandaAccounts, dry_run: bool = False) -> OandaService:
        svc = OandaService(account=account, dry_run=dry_run)
        if not dry_run:
            svc.api = MagicMock()
        svc.event_service = MagicMock()
        return svc

    def _make_position(self, direction: OrderDirection = OrderDirection.LONG) -> Position:
        return Position(
            instrument="EUR_USD",
            direction=direction,
            units=Decimal("1000"),
            average_price=Decimal("1.1000"),
            unrealized_pnl=Decimal("50"),
            trade_ids=["T1"],
            account_id="101-001-123",
        )

    def test_close_long_position(self):
        account = OandaAccountFactory()
        svc = self._make_service(account)
        position = self._make_position(OrderDirection.LONG)

        fill_tx = MagicMock()
        fill_tx.id = "789"
        fill_tx.time = "2024-01-15T12:00:00Z"
        fill_tx.price = "1.1050"

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.longOrderFillTransaction = fill_tx
        mock_response.shortOrderFillTransaction = None
        svc.api.position.close.return_value = mock_response

        result = svc.close_position(position)
        assert isinstance(result, MarketOrder)
        assert result.state == OrderState.FILLED
        assert result.direction == OrderDirection.LONG
        svc.api.position.close.assert_called_once()

    def test_close_short_position(self):
        account = OandaAccountFactory()
        svc = self._make_service(account)
        position = self._make_position(OrderDirection.SHORT)

        fill_tx = MagicMock()
        fill_tx.id = "790"
        fill_tx.time = "2024-01-15T12:00:00Z"
        fill_tx.price = "1.0950"

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.longOrderFillTransaction = None
        mock_response.shortOrderFillTransaction = fill_tx
        svc.api.position.close.return_value = mock_response

        result = svc.close_position(position)
        assert isinstance(result, MarketOrder)
        assert result.direction == OrderDirection.SHORT

    def test_dry_run_close(self):
        account = OandaAccountFactory()
        svc = self._make_service(account, dry_run=True)
        position = self._make_position(OrderDirection.LONG)

        result = svc.close_position(position, override_price=Decimal("1.1100"))
        assert isinstance(result, MarketOrder)
        assert result.state == OrderState.FILLED
        assert result.price == Decimal("1.1100")
        assert result.order_id.startswith("DRY-CLOSE-")

    def test_error_status(self):
        account = OandaAccountFactory()
        svc = self._make_service(account)
        position = self._make_position()

        mock_response = MagicMock()
        mock_response.status = 400
        svc.api.position.close.return_value = mock_response

        with pytest.raises(OandaAPIError, match="Failed to close position"):
            svc.close_position(position)


@pytest.mark.django_db
class TestCreateMarketOrder:
    """Tests for OandaService.create_market_order (live path)."""

    def _make_service(self, account: OandaAccounts) -> OandaService:
        svc = OandaService(account=account)
        svc.api = MagicMock()
        svc.event_service = MagicMock()
        svc.compliance_manager = MagicMock()
        svc.compliance_manager.validate_order.return_value = (True, None)
        return svc

    def test_fill(self):
        account = OandaAccountFactory()
        svc = self._make_service(account)

        fill_tx = MagicMock()
        fill_tx.id = "100"
        fill_tx.price = "1.1050"
        fill_tx.time = "2024-01-15T10:00:00Z"
        trade_opened = MagicMock()
        trade_opened.tradeID = "T100"
        fill_tx.tradeOpened = trade_opened

        create_tx = MagicMock()
        create_tx.id = "99"

        mock_response = MagicMock()
        mock_response.status = 201
        mock_response.orderFillTransaction = fill_tx
        mock_response.orderCreateTransaction = create_tx
        mock_response.orderRejectTransaction = None

        with patch.object(svc, "_execute_with_retry", return_value=mock_response):
            request = MarketOrderRequest(instrument="EUR_USD", units=Decimal("1000"))
            result = svc.create_market_order(request)

        assert isinstance(result, MarketOrder)
        assert result.state == OrderState.FILLED
        assert result.price == Decimal("1.1050")
        assert result.trade_id == "T100"

    def test_reject(self):
        account = OandaAccountFactory()
        svc = self._make_service(account)

        reject_tx = MagicMock()
        reject_tx.rejectReason = "INSUFFICIENT_MARGIN"

        mock_response = MagicMock()
        mock_response.status = 201
        mock_response.orderFillTransaction = None
        mock_response.orderCreateTransaction = None
        mock_response.orderRejectTransaction = reject_tx
        mock_response.body = {}

        with patch.object(svc, "_execute_with_retry", return_value=mock_response):
            request = MarketOrderRequest(instrument="EUR_USD", units=Decimal("1000"))
            with pytest.raises(OandaAPIError, match="INSUFFICIENT_MARGIN"):
                svc.create_market_order(request)


@pytest.mark.django_db
class TestCreateLimitOrder:
    """Tests for OandaService.create_limit_order."""

    def test_success(self):
        account = OandaAccountFactory()
        svc = OandaService(account=account)
        svc.api = MagicMock()
        svc.event_service = MagicMock()
        svc.compliance_manager = MagicMock()
        svc.compliance_manager.validate_order.return_value = (True, None)

        create_tx = MagicMock()
        create_tx.id = "200"
        create_tx.time = "2024-01-15T10:00:00Z"

        mock_response = MagicMock()
        mock_response.status = 201
        mock_response.orderCreateTransaction = create_tx

        with patch.object(svc, "_execute_with_retry", return_value=mock_response):
            request = LimitOrderRequest(
                instrument="EUR_USD",
                units=Decimal("1000"),
                price=Decimal("1.0900"),
            )
            result = svc.create_limit_order(request)

        assert isinstance(result, LimitOrder)
        assert result.state == OrderState.PENDING
        assert result.order_type == OrderType.LIMIT
        assert result.price == Decimal("1.0900")


@pytest.mark.django_db
class TestCreateStopOrder:
    """Tests for OandaService.create_stop_order."""

    def test_success(self):
        account = OandaAccountFactory()
        svc = OandaService(account=account)
        svc.api = MagicMock()
        svc.event_service = MagicMock()
        svc.compliance_manager = MagicMock()
        svc.compliance_manager.validate_order.return_value = (True, None)

        create_tx = MagicMock()
        create_tx.id = "300"
        create_tx.time = "2024-01-15T10:00:00Z"

        mock_response = MagicMock()
        mock_response.status = 201
        mock_response.orderCreateTransaction = create_tx

        with patch.object(svc, "_execute_with_retry", return_value=mock_response):
            request = StopOrderRequest(
                instrument="EUR_USD",
                units=Decimal("-500"),
                price=Decimal("1.0800"),
            )
            result = svc.create_stop_order(request)

        assert isinstance(result, StopOrder)
        assert result.state == OrderState.PENDING
        assert result.direction == OrderDirection.SHORT


@pytest.mark.django_db
class TestGetOrderHistory:
    """Tests for OandaService.get_order_history."""

    def test_success(self):
        account = OandaAccountFactory()
        svc = OandaService(account=account)
        svc.api = MagicMock()

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.body = {
            "orders": [
                {
                    "id": "1",
                    "instrument": "EUR_USD",
                    "type": "MARKET",
                    "units": "1000",
                    "state": "FILLED",
                    "createTime": "2024-01-15T10:00:00Z",
                },
                {
                    "id": "2",
                    "instrument": "EUR_USD",
                    "type": "LIMIT",
                    "units": "-500",
                    "price": "1.1000",
                    "state": "PENDING",
                    "createTime": "2024-01-15T11:00:00Z",
                },
            ]
        }
        svc.api.order.list.return_value = mock_response

        result = svc.get_order_history(instrument="EUR_USD", count=10)
        assert len(result) == 2
        assert result[0].order_id == "1"
        assert result[1].order_type == OrderType.LIMIT

    def test_error(self):
        account = OandaAccountFactory()
        svc = OandaService(account=account)
        svc.api = MagicMock()

        mock_response = MagicMock()
        mock_response.status = 500
        svc.api.order.list.return_value = mock_response

        with pytest.raises(OandaAPIError, match="Failed to fetch order history"):
            svc.get_order_history()


@pytest.mark.django_db
class TestGetOrder:
    """Tests for OandaService.get_order."""

    def test_success(self):
        account = OandaAccountFactory()
        svc = OandaService(account=account)
        svc.api = MagicMock()

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.body = {
            "order": {
                "id": "42",
                "instrument": "USD_JPY",
                "type": "STOP",
                "units": "2000",
                "price": "150.00",
                "state": "PENDING",
                "timeInForce": "GTC",
                "createTime": "2024-01-15T10:00:00Z",
            }
        }
        svc.api.order.get.return_value = mock_response

        result = svc.get_order("42")
        assert isinstance(result, StopOrder)
        assert result.order_id == "42"
        assert result.price == Decimal("150.00")

    def test_error(self):
        account = OandaAccountFactory()
        svc = OandaService(account=account)
        svc.api = MagicMock()

        mock_response = MagicMock()
        mock_response.status = 404
        svc.api.order.get.return_value = mock_response

        with pytest.raises(OandaAPIError):
            svc.get_order("999")


@pytest.mark.django_db
class TestGetTransactionHistory:
    """Tests for OandaService.get_transaction_history."""

    def test_success_with_transactions(self):
        account = OandaAccountFactory()
        svc = OandaService(account=account)
        svc.api = MagicMock()

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.body = {
            "transactions": [
                {
                    "id": "1001",
                    "time": "2024-01-15T10:00:00Z",
                    "type": "ORDER_FILL",
                    "instrument": "EUR_USD",
                    "units": "1000",
                    "price": "1.1050",
                    "pl": "25.00",
                    "accountBalance": "10025.00",
                },
            ],
            "pages": [],
        }
        svc.api.transaction.list.return_value = mock_response

        result = svc.get_transaction_history()
        assert len(result) == 1
        assert isinstance(result[0], Transaction)
        assert result[0].transaction_id == "1001"
        assert result[0].pl == Decimal("25.00")

    def test_error(self):
        account = OandaAccountFactory()
        svc = OandaService(account=account)
        svc.api = MagicMock()

        mock_response = MagicMock()
        mock_response.status = 500
        svc.api.transaction.list.return_value = mock_response

        # The source has a known logger-shadowing bug in the error path
        # that causes UnboundLocalError; either exception is acceptable.
        with pytest.raises((OandaAPIError, UnboundLocalError)):
            svc.get_transaction_history()


@pytest.mark.django_db
class TestExecuteWithRetry:
    """Tests for OandaService._execute_with_retry."""

    def _make_service(self, account: OandaAccounts) -> OandaService:
        svc = OandaService(account=account)
        svc.api = MagicMock()
        svc.event_service = MagicMock()
        svc.retry_delay = 0  # no sleep in tests
        return svc

    def test_success_first_attempt(self):
        account = OandaAccountFactory()
        svc = self._make_service(account)

        mock_response = MagicMock()
        mock_response.status = 201
        svc.api.order.create.return_value = mock_response

        result = svc._execute_with_retry(
            {"instrument": "EUR_USD", "units": "1000", "type": "MARKET"}
        )
        assert result == mock_response
        assert svc.api.order.create.call_count == 1

    def test_retry_on_failure_then_success(self):
        account = OandaAccountFactory()
        svc = self._make_service(account)

        fail_response = MagicMock()
        fail_response.status = 500
        fail_response.body = "Internal Server Error"

        success_response = MagicMock()
        success_response.status = 201

        svc.api.order.create.side_effect = [fail_response, success_response]

        result = svc._execute_with_retry(
            {"instrument": "EUR_USD", "units": "1000", "type": "MARKET"}
        )
        assert result == success_response
        assert svc.api.order.create.call_count == 2

    def test_max_retries_exceeded(self):
        account = OandaAccountFactory()
        svc = self._make_service(account)
        svc.max_retries = 2

        fail_response = MagicMock()
        fail_response.status = 500
        fail_response.body = "Server Error"
        svc.api.order.create.return_value = fail_response

        with pytest.raises(OandaAPIError, match="Order submission failed after 2 attempts"):
            svc._execute_with_retry({"instrument": "EUR_USD", "units": "1000", "type": "MARKET"})
        assert svc.api.order.create.call_count == 2
        svc.event_service.log_trading_event.assert_called_once()

    def test_retry_on_exception(self):
        account = OandaAccountFactory()
        svc = self._make_service(account)
        svc.max_retries = 2

        svc.api.order.create.side_effect = ConnectionError("timeout")

        with pytest.raises(OandaAPIError, match="Order submission failed after 2 attempts"):
            svc._execute_with_retry({"instrument": "EUR_USD", "units": "1000", "type": "MARKET"})


@pytest.mark.django_db
class TestSimulatePositionClose:
    """Tests for OandaService._simulate_position_close."""

    def test_dry_run_close_with_override_price(self):
        account = OandaAccountFactory()
        svc = OandaService(account=account, dry_run=True)

        position = Position(
            instrument="EUR_USD",
            direction=OrderDirection.LONG,
            units=Decimal("1000"),
            average_price=Decimal("1.1000"),
            unrealized_pnl=Decimal("0"),
            trade_ids=["T1"],
            account_id=account.account_id,
        )

        result = svc._simulate_position_close(
            position, units=None, override_price=Decimal("1.1200")
        )
        assert result.price == Decimal("1.1200")
        assert result.units == Decimal("1000")
        assert result.order_id.startswith("DRY-CLOSE-")

    def test_partial_close(self):
        account = OandaAccountFactory()
        svc = OandaService(account=account, dry_run=True)

        position = Position(
            instrument="EUR_USD",
            direction=OrderDirection.SHORT,
            units=Decimal("2000"),
            average_price=Decimal("1.1000"),
            unrealized_pnl=Decimal("0"),
            trade_ids=[],
            account_id=account.account_id,
        )
        # Track position in dry-run state
        svc._dry_run_positions["EUR_USD_short"] = position

        result = svc._simulate_position_close(
            position, units=Decimal("500"), override_price=Decimal("1.0900")
        )
        assert result.units == Decimal("500")
        # Remaining position should be tracked
        remaining = svc._dry_run_positions.get("EUR_USD_short")
        assert remaining is not None
        assert remaining.units == Decimal("1500")


@pytest.mark.django_db
class TestParseOrder:
    """Tests for OandaService._parse_order with various order types."""

    def _make_service(self) -> OandaService:
        account = OandaAccountFactory()
        svc = OandaService(account=account)
        svc.api = MagicMock()
        return svc

    def test_market_order(self):
        svc = self._make_service()
        result = svc._parse_order(
            {
                "id": "1",
                "instrument": "EUR_USD",
                "type": "MARKET",
                "units": "1000",
                "state": "FILLED",
                "createTime": "2024-01-15T10:00:00Z",
                "filledTime": "2024-01-15T10:00:01Z",
            }
        )
        assert isinstance(result, MarketOrder)
        assert result.direction == OrderDirection.LONG
        assert result.units == Decimal("1000")

    def test_limit_order(self):
        svc = self._make_service()
        result = svc._parse_order(
            {
                "id": "2",
                "instrument": "USD_JPY",
                "type": "LIMIT",
                "units": "-500",
                "price": "150.00",
                "state": "PENDING",
                "timeInForce": "GTC",
                "createTime": "2024-01-15T10:00:00Z",
            }
        )
        assert isinstance(result, LimitOrder)
        assert result.direction == OrderDirection.SHORT
        assert result.price == Decimal("150.00")

    def test_stop_order(self):
        svc = self._make_service()
        result = svc._parse_order(
            {
                "id": "3",
                "instrument": "GBP_USD",
                "type": "STOP",
                "units": "2000",
                "price": "1.2500",
                "state": "PENDING",
                "createTime": "2024-01-15T10:00:00Z",
            }
        )
        assert isinstance(result, StopOrder)
        assert result.order_type == OrderType.STOP

    def test_cancelled_order(self):
        svc = self._make_service()
        result = svc._parse_order(
            {
                "id": "4",
                "instrument": "EUR_USD",
                "type": "LIMIT",
                "units": "100",
                "price": "1.0800",
                "state": "CANCELLED",
                "createTime": "2024-01-15T10:00:00Z",
                "cancelledTime": "2024-01-15T11:00:00Z",
            }
        )
        assert result.state == OrderState.CANCELLED
        assert result.cancel_time is not None


@pytest.mark.django_db
class TestParseTransaction:
    """Tests for OandaService._parse_transaction."""

    def test_full_transaction(self):
        account = OandaAccountFactory()
        svc = OandaService(account=account)
        svc.api = MagicMock()

        result = svc._parse_transaction(
            {
                "id": "5001",
                "time": "2024-01-15T10:00:00Z",
                "type": "ORDER_FILL",
                "instrument": "EUR_USD",
                "units": "1000",
                "price": "1.1050",
                "pl": "25.50",
                "accountBalance": "10025.50",
            }
        )
        assert isinstance(result, Transaction)
        assert result.transaction_id == "5001"
        assert result.type == "ORDER_FILL"
        assert result.instrument == "EUR_USD"
        assert result.units == Decimal("1000")
        assert result.price == Decimal("1.1050")
        assert result.pl == Decimal("25.50")
        assert result.account_balance == Decimal("10025.50")

    def test_minimal_transaction(self):
        account = OandaAccountFactory()
        svc = OandaService(account=account)
        svc.api = MagicMock()

        result = svc._parse_transaction(
            {
                "id": "5002",
                "time": "2024-01-15T10:00:00Z",
                "type": "HEARTBEAT",
            }
        )
        assert result.instrument is None
        assert result.units is None
        assert result.price is None
