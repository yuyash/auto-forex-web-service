"""Recovery audit API views."""

from __future__ import annotations

from typing import Any

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request

from apps.trading.enums import TaskType
from apps.trading.models import RecoveryAttempt
from apps.trading.serializers import RecoveryAttemptSerializer


@extend_schema(
    tags=["Trading"],
    parameters=[
        OpenApiParameter("task_type", str, enum=[choice[0] for choice in TaskType.choices]),
        OpenApiParameter("task_id", str),
        OpenApiParameter("source", str),
        OpenApiParameter("result", str),
    ],
    responses={200: RecoveryAttemptSerializer(many=True)},
)
class RecoveryAttemptListView(ListAPIView):
    """Read-only list of automatic task recovery audit records."""

    serializer_class = RecoveryAttemptSerializer
    permission_classes = [IsAuthenticated]
    ordering = ("-created_at",)

    def get_queryset(self):
        """Return recovery attempts filtered by supported query parameters."""
        queryset = RecoveryAttempt.objects.all().order_by("-created_at")
        request = self.request
        assert isinstance(request, Request)

        filters: dict[str, Any] = {}
        for param_name in ("task_type", "task_id", "source", "result"):
            value = request.query_params.get(param_name)
            if value:
                filters[param_name] = value
        if filters:
            queryset = queryset.filter(**filters)
        return queryset
