"""Views for TradingTask CRUD operations."""

from typing import Any

from django.db.models import Model, Q, QuerySet
from rest_framework import serializers as drf_serializers
from rest_framework import status
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.trading.enums import TaskStatus
from apps.trading.models import TradingTasks
from apps.trading.serializers import (
    TradingTaskCreateSerializer,
    TradingTaskListSerializer,
    TradingTaskSerializer,
)


class TradingTaskView(ListCreateAPIView):
    """
    List and create trading tasks.

    GET: List all trading tasks for the authenticated user with filtering and pagination
    POST: Create a new trading task
    """

    permission_classes = [IsAuthenticated]

    def get_serializer_class(self) -> type[drf_serializers.Serializer]:
        """Return appropriate serializer based on request method."""
        if self.request.method == "POST":
            return TradingTaskCreateSerializer
        return TradingTaskListSerializer

    def get_queryset(self) -> QuerySet:
        """
        Get trading tasks for the authenticated user with filtering.

        Query parameters:
        - status: Filter by task status
        - config_id: Filter by configuration ID
        - oanda_account_id: Filter by account ID
        - strategy_type: Filter by strategy type
        - search: Search in name or description
        - ordering: Sort field (e.g., '-created_at', 'name')
        """
        queryset = TradingTasks.objects.filter(user=self.request.user.pk).select_related(
            "config", "oanda_account", "user"
        )

        # Filter by status
        status_param = self.request.query_params.get("status")  # type: ignore[union-attr]
        if status_param:
            queryset = queryset.filter(status=status_param)

        # Filter by config ID
        config_id = self.request.query_params.get("config_id")  # type: ignore[union-attr]
        if config_id:
            queryset = queryset.filter(config_id=int(config_id))

        # Filter by account ID
        oanda_account_id = self.request.query_params.get("oanda_account_id")  # type: ignore[union-attr]
        if oanda_account_id:
            queryset = queryset.filter(oanda_account_id=int(oanda_account_id))

        # Filter by strategy type
        strategy_type = self.request.query_params.get("strategy_type")  # type: ignore[union-attr]
        if strategy_type:
            queryset = queryset.filter(config__strategy_type=strategy_type)

        # Search in name or description
        search = self.request.query_params.get("search")  # type: ignore[union-attr]
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(description__icontains=search))

        # Ordering
        ordering = self.request.query_params.get("ordering", "-created_at")  # type: ignore[union-attr]
        queryset = queryset.order_by(ordering)

        return queryset


class TradingTaskDetailView(RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, or delete a trading task.

    GET: Retrieve trading task details
    PUT/PATCH: Update trading task
    DELETE: Delete trading task
    """

    permission_classes = [IsAuthenticated]
    lookup_url_kwarg = "task_id"

    def get_serializer_class(self) -> type[drf_serializers.Serializer]:
        """Return appropriate serializer based on request method."""
        if self.request.method in ["PUT", "PATCH"]:
            return TradingTaskCreateSerializer
        return TradingTaskSerializer

    def get_queryset(self) -> QuerySet[Model]:
        """Get trading tasks for the authenticated user."""
        return TradingTasks.objects.filter(user=self.request.user.pk).select_related(
            "config", "oanda_account", "user"
        )

    def destroy(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Delete trading task.

        Automatically stops the task if running before deletion.
        """
        from logging import getLogger

        logger = getLogger(__name__)
        task = self.get_object()

        # Stop the task if running (this will set cancellation flag)
        if task.status == TaskStatus.RUNNING:
            logger.info("Stopping running trading task %d before deletion", task.pk)

            try:
                task.stop()
            except Exception as e:
                logger.warning("Failed to stop task before deletion: %s", str(e))

        return super().destroy(request, *args, **kwargs)


class TradingTaskCopyView(APIView):
    """
    Copy a trading task with a new name.

    POST: Create a copy of the task with all properties except name and ID
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, task_id: int) -> Response:
        """
        Copy trading task.

        Request body:
        - new_name: Name for the copied task (required)
        """
        # Get the task
        try:
            task = TradingTasks.objects.get(id=task_id, user=request.user.pk)
        except TradingTasks.DoesNotExist:
            return Response(
                {"error": "Trading task not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Get new name from request
        new_name = request.data.get("new_name")
        if not new_name:
            return Response(
                {"error": "new_name is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Copy the task
        try:
            new_task = task.copy(new_name)
        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Serialize and return
        serializer = TradingTaskSerializer(new_task)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
