"""
Views for strategy configuration management.

This module contains views for:
- StrategyConfig CRUD operations
- Configuration validation
- Task reference tracking

Requirements: 1.3, 1.4, 1.5, 8.1, 8.2, 8.6
"""

import logging

from django.db import models
from django.db.models import QuerySet

from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import StrategyConfig
from .serializers import (
    StrategyConfigCreateSerializer,
    StrategyConfigDetailSerializer,
    StrategyConfigListSerializer,
)

logger = logging.getLogger(__name__)


class StrategyConfigPagination(PageNumberPagination):
    """
    Pagination class for strategy configurations.

    Requirements: 1.3, 8.1
    """

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class StrategyConfigListCreateView(APIView):
    """
    API endpoint for listing and creating strategy configurations.

    GET /api/strategy-configs/
    - List user's strategy configurations
    - Support filtering by strategy_type
    - Support pagination

    POST /api/strategy-configs/
    - Create new strategy configuration
    - Validate parameters against strategy schema

    Query Parameters (GET):
        - strategy_type: Filter by strategy type
        - search: Search by name or description
        - page: Page number for pagination
        - page_size: Number of results per page

    Requirements: 1.3, 1.4, 8.1, 8.2, 8.6
    """

    permission_classes = [IsAuthenticated]
    pagination_class = StrategyConfigPagination

    def get(self, request: Request) -> Response:
        """
        List user's strategy configurations.

        Args:
            request: HTTP request with query parameters

        Returns:
            Response with paginated configuration list
        """
        # Get query parameters
        strategy_type = request.query_params.get("strategy_type")
        search = request.query_params.get("search")

        # Build queryset
        queryset = self.get_queryset(request, strategy_type, search)

        # Apply pagination
        paginator = self.pagination_class()
        paginated_queryset = paginator.paginate_queryset(queryset, request)

        # Serialize
        serializer = StrategyConfigListSerializer(paginated_queryset, many=True)

        logger.info(
            "Strategy configurations listed",
            extra={
                "user_id": request.user.id,
                "strategy_type": strategy_type,
                "count": len(serializer.data),
            },
        )

        return paginator.get_paginated_response(serializer.data)

    def post(self, request: Request) -> Response:
        """
        Create new strategy configuration.

        Args:
            request: HTTP request with configuration data

        Returns:
            Response with created configuration or validation errors
        """
        serializer = StrategyConfigCreateSerializer(data=request.data, context={"request": request})

        if serializer.is_valid():
            try:
                config = serializer.save()

                logger.info(
                    "Strategy configuration created",
                    extra={
                        "user_id": request.user.id,
                        "config_id": config.id,
                        "strategy_type": config.strategy_type,
                        "config_name": config.name,
                    },
                )

                # Return full details
                response_serializer = StrategyConfigDetailSerializer(config)
                return Response(response_serializer.data, status=status.HTTP_201_CREATED)
            except Exception as e:
                # Handle database errors like duplicate names
                error_message = str(e)
                if "unique_user_config_name" in error_message or "duplicate key" in error_message:
                    return Response(
                        {"name": ["A configuration with this name already exists"]},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                # Re-raise other exceptions
                raise

        logger.warning(
            "Strategy configuration creation failed",
            extra={
                "user_id": request.user.id,
                "errors": serializer.errors,
            },
        )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def get_queryset(
        self, request: Request, strategy_type: str | None, search: str | None
    ) -> QuerySet[StrategyConfig]:
        """
        Build queryset with filters.

        Args:
            request: HTTP request
            strategy_type: Optional strategy type filter
            search: Optional search term

        Returns:
            Filtered queryset
        """
        queryset = StrategyConfig.objects.filter(user=request.user.id)

        # Apply strategy type filter
        if strategy_type:
            queryset = queryset.filter(strategy_type=strategy_type)

        # Apply search filter
        if search:
            queryset = queryset.filter(
                models.Q(name__icontains=search) | models.Q(description__icontains=search)
            )

        return queryset.order_by("-created_at")


class StrategyConfigDetailView(APIView):
    """
    API endpoint for retrieving, updating, and deleting strategy configurations.

    GET /api/strategy-configs/{id}/
    - Get configuration details

    PUT /api/strategy-configs/{id}/
    - Update configuration
    - Validate parameters against strategy schema

    DELETE /api/strategy-configs/{id}/
    - Delete configuration
    - Prevent deletion if in use by active tasks

    Requirements: 1.3, 1.4, 1.5, 8.1, 8.2
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, config_id: int) -> Response:
        """
        Get configuration details.

        Args:
            request: HTTP request
            config_id: Configuration ID

        Returns:
            Response with configuration details or 404
        """
        try:
            config = StrategyConfig.objects.get(id=config_id, user=request.user.id)
        except StrategyConfig.DoesNotExist:
            return Response({"error": "Configuration not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = StrategyConfigDetailSerializer(config)
        return Response(serializer.data)

    def put(self, request: Request, config_id: int) -> Response:
        """
        Update configuration.

        Args:
            request: HTTP request with updated data
            config_id: Configuration ID

        Returns:
            Response with updated configuration or validation errors
        """
        try:
            config = StrategyConfig.objects.get(id=config_id, user=request.user.id)
        except StrategyConfig.DoesNotExist:
            return Response({"error": "Configuration not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = StrategyConfigCreateSerializer(
            config, data=request.data, partial=True, context={"request": request}
        )

        if serializer.is_valid():
            updated_config = serializer.save()

            logger.info(
                "Strategy configuration updated",
                extra={
                    "user_id": request.user.id,
                    "config_id": updated_config.id,
                    "config_name": updated_config.name,
                },
            )

            # Return full details
            response_serializer = StrategyConfigDetailSerializer(updated_config)
            return Response(response_serializer.data)

        logger.warning(
            "Strategy configuration update failed",
            extra={
                "user_id": request.user.id,
                "config_id": config_id,
                "errors": serializer.errors,
            },
        )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request: Request, config_id: int) -> Response:
        """
        Delete configuration.

        Args:
            request: HTTP request
            config_id: Configuration ID

        Returns:
            Response with success or error message
        """
        try:
            config = StrategyConfig.objects.get(id=config_id, user=request.user.id)
        except StrategyConfig.DoesNotExist:
            return Response({"error": "Configuration not found"}, status=status.HTTP_404_NOT_FOUND)

        # Check if configuration is in use
        if config.is_in_use():
            logger.warning(
                "Attempted to delete configuration in use",
                extra={
                    "user_id": request.user.id,
                    "config_id": config_id,
                    "config_name": config.name,
                },
            )

            return Response(
                {
                    "error": "Cannot delete configuration that is in use by active tasks",
                    "detail": "Stop or delete all tasks using this configuration first",
                },
                status=status.HTTP_409_CONFLICT,
            )

        config_name = config.name
        config.delete()

        logger.info(
            "Strategy configuration deleted",
            extra={
                "user_id": request.user.id,
                "config_id": config_id,
                "config_name": config_name,
            },
        )

        return Response(
            {"message": "Configuration deleted successfully"}, status=status.HTTP_204_NO_CONTENT
        )


class StrategyConfigTasksView(APIView):
    """
    API endpoint for listing tasks using a configuration.

    GET /api/strategy-configs/{id}/tasks/
    - List all tasks (backtest and trading) using this configuration

    Requirements: 1.5, 8.1, 8.2
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, config_id: int) -> Response:
        """
        List tasks using this configuration.

        Args:
            request: HTTP request
            config_id: Configuration ID

        Returns:
            Response with task lists or 404
        """
        try:
            config = StrategyConfig.objects.get(id=config_id, user=request.user.id)
        except StrategyConfig.DoesNotExist:
            return Response({"error": "Configuration not found"}, status=status.HTTP_404_NOT_FOUND)

        # Get referencing tasks
        tasks = config.get_referencing_tasks()

        # Serialize backtest tasks
        from .serializers import BacktestListSerializer

        backtest_data = BacktestListSerializer(tasks["backtest_tasks"], many=True).data

        # Trading tasks will be empty for now (not yet implemented)
        trading_data: list[dict] = []

        response_data = {
            "config_id": config.id,
            "config_name": config.name,
            "backtest_tasks": backtest_data,
            "trading_tasks": trading_data,
            "total_tasks": len(backtest_data) + len(trading_data),
        }

        return Response(response_data)
