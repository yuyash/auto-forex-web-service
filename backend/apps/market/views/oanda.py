"""OANDA account views."""

from logging import Logger, getLogger

from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.market.models import OandaAccounts
from apps.market.serializers import OandaAccountsSerializer
from apps.market.services.oanda import OandaService

logger: Logger = getLogger(name=__name__)


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
        summary="GET /api/market/accounts/",
        description="Retrieve all OANDA accounts for the authenticated user",
        operation_id="list_oanda_accounts",
        tags=["Market - Accounts"],
        responses={
            200: OpenApiResponse(
                description="List of OANDA accounts",
                response=OandaAccountsSerializer(many=True),
            ),
            401: OpenApiResponse(description="Authentication required"),
        },
    )
    def get(self, request: Request) -> Response:
        if not request.user.is_authenticated:
            return Response(
                {"error": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED
            )

        accounts = OandaAccounts.objects.filter(user_id=request.user.id).order_by("-created_at")
        serializer = self.serializer_class(accounts, many=True)
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
        response_data = {
            "count": accounts.count(),
            "next": None,
            "previous": None,
            "results": serializer.data,
        }
        return Response(response_data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="POST /api/market/accounts/",
        description="Add a new OANDA account for the authenticated user",
        operation_id="create_oanda_account",
        tags=["Market - Accounts"],
        request=OandaAccountsSerializer,
        responses={
            201: OpenApiResponse(
                description="Account created successfully",
                response=OandaAccountsSerializer,
            ),
            400: OpenApiResponse(description="Invalid data"),
            401: OpenApiResponse(description="Authentication required"),
        },
    )
    def post(self, request: Request) -> Response:
        if not request.user.is_authenticated:
            return Response(
                {"error": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED
            )

        serializer = self.serializer_class(data=request.data, context={"request": request})
        if serializer.is_valid():
            account = serializer.save()
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
        if not request.user.is_authenticated:
            return None
        try:
            account = OandaAccounts.objects.get(id=account_id, user_id=request.user.id)
            return account
        except OandaAccounts.DoesNotExist:
            return None

    @extend_schema(
        summary="GET /api/market/accounts/{account_id}/",
        description="Retrieve detailed information about a specific OANDA account including live data from OANDA API",
        operation_id="get_oanda_account_detail",
        tags=["Market - Accounts"],
        parameters=[
            OpenApiParameter(
                name="account_id",
                type=int,
                location=OpenApiParameter.PATH,
                required=True,
                description="OANDA account database ID",
            ),
        ],
        responses={
            200: OpenApiResponse(
                description="Account details retrieved successfully",
                response=OandaAccountsSerializer,
            ),
            401: OpenApiResponse(description="Authentication required"),
            404: OpenApiResponse(description="Account not found"),
        },
    )
    def get(self, request: Request, account_id: int) -> Response:
        if not request.user.is_authenticated:
            return Response(
                {"error": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED
            )
        account = self.get_object(request, account_id)
        if account is None:
            return Response(
                {"error": "Account not found or you don't have permission to access it."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = self.serializer_class(account)
        response_data = serializer.data
        try:
            client = OandaService(account)
            live_data = client.get_account_details()

            account_resource = client.get_account_resource()
            hedging_enabled = bool(account_resource.get("hedgingEnabled", False))

            response_data["balance"] = str(live_data.balance)
            response_data["margin_used"] = str(live_data.margin_used)
            response_data["margin_available"] = str(live_data.margin_available)
            response_data["unrealized_pnl"] = str(live_data.unrealized_pl)
            response_data["nav"] = str(live_data.nav)
            response_data["open_trade_count"] = live_data.open_trade_count
            response_data["open_position_count"] = live_data.open_position_count
            response_data["pending_order_count"] = live_data.pending_order_count

            response_data["hedging_enabled"] = hedging_enabled
            response_data["position_mode"] = "hedging" if hedging_enabled else "netting"
            response_data["oanda_account"] = client.make_jsonable(account_resource)
            response_data["live_data"] = True
        except Exception as e:
            logger.warning(
                "Failed to fetch live data from OANDA for account %s: %s",
                account.account_id,
                str(e),
            )
            response_data["live_data"] = False
            response_data["live_data_error"] = str(e)
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
        summary="PUT /api/market/accounts/{account_id}/",
        description="Update a specific OANDA account",
        operation_id="update_oanda_account",
        tags=["Market - Accounts"],
        parameters=[
            OpenApiParameter(
                name="account_id",
                type=int,
                location=OpenApiParameter.PATH,
                required=True,
                description="OANDA account database ID",
            ),
        ],
        request=OandaAccountsSerializer,
        responses={
            200: OpenApiResponse(
                description="Account updated successfully",
                response=OandaAccountsSerializer,
            ),
            400: OpenApiResponse(description="Invalid data"),
            401: OpenApiResponse(description="Authentication required"),
            404: OpenApiResponse(description="Account not found"),
        },
    )
    def put(self, request: Request, account_id: int) -> Response:
        if not request.user.is_authenticated:
            return Response(
                {"error": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED
            )
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
            updated_account = serializer.save()
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
        summary="DELETE /api/market/accounts/{account_id}/",
        description="Delete a specific OANDA account",
        operation_id="delete_oanda_account",
        tags=["Market - Accounts"],
        parameters=[
            OpenApiParameter(
                name="account_id",
                type=int,
                location=OpenApiParameter.PATH,
                required=True,
                description="OANDA account database ID",
            ),
        ],
        responses={
            200: OpenApiResponse(description="Account deleted successfully"),
            400: OpenApiResponse(description="Account is in use"),
            401: OpenApiResponse(description="Authentication required"),
            404: OpenApiResponse(description="Account not found"),
        },
    )
    def delete(self, request: Request, account_id: int) -> Response:
        if not request.user.is_authenticated:
            return Response(
                {"error": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED
            )
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
        account.delete()
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
