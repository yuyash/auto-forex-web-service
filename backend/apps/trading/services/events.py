"""apps.trading.services.events

Trading-owned event logging.

This is intentionally independent of the market event mechanisms.
"""

from __future__ import annotations

from typing import Any

from django.apps import apps as django_apps

from apps.market.models import OandaAccount
from apps.trading.models import TaskExecution


class TradingEventService:
    """Event service that persists TradingEvent records.

    This service is intentionally side-effect-only and must never raise.
    """

    def log_event(
        self,
        *,
        event_type: str,
        description: str,
        severity: str = "info",
        user: Any | None = None,
        account: OandaAccount | None = None,
        instrument: str | None = None,
        task_type: str | None = None,
        task_id: int | None = None,
        execution: TaskExecution | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        try:
            TradingEvent = django_apps.get_model("trading", "TradingEvent")

            TradingEvent.objects.create(
                event_type=str(event_type),
                severity=str(severity),
                description=description,
                user=user if getattr(user, "pk", None) else None,
                account=account if getattr(account, "pk", None) else None,
                instrument=instrument,
                task_type=str(task_type or ""),
                task_id=task_id,
                execution=execution if getattr(execution, "pk", None) else None,
                details=details or {},
            )
        except Exception:  # pylint: disable=broad-exception-caught
            return
