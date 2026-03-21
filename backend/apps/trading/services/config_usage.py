"""Services for strategy configuration usage lookups."""

from __future__ import annotations

from typing import Any

from apps.trading.models import BacktestTask, TradingTask


def list_configuration_tasks(*, config) -> list[dict[str, Any]]:
    """Return tasks currently associated with a strategy configuration."""
    trading_tasks = (
        TradingTask.objects.filter(config=config)
        .order_by("-created_at")
        .values("id", "name", "status")
    )
    backtest_tasks = (
        BacktestTask.objects.filter(config=config)
        .order_by("-created_at")
        .values("id", "name", "status")
    )

    return [
        *[
            {
                "id": str(task["id"]),
                "task_type": "trading",
                "name": task["name"],
                "status": task["status"],
            }
            for task in trading_tasks
        ],
        *[
            {
                "id": str(task["id"]),
                "task_type": "backtest",
                "name": task["name"],
                "status": task["status"],
            }
            for task in backtest_tasks
        ],
    ]
