"""
Views for order management and execution.

This module contains views for:
- Order submission (market, limit, stop, OCO)
- Order listing with filtering (directly from OANDA API)
- Order details retrieval
- Order cancellation

Requirements: 8.1, 8.2
"""

import logging
from typing import TYPE_CHECKING

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import OandaAccount
from trading.oanda_api import OandaAPIClient, OandaAPIError
from trading.order_executor import OrderExecutionError, OrderExecutor
from trading.serializers import OrderCreateSerializer

if TYPE_CHECKING:
    from trading.models import Order

logger = logging.getLogger(__name__)


class OrderListCreateView(APIView):
    """
    API endpoint for order listing and creation.

    GET /api/orders
    - List user's orders directly from OANDA API
    - Filter by account, instrument, status

    POST /api/orders
    - Submit new order (market, limit, stop, OCO)
    - Validate order parameters
    - Execute via OANDA API with retry logic

    Query Parameters (GET):
        - account_id: Filter by OANDA account ID (required)
        - instrument: Filter by currency pair (e.g., 'EUR_USD')
        - status: Filter by order status (pending, all)
        - count: Number of orders to return (default: 50)

    Requirements: 8.1, 8.2
    """

    permission_classes = [IsAuthenticated]

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
                accounts = [OandaAccount.objects.get(id=int(account_id), user=request.user.id)]
            except OandaAccount.DoesNotExist:
                return Response(
                    {"error": "Account not found or access denied"},
                    status=status.HTTP_404_NOT_FOUND,
                )
        else:
            accounts = list(OandaAccount.objects.filter(user=request.user.id, is_active=True))

        if not accounts:
            return Response({"results": [], "count": 0})

        all_orders = []

        for account in accounts:
            try:
                client = OandaAPIClient(account)

                if order_status == "pending":
                    # Get only pending orders
                    orders = client.get_pending_orders(instrument=instrument)
                else:
                    # Get order history (includes all states)
                    orders = client.get_order_history(
                        instrument=instrument,
                        count=count,
                        state="ALL",
                    )

                # Add account info to each order
                for order in orders:
                    order["account_name"] = account.account_id
                    order["account_db_id"] = account.id

                all_orders.extend(orders)

            except OandaAPIError as e:
                logger.error(
                    "Failed to fetch orders from OANDA for account %s: %s",
                    account.account_id,
                    str(e),
                )
                # Continue with other accounts

        # Sort by create_time (newest first)
        all_orders.sort(key=lambda x: x.get("create_time", ""), reverse=True)

        # Limit total results
        all_orders = all_orders[:count]

        return Response(
            {
                "results": all_orders,
                "count": len(all_orders),
            }
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
        serializer = OrderCreateSerializer(data=request.data)
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
            account = OandaAccount.objects.get(id=account_id, user=request.user.id)
        except OandaAccount.DoesNotExist:
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

        # Execute order via OrderExecutor
        try:
            executor = OrderExecutor(account)

            if order_type == "market":
                result = executor.submit_market_order(
                    instrument=instrument,
                    units=signed_units,
                    take_profit=take_profit,
                    stop_loss=stop_loss,
                )
            elif order_type == "limit":
                result = executor.submit_limit_order(
                    instrument=instrument,
                    units=signed_units,
                    price=price,
                    take_profit=take_profit,
                    stop_loss=stop_loss,
                )
            elif order_type == "stop":
                result = executor.submit_stop_order(
                    instrument=instrument,
                    units=signed_units,
                    price=price,
                    take_profit=take_profit,
                    stop_loss=stop_loss,
                )
            elif order_type == "oco":
                limit_result, stop_result = executor.submit_oco_order(
                    instrument=instrument,
                    units=signed_units,
                    limit_price=limit_price,
                    stop_price=stop_price,
                )
                # Return both order responses for OCO
                return Response(
                    {
                        "limit_order": self._format_order_from_model(limit_result),
                        "stop_order": self._format_order_from_model(stop_result),
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
                self._format_order_from_model(result),
                status=status.HTTP_201_CREATED,
            )

        except OrderExecutionError as e:
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

    def _format_order_response(self, order_result: dict) -> dict:
        """Format order execution result for API response."""
        return {
            "id": order_result.get("order_id") or order_result.get("id"),
            "instrument": order_result.get("instrument"),
            "type": order_result.get("type"),
            "units": str(order_result.get("units", 0)),
            "price": (str(order_result.get("price", "")) if order_result.get("price") else None),
            "state": order_result.get("state", "PENDING"),
            "create_time": order_result.get("create_time") or order_result.get("time"),
        }

    def _format_order_from_model(self, order: "Order") -> dict:
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

    Requirements: 8.1, 8.2
    """

    permission_classes = [IsAuthenticated]

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
            account = OandaAccount.objects.get(id=int(account_id), user=request.user.id)
        except OandaAccount.DoesNotExist:
            return Response(
                {"error": "Account not found or access denied"},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            client = OandaAPIClient(account)
            # Get order from history to find it
            orders = client.get_order_history(count=100, state="ALL")
            order = next((o for o in orders if o.get("id") == order_id), None)

            if not order:
                return Response(
                    {"error": "Order not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            return Response(order)

        except OandaAPIError as e:
            logger.error("Failed to fetch order %s: %s", order_id, str(e))
            return Response(
                {"error": f"Failed to fetch order: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
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
            account = OandaAccount.objects.get(id=int(account_id), user=request.user.id)
        except OandaAccount.DoesNotExist:
            return Response(
                {"error": "Account not found or access denied"},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            client = OandaAPIClient(account)
            result = client.cancel_order(order_id)

            return Response(
                {"message": "Order cancelled successfully", "details": result},
                status=status.HTTP_200_OK,
            )

        except OandaAPIError as e:
            logger.error("Failed to cancel order %s: %s", order_id, str(e))
            return Response(
                {"error": f"Failed to cancel order: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
