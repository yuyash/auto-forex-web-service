"""Periodic tick data ingestion from AWS Athena.

Wraps the ``load_data`` management command as a Celery task so it can be
scheduled via Celery Beat to run daily.  The task fetches the previous day's
tick data and upserts it into the ``TickData`` table.

Configuration is via environment variables:

    LOAD_DATA_DATABASE      Athena database name (required)
    LOAD_DATA_TABLE         Athena table name (required)
    LOAD_DATA_INSTRUMENT    Instrument/ticker (default: C:USD-JPY)
    LOAD_DATA_AWS_PROFILE   AWS profile name (optional)
    LOAD_DATA_ROLE_ARN      IAM role ARN to assume (optional)
    LOAD_DATA_OUTPUT_BUCKET S3 bucket for Athena results (optional)

If ``LOAD_DATA_DATABASE`` is not set the task exits silently, allowing
environments without Athena access to skip data loading.
"""

from __future__ import annotations

import logging
import os
import re
from datetime import UTC, datetime, timedelta
from io import StringIO
from typing import Any

from celery import shared_task

logger = logging.getLogger(__name__)

_TOTAL_INSERTED_RE = re.compile(r"Inserted\s+(\d+)\s+tick rows")


def _task_request_details(task: Any) -> dict[str, Any]:
    request = getattr(task, "request", None)
    return {
        "celery_task_id": getattr(request, "id", None),
        "retries": getattr(request, "retries", None),
        "max_retries": getattr(task, "max_retries", None),
    }


def _parse_inserted_count(output: str) -> int | None:
    matches = _TOTAL_INSERTED_RE.findall(output)
    if not matches:
        return None
    return int(matches[-1])


def _persist_load_event(
    *,
    event_type: str,
    severity: str,
    description: str,
    instrument: str = "",
    details: dict[str, Any] | None = None,
) -> None:
    """Persist tick data load task activity without making logging a hard dependency."""
    try:
        from apps.market.models import MarketEvent

        MarketEvent.objects.create(
            event_type=event_type,
            category="tick_data_load",
            severity=severity,
            description=description,
            instrument=instrument,
            details=details or {},
        )
    except Exception:
        logger.warning("Failed to persist tick data load event", exc_info=True)


@shared_task(
    name="market.tasks.load_daily_tick_data",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
    acks_late=True,
)
def load_daily_tick_data(self) -> dict[str, str | int]:
    """Fetch yesterday's tick data from Athena and load into TickData.

    Designed to be called once per day by Celery Beat.  On failure the task
    retries up to 2 times with a 5-minute delay.
    """
    database = os.getenv("LOAD_DATA_DATABASE", "").strip()
    table = os.getenv("LOAD_DATA_TABLE", "").strip()
    task_details = _task_request_details(self)

    if not database or not table:
        logger.info("load_daily_tick_data skipped: LOAD_DATA_DATABASE or LOAD_DATA_TABLE not set")
        _persist_load_event(
            event_type="tick_data_load_skipped",
            severity="warning",
            description="Daily tick data load skipped because Athena is not configured.",
            details={
                **task_details,
                "missing_fields": [
                    key
                    for key, value in {
                        "LOAD_DATA_DATABASE": database,
                        "LOAD_DATA_TABLE": table,
                    }.items()
                    if not value
                ],
            },
        )
        return {"status": "skipped", "reason": "not configured"}

    instrument = os.getenv("LOAD_DATA_INSTRUMENT", "C:USD-JPY").strip()
    profile = os.getenv("LOAD_DATA_AWS_PROFILE", "").strip() or None
    role_arn = os.getenv("LOAD_DATA_ROLE_ARN", "").strip() or None
    output_bucket = os.getenv("LOAD_DATA_OUTPUT_BUCKET", "").strip() or None

    yesterday = datetime.now(UTC).date() - timedelta(days=1)
    start_str = yesterday.isoformat()
    end_str = yesterday.isoformat()

    logger.info(
        "load_daily_tick_data: loading %s data for %s from %s.%s",
        instrument,
        start_str,
        database,
        table,
    )
    base_details = {
        **task_details,
        "date": start_str,
        "start": start_str,
        "end": end_str,
        "database": database,
        "table": table,
        "instrument": instrument,
        "output_bucket_configured": output_bucket is not None,
        "role_arn_configured": role_arn is not None,
        "profile_configured": profile is not None,
    }
    _persist_load_event(
        event_type="tick_data_load_started",
        severity="info",
        description=f"Daily tick data load started for {instrument} on {start_str}.",
        instrument=instrument,
        details=base_details,
    )

    try:
        from django.core.management import call_command

        stdout = StringIO()
        call_command(
            "load_data",
            start=start_str,
            end=end_str,
            database=database,
            table=table,
            instrument=instrument,
            profile=profile,
            role_arn=role_arn,
            output_bucket=output_bucket,
            verbosity=1,
            stdout=stdout,
            stderr=stdout,
        )
        command_output = stdout.getvalue().strip()
    except Exception as exc:
        logger.exception("load_daily_tick_data failed: %s", exc)
        _persist_load_event(
            event_type="tick_data_load_failed",
            severity="error",
            description=f"Daily tick data load failed for {instrument} on {start_str}.",
            instrument=instrument,
            details={
                **base_details,
                "error_type": type(exc).__name__,
                "error": str(exc),
            },
        )
        raise self.retry(exc=exc) from exc

    inserted_count = _parse_inserted_count(command_output)
    logger.info("load_daily_tick_data: completed for %s", start_str)
    _persist_load_event(
        event_type="tick_data_load_completed",
        severity="info",
        description=f"Daily tick data load completed for {instrument} on {start_str}.",
        instrument=instrument,
        details={
            **base_details,
            "rows_inserted": inserted_count,
            "command_output": command_output,
        },
    )
    result: dict[str, str | int] = {
        "status": "completed",
        "date": start_str,
        "instrument": instrument,
    }
    if inserted_count is not None:
        result["rows_inserted"] = inserted_count
    return result
