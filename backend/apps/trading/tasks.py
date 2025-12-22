from __future__ import annotations

import json
import os
import socket
import time
from datetime import datetime, timezone
from decimal import Decimal
from logging import getLogger
from typing import Any, cast

import redis
from celery import current_task, shared_task
from django.conf import settings
from django.db import transaction
from django.utils import timezone as dj_timezone

from apps.trading.models import CeleryTaskStatus
from apps.trading.services.events import TradingEventService
from apps.trading.services.task import CeleryTaskService
from apps.trading.enums import TaskStatus, TaskType
from apps.trading.models import BacktestTask, ExecutionMetrics, TaskExecution, TradingTask
from apps.trading.services.registry import registry as strategy_registry
from apps.trading.services.performance import LivePerformanceService

logger = getLogger(__name__)


def _safe_json(value: Any, *, max_len: int = 600) -> str:
    try:
        s = json.dumps(value, default=str, ensure_ascii=False)
    except Exception:  # pylint: disable=broad-exception-caught
        s = str(value)
    if len(s) > max_len:
        return s[: max_len - 3] + "..."
    return s


def _format_strategy_event(*, event: dict[str, Any], tick_ts: str | None = None) -> str:
    e_type = str(event.get("type") or "")
    details_raw = event.get("details")
    details: dict[str, Any] = details_raw if isinstance(details_raw, dict) else {}

    prefix = f"[{tick_ts}] " if tick_ts else ""

    if e_type == "open":
        layer = details.get("layer")
        direction = details.get("direction")
        entry_price = details.get("entry_price")
        lot_size = details.get("lot_size")
        against_pips = details.get("against_pips")
        trigger_pips = details.get("trigger_pips")
        retr = details.get("retracement")
        retracement_open = " retracement" if details.get("retracement_open") else ""
        extra = ""
        if details.get("retracement_open"):
            extra = (
                f" (retracement={retr} against_pips={against_pips} " f"trigger_pips={trigger_pips})"
            )

        return (
            f"{prefix}Trade OPEN: layer={layer} dir={direction} "
            f"price={entry_price} lot={lot_size}{retracement_open}{extra}"
        )

    if e_type == "close":
        reason = details.get("reason")
        pips = details.get("pips")
        return f"{prefix}Trade CLOSE: reason={reason} pips={pips}"

    if e_type in {
        "layer_opened",
        "layer_retracement_opened",
        "take_profit_hit",
        "strategy_started",
        "strategy_paused",
        "strategy_resumed",
        "strategy_stopped",
    }:
        return f"{prefix}{e_type}: { _safe_json(details) if details else '' }".rstrip()

    # Default: include details so debugging is possible.
    return f"{prefix}strategy_event type={e_type} details={_safe_json(details)}"


def _extract_trade_from_strategy_event(event: dict[str, Any]) -> dict[str, Any] | None:
    """Extract a completed trade record from a strategy event.

    ExecutionMetrics.calculate_from_trades expects each item to include a usable `pnl`.
    For the floor strategy, completed trades are represented by `type == 'close'` events
    with pnl embedded in `details`.
    """
    if not isinstance(event, dict):
        return None

    # Already in trade-log shape (some strategies may emit this directly).
    if event.get("pnl") is not None and (event.get("exit_time") or event.get("timestamp")):
        return event

    e_type = str(event.get("type") or "")
    if e_type != "close":
        return None

    details_raw = event.get("details")
    details: dict[str, Any] = details_raw if isinstance(details_raw, dict) else {}

    pnl = details.get("pnl")
    if pnl is None:
        return None

    # Prefer explicit entry/exit times. Fall back to event timestamp.
    ts = event.get("timestamp")
    entry_time = details.get("entry_time") or ts
    exit_time = details.get("exit_time") or ts

    return {
        "entry_time": entry_time,
        "exit_time": exit_time,
        "instrument": details.get("instrument"),
        "direction": details.get("direction"),
        "units": details.get("units"),
        "entry_price": details.get("entry_price"),
        "exit_price": details.get("exit_price"),
        "pnl": pnl,
        "pips": details.get("pips"),
        "reason": details.get("reason"),
    }


def _current_task_id() -> str | None:
    try:
        return str(getattr(getattr(current_task, "request", None), "id", None) or "") or None
    except Exception:  # pylint: disable=broad-exception-caught
        return None


def _lock_value() -> str:
    return f"{socket.gethostname()}:{os.getpid()}"


def _redis_client() -> redis.Redis:
    return redis.Redis.from_url(getattr(settings, "MARKET_REDIS_URL"), decode_responses=True)


def _isoformat(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_iso_datetime(value: str) -> datetime:
    value_str = str(value)
    if value_str.endswith("Z"):
        value_str = value_str[:-1] + "+00:00"
    dt = datetime.fromisoformat(value_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _backtest_channel_for_request(request_id: str) -> str:
    prefix = getattr(settings, "MARKET_BACKTEST_TICK_CHANNEL_PREFIX", "market:backtest:ticks:")
    return f"{prefix}{request_id}"


@transaction.atomic
def _create_execution(*, task_type: str, task_id: int) -> TaskExecution:
    last_num = (
        TaskExecution.objects.filter(task_type=task_type, task_id=task_id)
        .order_by("-execution_number")
        .values_list("execution_number", flat=True)
        .first()
    )
    next_num = int(last_num or 0) + 1
    return TaskExecution.objects.create(
        task_type=task_type,
        task_id=task_id,
        execution_number=next_num,
        status=TaskStatus.RUNNING,
        progress=0,
        started_at=dj_timezone.now(),
    )


def _finalize_execution_success(execution: TaskExecution) -> None:
    execution.mark_completed()


def _finalize_execution_failure(execution: TaskExecution, exc: Exception) -> None:
    execution.mark_failed(exc)


def _ensure_strategies_registered() -> None:
    # trading.apps should call this, but tasks may run in a worker
    # process before Django app.ready hooks are exercised.
    from apps.trading.services.registry import register_all_strategies

    register_all_strategies()


@shared_task(name="trading.tasks.stop_trading_task")
def stop_trading_task(task_id: int, mode: str = "graceful") -> None:
    """Request stop for a running trading task."""
    event_service = TradingEventService()
    task_name = "trading.tasks.run_trading_task"
    instance_key = str(task_id)
    CeleryTaskStatus.objects.filter(task_name=task_name, instance_key=instance_key).update(
        status=CeleryTaskStatus.Status.STOP_REQUESTED,
        status_message=f"stop_requested mode={mode}",
        last_heartbeat_at=dj_timezone.now(),
    )

    event_service.log_event(
        event_type="trading_task_stop_requested",
        severity="info",
        description=f"Stop requested for trading task {task_id} (mode={mode})",
        task_type=TaskType.TRADING,
        task_id=task_id,
        details={"mode": mode},
    )


@shared_task(name="trading.tasks.run_trading_task")
def run_trading_task(task_id: int, execution_id: int | None = None) -> None:
    """Run a live trading task by subscribing to Market ticks."""

    _ensure_strategies_registered()

    task_name = "trading.tasks.run_trading_task"
    instance_key = str(task_id)
    task_service = CeleryTaskService(
        task_name=task_name,
        instance_key=instance_key,
        stop_check_interval_seconds=1.0,
        heartbeat_interval_seconds=5.0,
    )
    task_service.start(
        celery_task_id=_current_task_id(),
        worker=_lock_value(),
        meta={"kind": "trading", "task_id": task_id},
    )

    event_service = TradingEventService()

    try:
        task = TradingTask.objects.select_related("config", "oanda_account", "user").get(pk=task_id)
    except TradingTask.DoesNotExist:
        event_service.log_event(
            event_type="trading_task_not_found",
            severity="error",
            description=f"TradingTask {task_id} not found",
            task_type=TaskType.TRADING,
            task_id=task_id,
        )
        task_service.mark_stopped(
            status=CeleryTaskStatus.Status.FAILED, status_message="Task not found"
        )
        return

    execution: TaskExecution
    if execution_id is not None:
        try:
            execution = TaskExecution.objects.get(
                pk=int(execution_id),
                task_type=TaskType.TRADING,
                task_id=task_id,
            )
            if execution.status != TaskStatus.RUNNING or execution.progress != 0:
                execution.status = TaskStatus.RUNNING
                execution.progress = 0
            if execution.started_at is None:
                execution.started_at = dj_timezone.now()
            execution.save(update_fields=["status", "progress", "started_at"])
        except Exception:  # pylint: disable=broad-exception-caught
            execution = _create_execution(task_type=TaskType.TRADING, task_id=task_id)
    else:
        execution = _create_execution(task_type=TaskType.TRADING, task_id=task_id)
    execution.add_log("INFO", "=== Trading execution started ===")

    instrument = str((task.config.parameters or {}).get("instrument") or "") or None
    event_service.log_event(
        event_type="trading_task_started",
        severity="info",
        description=f"Trading execution started for task {task_id}",
        user=task.user,
        account=getattr(task, "oanda_account", None),
        instrument=instrument,
        task_type=TaskType.TRADING,
        task_id=task_id,
        execution=execution,
        details={
            "strategy_type": str(task.config.strategy_type),
            "celery_task_id": _current_task_id(),
        },
    )

    # Strategy
    strategy_type = str(task.config.strategy_type)
    config = dict(task.config.parameters or {})
    strategy = strategy_registry.create(identifier=strategy_type, config=config)

    state: dict[str, Any] = dict(task.strategy_state or {})
    trade_log: list[dict[str, Any]] = []
    strategy_events: list[dict[str, Any]] = []
    realized_pips = Decimal("0")

    state, start_events = strategy.on_start(state=state)
    if start_events:
        strategy_events.extend(start_events)
        for e in start_events:
            e_type = str(e.get("type") or "")
            # Persist to execution logs and echo to Celery stdout.
            try:
                msg = _format_strategy_event(event=e, tick_ts=None)
                execution.add_log("INFO", msg)
                logger.info(
                    "Trading strategy event (task_id=%s, type=%s): %s", task_id, e_type, msg
                )
            except Exception:  # pylint: disable=broad-exception-caught
                pass
            event_service.log_event(
                event_type=(f"strategy_{e_type}"[:64] if e_type else "strategy_event"),
                severity="info",
                description=f"Strategy event ({strategy_type}) for trading task {task_id}",
                user=task.user,
                account=getattr(task, "oanda_account", None),
                instrument=instrument,
                task_type=TaskType.TRADING,
                task_id=task_id,
                execution=execution,
                details={"event": e, "strategy_type": strategy_type},
            )

    client = _redis_client()
    channel = getattr(settings, "MARKET_TICK_CHANNEL")
    pubsub = client.pubsub(ignore_subscribe_messages=True)

    processed = 0
    last_task_status = str(task.status)
    last_status_check_monotonic = time.monotonic()
    try:
        pubsub.subscribe(channel)
        while True:
            if task_service.should_stop():
                execution.add_log("INFO", "Stop requested via CeleryTaskStatus")

                state, stop_events = strategy.on_stop(state=state)
                if stop_events:
                    strategy_events.extend(stop_events)
                    for e in stop_events:
                        e_type = str(e.get("type") or "")
                        try:
                            msg = _format_strategy_event(event=e, tick_ts=None)
                            execution.add_log("INFO", msg)
                            logger.info(
                                "Trading strategy event (task_id=%s, type=%s): %s",
                                task_id,
                                e_type,
                                msg,
                            )
                        except Exception:  # pylint: disable=broad-exception-caught
                            pass
                        event_service.log_event(
                            event_type=(f"strategy_{e_type}"[:64] if e_type else "strategy_event"),
                            severity="info",
                            description=(
                                f"Strategy event ({strategy_type}) for trading task {task_id}"
                            ),
                            user=task.user,
                            account=getattr(task, "oanda_account", None),
                            instrument=instrument,
                            task_type=TaskType.TRADING,
                            task_id=task_id,
                            execution=execution,
                            details={"event": e, "strategy_type": strategy_type},
                        )
                event_service.log_event(
                    event_type="trading_task_stop_detected",
                    severity="info",
                    description=f"Stop detected for trading task {task_id}",
                    user=task.user,
                    account=getattr(task, "oanda_account", None),
                    instrument=instrument,
                    task_type=TaskType.TRADING,
                    task_id=task_id,
                    execution=execution,
                    details={"processed": processed},
                )
                break

            # Respect persisted task lifecycle (pause/stop)
            now_mono = time.monotonic()
            if (now_mono - last_status_check_monotonic) >= 2.0:
                current_status = (
                    TradingTask.objects.filter(pk=task_id).values_list("status", flat=True).first()
                )
                if current_status is not None:
                    current_status_str = str(current_status)
                    if current_status_str != last_task_status:
                        if current_status_str == str(TaskStatus.PAUSED):
                            state, ctrl_events = strategy.on_pause(state=state)
                        elif current_status_str == str(
                            TaskStatus.RUNNING
                        ) and last_task_status == str(TaskStatus.PAUSED):
                            state, ctrl_events = strategy.on_resume(state=state)
                        elif current_status_str == str(TaskStatus.STOPPED):
                            state, ctrl_events = strategy.on_stop(state=state)
                        else:
                            ctrl_events = []

                        if ctrl_events:
                            strategy_events.extend(ctrl_events)
                            for e in ctrl_events:
                                e_type = str(e.get("type") or "")
                                try:
                                    msg = _format_strategy_event(event=e, tick_ts=None)
                                    execution.add_log("INFO", msg)
                                    logger.info(
                                        "Trading strategy event (task_id=%s, type=%s): %s",
                                        task_id,
                                        e_type,
                                        msg,
                                    )
                                except Exception:  # pylint: disable=broad-exception-caught
                                    pass
                                event_service.log_event(
                                    event_type=(
                                        f"strategy_{e_type}"[:64] if e_type else "strategy_event"
                                    ),
                                    severity="info",
                                    description=(
                                        f"Strategy event ({strategy_type}) "
                                        f"for trading task {task_id}"
                                    ),
                                    user=task.user,
                                    account=getattr(task, "oanda_account", None),
                                    instrument=instrument,
                                    task_type=TaskType.TRADING,
                                    task_id=task_id,
                                    execution=execution,
                                    details={
                                        "event": e,
                                        "strategy_type": strategy_type,
                                        "previous_task_status": last_task_status,
                                        "current_task_status": current_status_str,
                                    },
                                )

                        last_task_status = current_status_str
                        if current_status_str == str(TaskStatus.STOPPED):
                            execution.add_log("INFO", "Stop requested via TradingTask.status")
                            break

                last_status_check_monotonic = now_mono

            message = pubsub.get_message(timeout=1.0)
            if not message:
                task_service.heartbeat(
                    status_message=f"processed={processed}", meta_update={"processed": processed}
                )
                continue

            if message.get("type") != "message":
                continue

            payload_raw = message.get("data")
            try:
                payload = json.loads(payload_raw) if isinstance(payload_raw, str) else {}
            except Exception:  # pylint: disable=broad-exception-caught
                continue

            # Normalize tick
            bid_s = str(payload.get("bid") or "")
            ask_s = str(payload.get("ask") or "")
            mid_s = str(payload.get("mid") or "")

            def _is_missing_num(s: str) -> bool:
                x = (s or "").strip().lower()
                return x == "" or x in {"none", "null", "nan"}

            if _is_missing_num(mid_s):
                try:
                    if not _is_missing_num(bid_s) and not _is_missing_num(ask_s):
                        mid_s = str((Decimal(bid_s) + Decimal(ask_s)) / Decimal("2"))
                except Exception:  # pylint: disable=broad-exception-caught
                    pass

            tick = {
                "instrument": str(payload.get("instrument") or ""),
                "timestamp": str(payload.get("timestamp") or ""),
                "bid": bid_s,
                "ask": ask_s,
                "mid": mid_s,
            }

            state, events = strategy.on_tick(tick=tick, state=state)
            if events:
                strategy_events.extend(events)
                for e in events:
                    trade = _extract_trade_from_strategy_event(e)
                    if trade is not None:
                        trade_log.append(trade)
                for e in events:
                    e_type = str(e.get("type") or "")

                    # Persist all strategy events (not just open/close).
                    try:
                        msg = _format_strategy_event(event=e, tick_ts=tick.get("timestamp"))
                        execution.add_log("INFO", msg)
                        logger.info(
                            "Trading strategy event (task_id=%s, type=%s): %s",
                            task_id,
                            e_type,
                            msg,
                        )
                    except Exception:  # pylint: disable=broad-exception-caught
                        pass

                    if e_type == "close":
                        details_raw = e.get("details")
                        if isinstance(details_raw, dict) and details_raw.get("pips") is not None:
                            try:
                                realized_pips += Decimal(str(details_raw.get("pips")))
                            except Exception:  # pylint: disable=broad-exception-caught
                                pass

                    if e_type in {"open", "close"}:
                        event_type = f"trade_{e_type}"
                        description = f"Trade {e_type} event for trading task {task_id}"
                    else:
                        event_type = f"strategy_{e_type}"[:64] if e_type else "strategy_event"
                        description = f"Strategy event ({strategy_type}) for trading task {task_id}"

                    event_service.log_event(
                        event_type=event_type,
                        severity="info",
                        description=description,
                        user=task.user,
                        account=getattr(task, "oanda_account", None),
                        instrument=instrument,
                        task_type=TaskType.TRADING,
                        task_id=task_id,
                        execution=execution,
                        details={
                            "event": e,
                            "strategy_type": strategy_type,
                            "processed": processed,
                            "tick": tick,
                        },
                    )

            processed += 1
            if processed % 50 == 0:
                task.strategy_state = state
                task.save(update_fields=["strategy_state", "updated_at"])

                # Persist best-effort live snapshot for frontend polling.
                try:
                    unrealized_pips: str | None = None
                    if instrument and strategy_type == "floor":
                        snap = LivePerformanceService.compute_floor_unrealized_snapshot(
                            instrument=str(instrument), strategy_state=state
                        )
                        unrealized_pips = str(snap.unrealized_pips)

                    LivePerformanceService.store_trading_intermediate_results(
                        task_id,
                        {
                            "task_type": "trading",
                            "processed": processed,
                            "strategy_type": strategy_type,
                            "instrument": instrument,
                            "realized_pips": str(realized_pips),
                            "unrealized_pips": unrealized_pips,
                        },
                    )
                except Exception:  # pylint: disable=broad-exception-caught
                    pass
                task_service.heartbeat(
                    status_message=f"processed={processed}",
                    meta_update={"processed": processed},
                )

    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.exception("Trading task crashed: %s", exc)

        event_service.log_event(
            event_type="trading_task_failed",
            severity="error",
            description=str(exc),
            user=getattr(task, "user", None),
            account=getattr(task, "oanda_account", None),
            instrument=instrument,
            task_type=TaskType.TRADING,
            task_id=task_id,
            execution=execution,
            details={"processed": processed},
        )

        _finalize_execution_failure(execution, exc)
        task.status = TaskStatus.FAILED
        task.save(update_fields=["status", "updated_at"])
        task_service.mark_stopped(status=CeleryTaskStatus.Status.FAILED, status_message=str(exc))
        raise

    finally:
        try:
            pubsub.close()
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        try:
            client.close()
        except Exception:  # pylint: disable=broad-exception-caught
            pass

    state, final_stop_events = strategy.on_stop(state=state)
    if final_stop_events:
        strategy_events.extend(final_stop_events)
        for e in final_stop_events:
            e_type = str(e.get("type") or "")
            try:
                msg = _format_strategy_event(event=e, tick_ts=None)
                execution.add_log("INFO", msg)
                logger.info(
                    "Trading strategy event (task_id=%s, type=%s): %s", task_id, e_type, msg
                )
            except Exception:  # pylint: disable=broad-exception-caught
                pass
            event_service.log_event(
                event_type=(f"strategy_{e_type}"[:64] if e_type else "strategy_event"),
                severity="info",
                description=f"Strategy event ({strategy_type}) for trading task {task_id}",
                user=task.user,
                account=getattr(task, "oanda_account", None),
                instrument=instrument,
                task_type=TaskType.TRADING,
                task_id=task_id,
                execution=execution,
                details={"event": e, "strategy_type": strategy_type},
            )

    # Persist final state
    task.strategy_state = state
    task.status = TaskStatus.STOPPED
    task.save(update_fields=["strategy_state", "status", "updated_at"])

    event_service.log_event(
        event_type="trading_task_stopped",
        severity="info",
        description=f"Trading task {task_id} stopped",
        user=task.user,
        account=getattr(task, "oanda_account", None),
        instrument=instrument,
        task_type=TaskType.TRADING,
        task_id=task_id,
        execution=execution,
        details={"processed": processed},
    )

    # Metrics snapshot for this execution (immutable record)
    try:
        metrics = ExecutionMetrics(execution=execution)
        initial_balance = Decimal(str(getattr(task.oanda_account, "balance", "0") or "0"))
        metrics.calculate_from_trades(trade_log, initial_balance=initial_balance)
        metrics.strategy_events = strategy_events
        metrics.save()
    except Exception:  # pylint: disable=broad-exception-caught
        # Don't fail task shutdown if metrics fails.
        pass

    _finalize_execution_success(execution)
    task_service.mark_stopped(
        status=CeleryTaskStatus.Status.STOPPED, status_message=f"processed={processed}"
    )


@shared_task(name="trading.tasks.run_backtest_task")
def run_backtest_task(task_id: int, execution_id: int | None = None) -> None:
    """Run a backtest task by subscribing to the Market backtest tick channel."""

    _ensure_strategies_registered()

    task_name = "trading.tasks.run_backtest_task"
    instance_key = str(task_id)
    task_service = CeleryTaskService(
        task_name=task_name,
        instance_key=instance_key,
        stop_check_interval_seconds=1.0,
        heartbeat_interval_seconds=5.0,
    )
    task_service.start(
        celery_task_id=_current_task_id(),
        worker=_lock_value(),
        meta={"kind": "backtest", "task_id": task_id},
    )

    logger.info(
        "Backtest task started (task_id=%s, celery_task_id=%s)",
        task_id,
        _current_task_id(),
    )

    event_service = TradingEventService()

    try:
        task = BacktestTask.objects.select_related("config", "user").get(pk=task_id)
    except BacktestTask.DoesNotExist:
        event_service.log_event(
            event_type="backtest_task_not_found",
            severity="error",
            description=f"BacktestTask {task_id} not found",
            task_type=TaskType.BACKTEST,
            task_id=task_id,
        )
        task_service.mark_stopped(
            status=CeleryTaskStatus.Status.FAILED, status_message="Task not found"
        )
        return

    execution: TaskExecution
    if execution_id is not None:
        try:
            execution = TaskExecution.objects.get(
                pk=int(execution_id),
                task_type=TaskType.BACKTEST,
                task_id=task_id,
            )
            if execution.status != TaskStatus.RUNNING or execution.progress != 0:
                execution.status = TaskStatus.RUNNING
                execution.progress = 0
            if execution.started_at is None:
                execution.started_at = dj_timezone.now()
            execution.save(update_fields=["status", "progress", "started_at"])
        except Exception:  # pylint: disable=broad-exception-caught
            execution = _create_execution(task_type=TaskType.BACKTEST, task_id=task_id)
    else:
        execution = _create_execution(task_type=TaskType.BACKTEST, task_id=task_id)
    execution.add_log("INFO", "=== Backtest execution started ===")

    strategy_type = str(task.config.strategy_type)
    config = dict(task.config.parameters or {})
    strategy = strategy_registry.create(identifier=strategy_type, config=config)

    logger.info(
        "Backtest strategy created (task_id=%s, strategy_type=%s)",
        task_id,
        strategy_type,
    )
    try:
        execution.add_log("INFO", f"Strategy created: {strategy_type}")
    except Exception:  # pylint: disable=broad-exception-caught
        pass

    state: dict[str, Any] = {}
    strategy_events: list[dict[str, Any]] = []
    realized_pips = Decimal("0")

    instrument = str(config.get("instrument") or "")

    state, start_events = strategy.on_start(state=state)
    logger.info(
        "Backtest strategy on_start completed (task_id=%s, strategy_type=%s, start_events=%s)",
        task_id,
        strategy_type,
        len(start_events or []),
    )
    if start_events:
        strategy_events.extend(start_events)
        for e in start_events:
            e_type = str(e.get("type") or "")
            try:
                msg = _format_strategy_event(event=e, tick_ts=None)
                execution.add_log("INFO", msg)
                logger.info(
                    "Backtest strategy event (task_id=%s, type=%s): %s", task_id, e_type, msg
                )
            except Exception:  # pylint: disable=broad-exception-caught
                pass
            event_service.log_event(
                event_type=(f"strategy_{e_type}"[:64] if e_type else "strategy_event"),
                severity="info",
                description=f"Strategy event ({strategy_type}) for backtest task {task_id}",
                user=task.user,
                instrument=instrument or None,
                task_type=TaskType.BACKTEST,
                task_id=task_id,
                execution=execution,
                details={"event": e, "strategy_type": strategy_type},
            )

    # Request market to publish bounded historical ticks
    request_id = f"backtest:{task_id}:{int(time.time())}"
    channel = _backtest_channel_for_request(request_id)

    start = _isoformat(task.start_time)
    end = _isoformat(task.end_time)

    # Progress tracking: tick counts are only known at EOF, so estimate progress
    # during the run using tick timestamps within the requested time window.
    backtest_start_dt: datetime | None = None
    backtest_end_dt: datetime | None = None
    backtest_total_seconds: float | None = None
    try:
        backtest_start_dt = _parse_iso_datetime(start)
        backtest_end_dt = _parse_iso_datetime(end)
        total = (backtest_end_dt - backtest_start_dt).total_seconds()
        backtest_total_seconds = total if total > 0 else None
    except Exception:  # pylint: disable=broad-exception-caught
        backtest_start_dt = None
        backtest_end_dt = None
        backtest_total_seconds = None

    event_service.log_event(
        event_type="backtest_task_started",
        severity="info",
        description=f"Backtest execution started for task {task_id}",
        user=task.user,
        instrument=instrument or None,
        task_type=TaskType.BACKTEST,
        task_id=task_id,
        execution=execution,
        details={
            "strategy_type": str(task.config.strategy_type),
            "celery_task_id": _current_task_id(),
            "start": start,
            "end": end,
        },
    )

    client = _redis_client()
    pubsub = client.pubsub(ignore_subscribe_messages=True)

    # Subscribe before triggering the publisher task.
    # Redis pub/sub does not replay messages, so if the publisher starts first
    # we can miss initial ticks and/or the EOF marker and hang.
    pubsub.subscribe(channel)

    logger.info(
        "Backtest subscribed to tick channel (task_id=%s, request_id=%s, channel=%s)",
        task_id,
        request_id,
        channel,
    )
    try:
        execution.add_log("INFO", f"Subscribed to tick channel: {channel}")
    except Exception:  # pylint: disable=broad-exception-caught
        pass

    from apps.market.tasks import publish_ticks_for_backtest

    cast(Any, getattr(publish_ticks_for_backtest, "delay"))(
        instrument=instrument,
        start=start,
        end=end,
        request_id=request_id,
    )

    logger.info(
        "Backtest enqueued tick publisher (task_id=%s, request_id=%s, instrument=%s, start=%s, end=%s)",
        task_id,
        request_id,
        instrument,
        start,
        end,
    )
    try:
        execution.add_log("INFO", f"Enqueued tick publisher (request_id={request_id})")
    except Exception:  # pylint: disable=broad-exception-caught
        pass

    trade_log: list[dict[str, Any]] = []

    entry_signal_lookback_ticks = int(config.get("entry_signal_lookback_ticks") or 0)
    ticks_missing_mid = 0

    processed = 0
    published_total: int | None = None

    summary_emitted = False

    last_message_monotonic = time.monotonic()
    last_tick_timestamp: str | None = None
    next_idle_log_at = last_message_monotonic + 30.0
    next_progress_log_at = last_message_monotonic + 15.0
    last_progress_update_monotonic = 0.0

    def _enrich_event_from_tick(*, event: dict[str, Any], tick: dict[str, Any]) -> dict[str, Any]:
        """Ensure strategy events are plottable by attaching timestamp and price.

        Frontend chart markers require:
        - event["timestamp"] for time placement
        - a price-like field under event["details"] (price/current_price/entry_price/exit_price)
        """
        enriched = dict(event)

        tick_ts = str(tick.get("timestamp") or "")
        if tick_ts and not enriched.get("timestamp"):
            enriched["timestamp"] = tick_ts

        details_raw = enriched.get("details")
        details: dict[str, Any] = details_raw if isinstance(details_raw, dict) else {}
        tick_mid = tick.get("mid")

        # Add a generic current price if no price is present.
        if tick_mid and not any(
            k in details and details.get(k) not in {None, ""}
            for k in {"price", "current_price", "entry_price", "exit_price"}
        ):
            details = dict(details)
            details["current_price"] = tick_mid

        # Close events are easier to plot with an explicit exit price.
        if (
            str(enriched.get("type") or "") == "close"
            and tick_mid
            and not details.get("exit_price")
        ):
            details = dict(details)
            details["exit_price"] = tick_mid

        if details:
            enriched["details"] = details

        return enriched

    def _compute_progress_pct() -> int | None:
        if published_total and published_total > 0:
            return max(0, min(100, int((processed / published_total) * 100)))

        if not (backtest_start_dt and backtest_end_dt and backtest_total_seconds):
            return None

        if not last_tick_timestamp:
            return None

        try:
            tick_dt = _parse_iso_datetime(str(last_tick_timestamp))
        except Exception:  # pylint: disable=broad-exception-caught
            return None

        elapsed = (tick_dt - backtest_start_dt).total_seconds()
        # Clamp to [0, total]
        if elapsed < 0:
            elapsed = 0
        if elapsed > backtest_total_seconds:
            elapsed = backtest_total_seconds

        # Avoid showing 0 forever once we have at least one tick.
        pct = int((elapsed / backtest_total_seconds) * 100)
        return max(1, min(99, pct))

    def _maybe_update_execution_progress(*, now_mono: float, force: bool = False) -> None:
        nonlocal last_progress_update_monotonic
        if not force and (now_mono - last_progress_update_monotonic) < 5.0:
            return

        pct = _compute_progress_pct()
        if pct is None:
            return

        try:
            if int(execution.progress or 0) != int(pct):
                execution.update_progress(int(pct))
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        last_progress_update_monotonic = now_mono

    try:
        while True:
            if task_service.should_stop():
                execution.add_log("INFO", "Stop requested via CeleryTaskStatus")
                event_service.log_event(
                    event_type="backtest_task_stop_detected",
                    severity="info",
                    description=f"Stop detected for backtest task {task_id}",
                    user=task.user,
                    instrument=instrument or None,
                    task_type=TaskType.BACKTEST,
                    task_id=task_id,
                    execution=execution,
                    details={"processed": processed},
                )
                break

            redis_msg = pubsub.get_message(timeout=1.0)
            if not redis_msg:
                now_mono = time.monotonic()
                _maybe_update_execution_progress(now_mono=now_mono)
                if now_mono >= next_idle_log_at:
                    idle_for = int(max(0.0, now_mono - last_message_monotonic))
                    logger.warning(
                        "Backtest waiting for ticks (task_id=%s, request_id=%s, idle_for_s=%s, processed=%s, last_tick_ts=%s)",
                        task_id,
                        request_id,
                        idle_for,
                        processed,
                        last_tick_timestamp,
                    )
                    next_idle_log_at = now_mono + 30.0
                task_service.heartbeat(
                    status_message=(
                        f"processed={processed} last_tick={last_tick_timestamp or 'n/a'}"
                    ),
                    meta_update={
                        "processed": processed,
                        "last_tick": last_tick_timestamp,
                        "progress": int(execution.progress or 0),
                    },
                )
                continue

            if redis_msg.get("type") != "message":
                continue

            raw = redis_msg.get("data")
            try:
                payload = json.loads(raw) if isinstance(raw, str) else {}
            except Exception:  # pylint: disable=broad-exception-caught
                continue

            last_message_monotonic = time.monotonic()
            # After receiving something, delay the idle warning window.
            next_idle_log_at = last_message_monotonic + 30.0

            kind = str(payload.get("type") or "tick")
            if kind == "eof":
                published_total = int(payload.get("count") or processed)
                logger.info(
                    "Backtest received EOF (task_id=%s, request_id=%s, processed=%s, published_total=%s)",
                    task_id,
                    request_id,
                    processed,
                    published_total,
                )
                try:
                    execution.add_log(
                        "INFO",
                        f"EOF received: processed={processed} published_total={published_total}",
                    )
                except Exception:  # pylint: disable=broad-exception-caught
                    pass

                # Emit a strategy summary *immediately* at EOF so it shows up in
                # Celery stdout even if the worker exits quickly or logs are tailed.
                try:
                    s_initialized = bool(state.get("initialized") or False)
                    s_ticks_seen = int(state.get("ticks_seen") or 0)
                    s_active_layers_raw = state.get("active_layers")
                    s_active_layers: list[Any] = (
                        s_active_layers_raw if isinstance(s_active_layers_raw, list) else []
                    )
                    logger.info(
                        "Backtest summary (task_id=%s, processed=%s, ticks_seen=%s, initialized=%s, active_layers=%s, trades=%s, entry_lookback=%s, mid_missing=%s)",
                        task_id,
                        processed,
                        s_ticks_seen,
                        s_initialized,
                        len(s_active_layers),
                        len(trade_log),
                        entry_signal_lookback_ticks,
                        ticks_missing_mid,
                    )
                    summary_emitted = True
                    execution.add_log(
                        "INFO",
                        "Backtest summary: processed=%s ticks_seen=%s initialized=%s active_layers=%s trades=%s entry_lookback=%s mid_missing=%s"
                        % (
                            processed,
                            s_ticks_seen,
                            s_initialized,
                            len(s_active_layers),
                            len(trade_log),
                            entry_signal_lookback_ticks,
                            ticks_missing_mid,
                        ),
                    )
                    if len(trade_log) == 0:
                        execution.add_log(
                            "WARNING",
                            "No trades produced. Common causes: not enough ticks to satisfy entry_signal_lookback_ticks, mid price missing/invalid, or thresholds too strict for the chosen window.",
                        )
                except Exception:  # pylint: disable=broad-exception-caught
                    pass
                break
            if kind in {"stopped", "error"}:
                logger.warning(
                    "Backtest received terminal message (task_id=%s, request_id=%s, type=%s, message=%s)",
                    task_id,
                    request_id,
                    kind,
                    payload.get("message"),
                )
                try:
                    execution.add_log(
                        "WARNING",
                        f"Terminal message received: type={kind} message={payload.get('message')}",
                    )
                except Exception:  # pylint: disable=broad-exception-caught
                    pass
                break
            if kind != "tick":
                continue

            bid_s = str(payload.get("bid") or "")
            ask_s = str(payload.get("ask") or "")
            mid_s = str(payload.get("mid") or "")

            def _is_missing_num(s: str) -> bool:
                x = (s or "").strip().lower()
                return x == "" or x in {"none", "null", "nan"}

            # Strategy expects mid; compute it if missing.
            if _is_missing_num(mid_s):
                try:
                    if not _is_missing_num(bid_s) and not _is_missing_num(ask_s):
                        mid_s = str((Decimal(bid_s) + Decimal(ask_s)) / Decimal("2"))
                except Exception:  # pylint: disable=broad-exception-caught
                    pass

            if _is_missing_num(mid_s):
                ticks_missing_mid += 1

            tick = {
                "instrument": str(payload.get("instrument") or ""),
                "timestamp": str(payload.get("timestamp") or ""),
                "bid": bid_s,
                "ask": ask_s,
                "mid": mid_s,
            }

            if not last_tick_timestamp and tick.get("timestamp"):
                logger.info(
                    "Backtest received first tick (task_id=%s, request_id=%s, ts=%s)",
                    task_id,
                    request_id,
                    tick.get("timestamp"),
                )
                try:
                    execution.add_log("INFO", f"First tick received: {tick.get('timestamp')}")
                except Exception:  # pylint: disable=broad-exception-caught
                    pass
            if tick.get("timestamp"):
                last_tick_timestamp = str(tick.get("timestamp"))

            state, events = strategy.on_tick(tick=tick, state=state)
            if events:
                enriched_events = [
                    _enrich_event_from_tick(event=e, tick=tick)
                    for e in events
                    if isinstance(e, dict)
                ]

                strategy_events.extend(enriched_events)
                for e in enriched_events:
                    trade = _extract_trade_from_strategy_event(e)
                    if trade is not None:
                        trade_log.append(trade)
                for e in enriched_events:
                    e_type = str(e.get("type") or "")

                    # Persist all strategy events (layer opens/scales, take-profit hits, etc).
                    try:
                        msg = _format_strategy_event(event=e, tick_ts=tick.get("timestamp"))
                        execution.add_log("INFO", msg)
                        logger.info(
                            "Backtest strategy event (task_id=%s, type=%s): %s",
                            task_id,
                            e_type,
                            msg,
                        )
                    except Exception:  # pylint: disable=broad-exception-caught
                        pass

                    if e_type == "close":
                        details_raw = e.get("details")
                        if isinstance(details_raw, dict) and details_raw.get("pips") is not None:
                            try:
                                realized_pips += Decimal(str(details_raw.get("pips")))
                            except Exception:  # pylint: disable=broad-exception-caught
                                pass

                    if e_type in {"open", "close"}:
                        event_type = f"trade_{e_type}"
                        description = f"Trade {e_type} event for backtest task {task_id}"
                    else:
                        event_type = f"strategy_{e_type}"[:64] if e_type else "strategy_event"
                        description = (
                            f"Strategy event ({strategy_type}) for backtest task {task_id}"
                        )

                    event_service.log_event(
                        event_type=event_type,
                        severity="info",
                        description=description,
                        user=task.user,
                        instrument=instrument or None,
                        task_type=TaskType.BACKTEST,
                        task_id=task_id,
                        execution=execution,
                        details={
                            "event": e,
                            "strategy_type": strategy_type,
                            "processed": processed,
                            "tick": tick,
                        },
                    )

            processed += 1

            now_mono = time.monotonic()
            if now_mono >= next_progress_log_at:
                logger.info(
                    "Backtest processing progress (task_id=%s, request_id=%s, processed=%s, last_tick_ts=%s)",
                    task_id,
                    request_id,
                    processed,
                    last_tick_timestamp,
                )
                next_progress_log_at = now_mono + 15.0

            if processed % 250 == 0:
                # Update progress periodically. Prefer count-based when available,
                # otherwise use timestamp-based estimation.
                _maybe_update_execution_progress(now_mono=time.monotonic(), force=True)

                # Persist best-effort live snapshot for frontend polling.
                try:
                    unrealized_pips: str | None = None
                    if instrument and strategy_type == "floor":
                        snap = LivePerformanceService.compute_floor_unrealized_snapshot(
                            instrument=str(instrument), strategy_state=state
                        )
                        unrealized_pips = str(snap.unrealized_pips)

                    LivePerformanceService.store_backtest_intermediate_results(
                        task_id,
                        {
                            "task_type": "backtest",
                            "processed": processed,
                            "published_total": published_total,
                            "strategy_type": strategy_type,
                            "instrument": instrument,
                            "realized_pips": str(realized_pips),
                            "unrealized_pips": unrealized_pips,
                            "progress": int(execution.progress or 0),
                        },
                    )
                except Exception:  # pylint: disable=broad-exception-caught
                    pass
                task_service.heartbeat(
                    status_message=f"processed={processed}",
                    meta_update={
                        "processed": processed,
                        "last_tick": last_tick_timestamp,
                        "progress": int(execution.progress or 0),
                        "published_total": published_total,
                    },
                )

        # final progress
        execution.update_progress(100)

    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.exception("Backtest task crashed: %s", exc)

        event_service.log_event(
            event_type="backtest_task_failed",
            severity="error",
            description=str(exc),
            user=getattr(task, "user", None),
            instrument=instrument or None,
            task_type=TaskType.BACKTEST,
            task_id=task_id,
            execution=execution,
            details={"processed": processed},
        )

        _finalize_execution_failure(execution, exc)
        task.status = TaskStatus.FAILED
        task.save(update_fields=["status", "updated_at"])
        task_service.mark_stopped(status=CeleryTaskStatus.Status.FAILED, status_message=str(exc))
        raise

    finally:
        try:
            pubsub.close()
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        try:
            client.close()
        except Exception:  # pylint: disable=broad-exception-caught
            pass

    # Persist metrics & final status
    try:
        metrics = ExecutionMetrics(execution=execution)
        metrics.calculate_from_trades(trade_log, initial_balance=Decimal(str(task.initial_balance)))
        metrics.strategy_events = strategy_events
        metrics.save()
    except Exception:  # pylint: disable=broad-exception-caught
        pass

    # End-of-run diagnostics to help explain "strategy did nothing" cases.
    try:
        if summary_emitted:
            raise RuntimeError("summary already emitted")
        s_initialized = bool(state.get("initialized") or False)
        s_ticks_seen = int(state.get("ticks_seen") or 0)
        s_active_layers_raw = state.get("active_layers")
        s_active_layers_end: list[Any] = (
            s_active_layers_raw if isinstance(s_active_layers_raw, list) else []
        )

        logger.info(
            "Backtest summary (task_id=%s, processed=%s, ticks_seen=%s, initialized=%s, active_layers=%s, trades=%s, entry_lookback=%s, mid_missing=%s)",
            task_id,
            processed,
            s_ticks_seen,
            s_initialized,
            len(s_active_layers_end),
            len(trade_log),
            entry_signal_lookback_ticks,
            ticks_missing_mid,
        )
        execution.add_log(
            "INFO",
            "Backtest summary: processed=%s ticks_seen=%s initialized=%s active_layers=%s trades=%s entry_lookback=%s mid_missing=%s"
            % (
                processed,
                s_ticks_seen,
                s_initialized,
                len(s_active_layers_end),
                len(trade_log),
                entry_signal_lookback_ticks,
                ticks_missing_mid,
            ),
        )
        if len(trade_log) == 0:
            execution.add_log(
                "WARNING",
                "No trades produced. Common causes: not enough ticks to satisfy entry_signal_lookback_ticks, mid price missing/invalid, or thresholds too strict for the chosen window.",
            )
    except Exception:  # pylint: disable=broad-exception-caught
        pass

    task.status = TaskStatus.COMPLETED
    task.save(update_fields=["status", "updated_at"])

    event_service.log_event(
        event_type="backtest_task_completed",
        severity="info",
        description=f"Backtest task {task_id} completed",
        user=task.user,
        instrument=instrument or None,
        task_type=TaskType.BACKTEST,
        task_id=task_id,
        execution=execution,
        details={"processed": processed, "published_total": published_total},
    )

    _finalize_execution_success(execution)
    task_service.mark_stopped(
        status=CeleryTaskStatus.Status.COMPLETED, status_message=f"processed={processed}"
    )
