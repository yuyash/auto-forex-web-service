"""
OANDA API Health Check

This module provides health check functionality for OANDA API connectivity.
"""

import logging
from typing import Any, Dict

import v20

from accounts.models import OandaAccount

logger = logging.getLogger(__name__)


def check_oanda_health(account: OandaAccount) -> Dict[str, Any]:
    """
    Check the health of OANDA API connection for a given account.

    Args:
        account: OandaAccount instance to check

    Returns:
        Dictionary with health status:
        {
            "healthy": bool,
            "account_id": str,
            "message": str,
            "details": dict (optional)
        }
    """
    try:
        # Create API context
        api = v20.Context(
            hostname=account.api_hostname,
            token=account.get_api_token(),
            poll_timeout=5,  # 5 second timeout for health check
        )

        # Try to fetch account details - lightweight operation
        response = api.account.get(account.account_id)

        if response.status == 200:
            return {
                "healthy": True,
                "account_id": account.account_id,
                "message": "OANDA API connection is healthy",
                "details": {
                    "api_type": account.api_type,
                    "currency": account.currency,
                    "balance": str(account.balance),
                },
            }

        logger.warning(
            "OANDA health check failed for account %s: status %d",
            account.account_id,
            response.status,
        )
        return {
            "healthy": False,
            "account_id": account.account_id,
            "message": f"OANDA API returned status {response.status}",
        }

    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error(
            "OANDA health check error for account %s: %s",
            account.account_id,
            str(e),
            exc_info=True,
        )
        return {
            "healthy": False,
            "account_id": account.account_id,
            "message": f"OANDA API connection failed: {str(e)}",
        }


def check_all_accounts_health(user_id: int) -> Dict[str, Any]:
    """
    Check health of all OANDA accounts for a user.

    Args:
        user_id: User ID to check accounts for

    Returns:
        Dictionary with overall health status and individual account statuses
    """
    accounts = OandaAccount.objects.filter(user_id=user_id, is_active=True)

    if not accounts.exists():
        return {
            "healthy": False,
            "message": "No active OANDA accounts found",
            "accounts": [],
        }

    account_statuses = []
    all_healthy = True

    for account in accounts:
        status = check_oanda_health(account)
        account_statuses.append(status)
        if not status["healthy"]:
            all_healthy = False

    return {
        "healthy": all_healthy,
        "message": (
            "All OANDA accounts are healthy" if all_healthy else "Some OANDA accounts have issues"
        ),
        "accounts": account_statuses,
    }
