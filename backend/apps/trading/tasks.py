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
def run_trading_task(task_id: int) -> None:
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
            tick = {
                "instrument": str(payload.get("instrument") or ""),
                "timestamp": str(payload.get("timestamp") or ""),
                "bid": str(payload.get("bid") or ""),
                "ask": str(payload.get("ask") or ""),
                "mid": str(payload.get("mid") or ""),
            }

            state, events = strategy.on_tick(tick=tick, state=state)
            if events:
                strategy_events.extend(events)
                trade_log.extend([e for e in events if e.get("type") in {"open", "close"}])
                execution.add_log("INFO", f"events={len(events)}")

                for e in events:
                    e_type = str(e.get("type") or "")
                    if e_type == "close":
                        details = e.get("details")
                        if isinstance(details, dict) and details.get("pips") is not None:
                            try:
                                realized_pips += Decimal(str(details.get("pips")))
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
def run_backtest_task(task_id: int) -> None:
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

    execution = _create_execution(task_type=TaskType.BACKTEST, task_id=task_id)
    execution.add_log("INFO", "=== Backtest execution started ===")

    strategy_type = str(task.config.strategy_type)
    config = dict(task.config.parameters or {})
    strategy = strategy_registry.create(identifier=strategy_type, config=config)

    state: dict[str, Any] = {}
    strategy_events: list[dict[str, Any]] = []
    realized_pips = Decimal("0")

    instrument = str(config.get("instrument") or "")

    state, start_events = strategy.on_start(state=state)
    if start_events:
        strategy_events.extend(start_events)
        for e in start_events:
            e_type = str(e.get("type") or "")
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

    from apps.market.tasks import publish_ticks_for_backtest

    cast(Any, getattr(publish_ticks_for_backtest, "delay"))(
        instrument=instrument,
        start=start,
        end=end,
        request_id=request_id,
    )

    client = _redis_client()
    pubsub = client.pubsub(ignore_subscribe_messages=True)

    trade_log: list[dict[str, Any]] = []

    processed = 0
    published_total: int | None = None

    try:
        pubsub.subscribe(channel)
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

            msg = pubsub.get_message(timeout=1.0)
            if not msg:
                task_service.heartbeat(
                    status_message=f"processed={processed}", meta_update={"processed": processed}
                )
                continue

            if msg.get("type") != "message":
                continue

            raw = msg.get("data")
            try:
                payload = json.loads(raw) if isinstance(raw, str) else {}
            except Exception:  # pylint: disable=broad-exception-caught
                continue

            kind = str(payload.get("type") or "tick")
            if kind == "eof":
                published_total = int(payload.get("count") or processed)
                break
            if kind in {"stopped", "error"}:
                break
            if kind != "tick":
                continue

            tick = {
                "instrument": str(payload.get("instrument") or ""),
                "timestamp": str(payload.get("timestamp") or ""),
                "bid": str(payload.get("bid") or ""),
                "ask": str(payload.get("ask") or ""),
                "mid": str(payload.get("mid") or ""),
            }

            state, events = strategy.on_tick(tick=tick, state=state)
            if events:
                strategy_events.extend(events)
                trade_log.extend([e for e in events if e.get("type") in {"open", "close"}])

                for e in events:
                    e_type = str(e.get("type") or "")
                    if e_type == "close":
                        details = e.get("details")
                        if isinstance(details, dict) and details.get("pips") is not None:
                            try:
                                realized_pips += Decimal(str(details.get("pips")))
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
            if processed % 250 == 0:
                # Best-effort progress estimate when total unknown.
                if published_total and published_total > 0:
                    pct = int((processed / published_total) * 100)
                    execution.update_progress(pct)

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
                    status_message=f"processed={processed}", meta_update={"processed": processed}
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
