from __future__ import annotations

from logging import Logger, getLogger
from typing import Any

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.middlewares.utils import get_client_ip
from apps.health.services.health import HealthCheckResult, HealthCheckService

logger: Logger = getLogger(name=__name__)


class HealthView(APIView):
    """Health check endpoint.

    GET /api/health/
    """

    permission_classes = [AllowAny]
    # Public endpoint; avoid SessionAuthentication CSRF enforcement.
    authentication_classes = []
    throttle_classes: list = []

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.health_service = HealthCheckService()

    @extend_schema(
        operation_id="health_check",
        tags=["Health"],
        responses={
            200: inline_serializer(
                "HealthCheckResponse",
                fields={
                    "status": serializers.CharField(),
                    "timestamp": serializers.DateTimeField(),
                    "version": serializers.CharField(),
                    "components": serializers.DictField(),
                },
            ),
            503: inline_serializer(
                "HealthCheckUnavailableResponse",
                fields={
                    "status": serializers.CharField(),
                    "timestamp": serializers.DateTimeField(),
                    "version": serializers.CharField(),
                    "components": serializers.DictField(),
                },
            ),
        },
        description="System health check endpoint.",
    )
    def get(self, request: Request) -> Response:
        client_ip: str = get_client_ip(request)
        logger.debug(msg=f"Receiving health check request from IP: {client_ip}")
        result: HealthCheckResult = self.health_service.check()
        return Response(data=result.body, status=result.http_status)
