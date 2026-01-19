"""Order views."""

from logging import Logger, getLogger
from typing import Any

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.market.models import OandaAccounts
from apps.market.serializers import OrderSerializer
from apps.market.services.compliance import ComplianceViolationError
from apps.market.services.oanda import (
    LimitOrderRequest,
    MarketOrderRequest,
    OandaAPIError,
    OandaService,
    OcoOrderRequest,
    Order,
    StopOrderRequest,
)

logger: Logger = getLogger(name=__name__)


class OrderView(APIView):
    """
    API endpoint for order listing and creation.

    GET /api/market/orders
    - List user's orders directly from OANDA API
    - Filter by account, instrument, status

    POST /api/market/orders
    - Submit new order (market, limit, stop, OCO)
    - Validate order parameters
    - Execute via OANDA API with retry logic

    Query Parameters (GET):
        - account_id: Filter by OANDA account ID (required)
        - instrument: Filter by currency pair (e.g., 'EUR_USD')
        - status: Filter by order status (pending, all)
        - count: Number of orders to return (default: 50)
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="GET /api/market/orders/",
        description="List user's orders directly from OANDA API",
        operation_id="list_orders",
        tags=["Market - Orders"],
        parameters=[
            OpenApiParameter(
                name="account_id",
                type=int,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Filter by OANDA account ID",
            ),
            OpenApiParameter(
                name="instrument",
                type=str,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Filter by currency pair",
            ),
            OpenApiParameter(
                name="status",
                type=str,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Filter by order status (pending/all)",
                default="all",
            ),
            OpenApiParameter(
                name="count",
                type=int,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Number of orders to return",
                default=50,
            ),
        ],
        responses={200: dict},
    )
    def get(self, request: Request) -> Response:
        """
        List user's orders directly from OANDA API.

        Args:
            request: HTTP request with query parameters

        Returns:
            Response with order list from OANDA
        """
        account_id = request.query_params.get("account_id")
        instrument = request.query_params.get("instrument")
        order_status = request.query_params.get("status", "all").lower()
        count = int(request.query_params.get("count", "50"))

        # If no account_id specified, get orders from all user accounts
        if account_id:
            try:
                accounts = [OandaAccounts.objects.get(id=int(account_id), user=request.user.pk)]
            except OandaAccounts.DoesNotExist:
                return Response(
                    {"error": "Account not found or access denied"},
                    status=status.HTTP_404_NOT_FOUND,
                )
        else:
            accounts = list(OandaAccounts.objects.filter(user=request.user.pk, is_active=True))

        if not accounts:
            return Response({"results": [], "count": 0})

        all_orders = []

        for account in accounts:
            try:
                client = OandaService(account)

                if order_status == "pending":
                    # Get only pending orders
                    for pending_order in client.get_pending_orders(instrument=instrument):
                        all_orders.append(
                            {
                                "id": pending_order.order_id,
                                "instrument": pending_order.instrument,
                                "type": pending_order.order_type.value,
                                "direction": pending_order.direction.value,
                                "units": str(pending_order.units),
                                "price": (
                                    str(pending_order.price)
                                    if pending_order.price is not None
                                    else None
                                ),
                                "state": pending_order.state.value,
                                "time_in_force": pending_order.time_in_force,
                                "create_time": (
                                    pending_order.create_time.isoformat()
                                    if pending_order.create_time
                                    else None
                                ),
                                "fill_time": (
                                    pending_order.fill_time.isoformat()
                                    if pending_order.fill_time
                                    else None
                                ),
                                "cancel_time": (
                                    pending_order.cancel_time.isoformat()
                                    if pending_order.cancel_time
                                    else None
                                ),
                                "account_name": account.account_id,
                                "account_db_id": account.pk,
                            }
                        )
                else:
                    # Get order history (includes all states)
                    for order in client.get_order_history(
                        instrument=instrument,
                        count=count,
                        state="ALL",
                    ):
                        all_orders.append(
                            {
                                "id": order.order_id,
                                "instrument": order.instrument,
                                "type": order.order_type.value,
                                "direction": order.direction.value,
                                "units": str(order.units),
                                "price": str(order.price) if order.price is not None else None,
                                "state": order.state.value,
                                "time_in_force": order.time_in_force,
                                "create_time": (
                                    order.create_time.isoformat() if order.create_time else None
                                ),
                                "fill_time": (
                                    order.fill_time.isoformat() if order.fill_time else None
                                ),
                                "cancel_time": (
                                    order.cancel_time.isoformat() if order.cancel_time else None
                                ),
                                "account_name": account.account_id,
                                "account_db_id": account.pk,
                            }
                        )

            except OandaAPIError as e:
                logger.error(
                    "Failed to fetch orders from OANDA for account %s: %s",
                    account.account_id,
                    str(e),
                )
                # Continue with other accounts

        # Sort by create_time (newest first)
        all_orders.sort(key=lambda x: str(x.get("create_time") or ""), reverse=True)

        # Limit total results
        all_orders = all_orders[:count]

        return Response(
            {
                "results": all_orders,
                "count": len(all_orders),
            }
        )

    @extend_schema(
        summary="POST /api/market/orders/",
        description="Submit new order (market, limit, stop, OCO)",
        operation_id="create_order",
        tags=["Market - Orders"],
        request=OrderSerializer,
        responses={201: dict},
    )
    def post(  # pylint: disable=too-many-locals,too-many-return-statements
        self, request: Request
    ) -> Response:
        """
        Submit a new order.

        Args:
            request: HTTP request with order data

        Returns:
            Response with created order details or error
        """

        # Validate request data
        serializer = OrderSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Get account ID from request
        account_id = request.data.get("account_id")
        if not account_id:
            return Response(
                {"error": "account_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Verify account belongs to user
        try:
            account = OandaAccounts.objects.get(id=account_id, user=request.user.pk)
        except OandaAccounts.DoesNotExist:
            return Response(
                {"error": "Account not found or access denied"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Extract order parameters
        validated_data = serializer.validated_data
        instrument = validated_data["instrument"]
        order_type = validated_data["order_type"]
        direction = validated_data["direction"]
        units = validated_data["units"]

        # Convert direction to signed units (positive for long, negative for short)
        signed_units = units if direction == "long" else -units

        # Get optional parameters
        price = validated_data.get("price")
        take_profit = validated_data.get("take_profit")
        stop_loss = validated_data.get("stop_loss")
        limit_price = validated_data.get("limit_price")
        stop_price = validated_data.get("stop_price")

        # Execute order via OANDA API
        try:
            result: Order
            if order_type == "market":
                client = OandaService(account)
                result = client.create_market_order(
                    MarketOrderRequest(
                        instrument=instrument,
                        units=signed_units,
                        take_profit=take_profit,
                        stop_loss=stop_loss,
                    )
                )
            elif order_type == "limit":
                client = OandaService(account)
                result = client.create_limit_order(
                    LimitOrderRequest(
                        instrument=instrument,
                        units=signed_units,
                        price=price,
                        take_profit=take_profit,
                        stop_loss=stop_loss,
                    )
                )
            elif order_type == "stop":
                client = OandaService(account)
                result = client.create_stop_order(
                    StopOrderRequest(
                        instrument=instrument,
                        units=signed_units,
                        price=price,
                        take_profit=take_profit,
                        stop_loss=stop_loss,
                    )
                )
            elif order_type == "oco":
                client = OandaService(account)
                oco_order = client.create_oco_order(
                    OcoOrderRequest(
                        instrument=instrument,
                        units=signed_units,
                        limit_price=limit_price,
                        stop_price=stop_price,
                    )
                )
                # Return both order responses for OCO
                return Response(
                    {
                        "oco_order": self._format_order_response(oco_order),
                        "limit_order": (
                            self._format_order_response(oco_order.limit_order)
                            if oco_order.limit_order
                            else None
                        ),
                        "stop_order": (
                            self._format_order_response(oco_order.stop_order)
                            if oco_order.stop_order
                            else None
                        ),
                    },
                    status=status.HTTP_201_CREATED,
                )
            else:
                return Response(
                    {"error": f"Unsupported order type: {order_type}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Return created order
            return Response(
                self._format_order_response(result),
                status=status.HTTP_201_CREATED,
            )

        except (OandaAPIError, ComplianceViolationError) as e:
            logger.error("Order execution failed: %s", e)
            return Response(
                {"error": f"Order execution failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Unexpected error during order submission: %s", e)
            return Response(
                {"error": "An unexpected error occurred"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _format_order_response(self, order_result: Order) -> dict:
        """Format an Order object for API response."""
        return {
            "id": order_result.order_id,
            "instrument": order_result.instrument,
            "type": order_result.order_type.value,
            "direction": order_result.direction.value,
            "units": str(order_result.units),
            "price": str(order_result.price) if order_result.price is not None else None,
            "state": order_result.state.value,
            "time_in_force": order_result.time_in_force,
            "create_time": (
                order_result.create_time.isoformat() if order_result.create_time else None
            ),
            "fill_time": order_result.fill_time.isoformat() if order_result.fill_time else None,
            "cancel_time": (
                order_result.cancel_time.isoformat() if order_result.cancel_time else None
            ),
        }

    def _format_order_from_model(self, order: Any) -> dict:
        """Format Order model instance for API response."""
        return {
            "id": order.order_id,
            "instrument": order.instrument,
            "type": order.order_type,
            "units": str(order.units),
            "price": str(order.price) if order.price else None,
            "state": order.status.upper() if order.status else "PENDING",
            "create_time": order.created_at.isoformat() if order.created_at else None,
        }


class OrderDetailView(APIView):
    """
    API endpoint for order details and cancellation.

    GET /api/orders/{order_id}
    - Retrieve order details from OANDA API
    - order_id is the OANDA order ID

    DELETE /api/orders/{order_id}
    - Cancel a pending order via OANDA API
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="GET /api/market/orders/{order_id}/",
        description="Retrieve order details from OANDA API",
        operation_id="get_order_detail",
        tags=["Market - Orders"],
        parameters=[
            OpenApiParameter(
                name="order_id",
                type=str,
                location=OpenApiParameter.PATH,
                required=True,
                description="OANDA Order ID",
            ),
            OpenApiParameter(
                name="account_id",
                type=int,
                location=OpenApiParameter.QUERY,
                required=True,
                description="OANDA account database ID",
            ),
        ],
        responses={200: dict},
    )
    def get(self, request: Request, order_id: str) -> Response:
        """
        Retrieve order details from OANDA API.

        Args:
            request: HTTP request
            order_id: OANDA Order ID

        Returns:
            Response with order details or error
        """
        account_id = request.query_params.get("account_id")

        if not account_id:
            return Response(
                {"error": "account_id query parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            account = OandaAccounts.objects.get(id=int(account_id), user=request.user.pk)
        except OandaAccounts.DoesNotExist:
            return Response(
                {"error": "Account not found or access denied"},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            client = OandaService(account)
            order = client.get_order(order_id)

            return Response(
                {
                    "id": order.order_id,
                    "instrument": order.instrument,
                    "type": order.order_type.value,
                    "direction": order.direction.value,
                    "units": str(order.units),
                    "price": str(order.price) if order.price is not None else None,
                    "state": order.state.value,
                    "time_in_force": order.time_in_force,
                    "create_time": order.create_time.isoformat() if order.create_time else None,
                    "fill_time": order.fill_time.isoformat() if order.fill_time else None,
                    "cancel_time": order.cancel_time.isoformat() if order.cancel_time else None,
                }
            )

        except OandaAPIError as e:
            logger.error("Failed to fetch order %s: %s", order_id, str(e))
            return Response(
                {"error": f"Failed to fetch order: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        summary="DELETE /api/market/orders/{order_id}/",
        description="Cancel a pending order via OANDA API",
        operation_id="cancel_order",
        tags=["Market - Orders"],
        parameters=[
            OpenApiParameter(
                name="order_id",
                type=str,
                location=OpenApiParameter.PATH,
                required=True,
                description="OANDA Order ID",
            ),
            OpenApiParameter(
                name="account_id",
                type=int,
                location=OpenApiParameter.QUERY,
                required=True,
                description="OANDA account database ID",
            ),
        ],
        responses={200: dict},
    )
    def delete(self, request: Request, order_id: str) -> Response:
        """
        Cancel a pending order via OANDA API.

        Args:
            request: HTTP request
            order_id: OANDA Order ID

        Returns:
            Response with success message or error
        """
        account_id = request.query_params.get("account_id")

        if not account_id:
            return Response(
                {"error": "account_id query parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            account = OandaAccounts.objects.get(id=int(account_id), user=request.user.pk)
        except OandaAccounts.DoesNotExist:
            return Response(
                {"error": "Account not found or access denied"},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            client = OandaService(account)
            order = client.get_order(order_id)
            result = client.cancel_order(order)

            return Response(
                {
                    "message": "Order cancelled successfully",
                    "details": {
                        "order_id": result.order_id,
                        "transaction_id": result.transaction_id,
                        "time": result.cancel_time.isoformat() if result.cancel_time else None,
                        "state": result.state.value,
                    },
                },
                status=status.HTTP_200_OK,
            )

        except OandaAPIError as e:
            logger.error("Failed to cancel order %s: %s", order_id, str(e))
            return Response(
                {"error": f"Failed to cancel order: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
