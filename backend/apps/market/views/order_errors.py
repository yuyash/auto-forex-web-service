"""API response helpers for broker order submission failures."""

from __future__ import annotations

from rest_framework import status
from rest_framework.response import Response

from apps.market.services.broker_order_guard import BrokerOrderGuardError
from apps.market.services.compliance import ComplianceViolationError
from apps.market.services.oanda import OandaAPIError


def order_error_response(exc: Exception, *, fallback_error: str) -> Response:
    """Map broker-order exceptions to safe API responses."""

    if isinstance(exc, ComplianceViolationError):
        return Response(
            {
                "error": str(exc),
                "error_code": "ORDER_COMPLIANCE_VIOLATION",
            },
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    if isinstance(exc, OandaAPIError) and isinstance(exc.__cause__, BrokerOrderGuardError):
        return Response(
            {
                "error": str(exc),
                "error_code": "ORDER_GUARD_VIOLATION",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        {
            "error": fallback_error,
            "error_code": "OANDA_UPSTREAM_ERROR",
        },
        status=status.HTTP_502_BAD_GATEWAY,
    )
