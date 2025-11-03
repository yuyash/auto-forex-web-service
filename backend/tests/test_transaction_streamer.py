"""
Unit tests for TransactionStreamer class.

Tests cover:
- Transaction stream initialization with mocked v20 API
- Order fill transaction processing
- Order cancel transaction processing
- Position update transaction processing
- Reconnection logic with exponential backoff

Requirements: 8.3, 9.1
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from accounts.models import OandaAccount
from trading.event_models import Event
from trading.models import Order, Position, Strategy
from trading.transaction_streamer import TransactionData, TransactionStreamer


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
        api_token="test_token_12345",
        api_type="practice",
        balance=10000.00,
    )
    return account


@pytest.fixture
def mock_strategy(db, mock_oanda_account):
    """Create a mock strategy for testing"""
    strategy = Strategy.objects.create(
        account=mock_oanda_account,
        strategy_type="test_strategy",
        is_active=True,
        config={"lot_size": 1000},
        instruments=["EUR_USD"],
    )
    return strategy


@pytest.mark.django_db
class TestTransactionData:
    """Test TransactionData class"""

    def test_transaction_data_initialization(self):
        """Test TransactionData initialization with all fields"""
        transaction = TransactionData(
            transaction_id="12345",
            transaction_type="ORDER_FILL",
            time="2025-11-01T10:30:00.000000Z",
            account_id="001-001-1234567-001",
            details={
                "orderID": "67890",
                "instrument": "EUR_USD",
                "units": "1000",
                "price": "1.1000",
            },
        )

        assert transaction.transaction_id == "12345"
        assert transaction.transaction_type == "ORDER_FILL"
        assert transaction.time == "2025-11-01T10:30:00.000000Z"
        assert transaction.account_id == "001-001-1234567-001"
        assert transaction.details["orderID"] == "67890"

    def test_transaction_data_to_dict(self):
        """Test conversion to dictionary"""
        transaction = TransactionData(
            transaction_id="12345",
            transaction_type="ORDER_FILL",
            time="2025-11-01T10:30:00.000000Z",
            account_id="001-001-1234567-001",
            details={"orderID": "67890"},
        )

        transaction_dict = transaction.to_dict()

        assert transaction_dict["transaction_id"] == "12345"
        assert transaction_dict["transaction_type"] == "ORDER_FILL"
        assert transaction_dict["time"] == "2025-11-01T10:30:00.000000Z"
        assert transaction_dict["account_id"] == "001-001-1234567-001"
        assert transaction_dict["details"]["orderID"] == "67890"


@pytest.mark.django_db
class TestTransactionStreamer:
    """Test TransactionStreamer class"""

    def test_initialization(self, mock_oanda_account):
        """Test streamer initialization"""
        streamer = TransactionStreamer(mock_oanda_account)

        assert streamer.account == mock_oanda_account
        assert streamer.api_context is None
        assert streamer.stream is None
        assert streamer.is_connected is False
        assert streamer.transaction_callback is None

    @patch("trading.transaction_streamer.v20.Context")
    def test_initialize_connection_practice(self, mock_v20_context, mock_oanda_account):
        """Test connection initialization for practice account"""
        streamer = TransactionStreamer(mock_oanda_account)
        streamer.initialize_connection()

        # Verify v20.Context was called with correct parameters
        mock_v20_context.assert_called_once_with(
            hostname="api-fxpractice.oanda.com",
            token="test_token_12345",
            port=443,
            ssl=True,
            application="AutoForexTradingSystem",
        )

        assert streamer.api_context is not None

    @patch("trading.transaction_streamer.v20.Context")
    def test_initialize_connection_live(self, mock_v20_context, mock_oanda_account):
        """Test connection initialization for live account"""
        mock_oanda_account.api_type = "live"
        mock_oanda_account.save()

        streamer = TransactionStreamer(mock_oanda_account)
        streamer.initialize_connection()

        # Verify v20.Context was called with live hostname
        mock_v20_context.assert_called_once_with(
            hostname="api-fxtrade.oanda.com",
            token="test_token_12345",
            port=443,
            ssl=True,
            application="AutoForexTradingSystem",
        )

    def test_initialize_connection_no_token(self, mock_oanda_account):
        """Test connection initialization fails without API token"""
        mock_oanda_account.api_token = ""
        mock_oanda_account.save()

        streamer = TransactionStreamer(mock_oanda_account)

        with pytest.raises(ValueError, match="API token is required"):
            streamer.initialize_connection()

    def test_initialize_connection_invalid_api_type(self, mock_oanda_account):
        """Test connection initialization fails with invalid API type"""
        mock_oanda_account.api_type = "invalid"
        mock_oanda_account.save()

        streamer = TransactionStreamer(mock_oanda_account)

        with pytest.raises(ValueError, match="Invalid API type"):
            streamer.initialize_connection()

    @patch("trading.transaction_streamer.v20.Context")
    def test_start_stream_success(self, mock_v20_context, mock_oanda_account):
        """Test starting transaction stream successfully"""
        # Setup mock context and transaction stream
        mock_context_instance = MagicMock()
        mock_v20_context.return_value = mock_context_instance

        mock_response = MagicMock()
        mock_context_instance.transaction.stream.return_value = mock_response

        streamer = TransactionStreamer(mock_oanda_account)
        streamer.initialize_connection()
        streamer.start_stream()

        # Verify stream was started with correct parameters
        mock_context_instance.transaction.stream.assert_called_once_with(
            accountID="001-001-1234567-001"
        )

        assert streamer.is_connected is True
        assert streamer.stream == mock_response

    def test_start_stream_not_initialized(self, mock_oanda_account):
        """Test starting stream fails if connection not initialized"""
        streamer = TransactionStreamer(mock_oanda_account)

        with pytest.raises(RuntimeError, match="Connection not initialized"):
            streamer.start_stream()

    @patch("trading.transaction_streamer.v20.Context")
    def test_handle_order_fill(self, mock_v20_context, mock_oanda_account, mock_strategy):
        """Test handling ORDER_FILL transaction"""
        streamer = TransactionStreamer(mock_oanda_account)
        streamer.initialize_connection()

        # Create a pending order
        order = Order.objects.create(
            account=mock_oanda_account,
            strategy=mock_strategy,
            order_id="67890",
            instrument="EUR_USD",
            order_type="market",
            direction="long",
            units=Decimal("1000"),
            status="pending",
        )

        # Create mock transaction
        transaction = TransactionData(
            transaction_id="12345",
            transaction_type="ORDER_FILL",
            time="2025-11-01T10:30:00.000000Z",
            account_id="001-001-1234567-001",
            details={
                "orderID": "67890",
                "instrument": "EUR_USD",
                "units": "1000",
                "price": "1.1000",
                "pl": "0",
            },
        )

        # Handle the transaction
        streamer._handle_order_fill(transaction)

        # Verify order was updated
        order.refresh_from_db()
        assert order.status == "filled"
        assert order.filled_at is not None

        # Verify position was created
        position = Position.objects.filter(
            account=mock_oanda_account, instrument="EUR_USD", closed_at__isnull=True
        ).first()
        assert position is not None
        assert position.units == Decimal("1000")
        assert position.entry_price == Decimal("1.1000")

        # Verify event was logged
        event = Event.objects.filter(event_type="order_filled").first()
        assert event is not None
        assert event.category == "trading"

    @patch("trading.transaction_streamer.v20.Context")
    def test_handle_order_fill_order_not_found(self, mock_v20_context, mock_oanda_account):
        """Test handling ORDER_FILL for non-existent order"""
        streamer = TransactionStreamer(mock_oanda_account)
        streamer.initialize_connection()

        # Create mock transaction for non-existent order
        transaction = TransactionData(
            transaction_id="12345",
            transaction_type="ORDER_FILL",
            time="2025-11-01T10:30:00.000000Z",
            account_id="001-001-1234567-001",
            details={
                "orderID": "99999",
                "instrument": "EUR_USD",
                "units": "1000",
                "price": "1.1000",
                "pl": "0",
            },
        )

        # Should not raise exception
        streamer._handle_order_fill(transaction)

        # Verify event was still logged
        event = Event.objects.filter(event_type="order_filled").first()
        assert event is not None

    @patch("trading.transaction_streamer.v20.Context")
    def test_handle_order_cancel(self, mock_v20_context, mock_oanda_account, mock_strategy):
        """Test handling ORDER_CANCEL transaction"""
        streamer = TransactionStreamer(mock_oanda_account)
        streamer.initialize_connection()

        # Create a pending order
        order = Order.objects.create(
            account=mock_oanda_account,
            strategy=mock_strategy,
            order_id="67890",
            instrument="EUR_USD",
            order_type="limit",
            direction="long",
            units=Decimal("1000"),
            price=Decimal("1.0950"),
            status="pending",
        )

        # Create mock transaction
        transaction = TransactionData(
            transaction_id="12345",
            transaction_type="ORDER_CANCEL",
            time="2025-11-01T10:30:00.000000Z",
            account_id="001-001-1234567-001",
            details={
                "orderID": "67890",
                "reason": "USER_REQUEST",
            },
        )

        # Handle the transaction
        streamer._handle_order_cancel(transaction)

        # Verify order was updated
        order.refresh_from_db()
        assert order.status == "cancelled"

        # Verify event was logged
        event = Event.objects.filter(event_type="order_cancelled").first()
        assert event is not None
        assert event.category == "trading"

    @patch("trading.transaction_streamer.v20.Context")
    def test_handle_order_cancel_order_not_found(self, mock_v20_context, mock_oanda_account):
        """Test handling ORDER_CANCEL for non-existent order"""
        streamer = TransactionStreamer(mock_oanda_account)
        streamer.initialize_connection()

        # Create mock transaction for non-existent order
        transaction = TransactionData(
            transaction_id="12345",
            transaction_type="ORDER_CANCEL",
            time="2025-11-01T10:30:00.000000Z",
            account_id="001-001-1234567-001",
            details={
                "orderID": "99999",
                "reason": "USER_REQUEST",
            },
        )

        # Should not raise exception
        streamer._handle_order_cancel(transaction)

        # Verify event was still logged
        event = Event.objects.filter(event_type="order_cancelled").first()
        assert event is not None

    @patch("trading.transaction_streamer.v20.Context")
    def test_handle_position_close(self, mock_v20_context, mock_oanda_account, mock_strategy):
        """Test handling TRADE_CLOSE transaction"""
        streamer = TransactionStreamer(mock_oanda_account)
        streamer.initialize_connection()

        # Create an open position
        position = Position.objects.create(
            account=mock_oanda_account,
            strategy=mock_strategy,
            position_id="trade123",
            instrument="EUR_USD",
            direction="long",
            units=Decimal("1000"),
            entry_price=Decimal("1.1000"),
            current_price=Decimal("1.1000"),
            unrealized_pnl=Decimal("0"),
        )

        # Create mock transaction
        transaction = TransactionData(
            transaction_id="12345",
            transaction_type="TRADE_CLOSE",
            time="2025-11-01T10:30:00.000000Z",
            account_id="001-001-1234567-001",
            details={
                "tradeID": "trade123",
                "instrument": "EUR_USD",
                "units": "-1000",
                "price": "1.1050",
                "pl": "50.00",
            },
        )

        # Handle the transaction
        streamer._handle_position_update(transaction)

        # Verify position was closed
        position.refresh_from_db()
        assert position.closed_at is not None
        assert position.realized_pnl == Decimal("50.00")
        assert position.current_price == Decimal("1.1050")

        # Verify event was logged
        event = Event.objects.filter(event_type="position_closed").first()
        assert event is not None
        assert event.category == "trading"

    @patch("trading.transaction_streamer.v20.Context")
    def test_handle_position_reduce(self, mock_v20_context, mock_oanda_account, mock_strategy):
        """Test handling TRADE_REDUCE transaction (partial close)"""
        streamer = TransactionStreamer(mock_oanda_account)
        streamer.initialize_connection()

        # Create an open position
        position = Position.objects.create(
            account=mock_oanda_account,
            strategy=mock_strategy,
            position_id="trade123",
            instrument="EUR_USD",
            direction="long",
            units=Decimal("2000"),
            entry_price=Decimal("1.1000"),
            current_price=Decimal("1.1000"),
            unrealized_pnl=Decimal("0"),
        )

        # Create mock transaction
        transaction = TransactionData(
            transaction_id="12345",
            transaction_type="TRADE_REDUCE",
            time="2025-11-01T10:30:00.000000Z",
            account_id="001-001-1234567-001",
            details={
                "tradeID": "trade123",
                "instrument": "EUR_USD",
                "units": "-1000",
                "price": "1.1050",
                "pl": "50.00",
            },
        )

        # Handle the transaction
        streamer._handle_position_update(transaction)

        # Verify position was reduced
        position.refresh_from_db()
        assert position.closed_at is None  # Still open
        assert position.units == Decimal("1000")  # Reduced by 1000
        assert position.current_price == Decimal("1.1050")

        # Verify event was logged
        event = Event.objects.filter(event_type="position_reduced").first()
        assert event is not None
        assert event.category == "trading"

    @patch("trading.transaction_streamer.v20.Context")
    def test_handle_position_update_not_found(self, mock_v20_context, mock_oanda_account):
        """Test handling position update for non-existent position"""
        streamer = TransactionStreamer(mock_oanda_account)
        streamer.initialize_connection()

        # Create mock transaction for non-existent position
        transaction = TransactionData(
            transaction_id="12345",
            transaction_type="TRADE_CLOSE",
            time="2025-11-01T10:30:00.000000Z",
            account_id="001-001-1234567-001",
            details={
                "tradeID": "trade999",
                "instrument": "EUR_USD",
                "units": "-1000",
                "price": "1.1050",
                "pl": "50.00",
            },
        )

        # Should not raise exception
        streamer._handle_position_update(transaction)

    @patch("trading.transaction_streamer.v20.Context")
    def test_process_transaction_message(self, mock_v20_context, mock_oanda_account):
        """Test processing transaction message and routing to handlers"""
        streamer = TransactionStreamer(mock_oanda_account)
        streamer.initialize_connection()

        # Create mock transaction message
        mock_transaction_msg = MagicMock()
        mock_transaction_msg.id = "12345"
        mock_transaction_msg.type = "ORDER_FILL"
        mock_transaction_msg.time = "2025-11-01T10:30:00.000000Z"
        mock_transaction_msg.dict.return_value = {
            "id": "12345",
            "type": "ORDER_FILL",
            "orderID": "67890",
            "instrument": "EUR_USD",
            "units": "1000",
            "price": "1.1000",
        }

        # Register callback to capture transaction data
        captured_transaction = None

        def transaction_callback(transaction):
            nonlocal captured_transaction
            captured_transaction = transaction

        streamer.register_transaction_callback(transaction_callback)

        # Process the transaction message
        streamer._process_transaction_message(mock_transaction_msg)

        # Verify transaction data was processed correctly
        assert captured_transaction is not None
        assert captured_transaction.transaction_id == "12345"
        assert captured_transaction.transaction_type == "ORDER_FILL"

    @patch("trading.transaction_streamer.v20.Context")
    def test_process_heartbeat_message(self, mock_v20_context, mock_oanda_account):
        """Test processing heartbeat message"""
        streamer = TransactionStreamer(mock_oanda_account)
        streamer.initialize_connection()

        # Create mock heartbeat message
        mock_heartbeat = MagicMock()
        mock_heartbeat.time = "2025-11-01T10:30:00.000000Z"

        # Process heartbeat - should not raise exception
        streamer._process_heartbeat_message(mock_heartbeat)

    def test_register_transaction_callback(self, mock_oanda_account):
        """Test registering transaction callback"""
        streamer = TransactionStreamer(mock_oanda_account)

        def my_callback(transaction):
            pass

        streamer.register_transaction_callback(my_callback)

        assert streamer.transaction_callback == my_callback

    @patch("trading.transaction_streamer.v20.Context")
    def test_stop_stream(self, mock_v20_context, mock_oanda_account):
        """Test stopping transaction stream"""
        # Setup mock stream
        mock_context_instance = MagicMock()
        mock_v20_context.return_value = mock_context_instance

        mock_stream = MagicMock()
        mock_context_instance.transaction.stream.return_value = mock_stream

        streamer = TransactionStreamer(mock_oanda_account)
        streamer.initialize_connection()
        streamer.start_stream()

        # Stop the stream
        streamer.stop_stream()

        # Verify stream was terminated
        mock_stream.terminate.assert_called_once_with("User requested stop")
        assert streamer.stream is None
        assert streamer.is_connected is False

        # Verify event was logged
        event = Event.objects.filter(event_type="transaction_stream_stopped").first()
        assert event is not None

    def test_stop_stream_no_stream(self, mock_oanda_account):
        """Test stopping stream when no stream is active"""
        streamer = TransactionStreamer(mock_oanda_account)

        # Should not raise exception
        streamer.stop_stream()

        assert streamer.stream is None
        assert streamer.is_connected is False

    @patch("trading.transaction_streamer.v20.Context")
    def test_get_connection_status(self, mock_v20_context, mock_oanda_account):
        """Test getting connection status"""
        mock_context_instance = MagicMock()
        mock_v20_context.return_value = mock_context_instance

        mock_response = MagicMock()
        mock_context_instance.transaction.stream.return_value = mock_response

        streamer = TransactionStreamer(mock_oanda_account)
        streamer.initialize_connection()
        streamer.start_stream()

        status = streamer.get_connection_status()

        assert status["is_connected"] is True
        assert status["account_id"] == "001-001-1234567-001"
        assert status["api_type"] == "practice"

    def test_get_connection_status_not_connected(self, mock_oanda_account):
        """Test getting connection status when not connected"""
        streamer = TransactionStreamer(mock_oanda_account)

        status = streamer.get_connection_status()

        assert status["is_connected"] is False
        assert status["account_id"] == "001-001-1234567-001"
        assert status["api_type"] == "practice"


@pytest.mark.django_db
class TestTransactionStreamReconnection:
    """Test transaction stream reconnection logic"""

    @patch("trading.transaction_streamer.v20.Context")
    @patch("trading.transaction_streamer.time.sleep")
    def test_successful_reconnection_first_attempt(
        self, mock_sleep, mock_v20_context, mock_oanda_account
    ):
        """Test successful reconnection on first attempt"""
        # Setup mock context and transaction stream
        mock_context_instance = MagicMock()
        mock_v20_context.return_value = mock_context_instance

        mock_response = MagicMock()
        mock_context_instance.transaction.stream.return_value = mock_response

        streamer = TransactionStreamer(mock_oanda_account)
        streamer.initialize_connection()

        # Attempt reconnection
        result = streamer.reconnect()

        # Verify successful reconnection
        assert result is True
        assert streamer.is_connected is True
        # After successful connection, reconnection manager is reset to 0
        assert streamer.reconnection_manager.current_attempt == 0
        mock_sleep.assert_called_once_with(1)  # First backoff interval

    @patch("trading.transaction_streamer.v20.Context")
    @patch("trading.transaction_streamer.time.sleep")
    def test_successful_reconnection_after_failures(
        self, mock_sleep, mock_v20_context, mock_oanda_account
    ):
        """Test successful reconnection after some failures"""
        # Setup mock context
        mock_context_instance = MagicMock()
        mock_v20_context.return_value = mock_context_instance

        # First two attempts fail, third succeeds
        mock_context_instance.transaction.stream.side_effect = [
            Exception("Connection failed"),
            Exception("Connection failed"),
            MagicMock(),  # Success on third attempt
        ]

        streamer = TransactionStreamer(mock_oanda_account)
        streamer.initialize_connection()

        # Attempt reconnection
        result = streamer.reconnect()

        # Verify successful reconnection after 3 attempts
        assert result is True
        assert streamer.is_connected is True
        # After successful connection, reconnection manager is reset to 0
        assert streamer.reconnection_manager.current_attempt == 0
        # Should have called sleep 3 times (1s, 2s, 4s)
        assert mock_sleep.call_count == 3

    @patch("trading.transaction_streamer.v20.Context")
    @patch("trading.transaction_streamer.time.sleep")
    def test_reconnection_max_attempts_reached(
        self, mock_sleep, mock_v20_context, mock_oanda_account
    ):
        """Test reconnection fails after maximum attempts (5)"""
        # Setup mock context
        mock_context_instance = MagicMock()
        mock_v20_context.return_value = mock_context_instance

        # All attempts fail
        mock_context_instance.transaction.stream.side_effect = Exception("Connection failed")

        streamer = TransactionStreamer(mock_oanda_account)
        streamer.initialize_connection()

        # Attempt reconnection
        result = streamer.reconnect()

        # Verify reconnection failed
        assert result is False
        assert streamer.is_connected is False
        assert streamer.reconnection_manager.current_attempt == 5
        # Should have called sleep 5 times (1s, 2s, 4s, 8s, 16s)
        assert mock_sleep.call_count == 5

    @patch("trading.transaction_streamer.v20.Context")
    @patch("trading.transaction_streamer.time.sleep")
    def test_reconnection_manager_reset_on_success(
        self, mock_sleep, mock_v20_context, mock_oanda_account
    ):
        """Test reconnection manager is reset after successful connection"""
        # Setup mock context
        mock_context_instance = MagicMock()
        mock_v20_context.return_value = mock_context_instance

        mock_response = MagicMock()
        mock_context_instance.transaction.stream.return_value = mock_response

        streamer = TransactionStreamer(mock_oanda_account)
        streamer.initialize_connection()
        streamer.start_stream()

        # Verify reconnection manager was reset
        assert streamer.reconnection_manager.current_attempt == 0

    @patch("trading.transaction_streamer.v20.Context")
    def test_connection_status_includes_reconnection_status(
        self, mock_v20_context, mock_oanda_account
    ):
        """Test connection status includes reconnection manager status"""
        mock_context_instance = MagicMock()
        mock_v20_context.return_value = mock_context_instance

        streamer = TransactionStreamer(mock_oanda_account)
        streamer.initialize_connection()

        status = streamer.get_connection_status()

        # Verify reconnection status is included
        assert "reconnection_status" in status
        assert status["reconnection_status"]["current_attempt"] == 0
        assert status["reconnection_status"]["max_attempts"] == 5
        assert status["reconnection_status"]["can_retry"] is True
