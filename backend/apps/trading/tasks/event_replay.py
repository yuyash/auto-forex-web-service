"""Replay and idempotency helpers for persisted trading events."""

from __future__ import annotations

from typing import Protocol

from django.utils import timezone as dj_timezone

from apps.trading.enums import TaskType
from apps.trading.models import Position, TradingEvent
from apps.trading.models.state import ExecutionState


class EventReplayTask(Protocol):
    pk: object
    execution_id: object


class EventReplayExecutor(Protocol):
    task_type: TaskType
    task: EventReplayTask
    instrument: str


def classify_replay_event(trading_event: TradingEvent) -> str:
    """Classify replayed events by potential PnL impact."""
    trade_impacting = {
        "open_position",
        "close_position",
        "rebuild_position",
        "volatility_lock",
        "volatility_hedge_neutralize",
        "margin_protection",
    }
    return "trade-impacting" if trading_event.event_type in trade_impacting else "lifecycle"


def event_already_applied(
    executor: EventReplayExecutor,
    *,
    trading_event: TradingEvent,
    state: ExecutionState,
) -> bool:
    """Best-effort idempotency guard for resumed event replay."""
    from apps.trading.events import (
        ClosePositionEvent,
        MarginProtectionEvent,
        OpenPositionEvent,
        StrategyEvent,
        VolatilityHedgeNeutralizeEvent,
        VolatilityLockEvent,
    )

    strategy_event = StrategyEvent.from_dict(trading_event.details)
    strategy_state = state.strategy_state if isinstance(state.strategy_state, dict) else {}
    task_id = executor.task.pk
    execution_id = executor.task.execution_id

    if isinstance(strategy_event, OpenPositionEvent):
        entry_id = strategy_event.entry_id
        if entry_id is None:
            return False
        open_entries = strategy_state.get("open_entries")
        if not isinstance(open_entries, list):
            return False
        for entry in open_entries:
            if not isinstance(entry, dict):
                continue
            try:
                current_entry_id = int(entry.get("entry_id", -1))
            except (TypeError, ValueError):
                continue
            if current_entry_id != int(entry_id):
                continue
            position_id = str(entry.get("position_id") or "").strip()
            if not position_id:
                return False
            exists = Position.objects.filter(
                id=position_id,
                task_type=executor.task_type.value,
                task_id=task_id,
                execution_id=execution_id,
                is_open=True,
            ).exists()
            return bool(exists)
        return False

    if isinstance(strategy_event, ClosePositionEvent):
        position_id = str(strategy_event.position_id or "").strip()
        if not position_id:
            return False
        return not Position.objects.filter(
            id=position_id,
            task_type=executor.task_type.value,
            task_id=task_id,
            execution_id=execution_id,
            is_open=True,
        ).exists()

    if isinstance(strategy_event, (VolatilityLockEvent, MarginProtectionEvent)):
        return not Position.objects.filter(
            task_type=executor.task_type.value,
            task_id=task_id,
            execution_id=execution_id,
            instrument=executor.instrument,
            is_open=True,
        ).exists()

    if isinstance(strategy_event, VolatilityHedgeNeutralizeEvent):
        return False

    return False


def mark_event_processed(trading_event: TradingEvent) -> None:
    update_data = {
        "is_processed": True,
        "processed_at": dj_timezone.now(),
        "processing_error": "",
    }
    type(trading_event).objects.filter(pk=trading_event.pk).update(**update_data)
    trading_event.is_processed = True
    trading_event.processed_at = update_data["processed_at"]
    trading_event.processing_error = ""


def mark_event_processing_error(trading_event: TradingEvent, message: str) -> None:
    type(trading_event).objects.filter(pk=trading_event.pk).update(
        processing_error=str(message)[:4000]
    )
    trading_event.processing_error = str(message)[:4000]
