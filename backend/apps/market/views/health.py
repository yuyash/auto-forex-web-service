"""Health check views."""

from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers, status
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
        operation_id="market_oanda_health_status",
        tags=["Market"],
        parameters=[
            OpenApiParameter(name="account_id", type=str, required=False, location="query"),
        ],
        responses={
            200: inline_serializer(
                "OandaHealthGetResponse",
                fields={
                    "account": serializers.DictField(),
                    "status": OandaApiHealthStatusSerializer(allow_null=True),
                },
            )
        },
        description="Get latest persisted OANDA API health status.",
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
        operation_id="market_oanda_health_check",
        tags=["Market"],
        parameters=[
            OpenApiParameter(name="account_id", type=str, required=False, location="query"),
        ],
        responses={
            200: inline_serializer(
                "OandaHealthPostResponse",
                fields={
                    "account": serializers.DictField(),
                    "status": OandaApiHealthStatusSerializer(),
                },
            )
        },
        description="Perform a live OANDA API health check.",
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
