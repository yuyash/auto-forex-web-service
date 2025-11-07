"""
Views for backtest operations.

This module contains views for:
- Creating and starting backtests
- Retrieving backtest status and progress
- Retrieving backtest results
- Listing user's backtests

Requirements: 12.1, 12.2, 12.4, 12.5
"""

import logging

from django.db.models import QuerySet

from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .backtest_models import Backtest
from .serializers import (
    BacktestCreateSerializer,
    BacktestListSerializer,
    BacktestSerializer,
    BacktestStatusSerializer,
)
from .tasks import run_backtest_task

logger = logging.getLogger(__name__)


class BacktestPagination(PageNumberPagination):
    """
    Pagination class for backtest list.

    Provides configurable page size with reasonable defaults and limits.

    Requirements: 12.1
    """

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class BacktestListCreateView(APIView):
    """
    API endpoint for listing and creating backtests.

    GET /api/backtest
    - List user's backtests with pagination
    - Filter by status, strategy_type, date range
    - Order by created_at (newest first)

    POST /api/backtest/start
    - Create and start a new backtest
    - Validate strategy configuration
    - Queue backtest for execution

    Query Parameters (GET):
        - status: Filter by status (pending, running, completed, failed, cancelled)
        - strategy_type: Filter by strategy type
        - start_date: Filter by created_at >= start_date
        - end_date: Filter by created_at <= end_date
        - page: Page number for pagination (default: 1)
        - page_size: Number of results per page (default: 20, max: 100)

    Requirements: 12.1, 12.2
    """

    permission_classes = [IsAuthenticated]
    pagination_class = BacktestPagination

    def get(self, request: Request) -> Response:
        """
        List user's backtests with optional filtering.

        Args:
            request: HTTP request with query parameters

        Returns:
            Response with paginated backtest list
        """
        # Get query parameters
        status_filter = request.query_params.get("status")
        strategy_type = request.query_params.get("strategy_type")
        start_date_str = request.query_params.get("start_date")
        end_date_str = request.query_params.get("end_date")

        # Build queryset with filters
        queryset = self.get_queryset(
            request,
            {
                "status": status_filter,
                "strategy_type": strategy_type,
                "start_date_str": start_date_str,
                "end_date_str": end_date_str,
            },
        )

        # Handle validation errors
        if isinstance(queryset, Response):
            return queryset

        # Apply pagination
        paginator = self.pagination_class()
        paginated_queryset = paginator.paginate_queryset(queryset, request)

        serializer = BacktestListSerializer(paginated_queryset, many=True)

        logger.info(
            "Backtests listed",
            extra={
                "user_id": request.user.id,
                "count": len(serializer.data),
                "status": status_filter,
                "strategy_type": strategy_type,
            },
        )

        return paginator.get_paginated_response(serializer.data)

    def post(self, request: Request) -> Response:
        """
        Create and start a new backtest.

        Args:
            request: HTTP request with backtest configuration

        Returns:
            Response with created backtest details
        """
        from django.contrib.auth import get_user_model

        User = get_user_model()

        serializer = BacktestCreateSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Ensure user is authenticated
        if not isinstance(request.user, User):
            return Response(
                {"error": "Authentication required"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Create backtest instance
        backtest = Backtest.objects.create(
            user=request.user,
            strategy_type=serializer.validated_data["strategy_type"],
            config=serializer.validated_data["config"],
            instruments=serializer.validated_data["instruments"],
            start_date=serializer.validated_data["start_date"],
            end_date=serializer.validated_data["end_date"],
            initial_balance=serializer.validated_data.get("initial_balance", 10000),
            commission_per_trade=serializer.validated_data.get("commission_per_trade", 0),
            memory_limit_mb=serializer.validated_data.get("memory_limit_mb", 2048),
            cpu_limit_cores=serializer.validated_data.get("cpu_limit_cores", 1),
            status="pending",
        )

        # Prepare config dictionary for Celery task
        config_dict = {
            "strategy_type": backtest.strategy_type,
            "strategy_config": backtest.config,
            "instruments": backtest.instruments,
            "start_date": backtest.start_date.isoformat(),
            "end_date": backtest.end_date.isoformat(),
            "initial_balance": float(backtest.initial_balance),
            "commission_per_trade": float(backtest.commission_per_trade),
        }

        # Queue backtest for execution
        run_backtest_task.delay(backtest.id, config_dict)

        logger.info(
            "Backtest created and queued",
            extra={
                "user_id": request.user.id,
                "backtest_id": backtest.id,
                "strategy_type": backtest.strategy_type,
                "instruments": backtest.instruments,
            },
        )

        # Return created backtest
        response_serializer = BacktestSerializer(backtest)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    def get_queryset(
        self, request: Request, filters: dict[str, str | None]
    ) -> QuerySet[Backtest] | Response:
        """
        Build queryset with filters.

        Args:
            request: HTTP request
            filters: Dict with status, strategy_type, start_date_str, end_date_str

        Returns:
            Filtered queryset or error response
        """
        from django.contrib.auth import get_user_model

        User = get_user_model()

        status_filter = filters.get("status")
        strategy_type = filters.get("strategy_type")
        start_date_str = filters.get("start_date_str")
        end_date_str = filters.get("end_date_str")

        # Ensure user is authenticated
        if not isinstance(request.user, User):
            return Response(
                {"error": "Authentication required"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Start with base queryset filtered to user's backtests
        queryset = Backtest.objects.filter(user=request.user)

        # Apply status filter
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        # Apply strategy type filter
        if strategy_type:
            queryset = queryset.filter(strategy_type=strategy_type)

        # Apply date range filters
        if start_date_str:
            try:
                from django.utils.dateparse import parse_datetime

                start_date = parse_datetime(start_date_str)
                if start_date:
                    queryset = queryset.filter(created_at__gte=start_date)
                else:
                    return Response(
                        {"error": "Invalid start_date format. Use ISO format."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            except Exception as e:
                return Response(
                    {"error": f"Invalid start_date: {str(e)}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if end_date_str:
            try:
                from django.utils.dateparse import parse_datetime

                end_date = parse_datetime(end_date_str)
                if end_date:
                    queryset = queryset.filter(created_at__lte=end_date)
                else:
                    return Response(
                        {"error": "Invalid end_date format. Use ISO format."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            except Exception as e:
                return Response(
                    {"error": f"Invalid end_date: {str(e)}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Order by created_at (newest first)
        queryset = queryset.order_by("-created_at")

        return queryset


class BacktestStatusView(APIView):
    """
    API endpoint for retrieving backtest status.

    GET /api/backtest/{id}/status
    - Get current status and progress of a backtest
    - Returns status, progress, timestamps, and error message if failed

    Requirements: 12.2
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, backtest_id: int) -> Response:
        """
        Retrieve backtest status.

        Args:
            request: HTTP request
            backtest_id: Backtest ID

        Returns:
            Response with backtest status
        """
        from django.contrib.auth import get_user_model

        User = get_user_model()

        # Ensure user is authenticated
        if not isinstance(request.user, User):
            return Response(
                {"error": "Authentication required"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        try:
            backtest = Backtest.objects.get(id=backtest_id, user=request.user)
        except Backtest.DoesNotExist:
            return Response(
                {"error": "Backtest not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = BacktestStatusSerializer(
            {
                "id": backtest.id,
                "status": backtest.status,
                "progress": backtest.progress,
                "error_message": backtest.error_message,
                "started_at": backtest.started_at,
                "completed_at": backtest.completed_at,
                "duration": backtest.duration,
                "is_running": backtest.is_running,
                "is_completed": backtest.is_completed,
            }
        )

        logger.info(
            "Backtest status retrieved",
            extra={
                "user_id": request.user.id,
                "backtest_id": backtest.id,
                "status": backtest.status,
                "progress": backtest.progress,
            },
        )

        return Response(serializer.data)


class BacktestResultsView(APIView):
    """
    API endpoint for retrieving backtest results.

    GET /api/backtest/{id}/results
    - Get complete backtest results including performance metrics
    - Returns equity curve, trade log, and all performance metrics
    - Only available for completed backtests

    Requirements: 12.4, 12.5
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, backtest_id: int) -> Response:
        """
        Retrieve backtest results.

        Args:
            request: HTTP request
            backtest_id: Backtest ID

        Returns:
            Response with backtest results
        """
        from django.contrib.auth import get_user_model

        User = get_user_model()

        # Ensure user is authenticated
        if not isinstance(request.user, User):
            return Response(
                {"error": "Authentication required"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        try:
            backtest = Backtest.objects.get(id=backtest_id, user=request.user)
        except Backtest.DoesNotExist:
            return Response(
                {"error": "Backtest not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check if backtest is completed
        if not backtest.is_completed:
            return Response(
                {
                    "error": "Backtest is not completed yet",
                    "status": backtest.status,
                    "progress": backtest.progress,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = BacktestSerializer(backtest)

        logger.info(
            "Backtest results retrieved",
            extra={
                "user_id": request.user.id,
                "backtest_id": backtest.id,
                "total_trades": backtest.total_trades,
                "total_return": float(backtest.total_return),
            },
        )

        return Response(serializer.data)
