"""Metric and chart-layer projection for strategy data endpoints.

A single execution can produce hundreds of thousands of metric rows, so the
loaders here push pagination — and, where the database supports it, the
granularity bucketing — down to SQL rather than streaming every row into
Python. ``load_paginated_metric_points`` exposes the fast path used by
:class:`~apps.trading.services.strategy_data.StrategyDataService`. The
legacy in-memory helpers remain available for tests and light-weight call
sites that still iterate over complete result sets.
"""

from __future__ import annotations

from typing import Any

from django.db import connection
from django.db.models import QuerySet
from django.db.models.expressions import RawSQL

from apps.trading.models.metrics import ExecutionMetricAggregate, Metrics
from apps.trading.services.metric_money import MetricMoneyEnricher
from apps.trading.services.strategy_data_common import (
    DEFAULT_PAGE_SIZE,
    StrategyDataQuery,
    granularity_seconds,
)
from apps.trading.services.task_metrics import (
    ensure_metrics_dict,
    filter_metrics,
)


def load_paginated_metric_points(
    *, task: Any, task_type_label: str, query: StrategyDataQuery
) -> tuple[list[dict[str, Any]], int]:
    """Load one page of metric points along with the total row count.

    * ``raw`` granularity: a plain ``ORDER BY ... LIMIT/OFFSET`` over the
      ``metrics`` table. Runs on any backend Django supports.
    * bucketed granularities (``M5``, ``H1``, ``D`` …): rely on PostgreSQL
      window functions to keep only the latest row per bucket. On non-
      PostgreSQL backends we fall back to in-memory aggregation.
    """

    descending = query.ordering == "-timestamp"
    offset = max(0, (query.page - 1) * query.page_size)
    limit = query.page_size
    seconds = granularity_seconds(query.granularity)

    qs = _base_queryset(task=task, task_type_label=task_type_label, query=query)

    enricher = MetricMoneyEnricher.for_task(task=task, task_type_label=task_type_label)

    if seconds is None:
        return _load_raw_page(
            qs=qs,
            query=query,
            enricher=enricher,
            descending=descending,
            limit=limit,
            offset=offset,
        )

    if connection.vendor == "postgresql":
        return _load_bucketed_page_postgres(
            qs=qs,
            query=query,
            enricher=enricher,
            seconds=seconds,
            descending=descending,
            limit=limit,
            offset=offset,
        )

    return _load_bucketed_page_in_memory(
        qs=qs,
        query=query,
        enricher=enricher,
        seconds=seconds,
        descending=descending,
        limit=limit,
        offset=offset,
    )


def load_latest_metric_point(
    *, task: Any, task_type_label: str, query: StrategyDataQuery
) -> dict[str, Any] | None:
    """Load the latest metric snapshot without counting the full execution."""

    aggregate = (
        ExecutionMetricAggregate.objects.filter(
            task_type=task_type_label,
            task_id=task.pk,
            execution_id=query.execution_id,
        )
        .only("latest_timestamp", "latest_metrics")
        .first()
    )
    if (
        aggregate
        and aggregate.latest_timestamp is not None
        and isinstance(aggregate.latest_metrics, dict)
        and _timestamp_matches_query(aggregate.latest_timestamp, query)
    ):
        enricher = MetricMoneyEnricher.for_task(task=task, task_type_label=task_type_label)
        return _serialize_row(
            aggregate.latest_timestamp,
            aggregate.latest_metrics,
            query.metric_keys,
            enricher=enricher,
        )

    row = (
        _base_queryset(task=task, task_type_label=task_type_label, query=query)
        .order_by("-timestamp")
        .values_list("timestamp", "metrics")
        .first()
    )
    if row is None:
        return None
    timestamp, metrics = row
    enricher = MetricMoneyEnricher.for_task(task=task, task_type_label=task_type_label)
    return _serialize_row(timestamp, metrics, query.metric_keys, enricher=enricher)


def load_metric_points(
    *, task: Any, task_type_label: str, query: StrategyDataQuery
) -> list[dict[str, Any]]:
    """Load every metric row for an execution into memory (legacy helper)."""

    qs = _base_queryset(task=task, task_type_label=task_type_label, query=query)
    enricher = MetricMoneyEnricher.for_task(task=task, task_type_label=task_type_label)
    return [
        _serialize_row(timestamp, metrics, query.metric_keys, enricher=enricher)
        for timestamp, metrics in qs.order_by("timestamp").values_list("timestamp", "metrics")
    ]


def aggregate_metric_points(rows: list[dict[str, Any]], granularity: str) -> list[dict[str, Any]]:
    """Collapse metric points to one row per bucket, keeping the latest entry."""

    seconds = granularity_seconds(granularity)
    if seconds is None:
        return rows
    bucketed: dict[int, dict[str, Any]] = {}
    for row in rows:
        bucket = int(row["t"]) // seconds * seconds
        bucketed[bucket] = row
    return [bucketed[key] for key in sorted(bucketed)]


def build_ohlc_layers(
    *,
    strategy_type: str,
    strategy_state: dict[str, Any],
    since: str | None,
    until: str | None,
    granularity: str,
    page: int,
    page_size: int,
    ordering: str,
) -> dict[str, Any]:
    return _empty_ohlc_layers()


def metric_consistency_warnings(*, task: Any, task_type_label: str, execution_id: Any) -> list[Any]:
    aggregate = (
        ExecutionMetricAggregate.objects.filter(
            task_type=task_type_label,
            task_id=task.pk,
            execution_id=execution_id,
        )
        .only("continuity_warnings")
        .first()
    )
    return (
        aggregate.continuity_warnings
        if aggregate and isinstance(aggregate.continuity_warnings, list)
        else []
    )


def _empty_ohlc_layers() -> dict[str, Any]:
    return {
        "price_series": [],
        "price_band_series": [],
        "pagination": {"count": 0, "page": 1, "page_size": DEFAULT_PAGE_SIZE},
    }


def _serialize_row(
    timestamp: Any,
    metrics: Any,
    metric_keys: tuple[str, ...],
    *,
    enricher: MetricMoneyEnricher | None = None,
) -> dict[str, Any]:
    metrics_dict = ensure_metrics_dict(metrics)
    if enricher is not None:
        metrics_dict = enricher.enrich(
            metrics_dict,
            timestamp=timestamp,
            metric_keys=metric_keys,
        )
    return {
        "t": int(timestamp.timestamp()),
        "timestamp": timestamp.isoformat(),
        "metrics": filter_metrics(metrics_dict, metric_keys),
    }


def _base_queryset(
    *, task: Any, task_type_label: str, query: StrategyDataQuery
) -> QuerySet[Metrics]:
    qs = Metrics.objects.filter(
        task_type=task_type_label,
        task_id=task.pk,
        execution_id=query.execution_id,
    )
    if query.since is not None:
        qs = qs.filter(timestamp__gte=query.since)
    if query.until is not None:
        qs = qs.filter(timestamp__lte=query.until)
    return qs


def _timestamp_matches_query(timestamp: Any, query: StrategyDataQuery) -> bool:
    if query.since is not None and timestamp < query.since:
        return False
    if query.until is not None and timestamp > query.until:
        return False
    return True


def _load_raw_page(
    *,
    qs: QuerySet[Metrics],
    query: StrategyDataQuery,
    enricher: MetricMoneyEnricher,
    descending: bool,
    limit: int,
    offset: int,
) -> tuple[list[dict[str, Any]], int]:
    total = qs.count()
    order = "-timestamp" if descending else "timestamp"
    window = qs.order_by(order).values_list("timestamp", "metrics")[offset : offset + limit]
    rows = [
        _serialize_row(ts, metrics, query.metric_keys, enricher=enricher) for ts, metrics in window
    ]
    return rows, total


def _load_bucketed_page_postgres(
    *,
    qs: QuerySet[Metrics],
    query: StrategyDataQuery,
    enricher: MetricMoneyEnricher,
    seconds: int,
    descending: bool,
    limit: int,
    offset: int,
) -> tuple[list[dict[str, Any]], int]:
    """Aggregate rows to one entry per bucket using PostgreSQL window functions."""

    bucket_expr = RawSQL(
        "(FLOOR(EXTRACT(EPOCH FROM timestamp) / %s) * %s)::bigint",
        (seconds, seconds),
    )
    # DISTINCT ON + ORDER BY bucket, timestamp DESC keeps the last tick in each bucket.
    collapsed_sql, collapsed_params = (
        qs.annotate(bucket=bucket_expr)
        .order_by("bucket", "-timestamp")
        .distinct("bucket")
        .values_list("timestamp", "metrics", "bucket")
        .query.sql_with_params()
    )

    order = "DESC" if descending else "ASC"
    # ``collapsed_sql`` comes from Django's QuerySet compiler (parameters are
    # supplied separately) and ``order`` is constrained to ``ASC``/``DESC``,
    # so the f-string composition below is safe.
    count_sql = f"SELECT COUNT(*) FROM ({collapsed_sql}) AS collapsed"  # nosec B608
    page_sql = (
        f"SELECT timestamp, metrics FROM ({collapsed_sql}) AS collapsed "  # nosec B608
        f"ORDER BY bucket {order} LIMIT %s OFFSET %s"
    )

    with connection.cursor() as cursor:
        cursor.execute(count_sql, collapsed_params)
        total = int(cursor.fetchone()[0])
        cursor.execute(page_sql, [*collapsed_params, limit, offset])
        rows = cursor.fetchall()

    return [
        _serialize_row(ts, metrics, query.metric_keys, enricher=enricher) for ts, metrics in rows
    ], total


def _load_bucketed_page_in_memory(
    *,
    qs: QuerySet[Metrics],
    query: StrategyDataQuery,
    enricher: MetricMoneyEnricher,
    seconds: int,
    descending: bool,
    limit: int,
    offset: int,
) -> tuple[list[dict[str, Any]], int]:
    """Fallback aggregation for non-PostgreSQL backends (primarily SQLite tests)."""

    bucketed: dict[int, tuple[Any, Any]] = {}
    for ts, metrics in qs.order_by("timestamp").values_list("timestamp", "metrics").iterator():
        bucket = int(ts.timestamp()) // seconds * seconds
        bucketed[bucket] = (ts, metrics)
    ordered = sorted(bucketed.items(), key=lambda item: item[0], reverse=descending)
    page = ordered[offset : offset + limit]
    rows = [
        _serialize_row(ts, metrics, query.metric_keys, enricher=enricher)
        for _, (ts, metrics) in page
    ]
    return rows, len(ordered)
