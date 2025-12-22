"""Views for trading data and operations.

This module contains views for:
- Tick data retrieval with filtering and pagination
- CSV export for backtesting
- TradingTask management
- Task lifecycle operations (start, stop, pause, resume, rerun)
"""

import logging
from datetime import timedelta
from typing import Any, Type, cast

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError, transaction
from django.db.models import Model, Q, QuerySet
from django.utils import timezone

from rest_framework import serializers as drf_serializers
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.trading.enums import TaskStatus, TaskType
from apps.trading.models import BacktestTask, TaskExecution, TradingTask
from apps.trading.serializers import (
    BacktestTaskCreateSerializer,
    BacktestTaskListSerializer,
    BacktestTaskSerializer,
    TradingTaskCreateSerializer,
    TradingTaskListSerializer,
    TradingTaskSerializer,
)
from apps.trading.services.equity import EquityService
from apps.trading.services.lock import TaskLockManager
from apps.trading.services.performance import LivePerformanceService


logger = logging.getLogger(__name__)


def _normalize_strategy_event_for_api(event: object) -> dict[str, Any] | None:
    """Normalize heterogeneous strategy event payloads to a stable API shape.

    Frontend expects items like:
      { event_type: string, description: string, details: object, timestamp?: string }

    Historical strategy payloads may be emitted as:
      { type: string, details?: object, timestamp?: string }
    """
    if not isinstance(event, dict):
        return None

    # Already normalized by a newer backend.
    if event.get("event_type") is not None:
        details_raw = event.get("details")
        details: dict[str, Any] = details_raw if isinstance(details_raw, dict) else {}
        timestamp = event.get("timestamp")
        if timestamp is None:
            timestamp = details.get("timestamp")
        return {
            **event,
            "event_type": str(event.get("event_type") or ""),
            "description": str(event.get("description") or ""),
            "details": details,
            **({"timestamp": str(timestamp)} if timestamp else {}),
        }

    raw_type = str(event.get("type") or "")
    details_raw = event.get("details")
    details = details_raw if isinstance(details_raw, dict) else {}
    timestamp = event.get("timestamp") or details.get("timestamp")

    # Best-effort classification so the UI can treat entries consistently.
    event_type = raw_type
    if raw_type == "open":
        event_type = "retracement" if details.get("retracement_open") else "initial_entry"
    elif raw_type in {"layer_retracement_opened"}:
        event_type = "retracement"
    elif raw_type in {"close"}:
        # UI maps this to Take Profit display.
        event_type = "strategy_close"
    elif raw_type in {"take_profit_hit"}:
        event_type = "take_profit"

    description = str(event.get("description") or "")
    if not description:
        description = raw_type

    out: dict[str, Any] = {
        "event_type": event_type,
        "description": description,
        "details": details,
        "type": raw_type,
    }
    if timestamp:
        out["timestamp"] = str(timestamp)
    return out


def _merge_floor_strategy_events_for_api(
    events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge near-duplicate floor events emitted for the same retracement.

    The floor strategy commonly emits two events at the same timestamp:
      - type=open (details.retracement_open=true, includes entry_price/lot_size)
      - type=layer_retracement_opened (milestone, may include current_price)

    For frontend readability we merge them into the `open` event and drop the milestone.
    """

    def _as_int(value: Any) -> int | None:
        try:
            if value is None:
                return None
            return int(value)
        except Exception:  # pylint: disable=broad-exception-caught
            return None

    def _layer_key(details: dict[str, Any]) -> int | None:
        layer_number = details.get("layer_number")
        return _as_int(layer_number if layer_number is not None else details.get("layer"))

    def _retr_key(details: dict[str, Any]) -> int | None:
        retr_count = details.get("retracement_count")
        return _as_int(retr_count if retr_count is not None else details.get("retracement"))

    def _is_retracement_open(ev_type: str, details: dict[str, Any]) -> bool:
        return ev_type == "open" and bool(details.get("retracement_open"))

    merged: list[dict[str, Any]] = []

    for e in events:
        if not merged:
            merged.append(e)
            continue

        last = merged[-1]
        last_details_raw = last.get("details")
        cur_details_raw = e.get("details")
        last_details: dict[str, Any] = (
            cast(dict[str, Any], last_details_raw) if isinstance(last_details_raw, dict) else {}
        )
        cur_details: dict[str, Any] = (
            cast(dict[str, Any], cur_details_raw) if isinstance(cur_details_raw, dict) else {}
        )

        last_type = str(last.get("type") or "")
        cur_type = str(e.get("type") or "")
        last_ts = str(last.get("timestamp") or last_details.get("timestamp") or "")
        cur_ts = str(e.get("timestamp") or cur_details.get("timestamp") or "")

        layer_last = _layer_key(last_details)
        layer_cur = _layer_key(cur_details)
        retr_last = _retr_key(last_details)
        retr_cur = _retr_key(cur_details)

        # Prefer exact timestamp matching when available, but allow merging when
        # timestamps are missing (common in older persisted metrics payloads).
        both_have_ts = last_ts != "" and cur_ts != ""
        same_ts = (both_have_ts and last_ts == cur_ts) or (not both_have_ts)
        same_layer = layer_last is not None and layer_last == layer_cur
        # Older floor events may not include retracement counters on the `open`
        # event; treat missing keys as compatible for adjacency-based merging.
        retr_compatible = (retr_last is None) or (retr_cur is None) or (retr_last == retr_cur)

        # Case A: open retracement then milestone.
        if (
            same_ts
            and same_layer
            and retr_compatible
            and _is_retracement_open(last_type, last_details)
            and cur_type == "layer_retracement_opened"
        ):
            # Prefer `open` event as primary, but enrich with milestone-only fields.
            for key in (
                "current_price",
                "max_retracements_per_layer",
                "retracement",
                "retracement_count",
                "layer_number",
            ):
                if cur_details.get(key) is not None and last_details.get(key) is None:
                    last_details[key] = cur_details.get(key)
            last["details"] = last_details
            continue

        # Case B: milestone then open retracement (rare ordering).
        if (
            same_ts
            and same_layer
            and retr_compatible
            and last_type == "layer_retracement_opened"
            and _is_retracement_open(cur_type, cur_details)
        ):
            for key in (
                "current_price",
                "max_retracements_per_layer",
                "retracement",
                "retracement_count",
                "layer_number",
            ):
                if last_details.get(key) is not None and cur_details.get(key) is None:
                    cur_details[key] = last_details.get(key)
            e["details"] = cur_details
            merged[-1] = e
            continue

        merged.append(e)

    return merged


class StrategyView(APIView):
    """API endpoint for listing all available trading strategies."""

    permission_classes = [IsAuthenticated]

    def get(self, _request: Request) -> Response:
        from apps.trading.services.registry import registry

        strategies_info = registry.get_all_strategies_info()

        strategies_list: list[dict] = []
        for strategy_id, info in strategies_info.items():
            config_schema = info.get("config_schema", {})
            display_name = config_schema.get("display_name", strategy_id)
            strategies_list.append(
                {
                    "id": strategy_id,
                    "name": display_name,
                    "description": (info.get("description") or "").strip(),
                    "config_schema": config_schema,
                }
            )

        strategies_list.sort(key=lambda x: x["name"])
        return Response(
            {"strategies": strategies_list, "count": len(strategies_list)},
            status=status.HTTP_200_OK,
        )


class StrategyDefaultsView(APIView):
    """API endpoint for returning default parameters for a strategy."""

    permission_classes = [IsAuthenticated]

    def get(self, _request: Request, strategy_id: str) -> Response:
        from apps.trading.services.registry import registry

        strategy_key = str(strategy_id or "").strip()
        if not registry.is_registered(strategy_key):
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        strategies_info = registry.get_all_strategies_info()
        config_schema = cast(
            dict[str, Any],
            (strategies_info.get(strategy_key) or {}).get("config_schema") or {},
        )
        properties = config_schema.get("properties")
        schema_keys: set[str] = set(properties.keys()) if isinstance(properties, dict) else set()

        defaults: dict[str, Any] = {}

        # Strategy-specific defaults
        if strategy_key == "floor":
            raw = getattr(settings, "TRADING_FLOOR_STRATEGY_DEFAULTS", {})
            if isinstance(raw, dict):
                defaults.update(raw)

        # If schema includes defaults, include them as a fallback.
        if isinstance(properties, dict):
            for key, prop in properties.items():
                if not isinstance(prop, dict):
                    continue
                if "default" in prop and prop.get("default") is not None:
                    defaults.setdefault(key, prop.get("default"))

        # Only return keys that are part of the schema (if schema keys are known).
        if schema_keys:
            defaults = {k: v for k, v in defaults.items() if k in schema_keys}

        return Response(
            {"strategy_id": strategy_key, "defaults": defaults},
            status=status.HTTP_200_OK,
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
        from django.db import models

        from apps.trading.models import StrategyConfig
        from apps.trading.serializers import StrategyConfigListSerializer

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
        from apps.trading.serializers import (
            StrategyConfigCreateSerializer,
            StrategyConfigDetailSerializer,
        )

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
    except ObjectDoesNotExist:
        return None


class StrategyConfigDetailView(APIView):
    """Retrieve, update, and delete a strategy configuration."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, config_id: int) -> Response:
        from apps.trading.models import StrategyConfig
        from apps.trading.serializers import StrategyConfigDetailSerializer

        try:
            config = StrategyConfig.objects.get(id=config_id, user=request.user.pk)
        except StrategyConfig.DoesNotExist:
            return Response({"error": "Configuration not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = StrategyConfigDetailSerializer(config)
        return Response(serializer.data)

    def put(self, request: Request, config_id: int) -> Response:
        from apps.trading.models import StrategyConfig
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
        from apps.trading.models import StrategyConfig

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


class TradingTaskView(ListCreateAPIView):
    """
    List and create trading tasks.

    GET: List all trading tasks for the authenticated user with filtering and pagination
    POST: Create a new trading task
    """

    permission_classes = [IsAuthenticated]

    def get_serializer_class(self) -> Type[drf_serializers.Serializer]:
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
        queryset = TradingTask.objects.filter(user=self.request.user.pk).select_related(
            "config", "oanda_account", "user"
        )

        # Filter by status
        status_param = self.request.query_params.get("status")
        if status_param:
            queryset = queryset.filter(status=status_param)

        # Filter by config ID
        config_id = self.request.query_params.get("config_id")
        if config_id:
            queryset = queryset.filter(config_id=int(config_id))

        # Filter by account ID
        oanda_account_id = self.request.query_params.get("oanda_account_id")
        if oanda_account_id:
            queryset = queryset.filter(oanda_account_id=int(oanda_account_id))

        # Filter by strategy type
        strategy_type = self.request.query_params.get("strategy_type")
        if strategy_type:
            queryset = queryset.filter(config__strategy_type=strategy_type)

        # Search in name or description
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(description__icontains=search))

        # Ordering
        ordering = self.request.query_params.get("ordering", "-created_at")
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

    def get_serializer_class(self) -> Type[drf_serializers.Serializer]:
        """Return appropriate serializer based on request method."""
        if self.request.method in ["PUT", "PATCH"]:
            return TradingTaskCreateSerializer
        return TradingTaskSerializer

    def get_queryset(self) -> QuerySet[Model]:
        """Get trading tasks for the authenticated user."""
        return TradingTask.objects.filter(user=self.request.user.pk).select_related(
            "config", "oanda_account", "user"
        )

    def destroy(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Delete trading task (disallow deletion while running)."""
        task = self.get_object()
        if task.status == TaskStatus.RUNNING:
            raise ValidationError("Cannot delete a running task. Stop it first.")
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
            task = TradingTask.objects.get(id=task_id, user=request.user.pk)
        except TradingTask.DoesNotExist:
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


class TradingTaskStartView(APIView):
    """
    Start a trading task.

    POST: Start the live trading execution
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, task_id: int) -> Response:
        """
        Start trading task execution.

        Validates task status in database AND checks celery task lock status
        before starting. Creates a new TaskExecution and queues the trading
        task for processing. Enforces one active task per account constraint.
        """
        # Get the task
        try:
            task = TradingTask.objects.get(id=task_id, user=request.user.pk)
        except TradingTask.DoesNotExist:
            return Response(
                {"error": "Trading task not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check database status first
        if task.status == TaskStatus.RUNNING:
            return Response(
                {"error": "Task is already running according to database status"},
                status=status.HTTP_409_CONFLICT,
            )

        # Check if there's an active celery task lock (actual running state)
        lock_manager = TaskLockManager()
        lock_info = lock_manager.get_lock_info(TaskType.TRADING, task_id)

        if lock_info is not None:
            # Lock exists - check if it's stale
            if not lock_info.is_stale:
                # Active lock exists - task is actually running
                return Response(
                    {
                        "error": "Task has an active execution lock. "
                        "A celery task may already be running."
                    },
                    status=status.HTTP_409_CONFLICT,
                )
            # Stale lock - clean it up before proceeding
            logger.warning(
                "Cleaning up stale lock for trading task %d before starting",
                task_id,
            )
            lock_manager.release_lock(TaskType.TRADING, task_id)

            # Also sync database status if it's inconsistent
            if task.status == TaskStatus.RUNNING:
                task.status = TaskStatus.STOPPED
                task.save(update_fields=["status", "updated_at"])
                task.refresh_from_db()

        # Validate configuration before starting
        is_valid, error_message = task.validate_configuration()
        if not is_valid:
            return Response(
                {"error": f"Configuration validation failed: {error_message}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Start the task (this also checks for other running tasks on the account)
        try:
            task.start()
        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_409_CONFLICT,
            )

        now = timezone.now()
        execution: TaskExecution | None
        try:
            with transaction.atomic():
                last_num = (
                    TaskExecution.objects.select_for_update()
                    .filter(task_type=TaskType.TRADING, task_id=task_id)
                    .order_by("-execution_number")
                    .values_list("execution_number", flat=True)
                    .first()
                )
                next_num = int(last_num or 0) + 1
                execution = TaskExecution.objects.create(
                    task_type=TaskType.TRADING,
                    task_id=task_id,
                    execution_number=next_num,
                    status=TaskStatus.RUNNING,
                    progress=0,
                    started_at=now,
                    logs=[
                        {
                            "timestamp": now.isoformat(),
                            "level": "INFO",
                            "message": "Execution queued",
                        }
                    ],
                )
        except IntegrityError:
            # Concurrent starts should be prevented by the RUNNING status, but
            # if it races, fall back to whichever execution was created.
            execution = task.get_latest_execution()

        # Queue the trading task for execution
        from apps.trading.tasks import run_trading_task

        cast(Any, run_trading_task).delay(task.pk, execution_id=execution.pk if execution else None)

        # Log lifecycle event
        logger.info(
            "Trading task %d '%s' started by user %s",
            task.pk,
            task.name,
            request.user.pk,
        )

        # Return success response
        return Response(
            {
                "message": "Trading task started successfully",
                "task_id": task.pk,
            },
            status=status.HTTP_202_ACCEPTED,
        )


class TradingTaskStopView(APIView):
    """
    Stop a running trading task.

    POST: Stop the live trading execution with configurable stop mode

    Stop modes:
    - immediate: Stop immediately without waiting (fastest, keeps positions)
    - graceful: Stop gracefully, wait for pending operations (keeps positions)
    - graceful_close: Stop gracefully and close all open positions
    """

    permission_classes = [IsAuthenticated]

    # pylint: disable=too-many-locals
    def post(self, request: Request, task_id: int) -> Response:
        """
        Stop trading task execution.

        Validates task status in database AND checks celery task lock status
        before stopping. Updates task to stopped state and triggers cleanup.

        Request body (optional):
        - mode: Stop mode ('immediate', 'graceful', 'graceful_close')
                Default: 'graceful'
        """
        from apps.trading.enums import StopMode
        from apps.trading.tasks import stop_trading_task

        # Get the task
        try:
            task = TradingTask.objects.get(id=task_id, user=request.user.pk)
        except TradingTask.DoesNotExist:
            return Response(
                {"error": "Trading task not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check celery task lock status to determine actual running state
        lock_manager = TaskLockManager()
        lock_info = lock_manager.get_lock_info(TaskType.TRADING, task_id)
        has_active_lock = lock_info is not None and not lock_info.is_stale

        # Validate task status - check both database and actual celery state
        db_is_stoppable = task.status in [TaskStatus.RUNNING, TaskStatus.PAUSED]

        if not db_is_stoppable and not has_active_lock:
            # Task is not running in database AND no active celery task
            return Response(
                {"error": "Task is not running or paused"},
                status=status.HTTP_409_CONFLICT,
            )

        # If database says not running but lock exists, sync database first
        if not db_is_stoppable and has_active_lock:
            logger.warning(
                "Trading task %d has active lock but database status is %s. "
                "Syncing database status before stopping.",
                task_id,
                task.status,
            )
            # Don't change to RUNNING, just proceed to stop

        # Get stop mode from request (default: graceful)
        mode_str = request.data.get("mode", StopMode.GRACEFUL)
        try:
            stop_mode = StopMode(mode_str)
        except ValueError:
            return Response(
                {
                    "error": f"Invalid stop mode: {mode_str}. "
                    f"Valid modes: {', '.join([m.value for m in StopMode])}"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Update task status to stopped
        task.status = TaskStatus.STOPPED

        # For graceful_close mode, clear strategy state immediately so can_resume returns false
        # This prevents Resume button from showing when positions are being closed
        update_fields = ["status", "updated_at"]
        if stop_mode == StopMode.GRACEFUL_CLOSE:
            task.strategy_state = {}
            update_fields.append("strategy_state")

        task.save(update_fields=update_fields)

        # Update latest execution if it exists and is running
        latest_execution = task.get_latest_execution()
        if latest_execution and latest_execution.status in [
            TaskStatus.RUNNING,
            TaskStatus.PAUSED,
        ]:
            latest_execution.status = TaskStatus.STOPPED
            latest_execution.completed_at = timezone.now()
            latest_execution.save(update_fields=["status", "completed_at"])

            # Add lifecycle log to execution
            latest_execution.add_log("INFO", f"=== Task STOPPED (mode: {stop_mode.label}) ===")

        # Queue the stop task with the specified mode to handle cleanup
        # (closing positions, releasing locks, etc.)
        if has_active_lock:
            cast(Any, stop_trading_task).delay(task.pk, stop_mode.value)
        else:
            # No active celery task, just clean up any stale locks
            if lock_info:
                lock_manager.release_lock(TaskType.TRADING, task_id)

        # Log lifecycle event
        logger.info(
            "Trading task %d '%s' stopped by user %s (mode: %s)",
            task.pk,
            task.name,
            request.user.pk,
            stop_mode.value,
        )

        return Response(
            {
                "message": f"Trading task stop initiated ({stop_mode.label})",
                "task_id": task.pk,
                "stop_mode": stop_mode.value,
                "status": TaskStatus.STOPPED,
            },
            status=status.HTTP_200_OK,
        )


class TradingTaskPauseView(APIView):
    """
    Pause a running trading task.

    POST: Pause the live trading execution
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, task_id: int) -> Response:
        """
        Pause trading task execution.

        Transitions task to paused state. Strategy stops making new trades but
        execution continues to track.
        """
        # Get the task
        try:
            task = TradingTask.objects.get(id=task_id, user=request.user.pk)
        except TradingTask.DoesNotExist:
            return Response(
                {"error": "Trading task not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Pause the task
        try:
            task.pause()
        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_409_CONFLICT,
            )

        # Add lifecycle log to execution
        latest_execution = task.get_latest_execution()
        if latest_execution:
            latest_execution.add_log("INFO", "=== Task PAUSED ===")

        # Log lifecycle event
        logger.info(
            "Trading task %d '%s' paused by user %s",
            task.pk,
            task.name,
            request.user.pk,
        )

        return Response(
            {"message": "Trading task paused successfully"},
            status=status.HTTP_200_OK,
        )


class TradingTaskResumeView(APIView):
    """
    Resume a paused trading task.

    POST: Resume the live trading execution
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, task_id: int) -> Response:
        """
        Resume trading task execution.

        Transitions task back to running state. Enforces one active task per account.
        """
        # Get the task
        try:
            task = TradingTask.objects.get(id=task_id, user=request.user.pk)
        except TradingTask.DoesNotExist:
            return Response(
                {"error": "Trading task not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Resume the task
        try:
            task.resume()
        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_409_CONFLICT,
            )

        # Add lifecycle log to execution
        latest_execution = task.get_latest_execution()
        if latest_execution:
            latest_execution.add_log("INFO", "=== Task RESUMED ===")

        # Log lifecycle event
        logger.info(
            "Trading task %d '%s' resumed by user %s",
            task.pk,
            task.name,
            request.user.pk,
        )

        return Response(
            {"message": "Trading task resumed successfully"},
            status=status.HTTP_200_OK,
        )


class TradingTaskRestartView(APIView):
    """
    Restart a trading task with fresh state.

    POST: Clear strategy state and start fresh execution

    Unlike resume, restart clears all saved strategy state and starts from scratch.
    Use this when you want to abandon the previous state and start over.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, task_id: int) -> Response:
        """
        Restart trading task with fresh state.

        Clears strategy_state and starts a new execution. Task can be in any
        state (stopped, failed) to be restarted, but not running or paused.

        Request body:
            - clear_state: bool (default: True) - Clear strategy state
        """
        # Get the task
        try:
            task = TradingTask.objects.get(id=task_id, user=request.user.pk)
        except TradingTask.DoesNotExist:
            return Response(
                {"error": "Trading task not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Validate configuration before restarting
        is_valid, error_message = task.validate_configuration()
        if not is_valid:
            return Response(
                {"error": f"Configuration validation failed: {error_message}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get clear_state option (default True)
        clear_state = request.data.get("clear_state", True)

        # Restart the task
        try:
            task.restart(clear_state=clear_state)
        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_409_CONFLICT,
            )

        now = timezone.now()
        execution: TaskExecution | None
        try:
            with transaction.atomic():
                last_num = (
                    TaskExecution.objects.select_for_update()
                    .filter(task_type=TaskType.TRADING, task_id=task_id)
                    .order_by("-execution_number")
                    .values_list("execution_number", flat=True)
                    .first()
                )
                next_num = int(last_num or 0) + 1
                execution = TaskExecution.objects.create(
                    task_type=TaskType.TRADING,
                    task_id=task_id,
                    execution_number=next_num,
                    status=TaskStatus.RUNNING,
                    progress=0,
                    started_at=now,
                    logs=[
                        {
                            "timestamp": now.isoformat(),
                            "level": "INFO",
                            "message": "Execution queued",
                        }
                    ],
                )
        except IntegrityError:
            execution = task.get_latest_execution()

        # Queue the trading task for execution
        from apps.trading.tasks import run_trading_task

        cast(Any, run_trading_task).delay(task.pk, execution_id=execution.pk if execution else None)

        # Log lifecycle event
        state_info = "with state cleared" if clear_state else "preserving state"
        logger.info(
            "Trading task %d '%s' restarted by user %s (%s)",
            task.pk,
            task.name,
            request.user.pk,
            state_info,
        )

        # Return success response
        return Response(
            {
                "message": "Trading task restarted successfully",
                "task_id": task.pk,
                "state_cleared": clear_state,
            },
            status=status.HTTP_202_ACCEPTED,
        )


class TradingTaskExecutionsView(APIView):
    """
    Get execution history for a trading task.

    GET: List all executions for the task
    """

    permission_classes = [IsAuthenticated]
    pagination_class = TaskExecutionPagination

    def get(self, request: Request, task_id: int) -> Response:
        """
        Get execution history for trading task.

        Returns all executions ordered by execution number (most recent first).
        """
        # Get the task
        try:
            task = TradingTask.objects.get(id=task_id, user=request.user.pk)
        except TradingTask.DoesNotExist:
            return Response(
                {"error": "Trading task not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Get execution history
        executions = task.get_execution_history()

        from apps.trading.serializers import TaskExecutionListSerializer

        paginator = self.pagination_class()
        paginated = paginator.paginate_queryset(executions, request)
        serializer = TaskExecutionListSerializer(paginated, many=True)
        return paginator.get_paginated_response(serializer.data)


class TradingTaskLogsView(APIView):
    """
    Get logs for a trading task with pagination and filtering.

    GET: Return paginated log entries from TaskExecution.logs JSONField
    """

    permission_classes = [IsAuthenticated]

    def _collect_logs(
        self, executions_query: QuerySet, level: str | None
    ) -> list[dict[str, str | int | None]]:
        """Collect and filter logs from executions."""
        all_logs = []
        for execution in executions_query:
            logs = execution.logs if isinstance(execution.logs, list) else []
            for log_entry in logs:
                if level and log_entry.get("level") != level:
                    continue

                all_logs.append(
                    {
                        "timestamp": log_entry.get("timestamp"),
                        "level": log_entry.get("level"),
                        "message": log_entry.get("message"),
                        "execution_id": execution.pk,
                        "execution_number": execution.execution_number,
                    }
                )
        return all_logs

    def get(self, request: Request, task_id: int) -> Response:
        """
        Get task logs with pagination and filtering.

        Query parameters:
        - execution_id: Filter logs for specific execution (optional)
        - level: Filter by log level (INFO, WARNING, ERROR, DEBUG) (optional)
        - page: Page number (default: 1)
        - page_size: Page size (default: 100, max: 1000)

        Returns:
            Paginated log entries with execution_number included
        """
        # Verify task exists and user has access
        try:
            TradingTask.objects.get(id=task_id, user=request.user.pk)
        except TradingTask.DoesNotExist:
            return Response(
                {"error": "Trading task not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Get and validate query parameters
        execution_id = request.query_params.get("execution_id")
        level = request.query_params.get("level")

        executions_query = TaskExecution.objects.filter(
            task_type="trading",
            task_id=task_id,
        ).order_by("execution_number")

        if execution_id:
            try:
                executions_query = executions_query.filter(id=int(execution_id))
            except ValueError:
                return Response(
                    {"error": "Invalid execution_id"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Collect, filter, and sort logs
        all_logs = self._collect_logs(executions_query, level)
        all_logs.sort(key=lambda x: str(x.get("timestamp") or ""), reverse=True)

        pagination = _paginate_list_by_page(
            request=request,
            items=all_logs,
            base_url=f"/api/trading/trading-tasks/{task_id}/logs/",
            default_page_size=100,
            max_page_size=1000,
            extra_query={
                "execution_id": execution_id,
                "level": level,
            },
        )

        return Response(pagination, status=status.HTTP_200_OK)


class TradingTaskStatusView(APIView):
    """
    Get current trading task status and execution details.

    GET: Return current status, progress, and execution information
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, task_id: int) -> Response:  # pylint: disable=too-many-locals
        """
        Get current task status and execution details.

        Used by frontend for polling fallback when WebSocket connection fails.
        Returns current status, progress percentage, and latest execution details.
        Also detects and auto-completes stale running/stopped tasks.
        """
        # Get the task
        try:
            task = TradingTask.objects.get(id=task_id, user=request.user.pk)
        except TradingTask.DoesNotExist:
            return Response(
                {"error": "Trading task not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Get latest execution
        latest_execution = task.get_latest_execution()
        lock_manager = TaskLockManager()

        # Check for stale running tasks and auto-complete them
        # But first check if task was recently started (grace period for Celery to pick up)
        task_recently_started = task.updated_at and (timezone.now() - task.updated_at) < timedelta(
            seconds=30
        )

        if task.status == TaskStatus.RUNNING and latest_execution and not task_recently_started:
            lock_info = lock_manager.get_lock_info(TaskType.TRADING, task_id)

            # Task is "running" but no lock exists or lock is stale
            is_stale = lock_info is None or lock_info.is_stale

            # Check if latest execution is already completed (stale task)
            execution_completed = latest_execution.status in [
                TaskStatus.COMPLETED,
                TaskStatus.FAILED,
                TaskStatus.STOPPED,
            ]

            # Only auto-complete if execution is done AND (no lock OR stale lock)
            if execution_completed and is_stale:
                logger.warning(
                    "Detected stale running trading task %d (execution_status=%s, is_stale=%s), "
                    "auto-completing",
                    task_id,
                    latest_execution.status,
                    is_stale,
                )

                # Clean up any stale locks
                if lock_info:
                    lock_manager.release_lock(TaskType.TRADING, task_id)

                # Update task status to match execution status
                task.status = latest_execution.status
                task.save(update_fields=["status", "updated_at"])
                task.refresh_from_db()

        # If the API queued an execution but no worker ever started it (no lock acquired),
        # fail the execution so the UI doesn't look "completed" with missing logs.
        if (
            task.status == TaskStatus.RUNNING
            and latest_execution
            and latest_execution.status == TaskStatus.RUNNING
        ):
            lock_info = lock_manager.get_lock_info(TaskType.TRADING, task_id)
            started_at = latest_execution.started_at
            startup_timeout_seconds = 120
            if (
                lock_info is None
                and started_at is not None
                and (timezone.now() - started_at) > timedelta(seconds=startup_timeout_seconds)
                and int(latest_execution.progress or 0) == 0
            ):
                msg = "Execution did not start (no worker lock acquired)"
                try:
                    latest_execution.add_log("ERROR", msg)
                except Exception:  # pylint: disable=broad-exception-caught
                    pass

                latest_execution.status = TaskStatus.FAILED
                latest_execution.completed_at = timezone.now()
                latest_execution.error_message = msg
                latest_execution.save(
                    update_fields=["status", "completed_at", "error_message", "logs"]
                )

                task.status = TaskStatus.FAILED
                task.save(update_fields=["status", "updated_at"])
                task.refresh_from_db()

        # When task is stopped but execution is still running, update execution immediately
        # The task status being STOPPED is authoritative - user requested stop
        if (
            task.status == TaskStatus.STOPPED
            and latest_execution
            and latest_execution.status == TaskStatus.RUNNING
        ):
            logger.info(
                "Trading task %d is stopped but execution still running, "
                "updating execution status",
                task_id,
            )

            # Clean up any locks
            lock_info = lock_manager.get_lock_info(TaskType.TRADING, task_id)
            if lock_info:
                lock_manager.release_lock(TaskType.TRADING, task_id)

            # Update execution to stopped
            latest_execution.status = TaskStatus.STOPPED
            latest_execution.completed_at = timezone.now()
            latest_execution.save(update_fields=["status", "completed_at"])
            latest_execution.refresh_from_db()

        # Determine the correct progress to report
        pending_new_execution = (
            task.status == TaskStatus.RUNNING
            and latest_execution
            and latest_execution.status
            in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.STOPPED]
        )

        if pending_new_execution:
            reported_progress = 0
        elif latest_execution:
            reported_progress = latest_execution.progress
        else:
            reported_progress = 0

        # Build execution details
        execution_data = None
        if latest_execution:
            execution_data = {
                "id": latest_execution.pk,
                "execution_number": latest_execution.execution_number,
                "status": latest_execution.status,
                "progress": latest_execution.progress,
                "started_at": (
                    latest_execution.started_at.isoformat() if latest_execution.started_at else None
                ),
                "completed_at": (
                    latest_execution.completed_at.isoformat()
                    if latest_execution.completed_at
                    else None
                ),
                "error_message": latest_execution.error_message or None,
            }

        # Build response data matching TaskStatusResponse interface
        response_data = {
            "task_id": task.pk,
            "task_type": "trading",
            "status": task.status,
            "progress": reported_progress,
            "pending_new_execution": pending_new_execution,
            "started_at": (
                latest_execution.started_at.isoformat()
                if latest_execution and latest_execution.started_at
                else None
            ),
            "completed_at": (
                latest_execution.completed_at.isoformat()
                if latest_execution and latest_execution.completed_at
                else None
            ),
            "error_message": (latest_execution.error_message or None) if latest_execution else None,
            "execution": execution_data,
        }

        return Response(response_data, status=status.HTTP_200_OK)


class BacktestTaskView(ListCreateAPIView):
    """List and create backtest tasks."""

    permission_classes = [IsAuthenticated]

    def get_serializer_class(self) -> Type[drf_serializers.Serializer]:
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
        status_param = self.request.query_params.get("status")
        if status_param:
            queryset = queryset.filter(status=status_param)

        # Filter by config ID
        config_id = self.request.query_params.get("config_id")
        if config_id:
            queryset = queryset.filter(config_id=int(config_id))

        # Filter by strategy type
        strategy_type = self.request.query_params.get("strategy_type")
        if strategy_type:
            queryset = queryset.filter(config__strategy_type=strategy_type)

        # Search in name or description
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(description__icontains=search))

        # Ordering
        ordering = self.request.query_params.get("ordering", "-created_at")
        queryset = queryset.order_by(ordering)

        return queryset


class BacktestTaskDetailView(RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a backtest task."""

    permission_classes = [IsAuthenticated]
    lookup_url_kwarg = "task_id"

    def get_serializer_class(self) -> Type[drf_serializers.Serializer]:
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
        """Delete backtest task (disallow deletion while running)."""
        task = cast(BacktestTask, instance)
        if task.status == TaskStatus.RUNNING:
            raise ValidationError("Cannot delete a running task. Stop it first.")
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


class BacktestTaskStartView(APIView):
    """Start a backtest task."""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, task_id: int) -> Response:
        """Start backtest task execution."""
        try:
            task = BacktestTask.objects.get(id=task_id, user=request.user.pk)
        except BacktestTask.DoesNotExist:
            return Response({"error": "Backtest task not found"}, status=status.HTTP_404_NOT_FOUND)

        if task.status == TaskStatus.RUNNING:
            return Response(
                {"error": "Task is already running according to database status"},
                status=status.HTTP_409_CONFLICT,
            )

        lock_manager = TaskLockManager()
        lock_info = lock_manager.get_lock_info(TaskType.BACKTEST, task_id)

        if lock_info is not None:
            if not lock_info.is_stale:
                return Response(
                    {"error": "Task has an active lock. The task may already be running."},
                    status=status.HTTP_409_CONFLICT,
                )

            logger.warning(
                "Cleaning up stale lock for backtest task %d before starting",
                task_id,
            )
            lock_manager.release_lock(TaskType.BACKTEST, task_id)

            if task.status == TaskStatus.RUNNING:
                task.status = TaskStatus.STOPPED
                task.save(update_fields=["status", "updated_at"])
                task.refresh_from_db()

        is_valid, error_message = task.validate_configuration()
        if not is_valid:
            return Response(
                {"error": f"Configuration validation failed: {error_message}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            task.start()
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_409_CONFLICT)

        now = timezone.now()
        execution: TaskExecution | None
        try:
            with transaction.atomic():
                last_num = (
                    TaskExecution.objects.select_for_update()
                    .filter(task_type=TaskType.BACKTEST, task_id=task_id)
                    .order_by("-execution_number")
                    .values_list("execution_number", flat=True)
                    .first()
                )
                next_num = int(last_num or 0) + 1
                execution = TaskExecution.objects.create(
                    task_type=TaskType.BACKTEST,
                    task_id=task_id,
                    execution_number=next_num,
                    status=TaskStatus.RUNNING,
                    progress=0,
                    started_at=now,
                    logs=[
                        {
                            "timestamp": now.isoformat(),
                            "level": "INFO",
                            "message": "Execution queued",
                        }
                    ],
                )
        except IntegrityError:
            execution = task.get_latest_execution()

        from apps.trading.tasks import run_backtest_task

        cast(Any, run_backtest_task).delay(
            task.pk, execution_id=execution.pk if execution else None
        )

        return Response(
            {"message": "Backtest task started successfully", "task_id": task.pk},
            status=status.HTTP_202_ACCEPTED,
        )


class BacktestTaskStopView(APIView):
    """Stop a running backtest task."""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, task_id: int) -> Response:
        """Stop backtest task execution."""
        try:
            task = BacktestTask.objects.get(id=task_id, user=request.user.pk)
        except BacktestTask.DoesNotExist:
            return Response({"error": "Backtest task not found"}, status=status.HTTP_404_NOT_FOUND)

        lock_manager = TaskLockManager()
        lock_info = lock_manager.get_lock_info(TaskType.BACKTEST, task_id)
        has_active_lock = lock_info is not None and not lock_info.is_stale

        db_is_running = task.status == TaskStatus.RUNNING
        if not db_is_running and not has_active_lock:
            return Response({"error": "Task is not running"}, status=status.HTTP_400_BAD_REQUEST)

        if not db_is_running and has_active_lock:
            logger.warning(
                "Backtest task %d has active lock but database status is %s. Proceeding with stop.",
                task_id,
                task.status,
            )

        if has_active_lock:
            lock_manager.set_cancellation_flag(TaskType.BACKTEST, task_id)
        else:
            if lock_info:
                lock_manager.release_lock(TaskType.BACKTEST, task_id)

        task.status = TaskStatus.STOPPED
        task.save(update_fields=["status", "updated_at"])

        latest_execution = task.get_latest_execution()
        if latest_execution and latest_execution.status == TaskStatus.RUNNING:
            latest_execution.status = TaskStatus.STOPPED
            latest_execution.completed_at = timezone.now()
            latest_execution.save(update_fields=["status", "completed_at"])
        return Response(
            {"id": task.pk, "status": TaskStatus.STOPPED, "message": "Task stop initiated"},
            status=status.HTTP_200_OK,
        )


class BacktestTaskStatusView(APIView):
    """Get current status of a backtest task."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, task_id: int) -> Response:
        """Get current task status and execution details."""
        try:
            task = BacktestTask.objects.get(id=task_id, user=request.user.pk)
        except BacktestTask.DoesNotExist:
            return Response({"error": "Backtest task not found"}, status=status.HTTP_404_NOT_FOUND)

        latest_execution = task.get_latest_execution()
        lock_manager = TaskLockManager()

        if task.status == TaskStatus.RUNNING and latest_execution:
            lock_info = lock_manager.get_lock_info(TaskType.BACKTEST, task_id)
            is_stale = lock_info is None or lock_info.is_stale

            execution_completed = latest_execution.status in [
                TaskStatus.COMPLETED,
                TaskStatus.FAILED,
                TaskStatus.STOPPED,
            ]

            # When a task is (re)started, there's a short window where:
            # - DB status is RUNNING (set by /start/)
            # - The new TaskExecution isn't created yet (created by Celery)
            # - The Celery lock isn't acquired yet
            # Treat that as "pending new execution" rather than "stale".
            grace_period_seconds = 30
            recently_updated = (
                task.updated_at is not None
                and timezone.now() - task.updated_at < timedelta(seconds=grace_period_seconds)
            )

            if execution_completed and is_stale and not recently_updated:
                logger.warning(
                    "Detected stale task %d (execution_status=%s, is_stale=%s), auto-completing",
                    task_id,
                    latest_execution.status,
                    is_stale,
                )

                if lock_info:
                    lock_manager.release_lock(TaskType.BACKTEST, task_id)

                task.status = latest_execution.status
                task.save(update_fields=["status", "updated_at"])
                task.refresh_from_db()

        # If the API queued an execution but no worker ever started it (no lock acquired),
        # fail the execution so users see a clear error instead of missing logs.
        if (
            task.status == TaskStatus.RUNNING
            and latest_execution
            and latest_execution.status == TaskStatus.RUNNING
        ):
            lock_info = lock_manager.get_lock_info(TaskType.BACKTEST, task_id)
            started_at = latest_execution.started_at
            startup_timeout_seconds = 120
            if (
                lock_info is None
                and started_at is not None
                and (timezone.now() - started_at) > timedelta(seconds=startup_timeout_seconds)
                and int(latest_execution.progress or 0) == 0
            ):
                msg = "Execution did not start (no worker lock acquired)"
                try:
                    latest_execution.add_log("ERROR", msg)
                except Exception:  # pylint: disable=broad-exception-caught
                    pass

                latest_execution.status = TaskStatus.FAILED
                latest_execution.completed_at = timezone.now()
                latest_execution.error_message = msg
                latest_execution.save(
                    update_fields=["status", "completed_at", "error_message", "logs"]
                )

                task.status = TaskStatus.FAILED
                task.save(update_fields=["status", "updated_at"])
                task.refresh_from_db()

        if (
            task.status == TaskStatus.STOPPED
            and latest_execution
            and latest_execution.status == TaskStatus.RUNNING
        ):
            logger.info(
                "Task %d is stopped but execution still running, updating execution status",
                task_id,
            )

            lock_info = lock_manager.get_lock_info(TaskType.BACKTEST, task_id)
            if lock_info:
                lock_manager.release_lock(TaskType.BACKTEST, task_id)

            latest_execution.status = TaskStatus.STOPPED
            latest_execution.completed_at = timezone.now()
            latest_execution.save(update_fields=["status", "completed_at"])
            latest_execution.refresh_from_db()

        pending_new_execution = (
            task.status == TaskStatus.RUNNING
            and latest_execution
            and latest_execution.status
            in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.STOPPED]
        )

        if pending_new_execution:
            reported_progress = 0
        elif latest_execution:
            reported_progress = latest_execution.progress
        else:
            reported_progress = 0

        execution_data = None
        if latest_execution:
            execution_data = {
                "id": latest_execution.pk,
                "execution_number": latest_execution.execution_number,
                "status": latest_execution.status,
                "progress": latest_execution.progress,
                "started_at": (
                    latest_execution.started_at.isoformat() if latest_execution.started_at else None
                ),
                "completed_at": (
                    latest_execution.completed_at.isoformat()
                    if latest_execution.completed_at
                    else None
                ),
                "error_message": latest_execution.error_message or None,
            }

        response_data = {
            "task_id": task.pk,
            "task_type": "backtest",
            "status": task.status,
            "progress": reported_progress,
            "pending_new_execution": pending_new_execution,
            "started_at": (
                latest_execution.started_at.isoformat()
                if latest_execution and latest_execution.started_at
                else None
            ),
            "completed_at": (
                latest_execution.completed_at.isoformat()
                if latest_execution and latest_execution.completed_at
                else None
            ),
            "error_message": (latest_execution.error_message or None) if latest_execution else None,
            "execution": execution_data,
        }

        return Response(response_data, status=status.HTTP_200_OK)


class BacktestTaskExecutionsView(APIView):
    """Get execution history for a backtest task."""

    permission_classes = [IsAuthenticated]
    pagination_class = TaskExecutionPagination

    def get(self, request: Request, task_id: int) -> Response:
        """Get execution history for backtest task."""
        try:
            task = BacktestTask.objects.get(id=task_id, user=request.user.pk)
        except BacktestTask.DoesNotExist:
            return Response({"error": "Backtest task not found"}, status=status.HTTP_404_NOT_FOUND)

        executions = task.get_execution_history()

        from apps.trading.serializers import TaskExecutionListSerializer

        paginator = self.pagination_class()
        paginated = paginator.paginate_queryset(executions, request)
        serializer = TaskExecutionListSerializer(paginated, many=True)
        return paginator.get_paginated_response(serializer.data)


class BacktestTaskExportView(APIView):
    """Export backtest results as JSON."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, task_id: int) -> Response:
        """Export complete backtest results."""
        try:
            task = BacktestTask.objects.select_related("config", "user").get(
                id=task_id, user=request.user.pk
            )
        except BacktestTask.DoesNotExist:
            return Response({"error": "Backtest task not found"}, status=status.HTTP_404_NOT_FOUND)

        latest_execution = task.get_latest_execution()
        if not latest_execution:
            return Response(
                {"error": "No execution found for this task"}, status=status.HTTP_404_NOT_FOUND
            )

        metrics_obj = _get_execution_metrics_or_none(latest_execution)
        if not metrics_obj:
            return Response(
                {"error": "No metrics available for export"},
                status=status.HTTP_404_NOT_FOUND,
            )
        metrics = None
        if metrics_obj:
            metrics = {
                "total_return": str(metrics_obj.total_return),
                "total_pnl": str(metrics_obj.total_pnl),
                "realized_pnl": str(getattr(metrics_obj, "realized_pnl", metrics_obj.total_pnl)),
                "unrealized_pnl": str(getattr(metrics_obj, "unrealized_pnl", "0.00")),
                "total_trades": metrics_obj.total_trades,
                "winning_trades": metrics_obj.winning_trades,
                "losing_trades": metrics_obj.losing_trades,
                "win_rate": str(metrics_obj.win_rate),
                "max_drawdown": str(metrics_obj.max_drawdown),
                "sharpe_ratio": str(metrics_obj.sharpe_ratio) if metrics_obj.sharpe_ratio else None,
                "profit_factor": (
                    str(metrics_obj.profit_factor) if metrics_obj.profit_factor else None
                ),
                "average_win": str(metrics_obj.average_win) if metrics_obj.average_win else None,
                "average_loss": str(metrics_obj.average_loss) if metrics_obj.average_loss else None,
                "trade_log": metrics_obj.trade_log or [],
                "strategy_events": metrics_obj.strategy_events or [],
            }

        strategy_type = task.config.strategy_type if task.config else None
        export_data = {
            "task": {
                "id": task.pk,
                "name": task.name,
                "description": task.description,
                "strategy_type": strategy_type,
                "instrument": task.instrument,
                "start_time": task.start_time.isoformat(),
                "end_time": task.end_time.isoformat(),
                "status": task.status,
            },
            "configuration": {
                "id": task.config.pk if task.config else None,
                "name": task.config.name if task.config else None,
                "strategy_type": strategy_type,
                "parameters": task.config.parameters if task.config else {},
            },
            "execution": {
                "id": latest_execution.pk,
                "execution_number": latest_execution.execution_number,
                "status": latest_execution.status,
                "started_at": (
                    latest_execution.started_at.isoformat() if latest_execution.started_at else None
                ),
                "completed_at": (
                    latest_execution.completed_at.isoformat()
                    if latest_execution.completed_at
                    else None
                ),
                "logs": latest_execution.logs or [],
            },
            "metrics": metrics,
            "exported_at": timezone.now().isoformat(),
        }

        return Response(export_data, status=status.HTTP_200_OK)


class BacktestTaskLogsView(APIView):
    """Get logs for a backtest task with pagination and filtering."""

    permission_classes = [IsAuthenticated]

    def _collect_logs(
        self, executions_query: QuerySet, level: str | None
    ) -> list[dict[str, str | int | None]]:
        all_logs = []
        for execution in executions_query:
            logs = execution.logs if isinstance(execution.logs, list) else []
            for log_entry in logs:
                if level and log_entry.get("level") != level:
                    continue

                all_logs.append(
                    {
                        "timestamp": log_entry.get("timestamp"),
                        "level": log_entry.get("level"),
                        "message": log_entry.get("message"),
                        "execution_id": execution.pk,
                        "execution_number": execution.execution_number,
                    }
                )
        return all_logs

    def get(self, request: Request, task_id: int) -> Response:
        """Get task logs with pagination and filtering."""
        try:
            BacktestTask.objects.get(id=task_id, user=request.user.pk)
        except BacktestTask.DoesNotExist:
            return Response({"error": "Backtest task not found"}, status=status.HTTP_404_NOT_FOUND)

        execution_id = request.query_params.get("execution_id")
        level = request.query_params.get("level")

        executions_query = TaskExecution.objects.filter(
            task_type="backtest", task_id=task_id
        ).order_by("execution_number")

        if execution_id:
            try:
                executions_query = executions_query.filter(id=int(execution_id))
            except ValueError:
                return Response(
                    {"error": "Invalid execution_id"}, status=status.HTTP_400_BAD_REQUEST
                )

        all_logs = self._collect_logs(executions_query, level)
        all_logs.sort(key=lambda x: str(x.get("timestamp") or ""), reverse=True)

        pagination = _paginate_list_by_page(
            request=request,
            items=all_logs,
            base_url=f"/api/trading/backtest-tasks/{task_id}/logs/",
            default_page_size=100,
            max_page_size=1000,
            extra_query={
                "execution_id": execution_id,
                "level": level,
            },
        )

        return Response(pagination, status=status.HTTP_200_OK)


class BacktestTaskResultsView(APIView):
    """Unified results endpoint for a backtest task.

    Returns live Redis snapshot when running and latest execution metrics when available.
    Equity curve is downsampled so the returned point count does not exceed 500.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, task_id: int) -> Response:
        try:
            task = BacktestTask.objects.select_related("config", "user").get(
                id=task_id, user=request.user.pk
            )
        except BacktestTask.DoesNotExist:
            return Response({"error": "Backtest task not found"}, status=status.HTTP_404_NOT_FOUND)

        latest_execution = task.get_latest_execution()
        execution_payload = None
        metrics_payload = None

        if latest_execution:
            execution_payload = {
                "id": latest_execution.pk,
                "execution_number": latest_execution.execution_number,
                "status": latest_execution.status,
                "progress": latest_execution.progress,
                "started_at": (
                    latest_execution.started_at.isoformat() if latest_execution.started_at else None
                ),
                "completed_at": (
                    latest_execution.completed_at.isoformat()
                    if latest_execution.completed_at
                    else None
                ),
                "error_message": latest_execution.error_message or None,
            }

            metrics_obj = _get_execution_metrics_or_none(latest_execution)
            if metrics_obj:
                from apps.trading.serializers import ExecutionMetricsSummarySerializer

                metrics_payload = ExecutionMetricsSummarySerializer(metrics_obj).data

        live = LivePerformanceService.get_backtest_intermediate_results(task_id)
        has_live = live is not None
        has_metrics = metrics_payload is not None

        return Response(
            {
                "task_id": task_id,
                "task_type": "backtest",
                "has_live": has_live,
                "live": live,
                "has_metrics": has_metrics,
                "metrics": metrics_payload,
                "execution": execution_payload,
            },
            status=status.HTTP_200_OK,
        )


class BacktestTaskEquityCurveView(APIView):
    """Equity curve for the latest backtest execution.

    This is split out from the unified results endpoint to keep the main payload light.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, task_id: int) -> Response:
        try:
            task = BacktestTask.objects.select_related("config", "user").get(
                id=task_id, user=request.user.pk
            )
        except BacktestTask.DoesNotExist:
            return Response({"error": "Backtest task not found"}, status=status.HTTP_404_NOT_FOUND)

        latest_execution = task.get_latest_execution()
        if not latest_execution:
            return Response(
                {
                    "task_id": task_id,
                    "task_type": "backtest",
                    "execution_id": None,
                    "has_metrics": False,
                    "equity_curve": [],
                    "count": 0,
                    "next": None,
                    "previous": None,
                    "equity_curve_granularity_seconds": None,
                },
                status=status.HTTP_200_OK,
            )

        metrics_obj = _get_execution_metrics_or_none(latest_execution)
        # Live fallback (DB-backed incremental equity points)
        if not metrics_obj:
            from apps.trading.models import ExecutionEquityPoint

            qs = (
                ExecutionEquityPoint.objects.filter(execution=latest_execution)
                .order_by("sequence", "id")
                .values("timestamp", "timestamp_raw", "balance", "created_at")
            )

            pagination = _paginate_queryset_by_page(
                request=request,
                queryset=qs,
                base_url=f"/api/trading/backtest-tasks/{task_id}/equity-curve/",
                default_page_size=500,
                max_page_size=1000,
            )

            points: list[dict[str, Any]] = []
            results_raw = pagination.get("results")
            results_rows: list[dict[str, Any]] = (
                results_raw if isinstance(results_raw, list) else []
            )
            for row in results_rows:
                ts = row.get("timestamp")
                ts_s = None
                if ts is not None and hasattr(ts, "isoformat"):
                    try:
                        ts_s = str(ts.isoformat())
                    except Exception:  # pylint: disable=broad-exception-caught
                        ts_s = None
                if not ts_s:
                    ts_s = str(row.get("timestamp_raw") or "") or str(
                        getattr(row.get("created_at"), "isoformat", lambda: "")()
                    )
                points.append({"timestamp": ts_s, "balance": float(row.get("balance") or 0)})

            return Response(
                {
                    "task_id": task_id,
                    "task_type": "backtest",
                    "execution_id": latest_execution.pk,
                    "has_metrics": len(points) > 0,
                    "equity_curve": points,
                    "count": pagination["count"],
                    "next": pagination["next"],
                    "previous": pagination["previous"],
                    "equity_curve_granularity_seconds": None,
                },
                status=status.HTTP_200_OK,
            )

        equity_service = EquityService()
        ds = equity_service.downsample_equity_curve(
            metrics_obj.equity_curve,
            max_points=500,
            start_dt=task.start_time,
            end_dt=task.end_time,
        )

        pagination = _paginate_list_by_page(
            request=request,
            items=list(ds.points),
            base_url=f"/api/trading/backtest-tasks/{task_id}/equity-curve/",
            default_page_size=500,
            max_page_size=1000,
        )

        return Response(
            {
                "task_id": task_id,
                "task_type": "backtest",
                "execution_id": latest_execution.pk,
                "has_metrics": True,
                "equity_curve": pagination["results"],
                "count": pagination["count"],
                "next": pagination["next"],
                "previous": pagination["previous"],
                "equity_curve_granularity_seconds": ds.granularity_seconds,
            },
            status=status.HTTP_200_OK,
        )


class BacktestTaskStrategyEventsView(APIView):
    """Strategy events for the latest backtest execution."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, task_id: int) -> Response:
        try:
            task = BacktestTask.objects.select_related("config", "user").get(
                id=task_id, user=request.user.pk
            )
        except BacktestTask.DoesNotExist:
            return Response({"error": "Backtest task not found"}, status=status.HTTP_404_NOT_FOUND)

        latest_execution = task.get_latest_execution()
        if not latest_execution:
            return Response(
                {
                    "task_id": task_id,
                    "task_type": "backtest",
                    "execution_id": None,
                    "has_metrics": False,
                    "strategy_events": [],
                    "count": 0,
                    "next": None,
                    "previous": None,
                },
                status=status.HTTP_200_OK,
            )

        from apps.trading.models import ExecutionStrategyEvent

        qs = (
            ExecutionStrategyEvent.objects.filter(execution=latest_execution)
            .order_by("sequence", "id")
            .values_list("event", flat=True)
        )

        pagination = _paginate_queryset_by_page(
            request=request,
            queryset=qs,
            base_url=f"/api/trading/backtest-tasks/{task_id}/strategy-events/",
            default_page_size=1000,
            max_page_size=1000,
        )

        return Response(
            {
                "task_id": task_id,
                "task_type": "backtest",
                "execution_id": latest_execution.pk,
                "has_metrics": pagination["count"] > 0,
                "strategy_events": list(pagination["results"]),
                "count": pagination["count"],
                "next": pagination["next"],
                "previous": pagination["previous"],
            },
            status=status.HTTP_200_OK,
        )


class BacktestTaskTradeLogsView(APIView):
    """Trade logs for the latest backtest execution."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, task_id: int) -> Response:
        try:
            task = BacktestTask.objects.select_related("config", "user").get(
                id=task_id, user=request.user.pk
            )
        except BacktestTask.DoesNotExist:
            return Response({"error": "Backtest task not found"}, status=status.HTTP_404_NOT_FOUND)

        latest_execution = task.get_latest_execution()
        if not latest_execution:
            return Response(
                {
                    "task_id": task_id,
                    "task_type": "backtest",
                    "execution_id": None,
                    "has_metrics": False,
                    "trade_logs": [],
                    "count": 0,
                    "next": None,
                    "previous": None,
                },
                status=status.HTTP_200_OK,
            )

        metrics_obj = _get_execution_metrics_or_none(latest_execution)
        # Live fallback (DB-backed incremental trades)
        if not metrics_obj:
            from apps.trading.models import ExecutionTradeLogEntry

            qs = (
                ExecutionTradeLogEntry.objects.filter(execution=latest_execution)
                .order_by("sequence", "id")
                .values_list("trade", flat=True)
            )

            pagination = _paginate_queryset_by_page(
                request=request,
                queryset=qs,
                base_url=f"/api/trading/backtest-tasks/{task_id}/trade-logs/",
                default_page_size=1000,
                max_page_size=1000,
            )

            return Response(
                {
                    "task_id": task_id,
                    "task_type": "backtest",
                    "execution_id": latest_execution.pk,
                    "has_metrics": pagination["count"] > 0,
                    "trade_logs": pagination["results"],
                    "count": pagination["count"],
                    "next": pagination["next"],
                    "previous": pagination["previous"],
                },
                status=status.HTTP_200_OK,
            )

        trades = metrics_obj.trade_log if isinstance(metrics_obj.trade_log, list) else []

        pagination = _paginate_list_by_page(
            request=request,
            items=list(trades),
            base_url=f"/api/trading/backtest-tasks/{task_id}/trade-logs/",
            default_page_size=1000,
            max_page_size=1000,
        )

        return Response(
            {
                "task_id": task_id,
                "task_type": "backtest",
                "execution_id": latest_execution.pk,
                "has_metrics": True,
                "trade_logs": pagination["results"],
                "count": pagination["count"],
                "next": pagination["next"],
                "previous": pagination["previous"],
            },
            status=status.HTTP_200_OK,
        )


class BacktestTaskMetricsCheckpointView(APIView):
    """Latest metrics checkpoint for the latest backtest execution."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, task_id: int) -> Response:
        try:
            task = BacktestTask.objects.select_related("config", "user").get(
                id=task_id, user=request.user.pk
            )
        except BacktestTask.DoesNotExist:
            return Response({"error": "Backtest task not found"}, status=status.HTTP_404_NOT_FOUND)

        latest_execution = task.get_latest_execution()
        if not latest_execution:
            return Response(
                {
                    "task_id": task_id,
                    "task_type": "backtest",
                    "execution_id": None,
                    "has_checkpoint": False,
                    "checkpoint": None,
                },
                status=status.HTTP_200_OK,
            )

        checkpoint = latest_execution.metrics_checkpoints.order_by("-created_at", "-id").first()

        if not checkpoint:
            return Response(
                {
                    "task_id": task_id,
                    "task_type": "backtest",
                    "execution_id": latest_execution.pk,
                    "has_checkpoint": False,
                    "checkpoint": None,
                },
                status=status.HTTP_200_OK,
            )

        return Response(
            {
                "task_id": task_id,
                "task_type": "backtest",
                "execution_id": latest_execution.pk,
                "has_checkpoint": True,
                "checkpoint": {
                    "id": checkpoint.pk,
                    "execution_id": latest_execution.pk,
                    "processed": checkpoint.processed,
                    "total_return": str(checkpoint.total_return),
                    "total_pnl": str(checkpoint.total_pnl),
                    "realized_pnl": str(checkpoint.realized_pnl),
                    "unrealized_pnl": str(checkpoint.unrealized_pnl),
                    "total_trades": checkpoint.total_trades,
                    "winning_trades": checkpoint.winning_trades,
                    "losing_trades": checkpoint.losing_trades,
                    "win_rate": str(checkpoint.win_rate),
                    "max_drawdown": str(checkpoint.max_drawdown),
                    "sharpe_ratio": (
                        str(checkpoint.sharpe_ratio)
                        if checkpoint.sharpe_ratio is not None
                        else None
                    ),
                    "profit_factor": (
                        str(checkpoint.profit_factor)
                        if checkpoint.profit_factor is not None
                        else None
                    ),
                    "average_win": str(checkpoint.average_win),
                    "average_loss": str(checkpoint.average_loss),
                    "created_at": checkpoint.created_at.isoformat(),
                },
            },
            status=status.HTTP_200_OK,
        )


class TradingTaskResultsView(APIView):
    """Unified results endpoint for a trading task.

    Returns live Redis snapshot when running and latest execution metrics when available.
    Equity curve is downsampled so the returned point count does not exceed 500.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, task_id: int) -> Response:
        try:
            task = TradingTask.objects.select_related("config", "user", "oanda_account").get(
                id=task_id, user=request.user.pk
            )
        except TradingTask.DoesNotExist:
            return Response({"error": "Trading task not found"}, status=status.HTTP_404_NOT_FOUND)

        latest_execution = task.get_latest_execution()
        execution_payload = None
        metrics_payload = None

        if latest_execution:
            execution_payload = {
                "id": latest_execution.pk,
                "execution_number": latest_execution.execution_number,
                "status": latest_execution.status,
                "progress": latest_execution.progress,
                "started_at": (
                    latest_execution.started_at.isoformat() if latest_execution.started_at else None
                ),
                "completed_at": (
                    latest_execution.completed_at.isoformat()
                    if latest_execution.completed_at
                    else None
                ),
                "error_message": latest_execution.error_message or None,
            }

            metrics_obj = _get_execution_metrics_or_none(latest_execution)
            if metrics_obj:
                from apps.trading.serializers import ExecutionMetricsSummarySerializer

                metrics_payload = ExecutionMetricsSummarySerializer(metrics_obj).data

        live = LivePerformanceService.get_trading_intermediate_results(task_id)
        has_live = live is not None
        has_metrics = metrics_payload is not None

        return Response(
            {
                "task_id": task_id,
                "task_type": "trading",
                "has_live": has_live,
                "live": live,
                "has_metrics": has_metrics,
                "metrics": metrics_payload,
                "execution": execution_payload,
            },
            status=status.HTTP_200_OK,
        )


class TradingTaskEquityCurveView(APIView):
    """Equity curve for the latest trading execution."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, task_id: int) -> Response:
        try:
            task = TradingTask.objects.select_related("config", "user", "oanda_account").get(
                id=task_id, user=request.user.pk
            )
        except TradingTask.DoesNotExist:
            return Response({"error": "Trading task not found"}, status=status.HTTP_404_NOT_FOUND)

        latest_execution = task.get_latest_execution()
        if not latest_execution:
            return Response(
                {
                    "task_id": task_id,
                    "task_type": "trading",
                    "execution_id": None,
                    "has_metrics": False,
                    "equity_curve": [],
                    "count": 0,
                    "next": None,
                    "previous": None,
                    "equity_curve_granularity_seconds": None,
                },
                status=status.HTTP_200_OK,
            )

        metrics_obj = _get_execution_metrics_or_none(latest_execution)
        # Live fallback (DB-backed incremental equity points)
        if not metrics_obj:
            from apps.trading.models import ExecutionEquityPoint

            qs = (
                ExecutionEquityPoint.objects.filter(execution=latest_execution)
                .order_by("sequence", "id")
                .values("timestamp", "timestamp_raw", "balance", "created_at")
            )

            pagination = _paginate_queryset_by_page(
                request=request,
                queryset=qs,
                base_url=f"/api/trading/trading-tasks/{task_id}/equity-curve/",
                default_page_size=500,
                max_page_size=1000,
            )

            points: list[dict[str, Any]] = []
            results_raw = pagination.get("results")
            results_rows: list[dict[str, Any]] = (
                results_raw if isinstance(results_raw, list) else []
            )
            for row in results_rows:
                ts = row.get("timestamp")
                ts_s = None
                if ts is not None and hasattr(ts, "isoformat"):
                    try:
                        ts_s = str(ts.isoformat())
                    except Exception:  # pylint: disable=broad-exception-caught
                        ts_s = None
                if not ts_s:
                    ts_s = str(row.get("timestamp_raw") or "") or str(
                        getattr(row.get("created_at"), "isoformat", lambda: "")()
                    )
                points.append({"timestamp": ts_s, "balance": float(row.get("balance") or 0)})

            return Response(
                {
                    "task_id": task_id,
                    "task_type": "trading",
                    "execution_id": latest_execution.pk,
                    "has_metrics": len(points) > 0,
                    "equity_curve": points,
                    "count": pagination["count"],
                    "next": pagination["next"],
                    "previous": pagination["previous"],
                    "equity_curve_granularity_seconds": None,
                },
                status=status.HTTP_200_OK,
            )

        equity_service = EquityService()
        ds = equity_service.downsample_equity_curve(
            metrics_obj.equity_curve,
            max_points=500,
            start_dt=latest_execution.started_at,
            end_dt=latest_execution.completed_at,
        )

        pagination = _paginate_list_by_page(
            request=request,
            items=list(ds.points),
            base_url=f"/api/trading/trading-tasks/{task_id}/equity-curve/",
            default_page_size=500,
            max_page_size=1000,
        )

        return Response(
            {
                "task_id": task_id,
                "task_type": "trading",
                "execution_id": latest_execution.pk,
                "has_metrics": True,
                "equity_curve": pagination["results"],
                "count": pagination["count"],
                "next": pagination["next"],
                "previous": pagination["previous"],
                "equity_curve_granularity_seconds": ds.granularity_seconds,
            },
            status=status.HTTP_200_OK,
        )


class TradingTaskStrategyEventsView(APIView):
    """Strategy events for the latest trading execution."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, task_id: int) -> Response:
        try:
            task = TradingTask.objects.select_related("config", "user", "oanda_account").get(
                id=task_id, user=request.user.pk
            )
        except TradingTask.DoesNotExist:
            return Response({"error": "Trading task not found"}, status=status.HTTP_404_NOT_FOUND)

        latest_execution = task.get_latest_execution()
        if not latest_execution:
            return Response(
                {
                    "task_id": task_id,
                    "task_type": "trading",
                    "execution_id": None,
                    "has_metrics": False,
                    "strategy_events": [],
                    "count": 0,
                    "next": None,
                    "previous": None,
                },
                status=status.HTTP_200_OK,
            )

        from apps.trading.models import ExecutionStrategyEvent

        qs = (
            ExecutionStrategyEvent.objects.filter(execution=latest_execution)
            .order_by("sequence", "id")
            .values_list("event", flat=True)
        )

        pagination = _paginate_queryset_by_page(
            request=request,
            queryset=qs,
            base_url=f"/api/trading/trading-tasks/{task_id}/strategy-events/",
            default_page_size=1000,
            max_page_size=1000,
        )

        return Response(
            {
                "task_id": task_id,
                "task_type": "trading",
                "execution_id": latest_execution.pk,
                "has_metrics": pagination["count"] > 0,
                "strategy_events": list(pagination["results"]),
                "count": pagination["count"],
                "next": pagination["next"],
                "previous": pagination["previous"],
            },
            status=status.HTTP_200_OK,
        )


class TradingTaskTradeLogsView(APIView):
    """Trade logs for the latest trading execution."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, task_id: int) -> Response:
        try:
            task = TradingTask.objects.select_related("config", "user", "oanda_account").get(
                id=task_id, user=request.user.pk
            )
        except TradingTask.DoesNotExist:
            return Response({"error": "Trading task not found"}, status=status.HTTP_404_NOT_FOUND)

        latest_execution = task.get_latest_execution()
        if not latest_execution:
            return Response(
                {
                    "task_id": task_id,
                    "task_type": "trading",
                    "execution_id": None,
                    "has_metrics": False,
                    "trade_logs": [],
                    "count": 0,
                    "next": None,
                    "previous": None,
                },
                status=status.HTTP_200_OK,
            )

        metrics_obj = _get_execution_metrics_or_none(latest_execution)
        # Live fallback (DB-backed incremental trades)
        if not metrics_obj:
            from apps.trading.models import ExecutionTradeLogEntry

            qs = (
                ExecutionTradeLogEntry.objects.filter(execution=latest_execution)
                .order_by("sequence", "id")
                .values_list("trade", flat=True)
            )

            pagination = _paginate_queryset_by_page(
                request=request,
                queryset=qs,
                base_url=f"/api/trading/trading-tasks/{task_id}/trade-logs/",
                default_page_size=1000,
                max_page_size=1000,
            )

            return Response(
                {
                    "task_id": task_id,
                    "task_type": "trading",
                    "execution_id": latest_execution.pk,
                    "has_metrics": pagination["count"] > 0,
                    "trade_logs": pagination["results"],
                    "count": pagination["count"],
                    "next": pagination["next"],
                    "previous": pagination["previous"],
                },
                status=status.HTTP_200_OK,
            )

        trades = metrics_obj.trade_log if isinstance(metrics_obj.trade_log, list) else []

        pagination = _paginate_list_by_page(
            request=request,
            items=list(trades),
            base_url=f"/api/trading/trading-tasks/{task_id}/trade-logs/",
            default_page_size=1000,
            max_page_size=1000,
        )

        return Response(
            {
                "task_id": task_id,
                "task_type": "trading",
                "execution_id": latest_execution.pk,
                "has_metrics": True,
                "trade_logs": pagination["results"],
                "count": pagination["count"],
                "next": pagination["next"],
                "previous": pagination["previous"],
            },
            status=status.HTTP_200_OK,
        )


class TradingTaskMetricsCheckpointView(APIView):
    """Latest metrics checkpoint for the latest trading execution."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, task_id: int) -> Response:
        try:
            task = TradingTask.objects.select_related("config", "user", "oanda_account").get(
                id=task_id, user=request.user.pk
            )
        except TradingTask.DoesNotExist:
            return Response({"error": "Trading task not found"}, status=status.HTTP_404_NOT_FOUND)

        latest_execution = task.get_latest_execution()
        if not latest_execution:
            return Response(
                {
                    "task_id": task_id,
                    "task_type": "trading",
                    "execution_id": None,
                    "has_checkpoint": False,
                    "checkpoint": None,
                },
                status=status.HTTP_200_OK,
            )

        checkpoint = latest_execution.metrics_checkpoints.order_by("-created_at", "-id").first()

        if not checkpoint:
            return Response(
                {
                    "task_id": task_id,
                    "task_type": "trading",
                    "execution_id": latest_execution.pk,
                    "has_checkpoint": False,
                    "checkpoint": None,
                },
                status=status.HTTP_200_OK,
            )

        return Response(
            {
                "task_id": task_id,
                "task_type": "trading",
                "execution_id": latest_execution.pk,
                "has_checkpoint": True,
                "checkpoint": {
                    "id": checkpoint.pk,
                    "execution_id": latest_execution.pk,
                    "processed": checkpoint.processed,
                    "total_return": str(checkpoint.total_return),
                    "total_pnl": str(checkpoint.total_pnl),
                    "realized_pnl": str(checkpoint.realized_pnl),
                    "unrealized_pnl": str(checkpoint.unrealized_pnl),
                    "total_trades": checkpoint.total_trades,
                    "winning_trades": checkpoint.winning_trades,
                    "losing_trades": checkpoint.losing_trades,
                    "win_rate": str(checkpoint.win_rate),
                    "max_drawdown": str(checkpoint.max_drawdown),
                    "sharpe_ratio": (
                        str(checkpoint.sharpe_ratio)
                        if checkpoint.sharpe_ratio is not None
                        else None
                    ),
                    "profit_factor": (
                        str(checkpoint.profit_factor)
                        if checkpoint.profit_factor is not None
                        else None
                    ),
                    "average_win": str(checkpoint.average_win),
                    "average_loss": str(checkpoint.average_loss),
                    "created_at": checkpoint.created_at.isoformat(),
                },
            },
            status=status.HTTP_200_OK,
        )
