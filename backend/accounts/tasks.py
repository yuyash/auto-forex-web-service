"""
Celery tasks for account management.

This module contains Celery tasks for:
- Fetching account balance and margin from OANDA API
- Periodic updates of account information

Requirements: 4.1, 4.5
"""

import logging
from typing import Dict, Optional

from django.db import transaction

import v20
from celery import shared_task
from v20.errors import V20ConnectionError, V20Timeout

from accounts.models import OandaAccount

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(V20ConnectionError, V20Timeout),
)
def fetch_account_balance(  # type: ignore[no-untyped-def]
    self, account_id: int
) -> Dict[str, Optional[float] | bool | str]:
    """
    Fetch account balance and margin information from OANDA API.

    This task retrieves the current account balance, margin used, margin available,
    and unrealized P&L from the OANDA API and updates the OandaAccount model.

    Args:
        account_id: Primary key of the OandaAccount to update

    Returns:
        Dictionary containing updated account information:
            - balance: Current account balance
            - margin_used: Margin used by open positions
            - margin_available: Margin available for new positions
            - unrealized_pnl: Unrealized profit/loss
            - success: Whether the update was successful
            - error: Error message if update failed

    Requirements: 4.1, 4.5
    """
    try:
        # Fetch the OandaAccount from database
        try:
            oanda_account = OandaAccount.objects.get(id=account_id)
        except OandaAccount.DoesNotExist:
            error_msg = f"OandaAccount with id {account_id} does not exist"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "balance": None,
                "margin_used": None,
                "margin_available": None,
                "unrealized_pnl": None,
            }

        # Skip if account is not active
        if not oanda_account.is_active:
            logger.info(
                "Skipping balance fetch for inactive account %s",
                oanda_account.account_id,
            )
            return {
                "success": False,
                "error": "Account is not active",
                "balance": None,
                "margin_used": None,
                "margin_available": None,
                "unrealized_pnl": None,
            }

        # Get decrypted API token
        api_token = oanda_account.get_api_token()

        # Create v20 API context
        api = v20.Context(
            hostname=oanda_account.api_hostname,
            token=api_token,
            datetime_format="RFC3339",
        )

        # Fetch account details from OANDA API
        response = api.account.get(oanda_account.account_id)

        # Check if request was successful
        if response.status != 200:
            error_msg = f"OANDA API request failed with status {response.status}"
            logger.error(
                "Failed to fetch balance for account %s: %s",
                oanda_account.account_id,
                error_msg,
            )
            return {
                "success": False,
                "error": error_msg,
                "balance": None,
                "margin_used": None,
                "margin_available": None,
                "unrealized_pnl": None,
            }

        # Extract account details
        account = response.body.get("account")
        if not account:
            error_msg = "No account data returned from API"
            logger.error(
                "Failed to fetch balance for account %s: %s",
                oanda_account.account_id,
                error_msg,
            )
            return {
                "success": False,
                "error": error_msg,
                "balance": None,
                "margin_used": None,
                "margin_available": None,
                "unrealized_pnl": None,
            }

        # Extract balance and margin information
        balance = float(account.balance)
        margin_used = float(account.marginUsed) if account.marginUsed else 0.0
        margin_available = float(account.marginAvailable) if account.marginAvailable else 0.0
        unrealized_pnl = float(account.unrealizedPL) if account.unrealizedPL else 0.0

        # Update the OandaAccount model
        with transaction.atomic():
            oanda_account.update_balance(
                balance=balance,
                margin_used=margin_used,
                margin_available=margin_available,
                unrealized_pnl=unrealized_pnl,
            )

        logger.info(
            (
                "Successfully updated balance for account %s: "
                "balance=%s, margin_used=%s, margin_available=%s, "
                "unrealized_pnl=%s"
            ),
            oanda_account.account_id,
            balance,
            margin_used,
            margin_available,
            unrealized_pnl,
        )

        return {
            "success": True,
            "error": None,
            "balance": balance,
            "margin_used": margin_used,
            "margin_available": margin_available,
            "unrealized_pnl": unrealized_pnl,
        }

    except (V20ConnectionError, V20Timeout) as e:
        # Log and retry on connection errors
        error_msg = f"OANDA API connection error: {str(e)}"
        logger.warning(
            (
                "Connection error fetching balance for account %s: %s. "
                "Retrying... (attempt %s/%s)"
            ),
            account_id,
            error_msg,
            self.request.retries + 1,
            self.max_retries,
        )
        # Raise to trigger Celery retry
        raise

    except Exception as e:  # pylint: disable=broad-exception-caught
        # Log unexpected errors - broad catch is intentional for robustness
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(
            "Unexpected error fetching balance for account %s: %s",
            account_id,
            error_msg,
            exc_info=True,
        )
        return {
            "success": False,
            "error": error_msg,
            "balance": None,
            "margin_used": None,
            "margin_available": None,
            "unrealized_pnl": None,
        }


@shared_task
def fetch_all_active_account_balances() -> Dict[str, int]:
    """
    Fetch balance and margin for all active OANDA accounts.

    This task iterates through all active OandaAccount records and triggers
    the fetch_account_balance task for each one.

    Returns:
        Dictionary containing:
            - total_accounts: Total number of active accounts
            - tasks_scheduled: Number of tasks scheduled

    Requirements: 4.1, 4.5
    """
    # Get all active OANDA accounts
    active_accounts = OandaAccount.objects.filter(is_active=True)
    total_accounts = active_accounts.count()

    logger.info("Scheduling balance fetch for %s active accounts", total_accounts)

    # Schedule fetch_account_balance task for each account
    for account in active_accounts:
        fetch_account_balance.delay(account.id)

    logger.info("Scheduled %s balance fetch tasks", total_accounts)

    return {
        "total_accounts": total_accounts,
        "tasks_scheduled": total_accounts,
    }
