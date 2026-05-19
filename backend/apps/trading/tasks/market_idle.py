"""Market-aware idle transitions for task execution."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from django.utils import timezone as dj_timezone

from apps.trading.enums import TaskStatus, TaskType
from apps.trading.services.market_schedule import (
    DEFAULT_SESSION_CONFIG,
    MarketSessionConfig,
    is_forex_market_closed,
    should_enter_pre_close_idle,
    should_resume_from_idle,
)

logger = logging.getLogger(__name__)


class MarketIdleCoordinator:
    """Flip executable tasks between RUNNING and IDLE around market closures."""

    def __init__(self, *, task: Any, task_type: TaskType) -> None:
        self.task = task
        self.task_type = task_type

    def clock(self, loop: Any) -> datetime | None:
        if self.task_type == TaskType.TRADING:
            return dj_timezone.now()
        return loop.last_delivered_tick_timestamp or loop.state.last_tick_timestamp

    def session_config(self) -> MarketSessionConfig:
        if self.task_type != TaskType.BACKTEST:
            return DEFAULT_SESSION_CONFIG

        task = self.task
        holidays_enabled_raw = getattr(task, "holidays_enabled", False)
        holidays_enabled = (
            bool(holidays_enabled_raw) if isinstance(holidays_enabled_raw, bool) else False
        )
        excluded_dates_raw = getattr(task, "excluded_dates", None)
        excluded_dates: list = (
            list(excluded_dates_raw) if isinstance(excluded_dates_raw, list) else []
        )

        if holidays_enabled or excluded_dates:
            from apps.trading.services.market_holidays import resolve_holiday_dates

            start_dt = getattr(task, "start_time", None)
            end_dt = getattr(task, "end_time", None)
            start_date = start_dt.date() if isinstance(start_dt, datetime) else None
            end_date = end_dt.date() if isinstance(end_dt, datetime) else None
            holiday_dates = resolve_holiday_dates(
                enabled=holidays_enabled,
                start=start_date,
                end=end_date,
                excluded_dates=excluded_dates,
            )
        else:
            holiday_dates = frozenset()

        return MarketSessionConfig(
            enabled=bool(getattr(task, "market_close_enabled", True)),
            close_weekday=int(getattr(task, "market_close_weekday", 4) or 0),
            close_hour_utc=int(getattr(task, "market_close_hour_utc", 21) or 0),
            open_weekday=int(getattr(task, "market_open_weekday", 6) or 0),
            open_hour_utc=int(getattr(task, "market_open_hour_utc", 21) or 0),
            holiday_dates=holiday_dates,
        )

    def evaluate(self, loop: Any) -> None:
        """Apply the task's market-idle policy for the current task clock."""
        now = self.clock(loop)
        if now is None:
            return

        task = self.task
        pre_close_minutes = int(getattr(task, "market_idle_pre_close_minutes", 0) or 0)
        resume_delay_minutes = int(getattr(task, "market_idle_resume_delay_minutes", 0) or 0)
        session_config = self.session_config()

        if self.task_type == TaskType.BACKTEST:
            if not session_config.enabled and not session_config.has_holiday_calendar:
                return
            if (
                pre_close_minutes == 0
                and resume_delay_minutes == 0
                and not is_forex_market_closed(now, config=session_config)
            ):
                return

        task.refresh_from_db(fields=["status"])
        if task.status not in (TaskStatus.RUNNING, TaskStatus.IDLE):
            return

        market_closed = is_forex_market_closed(now, config=session_config)
        should_idle = market_closed or should_enter_pre_close_idle(
            now=now,
            pre_close_minutes=pre_close_minutes,
            config=session_config,
        )

        if task.status == TaskStatus.RUNNING and should_idle:
            self.enter(loop, now=now, reason="market_closed_or_pre_close")
            return

        if task.status == TaskStatus.IDLE and not should_idle:
            idle_marker = self.read_marker(loop)
            if should_resume_from_idle(
                now=now,
                idle_entered_at=idle_marker,
                resume_delay_minutes=resume_delay_minutes,
                config=session_config,
            ):
                self.exit(loop)

    def enter(self, loop: Any, *, now: datetime, reason: str) -> None:
        task = self.task
        type(task).objects.filter(pk=task.pk, status=TaskStatus.RUNNING).update(
            status=TaskStatus.IDLE,
            updated_at=dj_timezone.now(),
        )
        task.refresh_from_db(fields=["status"])
        logger.info(
            "Task switched to IDLE - task_id=%s, task_type=%s, reason=%s, clock=%s",
            task.pk,
            self.task_type.value,
            reason,
            now.isoformat(),
        )
        self.record_marker(loop, now)

    def exit(self, loop: Any) -> None:
        task = self.task
        type(task).objects.filter(pk=task.pk, status=TaskStatus.IDLE).update(
            status=TaskStatus.RUNNING,
            updated_at=dj_timezone.now(),
        )
        task.refresh_from_db(fields=["status"])
        logger.info(
            "Task resumed from IDLE - task_id=%s, task_type=%s",
            task.pk,
            self.task_type.value,
        )
        self.record_marker(loop, None)

    @staticmethod
    def record_marker(loop: Any, entered_at: datetime | None) -> None:
        strategy_state = (
            loop.state.strategy_state if isinstance(loop.state.strategy_state, dict) else {}
        )
        if entered_at is None:
            strategy_state.pop("_idle_entered_at", None)
        else:
            strategy_state["_idle_entered_at"] = entered_at.isoformat()
        loop.state.strategy_state = strategy_state
        try:
            loop.state.save(update_fields=["strategy_state", "updated_at"])
        except Exception:  # pragma: no cover - best effort persistence
            logger.debug("Failed to persist idle marker", exc_info=True)

    @staticmethod
    def read_marker(loop: Any) -> datetime | None:
        strategy_state = (
            loop.state.strategy_state if isinstance(loop.state.strategy_state, dict) else {}
        )
        raw = strategy_state.get("_idle_entered_at")
        if not raw:
            return None
        try:
            return datetime.fromisoformat(str(raw))
        except ValueError:
            return None
