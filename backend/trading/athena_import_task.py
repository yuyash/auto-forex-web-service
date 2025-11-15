"""
Celery task for importing historical tick data from Athena to PostgreSQL.

This module provides:
- Daily scheduled task to fetch data from Athena (runs at 1:00 AM UTC)
- Import data into PostgreSQL tick_data table
- Automatic task registration when OANDA accounts are added
- Backfill support for historical date ranges

Task Flow:
1. When a new OANDA account is created:
   - Signal handler (accounts/signals.py) triggers import_athena_data_daily
   - Imports last 7 days of data for the new account

2. Daily scheduled import (Celery Beat):
   - schedule_daily_athena_import runs at 1:00 AM UTC
   - Imports previous day's data for all active accounts
   - Configured in trading_system/settings.py CELERY_BEAT_SCHEDULE

3. Manual/backfill import:
   - import_historical_range can be called for specific date ranges
   - Useful for backfilling historical data

Configuration:
- Athena database, table, and S3 bucket configured in SystemSettings model
- Instruments to import configured in SystemSettings.athena_instruments
- Default instruments: EUR_USD, GBP_USD, USD_JPY, USD_CHF, AUD_USD, USD_CAD, NZD_USD

Requirements: 12.1
"""

import logging
from datetime import datetime, timedelta

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from celery import Task, shared_task

from accounts.models import OandaAccount
from trading.historical_data_loader import HistoricalDataLoader
from trading.tick_data_models import TickData

logger = logging.getLogger(__name__)

# Cache key for progress tracking
PROGRESS_CACHE_KEY = "athena_import_progress"
PROGRESS_CACHE_TTL = 3600  # 1 hour


def _get_progress_state() -> dict | None:
    """
    Get current progress state from cache.

    Returns:
        Progress state dictionary or None if not found
    """
    try:
        result = cache.get(PROGRESS_CACHE_KEY)
        return dict(result) if result else None
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Failed to get progress state from cache: %s", e)
        return None


def _update_progress_state(updates: dict) -> None:
    """
    Update progress state in cache.

    Args:
        updates: Dictionary with fields to update
    """
    try:
        # Get current state or create new one
        progress = _get_progress_state() or {}

        # Update with new values
        progress.update(updates)

        # Calculate percentage if current_day and total_days are present
        if "current_day" in progress and "total_days" in progress:
            total_days = progress["total_days"]
            current_day = progress["current_day"]
            if total_days > 0:
                progress["percentage"] = (current_day / total_days) * 100
            else:
                progress["percentage"] = 0

        # Save to cache
        cache.set(PROGRESS_CACHE_KEY, progress, PROGRESS_CACHE_TTL)
        logger.debug("Updated progress state: %s", progress)

    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Failed to update progress state in cache: %s", e)


def _increment_progress() -> None:
    """
    Increment the current_day counter in progress state.
    """
    try:
        progress = _get_progress_state()
        if progress:
            current_day = progress.get("current_day", 0)
            total_days = progress.get("total_days", 0)

            # Increment current day
            current_day += 1

            # Update message
            message = f"Importing day {current_day} of {total_days}"

            _update_progress_state(
                {
                    "current_day": current_day,
                    "message": message,
                }
            )
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Failed to increment progress: %s", e)


@shared_task(bind=True, max_retries=3)
def import_athena_data_daily(  # pylint: disable=too-many-locals,too-many-branches,too-many-statements  # noqa: E501
    self: Task,
    account_id: int | None = None,
    days_back: int = 1,
    specific_date: str | None = None,
) -> dict[str, int | str | list[str]]:
    """
    Import historical tick data from Athena to PostgreSQL.

    This task runs daily to fetch the previous day's data from Athena
    and import it into the PostgreSQL tick_data table.

    Args:
        account_id: Optional specific account ID to import for
        days_back: Number of days back to fetch (default: 1 for yesterday)
        specific_date: Optional ISO format date string to import specific date

    Returns:
        Dictionary with import statistics:
            - success: Whether import was successful
            - accounts_processed: Number of accounts processed
            - total_ticks_imported: Total ticks imported
            - instruments: List of instruments imported
            - errors: List of error messages
    """
    logger.info(
        "Starting Athena data import task (days_back=%d, specific_date=%s)",
        days_back,
        specific_date or "None",
    )

    results: dict[str, int | str | list[str]] = {
        "success": True,
        "accounts_processed": 0,
        "total_ticks_imported": 0,
        "instruments": [],
        "errors": [],
    }

    try:
        # Increment progress at the start of each day's import
        _increment_progress()
        # Get accounts to process
        if account_id:
            accounts = OandaAccount.objects.filter(id=account_id, is_active=True)
        else:
            accounts = OandaAccount.objects.filter(is_active=True)

        if not accounts.exists():
            logger.warning("No active OANDA accounts found")
            errors_list = results.get("errors", [])
            if isinstance(errors_list, list):
                errors_list.append("No active OANDA accounts found")
            return results

        # Calculate date range
        if specific_date:
            # Use specific date provided
            start_date = datetime.fromisoformat(specific_date.replace("Z", "+00:00"))
            end_date = start_date + timedelta(days=1)
        else:
            # Default to yesterday
            end_date = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
            start_date = end_date - timedelta(days=days_back)

        logger.info(
            "Importing data from %s to %s for %d accounts",
            start_date,
            end_date,
            accounts.count(),
        )

        # Initialize Athena loader
        loader = HistoricalDataLoader(data_source="athena")

        # Get list of instruments to import
        instruments = _get_instruments_to_import()

        if not instruments:
            logger.warning("No instruments configured for import")
            errors_list = results.get("errors", [])
            if isinstance(errors_list, list):
                errors_list.append("No instruments configured for import")
            return results

        # Process each account
        for account in accounts:
            try:
                account_ticks = _import_account_data(
                    account, loader, instruments, start_date, end_date
                )

                accounts_processed = results.get("accounts_processed", 0)
                if isinstance(accounts_processed, int):
                    results["accounts_processed"] = accounts_processed + 1

                total_ticks = results.get("total_ticks_imported", 0)
                if isinstance(total_ticks, int):
                    results["total_ticks_imported"] = total_ticks + account_ticks

                logger.info("Imported %d ticks for account %s", account_ticks, account.account_id)

            except Exception as e:  # pylint: disable=broad-exception-caught
                error_msg = f"Failed to import data for account {account.account_id}: {str(e)}"
                logger.error(error_msg, exc_info=True)
                errors_list = results.get("errors", [])
                if isinstance(errors_list, list):
                    errors_list.append(error_msg)
                results["success"] = False

        results["instruments"] = instruments

        logger.info(
            "Athena import completed: %d accounts, %d ticks imported",
            results["accounts_processed"],
            results["total_ticks_imported"],
        )

        # Check if this is the last day - mark as completed
        progress = _get_progress_state()
        if progress:
            current_day = progress.get("current_day", 0)
            total_days = progress.get("total_days", 0)

            if current_day >= total_days:
                # All days completed
                _update_progress_state(
                    {
                        "status": "completed",
                        "message": f"Import completed successfully ({total_days} days)",
                        "completed_at": timezone.now().isoformat(),
                    }
                )
                logger.info("All days imported successfully")

        return results

    except Exception as e:  # pylint: disable=broad-exception-caught
        error_msg = f"Athena import task failed: {str(e)}"
        logger.error(error_msg, exc_info=True)
        results["success"] = False
        errors_list = results.get("errors", [])
        if isinstance(errors_list, list):
            errors_list.append(error_msg)

        # Mark progress as failed
        _update_progress_state(
            {
                "status": "failed",
                "message": "Import failed",
                "error": error_msg,
                "completed_at": timezone.now().isoformat(),
            }
        )

        # Retry on failure
        raise self.retry(exc=e, countdown=300) from e  # Retry after 5 minutes


def _get_instruments_to_import() -> list[str]:
    """
    Get list of instruments to import from Athena.

    Returns:
        List of instrument names (e.g., ['EUR_USD', 'GBP_USD'])
    """
    # Get instruments from system settings or use defaults
    try:
        from accounts.models import SystemSettings

        settings = SystemSettings.objects.first()
        if settings and hasattr(settings, "athena_instruments"):
            instruments_str = getattr(settings, "athena_instruments", "")
            if instruments_str:
                return [i.strip() for i in instruments_str.split(",")]
    except Exception:  # nosec B110 pylint: disable=broad-exception-caught
        # Silently fall back to defaults if settings unavailable
        pass

    # Default instruments (major pairs)
    return [
        "EUR_USD",
        "GBP_USD",
        "USD_JPY",
        "USD_CHF",
        "AUD_USD",
        "USD_CAD",
        "NZD_USD",
    ]


def _import_account_data(
    account: OandaAccount,
    loader: HistoricalDataLoader,
    instruments: list[str],
    start_date: datetime,
    end_date: datetime,
) -> int:
    """
    Import data for a specific account.

    Args:
        account: OandaAccount instance
        loader: HistoricalDataLoader instance
        instruments: List of instruments to import
        start_date: Start date for import
        end_date: End date for import

    Returns:
        Number of ticks imported
    """
    total_ticks = 0

    for instrument in instruments:
        try:
            # Load data from Athena
            tick_data_points = loader.load_data(instrument, start_date, end_date)

            if not tick_data_points:
                logger.info("No data found for %s", instrument)
                continue

            # Import to PostgreSQL in batches
            batch_size = 1000
            imported = _import_ticks_batch(account, tick_data_points, batch_size)

            total_ticks += imported
            logger.info("Imported %d ticks for %s", imported, instrument)

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Failed to import %s: %s", instrument, e, exc_info=True)
            continue

    return total_ticks


def _import_ticks_batch(
    account: OandaAccount, tick_data_points: list, batch_size: int = 1000
) -> int:
    """
    Import tick data points to PostgreSQL in batches.

    Args:
        account: OandaAccount instance
        tick_data_points: List of TickDataPoint objects
        batch_size: Number of records per batch

    Returns:
        Number of ticks imported
    """
    total_imported = 0

    # Process in batches
    for i in range(0, len(tick_data_points), batch_size):
        batch = tick_data_points[i : i + batch_size]  # noqa: E203

        try:
            with transaction.atomic():
                tick_objects = []

                for tick_point in batch:
                    # Check if tick already exists (avoid duplicates)
                    exists = TickData.objects.filter(
                        account=account,
                        instrument=tick_point.instrument,
                        timestamp=tick_point.timestamp,
                    ).exists()

                    if not exists:
                        tick_objects.append(
                            TickData(
                                account=account,
                                instrument=tick_point.instrument,
                                timestamp=tick_point.timestamp,
                                bid=tick_point.bid,
                                ask=tick_point.ask,
                                mid=tick_point.mid,
                                spread=tick_point.spread,
                            )
                        )

                # Bulk create for efficiency
                if tick_objects:
                    TickData.objects.bulk_create(tick_objects, ignore_conflicts=True)
                    total_imported += len(tick_objects)

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Failed to import batch: %s", e, exc_info=True)
            continue

    return total_imported


@shared_task(bind=True, max_retries=3)
def schedule_daily_athena_import(self: Task) -> dict[str, str | int]:
    """
    Schedule daily Athena import for all active accounts.

    This task is triggered by Celery Beat scheduler daily.
    It imports the previous day's data from Athena to PostgreSQL.

    Returns:
        Dictionary with task status and statistics
    """
    logger.info("Starting scheduled daily Athena import")

    try:
        # Get all active accounts
        accounts = OandaAccount.objects.filter(is_active=True)

        if not accounts.exists():
            logger.warning("No active OANDA accounts found for daily import")
            return {
                "status": "skipped",
                "message": "No active OANDA accounts found",
                "accounts_processed": 0,
            }

        # Trigger import for all accounts (previous day's data)
        result = import_athena_data_daily.delay(days_back=1)

        logger.info(
            "Daily Athena import scheduled for %d accounts (task: %s)",
            accounts.count(),
            result.id,
        )

        return {
            "status": "scheduled",
            "task_id": result.id,
            "accounts_count": accounts.count(),
            "message": f"Daily Athena import scheduled for {accounts.count()} accounts",
        }

    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Failed to schedule daily import: %s", e, exc_info=True)

        # Retry on failure
        raise self.retry(exc=e, countdown=600)  # Retry after 10 minutes


@shared_task
def import_historical_range(
    account_id: int, instrument: str, start_date_str: str, end_date_str: str
) -> dict[str, int | str]:
    """
    Import historical data for a specific date range.

    Useful for backfilling historical data.

    Args:
        account_id: OANDA account ID
        instrument: Instrument to import (e.g., 'EUR_USD')
        start_date_str: Start date in ISO format (YYYY-MM-DD)
        end_date_str: End date in ISO format (YYYY-MM-DD)

    Returns:
        Dictionary with import statistics
    """
    logger.info(
        "Importing historical range: %s from %s to %s",
        instrument,
        start_date_str,
        end_date_str,
    )

    try:
        # Get account
        account = OandaAccount.objects.get(id=account_id, is_active=True)

        # Parse dates
        start_date = datetime.fromisoformat(start_date_str)
        end_date = datetime.fromisoformat(end_date_str)

        # Initialize loader
        loader = HistoricalDataLoader(data_source="athena")

        # Load data
        tick_data_points = loader.load_data(instrument, start_date, end_date)

        # Import to PostgreSQL
        imported = _import_ticks_batch(account, tick_data_points)

        logger.info("Imported %d ticks for historical range", imported)

        return {
            "success": True,
            "ticks_imported": imported,
            "instrument": instrument,
            "start_date": start_date_str,
            "end_date": end_date_str,
        }

    except OandaAccount.DoesNotExist:
        error_msg = f"Account {account_id} not found"
        logger.error(error_msg)
        return {"success": False, "error": error_msg}

    except Exception as e:  # pylint: disable=broad-exception-caught
        error_msg = f"Historical import failed: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {"success": False, "error": error_msg}
