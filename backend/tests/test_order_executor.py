"""
Unit tests for OrderExecutor class.

Tests cover:
- Market order submission (mocked)
- Limit order submission
- Stop order submission
- OCO order submission
- Retry logic on failures

Requirements: 8.1, 8.2, 8.4
"""

from decimal import Decimal
from unittest.mock import Mock, patch

import pytest

from accounts.models import OandaAccount
from trading.models import Order
from trading.order_executor import OrderExecutionError, OrderExecutor


@pytest.fixture
def mock_oanda_account(db):
    """Create a mock OANDA account for testing"""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = User.objects.create_user(
        username="testuser", email="test@example.com", password="testpass123"
    )

    account = OandaAccount.objects.create(
        user=user,
        account_id="001-001-1234567-001",
        api_type="practice",
        balance=10000.00,
    )
    # Use set_api_token to properly encrypt the token
    account.set_api_token("test_token_12345")
    account.save()
    return account


@pytest.fixture
def mock_v20_context():
    """Create a mock v20 Context"""
    with patch("trading.order_executor.v20.Context") as mock_context:
        yield mock_context


@pytest.mark.django_db
class TestOrderExecutor:
    """Test OrderExecutor class"""

    def test_initialization(self, mock_oanda_account, mock_v20_context):
        """Test OrderExecutor initialization"""
        executor = OrderExecutor(mock_oanda_account)

        assert executor.account == mock_oanda_account
        assert executor.max_retries == 3
        assert executor.retry_delay == 0.5
        mock_v20_context.assert_called_once()

    def test_submit_market_order_success(self, mock_oanda_account, mock_v20_context):
        """Test successful market order submission"""
        # Setup mock response
        mock_response = Mock()
        mock_response.status = 201
        mock_response.orderFillTransaction = Mock()
        mock_response.orderFillTransaction.id = "12345"
        mock_response.orderFillTransaction.price = "1.1000"

        mock_api = Mock()
        mock_api.order.create.return_value = mock_response
        mock_v20_context.return_value = mock_api

        executor = OrderExecutor(mock_oanda_account)

        # Submit market order
        order = executor.submit_market_order(
            instrument="EUR_USD",
            units=Decimal("1000"),
            take_profit=Decimal("1.1050"),
            stop_loss=Decimal("1.0950"),
        )

        # Verify order was created
        assert order.order_id == "12345"
        assert order.instrument == "EUR_USD"
        assert order.order_type == "market"
        assert order.direction == "long"
        assert order.units == Decimal("1000")
        assert order.take_profit == Decimal("1.1050")
        assert order.stop_loss == Decimal("1.0950")
        assert order.status == "filled"

        # Verify API was called
        mock_api.order.create.assert_called_once()

    def test_submit_market_order_short(self, mock_oanda_account, mock_v20_context):
        """Test market order submission for short position"""
        # Setup mock response
        mock_response = Mock()
        mock_response.status = 201
        mock_response.orderFillTransaction = Mock()
        mock_response.orderFillTransaction.id = "12346"
        mock_response.orderFillTransaction.price = "1.1000"

        mock_api = Mock()
        mock_api.order.create.return_value = mock_response
        mock_v20_context.return_value = mock_api

        executor = OrderExecutor(mock_oanda_account)

        # Submit short market order
        order = executor.submit_market_order(
            instrument="EUR_USD",
            units=Decimal("-1000"),
        )

        # Verify order direction
        assert order.direction == "short"
        assert order.units == Decimal("1000")

    def test_submit_limit_order_success(self, mock_oanda_account, mock_v20_context):
        """Test successful limit order submission"""
        # Setup mock response
        mock_response = Mock()
        mock_response.status = 201
        mock_response.orderCreateTransaction = Mock()
        mock_response.orderCreateTransaction.id = "12347"

        mock_api = Mock()
        mock_api.order.create.return_value = mock_response
        mock_v20_context.return_value = mock_api

        executor = OrderExecutor(mock_oanda_account)

        # Submit limit order
        order = executor.submit_limit_order(
            instrument="GBP_USD",
            units=Decimal("2000"),
            price=Decimal("1.2500"),
            take_profit=Decimal("1.2550"),
            stop_loss=Decimal("1.2450"),
        )

        # Verify order was created
        assert order.order_id == "12347"
        assert order.instrument == "GBP_USD"
        assert order.order_type == "limit"
        assert order.direction == "long"
        assert order.units == Decimal("2000")
        assert order.price == Decimal("1.2500")
        assert order.take_profit == Decimal("1.2550")
        assert order.stop_loss == Decimal("1.2450")
        assert order.status == "pending"

    def test_submit_stop_order_success(self, mock_oanda_account, mock_v20_context):
        """Test successful stop order submission"""
        # Setup mock response
        mock_response = Mock()
        mock_response.status = 201
        mock_response.orderCreateTransaction = Mock()
        mock_response.orderCreateTransaction.id = "12348"

        mock_api = Mock()
        mock_api.order.create.return_value = mock_response
        mock_v20_context.return_value = mock_api

        executor = OrderExecutor(mock_oanda_account)

        # Submit stop order
        order = executor.submit_stop_order(
            instrument="USD_JPY",
            units=Decimal("1500"),
            price=Decimal("150.00"),
            take_profit=Decimal("150.50"),
            stop_loss=Decimal("149.50"),
        )

        # Verify order was created
        assert order.order_id == "12348"
        assert order.instrument == "USD_JPY"
        assert order.order_type == "stop"
        assert order.direction == "long"
        assert order.units == Decimal("1500")
        assert order.price == Decimal("150.00")
        assert order.take_profit == Decimal("150.50")
        assert order.stop_loss == Decimal("149.50")
        assert order.status == "pending"

    def test_submit_oco_order_success(self, mock_oanda_account, mock_v20_context):
        """Test successful OCO order submission"""
        # Setup mock responses
        mock_limit_response = Mock()
        mock_limit_response.status = 201
        mock_limit_response.orderCreateTransaction = Mock()
        mock_limit_response.orderCreateTransaction.id = "12349"

        mock_stop_response = Mock()
        mock_stop_response.status = 201
        mock_stop_response.orderCreateTransaction = Mock()
        mock_stop_response.orderCreateTransaction.id = "12350"

        mock_api = Mock()
        mock_api.order.create.side_effect = [mock_limit_response, mock_stop_response]
        mock_v20_context.return_value = mock_api

        executor = OrderExecutor(mock_oanda_account)

        # Submit OCO order
        limit_order, stop_order = executor.submit_oco_order(
            instrument="EUR_USD",
            units=Decimal("1000"),
            limit_price=Decimal("1.1050"),
            stop_price=Decimal("1.0950"),
        )

        # Verify limit order
        assert limit_order.order_id == "12349"
        assert limit_order.instrument == "EUR_USD"
        assert limit_order.order_type == "oco"
        assert limit_order.direction == "long"
        assert limit_order.units == Decimal("1000")
        assert limit_order.price == Decimal("1.1050")
        assert limit_order.status == "pending"

        # Verify stop order
        assert stop_order.order_id == "12350"
        assert stop_order.instrument == "EUR_USD"
        assert stop_order.order_type == "oco"
        assert stop_order.direction == "long"
        assert stop_order.units == Decimal("1000")
        assert stop_order.price == Decimal("1.0950")
        assert stop_order.status == "pending"

        # Verify API was called twice
        assert mock_api.order.create.call_count == 2

    def test_retry_logic_success_on_second_attempt(self, mock_oanda_account, mock_v20_context):
        """Test retry logic succeeds on second attempt"""
        # Setup mock responses - first fails, second succeeds
        mock_fail_response = Mock()
        mock_fail_response.status = 500

        mock_success_response = Mock()
        mock_success_response.status = 201
        mock_success_response.orderFillTransaction = Mock()
        mock_success_response.orderFillTransaction.id = "12351"
        mock_success_response.orderFillTransaction.price = "1.1000"

        mock_api = Mock()
        mock_api.order.create.side_effect = [mock_fail_response, mock_success_response]
        mock_v20_context.return_value = mock_api

        executor = OrderExecutor(mock_oanda_account)

        # Submit market order
        order = executor.submit_market_order(
            instrument="EUR_USD",
            units=Decimal("1000"),
        )

        # Verify order was created after retry
        assert order.order_id == "12351"
        assert order.status == "filled"

        # Verify API was called twice
        assert mock_api.order.create.call_count == 2

    def test_retry_logic_fails_after_max_attempts(self, mock_oanda_account, mock_v20_context):
        """Test retry logic fails after max attempts"""
        # Setup mock response - always fails
        mock_fail_response = Mock()
        mock_fail_response.status = 500

        mock_api = Mock()
        mock_api.order.create.return_value = mock_fail_response
        mock_v20_context.return_value = mock_api

        executor = OrderExecutor(mock_oanda_account)

        # Submit market order should raise exception
        with pytest.raises(OrderExecutionError) as exc_info:
            executor.submit_market_order(
                instrument="EUR_USD",
                units=Decimal("1000"),
            )

        # Verify error message
        assert "failed after 3 attempts" in str(exc_info.value)

        # Verify API was called 3 times
        assert mock_api.order.create.call_count == 3

    def test_retry_logic_with_exception(self, mock_oanda_account, mock_v20_context):
        """Test retry logic with API exception"""
        # Setup mock to raise exception
        mock_api = Mock()
        mock_api.order.create.side_effect = Exception("Connection error")
        mock_v20_context.return_value = mock_api

        executor = OrderExecutor(mock_oanda_account)

        # Submit market order should raise exception
        with pytest.raises(OrderExecutionError) as exc_info:
            executor.submit_market_order(
                instrument="EUR_USD",
                units=Decimal("1000"),
            )

        # Verify error message
        assert "failed after 3 attempts" in str(exc_info.value)
        assert "Connection error" in str(exc_info.value)

        # Verify API was called 3 times
        assert mock_api.order.create.call_count == 3

    def test_cancel_order_success(self, mock_oanda_account, mock_v20_context):
        """Test successful order cancellation"""
        # Create an order first
        order = Order.objects.create(
            account=mock_oanda_account,
            order_id="12352",
            instrument="EUR_USD",
            order_type="limit",
            direction="long",
            units=Decimal("1000"),
            price=Decimal("1.1000"),
            status="pending",
        )

        # Setup mock response
        mock_response = Mock()
        mock_response.status = 200

        mock_api = Mock()
        mock_api.order.cancel.return_value = mock_response
        mock_v20_context.return_value = mock_api

        executor = OrderExecutor(mock_oanda_account)

        # Cancel order
        result = executor.cancel_order("12352")

        # Verify cancellation
        assert result is True

        # Verify order status was updated
        order.refresh_from_db()
        assert order.status == "cancelled"

        # Verify API was called
        mock_api.order.cancel.assert_called_once_with(mock_oanda_account.account_id, "12352")

    def test_cancel_order_failure(self, mock_oanda_account, mock_v20_context):
        """Test order cancellation failure"""
        # Setup mock response
        mock_response = Mock()
        mock_response.status = 404

        mock_api = Mock()
        mock_api.order.cancel.return_value = mock_response
        mock_v20_context.return_value = mock_api

        executor = OrderExecutor(mock_oanda_account)

        # Cancel order
        result = executor.cancel_order("99999")

        # Verify cancellation failed
        assert result is False

    def test_cancel_order_exception(self, mock_oanda_account, mock_v20_context):
        """Test order cancellation with exception"""
        # Setup mock to raise exception
        mock_api = Mock()
        mock_api.order.cancel.side_effect = Exception("API error")
        mock_v20_context.return_value = mock_api

        executor = OrderExecutor(mock_oanda_account)

        # Cancel order
        result = executor.cancel_order("12353")

        # Verify cancellation failed
        assert result is False
