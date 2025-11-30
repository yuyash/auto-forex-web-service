"""
Health check endpoints for system monitoring.

This module provides public health check endpoints for monitoring
the status of backend services including database, Redis, and Celery workers.

Requirements: 6.2, 6.3, 6.4
"""

import logging
from typing import Any, Dict

from django.http import JsonResponse

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from trading.system_health_monitor import SystemHealthMonitor

logger = logging.getLogger(__name__)


@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(request: Request) -> Response:  # pylint: disable=unused-argument
    """
    Public health check endpoint for monitoring backend services.

    This endpoint checks the health of:
    - PostgreSQL database connectivity
    - Redis connectivity
    - Celery workers (optional, may be slow)

    Returns HTTP 200 if all checks pass, HTTP 503 if any check fails.
    Response time is kept under 1 second.

    Requirements: 6.2, 6.3, 6.4

    Args:
        request: HTTP request object

    Returns:
        Response with health status of each component
    """
    try:
        monitor = SystemHealthMonitor()

        # Check database connectivity
        database_health = monitor.check_database_connection()

        # Check Redis connectivity
        redis_health = monitor.check_redis_connection()

        # Determine overall health status
        all_healthy = database_health["status"] in ["healthy", "warning"] and redis_health[
            "status"
        ] in ["healthy", "warning"]

        # Build response
        health_data: Dict[str, Any] = {
            "status": "healthy" if all_healthy else "unhealthy",
            "database": {
                "status": database_health["status"],
                "connected": database_health.get("connected", False),
                "response_time_ms": database_health.get("response_time_ms", 0),
            },
            "redis": {
                "status": redis_health["status"],
                "connected": redis_health.get("connected", False),
                "response_time_ms": redis_health.get("response_time_ms", 0),
            },
        }

        # Return appropriate status code
        http_status = status.HTTP_200_OK if all_healthy else status.HTTP_503_SERVICE_UNAVAILABLE

        return Response(health_data, status=http_status)

    except Exception as e:
        logger.error("Health check failed: %s", e, exc_info=True)
        return Response(
            {
                "status": "unhealthy",
                "error": "Health check failed",
                "database": {"status": "error", "connected": False},
                "redis": {"status": "error", "connected": False},
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


def simple_health_check(request):  # type: ignore[no-untyped-def] # pylint: disable=unused-argument
    """
    Simple health check endpoint that returns a basic JSON response.

    This is a lightweight endpoint for basic health monitoring.

    Args:
        request: HTTP request object

    Returns:
        JsonResponse with status
    """
    return JsonResponse({"status": "ok"}, status=200)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def oanda_health_check(request: Request) -> Response:
    """
    Check OANDA API connectivity for the authenticated user's accounts.

    This endpoint checks the health of all active OANDA accounts
    for the authenticated user by making a lightweight API call
    to verify connectivity and authentication.

    Returns HTTP 200 with health status for each account.

    Args:
        request: HTTP request object with authenticated user

    Returns:
        Response with OANDA API health status
    """
    # Import here to avoid circular dependency
    from trading.health_check import (  # pylint: disable=import-outside-toplevel
        check_all_accounts_health,
    )

    try:
        # Check health of all user's accounts
        user_id = request.user.id
        if user_id is None:
            return Response(
                {
                    "healthy": False,
                    "message": "User ID not found",
                    "accounts": [],
                },
                status=status.HTTP_200_OK,
            )
        health_status = check_all_accounts_health(user_id)

        # Return 200 even if unhealthy - client should check the 'healthy' field
        return Response(health_status, status=status.HTTP_200_OK)

    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error(
            "OANDA health check failed for user %s: %s",
            request.user.id,
            str(e),
            exc_info=True,
        )
        return Response(
            {
                "healthy": False,
                "message": f"Health check failed: {str(e)}",
                "accounts": [],
            },
            status=status.HTTP_200_OK,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def uptime_check(request: Request) -> Response:
    """
    Get system uptime information for host, container, and Celery processes.

    This endpoint provides detailed uptime monitoring:
    - Host: Time since last system reboot
    - Container: Time since Docker container started
    - Process: Current Python/Django process uptime
    - Celery: Worker process information

    Returns HTTP 200 with uptime data.

    Args:
        request: HTTP request object with authenticated user

    Returns:
        Response with uptime information for all components
    """
    try:
        monitor = SystemHealthMonitor()
        uptime_data = monitor.get_uptime_info()

        return Response(uptime_data, status=status.HTTP_200_OK)

    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error(
            "Uptime check failed: %s",
            str(e),
            exc_info=True,
        )
        return Response(
            {
                "status": "error",
                "message": f"Uptime check failed: {str(e)}",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
