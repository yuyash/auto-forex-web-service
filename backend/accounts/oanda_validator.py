"""
OANDA API credential validation.

This module provides validation for OANDA API credentials using the v20 library.
It validates credentials against practice or live API endpoints and tests account
access before saving.

Requirements: 4.2, 4.3
"""

from typing import Dict, Optional, Tuple

import v20
from v20.errors import V20ConnectionError, V20Timeout
from v20.response import Response


class OandaAPIValidator:
    """
    Validator for OANDA API credentials.

    This class validates OANDA API credentials by attempting to connect to the
    OANDA API and retrieve account information.

    Requirements: 4.2, 4.3
    """

    # OANDA API endpoints
    PRACTICE_API = "https://api-fxpractice.oanda.com"
    LIVE_API = "https://api-fxtrade.oanda.com"

    def __init__(self, account_id: str, api_token: str, api_type: str = "practice"):
        """
        Initialize the OANDA API validator.

        Args:
            account_id: OANDA account ID
            api_token: OANDA API token
            api_type: API endpoint type ('practice' or 'live')

        Raises:
            ValueError: If api_type is not 'practice' or 'live'
        """
        if api_type not in ["practice", "live"]:
            raise ValueError("api_type must be 'practice' or 'live'")

        self.account_id = account_id
        self.api_token = api_token
        self.api_type = api_type
        self.hostname = self.LIVE_API if api_type == "live" else self.PRACTICE_API

    def validate(self) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """
        Validate OANDA API credentials.

        Attempts to connect to the OANDA API and retrieve account information
        to verify that the credentials are valid and the account is accessible.

        Returns:
            Tuple containing:
                - bool: True if validation successful, False otherwise
                - Optional[str]: Error message if validation failed, None otherwise
                - Optional[Dict]: Account details if validation successful, None otherwise

        Examples:
            >>> validator = OandaAPIValidator("001-001-1234567-001", "token", "practice")
            >>> is_valid, error, details = validator.validate()
            >>> if is_valid:
            ...     print(f"Account balance: {details['balance']}")
            ... else:
            ...     print(f"Validation failed: {error}")
        """
        try:
            # Create v20 API context
            api = v20.Context(
                hostname=self.hostname,
                token=self.api_token,
                datetime_format="RFC3339",
            )

            # Attempt to retrieve account information
            response = api.account.get(self.account_id)

            # Check if request was successful
            if response.status != 200:
                error_msg = self._extract_error_message(response)
                return False, error_msg, None

            # Extract account details
            account = response.body.get("account")
            if not account:
                return False, "No account data returned from API", None

            # Build account details dictionary
            account_details = {
                "account_id": account.id,
                "currency": account.currency,
                "balance": float(account.balance),
                "margin_used": float(account.marginUsed) if account.marginUsed else 0.0,
                "margin_available": (
                    float(account.marginAvailable) if account.marginAvailable else 0.0
                ),
                "unrealized_pnl": float(account.unrealizedPL) if account.unrealizedPL else 0.0,
                "open_trade_count": account.openTradeCount,
                "open_position_count": account.openPositionCount,
            }

            return True, None, account_details

        except (V20ConnectionError, V20Timeout) as e:
            # Handle v20-specific errors
            error_msg = f"OANDA API error: {str(e)}"
            return False, error_msg, None

        except Exception as e:  # pylint: disable=broad-exception-caught
            # Handle unexpected errors - broad catch is intentional for robustness
            error_msg = f"Unexpected error during validation: {str(e)}"
            return False, error_msg, None

    def _extract_error_message(self, response: Response) -> str:
        """
        Extract error message from OANDA API response.

        Args:
            response: v20 API response object

        Returns:
            Error message string
        """
        try:
            # Try to extract error message from response body
            if hasattr(response, "body") and response.body and isinstance(response.body, dict):
                error_message = response.body.get("errorMessage", "")
                if error_message:
                    return f"API error: {error_message}"

            # Fallback to status code
            return f"API request failed with status code {response.status}"

        except Exception:  # pylint: disable=broad-exception-caught
            # Broad catch is intentional - fallback to status code on any error
            return f"API request failed with status code {response.status}"

    @classmethod
    def validate_credentials(
        cls, account_id: str, api_token: str, api_type: str = "practice"
    ) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """
        Class method to validate OANDA API credentials.

        This is a convenience method that creates a validator instance and
        performs validation in one step.

        Args:
            account_id: OANDA account ID
            api_token: OANDA API token
            api_type: API endpoint type ('practice' or 'live')

        Returns:
            Tuple containing:
                - bool: True if validation successful, False otherwise
                - Optional[str]: Error message if validation failed, None otherwise
                - Optional[Dict]: Account details if validation successful, None otherwise

        Examples:
            >>> is_valid, error, details = OandaAPIValidator.validate_credentials(
            ...     "001-001-1234567-001", "token", "practice"
            ... )
        """
        validator = cls(account_id, api_token, api_type)
        return validator.validate()
