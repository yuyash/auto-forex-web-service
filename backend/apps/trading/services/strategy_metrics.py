"""Metric and chart-layer projection for strategy data endpoints."""

from __future__ import annotations

from typing import Any

from apps.trading.models.metrics import ExecutionMetricAggregate, Metrics
from apps.trading.services.strategy_data_common import (
    DEFAULT_PAGE_SIZE,
    StrategyDataQuery,
    granularity_seconds,
)
from apps.trading.services.task_metrics import ensure_metrics_dict, filter_metrics


def load_metric_points(
    *, task: Any, task_type_label: str, query: StrategyDataQuery
) -> list[dict[str, Any]]:
    qs = Metrics.objects.filter(
        task_type=task_type_label,
        task_id=task.pk,
        execution_id=query.execution_id,
    )
    if query.since:
        qs = qs.filter(timestamp__gte=query.since)
    if query.until:
        qs = qs.filter(timestamp__lte=query.until)
    return [
        {
            "t": int(timestamp.timestamp()),
            "timestamp": timestamp.isoformat(),
            "metrics": filter_metrics(ensure_metrics_dict(metrics), query.metric_keys),
        }
        for timestamp, metrics in qs.order_by("timestamp").values_list("timestamp", "metrics")
    ]


def aggregate_metric_points(rows: list[dict[str, Any]], granularity: str) -> list[dict[str, Any]]:
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
