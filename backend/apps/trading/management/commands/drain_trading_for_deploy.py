"""Gracefully stop active trading tasks before deployment."""

from __future__ import annotations

import time
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.trading.enums import TaskStatus
from apps.trading.models import TradingTask
from apps.trading.tasks.service import TaskService


class Command(BaseCommand):
    """Drain live trading tasks before replacing worker containers."""

    help = "Gracefully stop active trading tasks and wait for them to become terminal"

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

    def handle(self, *args: Any, **options: Any) -> None:
        """Handle the command."""
        timeout = max(1, int(options["timeout"]))
        poll_interval = max(0.1, float(options["poll_interval"]))
        stop_mode = str(options["mode"])

        service = TaskService()
        active_tasks = list(
            TradingTask.objects.select_related("config", "oanda_account", "user")
            .filter(status__in=self.active_statuses)
            .order_by("created_at")
        )

        if not active_tasks:
            self.stdout.write("No active trading tasks to drain.")
            return

        self.stdout.write(
            self.style.WARNING(
                f"Draining {len(active_tasks)} active trading task(s) with mode={stop_mode}."
            )
        )

        for task in active_tasks:
            self.stdout.write(
                f"- Requesting stop for {task.pk} "
                f"({task.name}, strategy={task.config.strategy_type}, account={task.oanda_account.account_id}, "
                f"status={task.status})"
            )
            try:
                service.stop_task(task.pk, mode=stop_mode)
            except ValueError as exc:
                raise CommandError(f"Failed to stop trading task {task.pk}: {exc}") from exc

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            remaining = list(
                TradingTask.objects.select_related("config", "oanda_account", "user")
                .filter(status__in=self.active_statuses)
                .order_by("created_at")
            )
            if not remaining:
                self.stdout.write(self.style.SUCCESS("All active trading tasks drained."))
                return

            summary = ", ".join(
                f"{task.pk}:{task.status}:{task.config.strategy_type}:{task.oanda_account.account_id}"
                for task in remaining
            )
            self.stdout.write(f"Waiting for {len(remaining)} task(s): {summary}")
            time.sleep(poll_interval)

        remaining = list(
            TradingTask.objects.select_related("config", "oanda_account", "user")
            .filter(status__in=self.active_statuses)
            .order_by("created_at")
        )
        summary = ", ".join(
            f"{task.pk}:{task.status}:{task.config.strategy_type}:{task.oanda_account.account_id}"
            for task in remaining
        )
        raise CommandError(
            "Timed out draining active trading tasks before deployment. "
            f"Remaining task(s): {summary}"
        )
