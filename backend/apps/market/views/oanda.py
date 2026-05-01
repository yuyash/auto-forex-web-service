"""OANDA account views."""

from logging import Logger, getLogger

from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.querying import (
    OrderingConfig,
    apply_queryset_ordering,
    invalid_query_param,
    parse_datetime_param,
)
from apps.market.models import OandaAccounts
from apps.market.serializers import OandaAccountsSerializer
from apps.market.services.accounts import (
    apply_cached_oanda_account_snapshot,
    create_oanda_account,
    delete_oanda_account,
    enqueue_oanda_account_snapshot_refresh,
    is_oanda_account_snapshot_stale,
    update_oanda_account,
)
from apps.trading.views.pagination import StandardPagination

logger: Logger = getLogger(name=__name__)

OANDA_ACCOUNT_ORDERING = OrderingConfig(
    fields={
        "id": "id",
        "account_id": "account_id",
        "api_type": "api_type",
        "currency": "currency",
        "balance": "balance",
        "nav": "nav",
        "is_active": "is_active",
        "is_default": "is_default",
        "snapshot_refreshed_at": "snapshot_refreshed_at",
        "created_at": "created_at",
        "updated_at": "updated_at",
    },
    default="-created_at",
)


class OandaAccountDetailResponseSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    """Schema serializer for OANDA account responses with cached snapshot fields."""

    id = serializers.IntegerField()
    account_id = serializers.CharField()
    api_type = serializers.CharField()
    jurisdiction = serializers.CharField()
    currency = serializers.CharField()
    balance = serializers.CharField(required=False)
    margin_used = serializers.CharField(required=False)
    margin_available = serializers.CharField(required=False)
    nav = serializers.CharField(required=False)
    is_active = serializers.BooleanField()
    is_default = serializers.BooleanField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()
    unrealized_pnl = serializers.CharField(required=False)
    open_trade_count = serializers.IntegerField(required=False)
    open_position_count = serializers.IntegerField(required=False)
    pending_order_count = serializers.IntegerField(required=False)
    hedging_enabled = serializers.BooleanField(required=False)
    position_mode = serializers.CharField(required=False)
    oanda_account = serializers.DictField(required=False)
    live_data = serializers.BooleanField(required=False)
    live_data_error = serializers.CharField(required=False)
    snapshot_refreshed_at = serializers.DateTimeField(required=False, allow_null=True)
    snapshot_stale = serializers.BooleanField(required=False)
    snapshot_refresh_error = serializers.CharField(required=False, allow_blank=True)


class OandaAccountSnapshotRefreshResponseSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    """Schema serializer for queued OANDA account snapshot refreshes."""

    id = serializers.IntegerField()
    account_id = serializers.CharField()
    task_id = serializers.CharField()
    status = serializers.CharField()
    snapshot_refreshed_at = serializers.DateTimeField(allow_null=True)
    snapshot_stale = serializers.BooleanField()
    snapshot_refresh_error = serializers.CharField(allow_blank=True)


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


def _get_owned_oanda_account(request: Request, account_id: int) -> OandaAccounts | None:
    return OandaAccounts.objects.filter(id=account_id, user_id=request.user.id).first()


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
    pagination_class = StandardPagination

    @extend_schema(
        operation_id="market_accounts_list",
        tags=["Market"],
        parameters=[
            OpenApiParameter(name="page", type=int, required=False),
            OpenApiParameter(name="page_size", type=int, required=False),
            OpenApiParameter(name="ordering", type=str, required=False),
            OpenApiParameter(name="search", type=str, required=False),
            OpenApiParameter(name="created_from", type=str, required=False),
            OpenApiParameter(name="created_to", type=str, required=False),
        ],
        responses={
            200: inline_serializer(
                "OandaAccountPaginatedResponse",
                fields={
                    "count": serializers.IntegerField(),
                    "next": serializers.CharField(allow_null=True),
                    "previous": serializers.CharField(allow_null=True),
                    "results": OandaAccountDetailResponseSerializer(many=True),
                },
            )
        },
    )
    def get(self, request: Request) -> Response:
        created_from = parse_datetime_param(
            request.query_params.get("created_from"),
            field_name="created_from",
        )
        created_to = parse_datetime_param(
            request.query_params.get("created_to"),
            field_name="created_to",
        )
        if created_from and created_to and created_from > created_to:
            raise invalid_query_param("created_from must be earlier than or equal to created_to")
        accounts = OandaAccounts.objects.filter(user_id=request.user.id).select_related("user")
        search = request.query_params.get("search")
        if search:
            accounts = accounts.filter(account_id__icontains=search)
        if created_from:
            accounts = accounts.filter(created_at__gte=created_from)
        if created_to:
            accounts = accounts.filter(created_at__lte=created_to)
        accounts = apply_queryset_ordering(
            accounts,
            request.query_params.get("ordering"),
            OANDA_ACCOUNT_ORDERING,
        )
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(accounts, request)
        serializer = self.serializer_class(page, many=True)
        response_data = list(serializer.data)
        for account, account_data in zip(page, response_data, strict=False):
            apply_cached_oanda_account_snapshot(account=account, response_data=account_data)
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
        return paginator.get_paginated_response(response_data)

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
        return _get_owned_oanda_account(request, account_id)

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
        apply_cached_oanda_account_snapshot(account=account, response_data=response_data)
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


class OandaAccountSnapshotRefreshView(APIView):
    """Queue a refresh for a cached OANDA account snapshot."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="market_account_snapshot_refresh",
        tags=["Market"],
        request=None,
        responses={
            202: OandaAccountSnapshotRefreshResponseSerializer,
            400: inline_serializer(
                "OandaAccountSnapshotRefreshBadRequest",
                fields={"error": serializers.CharField()},
            ),
            404: inline_serializer(
                "OandaAccountSnapshotRefreshNotFound",
                fields={"error": serializers.CharField()},
            ),
            503: inline_serializer(
                "OandaAccountSnapshotRefreshUnavailable",
                fields={"error": serializers.CharField()},
            ),
        },
    )
    def post(self, request: Request, account_id: int) -> Response:
        account = _get_owned_oanda_account(request, account_id)
        if account is None:
            return Response(
                {"error": "Account not found or you don't have permission to access it."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if not account.is_active:
            return Response(
                {"error": "Cannot refresh an inactive OANDA account."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            task_id = enqueue_oanda_account_snapshot_refresh(account)
        except Exception:
            logger.exception(
                "Failed to queue OANDA account snapshot refresh for account %s",
                account.account_id,
            )
            return Response(
                {"error": "Failed to queue account snapshot refresh."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {
                "id": account.pk,
                "account_id": account.account_id,
                "task_id": task_id,
                "status": "queued",
                "snapshot_refreshed_at": account.snapshot_refreshed_at,
                "snapshot_stale": is_oanda_account_snapshot_stale(account),
                "snapshot_refresh_error": account.snapshot_refresh_error,
            },
            status=status.HTTP_202_ACCEPTED,
        )
