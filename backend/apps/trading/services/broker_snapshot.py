"""Broker snapshot objects for trading reconciliation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class BrokerSnapshot:
    """Cached broker-side state used during one reconciliation pass."""

    account_details: Any | None = None
    pending_orders_by_instrument: dict[str, list[Any]] = field(default_factory=dict)
    open_trades_by_instrument: dict[str, list[Any]] = field(default_factory=dict)

    def cache_account_details(self, details: Any) -> Any:
        """Store and return account details."""
        self.account_details = details
        return details

    def cache_pending_orders(self, *, instrument: str, orders: list[Any]) -> list[Any]:
        """Store and return pending orders for an instrument."""
        self.pending_orders_by_instrument[instrument] = orders
        return orders

    def cache_open_trades(self, *, instrument: str, trades: list[Any]) -> list[Any]:
        """Store and return open trades for an instrument."""
        self.open_trades_by_instrument[instrument] = trades
        return trades


class BrokerSnapshotLoader:
    """Load broker-side state through a retry-aware request runner."""

    def __init__(
        self,
        *,
        broker_service: Any,
        request_runner: Callable[..., Any],
        snapshot: BrokerSnapshot | None = None,
    ) -> None:
        self.broker_service = broker_service
        self.request_runner = request_runner
        self.snapshot = snapshot or BrokerSnapshot()

    def account_details(self, *, label: str = "Fetch account snapshot") -> Any:
        """Return cached account details, loading from the broker once if needed."""
        if self.snapshot.account_details is not None:
            return self.snapshot.account_details
        details = self.request_runner(
            self.broker_service.get_account_details,
            label=label,
        )
        return self.snapshot.cache_account_details(details)

    def pending_orders_for(
        self,
        *,
        instrument: str,
        label: str = "Fetch pending orders",
    ) -> list[Any]:
        """Return cached pending orders for *instrument*."""
        if instrument in self.snapshot.pending_orders_by_instrument:
            return self.snapshot.pending_orders_by_instrument[instrument]
        orders = self.request_runner(
            self.broker_service.get_pending_orders,
            instrument=instrument,
            label=label,
        )
        return self.snapshot.cache_pending_orders(instrument=instrument, orders=list(orders))

    def open_trades_for(
        self,
        *,
        instrument: str,
        label: str,
    ) -> list[Any]:
        """Return cached open trades for *instrument*."""
        if instrument in self.snapshot.open_trades_by_instrument:
            return self.snapshot.open_trades_by_instrument[instrument]
        trades = self.request_runner(
            self.broker_service.get_open_trades,
            instrument=instrument,
            label=label,
        )
        return self.snapshot.cache_open_trades(instrument=instrument, trades=list(trades))
