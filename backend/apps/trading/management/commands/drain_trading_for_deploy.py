"""Gracefully stop active trading tasks before deployment."""

from __future__ import annotations

import time
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.trading.models import TradingTask
from apps.trading.enums import TaskStatus
from apps.trading.tasks.service import TaskService


class Command(BaseCommand):
    """Drain live trading tasks before replacing worker containers."""

    help = "Stop active trading tasks and wait for the workers to quiesce"

    active_statuses = (
        TaskStatus.STARTING,
        TaskStatus.RUNNING,
        TaskStatus.STOPPING,
    )

    def add_arguments(self, parser: Any) -> None:
        """Add command arguments."""
        parser.add_argument(
            "--mode",
            type=str,
            default="graceful",
            choices=["immediate", "graceful", "graceful_close"],
            help="Stop mode to request for active trading tasks.",
        )
        parser.add_argument(
            "--timeout",
            type=int,
            default=180,
            help="Seconds to wait for active trading tasks to stop.",
        )
        parser.add_argument(
            "--poll-interval",
            type=float,
            default=2.0,
            help="Seconds between status checks while draining.",
        )
        parser.add_argument(
            "--emit-task-ids",
            action="store_true",
            help="Emit drained trading task IDs in a machine-readable format.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """Handle the command."""
        timeout = max(1, int(options["timeout"]))
        poll_interval = max(0.1, float(options["poll_interval"]))
        stop_mode = str(options["mode"])
        emit_task_ids = bool(options["emit_task_ids"])

        service = TaskService()
        active_tasks = list(
            TradingTask.objects.select_related("config", "oanda_account", "user")
            .filter(status__in=self.active_statuses)
            .order_by("created_at")
        )

        if not active_tasks:
            self.stdout.write("No active trading tasks to drain.")
            if emit_task_ids:
                self.stdout.write("DRAINED_TASK_IDS=")
            return

        resumable_tasks = [
            task
            for task in active_tasks
            if task.status in (TaskStatus.STARTING, TaskStatus.RUNNING)
        ]
        drained_task_ids = ",".join(str(task.pk) for task in resumable_tasks)

        self.stdout.write(
            self.style.WARNING(
                f"Draining {len(active_tasks)} active trading task(s) with mode={stop_mode}."
            )
        )

        for task in active_tasks:
            self.stdout.write(
                f"- Requesting {stop_mode} for {task.pk} "
                f"({task.name}, strategy={task.config.strategy_type}, account={task.oanda_account.account_id}, "
                f"status={task.status})"
            )
            try:
                service.stop_task(task.pk, mode=stop_mode)
            except ValueError as exc:
                raise CommandError(f"Failed to transition trading task {task.pk}: {exc}") from exc

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            remaining = self._get_remaining_tasks(
                stop_mode=stop_mode,
                resumable_tasks=resumable_tasks,
            )
            if not remaining:
                self.stdout.write(self.style.SUCCESS("All active trading tasks drained."))
                if emit_task_ids:
                    self.stdout.write(f"DRAINED_TASK_IDS={drained_task_ids}")
                return

            summary = ", ".join(
                f"{task.pk}:{task.status}:{task.config.strategy_type}:{task.oanda_account.account_id}"
                for task in remaining
            )
            self.stdout.write(f"Waiting for {len(remaining)} task(s): {summary}")
            time.sleep(poll_interval)

        remaining = self._get_remaining_tasks(
            stop_mode=stop_mode,
            resumable_tasks=resumable_tasks,
        )
        summary = ", ".join(
            f"{task.pk}:{task.status}:{task.config.strategy_type}:{task.oanda_account.account_id}"
            for task in remaining
        )
        raise CommandError(
            "Timed out draining active trading tasks before deployment. "
            f"Remaining task(s): {summary}"
        )

    def _get_remaining_tasks(
        self, *, stop_mode: str, resumable_tasks: list[TradingTask]
    ) -> list[TradingTask]:
        """Return tasks that are not yet safe for deployment."""
        return list(
            TradingTask.objects.select_related("config", "oanda_account", "user")
            .filter(status__in=self.active_statuses)
            .order_by("created_at")
        )
