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
from datetime import UTC, datetime, timedelta

from celery import shared_task

logger = logging.getLogger(__name__)


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

    if not database or not table:
        logger.info("load_daily_tick_data skipped: LOAD_DATA_DATABASE or LOAD_DATA_TABLE not set")
        return {"status": "skipped", "reason": "not configured"}

    instrument = os.getenv("LOAD_DATA_INSTRUMENT", "C:USD-JPY").strip()
    profile = os.getenv("LOAD_DATA_AWS_PROFILE", "").strip() or None
    role_arn = os.getenv("LOAD_DATA_ROLE_ARN", "").strip() or None
    output_bucket = os.getenv("LOAD_DATA_OUTPUT_BUCKET", "").strip() or None

    yesterday = datetime.now(UTC).date() - timedelta(days=1)
    today = datetime.now(UTC).date()
    start_str = yesterday.isoformat()
    end_str = today.isoformat()

    logger.info(
        "load_daily_tick_data: loading %s data for %s from %s.%s",
        instrument,
        start_str,
        database,
        table,
    )

    try:
        from django.core.management import call_command

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
        )
    except Exception as exc:
        logger.exception("load_daily_tick_data failed: %s", exc)
        raise self.retry(exc=exc) from exc

    logger.info("load_daily_tick_data: completed for %s", start_str)
    return {"status": "completed", "date": start_str, "instrument": instrument}
