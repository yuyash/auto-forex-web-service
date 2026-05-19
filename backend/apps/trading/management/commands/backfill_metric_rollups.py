"""Backfill metrics_rollups for an existing task execution."""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from apps.trading.services.strategy_data_common import parse_datetime
from apps.trading.services.strategy_metrics import ROLLUP_GRANULARITY_BY_SECONDS


class Command(BaseCommand):
    help = (
        "Backfill pre-aggregated metrics_rollups for one task. "
        "Scope the command to a task/execution before running it on production-sized data."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument("--task-type", required=True, choices=("backtest", "trading"))
        parser.add_argument("--task-id", required=True)
        parser.add_argument("--execution-id")
        parser.add_argument(
            "--granularity",
            action="append",
            choices=tuple(ROLLUP_GRANULARITY_BY_SECONDS.values()),
            help="Rollup granularity to backfill. Repeatable. Defaults to all chart rollups.",
        )
        parser.add_argument("--since", help="Optional lower timestamp bound.")
        parser.add_argument("--until", help="Optional upper timestamp bound.")

    def handle(self, *args: Any, **options: Any) -> None:
        if connection.vendor != "postgresql":
            raise CommandError("backfill_metric_rollups requires PostgreSQL.")

        task_type = options["task_type"]
        task_id = options["task_id"]
        execution_id = options.get("execution_id")
        since = parse_datetime(options.get("since"))
        until = parse_datetime(options.get("until"))
        granularities = options.get("granularity") or list(ROLLUP_GRANULARITY_BY_SECONDS.values())

        seconds_by_granularity = {
            granularity: seconds
            for seconds, granularity in ROLLUP_GRANULARITY_BY_SECONDS.items()
            if granularity in granularities
        }
        total_rows = 0
        for granularity, seconds in seconds_by_granularity.items():
            rows = self._backfill_one(
                task_type=task_type,
                task_id=task_id,
                execution_id=execution_id,
                granularity=granularity,
                seconds=seconds,
                since=since,
                until=until,
            )
            total_rows += rows
            self.stdout.write(f"{granularity}: upserted {rows} rollup rows")

        self.stdout.write(self.style.SUCCESS(f"Backfilled {total_rows} metric rollup rows"))

    def _backfill_one(
        self,
        *,
        task_type: str,
        task_id: str,
        execution_id: str | None,
        granularity: str,
        seconds: int,
        since: Any,
        until: Any,
    ) -> int:
        filters = ["task_type = %s", "task_id = %s"]
        params: list[Any] = [task_type, task_id]
        if execution_id:
            filters.append("execution_id = %s")
            params.append(execution_id)
        else:
            filters.append("execution_id IS NULL")
        if since is not None:
            filters.append("timestamp >= %s")
            params.append(since)
        if until is not None:
            filters.append("timestamp <= %s")
            params.append(until)

        sql = f"""
            WITH source_rows AS (
                SELECT
                    task_type,
                    task_id,
                    execution_id,
                    (FLOOR(EXTRACT(EPOCH FROM timestamp) / %s) * %s)::bigint AS bucket_epoch,
                    MAX(timestamp) AS source_timestamp
                FROM metrics
                WHERE {" AND ".join(filters)}
                GROUP BY task_type, task_id, execution_id, bucket_epoch
            ),
            latest_rows AS (
                SELECT
                    source_rows.task_type,
                    source_rows.task_id,
                    source_rows.execution_id,
                    source_rows.bucket_epoch,
                    source_rows.source_timestamp,
                    metrics.metrics
                FROM source_rows
                JOIN metrics
                  ON metrics.task_type = source_rows.task_type
                 AND metrics.task_id = source_rows.task_id
                 AND (
                      metrics.execution_id = source_rows.execution_id
                      OR (
                          metrics.execution_id IS NULL
                          AND source_rows.execution_id IS NULL
                      )
                 )
                 AND metrics.timestamp = source_rows.source_timestamp
            )
            INSERT INTO metrics_rollups (
                id,
                task_type,
                task_id,
                execution_id,
                granularity,
                bucket,
                source_timestamp,
                metrics,
                created_at,
                updated_at
            )
            SELECT
                gen_random_uuid(),
                task_type,
                task_id,
                execution_id,
                %s,
                to_timestamp(bucket_epoch),
                source_timestamp,
                metrics,
                NOW(),
                NOW()
            FROM latest_rows
            ON CONFLICT (task_type, task_id, execution_id, granularity, bucket)
            DO UPDATE SET
                source_timestamp = EXCLUDED.source_timestamp,
                metrics = EXCLUDED.metrics,
                updated_at = EXCLUDED.updated_at
        """  # nosec B608

        with connection.cursor() as cursor:
            cursor.execute(sql, [seconds, seconds, *params, granularity])
            return cursor.rowcount
