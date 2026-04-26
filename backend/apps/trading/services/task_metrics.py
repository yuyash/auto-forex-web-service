"""Query services for task metric API resources."""

from __future__ import annotations

import json
import math
from typing import Any
from urllib.parse import urlencode

from django.db import connection
from rest_framework.request import Request

from apps.trading.models.metrics import ExecutionMetricAggregate, Metrics
from apps.trading.models.state import ExecutionState
from apps.trading.views.pagination import MetricsPagination
from apps.trading.views.query_params import MetricsQueryParams


def ensure_metrics_dict(value: Any) -> dict:
    """Ensure a metrics value is a dict, including double-encoded JSON strings."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
    return {}


def filter_metrics(metrics: dict, metric_keys: tuple[str, ...]) -> dict:
    """Return only requested metric keys when a metrics key filter is present."""
    if not metric_keys:
        return metrics
    return {key: metrics[key] for key in metric_keys if key in metrics}


def paginated_envelope(
    request: Request,
    results: list,
    total: int,
    page: int,
    page_size: int,
) -> dict:
    """Build a standard paginated response envelope."""
    total_pages = math.ceil(total / page_size) if page_size else 1
    base_url = request.build_absolute_uri(request.path)
    params = request.query_params.copy()

    def build_url(p: int) -> str | None:
        if p < 1 or p > total_pages:
            return None
        params["page"] = str(p)
        params["page_size"] = str(page_size)
        qs = urlencode(params, doseq=True)
        return f"{base_url}?{qs}"

    return {
        "count": total,
        "next": build_url(page + 1),
        "previous": build_url(page - 1),
        "results": results,
    }


class TaskMetricsQueryService:
    """Build task metrics payloads for API views."""

    def list_metrics(self, *, request: Request, task, task_type_label: str) -> dict:
        query = MetricsQueryParams.from_request(
            request,
            default_execution_id=task.execution_id,
            default_page_size=MetricsPagination.page_size,
            max_page_size=MetricsPagination.max_page_size,
        )
        queryset = Metrics.objects.filter(
            task_type=task_type_label,
            task_id=task.pk,
            execution_id=query.execution.execution_id,
        ).order_by("timestamp")
        metadata = self._metadata(
            task=task,
            task_type_label=task_type_label,
            execution_id=query.execution.execution_id,
        )

        if query.execution.since:
            queryset = queryset.filter(timestamp__gt=query.execution.since)
        if query.until:
            queryset = queryset.filter(timestamp__lt=query.until)

        interval = query.interval
        page = query.execution.pagination.page
        page_size = query.execution.pagination.page_size

        if interval > 1:
            if connection.vendor != "postgresql":
                envelope = self._windowed_python(
                    request=request,
                    queryset=queryset,
                    interval=interval,
                    page=page,
                    page_size=page_size,
                    metric_keys=query.metric_keys,
                )
                return self._attach_metadata(envelope, metadata, "db_window_last_python")

            envelope = self._windowed_postgres(
                request=request,
                task=task,
                task_type_label=task_type_label,
                query=query,
                interval=interval,
                page=page,
                page_size=page_size,
            )
            return self._attach_metadata(envelope, metadata, "db_window_last")

        total_count = queryset.count()
        start = (page - 1) * page_size
        rows = queryset.values_list("timestamp", "metrics")[start : start + page_size]
        data = [
            {
                "t": int(ts.timestamp()),
                "metrics": filter_metrics(ensure_metrics_dict(m), query.metric_keys),
            }
            for ts, m in rows
        ]
        envelope = paginated_envelope(request, data, total_count, page, page_size)
        return self._attach_metadata(envelope, metadata, "db_raw")

    def latest_metric(self, *, request: Request, task, task_type_label: str) -> dict:
        query = MetricsQueryParams.from_request(
            request,
            default_execution_id=task.execution_id,
            default_page_size=1,
            max_page_size=1,
        )
        row = (
            Metrics.objects.filter(
                task_type=task_type_label,
                task_id=task.pk,
                execution_id=query.execution.execution_id,
            )
            .order_by("-timestamp")
            .values_list("timestamp", "metrics")
            .first()
        )
        state_row = (
            ExecutionState.objects.filter(
                task_type=task_type_label,
                task_id=task.pk,
                execution_id=query.execution.execution_id,
            )
            .order_by("-updated_at")
            .values_list("resume_cursor_timestamp", "last_tick_timestamp", "strategy_state")
            .first()
        )
        metadata = self._metadata(
            task=task,
            task_type_label=task_type_label,
            execution_id=query.execution.execution_id,
        )
        if state_row is not None:
            state_ts = state_row[0] or state_row[1]
            strategy_state = state_row[2] if isinstance(state_row[2], dict) else {}
            state_metrics = (
                strategy_state.get("metrics") if isinstance(strategy_state, dict) else None
            )
            row_ts = row[0] if row is not None else None
            if (
                state_ts is not None
                and isinstance(state_metrics, dict)
                and (row_ts is None or state_ts >= row_ts)
            ):
                return {
                    "data_source": "state_latest",
                    **metadata,
                    "result": {
                        "t": int(state_ts.timestamp()),
                        "metrics": filter_metrics(
                            ensure_metrics_dict(state_metrics), query.metric_keys
                        ),
                    },
                }
        return {
            "data_source": "db_latest",
            **metadata,
            "result": (
                {
                    "t": int(row[0].timestamp()),
                    "metrics": filter_metrics(ensure_metrics_dict(row[1]), query.metric_keys),
                }
                if row is not None
                else None
            ),
        }

    @staticmethod
    def _metadata(*, task, task_type_label: str, execution_id) -> dict:
        aggregate = (
            ExecutionMetricAggregate.objects.filter(
                task_type=task_type_label,
                task_id=task.pk,
                execution_id=execution_id,
            )
            .only("continuity_warnings")
            .first()
        )
        state = (
            ExecutionState.objects.filter(
                task_type=task_type_label,
                task_id=task.pk,
                execution_id=execution_id,
            )
            .only("resume_cursor_timestamp")
            .order_by("-updated_at")
            .first()
        )
        return {
            "resume_cursor_timestamp": (
                state.resume_cursor_timestamp.isoformat()
                if state and state.resume_cursor_timestamp
                else None
            ),
            "consistency_warnings": (
                aggregate.continuity_warnings
                if aggregate and isinstance(aggregate.continuity_warnings, list)
                else []
            ),
        }

    @staticmethod
    def _attach_metadata(envelope: dict, metadata: dict, data_source: str) -> dict:
        envelope["data_source"] = data_source
        envelope.update(metadata)
        return envelope

    @staticmethod
    def _windowed_python(
        *,
        request: Request,
        queryset,
        interval: int,
        page: int,
        page_size: int,
        metric_keys: tuple[str, ...],
    ) -> dict:
        rows = list(queryset.values_list("timestamp", "metrics"))
        bucketed: dict[int, tuple] = {}
        interval_seconds = interval * 60
        for ts, metrics in rows:
            bucket = int(ts.timestamp()) // interval_seconds
            bucketed[bucket] = (ts, metrics)

        aggregated = [bucketed[key] for key in sorted(bucketed)]
        total_count = len(aggregated)
        start = (page - 1) * page_size
        page_rows = aggregated[start : start + page_size]
        data = [
            {
                "t": int(ts.timestamp()),
                "metrics": filter_metrics(ensure_metrics_dict(m), metric_keys),
            }
            for ts, m in page_rows
        ]
        return paginated_envelope(request, data, total_count, page, page_size)

    @staticmethod
    def _windowed_postgres(
        *,
        request: Request,
        task,
        task_type_label: str,
        query: MetricsQueryParams,
        interval: int,
        page: int,
        page_size: int,
    ) -> dict:
        base_where = "task_type = %s AND task_id = %s"
        where_params: list = [task_type_label, str(task.pk)]

        if query.execution.execution_id is None:
            base_where += " AND execution_id IS NULL"
        else:
            base_where += " AND execution_id = %s"
            where_params.append(str(query.execution.execution_id))

        if query.execution.since:
            base_where += " AND timestamp > %s"
            where_params.append(query.execution.since)
        if query.until:
            base_where += " AND timestamp < %s"
            where_params.append(query.until)

        interval_seconds = interval * 60
        offset = (page - 1) * page_size
        count_sql = (
            "SELECT COUNT(*) "  # nosec B608
            "FROM ("
            "  SELECT FLOOR(EXTRACT(EPOCH FROM timestamp) / %s) AS bucket "
            "  FROM metrics "
            f"  WHERE {base_where} "
            "  GROUP BY bucket"
            ") sub"
        )
        sql = (
            "SELECT DISTINCT ON (bucket) "  # nosec B608
            "  timestamp, metrics "
            "FROM ("
            "  SELECT timestamp, metrics, "
            "    FLOOR(EXTRACT(EPOCH FROM timestamp) / %s) AS bucket "
            "  FROM metrics "
            f"  WHERE {base_where}"
            ") sub "
            "ORDER BY bucket, timestamp DESC "
            "LIMIT %s OFFSET %s"
        )

        with connection.cursor() as cursor:
            cursor.execute(count_sql, [interval_seconds, *where_params])
            total_count = int(cursor.fetchone()[0])
            cursor.execute(sql, [interval_seconds, *where_params, page_size, offset])
            rows = cursor.fetchall()

        data = [
            {
                "t": int(ts.timestamp()),
                "metrics": filter_metrics(ensure_metrics_dict(m), query.metric_keys),
            }
            for ts, m in rows
        ]
        return paginated_envelope(request, data, total_count, page, page_size)
