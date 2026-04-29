"""Recovery audit API views."""

from __future__ import annotations

from typing import Any

from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request

from apps.common.querying import invalid_query_param, parse_datetime_param
from apps.trading.enums import TaskType
from apps.trading.models import RecoveryAttempt
from apps.trading.serializers import RecoveryAttemptSerializer
from apps.trading.views.pagination import StandardPagination


@extend_schema(
    tags=["Trading"],
    parameters=[
        OpenApiParameter("task_type", str, enum=[choice[0] for choice in TaskType.choices]),
        OpenApiParameter("task_id", str),
        OpenApiParameter("source", str),
        OpenApiParameter("result", str),
        OpenApiParameter("created_from", str),
        OpenApiParameter("created_to", str),
        OpenApiParameter("ordering", str),
    ],
    responses={
        200: inline_serializer(
            "RecoveryAttemptPaginatedResponse",
            fields={
                "count": serializers.IntegerField(),
                "next": serializers.CharField(allow_null=True),
                "previous": serializers.CharField(allow_null=True),
                "results": RecoveryAttemptSerializer(many=True),
            },
        )
    },
)
class RecoveryAttemptListView(ListAPIView):
    """Read-only list of automatic task recovery audit records."""

    serializer_class = RecoveryAttemptSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardPagination
    ordering = ("-created_at",)
    ordering_fields = (
        "id",
        "created_at",
        "task_type",
        "task_id",
        "source",
        "reason",
        "action",
        "result",
    )

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
        created_from = parse_datetime_param(
            request.query_params.get("created_from"),
            field_name="created_from",
        )
        created_to = parse_datetime_param(
            request.query_params.get("created_to"),
            field_name="created_to",
        )
        if created_from and created_to and created_from > created_to:
            raise invalid_query_param("created_from must be earlier than or equal to created_to")
        if created_from:
            queryset = queryset.filter(created_at__gte=created_from)
        if created_to:
            queryset = queryset.filter(created_at__lte=created_to)
        return queryset
