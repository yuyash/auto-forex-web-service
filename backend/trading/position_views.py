"""
Views for position management and tracking.

This module contains views for:
- Position listing with filtering
- Position detail retrieval
- Position closing

Requirements: 9.1, 9.2
"""

import logging
from decimal import Decimal

from django.db.models import QuerySet

from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Position
from .position_manager import PositionManager
from .serializers import PositionSerializer

logger = logging.getLogger(__name__)


class PositionPagination(PageNumberPagination):
    """
    Pagination class for positions.

    Provides configurable page size with reasonable defaults and limits.

    Requirements: 9.1
    """

    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200


class PositionListView(APIView):
    """
    API endpoint for position listing.

    GET /api/positions
    - Retrieve positions with filtering
    - Support pagination for large datasets
    - Filter by account, strategy, instrument, status (open/closed)

    Query Parameters:
        - account_id: OANDA account ID (optional, filters to user's accounts)
        - strategy_id: Strategy ID (optional)
        - instrument: Currency pair (e.g., 'EUR_USD')
        - status: Position status ('open' or 'closed', default: 'open')
        - page: Page number for pagination (default: 1)
        - page_size: Number of results per page (default: 50, max: 200)

    Requirements: 9.1, 9.2
    """

    permission_classes = [IsAuthenticated]
    pagination_class = PositionPagination

    def get(self, request: Request) -> Response:
        """
        Retrieve positions with optional filtering.

        Args:
            request: HTTP request with query parameters

        Returns:
            Response with paginated position data
        """
        # Get query parameters
        account_id = request.query_params.get("account_id")
        strategy_id = request.query_params.get("strategy_id")
        trading_task_id = request.query_params.get("trading_task_id")
        instrument = request.query_params.get("instrument")
        position_status = request.query_params.get("status", "open").lower()
        opened_after = request.query_params.get("opened_after")

        # Validate status parameter
        if position_status not in ["open", "closed", "all"]:
            return Response(
                {"error": "Invalid status. Must be 'open', 'closed', or 'all'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Build queryset with filters
        filters = {
            "account_id": account_id,
            "strategy_id": strategy_id,
            "trading_task_id": trading_task_id,
            "instrument": instrument,
            "position_status": position_status,
            "opened_after": opened_after,
        }
        queryset = self.get_queryset(request, filters)

        # Handle validation errors
        if isinstance(queryset, Response):
            return queryset

        # Apply pagination
        paginator = self.pagination_class()
        paginated_queryset = paginator.paginate_queryset(queryset, request)

        serializer = PositionSerializer(paginated_queryset, many=True)

        logger.info(
            "Positions retrieved",
            extra={
                "user_id": request.user.id,
                "account_id": account_id,
                "strategy_id": strategy_id,
                "instrument": instrument,
                "status": position_status,
                "count": len(serializer.data),
            },
        )

        return paginator.get_paginated_response(serializer.data)

    def get_queryset(
        self, request: Request, filters: dict[str, str | None]
    ) -> QuerySet[Position] | Response:
        """
        Build queryset with filters.

        Args:
            request: HTTP request
            filters: Dict with account_id, strategy_id, trading_task_id,
                instrument, position_status, opened_after

        Returns:
            Filtered queryset or error response
        """
        account_id = filters.get("account_id")
        strategy_id = filters.get("strategy_id")
        trading_task_id = filters.get("trading_task_id")
        instrument = filters.get("instrument")
        position_status = filters.get("position_status")
        opened_after = filters.get("opened_after")

        # Start with base queryset filtered to user's accounts
        queryset = Position.objects.filter(account__user=request.user.id).select_related(
            "account", "strategy"
        )

        # Apply status filter
        if position_status == "open":
            queryset = queryset.filter(closed_at__isnull=True)
        elif position_status == "closed":
            queryset = queryset.filter(closed_at__isnull=False)
        # 'all' means no status filter

        # Apply account filter
        if account_id:
            try:
                account_id_int = int(account_id)
                # Ensure the account belongs to the user
                queryset = queryset.filter(account__id=account_id_int)
            except ValueError:
                return Response(
                    {"error": "Invalid account_id. Must be an integer."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Apply strategy filter
        if strategy_id:
            try:
                strategy_id_int = int(strategy_id)
                queryset = queryset.filter(strategy__id=strategy_id_int)
            except ValueError:
                return Response(
                    {"error": "Invalid strategy_id. Must be an integer."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Apply trading_task filter
        if trading_task_id:
            try:
                trading_task_id_int = int(trading_task_id)
                queryset = queryset.filter(trading_task__id=trading_task_id_int)
            except ValueError:
                return Response(
                    {"error": "Invalid trading_task_id. Must be an integer."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Apply instrument filter
        if instrument:
            queryset = queryset.filter(instrument=instrument)

        # Apply opened_after filter (for filtering by execution start time)
        if opened_after:
            from django.utils.dateparse import parse_datetime

            parsed_date = parse_datetime(opened_after)
            if parsed_date:
                queryset = queryset.filter(opened_at__gte=parsed_date)

        # Order by opened_at (newest first)
        queryset = queryset.order_by("-opened_at")

        return queryset


class PositionDetailView(APIView):
    """
    API endpoint for position detail retrieval.

    GET /api/positions/{id}
    - Retrieve detailed information for a specific position

    Requirements: 9.1, 9.2
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, position_id: int) -> Response:
        """
        Retrieve position details.

        Args:
            request: HTTP request
            position_id: Position ID

        Returns:
            Response with position data
        """
        try:
            # Get position and ensure it belongs to the user
            position = Position.objects.select_related("account", "strategy").get(
                id=position_id,
                account__user=request.user.id,
            )
        except Position.DoesNotExist:
            return Response(
                {"error": "Position not found or access denied."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = PositionSerializer(position)

        logger.info(
            "Position details retrieved",
            extra={
                "user_id": request.user.id,
                "position_id": position_id,
            },
        )

        return Response(serializer.data, status=status.HTTP_200_OK)


class PositionCloseView(APIView):
    """
    API endpoint for closing positions.

    POST /api/positions/{id}/close
    - Close a specific position at current market price or specified price

    Request Body:
        - exit_price: Exit price for the position (optional, uses current price if not provided)

    Requirements: 9.1, 9.2
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, position_id: int) -> Response:
        """
        Close a position.

        Args:
            request: HTTP request with exit_price in body
            position_id: Position ID

        Returns:
            Response with closed position data
        """
        try:
            # Get position and ensure it belongs to the user
            position = Position.objects.select_related("account", "strategy").get(
                id=position_id,
                account__user=request.user.id,
                closed_at__isnull=True,  # Ensure position is open
            )
        except Position.DoesNotExist:
            return Response(
                {"error": "Position not found, already closed, or access denied."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Get exit price from request body
        exit_price_str = request.data.get("exit_price")

        if exit_price_str:
            try:
                exit_price = Decimal(str(exit_price_str))
            except (ValueError, TypeError):
                return Response(
                    {"error": "Invalid exit_price. Must be a valid decimal number."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            # Use current price if not provided
            exit_price = position.current_price

        # Close the position
        try:
            closed_position = PositionManager.close_position(
                position=position,
                exit_price=exit_price,
                create_trade_record=True,
            )
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(
                "Failed to close position",
                extra={
                    "user_id": request.user.id,
                    "position_id": position_id,
                    "error": str(e),
                },
            )
            return Response(
                {"error": f"Failed to close position: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        serializer = PositionSerializer(closed_position)

        logger.info(
            "Position closed",
            extra={
                "user_id": request.user.id,
                "position_id": position_id,
                "exit_price": str(exit_price),
                "realized_pnl": str(closed_position.realized_pnl),
            },
        )

        return Response(serializer.data, status=status.HTTP_200_OK)
