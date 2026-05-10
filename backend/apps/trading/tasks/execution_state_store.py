"""Persistence helper for execution state updates."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db.models import F
from django.utils import timezone as dj_timezone

if TYPE_CHECKING:
    from apps.trading.models.state import ExecutionState


class ExecutionStateConflict(RuntimeError):
    """Raised when another writer updated the execution state first."""


class ExecutionStateStore:
    """Persist execution state with optimistic locking."""

    def save(self, state: "ExecutionState") -> None:
        update_fields: dict[str, object] = {
            "strategy_state": state.strategy_state,
            "current_balance": state.current_balance,
            "current_balance_currency": getattr(state, "current_balance_currency", ""),
            "ticks_processed": state.ticks_processed,
            "last_tick_timestamp": state.last_tick_timestamp,
            "resume_cursor_timestamp": (state.resume_cursor_timestamp or state.last_tick_timestamp),
            "last_tick_price": state.last_tick_price,
            "last_tick_bid": state.last_tick_bid,
            "last_tick_ask": state.last_tick_ask,
            "updated_at": dj_timezone.now(),
            "state_version": F("state_version") + 1,
        }
        rows = (
            type(state)
            .objects.filter(
                pk=state.pk,
                state_version=state.state_version,
            )
            .update(**update_fields)
        )
        if rows != 1:
            raise ExecutionStateConflict(
                "ExecutionState optimistic lock conflict: stale state_version detected "
                f"(task_id={state.task_id}, execution_id={state.execution_id}, "
                f"state_version={state.state_version})"
            )
        state.state_version += 1
