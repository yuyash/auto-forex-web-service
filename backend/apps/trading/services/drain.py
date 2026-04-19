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

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Iterable


@dataclass(frozen=True, slots=True)
class DrainCandidate:
    """A position the drain policy may close on this tick."""

    position_id: str
    current_unrealized_pnl: Decimal


@dataclass(frozen=True, slots=True)
class DrainDecision:
    """Outcome of evaluating the drain policy against current positions."""

    close_position_ids: tuple[str, ...]
    should_finalize: bool
    finalize_reason: str | None = None


@dataclass(frozen=True, slots=True)
class DrainPolicy:
    """Encapsulates drain behaviour: when to close, when to give up."""

    drain_started_at: datetime
    duration_hours: int
    # Optional finer-grained override. When set and > 0 it takes precedence
    # over ``duration_hours``. Used when the user specifies a per-stop
    # drain duration in minutes from the Stop dialog.
    duration_minutes: int | None = None

    @property
    def effective_timeout_seconds(self) -> int:
        if self.duration_minutes is not None and self.duration_minutes > 0:
            return self.duration_minutes * 60
        if self.duration_hours > 0:
            return self.duration_hours * 3600
        return 0

    @property
    def has_timeout(self) -> bool:
        return self.effective_timeout_seconds > 0

    def timeout_deadline(self) -> datetime | None:
        if not self.has_timeout:
            return None
        return self.drain_started_at + timedelta(seconds=self.effective_timeout_seconds)

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
            if self._is_breakeven_or_profit(position.current_unrealized_pnl):
                to_close.append(position.position_id)

        if remaining == 0:
            return DrainDecision(
                close_position_ids=(),
                should_finalize=True,
                finalize_reason="drain_complete_no_open_positions",
            )

        if self.has_timeout:
            deadline = self.timeout_deadline()
            if deadline is not None and now >= deadline:
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

    @staticmethod
    def _is_breakeven_or_profit(value: object) -> bool:
        try:
            dec = Decimal(str(value))
        except (TypeError, ValueError, InvalidOperation):
            return False
        return dec >= Decimal("0")
