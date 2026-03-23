"""Views for strategy configuration management."""

import logging
from typing import cast
from uuid import UUID

from django.db import IntegrityError, models
from django.db.models import ProtectedError
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import generics, serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.trading.models import StrategyConfiguration
from apps.trading.serializers import (
    StrategyConfigCreateSerializer,
    StrategyConfigDetailSerializer,
    StrategyConfigListSerializer,
)
from apps.trading.services.config_usage import list_configuration_tasks
from apps.trading.views.pagination import StandardPagination

logger = logging.getLogger(__name__)


def _integrity_constraint_id(exc: IntegrityError) -> str:
    """Extract the constraint name from an IntegrityError without leaking internals.

    Checks the psycopg2 diagnostic first, then falls back to the first
    exception arg (which Django uses to wrap the constraint name).
    The return value is only used for ``in`` checks — never sent to clients.
    """
    pg_diag = getattr(getattr(exc, "__cause__", None), "diag", None)
    name = getattr(pg_diag, "constraint_name", None)
    if name:
        return name
    return str(exc.args[0]) if exc.args else ""


class StrategyConfigView(generics.ListCreateAPIView):
    """List and create strategy configurations."""

    permission_classes = [IsAuthenticated]
    pagination_class = StandardPagination
    serializer_class = StrategyConfigListSerializer

    def get_queryset(self):
        request = cast(Request, self.request)

        strategy_type = request.query_params.get("strategy_type")
        search = request.query_params.get("search")

        queryset = StrategyConfiguration.objects.filter(user=request.user.pk)
        if strategy_type:
            queryset = queryset.filter(strategy_type=strategy_type)
        if search:
            queryset = queryset.filter(
                models.Q(name__icontains=search) | models.Q(description__icontains=search)
            )
        return queryset.order_by("-created_at")

    def get_serializer_class(self):
        if self.request.method == "POST":
            return StrategyConfigCreateSerializer
        return StrategyConfigListSerializer

    @extend_schema(
        operation_id="trading_strategy_configs_list",
        tags=["Trading"],
        responses={
            200: inline_serializer(
                "StrategyConfigPaginatedResponse",
                fields={
                    "count": serializers.IntegerField(),
                    "next": serializers.CharField(allow_null=True),
                    "previous": serializers.CharField(allow_null=True),
                    "results": StrategyConfigListSerializer(many=True),
                },
            ),
        },
    )
    def get(self, request: Request, *args, **kwargs) -> Response:
        return super().get(request, *args, **kwargs)

    @extend_schema(
        operation_id="trading_strategy_configs_create",
        tags=["Trading"],
        request=StrategyConfigCreateSerializer,
        responses={
            201: StrategyConfigDetailSerializer,
            400: inline_serializer(
                "StrategyConfigCreateError",
                fields={"detail": serializers.CharField(required=False)},
            ),
        },
    )
    def post(self, request: Request, *args, **kwargs) -> Response:
        serializer = StrategyConfigCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        try:
            config = serializer.save()
        except IntegrityError as exc:
            logger.warning("IntegrityError creating config: %s", exc)
            exc_text = _integrity_constraint_id(exc)
            if "unique_user_config_name" in exc_text or "duplicate key" in exc_text:
                return Response(
                    {"name": ["A configuration with this name already exists"]},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            raise

        response_serializer = StrategyConfigDetailSerializer(config)
        headers = self.get_success_headers(response_serializer.data)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class StrategyConfigDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, and delete a strategy configuration."""

    permission_classes = [IsAuthenticated]
    serializer_class = StrategyConfigDetailSerializer

    @extend_schema(
        operation_id="trading_strategy_config_detail",
        tags=["Trading"],
        responses={200: StrategyConfigDetailSerializer},
    )
    def get(self, request: Request, config_id: UUID) -> Response:
        try:
            config = StrategyConfiguration.objects.get(id=config_id, user=request.user.pk)
        except StrategyConfiguration.DoesNotExist:
            return Response({"error": "Configuration not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = StrategyConfigDetailSerializer(config)
        return Response(serializer.data)

    @extend_schema(
        operation_id="trading_strategy_config_update",
        tags=["Trading"],
        request=StrategyConfigCreateSerializer,
        responses={200: StrategyConfigDetailSerializer},
    )
    def put(self, request: Request, config_id: UUID) -> Response:
        try:
            config = StrategyConfiguration.objects.get(id=config_id, user=request.user.pk)
        except StrategyConfiguration.DoesNotExist:
            return Response({"error": "Configuration not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = StrategyConfigCreateSerializer(
            config, data=request.data, partial=True, context={"request": request}
        )

        if serializer.is_valid():
            updated_config = serializer.save()
            response_serializer = StrategyConfigDetailSerializer(updated_config)
            return Response(response_serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        operation_id="trading_strategy_config_delete",
        tags=["Trading"],
        responses={204: None},
    )
    def delete(self, request: Request, config_id: UUID) -> Response:
        try:
            config = StrategyConfiguration.objects.get(id=config_id, user=request.user.pk)
        except StrategyConfiguration.DoesNotExist:
            return Response({"error": "Configuration not found"}, status=status.HTTP_404_NOT_FOUND)

        if config.is_in_use():
            return Response(
                {
                    "error": "Cannot delete configuration that is in use by tasks",
                    "detail": "Delete all tasks using this configuration first",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            config.delete()
        except ProtectedError:
            return Response(
                {
                    "error": "Cannot delete configuration that is in use by tasks",
                    "detail": "Delete all tasks using this configuration first",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(status=status.HTTP_204_NO_CONTENT)


class StrategyConfigTasksView(generics.GenericAPIView):
    """List tasks using a strategy configuration."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="trading_strategy_config_tasks",
        tags=["Trading"],
        responses={
            200: inline_serializer(
                "StrategyConfigTaskUsageList",
                fields={
                    "results": serializers.ListField(
                        child=inline_serializer(
                            "StrategyConfigTaskUsage",
                            fields={
                                "id": serializers.CharField(),
                                "task_type": serializers.CharField(),
                                "name": serializers.CharField(),
                                "status": serializers.CharField(),
                            },
                        )
                    )
                },
            )
        },
    )
    def get(self, request: Request, config_id: UUID) -> Response:
        try:
            config = StrategyConfiguration.objects.get(id=config_id, user=request.user.pk)
        except StrategyConfiguration.DoesNotExist:
            return Response({"error": "Configuration not found"}, status=status.HTTP_404_NOT_FOUND)

        return Response({"results": list_configuration_tasks(config=config)})
