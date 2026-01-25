"""Health check views."""

from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
)
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.market.models import OandaAccounts
from apps.market.serializers import OandaApiHealthStatusSerializer
from apps.market.services.health import OandaHealthCheckService


class OandaApiHealthView(APIView):
    """API endpoint for OANDA API health checks.

    GET /api/market/health/oanda/
    - Returns latest persisted status for the selected account (or null if none yet)

    POST /api/market/health/oanda/
    - Performs a live check against OANDA and persists/returns the result
    """

    permission_classes = [IsAuthenticated]
    serializer_class = OandaApiHealthStatusSerializer

    def _get_account(self, request: Request) -> OandaAccounts | None:
        account_id = request.query_params.get("account_id")

        if account_id:
            return OandaAccounts.objects.filter(
                account_id=account_id,
                user=request.user.id,
            ).first()

        return (
            OandaAccounts.objects.filter(user=request.user.id, is_default=True).first()
            or OandaAccounts.objects.filter(user=request.user.id).first()
        )

    @extend_schema(
        summary="GET /api/market/health/oanda/",
        description="Retrieve the latest health check status for the selected OANDA account",
        operation_id="get_oanda_health_status",
        tags=["Market - Health"],
        parameters=[
            OpenApiParameter(
                name="account_id",
                type=str,
                location=OpenApiParameter.QUERY,
                required=False,
                description="OANDA account ID (uses default if not provided)",
            ),
        ],
        responses={
            200: OpenApiResponse(
                description="Health status retrieved successfully",
                response=OandaApiHealthStatusSerializer,
            ),
            400: OpenApiResponse(description="No OANDA account found"),
        },
    )
    def get(self, request: Request) -> Response:
        account = self._get_account(request)
        if account is None:
            return Response(
                {
                    "error": "No OANDA account found. Please configure an account first.",
                    "error_code": "NO_OANDA_ACCOUNT",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        latest = account.api_health_statuses.order_by("-checked_at").first()  # type: ignore[attr-defined]

        return Response(
            {
                "account": {
                    "id": account.pk,
                    "account_id": account.account_id,
                    "api_type": account.api_type,
                },
                "status": OandaApiHealthStatusSerializer(latest).data if latest else None,
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary="POST /api/market/health/oanda/",
        description="Perform a live health check against OANDA API and persist the result",
        operation_id="check_oanda_health",
        tags=["Market - Health"],
        parameters=[
            OpenApiParameter(
                name="account_id",
                type=str,
                location=OpenApiParameter.QUERY,
                required=False,
                description="OANDA account ID (uses default if not provided)",
            ),
        ],
        responses={
            200: OpenApiResponse(
                description="Health check performed successfully",
                response=OandaApiHealthStatusSerializer,
            ),
            400: OpenApiResponse(description="No OANDA account found"),
        },
    )
    def post(self, request: Request) -> Response:
        account = self._get_account(request)
        if account is None:
            return Response(
                {
                    "error": "No OANDA account found. Please configure an account first.",
                    "error_code": "NO_OANDA_ACCOUNT",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        row = OandaHealthCheckService(account).check()
        return Response(
            {
                "account": {
                    "id": account.pk,
                    "account_id": account.account_id,
                    "api_type": account.api_type,
                },
                "status": OandaApiHealthStatusSerializer(row).data,
            },
            status=status.HTTP_200_OK,
        )
