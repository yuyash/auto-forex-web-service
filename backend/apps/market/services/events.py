"""apps.market.services.events

Market-owned event logging.

This is intentionally independent of the accounts/trading event mechanisms.
"""

from __future__ import annotations

from typing import Any

from django.apps import apps as django_apps

from apps.market.enums import MarketEventCategory, MarketEventSeverity, MarketEventType
from apps.market.models import OandaAccount


class MarketEventService:
    """Event service that persists MarketEvent records.

    This service is intentionally side-effect-only and must never raise.
    """

    def log_event(
        self,
        *,
        event_type: MarketEventType,
        description: str,
        severity: MarketEventSeverity = MarketEventSeverity.INFO,
        category: MarketEventCategory = MarketEventCategory.MARKET,
        user: Any | None = None,
        account: OandaAccount | None = None,
        instrument: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        try:
            MarketEvent = django_apps.get_model("market", "MarketEvent")

            MarketEvent.objects.create(
                event_type=str(event_type),
                category=str(category),
                severity=str(severity),
                description=description,
                user=user if getattr(user, "pk", None) else None,
                account=account if getattr(account, "pk", None) else None,
                instrument=instrument,
                details=details or {},
            )
        except Exception:  # pylint: disable=broad-exception-caught
            # Never break request handling/tasks due to logging failures.
            return

    def log_trading_event(
        self,
        *,
        event_type: MarketEventType,
        description: str,
        severity: MarketEventSeverity = MarketEventSeverity.INFO,
        user: Any | None = None,
        account: OandaAccount | None = None,
        instrument: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.log_event(
            event_type=event_type,
            description=description,
            severity=severity,
            category=MarketEventCategory.TRADING,
            user=user,
            account=account,
            instrument=instrument,
            details=details,
        )

    def log_security_event(
        self,
        *,
        event_type: MarketEventType,
        description: str,
        severity: MarketEventSeverity = MarketEventSeverity.INFO,
        user: Any | None = None,
        account: OandaAccount | None = None,
        instrument: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.log_event(
            event_type=event_type,
            description=description,
            severity=severity,
            category=MarketEventCategory.SECURITY,
            user=user,
            account=account,
            instrument=instrument,
            details=details,
        )
