"""
Unit tests for OANDA API credential validation.

Tests cover:
- Validation with valid credentials (mocked)
- Validation with invalid credentials
- Practice API endpoint validation
- Live API endpoint validation

Requirements: 4.2, 4.3
"""

from typing import Any, Dict
from unittest.mock import Mock, patch

import pytest
from v20.errors import V20ConnectionError

from accounts.oanda_validator import OandaAPIValidator


@pytest.fixture
def mock_account_response() -> Dict[str, Any]:
    """Create a mock OANDA account response."""
    return {
        "account": {
            "id": "001-001-1234567-001",
            "currency": "USD",
            "balance": "10000.00",
            "marginUsed": "500.00",
            "marginAvailable": "9500.00",
            "unrealizedPL": "50.00",
            "openTradeCount": 2,
            "openPositionCount": 1,
        }
    }


@pytest.fixture
def mock_v20_context() -> Mock:
    """Create a mock v20 Context."""
    return Mock()


class TestOandaAPIValidatorInit:
    """Test cases for OandaAPIValidator initialization."""

    def test_init_practice_api(self) -> None:
        """Test initialization with practice API type."""
        validator = OandaAPIValidator(
            account_id="001-001-1234567-001",
            api_token="test_token",
            api_type="practice",
        )

        assert validator.account_id == "001-001-1234567-001"
        assert validator.api_token == "test_token"
        assert validator.api_type == "practice"
        assert validator.hostname == OandaAPIValidator.PRACTICE_API

    def test_init_live_api(self) -> None:
        """Test initialization with live API type."""
        validator = OandaAPIValidator(
            account_id="001-001-1234567-001",
            api_token="test_token",
            api_type="live",
        )

        assert validator.account_id == "001-001-1234567-001"
        assert validator.api_token == "test_token"
        assert validator.api_type == "live"
        assert validator.hostname == OandaAPIValidator.LIVE_API

    def test_init_invalid_api_type(self) -> None:
        """Test initialization with invalid API type."""
        with pytest.raises(ValueError, match="api_type must be 'practice' or 'live'"):
            OandaAPIValidator(
                account_id="001-001-1234567-001",
                api_token="test_token",
                api_type="invalid",
            )


class TestOandaAPIValidatorValidation:
    """Test cases for OANDA API credential validation."""

    @patch("accounts.oanda_validator.v20.Context")
    def test_validate_with_valid_credentials_practice(
        self, mock_context_class: Mock, mock_account_response: Dict[str, Any]
    ) -> None:
        """Test validation with valid credentials on practice API."""
        # Setup mock response
        mock_response = Mock()
        mock_response.status = 200
        mock_response.body = mock_account_response

        # Setup mock account object
        mock_account = Mock()
        mock_account.id = "001-001-1234567-001"
        mock_account.currency = "USD"
        mock_account.balance = "10000.00"
        mock_account.marginUsed = "500.00"
        mock_account.marginAvailable = "9500.00"
        mock_account.unrealizedPL = "50.00"
        mock_account.openTradeCount = 2
        mock_account.openPositionCount = 1

        mock_response.body = {"account": mock_account}

        # Setup mock context
        mock_context = Mock()
        mock_context.account.get.return_value = mock_response
        mock_context_class.return_value = mock_context

        # Create validator and validate
        validator = OandaAPIValidator(
            account_id="001-001-1234567-001",
            api_token="test_token",
            api_type="practice",
        )

        is_valid, error, details = validator.validate()

        # Assertions
        assert is_valid is True
        assert error is None
        assert details is not None
        assert details["account_id"] == "001-001-1234567-001"
        assert details["currency"] == "USD"
        assert details["balance"] == 10000.00
        assert details["margin_used"] == 500.00
        assert details["margin_available"] == 9500.00
        assert details["unrealized_pnl"] == 50.00
        assert details["open_trade_count"] == 2
        assert details["open_position_count"] == 1

        # Verify API was called with correct parameters
        mock_context_class.assert_called_once_with(
            hostname=OandaAPIValidator.PRACTICE_API,
            token="test_token",
            datetime_format="RFC3339",
        )
        mock_context.account.get.assert_called_once_with("001-001-1234567-001")

    @patch("accounts.oanda_validator.v20.Context")
    def test_validate_with_valid_credentials_live(
        self, mock_context_class: Mock, mock_account_response: Dict[str, Any]
    ) -> None:
        """Test validation with valid credentials on live API."""
        # Setup mock response
        mock_response = Mock()
        mock_response.status = 200

        # Setup mock account object
        mock_account = Mock()
        mock_account.id = "001-001-1234567-001"
        mock_account.currency = "USD"
        mock_account.balance = "50000.00"
        mock_account.marginUsed = "2000.00"
        mock_account.marginAvailable = "48000.00"
        mock_account.unrealizedPL = "100.00"
        mock_account.openTradeCount = 5
        mock_account.openPositionCount = 3

        mock_response.body = {"account": mock_account}

        # Setup mock context
        mock_context = Mock()
        mock_context.account.get.return_value = mock_response
        mock_context_class.return_value = mock_context

        # Create validator and validate
        validator = OandaAPIValidator(
            account_id="001-001-1234567-001",
            api_token="live_token",
            api_type="live",
        )

        is_valid, error, details = validator.validate()

        # Assertions
        assert is_valid is True
        assert error is None
        assert details is not None
        assert details["account_id"] == "001-001-1234567-001"
        assert details["balance"] == 50000.00

        # Verify API was called with live endpoint
        mock_context_class.assert_called_once_with(
            hostname=OandaAPIValidator.LIVE_API,
            token="live_token",
            datetime_format="RFC3339",
        )

    @patch("accounts.oanda_validator.v20.Context")
    def test_validate_with_invalid_credentials(self, mock_context_class: Mock) -> None:
        """Test validation with invalid credentials."""
        # Setup mock response with error
        mock_response = Mock()
        mock_response.status = 401
        mock_response.body = {"errorMessage": "Invalid authentication credentials"}

        # Setup mock context
        mock_context = Mock()
        mock_context.account.get.return_value = mock_response
        mock_context_class.return_value = mock_context

        # Create validator and validate
        validator = OandaAPIValidator(
            account_id="001-001-1234567-001",
            api_token="invalid_token",
            api_type="practice",
        )

        is_valid, error, details = validator.validate()

        # Assertions
        assert is_valid is False
        assert error is not None
        assert "Invalid authentication credentials" in error
        assert details is None

    @patch("accounts.oanda_validator.v20.Context")
    def test_validate_with_invalid_account_id(self, mock_context_class: Mock) -> None:
        """Test validation with invalid account ID."""
        # Setup mock response with error
        mock_response = Mock()
        mock_response.status = 404
        mock_response.body = {"errorMessage": "Account not found"}

        # Setup mock context
        mock_context = Mock()
        mock_context.account.get.return_value = mock_response
        mock_context_class.return_value = mock_context

        # Create validator and validate
        validator = OandaAPIValidator(
            account_id="invalid-account-id",
            api_token="test_token",
            api_type="practice",
        )

        is_valid, error, details = validator.validate()

        # Assertions
        assert is_valid is False
        assert error is not None
        assert "Account not found" in error
        assert details is None

    @patch("accounts.oanda_validator.v20.Context")
    def test_validate_with_v20_error(self, mock_context_class: Mock) -> None:
        """Test validation when v20 library raises an error."""
        # Setup mock context to raise V20ConnectionError
        mock_context = Mock()
        mock_context.account.get.side_effect = V20ConnectionError("Connection timeout")
        mock_context_class.return_value = mock_context

        # Create validator and validate
        validator = OandaAPIValidator(
            account_id="001-001-1234567-001",
            api_token="test_token",
            api_type="practice",
        )

        is_valid, error, details = validator.validate()

        # Assertions
        assert is_valid is False
        assert error is not None
        assert "OANDA API error" in error
        assert "Connection timeout" in error
        assert details is None

    @patch("accounts.oanda_validator.v20.Context")
    def test_validate_with_unexpected_error(self, mock_context_class: Mock) -> None:
        """Test validation when an unexpected error occurs."""
        # Setup mock context to raise unexpected exception
        mock_context = Mock()
        mock_context.account.get.side_effect = Exception("Unexpected error")
        mock_context_class.return_value = mock_context

        # Create validator and validate
        validator = OandaAPIValidator(
            account_id="001-001-1234567-001",
            api_token="test_token",
            api_type="practice",
        )

        is_valid, error, details = validator.validate()

        # Assertions
        assert is_valid is False
        assert error is not None
        assert "Unexpected error during validation" in error
        assert details is None

    @patch("accounts.oanda_validator.v20.Context")
    def test_validate_with_no_account_data(self, mock_context_class: Mock) -> None:
        """Test validation when API returns no account data."""
        # Setup mock response with no account data
        mock_response = Mock()
        mock_response.status = 200
        mock_response.body = {}

        # Setup mock context
        mock_context = Mock()
        mock_context.account.get.return_value = mock_response
        mock_context_class.return_value = mock_context

        # Create validator and validate
        validator = OandaAPIValidator(
            account_id="001-001-1234567-001",
            api_token="test_token",
            api_type="practice",
        )

        is_valid, error, details = validator.validate()

        # Assertions
        assert is_valid is False
        assert error == "No account data returned from API"
        assert details is None

    @patch("accounts.oanda_validator.v20.Context")
    def test_validate_with_missing_optional_fields(self, mock_context_class: Mock) -> None:
        """Test validation when optional fields are missing from response."""
        # Setup mock response with minimal data
        mock_response = Mock()
        mock_response.status = 200

        # Setup mock account object with minimal fields
        mock_account = Mock()
        mock_account.id = "001-001-1234567-001"
        mock_account.currency = "USD"
        mock_account.balance = "10000.00"
        mock_account.marginUsed = None
        mock_account.marginAvailable = None
        mock_account.unrealizedPL = None
        mock_account.openTradeCount = 0
        mock_account.openPositionCount = 0

        mock_response.body = {"account": mock_account}

        # Setup mock context
        mock_context = Mock()
        mock_context.account.get.return_value = mock_response
        mock_context_class.return_value = mock_context

        # Create validator and validate
        validator = OandaAPIValidator(
            account_id="001-001-1234567-001",
            api_token="test_token",
            api_type="practice",
        )

        is_valid, error, details = validator.validate()

        # Assertions
        assert is_valid is True
        assert error is None
        assert details is not None
        assert details["margin_used"] == 0.0
        assert details["margin_available"] == 0.0
        assert details["unrealized_pnl"] == 0.0


class TestOandaAPIValidatorClassMethod:
    """Test cases for OandaAPIValidator class method."""

    @patch("accounts.oanda_validator.v20.Context")
    def test_validate_credentials_class_method(self, mock_context_class: Mock) -> None:
        """Test validate_credentials class method."""
        # Setup mock response
        mock_response = Mock()
        mock_response.status = 200

        # Setup mock account object
        mock_account = Mock()
        mock_account.id = "001-001-1234567-001"
        mock_account.currency = "USD"
        mock_account.balance = "10000.00"
        mock_account.marginUsed = "500.00"
        mock_account.marginAvailable = "9500.00"
        mock_account.unrealizedPL = "50.00"
        mock_account.openTradeCount = 2
        mock_account.openPositionCount = 1

        mock_response.body = {"account": mock_account}

        # Setup mock context
        mock_context = Mock()
        mock_context.account.get.return_value = mock_response
        mock_context_class.return_value = mock_context

        # Use class method to validate
        is_valid, error, details = OandaAPIValidator.validate_credentials(
            account_id="001-001-1234567-001",
            api_token="test_token",
            api_type="practice",
        )

        # Assertions
        assert is_valid is True
        assert error is None
        assert details is not None
        assert details["account_id"] == "001-001-1234567-001"


class TestOandaAPIValidatorErrorExtraction:
    """Test cases for error message extraction."""

    def test_extract_error_message_with_error_message(self) -> None:
        """Test error extraction when errorMessage is present."""
        validator = OandaAPIValidator(
            account_id="001-001-1234567-001",
            api_token="test_token",
            api_type="practice",
        )

        mock_response = Mock()
        mock_response.status = 401
        mock_response.body = {"errorMessage": "Invalid credentials"}

        error_msg = validator._extract_error_message(mock_response)

        assert "Invalid credentials" in error_msg

    def test_extract_error_message_without_error_message(self) -> None:
        """Test error extraction when errorMessage is not present."""
        validator = OandaAPIValidator(
            account_id="001-001-1234567-001",
            api_token="test_token",
            api_type="practice",
        )

        mock_response = Mock()
        mock_response.status = 500
        mock_response.body = {}

        error_msg = validator._extract_error_message(mock_response)

        assert "status code 500" in error_msg

    def test_extract_error_message_with_exception(self) -> None:
        """Test error extraction when an exception occurs."""
        validator = OandaAPIValidator(
            account_id="001-001-1234567-001",
            api_token="test_token",
            api_type="practice",
        )

        mock_response = Mock()
        mock_response.status = 500
        mock_response.body = Mock(side_effect=Exception("Error"))

        error_msg = validator._extract_error_message(mock_response)

        assert "status code 500" in error_msg
