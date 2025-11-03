"""
Views for order management and execution.

This module contains views for:
- Order submission (market, limit, stop, OCO)
- Order listing with filtering
- Order details retrieval
- Order cancellation

Requirements: 8.1, 8.2
"""

import logging

from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import OandaAccount
from trading.models import Order
from trading.order_executor import OrderExecutionError, OrderExecutor
from trading.serializers import OrderCreateSerializer, OrderSerializer

logger = logging.getLogger(__name__)


class OrderPagination(PageNumberPagination):
    """
    Pagination class for orders.

    Provides configurable page size with reasonable defaults and limits.

    Requirements: 8.1, 8.2
    """

    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 100


class OrderListCreateView(APIView):
    """
    API endpoint for order listing and creation.

    GET /api/orders
    - List user's orders with filtering
    - Support pagination
    - Filter by account, instrument, status, date range

    POST /api/orders
    - Submit new order (market, limit, stop, OCO)
    - Validate order parameters
    - Execute via OANDA API with retry logic

    Query Parameters (GET):
        - account_id: Filter by OANDA account ID
        - instrument: Filter by currency pair (e.g., 'EUR_USD')
        - status: Filter by order status (pending, filled, cancelled, rejected)
        - start_date: Filter orders created after this date (ISO format)
        - end_date: Filter orders created before this date (ISO format)
        - page: Page number for pagination (default: 1)
        - page_size: Number of results per page (default: 50, max: 100)

    Requirements: 8.1, 8.2
    """

    permission_classes = [IsAuthenticated]
    pagination_class = OrderPagination

    def get(self, request: Request) -> Response:
        """
        List user's orders with optional filtering.

        Args:
            request: HTTP request with query parameters

        Returns:
            Response with paginated order list
        """
        # Get user's OANDA accounts
        user_accounts = OandaAccount.objects.filter(user=request.user.id)

        # Start with orders from user's accounts
        queryset = Order.objects.filter(account__in=user_accounts)

        # Apply filters
        account_id = request.query_params.get("account_id")
        if account_id:
            queryset = queryset.filter(account_id=int(account_id))

        instrument = request.query_params.get("instrument")
        if instrument:
            queryset = queryset.filter(instrument=instrument)

        order_status = request.query_params.get("status")
        if order_status:
            queryset = queryset.filter(status=order_status)

        start_date = request.query_params.get("start_date")
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)

        end_date = request.query_params.get("end_date")
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)

        # Order by creation date (newest first)
        queryset = queryset.order_by("-created_at")

        # Apply pagination
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request)

        if page is not None:
            serializer = OrderSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = OrderSerializer(queryset, many=True)
        return Response(serializer.data)

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
                order = executor.submit_market_order(
                    instrument=instrument,
                    units=signed_units,
                    take_profit=take_profit,
                    stop_loss=stop_loss,
                )
            elif order_type == "limit":
                order = executor.submit_limit_order(
                    instrument=instrument,
                    units=signed_units,
                    price=price,
                    take_profit=take_profit,
                    stop_loss=stop_loss,
                )
            elif order_type == "stop":
                order = executor.submit_stop_order(
                    instrument=instrument,
                    units=signed_units,
                    price=price,
                    take_profit=take_profit,
                    stop_loss=stop_loss,
                )
            elif order_type == "oco":
                limit_order, stop_order = executor.submit_oco_order(
                    instrument=instrument,
                    units=signed_units,
                    limit_price=limit_price,
                    stop_price=stop_price,
                )
                # Return both orders for OCO
                return Response(
                    {
                        "limit_order": OrderSerializer(limit_order).data,
                        "stop_order": OrderSerializer(stop_order).data,
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
                OrderSerializer(order).data,
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


class OrderDetailView(APIView):
    """
    API endpoint for order details and cancellation.

    GET /api/orders/{id}
    - Retrieve order details by ID
    - Verify user has access to the order

    DELETE /api/orders/{id}
    - Cancel a pending order
    - Only pending orders can be cancelled

    Requirements: 8.1, 8.2
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, order_id: int) -> Response:
        """
        Retrieve order details.

        Args:
            request: HTTP request
            order_id: Order ID

        Returns:
            Response with order details or error
        """
        # Get user's OANDA accounts
        user_accounts = OandaAccount.objects.filter(user=request.user.id)

        # Get order
        try:
            order = Order.objects.get(id=order_id, account__in=user_accounts)
        except Order.DoesNotExist:
            return Response(
                {"error": "Order not found or access denied"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = OrderSerializer(order)
        return Response(serializer.data)

    def delete(self, request: Request, order_id: int) -> Response:
        """
        Cancel a pending order.

        Args:
            request: HTTP request
            order_id: Order ID

        Returns:
            Response with success message or error
        """
        # Get user's OANDA accounts
        user_accounts = OandaAccount.objects.filter(user=request.user.id)

        # Get order
        try:
            order = Order.objects.get(id=order_id, account__in=user_accounts)
        except Order.DoesNotExist:
            return Response(
                {"error": "Order not found or access denied"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check if order can be cancelled
        if order.status != "pending":
            return Response(
                {"error": f"Cannot cancel order with status: {order.status}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Cancel order via OrderExecutor
        try:
            executor = OrderExecutor(order.account)
            success = executor.cancel_order(order.order_id)

            if success:
                return Response(
                    {"message": "Order cancelled successfully"},
                    status=status.HTTP_200_OK,
                )

            return Response(
                {"error": "Failed to cancel order"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error cancelling order %s: %s", order_id, e)
            return Response(
                {"error": "An unexpected error occurred"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
