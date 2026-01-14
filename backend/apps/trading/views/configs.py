"""Views for strategy configuration management."""

from typing import Any

from django.db import models
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.trading.models import StrategyConfig
from apps.trading.serializers import (
    StrategyConfigCreateSerializer,
    StrategyConfigDetailSerializer,
    StrategyConfigListSerializer,
)


class StrategyConfigPagination(PageNumberPagination):
    """Pagination class for strategy configurations."""

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class StrategyConfigView(APIView):
    """List and create strategy configurations."""

    permission_classes = [IsAuthenticated]
    pagination_class = StrategyConfigPagination

    def get(self, request: Request) -> Response:
        from apps.trading.models import StrategyConfig

        strategy_type = request.query_params.get("strategy_type")
        search = request.query_params.get("search")

        queryset = StrategyConfig.objects.filter(user=request.user.pk)
        if strategy_type:
            queryset = queryset.filter(strategy_type=strategy_type)
        if search:
            queryset = queryset.filter(
                models.Q(name__icontains=search) | models.Q(description__icontains=search)
            )

        queryset = queryset.order_by("-created_at")
        paginator = self.pagination_class()
        paginated_queryset = paginator.paginate_queryset(queryset, request)
        serializer = StrategyConfigListSerializer(paginated_queryset, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request: Request) -> Response:
        serializer = StrategyConfigCreateSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            try:
                config = serializer.save()
                response_serializer = StrategyConfigDetailSerializer(config)
                return Response(response_serializer.data, status=status.HTTP_201_CREATED)
            except Exception as e:
                error_message = str(e)
                if "unique_user_config_name" in error_message or "duplicate key" in error_message:
                    return Response(
                        {"name": ["A configuration with this name already exists"]},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                raise

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TaskExecutionPagination(PageNumberPagination):
    """Pagination for task execution history endpoints."""

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


def _paginate_list_by_page(
    *,
    request: Request,
    items: list,
    base_url: str,
    page_param: str = "page",
    page_size_param: str = "page_size",
    default_page_size: int = 100,
    max_page_size: int = 1000,
    extra_query: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    """Paginate an in-memory list using page/page_size.

    Returns a dict with keys: count, next, previous, results.
    """

    def _to_int(value: str | None, default: int) -> int:
        if value is None or value == "":
            return default
        return int(value)

    raw_page = request.query_params.get(page_param)
    raw_page_size = request.query_params.get(page_size_param)

    page = _to_int(raw_page, 1)
    page_size = _to_int(raw_page_size, default_page_size)

    if page < 1:
        page = 1
    if page_size < 1:
        page_size = default_page_size
    page_size = min(page_size, max_page_size)

    count = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    results = items[start:end]

    extra_query = extra_query or {}
    query_parts = [f"{page_size_param}={page_size}"] + [
        f"{k}={v}" for k, v in extra_query.items() if v is not None
    ]

    next_url = None
    if end < count:
        next_url = f"{base_url}?{page_param}={page + 1}&" + "&".join(query_parts)

    previous_url = None
    if page > 1:
        previous_url = f"{base_url}?{page_param}={page - 1}&" + "&".join(query_parts)

    return {
        "count": count,
        "next": next_url,
        "previous": previous_url,
        "results": results,
    }


def _paginate_queryset_by_page(
    *,
    request: Request,
    queryset: Any,
    base_url: str,
    page_param: str = "page",
    page_size_param: str = "page_size",
    default_page_size: int = 100,
    max_page_size: int = 1000,
    extra_query: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    """Paginate a queryset using page/page_size.

    The queryset must support slicing and .count().
    Returns a dict with keys: count, next, previous, results.
    """

    def _to_int(value: str | None, default: int) -> int:
        if value is None or value == "":
            return default
        return int(value)

    raw_page = request.query_params.get(page_param)
    raw_page_size = request.query_params.get(page_size_param)

    page = _to_int(raw_page, 1)
    page_size = _to_int(raw_page_size, default_page_size)

    if page < 1:
        page = 1
    if page_size < 1:
        page_size = default_page_size
    page_size = min(page_size, max_page_size)

    count = int(queryset.count())
    start = (page - 1) * page_size
    end = start + page_size
    results = list(queryset[start:end])

    extra_query = extra_query or {}
    query_parts = [f"{page_size_param}={page_size}"] + [
        f"{k}={v}" for k, v in extra_query.items() if v is not None
    ]

    next_url = None
    if end < count:
        next_url = f"{base_url}?{page_param}={page + 1}&" + "&".join(query_parts)

    previous_url = None
    if page > 1:
        previous_url = f"{base_url}?{page_param}={page - 1}&" + "&".join(query_parts)

    return {
        "count": count,
        "next": next_url,
        "previous": previous_url,
        "results": results,
    }


def _get_execution_metrics_or_none(execution: Any) -> Any | None:
    """Safely resolve the reverse OneToOne `execution.metrics` relation.

    Accessing a missing reverse OneToOne raises `<RelatedModel>.DoesNotExist`,
    which does *not* inherit from `AttributeError` and therefore is not safely
    handled by `getattr(..., default)` or `hasattr(...)`.
    """

    try:
        return execution.metrics
    except Exception:
        return None


class StrategyConfigDetailView(APIView):
    """Retrieve, update, and delete a strategy configuration."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, config_id: int) -> Response:
        from apps.trading.serializers import StrategyConfigDetailSerializer

        try:
            config = StrategyConfig.objects.get(id=config_id, user=request.user.pk)
        except StrategyConfig.DoesNotExist:
            return Response({"error": "Configuration not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = StrategyConfigDetailSerializer(config)
        return Response(serializer.data)

    def put(self, request: Request, config_id: int) -> Response:
        from apps.trading.serializers import (
            StrategyConfigCreateSerializer,
            StrategyConfigDetailSerializer,
        )

        try:
            config = StrategyConfig.objects.get(id=config_id, user=request.user.pk)
        except StrategyConfig.DoesNotExist:
            return Response({"error": "Configuration not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = StrategyConfigCreateSerializer(
            config, data=request.data, partial=True, context={"request": request}
        )

        if serializer.is_valid():
            updated_config = serializer.save()
            response_serializer = StrategyConfigDetailSerializer(updated_config)
            return Response(response_serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request: Request, config_id: int) -> Response:
        try:
            config = StrategyConfig.objects.get(id=config_id, user=request.user.pk)
        except StrategyConfig.DoesNotExist:
            return Response({"error": "Configuration not found"}, status=status.HTTP_404_NOT_FOUND)

        if config.is_in_use():
            return Response(
                {
                    "error": "Cannot delete configuration that is in use by active tasks",
                    "detail": "Stop or delete all tasks using this configuration first",
                },
                status=status.HTTP_409_CONFLICT,
            )

        config.delete()
        return Response(
            {"message": "Configuration deleted successfully"}, status=status.HTTP_204_NO_CONTENT
        )
