"""Drain-on-stop support for trading and backtest tasks.

When the user stops a task with mode DRAIN the task must continue running —
processing ticks — but:

* No new entries may be opened.
* Existing positions are inspected on each tick and closed as soon as their
  unrealised PnL is non-negative.
* The task finishes once all open positions are closed, optionally capped
  by a timeout measured from when draining started.

This module exposes a small policy object consumed by the executor.  The
executor remains responsible for interacting with the ``OrderService`` and
emitting close events; the policy decides only which positions should be
closed on this tick.

Keeping the decision logic here means it is unit-testable in isolation and
the executor can reuse it between backtest replay and live trading.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Iterable

from apps.trading.money import Money


@dataclass(frozen=True, slots=True)
class DrainCandidate:
    """A position the drain policy may close on this tick."""

    position_id: str
    current_unrealized_pnl: Decimal
    pnl_currency: str = ""

    @property
    def current_unrealized_pnl_money(self) -> Money:
        """Return unrealized PnL as an amount/currency pair."""
        return Money.coerce(self.current_unrealized_pnl, self.pnl_currency)


@dataclass(frozen=True, slots=True)
class DrainDecision:
    """Outcome of evaluating the drain policy against current positions."""

    close_position_ids: tuple[str, ...]
    should_finalize: bool
    finalize_reason: str | None = None


@dataclass(frozen=True, slots=True)
class DrainClosePolicy:
    """Decide whether an individual drain candidate should be closed."""

    def should_close(self, candidate: DrainCandidate) -> bool:
        """Return True when the position is at breakeven or better."""
        return self._is_breakeven_or_profit(candidate.current_unrealized_pnl_money.amount)

    def _is_breakeven_or_profit(self, value: object) -> bool:
        try:
            dec = Decimal(str(value))
        except (TypeError, ValueError, InvalidOperation):
            return False
        return dec >= Decimal("0")


@dataclass(frozen=True, slots=True)
class DrainTimeoutPolicy:
    """Compute drain timeout windows from task-level settings."""

    drain_started_at: datetime
    duration_hours: int
    duration_minutes: int | None = None

    @property
    def effective_timeout_seconds(self) -> int:
        """Return the effective timeout in seconds."""
        if self.duration_minutes is not None and self.duration_minutes > 0:
            return self.duration_minutes * 60
        if self.duration_hours > 0:
            return self.duration_hours * 3600
        return 0

    @property
    def has_timeout(self) -> bool:
        """Return whether a finite timeout is configured."""
        return self.effective_timeout_seconds > 0

    def deadline(self) -> datetime | None:
        """Return the absolute timeout deadline."""
        if not self.has_timeout:
            return None
        return self.drain_started_at + timedelta(seconds=self.effective_timeout_seconds)

    def expired(self, *, now: datetime) -> bool:
        """Return True when the drain timeout has elapsed."""
        deadline = self.deadline()
        return deadline is not None and now >= deadline


@dataclass(frozen=True, slots=True)
class DrainPolicy:
    """Encapsulates drain behaviour: when to close, when to give up."""

    drain_started_at: datetime
    duration_hours: int
    # Optional finer-grained override. When set and > 0 it takes precedence
    # over ``duration_hours``. Used when the user specifies a per-stop
    # drain duration in minutes from the Stop dialog.
    duration_minutes: int | None = None
    close_policy: DrainClosePolicy = field(default_factory=DrainClosePolicy)

    @property
    def effective_timeout_seconds(self) -> int:
        return self.timeout_policy.effective_timeout_seconds

    @property
    def has_timeout(self) -> bool:
        return self.timeout_policy.has_timeout

    @property
    def timeout_policy(self) -> DrainTimeoutPolicy:
        """Return the timeout policy for this drain window."""
        return DrainTimeoutPolicy(
            drain_started_at=self.drain_started_at,
            duration_hours=self.duration_hours,
            duration_minutes=self.duration_minutes,
        )

    def timeout_deadline(self) -> datetime | None:
        return self.timeout_policy.deadline()

    def evaluate(
        self,
        *,
        now: datetime,
        open_positions: Iterable[DrainCandidate],
    ) -> DrainDecision:
        """Decide which positions to close and whether to finish draining."""
        to_close: list[str] = []
        remaining = 0
        for position in open_positions:
            remaining += 1
            if self.close_policy.should_close(position):
                to_close.append(position.position_id)

        if remaining == 0:
            return DrainDecision(
                close_position_ids=(),
                should_finalize=True,
                finalize_reason="drain_complete_no_open_positions",
            )

        if self.timeout_policy.expired(now=now):
            return DrainDecision(
                close_position_ids=tuple(to_close),
                should_finalize=True,
                finalize_reason="drain_timeout",
            )

        return DrainDecision(
            close_position_ids=tuple(to_close),
            should_finalize=False,
            finalize_reason=None,
        )
