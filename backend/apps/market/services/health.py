"""Health check services for external dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from time import perf_counter

import v20
from django.utils import timezone

from apps.market.models import OandaAccount, OandaApiHealthStatus


@dataclass(frozen=True, slots=True)
class OandaHealthCheckResult:
    is_available: bool
    checked_at: datetime
    latency_ms: int | None
    http_status: int | None
    error_message: str


class OandaHealthCheckService:
    """Checks OANDA API availability for a given account and persists the result."""

    def __init__(self, account: OandaAccount):
        self.account = account

    def check(self) -> OandaApiHealthStatus:
        checked_at = timezone.now()
        start = perf_counter()

        http_status: int | None = None
        error_message = ""
        is_available = False

        try:
            api = v20.Context(
                hostname=self.account.api_hostname,
                token=self.account.get_api_token(),
                poll_timeout=10,
            )
            response = api.account.get(self.account.account_id)
            http_status = int(getattr(response, "status", 0) or 0) or None

            if http_status == 200:
                is_available = True
            else:
                # Avoid depending on OANDA response schema; store a compact message.
                error_message = (
                    f"OANDA API returned status {http_status}"
                    if http_status
                    else "OANDA API call failed"
                )

        except Exception as exc:  # pylint: disable=broad-exception-caught
            error_message = str(exc)

        latency_ms = int((perf_counter() - start) * 1000)

        return OandaApiHealthStatus.objects.create(
            account=self.account,
            is_available=is_available,
            checked_at=checked_at,
            latency_ms=latency_ms,
            http_status=http_status,
            error_message=error_message,
        )
