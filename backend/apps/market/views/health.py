"""Health check views."""

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
