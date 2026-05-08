"""Broker-facing OANDA DTOs and exceptions.

These types are intentionally independent from the concrete v20 client so
callers can depend on stable domain shapes without importing transport logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any


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
    client_order_id: str | None = None


@dataclass(frozen=True, slots=True)
class LimitOrderRequest:
    instrument: str
    units: Decimal  # signed (+ long, - short)
    price: Decimal
    take_profit: Decimal | None = None
    stop_loss: Decimal | None = None
    client_order_id: str | None = None


@dataclass(frozen=True, slots=True)
class StopOrderRequest:
    instrument: str
    units: Decimal  # signed (+ long, - short)
    price: Decimal
    take_profit: Decimal | None = None
    stop_loss: Decimal | None = None
    client_order_id: str | None = None


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
    def from_raw(cls, value: Any) -> "OrderState":
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
    close_time: datetime | None = None
    realized_pnl: Decimal | None = None


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
    trade_id: str | None = None


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
    order_id: str | None = None
    trade_id: str | None = None
    reason: str | None = None
    raw: dict[str, Any] | None = None


class OandaAPIError(Exception):
    """Exception raised when an OANDA API call fails.

    The ``str()`` of this exception returns only the safe, user-facing
    message. Raw upstream details are stored in ``internal_detail`` for
    server-side logging and must never be sent to the client.
    """

    def __init__(self, message: str, *, internal_detail: str = ""):
        super().__init__(message)
        self.internal_detail = internal_detail
