"""Pure response parsing helpers for the OANDA service."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from apps.market.services.oanda_types import (
    LimitOrder,
    MarketOrder,
    Order,
    OrderDirection,
    OrderState,
    OrderType,
    PendingOrder,
    Position,
    StopOrder,
    Transaction,
)


class OandaResponseParser:
    """Parser for OANDA response objects and transaction payloads."""

    def make_jsonable(self, value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, dict):
            return {str(k): self.make_jsonable(v) for k, v in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [self.make_jsonable(v) for v in value]
        return str(value)

    def response_field(self, response: Any, field_name: str) -> Any:
        value = getattr(response, field_name, None)
        if value is not None:
            return value

        body = getattr(response, "body", None)
        if isinstance(body, dict):
            return body.get(field_name)

        return None

    def object_field(self, value: Any, field_name: str) -> Any:
        if value is None:
            return None
        if isinstance(value, dict):
            return value.get(field_name)
        return getattr(value, field_name, None)

    def account_object_to_dict(self, account_data: Any) -> dict[str, Any]:
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
            except Exception:
                maybe_dict = None

        try:
            return dict(vars(account_data))
        except Exception:
            return {"value": str(account_data)}

    def as_pending_order(self, order: Order) -> PendingOrder:
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

    def format_position(
        self,
        *,
        instrument: str,
        direction: OrderDirection,
        pos_data: dict[str, Any],
        account_id: str,
    ) -> Position:
        units = Decimal(str(pos_data.get("units", "0")))
        avg_price = Decimal(str(pos_data.get("averagePrice", "0")))
        unrealized_pl = Decimal(str(pos_data.get("unrealizedPL", "0")))
        trade_ids = pos_data.get("tradeIDs", [])

        return Position(
            instrument=instrument,
            direction=direction,
            units=abs(units),
            average_price=avg_price,
            unrealized_pnl=unrealized_pl,
            trade_ids=[str(t) for t in trade_ids],
            account_id=account_id,
        )

    def parse_iso_datetime(self, value: Any) -> datetime | None:
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        value_str = str(value)
        if value_str.endswith("Z"):
            value_str = value_str[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(value_str)
        except ValueError:
            return None

    def parse_order(self, order: Any) -> Order:
        raw_type = str(self.object_field(order, "type") or "").upper()
        order_type = {
            "MARKET": OrderType.MARKET,
            "LIMIT": OrderType.LIMIT,
            "STOP": OrderType.STOP,
        }.get(raw_type, OrderType.MARKET)

        units_signed = self.to_decimal(self.object_field(order, "units")) or Decimal("0")
        direction = (
            OrderDirection.LONG
            if units_signed > 0
            else OrderDirection.SHORT
            if units_signed < 0
            else OrderDirection.LONG
        )
        units_abs = abs(units_signed)
        price = self.to_decimal(self.object_field(order, "price"))

        create_time = self.parse_iso_datetime(self.object_field(order, "createTime"))
        fill_time = self.parse_iso_datetime(self.object_field(order, "filledTime"))
        cancel_time = self.parse_iso_datetime(self.object_field(order, "cancelledTime"))
        state = OrderState.from_raw(self.object_field(order, "state"))
        time_in_force_raw = self.object_field(order, "timeInForce")
        time_in_force = str(time_in_force_raw) if time_in_force_raw else None

        order_id = str(self.object_field(order, "id") or "")
        instrument = str(self.object_field(order, "instrument") or "")

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

    def parse_transaction(self, txn: dict[str, Any]) -> Transaction:
        trade_id = None
        trade_opened = txn.get("tradeOpened")
        if isinstance(trade_opened, dict):
            trade_id = trade_opened.get("tradeID")
        trades_closed = txn.get("tradesClosed")
        if trade_id is None and isinstance(trades_closed, list) and trades_closed:
            first_closed = trades_closed[0]
            if isinstance(first_closed, dict):
                trade_id = first_closed.get("tradeID")
        return Transaction(
            transaction_id=str(txn.get("id", "")),
            time=self.parse_iso_datetime(txn.get("time")),
            type=str(txn.get("type", "")),
            instrument=str(txn.get("instrument")) if txn.get("instrument") else None,
            units=self.to_decimal(txn.get("units")),
            price=self.to_decimal(txn.get("price")),
            pl=self.to_decimal(txn.get("pl")),
            account_balance=self.to_decimal(txn.get("accountBalance")),
            order_id=str(txn.get("orderID")) if txn.get("orderID") is not None else None,
            trade_id=str(trade_id) if trade_id not in (None, "") else None,
            reason=str(txn.get("reason")) if txn.get("reason") else None,
            raw=self.make_jsonable(txn),
        )

    def to_decimal(self, value: Any) -> Decimal | None:
        if value is None:
            return None
        value_str = str(value)
        if value_str == "":
            return None
        try:
            return Decimal(value_str)
        except Exception:
            return None


OANDA_RESPONSE_PARSER = OandaResponseParser()


def make_jsonable(value: Any) -> Any:
    return OANDA_RESPONSE_PARSER.make_jsonable(value)


def response_field(response: Any, field_name: str) -> Any:
    return OANDA_RESPONSE_PARSER.response_field(response, field_name)


def object_field(value: Any, field_name: str) -> Any:
    return OANDA_RESPONSE_PARSER.object_field(value, field_name)


def account_object_to_dict(account_data: Any) -> dict[str, Any]:
    return OANDA_RESPONSE_PARSER.account_object_to_dict(account_data)


def as_pending_order(order: Order) -> PendingOrder:
    return OANDA_RESPONSE_PARSER.as_pending_order(order)


def format_position(
    *,
    instrument: str,
    direction: OrderDirection,
    pos_data: dict[str, Any],
    account_id: str,
) -> Position:
    return OANDA_RESPONSE_PARSER.format_position(
        instrument=instrument,
        direction=direction,
        pos_data=pos_data,
        account_id=account_id,
    )


def parse_iso_datetime(value: Any) -> datetime | None:
    return OANDA_RESPONSE_PARSER.parse_iso_datetime(value)


def parse_order(order: Any) -> Order:
    return OANDA_RESPONSE_PARSER.parse_order(order)


def parse_transaction(txn: dict[str, Any]) -> Transaction:
    return OANDA_RESPONSE_PARSER.parse_transaction(txn)


def to_decimal(value: Any) -> Decimal | None:
    return OANDA_RESPONSE_PARSER.to_decimal(value)
