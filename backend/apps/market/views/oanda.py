"""OANDA account views."""

from logging import Logger, getLogger

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.market.models import OandaAccounts
from apps.market.serializers import OandaAccountsSerializer
from apps.market.services.accounts import (
    create_oanda_account,
    delete_oanda_account,
    update_oanda_account,
)
from apps.market.services.oanda import OandaService

logger: Logger = getLogger(name=__name__)


OandaAccountDetailResponseSerializer = inline_serializer(
    "OandaAccountDetailResponse",
    fields={
        "id": serializers.IntegerField(),
        "account_id": serializers.CharField(),
        "api_type": serializers.CharField(),
        "jurisdiction": serializers.CharField(),
        "currency": serializers.CharField(),
        "balance": serializers.CharField(required=False),
        "margin_used": serializers.CharField(required=False),
        "margin_available": serializers.CharField(required=False),
        "is_active": serializers.BooleanField(),
        "is_default": serializers.BooleanField(),
        "created_at": serializers.DateTimeField(),
        "updated_at": serializers.DateTimeField(),
        "unrealized_pnl": serializers.CharField(required=False),
        "nav": serializers.CharField(required=False),
        "open_trade_count": serializers.IntegerField(required=False),
        "open_position_count": serializers.IntegerField(required=False),
        "pending_order_count": serializers.IntegerField(required=False),
        "hedging_enabled": serializers.BooleanField(required=False),
        "position_mode": serializers.CharField(required=False),
        "oanda_account": serializers.DictField(required=False),
        "live_data": serializers.BooleanField(required=False),
        "live_data_error": serializers.CharField(required=False),
    },
)

OandaAccountUpdateRequestSerializer = inline_serializer(
    "OandaAccountUpdateRequest",
    fields={
        "account_id": serializers.CharField(required=False),
        "api_token": serializers.CharField(required=False, write_only=True),
        "api_type": serializers.CharField(required=False),
        "jurisdiction": serializers.CharField(required=False),
        "currency": serializers.CharField(required=False),
        "is_active": serializers.BooleanField(required=False),
        "is_default": serializers.BooleanField(required=False),
    },
)


def _apply_live_account_snapshot(
    *,
    account: OandaAccounts,
    response_data: dict,
    include_account_resource: bool = False,
) -> None:
    """Populate response data from the latest OANDA account snapshot."""
    client = OandaService(account)
    live_data = client.get_account_details()

    response_data["currency"] = live_data.currency
    response_data["balance"] = str(live_data.balance)
    response_data["margin_used"] = str(live_data.margin_used)
    response_data["margin_available"] = str(live_data.margin_available)
    response_data["unrealized_pnl"] = str(live_data.unrealized_pl)
    response_data["nav"] = str(live_data.nav)
    response_data["open_trade_count"] = live_data.open_trade_count
    response_data["open_position_count"] = live_data.open_position_count
    response_data["pending_order_count"] = live_data.pending_order_count
    response_data["live_data"] = True

    updated_fields: list[str] = []
    if account.currency != live_data.currency:
        account.currency = live_data.currency
        updated_fields.append("currency")
    if account.balance != live_data.balance:
        account.balance = live_data.balance
        updated_fields.append("balance")
    if account.margin_used != live_data.margin_used:
        account.margin_used = live_data.margin_used
        updated_fields.append("margin_used")
    if account.margin_available != live_data.margin_available:
        account.margin_available = live_data.margin_available
        updated_fields.append("margin_available")
    if account.unrealized_pnl != live_data.unrealized_pl:
        account.unrealized_pnl = live_data.unrealized_pl
        updated_fields.append("unrealized_pnl")
    if updated_fields:
        account.save(update_fields=[*updated_fields, "updated_at"])

    if not include_account_resource:
        return

    account_resource = client.get_account_resource()
    hedging_enabled = bool(account_resource.get("hedgingEnabled", False))
    response_data["hedging_enabled"] = hedging_enabled
    response_data["position_mode"] = "hedging" if hedging_enabled else "netting"
    response_data["oanda_account"] = client.make_jsonable(account_resource)


class OandaAccountView(APIView):
    """
    API endpoint for OANDA accounts.

    GET /api/market/accounts/
    - List all OANDA accounts for the authenticated user

    POST /api/market/accounts/
    - Add a new OANDA account
    """

    permission_classes = [IsAuthenticated]
    serializer_class = OandaAccountsSerializer

    @extend_schema(
        operation_id="market_accounts_list",
        tags=["Market"],
        responses={200: OandaAccountsSerializer(many=True)},
    )
    def get(self, request: Request) -> Response:
        accounts = (
            OandaAccounts.objects.filter(user_id=request.user.id)
            .select_related("user")
            .order_by("-created_at")
        )
        serializer = self.serializer_class(accounts, many=True)
        response_data = list(serializer.data)
        for account, account_data in zip(accounts, response_data, strict=False):
            try:
                _apply_live_account_snapshot(account=account, response_data=account_data)
            except Exception as e:
                logger.warning(
                    "Failed to fetch live data from OANDA for account %s: %s",
                    account.account_id,
                    str(e),
                )
                account_data["live_data"] = False
                account_data["live_data_error"] = "Failed to fetch live data from OANDA"
        logger.info(
            "User %s retrieved %s OANDA accounts",
            request.user.email,
            accounts.count(),
            extra={
                "user_id": request.user.id,
                "email": request.user.email,
                "count": accounts.count(),
            },
        )
        return Response(response_data, status=status.HTTP_200_OK)

    @extend_schema(
        operation_id="market_accounts_create",
        tags=["Market"],
        request=OandaAccountsSerializer,
        responses={201: OandaAccountsSerializer},
    )
    def post(self, request: Request) -> Response:
        serializer = self.serializer_class(data=request.data, context={"request": request})
        if serializer.is_valid():
            account = create_oanda_account(serializer)
            logger.info(
                "User %s created OANDA account %s",
                request.user.email,
                account.account_id,
                extra={
                    "user_id": request.user.id,
                    "email": request.user.email,
                    "account_id": account.account_id,
                    "api_type": account.api_type,
                },
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        logger.warning(
            "User %s failed to create OANDA account: %s",
            request.user.email,
            serializer.errors,
            extra={
                "user_id": request.user.id,
                "email": request.user.email,
                "errors": serializer.errors,
                "data_keys": list(request.data.keys()) if hasattr(request.data, "keys") else None,
            },
        )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class OandaAccountDetailView(APIView):
    """
    API endpoint for retrieving, updating, and deleting a specific OANDA account.

    GET /api/market/accounts/{id}/
    - Retrieve details of a specific OANDA account

    PUT /api/market/accounts/{id}/
    - Update a specific OANDA account

    DELETE /api/market/accounts/{id}/
    - Delete a specific OANDA account
    """

    permission_classes = [IsAuthenticated]
    serializer_class = OandaAccountsSerializer

    def get_object(self, request: Request, account_id: int) -> OandaAccounts | None:
        try:
            return OandaAccounts.objects.get(id=account_id, user_id=request.user.id)
        except OandaAccounts.DoesNotExist:
            return None

    @extend_schema(
        operation_id="market_account_detail",
        tags=["Market"],
        responses={200: OandaAccountDetailResponseSerializer},
    )
    def get(self, request: Request, account_id: int) -> Response:
        account = self.get_object(request, account_id)
        if account is None:
            return Response(
                {"error": "Account not found or you don't have permission to access it."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = self.serializer_class(account)
        response_data = serializer.data
        try:
            _apply_live_account_snapshot(
                account=account,
                response_data=response_data,
                include_account_resource=True,
            )
        except Exception as e:
            logger.warning(
                "Failed to fetch live data from OANDA for account %s: %s",
                account.account_id,
                str(e),
            )
            response_data["live_data"] = False
            response_data["live_data_error"] = "Failed to fetch live data from OANDA"
        logger.info(
            "User %s retrieved OANDA account %s",
            request.user.email,
            account.account_id,
            extra={
                "user_id": request.user.id,
                "email": request.user.email,
                "account_id": account.account_id,
            },
        )
        return Response(response_data, status=status.HTTP_200_OK)

    @extend_schema(
        operation_id="market_account_update",
        tags=["Market"],
        request=OandaAccountUpdateRequestSerializer,
        responses={200: OandaAccountsSerializer},
    )
    def put(self, request: Request, account_id: int) -> Response:
        account = self.get_object(request, account_id)
        if account is None:
            return Response(
                {"error": "Account not found or you don't have permission to access it."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = self.serializer_class(
            account, data=request.data, partial=True, context={"request": request}
        )
        if serializer.is_valid():
            updated_account = update_oanda_account(serializer)
            logger.info(
                "User %s updated OANDA account %s",
                request.user.email,
                updated_account.account_id,
                extra={
                    "user_id": request.user.id,
                    "email": request.user.email,
                    "account_id": updated_account.account_id,
                    "updated_fields": list(request.data.keys()),
                },
            )
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        operation_id="market_account_delete",
        tags=["Market"],
        responses={
            200: inline_serializer(
                "OandaAccountDeleteResponse",
                fields={"message": serializers.CharField()},
            )
        },
    )
    def delete(self, request: Request, account_id: int) -> Response:
        account = self.get_object(request, account_id)
        if account is None:
            return Response(
                {"error": "Account not found or you don't have permission to access it."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if account.is_used:
            error_message = (
                "Cannot delete this OANDA account because it is marked as in use. "
                "Please stop the process using this account first."
            )
            logger.warning(
                "User %s attempted to delete OANDA account %s that is in use",
                request.user.email,
                account.account_id,
                extra={
                    "user_id": request.user.id,
                    "email": request.user.email,
                    "account_id": account.account_id,
                    "is_used": True,
                },
            )
            return Response({"error": error_message}, status=status.HTTP_400_BAD_REQUEST)
        account_id_str = account.account_id
        delete_oanda_account(account)
        logger.info(
            "User %s deleted OANDA account %s",
            request.user.email,
            account_id_str,
            extra={
                "user_id": request.user.pk,
                "email": request.user.email,
                "account_id": account_id_str,
            },
        )
        return Response({"message": "Account deleted successfully."}, status=status.HTTP_200_OK)
