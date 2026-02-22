"""Tests for apps.market.services.oanda – OandaService and related dataclasses."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from apps.market.services.compliance import ComplianceViolationError
from apps.market.services.oanda import (
    AccountDetails,
    CancelledOrder,
    LimitOrderRequest,
    MarketOrder,
    MarketOrderRequest,
    OandaAPIError,
    OandaService,
    OcoOrder,
    OcoOrderRequest,
    OpenTrade,
    Order,
    OrderDirection,
    OrderState,
    OrderType,
    Position,
    StopOrderRequest,
    StreamMessageType,
    Transaction,
)

# ---------------------------------------------------------------------------
# Dataclass / Enum tests
# ---------------------------------------------------------------------------


class TestOrderType:
    def test_values(self):
        assert OrderType.MARKET == "market"
        assert OrderType.LIMIT == "limit"
        assert OrderType.STOP == "stop"
        assert OrderType.OCO == "oco"


class TestOrderDirection:
    def test_values(self):
        assert OrderDirection.LONG == "long"
        assert OrderDirection.SHORT == "short"


class TestStreamMessageType:
    def test_values(self):
        assert StreamMessageType.PRICE == "PRICE"
        assert StreamMessageType.HEARTBEAT == "HEARTBEAT"


class TestMarketOrderRequest:
    def test_creation(self):
        req = MarketOrderRequest(instrument="EUR_USD", units=Decimal("1000"))
        assert req.instrument == "EUR_USD"
        assert req.units == Decimal("1000")
        assert req.take_profit is None
        assert req.stop_loss is None

    def test_with_tp_sl(self):
        req = MarketOrderRequest(
            instrument="GBP_USD",
            units=Decimal("-500"),
            take_profit=Decimal("1.2500"),
            stop_loss=Decimal("1.3000"),
        )
        assert req.take_profit == Decimal("1.2500")
        assert req.stop_loss == Decimal("1.3000")


class TestLimitOrderRequest:
    def test_creation(self):
        req = LimitOrderRequest(instrument="USD_JPY", units=Decimal("100"), price=Decimal("110.5"))
        assert req.price == Decimal("110.5")


class TestStopOrderRequest:
    def test_creation(self):
        req = StopOrderRequest(instrument="USD_JPY", units=Decimal("100"), price=Decimal("112.0"))
        assert req.price == Decimal("112.0")


class TestOcoOrderRequest:
    def test_creation(self):
        req = OcoOrderRequest(
            instrument="EUR_USD",
            units=Decimal("1000"),
            limit_price=Decimal("1.1000"),
            stop_price=Decimal("1.0800"),
        )
        assert req.limit_price == Decimal("1.1000")
        assert req.stop_price == Decimal("1.0800")


class TestOrderState:
    def test_values(self):
        assert OrderState.PENDING == "PENDING"
        assert OrderState.FILLED == "FILLED"
        assert OrderState.CANCELLED == "CANCELLED"
        assert OrderState.TRIGGERED == "TRIGGERED"
        assert OrderState.UNKNOWN == "UNKNOWN"

    def test_from_raw_valid(self):
        assert OrderState.from_raw("FILLED") == OrderState.FILLED
        assert OrderState.from_raw("pending") == OrderState.PENDING

    def test_from_raw_none(self):
        assert OrderState.from_raw(None) == OrderState.UNKNOWN
        assert OrderState.from_raw("") == OrderState.UNKNOWN

    def test_from_raw_unknown_string(self):
        assert OrderState.from_raw("BOGUS") == OrderState.UNKNOWN

    def test_from_raw_integer(self):
        assert OrderState.from_raw(42) == OrderState.UNKNOWN


class TestAccountDetails:
    def test_creation(self):
        ad = AccountDetails(
            account_id="001",
            currency="USD",
            balance=Decimal("10000"),
            nav=Decimal("10500"),
            unrealized_pl=Decimal("500"),
            margin_used=Decimal("200"),
            margin_available=Decimal("9800"),
            position_value=Decimal("5000"),
            open_trade_count=2,
            open_position_count=1,
            pending_order_count=0,
            last_transaction_id="100",
        )
        assert ad.account_id == "001"
        assert ad.balance == Decimal("10000")


class TestPosition:
    def test_creation(self):
        pos = Position(
            instrument="EUR_USD",
            direction=OrderDirection.LONG,
            units=Decimal("1000"),
            average_price=Decimal("1.1000"),
            unrealized_pnl=Decimal("50"),
            trade_ids=["t1", "t2"],
            account_id="001",
        )
        assert pos.instrument == "EUR_USD"
        assert pos.trade_ids == ["t1", "t2"]


class TestOpenTrade:
    def test_creation(self):
        trade = OpenTrade(
            trade_id="123",
            instrument="EUR_USD",
            direction=OrderDirection.LONG,
            units=Decimal("1000"),
            entry_price=Decimal("1.1000"),
            unrealized_pnl=Decimal("10"),
            open_time=datetime(2024, 1, 1, tzinfo=UTC),
            state="OPEN",
            account_id="001",
        )
        assert trade.trade_id == "123"


class TestOrderDataclass:
    def test_creation(self):
        order = Order(
            order_id="O1",
            instrument="EUR_USD",
            order_type=OrderType.MARKET,
            direction=OrderDirection.LONG,
            units=Decimal("1000"),
            price=Decimal("1.1000"),
            state=OrderState.FILLED,
            time_in_force="FOK",
            create_time=datetime(2024, 1, 1, tzinfo=UTC),
        )
        assert order.order_id == "O1"
        assert order.fill_time is None
        assert order.cancel_time is None


class TestMarketOrderDataclass:
    def test_creation(self):
        mo = MarketOrder(
            order_id="MO1",
            instrument="EUR_USD",
            order_type=OrderType.MARKET,
            direction=OrderDirection.LONG,
            units=Decimal("1000"),
            price=Decimal("1.1000"),
            state=OrderState.FILLED,
            time_in_force="FOK",
            create_time=None,
            trade_id="T1",
        )
        assert mo.trade_id == "T1"


class TestCancelledOrder:
    def test_creation(self):
        co = CancelledOrder(
            order_id="CO1",
            instrument="EUR_USD",
            order_type=OrderType.LIMIT,
            direction=OrderDirection.SHORT,
            units=Decimal("500"),
            price=Decimal("1.0900"),
            state=OrderState.CANCELLED,
            time_in_force="GTC",
            create_time=None,
            transaction_id="TX1",
        )
        assert co.transaction_id == "TX1"


class TestOcoOrderDataclass:
    def test_creation(self):
        oco = OcoOrder(
            order_id="OCO1",
            instrument="EUR_USD",
            order_type=OrderType.OCO,
            direction=OrderDirection.LONG,
            units=Decimal("1000"),
            price=None,
            state=OrderState.PENDING,
            time_in_force=None,
            create_time=None,
        )
        assert oco.limit_order is None
        assert oco.stop_order is None


class TestTransaction:
    def test_creation(self):
        tx = Transaction(
            transaction_id="TX1",
            time=datetime(2024, 1, 1, tzinfo=UTC),
            type="ORDER_FILL",
            instrument="EUR_USD",
            units=Decimal("1000"),
            price=Decimal("1.1000"),
            pl=Decimal("50"),
            account_balance=Decimal("10050"),
        )
        assert tx.transaction_id == "TX1"

    def test_defaults(self):
        tx = Transaction(transaction_id="TX2", time=None, type="HEARTBEAT")
        assert tx.instrument is None
        assert tx.units is None


class TestOandaAPIError:
    def test_is_exception(self):
        err = OandaAPIError("test error")
        assert str(err) == "test error"
        assert isinstance(err, Exception)


# ---------------------------------------------------------------------------
# OandaService helper / static method tests
# ---------------------------------------------------------------------------


def _make_mock_account(**overrides):
    account = MagicMock()
    account.account_id = overrides.get("account_id", "001-001-001-001")
    account.api_hostname = overrides.get("api_hostname", "api-fxpractice.oanda.com")
    account.get_api_token.return_value = "fake-token"
    account.jurisdiction = overrides.get("jurisdiction", "US")
    account.user = MagicMock()
    account.margin_available = overrides.get("margin_available", Decimal("50000"))
    account.balance = overrides.get("balance", Decimal("100000"))
    account.unrealized_pnl = overrides.get("unrealized_pnl", Decimal("0"))
    account.margin_used = overrides.get("margin_used", Decimal("0"))
    return account


class TestToStreamHostname:
    def test_api_prefix(self):
        assert (
            OandaService._to_stream_hostname("api-fxpractice.oanda.com")
            == "stream-fxpractice.oanda.com"
        )

    def test_already_stream(self):
        assert (
            OandaService._to_stream_hostname("stream-fxpractice.oanda.com")
            == "stream-fxpractice.oanda.com"
        )

    def test_no_prefix(self):
        assert OandaService._to_stream_hostname("custom.oanda.com") == "custom.oanda.com"

    def test_empty(self):
        assert OandaService._to_stream_hostname("") == ""

    def test_whitespace(self):
        assert OandaService._to_stream_hostname("  ") == ""


class TestMakeJsonable:
    def test_none(self):
        assert OandaService._make_jsonable(None) is None

    def test_primitives(self):
        assert OandaService._make_jsonable("hello") == "hello"
        assert OandaService._make_jsonable(42) == 42
        assert OandaService._make_jsonable(3.14) == 3.14
        assert OandaService._make_jsonable(True) is True

    def test_decimal(self):
        assert OandaService._make_jsonable(Decimal("1.23")) == "1.23"

    def test_datetime(self):
        dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        result = OandaService._make_jsonable(dt)
        assert isinstance(result, str)
        assert "2024-01-01" in result

    def test_dict(self):
        result = OandaService._make_jsonable({"a": Decimal("1"), "b": 2})
        assert result == {"a": "1", "b": 2}

    def test_list(self):
        result = OandaService._make_jsonable([Decimal("1"), "two", 3])
        assert result == ["1", "two", 3]

    def test_set(self):
        result = OandaService._make_jsonable({Decimal("1")})
        assert result == ["1"]

    def test_tuple(self):
        result = OandaService._make_jsonable((1, 2))
        assert result == [1, 2]

    def test_arbitrary_object(self):
        obj = object()
        result = OandaService._make_jsonable(obj)
        assert isinstance(result, str)

    def test_public_alias(self):
        assert OandaService.make_jsonable(Decimal("9.9")) == "9.9"


class TestAccountObjectToDict:
    def test_none(self):
        assert OandaService._account_object_to_dict(None) == {}

    def test_dict_passthrough(self):
        d = {"balance": "100"}
        assert OandaService._account_object_to_dict(d) is d

    def test_properties_attr(self):
        obj = MagicMock()
        obj._properties = {"balance": "100", "currency": "USD"}
        # Remove dict callable so _properties path is taken
        del obj.dict
        result = OandaService._account_object_to_dict(obj)
        assert result == {"balance": "100", "currency": "USD"}

    def test_dict_method(self):
        obj = MagicMock()
        obj._properties = None
        obj.dict.return_value = {"balance": "200"}
        result = OandaService._account_object_to_dict(obj)
        assert result == {"balance": "200"}

    def test_fallback_vars(self):
        class Simple:
            def __init__(self):
                self.x = 1

        result = OandaService._account_object_to_dict(Simple())
        assert result == {"x": 1}

    def test_fallback_str(self):
        # An object with no __dict__ and no _properties
        result = OandaService._account_object_to_dict(42)
        assert result == {"value": "42"}


# ---------------------------------------------------------------------------
# OandaService __init__ tests
# ---------------------------------------------------------------------------


class TestOandaServiceInit:
    @patch("apps.market.services.oanda.v20.Context")
    @patch("apps.market.services.oanda.ComplianceService")
    @patch("apps.market.services.oanda.MarketEventService")
    def test_init_with_account(self, mock_event_svc, mock_compliance, mock_v20_ctx):
        account = _make_mock_account()
        svc = OandaService(account=account, dry_run=False)
        assert svc.account is account
        assert svc.dry_run is False
        assert svc.api is not None
        assert svc.stream_api is not None
        assert svc.compliance_manager is not None

    @patch("apps.market.services.oanda.MarketEventService")
    def test_init_dry_run_no_account(self, mock_event_svc):
        svc = OandaService(account=None, dry_run=True)
        assert svc.dry_run is True
        assert svc.api is None
        assert svc.stream_api is None
        assert svc.compliance_manager is None


# ---------------------------------------------------------------------------
# _to_decimal / _parse_iso_datetime
# ---------------------------------------------------------------------------


class TestToDecimal:
    @patch("apps.market.services.oanda.MarketEventService")
    def test_none(self, _):
        svc = OandaService(account=None, dry_run=True)
        assert svc._to_decimal(None) is None

    @patch("apps.market.services.oanda.MarketEventService")
    def test_empty_string(self, _):
        svc = OandaService(account=None, dry_run=True)
        assert svc._to_decimal("") is None

    @patch("apps.market.services.oanda.MarketEventService")
    def test_valid(self, _):
        svc = OandaService(account=None, dry_run=True)
        assert svc._to_decimal("1.2345") == Decimal("1.2345")

    @patch("apps.market.services.oanda.MarketEventService")
    def test_invalid(self, _):
        svc = OandaService(account=None, dry_run=True)
        assert svc._to_decimal("not-a-number") is None


class TestParseIsoDatetime:
    @patch("apps.market.services.oanda.MarketEventService")
    def test_none(self, _):
        svc = OandaService(account=None, dry_run=True)
        assert svc._parse_iso_datetime(None) is None

    @patch("apps.market.services.oanda.MarketEventService")
    def test_empty(self, _):
        svc = OandaService(account=None, dry_run=True)
        assert svc._parse_iso_datetime("") is None

    @patch("apps.market.services.oanda.MarketEventService")
    def test_datetime_passthrough(self, _):
        svc = OandaService(account=None, dry_run=True)
        dt = datetime(2024, 1, 1, tzinfo=UTC)
        assert svc._parse_iso_datetime(dt) is dt

    @patch("apps.market.services.oanda.MarketEventService")
    def test_z_suffix(self, _):
        svc = OandaService(account=None, dry_run=True)
        result = svc._parse_iso_datetime("2024-01-01T12:00:00Z")
        assert result is not None
        assert result.year == 2024

    @patch("apps.market.services.oanda.MarketEventService")
    def test_invalid_string(self, _):
        svc = OandaService(account=None, dry_run=True)
        assert svc._parse_iso_datetime("not-a-date") is None


# ---------------------------------------------------------------------------
# get_account_details (mocked v20 API)
# ---------------------------------------------------------------------------


class TestGetAccountDetails:
    @patch("apps.market.services.oanda.v20.Context")
    @patch("apps.market.services.oanda.ComplianceService")
    @patch("apps.market.services.oanda.MarketEventService")
    def test_success(self, mock_event_svc, mock_compliance, mock_v20_ctx):
        account = _make_mock_account()
        svc = OandaService(account=account)

        svc._account_resource_cache = {
            "currency": "USD",
            "balance": "10000",
            "unrealizedPL": "500",
            "NAV": "10500",
            "marginUsed": "200",
            "marginAvailable": "9800",
            "positionValue": "5000",
            "openTradeCount": 2,
            "openPositionCount": 1,
            "pendingOrderCount": 0,
            "lastTransactionID": "100",
        }

        details = svc.get_account_details()
        assert isinstance(details, AccountDetails)
        assert details.balance == Decimal("10000")
        assert details.currency == "USD"
        assert details.open_trade_count == 2


# ---------------------------------------------------------------------------
# get_account_hedging_enabled
# ---------------------------------------------------------------------------


class TestGetAccountHedgingEnabled:
    @patch("apps.market.services.oanda.v20.Context")
    @patch("apps.market.services.oanda.ComplianceService")
    @patch("apps.market.services.oanda.MarketEventService")
    def test_hedging_true(self, mock_event_svc, mock_compliance, mock_v20_ctx):
        account = _make_mock_account()
        svc = OandaService(account=account)
        svc._account_resource_cache = {"hedgingEnabled": True}
        assert svc.get_account_hedging_enabled() is True

    @patch("apps.market.services.oanda.v20.Context")
    @patch("apps.market.services.oanda.ComplianceService")
    @patch("apps.market.services.oanda.MarketEventService")
    def test_hedging_false(self, mock_event_svc, mock_compliance, mock_v20_ctx):
        account = _make_mock_account()
        svc = OandaService(account=account)
        svc._account_resource_cache = {"hedgingEnabled": False}
        assert svc.get_account_hedging_enabled() is False


# ---------------------------------------------------------------------------
# get_open_positions (mocked v20 API)
# ---------------------------------------------------------------------------


class TestGetOpenPositions:
    @patch("apps.market.services.oanda.v20.Context")
    @patch("apps.market.services.oanda.ComplianceService")
    @patch("apps.market.services.oanda.MarketEventService")
    def test_returns_positions(self, mock_event_svc, mock_compliance, mock_v20_ctx):
        account = _make_mock_account()
        svc = OandaService(account=account)

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.body = {
            "positions": [
                {
                    "instrument": "EUR_USD",
                    "long": {
                        "units": "1000",
                        "averagePrice": "1.1000",
                        "unrealizedPL": "50",
                        "tradeIDs": ["t1"],
                    },
                    "short": {"units": "0"},
                }
            ]
        }
        svc.api.position.list_open.return_value = mock_response

        positions = svc.get_open_positions()
        assert len(positions) == 1
        assert positions[0].instrument == "EUR_USD"
        assert positions[0].direction == OrderDirection.LONG

    @patch("apps.market.services.oanda.v20.Context")
    @patch("apps.market.services.oanda.ComplianceService")
    @patch("apps.market.services.oanda.MarketEventService")
    def test_filter_by_instrument(self, mock_event_svc, mock_compliance, mock_v20_ctx):
        account = _make_mock_account()
        svc = OandaService(account=account)

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.body = {
            "positions": [
                {
                    "instrument": "EUR_USD",
                    "long": {
                        "units": "1000",
                        "averagePrice": "1.1",
                        "unrealizedPL": "0",
                        "tradeIDs": [],
                    },
                    "short": {"units": "0"},
                },
                {
                    "instrument": "GBP_USD",
                    "long": {
                        "units": "500",
                        "averagePrice": "1.3",
                        "unrealizedPL": "0",
                        "tradeIDs": [],
                    },
                    "short": {"units": "0"},
                },
            ]
        }
        svc.api.position.list_open.return_value = mock_response

        positions = svc.get_open_positions(instrument="GBP_USD")
        assert len(positions) == 1
        assert positions[0].instrument == "GBP_USD"


# ---------------------------------------------------------------------------
# get_open_trades
# ---------------------------------------------------------------------------


class TestGetOpenTrades:
    @patch("apps.market.services.oanda.v20.Context")
    @patch("apps.market.services.oanda.ComplianceService")
    @patch("apps.market.services.oanda.MarketEventService")
    def test_returns_trades(self, mock_event_svc, mock_compliance, mock_v20_ctx):
        account = _make_mock_account()
        svc = OandaService(account=account)

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.body = {
            "trades": [
                {
                    "id": "T1",
                    "instrument": "EUR_USD",
                    "currentUnits": "1000",
                    "price": "1.1000",
                    "unrealizedPL": "10",
                    "openTime": "2024-01-01T00:00:00Z",
                    "state": "OPEN",
                }
            ]
        }
        svc.api.trade.list_open.return_value = mock_response

        trades = svc.get_open_trades()
        assert len(trades) == 1
        assert trades[0].trade_id == "T1"
        assert trades[0].direction == OrderDirection.LONG


# ---------------------------------------------------------------------------
# get_pending_orders
# ---------------------------------------------------------------------------


class TestGetPendingOrders:
    @patch("apps.market.services.oanda.v20.Context")
    @patch("apps.market.services.oanda.ComplianceService")
    @patch("apps.market.services.oanda.MarketEventService")
    def test_returns_pending(self, mock_event_svc, mock_compliance, mock_v20_ctx):
        account = _make_mock_account()
        svc = OandaService(account=account)

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.body = {
            "orders": [
                {
                    "id": "O1",
                    "instrument": "EUR_USD",
                    "type": "LIMIT",
                    "units": "1000",
                    "price": "1.0900",
                    "state": "PENDING",
                    "timeInForce": "GTC",
                    "createTime": "2024-01-01T00:00:00Z",
                }
            ]
        }
        svc.api.order.list_pending.return_value = mock_response

        orders = svc.get_pending_orders()
        assert len(orders) == 1
        assert orders[0].order_id == "O1"
        assert orders[0].state == OrderState.PENDING


# ---------------------------------------------------------------------------
# create_market_order – dry_run mode
# ---------------------------------------------------------------------------


class TestCreateMarketOrderDryRun:
    @patch("apps.market.services.oanda.MarketEventService")
    def test_dry_run_with_override_price(self, mock_event_svc):
        svc = OandaService(account=None, dry_run=True)
        req = MarketOrderRequest(instrument="EUR_USD", units=Decimal("1000"))
        result = svc.create_market_order(req, override_price=Decimal("1.1234"))

        assert isinstance(result, MarketOrder)
        assert result.state == OrderState.FILLED
        assert result.price == Decimal("1.1234")
        assert result.direction == OrderDirection.LONG
        assert result.order_id.startswith("DRY-")
        assert result.trade_id is not None

    @patch("apps.market.services.oanda.MarketEventService")
    def test_dry_run_short(self, mock_event_svc):
        svc = OandaService(account=None, dry_run=True)
        req = MarketOrderRequest(instrument="EUR_USD", units=Decimal("-500"))
        result = svc.create_market_order(req, override_price=Decimal("1.1000"))

        assert result.direction == OrderDirection.SHORT
        assert result.units == Decimal("500")

    @patch("apps.market.services.oanda.MarketEventService")
    def test_dry_run_updates_position_tracking(self, mock_event_svc):
        svc = OandaService(account=None, dry_run=True)
        req = MarketOrderRequest(instrument="EUR_USD", units=Decimal("1000"))
        svc.create_market_order(req, override_price=Decimal("1.1000"))

        assert "EUR_USD_long" in svc._dry_run_positions
        assert svc._dry_run_positions["EUR_USD_long"].units == Decimal("1000")


# ---------------------------------------------------------------------------
# close_trade – dry_run mode (requires account for live)
# ---------------------------------------------------------------------------


class TestCloseTradeLive:
    @patch("apps.market.services.oanda.v20.Context")
    @patch("apps.market.services.oanda.ComplianceService")
    @patch("apps.market.services.oanda.MarketEventService")
    def test_close_trade_success(self, mock_event_svc, mock_compliance, mock_v20_ctx):
        account = _make_mock_account()
        svc = OandaService(account=account)

        trade = OpenTrade(
            trade_id="T1",
            instrument="EUR_USD",
            direction=OrderDirection.LONG,
            units=Decimal("1000"),
            entry_price=Decimal("1.1000"),
            unrealized_pnl=Decimal("10"),
            open_time=None,
            state="OPEN",
            account_id="001",
        )

        fill_tx = MagicMock()
        fill_tx.time = "2024-06-01T12:00:00Z"
        fill_tx.price = "1.1050"
        fill_tx.id = "TX1"

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.orderFillTransaction = fill_tx
        svc.api.trade.close.return_value = mock_response

        result = svc.close_trade(trade)
        assert isinstance(result, MarketOrder)
        assert result.state == OrderState.FILLED


# ---------------------------------------------------------------------------
# _validate_compliance
# ---------------------------------------------------------------------------


class TestValidateCompliance:
    @patch("apps.market.services.oanda.v20.Context")
    @patch("apps.market.services.oanda.ComplianceService")
    @patch("apps.market.services.oanda.MarketEventService")
    def test_valid_order(self, mock_event_svc, mock_compliance_cls, mock_v20_ctx):
        account = _make_mock_account()
        svc = OandaService(account=account)
        svc.compliance_manager.validate_order.return_value = (True, None)

        # Should not raise
        svc._validate_compliance({"instrument": "EUR_USD", "units": 1000})

    @patch("apps.market.services.oanda.v20.Context")
    @patch("apps.market.services.oanda.ComplianceService")
    @patch("apps.market.services.oanda.MarketEventService")
    def test_invalid_order_raises(self, mock_event_svc, mock_compliance_cls, mock_v20_ctx):
        account = _make_mock_account()
        svc = OandaService(account=account)
        svc.compliance_manager.validate_order.return_value = (False, "Hedging not allowed")

        with pytest.raises(ComplianceViolationError, match="Hedging not allowed"):
            svc._validate_compliance({"instrument": "EUR_USD", "units": 1000})

    @patch("apps.market.services.oanda.MarketEventService")
    def test_no_account_skips(self, mock_event_svc):
        svc = OandaService(account=None, dry_run=True)
        # Should not raise
        svc._validate_compliance({"instrument": "EUR_USD", "units": 1000})
