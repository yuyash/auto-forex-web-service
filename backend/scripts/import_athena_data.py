#!/usr/bin/env python
"""
Standalone script to import historical tick data from Athena to PostgreSQL.

Usage:
    python scripts/import_athena_data.py --account-id 1 --days-back 7
    python scripts/import_athena_data.py --account-id 1 \\
        --start-date 2024-01-01 --end-date 2024-01-31
    python scripts/import_athena_data.py --all-accounts --days-back 1

Requirements:
    - Django environment must be configured
    - AWS credentials must be available
    - Athena database and table must be configured in SystemSettings
"""

import argparse
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path for Django imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "trading_system.settings")

import django  # noqa: E402 pylint: disable=wrong-import-position

django.setup()

from accounts.models import OandaAccount  # noqa: E402 pylint: disable=wrong-import-position
from trading.athena_import_task import (  # noqa: E402 pylint: disable=wrong-import-position
    _get_instruments_to_import,
    _import_account_data,
)
from trading.historical_data_loader import (  # noqa: E402 pylint: disable=wrong-import-position
    HistoricalDataLoader,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Import historical tick data from Athena to PostgreSQL"
    )

    # Account selection
    account_group = parser.add_mutually_exclusive_group(required=True)
    account_group.add_argument(
        "--account-id",
        type=int,
        help="Specific OANDA account ID to import for",
    )
    account_group.add_argument(
        "--all-accounts",
        action="store_true",
        help="Import for all active accounts",
    )

    # Date range selection
    date_group = parser.add_mutually_exclusive_group(required=True)
    date_group.add_argument(
        "--days-back",
        type=int,
        help="Number of days back to import (e.g., 7 for last week)",
    )
    date_group.add_argument(
        "--date-range",
        nargs=2,
        metavar=("START_DATE", "END_DATE"),
        help="Specific date range (format: YYYY-MM-DD YYYY-MM-DD)",
    )

    # Optional parameters
    parser.add_argument(
        "--instruments",
        nargs="+",
        help="Specific instruments to import (e.g., EUR_USD GBP_USD)",
    )

    return parser.parse_args()


def get_accounts(account_id: int | None, all_accounts: bool) -> list:
    """Get accounts to process."""
    if account_id:
        accounts = OandaAccount.objects.filter(id=account_id, is_active=True)
        if not accounts.exists():
            logger.error("Account %d not found or not active", account_id)
            sys.exit(1)
    elif all_accounts:
        accounts = OandaAccount.objects.filter(is_active=True)
        if not accounts.exists():
            logger.error("No active OANDA accounts found")
            sys.exit(1)
    else:
        logger.error("Must specify --account-id or --all-accounts")
        sys.exit(1)

    return list(accounts)


def get_date_range(args: argparse.Namespace) -> tuple[datetime, datetime]:
    """Get date range from arguments."""
    if args.days_back:
        end_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        start_date = end_date - timedelta(days=args.days_back)
    elif args.date_range:
        start_date = datetime.fromisoformat(args.date_range[0])
        end_date = datetime.fromisoformat(args.date_range[1])
    else:
        logger.error("Must specify --days-back or --date-range")
        sys.exit(1)

    return start_date, end_date


def main() -> None:
    """Main entry point."""
    args = parse_args()

    # Get accounts
    accounts = get_accounts(args.account_id, args.all_accounts)
    logger.info("Processing %d account(s)", len(accounts))

    # Get date range
    start_date, end_date = get_date_range(args)
    logger.info("Date range: %s to %s", start_date, end_date)

    # Get instruments
    if args.instruments:
        instruments = args.instruments
    else:
        instruments = _get_instruments_to_import()

    logger.info("Instruments: %s", ", ".join(instruments))

    # Initialize loader
    try:
        loader = HistoricalDataLoader(data_source="athena")
    except Exception as e:
        logger.error("Failed to initialize Athena loader: %s", e)
        sys.exit(1)

    # Process each account
    total_ticks = 0
    for account in accounts:
        logger.info("Processing account: %s", account.account_id)

        try:
            ticks_imported = _import_account_data(
                account, loader, instruments, start_date, end_date
            )

            total_ticks += ticks_imported
            logger.info("Account %s: imported %d ticks", account.account_id, ticks_imported)

        except Exception as e:
            logger.error("Failed to import data for account %s: %s", account.account_id, e)
            continue

    # Summary
    logger.info("=" * 60)
    logger.info("Import completed successfully")
    logger.info("Accounts processed: %d", len(accounts))
    logger.info("Total ticks imported: %d", total_ticks)
    logger.info("Instruments: %s", ", ".join(instruments))
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
