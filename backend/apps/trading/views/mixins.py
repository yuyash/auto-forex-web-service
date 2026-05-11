"""Shared mixins for task viewsets.

Extracts common paginated action logic (logs, events, trades, positions)
used by both BacktestTaskViewSet and TradingTaskViewSet.
"""

from __future__ import annotations

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from apps.trading.views.strategy_data_mixin import TaskStrategyDataMixin
from apps.trading.views.throttles import TaskDataRateThrottle

from apps.trading.serializers.events import (
    OrderSerializer,
    PositionSerializer,
    TradeSerializer,
    TradingEventSerializer,
)
from apps.trading.serializers.money import CurrencyConversionContextSerializer, MoneySerializer
from apps.trading.services.position_money import PositionMoneyEnricher
from apps.trading.services.task_activity import TaskActivityQueryService
from apps.trading.serializers.execution import TaskExecutionSerializer
from apps.trading.serializers.summary import TaskSummarySerializer
from apps.trading.serializers.task import TaskLogSerializer
from apps.trading.services.task_metrics import (
    paginated_envelope as _paginated_envelope,
)
from apps.trading.views.query_params import (
    ExecutionDetailQueryParams,
    ExecutionDetailQueryParamsSchemaSerializer,
    ExecutionsQueryParams,
    ExecutionsQueryParamsSchemaSerializer,
    EventsQueryParamsSchemaSerializer,
    LogComponentsQueryParamsSchemaSerializer,
    LogsQueryParamsSchemaSerializer,
    OrdersQueryParamsSchemaSerializer,
    PositionLifecycleQueryParams,
    PositionLifecycleQueryParamsSchemaSerializer,
    PositionsQueryParamsSchemaSerializer,
    StrategyEventsQueryParams,
    StrategyEventsQueryParamsSchemaSerializer,
    SummaryQueryParams,
    SummaryQueryParamsSchemaSerializer,
    TradesQueryParamsSchemaSerializer,
)
from apps.trading.views.pagination import (
    ActivityPagination,
    TradePositionPagination,
)


class TaskSubResourceMixin(TaskStrategyDataMixin):
    """Mixin providing paginated logs / events / trades actions."""

    task_type_label: str

    @extend_schema(
        tags=["Trading"],
        parameters=[LogsQueryParamsSchemaSerializer],
        responses={
            200: inline_serializer(
                "TaskLogPaginatedResponse",
                fields={
                    "count": serializers.IntegerField(),
                    "next": serializers.CharField(allow_null=True),
                    "previous": serializers.CharField(allow_null=True),
                    "results": TaskLogSerializer(many=True),
                },
            )
        },
        description="Retrieve paginated task logs.",
    )
    @action(detail=True, methods=["get"], throttle_classes=[TaskDataRateThrottle])
    def logs(self, request: Request, pk: int | None = None) -> Response:
        task = self.get_object()  # type: ignore[attr-defined]
        queryset = TaskActivityQueryService().logs_queryset(
            request=request,
            task=task,
            task_type_label=self.task_type_label,
        )
        paginator = ActivityPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = TaskLogSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        tags=["Trading"],
        parameters=[LogComponentsQueryParamsSchemaSerializer],
        responses={
            200: inline_serializer(
                "TaskLogComponentsResponse",
                fields={"components": serializers.ListField(child=serializers.CharField())},
            )
        },
        description="Return distinct logger/component names for a task's logs.",
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="log-components",
        throttle_classes=[TaskDataRateThrottle],
    )
    def log_components(self, request: Request, pk: int | None = None) -> Response:
        """Return distinct component names for the task's logs."""
        task = self.get_object()  # type: ignore[attr-defined]
        components = TaskActivityQueryService().log_components(
            request=request,
            task=task,
            task_type_label=self.task_type_label,
        )
        return Response({"components": components})

    @extend_schema(
        tags=["Trading"],
        parameters=[EventsQueryParamsSchemaSerializer],
        responses={
            200: inline_serializer(
                "TaskEventPaginatedResponse",
                fields={
                    "count": serializers.IntegerField(),
                    "next": serializers.CharField(allow_null=True),
                    "previous": serializers.CharField(allow_null=True),
                    "results": TradingEventSerializer(many=True),
                },
            )
        },
        description="Retrieve paginated task events.",
    )
    @action(detail=True, methods=["get"], throttle_classes=[TaskDataRateThrottle])
    def events(self, request: Request, pk: int | None = None) -> Response:
        task = self.get_object()  # type: ignore[attr-defined]
        queryset = TaskActivityQueryService().events_queryset(
            request=request,
            task=task,
            task_type_label=self.task_type_label,
        )
        paginator = ActivityPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = TradingEventSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        tags=["Trading"],
        parameters=[StrategyEventsQueryParamsSchemaSerializer],
        responses={
            200: inline_serializer(
                "TaskStrategyCyclesResponse",
                fields={
                    "execution_id": serializers.CharField(allow_null=True),
                    "cycles": serializers.ListField(child=serializers.JSONField()),
                    "summary": serializers.JSONField(),
                    "pagination": serializers.JSONField(allow_null=True),
                    "last_tick_timestamp": serializers.CharField(allow_null=True),
                    "strategy_type": serializers.CharField(allow_null=True),
                    "visualization": serializers.JSONField(),
                },
            )
        },
        description=(
            "Retrieve strategy cycles built from Trade.cycle_id. "
            "When ``cycle_id`` is omitted, returns a paginated list of cycle "
            "aggregates (no per-cycle trade ledger).  When ``cycle_id`` is "
            "supplied, returns a single cycle with its full trade ledger."
        ),
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="strategy-events",
        throttle_classes=[TaskDataRateThrottle],
    )
    def strategy_events(self, request: Request, pk: int | None = None) -> Response:
        from apps.trading.services.strategy_cycles import StrategyCyclesService

        task = self.get_object()  # type: ignore[attr-defined]
        query = StrategyEventsQueryParams.from_request(
            request,
            default_execution_id=task.execution_id,
        )
        response = StrategyCyclesService().build(
            task=task,
            task_type=self.task_type_label,
            execution_id=query.execution_id,
            cycle_id=query.cycle_id,
            cycle_page=query.cycle_page,
            cycle_page_size=query.cycle_page_size,
            cycle_sort=query.cycle_sort,
            cycle_status=query.cycle_status,
            position_id=query.position_id,
            trade_id=query.trade_id,
        )
        return Response(response)

    @extend_schema(
        tags=["Trading"],
        parameters=[TradesQueryParamsSchemaSerializer],
        responses={
            200: inline_serializer(
                "TaskTradePaginatedResponse",
                fields={
                    "count": serializers.IntegerField(),
                    "next": serializers.CharField(allow_null=True),
                    "previous": serializers.CharField(allow_null=True),
                    "results": TradeSerializer(many=True),
                },
            )
        },
        description="Retrieve paginated task trades.",
    )
    @action(detail=True, methods=["get"], throttle_classes=[TaskDataRateThrottle])
    def trades(self, request: Request, pk: str | None = None) -> Response:
        task = self.get_object()  # type: ignore[attr-defined]
        rows, total_count, page, page_size = TaskActivityQueryService().trades(
            request=request,
            task=task,
            task_type_label=self.task_type_label,
        )
        serializer = TradeSerializer(rows, many=True)
        return Response(_paginated_envelope(request, serializer.data, total_count, page, page_size))

    @extend_schema(
        tags=["Trading"],
        parameters=[PositionsQueryParamsSchemaSerializer],
        responses={
            200: inline_serializer(
                "TaskPositionPaginatedResponse",
                fields={
                    "count": serializers.IntegerField(),
                    "next": serializers.CharField(allow_null=True),
                    "previous": serializers.CharField(allow_null=True),
                    "results": PositionSerializer(many=True),
                },
            )
        },
        description="Retrieve paginated task positions.",
    )
    @action(detail=True, methods=["get"], throttle_classes=[TaskDataRateThrottle])
    def positions(self, request: Request, pk: str | None = None) -> Response:
        task = self.get_object()  # type: ignore[attr-defined]
        queryset, query = TaskActivityQueryService().positions_queryset(
            request=request,
            task=task,
            task_type_label=self.task_type_label,
        )
        paginator = TradePositionPagination()
        page = paginator.paginate_queryset(queryset, request)
        if page is not None:
            page = PositionMoneyEnricher.for_task(
                task=task,
                task_type_label=self.task_type_label,
            ).enrich_positions(list(page))
        serializer = PositionSerializer(
            page,
            many=True,
            context={"include_trade_ids": query.include_trade_ids},
        )
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        tags=["Trading"],
        parameters=[PositionLifecycleQueryParamsSchemaSerializer],
        responses={
            200: inline_serializer(
                "TaskPositionLifecycleResponse",
                fields={
                    "requested_position_id": serializers.CharField(),
                    "matched_position_id": serializers.UUIDField(),
                    "position_ids": serializers.ListField(child=serializers.UUIDField()),
                    "positions": serializers.ListField(child=serializers.DictField()),
                    "chain_realized_pnl": serializers.CharField(allow_null=True),
                    "chain_realized_pnl_currency": serializers.CharField(
                        allow_blank=True,
                        allow_null=True,
                    ),
                    "chain_realized_pnl_money": MoneySerializer(allow_null=True),
                    "chain_realized_pnl_display_money": MoneySerializer(allow_null=True),
                    "chain_realized_pnl_display_conversion_context": (
                        CurrencyConversionContextSerializer(allow_null=True)
                    ),
                },
            )
        },
        description="Retrieve the full lifecycle chain for one position, including rebuild links.",
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="position-lifecycle",
        throttle_classes=[TaskDataRateThrottle],
    )
    def position_lifecycle(self, request: Request, pk: str | None = None) -> Response:
        from apps.trading.services.position_lifecycle import (
            PositionLifecycleQuery,
            PositionLifecycleService,
        )

        task = self.get_object()  # type: ignore[attr-defined]
        query = PositionLifecycleQueryParams.from_request(
            request,
            default_execution_id=task.execution_id,
        )
        try:
            payload = PositionLifecycleService().build(
                PositionLifecycleQuery(
                    task_type=self.task_type_label,
                    task_id=task.pk,
                    execution_id=query.execution_id,
                    position_id_query=query.position_id,
                    task=task,
                )
            )
        except ValueError as exc:
            raise ValidationError(
                {"code": "invalid_query_param", "detail": "Invalid query parameters."}
            ) from exc
        return Response(payload)

    # ------------------------------------------------------------------
    # orders (with incremental fetching via `since`)
    # ------------------------------------------------------------------
    @extend_schema(
        tags=["Trading"],
        parameters=[OrdersQueryParamsSchemaSerializer],
        responses={
            200: inline_serializer(
                "TaskOrderPaginatedResponse",
                fields={
                    "count": serializers.IntegerField(),
                    "next": serializers.CharField(allow_null=True),
                    "previous": serializers.CharField(allow_null=True),
                    "results": OrderSerializer(many=True),
                },
            )
        },
        description="Retrieve paginated task orders.",
    )
    @action(detail=True, methods=["get"], throttle_classes=[TaskDataRateThrottle])
    def orders(self, request: Request, pk: str | None = None) -> Response:
        task = self.get_object()  # type: ignore[attr-defined]
        queryset = TaskActivityQueryService().orders_queryset(
            request=request,
            task=task,
            task_type_label=self.task_type_label,
        )
        paginator = TradePositionPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = OrderSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        tags=["Trading"],
        parameters=[SummaryQueryParamsSchemaSerializer],
        responses={200: TaskSummarySerializer},
        description=(
            "Retrieve structured task summary including PnL, "
            "trade/position counts, execution state, tick info, and task status."
        ),
    )
    @action(
        detail=True, methods=["get"], url_path="summary", throttle_classes=[TaskDataRateThrottle]
    )
    def summary(self, request: Request, pk: str | None = None) -> Response:
        """Retrieve comprehensive task summary."""
        from apps.trading.services.summary import TaskSummaryResponseService

        task = self.get_object()  # type: ignore[attr-defined]
        query = SummaryQueryParams.from_request(
            request,
            default_execution_id=task.execution_id,
        )

        result = TaskSummaryResponseService().build(
            task=task,
            task_type=self.task_type_label,
            execution_id=query.execution_id,
        )

        serializer = TaskSummarySerializer(result)
        return Response(serializer.data)

    @extend_schema(
        tags=["Trading"],
        parameters=[ExecutionsQueryParamsSchemaSerializer],
        responses={
            200: inline_serializer(
                "TaskExecutionPaginatedResponse",
                fields={
                    "count": serializers.IntegerField(),
                    "next": serializers.CharField(allow_null=True),
                    "previous": serializers.CharField(allow_null=True),
                    "results": TaskExecutionSerializer(many=True),
                },
            )
        },
        description="Retrieve execution history for a task.",
    )
    @action(detail=True, methods=["get"], throttle_classes=[TaskDataRateThrottle])
    def executions(self, request: Request, pk: str | None = None) -> Response:
        from apps.trading.services.executions import list_task_executions

        task = self.get_object()  # type: ignore[attr-defined]
        query = ExecutionsQueryParams.from_request(
            request,
            default_page_size=ActivityPagination.page_size,
            max_page_size=ActivityPagination.max_page_size,
        )
        total_count, rows = list_task_executions(
            task=task,
            task_type=self.task_type_label,
            include_metrics=query.include_metrics,
            page=query.pagination.page,
            page_size=query.pagination.page_size,
        )
        serializer = TaskExecutionSerializer(rows, many=True)
        return Response(
            _paginated_envelope(
                request,
                serializer.data,
                total_count,
                query.pagination.page,
                query.pagination.page_size,
            )
        )

    @extend_schema(
        tags=["Trading"],
        parameters=[ExecutionDetailQueryParamsSchemaSerializer],
        responses={200: TaskExecutionSerializer},
        description="Retrieve a single execution record for a task.",
    )
    @action(
        detail=True,
        methods=["get"],
        url_path=r"executions/(?P<execution_id>[^/.]+)",
        throttle_classes=[TaskDataRateThrottle],
    )
    def execution_detail(
        self, request: Request, pk: str | None = None, execution_id: str | None = None
    ) -> Response:
        from apps.trading.services.executions import get_task_execution

        task = self.get_object()  # type: ignore[attr-defined]
        query = ExecutionDetailQueryParams.from_request(request)
        row = get_task_execution(
            task=task,
            task_type=self.task_type_label,
            execution_id=execution_id or "",
            include_metrics=query.include_metrics,
        )
        if row is None:
            return Response({"detail": "Execution not found."}, status=404)
        serializer = TaskExecutionSerializer(row)
        return Response(serializer.data)

    @extend_schema(
        tags=["Trading"],
        responses={204: None},
        description="Delete execution records for a task.",
    )
    @action(
        detail=True,
        methods=["delete"],
        url_path=r"executions/(?P<execution_id>[^/.]+)/delete",
        throttle_classes=[TaskDataRateThrottle],
    )
    def delete_execution(
        self, request: Request, pk: str | None = None, execution_id: str | None = None
    ) -> Response:
        """Delete a single execution and all its associated data."""
        from apps.trading.services.executions import delete_task_execution

        task = self.get_object()  # type: ignore[attr-defined]
        deleted = delete_task_execution(
            task=task,
            task_type=self.task_type_label,
            execution_id=execution_id or "",
        )
        if not deleted:
            return Response({"detail": "Execution not found."}, status=404)
        return Response(status=204)

    @extend_schema(
        tags=["Trading"],
        request=inline_serializer(
            "ExecutionNotesRequest",
            fields={
                "notes": serializers.CharField(allow_blank=True),
            },
        ),
        responses={200: TaskExecutionSerializer},
        description="Update notes for an execution.",
    )
    @action(
        detail=True,
        methods=["patch"],
        url_path=r"executions/(?P<execution_id>[^/.]+)/notes",
        throttle_classes=[TaskDataRateThrottle],
    )
    def update_execution_notes(
        self, request: Request, pk: str | None = None, execution_id: str | None = None
    ) -> Response:
        """Update notes for a specific execution."""
        from apps.trading.services.executions import (
            get_task_execution,
            update_execution_notes,
        )

        task = self.get_object()  # type: ignore[attr-defined]
        notes = request.data.get("notes", "")
        update_execution_notes(
            task_type=self.task_type_label,
            task_id=str(task.pk),
            execution_id=execution_id or "",
            notes=str(notes),
        )
        row = get_task_execution(
            task=task,
            task_type=self.task_type_label,
            execution_id=execution_id or "",
            include_metrics=False,
        )
        if row is None:
            return Response({"detail": "Execution not found."}, status=404)
        serializer = TaskExecutionSerializer(row)
        return Response(serializer.data)
