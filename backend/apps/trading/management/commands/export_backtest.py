"""apps.trading.management.commands.export_backtest

Export backtest results as JSON.

Legacy note:
This command used to export the (now removed) Backtest/BacktestResult models.
Backtests are now represented by BacktestTask + TaskExecution (+ ExecutionMetrics).

Usage:
    python manage.py export_backtest <backtest_task_id>
    python manage.py export_backtest <backtest_task_id> --execution-id <id>
    python manage.py export_backtest <backtest_task_id> --output results.json
"""

import json
import sys
from decimal import Decimal
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.trading.models import BacktestTask, TaskExecution


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal types."""

    def default(self, o: Any) -> Any:  # pylint: disable=method-hidden
        if isinstance(o, Decimal):
            return float(o)
        return super().default(o)


class Command(BaseCommand):
    """Export backtest results to JSON format."""

    help = "Export BacktestTask execution results including metrics/logs to JSON"

    def add_arguments(self, parser: Any) -> None:
        """Add command arguments."""
        parser.add_argument(
            "backtest_task_id",
            type=int,
            help="ID of the BacktestTask to export",
        )
        parser.add_argument(
            "--execution-id",
            type=int,
            help="Specific TaskExecution ID to export (default: latest execution for the task)",
        )
        parser.add_argument(
            "--output",
            "-o",
            type=str,
            help="Output file path (default: stdout)",
        )
        parser.add_argument(
            "--pretty",
            action="store_true",
            help="Pretty-print JSON output",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """Execute the command."""
        task_id = options["backtest_task_id"]
        execution_id = options.get("execution_id")
        output_file = options.get("output")
        pretty = options.get("pretty", False)

        try:
            task = BacktestTask.objects.select_related("config", "user").get(id=task_id)
        except BacktestTask.DoesNotExist as exc:
            raise CommandError(f"BacktestTask with ID {task_id} does not exist") from exc

        if execution_id is not None:
            try:
                execution = TaskExecution.objects.select_related("metrics").get(
                    id=execution_id,
                    task_type="backtest",
                    task_id=task.pk,
                )
            except TaskExecution.DoesNotExist as exc:
                raise CommandError(
                    f"TaskExecution {execution_id} does not exist for BacktestTask {task_id}"
                ) from exc
        else:
            execution = task.get_latest_execution()

        if not execution:
            raise CommandError(f"No execution found for BacktestTask {task_id}")

        metrics_obj = getattr(execution, "metrics", None)

        # Derive a convenient final_balance without requiring a dedicated column.
        final_balance = None
        if metrics_obj and metrics_obj.equity_curve:
            try:
                final_balance = metrics_obj.equity_curve[-1].get("balance")
            except Exception:  # pylint: disable=broad-exception-caught
                final_balance = None
        if final_balance is None and metrics_obj is not None:
            try:
                final_balance = float(task.initial_balance + metrics_obj.total_pnl)
            except Exception:  # pylint: disable=broad-exception-caught
                final_balance = None

        strategy_type = task.config.strategy_type if task.config else None

        # Build export data
        export_data = {
            "task": {
                "id": task.pk,
                "name": task.name,
                "description": task.description,
                "strategy_type": strategy_type,
                "instrument": task.instrument,
                "start_time": task.start_time.isoformat(),
                "end_time": task.end_time.isoformat(),
                "initial_balance": float(task.initial_balance),
                "commission_per_trade": float(task.commission_per_trade),
                "status": task.status,
            },
            "execution": {
                "id": execution.pk,
                "execution_number": execution.execution_number,
                "status": execution.status,
                "started_at": execution.started_at.isoformat() if execution.started_at else None,
                "completed_at": (
                    execution.completed_at.isoformat() if execution.completed_at else None
                ),
                "duration": execution.get_duration(),
                "error_message": execution.error_message or None,
                "logs": execution.logs or [],
                "resource_usage": {
                    "peak_memory_mb": (
                        float(getattr(execution, "peak_memory_mb"))
                        if getattr(execution, "peak_memory_mb", None) is not None
                        else None
                    ),
                    "memory_limit_mb": (
                        float(getattr(execution, "memory_limit_mb"))
                        if getattr(execution, "memory_limit_mb", None) is not None
                        else None
                    ),
                    "cpu_limit_cores": getattr(execution, "cpu_limit_cores", None),
                },
            },
            "metrics": (
                {
                    "total_return": float(metrics_obj.total_return),
                    "total_pnl": float(metrics_obj.total_pnl),
                    "total_trades": metrics_obj.total_trades,
                    "winning_trades": metrics_obj.winning_trades,
                    "losing_trades": metrics_obj.losing_trades,
                    "win_rate": float(metrics_obj.win_rate),
                    "max_drawdown": float(metrics_obj.max_drawdown),
                    "sharpe_ratio": (
                        float(metrics_obj.sharpe_ratio) if metrics_obj.sharpe_ratio else None
                    ),
                    "profit_factor": (
                        float(metrics_obj.profit_factor) if metrics_obj.profit_factor else None
                    ),
                    "average_win": float(metrics_obj.average_win),
                    "average_loss": float(metrics_obj.average_loss),
                    "final_balance": final_balance,
                    "equity_curve": metrics_obj.equity_curve or [],
                    "trade_log": metrics_obj.trade_log or [],
                    "strategy_events": metrics_obj.strategy_events or [],
                }
                if metrics_obj
                else None
            ),
            "exported_at": timezone.now().isoformat(),
        }

        # Serialize to JSON
        indent = 2 if pretty else None
        json_output = json.dumps(export_data, cls=DecimalEncoder, indent=indent)

        # Output to file or stdout
        if output_file:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(json_output)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully exported BacktestTask {task_id} execution {execution.pk} to {output_file}"
                )
            )
        else:
            sys.stdout.write(json_output)
            sys.stdout.write("\n")
