"""Validation helpers for task lifecycle commands."""

from __future__ import annotations

from dataclasses import dataclass
from logging import Logger
from typing import Callable

from apps.trading.models import BacktestTask, TradingTask
from apps.trading.services import resume_config
from apps.trading.tasks.lifecycle_state_machine import allowed_statuses_for_command


@dataclass(frozen=True)
class ResumeCommandValidator:
    """Validate a locked task before a resume transition mutates it."""

    logger: Logger
    ensure_dispatch_risk_guard_allows: Callable[[BacktestTask | TradingTask], None]

    def validate(self, *, task: BacktestTask | TradingTask, task_type: str) -> None:
        """Validate task state, resume configuration, and dispatch risk."""

        command = "resume_trading" if task_type == "trading" else "resume_backtest"
        allowed_statuses = allowed_statuses_for_command(command)
        task_status = task.status
        if allowed_statuses and task_status not in allowed_statuses:
            from apps.trading.tasks.service import TaskValidationError

            allowed = ", ".join(str(status.value).upper() for status in allowed_statuses)
            raise TaskValidationError(
                f"Task cannot be resumed from {task_status} state. "
                f"Only {allowed} tasks can be resumed."
            )

        if not task.execution_id:
            from apps.trading.tasks.service import TaskValidationError

            raise TaskValidationError("Cannot resume task without an execution_id")

        try:
            audit = resume_config.validate_resume_configuration(task=task, task_type=task_type)
            resume_config.log_effective_resume_configuration(
                logger=self.logger,
                audit=audit,
                task=task,
            )
        except resume_config.ResumeConfigurationError as exc:
            from apps.trading.tasks.service import TaskValidationError

            raise TaskValidationError(
                str(exc),
                resume_config_error=exc.as_payload(),
            ) from exc
        except ValueError as exc:
            from apps.trading.tasks.service import TaskValidationError

            raise TaskValidationError(str(exc)) from exc

        self.ensure_dispatch_risk_guard_allows(task)
