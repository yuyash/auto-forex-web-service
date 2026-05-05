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

from celery import shared_task

logger = logging.getLogger(__name__)

_TOTAL_INSERTED_RE = re.compile(r"Inserted\s+(\d+)\s+tick rows")


class _CommandLogStream:
    """Mirror management command output into the task logger while retaining it."""

    def __init__(self) -> None:
        self._buffer = StringIO()
        self._pending_line = ""

    def write(self, value: str) -> int:
        written = self._buffer.write(value)
        self._write_to_log(value)
        return written

    def flush(self) -> None:
        if self._pending_line:
            logger.info("load_data: %s", self._pending_line)
            self._pending_line = ""
        self._buffer.flush()

    def getvalue(self) -> str:
        return self._buffer.getvalue()

    def _write_to_log(self, value: str) -> None:
        if not value:
            return

        text = self._pending_line + value
        lines = text.splitlines(keepends=True)
        self._pending_line = ""

        for line in lines:
            if line.endswith(("\n", "\r")):
                logger.info("load_data: %s", line.rstrip("\r\n"))
            else:
                self._pending_line = line


def _parse_inserted_count(output: str) -> int | None:
    matches = _TOTAL_INSERTED_RE.findall(output)
    if not matches:
        return None
    return int(matches[-1])


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
        missing_fields = [
            key
            for key, value in {
                "LOAD_DATA_DATABASE": database,
                "LOAD_DATA_TABLE": table,
            }.items()
            if not value
        ]
        logger.warning(
            "load_daily_tick_data skipped: missing Athena configuration fields=%s",
            ",".join(missing_fields),
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
    logger.info(
        "load_daily_tick_data: config output_bucket=%s role_arn=%s profile=%s",
        output_bucket is not None,
        role_arn is not None,
        profile is not None,
    )

    stdout = _CommandLogStream()

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
            stdout=stdout,
            stderr=stdout,
        )
        stdout.flush()
        command_output = stdout.getvalue().strip()
    except Exception as exc:
        stdout.flush()
        logger.exception("load_daily_tick_data failed: %s", exc)
        raise self.retry(exc=exc) from exc

    inserted_count = _parse_inserted_count(command_output)
    if inserted_count == 0:
        logger.warning("load_daily_tick_data: completed for %s with 0 inserted rows", start_str)
    else:
        logger.info(
            "load_daily_tick_data: completed for %s rows_inserted=%s",
            start_str,
            inserted_count,
        )
    result: dict[str, str | int] = {
        "status": "completed",
        "date": start_str,
        "instrument": instrument,
    }
    if inserted_count is not None:
        result["rows_inserted"] = inserted_count
    return result
