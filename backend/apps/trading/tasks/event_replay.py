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
        if _is_snowball_net_event(strategy_event):
            return _snowball_net_open_already_applied(strategy_event, strategy_state)

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
        if _is_snowball_net_event(strategy_event):
            return _snowball_net_close_already_applied(strategy_event, strategy_state)

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


def _is_snowball_net_event(strategy_event: object) -> bool:
    strategy_event_type = str(getattr(strategy_event, "strategy_event_type", "") or "")
    strategy_type = str(getattr(strategy_event, "strategy_type", "") or "")
    return strategy_type == "snowball_net" or strategy_event_type.startswith("snowball_net_")


def _snowball_net_open_already_applied(
    strategy_event: object,
    strategy_state: dict,
) -> bool:
    last_action = _dict(strategy_state.get("last_action"))
    if not _snowball_net_action_matches(last_action, action="open", strategy_event=strategy_event):
        return False

    event_entry_id = getattr(strategy_event, "entry_id", None)
    if event_entry_id is None:
        return False
    action_entry_id = _optional_int(last_action.get("entry_id"))
    event_entry_id_int = _optional_int(event_entry_id)
    if action_entry_id is None or event_entry_id_int is None:
        return False
    return action_entry_id == event_entry_id_int


def _snowball_net_close_already_applied(
    strategy_event: object,
    strategy_state: dict,
) -> bool:
    last_action = _dict(strategy_state.get("last_action"))
    if not _snowball_net_action_matches(last_action, action="close", strategy_event=strategy_event):
        return False

    event_units = int(getattr(strategy_event, "units", 0) or 0)
    try:
        action_units = int(last_action.get("units", 0) or 0)
    except (TypeError, ValueError):
        return False
    return action_units >= event_units > 0


def _snowball_net_action_matches(
    last_action: dict,
    *,
    action: str,
    strategy_event: object,
) -> bool:
    if str(last_action.get("kind") or "") not in {"executed", "reconciled"}:
        return False
    if str(last_action.get("action") or "") != action:
        return False

    action_timestamp = str(last_action.get("timestamp") or "")
    event_timestamp = getattr(strategy_event, "timestamp", None)
    if action_timestamp and event_timestamp is not None:
        event_timestamp_text = (
            event_timestamp.isoformat()
            if hasattr(event_timestamp, "isoformat")
            else str(event_timestamp)
        )
        return action_timestamp == event_timestamp_text
    return True


def _dict(value: object) -> dict:
    return value if isinstance(value, dict) else {}


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


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
