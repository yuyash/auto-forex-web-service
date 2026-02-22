from __future__ import annotations

from logging import Logger, getLogger
from typing import Any

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.health.services.health import HealthCheckResult, HealthCheckService

logger: Logger = getLogger(name=__name__)


def get_client_ip(request: Request) -> str:
    """Get client IP address from request, considering proxy headers."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        # X-Forwarded-For can contain multiple IPs; the first is the client
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


class HealthView(APIView):
    """Health check endpoint.

    GET /api/health/
    """

    permission_classes = [AllowAny]
    # Public endpoint; avoid SessionAuthentication CSRF enforcement.
    authentication_classes = []

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.health_service = HealthCheckService()

    @extend_schema(
        operation_id="health_check",
        summary="GET /api/health/",
        description="Check the health status of the backend API service. Returns overall system status.",
        tags=["health"],
        responses={
            200: OpenApiResponse(
                description="Service is healthy",
                response={
                    "type": "object",
                    "properties": {
                        "status": {
                            "type": "string",
                            "enum": ["healthy"],
                            "description": "Overall health status",
                        },
                        "timestamp": {
                            "type": "string",
                            "format": "date-time",
                            "description": "Timestamp of the health check",
                        },
                        "response_time_ms": {
                            "type": "integer",
                            "description": "Response time in milliseconds",
                        },
                    },
                    "required": ["status", "timestamp", "response_time_ms"],
                    "example": {
                        "status": "healthy",
                        "timestamp": "2024-01-18T12:00:00Z",
                        "response_time_ms": 15,
                    },
                },
            ),
            503: OpenApiResponse(
                description="Service is unhealthy",
                response={
                    "type": "object",
                    "properties": {
                        "status": {
                            "type": "string",
                            "enum": ["unhealthy"],
                            "description": "Overall health status",
                        },
                        "timestamp": {
                            "type": "string",
                            "format": "date-time",
                            "description": "Timestamp of the health check",
                        },
                        "response_time_ms": {
                            "type": "integer",
                            "description": "Response time in milliseconds",
                        },
                    },
                    "required": ["status", "timestamp", "response_time_ms"],
                    "example": {
                        "status": "unhealthy",
                        "timestamp": "2024-01-18T12:00:00Z",
                        "response_time_ms": 20,
                    },
                },
            ),
        },
    )
    def get(self, request: Request) -> Response:
        client_ip: str = get_client_ip(request)
        logger.debug(msg=f"Receiving health check request from IP: {client_ip}")
        result: HealthCheckResult = self.health_service.check()
        return Response(data=result.body, status=result.http_status)
