from __future__ import annotations

from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.health.services.health_check import HealthCheckService


class HealthView(APIView):
    """Public health check endpoint.

    GET /api/health/
    """

    permission_classes = [AllowAny]
    # Public endpoint; avoid SessionAuthentication CSRF enforcement.
    authentication_classes = []

    def get(self, request: Request) -> Response:  # pylint: disable=unused-argument
        result = HealthCheckService().check()
        return Response(result.body, status=result.http_status)
