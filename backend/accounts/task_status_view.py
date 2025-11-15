"""
API endpoint for checking Celery task status.

This module provides endpoints for:
- Checking status of individual tasks
- Checking status of multiple tasks (for batch operations)
"""

import logging

from celery.result import AsyncResult
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .permissions import IsAdminUser

logger = logging.getLogger(__name__)


class TaskStatusView(APIView):
    """
    API endpoint for checking Celery task status.

    POST /api/admin/task-status
    - Check status of one or more Celery tasks
    - Admin only
    """

    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request: Request) -> Response:
        """
        Check status of Celery tasks.

        Args:
            request: HTTP request with task_ids (list of task IDs)

        Returns:
            Response with task statuses
        """
        task_ids = request.data.get("task_ids", [])

        if not task_ids:
            return Response(
                {"error": "task_ids is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not isinstance(task_ids, list):
            return Response(
                {"error": "task_ids must be a list"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            task_statuses = []

            for task_id in task_ids:
                result = AsyncResult(task_id)

                task_info = {
                    "task_id": task_id,
                    "state": result.state,
                    "ready": result.ready(),
                    "successful": result.successful() if result.ready() else None,
                    "failed": result.failed() if result.ready() else None,
                }

                # Add result info if task is complete
                if result.ready():
                    if result.successful():
                        task_info["result"] = result.result
                    elif result.failed():
                        task_info["error"] = str(result.info)

                task_statuses.append(task_info)

            # Calculate overall progress
            completed = sum(1 for t in task_statuses if t["ready"])
            total = len(task_statuses)

            return Response(
                {
                    "tasks": task_statuses,
                    "progress": {
                        "completed": completed,
                        "total": total,
                        "percentage": (completed / total * 100) if total > 0 else 0,
                    },
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Failed to check task status: %s", e, exc_info=True)
            return Response(
                {
                    "error": "Failed to check task status",
                    "details": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
