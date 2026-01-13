"""Views for BacktestTask CRUD operations."""

from typing import cast

from django.db.models import Model, Q, QuerySet
from rest_framework import serializers as drf_serializers
from rest_framework import status
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.trading.enums import TaskStatus
from apps.trading.models import BacktestTask
from apps.trading.serializers import (
    BacktestTaskCreateSerializer,
    BacktestTaskListSerializer,
    BacktestTaskSerializer,
)


class BacktestTaskView(ListCreateAPIView):
    """List and create backtest tasks."""

    permission_classes = [IsAuthenticated]

    def get_serializer_class(self) -> type[drf_serializers.Serializer]:
        """Return appropriate serializer based on request method."""
        if self.request.method == "POST":
            return BacktestTaskCreateSerializer
        return BacktestTaskListSerializer

    def get_queryset(self) -> QuerySet:
        """Get backtest tasks for the authenticated user with filtering."""
        queryset = BacktestTask.objects.filter(user=self.request.user.pk).select_related(
            "config", "user"
        )

        # Filter by status
        status_param = self.request.query_params.get("status")  # type: ignore[union-attr]
        if status_param:
            queryset = queryset.filter(status=status_param)

        # Filter by config ID
        config_id = self.request.query_params.get("config_id")  # type: ignore[union-attr]
        if config_id:
            queryset = queryset.filter(config_id=int(config_id))

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


class BacktestTaskDetailView(RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a backtest task."""

    permission_classes = [IsAuthenticated]
    lookup_url_kwarg = "task_id"

    def get_serializer_class(self) -> type[drf_serializers.Serializer]:
        """Return appropriate serializer based on request method."""
        if self.request.method in ["PUT", "PATCH"]:
            return BacktestTaskCreateSerializer
        return BacktestTaskSerializer

    def get_queryset(self) -> QuerySet[Model]:
        """Get backtest tasks for the authenticated user."""
        return BacktestTask.objects.filter(user=self.request.user.pk).select_related(
            "config", "user"
        )

    def perform_destroy(self, instance: Model) -> None:
        """Delete backtest task.

        Automatically stops the task if running before deletion.
        """
        task = cast(BacktestTask, instance)

        # Stop the task if running (this will set cancellation flag)
        if task.status == TaskStatus.RUNNING:
            from logging import getLogger

            logger = getLogger(__name__)
            logger.info("Stopping running backtest task %d before deletion", task.pk)

            try:
                task.stop()
            except Exception as e:
                logger.warning("Failed to stop task before deletion: %s", str(e))

        task.delete()


class BacktestTaskCopyView(APIView):
    """Copy a backtest task with a new name."""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, task_id: int) -> Response:
        """Copy backtest task."""
        try:
            task = BacktestTask.objects.get(id=task_id, user=request.user.pk)
        except BacktestTask.DoesNotExist:
            return Response({"error": "Backtest task not found"}, status=status.HTTP_404_NOT_FOUND)

        new_name = request.data.get("new_name")
        if not new_name:
            return Response({"error": "new_name is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            new_task = task.copy(new_name)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        serializer = BacktestTaskSerializer(new_task)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
