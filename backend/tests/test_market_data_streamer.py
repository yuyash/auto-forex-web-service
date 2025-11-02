"""
Unit tests for MarketDataStreamer class.

Tests cover:
- Stream initialization with mocked v20 API
- Tick data processing and normalization
- Connection handling
"""

from unittest.mock import MagicMock, patch

import pytest

from accounts.models import OandaAccount
from trading.market_data_streamer import MarketDataStreamer, TickData


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


@pytest.mark.django_db
class TestTickData:
    """Test TickData class"""

    def test_tick_data_initialization(self):
        """Test TickData initialization with all fields"""
        tick = TickData(
            instrument="EUR_USD",
            time="2025-11-01T10:30:00.000000Z",
            bid=1.1000,
            ask=1.1002,
            bid_liquidity=1000000,
            ask_liquidity=1000000,
        )

        assert tick.instrument == "EUR_USD"
        assert tick.time == "2025-11-01T10:30:00.000000Z"
        assert tick.bid == 1.1000
        assert tick.ask == 1.1002
        assert tick.mid == pytest.approx(1.1001)
        assert tick.spread == pytest.approx(0.0002)
        assert tick.bid_liquidity == 1000000
        assert tick.ask_liquidity == 1000000

    def test_tick_data_mid_calculation(self):
        """Test mid price calculation"""
        tick = TickData(
            instrument="GBP_USD", time="2025-11-01T10:30:00.000000Z", bid=1.2500, ask=1.2504
        )

        assert tick.mid == 1.2502

    def test_tick_data_spread_calculation(self):
        """Test spread calculation"""
        tick = TickData(
            instrument="USD_JPY", time="2025-11-01T10:30:00.000000Z", bid=150.00, ask=150.05
        )

        assert tick.spread == pytest.approx(0.05)

    def test_tick_data_to_dict(self):
        """Test conversion to dictionary"""
        tick = TickData(
            instrument="EUR_USD",
            time="2025-11-01T10:30:00.000000Z",
            bid=1.1000,
            ask=1.1002,
            bid_liquidity=1000000,
            ask_liquidity=1000000,
        )

        tick_dict = tick.to_dict()

        assert tick_dict["instrument"] == "EUR_USD"
        assert tick_dict["time"] == "2025-11-01T10:30:00.000000Z"
        assert tick_dict["bid"] == 1.1000
        assert tick_dict["ask"] == 1.1002
        assert tick_dict["mid"] == pytest.approx(1.1001)
        assert tick_dict["spread"] == pytest.approx(0.0002)
        assert tick_dict["bid_liquidity"] == 1000000
        assert tick_dict["ask_liquidity"] == 1000000


@pytest.mark.django_db
class TestMarketDataStreamer:
    """Test MarketDataStreamer class"""

    def test_initialization(self, mock_oanda_account):
        """Test streamer initialization"""
        streamer = MarketDataStreamer(mock_oanda_account)

        assert streamer.account == mock_oanda_account
        assert streamer.api_context is None
        assert streamer.stream is None
        assert streamer.is_connected is False
        assert streamer.instruments == []
        assert streamer.tick_callback is None

    @patch("trading.market_data_streamer.v20.Context")
    def test_initialize_connection_practice(self, mock_v20_context, mock_oanda_account):
        """Test connection initialization for practice account"""
        streamer = MarketDataStreamer(mock_oanda_account)
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

    @patch("trading.market_data_streamer.v20.Context")
    def test_initialize_connection_live(self, mock_v20_context, mock_oanda_account):
        """Test connection initialization for live account"""
        mock_oanda_account.api_type = "live"
        mock_oanda_account.save()

        streamer = MarketDataStreamer(mock_oanda_account)
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

        streamer = MarketDataStreamer(mock_oanda_account)

        with pytest.raises(ValueError, match="API token is required"):
            streamer.initialize_connection()

    def test_initialize_connection_invalid_api_type(self, mock_oanda_account):
        """Test connection initialization fails with invalid API type"""
        mock_oanda_account.api_type = "invalid"
        mock_oanda_account.save()

        streamer = MarketDataStreamer(mock_oanda_account)

        with pytest.raises(ValueError, match="Invalid API type"):
            streamer.initialize_connection()

    @patch("trading.market_data_streamer.v20.Context")
    def test_start_stream_success(self, mock_v20_context, mock_oanda_account):
        """Test starting market data stream successfully"""
        # Setup mock context and pricing stream
        mock_context_instance = MagicMock()
        mock_v20_context.return_value = mock_context_instance

        mock_response = MagicMock()
        mock_context_instance.pricing.stream.return_value = mock_response

        streamer = MarketDataStreamer(mock_oanda_account)
        streamer.initialize_connection()
        streamer.start_stream(["EUR_USD", "GBP_USD"])

        # Verify stream was started with correct parameters
        mock_context_instance.pricing.stream.assert_called_once_with(
            accountID="001-001-1234567-001", instruments="EUR_USD,GBP_USD", snapshot=True
        )

        assert streamer.is_connected is True
        assert streamer.instruments == ["EUR_USD", "GBP_USD"]
        assert streamer.stream == mock_response

    def test_start_stream_not_initialized(self, mock_oanda_account):
        """Test starting stream fails if connection not initialized"""
        streamer = MarketDataStreamer(mock_oanda_account)

        with pytest.raises(RuntimeError, match="Connection not initialized"):
            streamer.start_stream(["EUR_USD"])

    @patch("trading.market_data_streamer.v20.Context")
    def test_start_stream_no_instruments(self, mock_v20_context, mock_oanda_account):
        """Test starting stream fails without instruments"""
        streamer = MarketDataStreamer(mock_oanda_account)
        streamer.initialize_connection()

        with pytest.raises(ValueError, match="At least one instrument is required"):
            streamer.start_stream([])

    @patch("trading.market_data_streamer.v20.Context")
    def test_process_price_message(self, mock_v20_context, mock_oanda_account):
        """Test processing price message and tick normalization"""
        streamer = MarketDataStreamer(mock_oanda_account)
        streamer.initialize_connection()

        # Create mock price message
        mock_price_msg = MagicMock()
        mock_price_msg.instrument = "EUR_USD"
        mock_price_msg.time = "2025-11-01T10:30:00.000000Z"

        # Mock bid/ask data
        mock_bid = MagicMock()
        mock_bid.price = "1.1000"
        mock_bid.liquidity = 1000000

        mock_ask = MagicMock()
        mock_ask.price = "1.1002"
        mock_ask.liquidity = 1000000

        mock_price_msg.bids = [mock_bid]
        mock_price_msg.asks = [mock_ask]

        # Register callback to capture tick data
        captured_tick = None

        def tick_callback(tick):
            nonlocal captured_tick
            captured_tick = tick

        streamer.register_tick_callback(tick_callback)

        # Process the price message
        streamer._process_price_message(mock_price_msg)

        # Verify tick data was processed correctly
        assert captured_tick is not None
        assert captured_tick.instrument == "EUR_USD"
        assert captured_tick.time == "2025-11-01T10:30:00.000000Z"
        assert captured_tick.bid == 1.1000
        assert captured_tick.ask == 1.1002
        assert captured_tick.mid == pytest.approx(1.1001)
        assert captured_tick.spread == pytest.approx(0.0002)
        assert captured_tick.bid_liquidity == 1000000
        assert captured_tick.ask_liquidity == 1000000

    @patch("trading.market_data_streamer.v20.Context")
    def test_process_price_message_missing_data(self, mock_v20_context, mock_oanda_account):
        """Test processing price message with missing bid/ask data"""
        streamer = MarketDataStreamer(mock_oanda_account)
        streamer.initialize_connection()

        # Create mock price message with missing data
        mock_price_msg = MagicMock()
        mock_price_msg.instrument = "EUR_USD"
        mock_price_msg.time = "2025-11-01T10:30:00.000000Z"
        mock_price_msg.bids = []
        mock_price_msg.asks = []

        # Register callback
        captured_tick = None

        def tick_callback(tick):
            nonlocal captured_tick
            captured_tick = tick

        streamer.register_tick_callback(tick_callback)

        # Process the price message - should not call callback
        streamer._process_price_message(mock_price_msg)

        # Verify callback was not called
        assert captured_tick is None

    @patch("trading.market_data_streamer.v20.Context")
    def test_process_heartbeat_message(self, mock_v20_context, mock_oanda_account):
        """Test processing heartbeat message"""
        streamer = MarketDataStreamer(mock_oanda_account)
        streamer.initialize_connection()

        # Create mock heartbeat message
        mock_heartbeat = MagicMock()
        mock_heartbeat.time = "2025-11-01T10:30:00.000000Z"

        # Process heartbeat - should not raise exception
        streamer._process_heartbeat_message(mock_heartbeat)

    def test_register_tick_callback(self, mock_oanda_account):
        """Test registering tick callback"""
        streamer = MarketDataStreamer(mock_oanda_account)

        def my_callback(tick):
            pass

        streamer.register_tick_callback(my_callback)

        assert streamer.tick_callback == my_callback

    @patch("trading.market_data_streamer.v20.Context")
    def test_stop_stream(self, mock_v20_context, mock_oanda_account):
        """Test stopping market data stream"""
        # Setup mock stream
        mock_context_instance = MagicMock()
        mock_v20_context.return_value = mock_context_instance

        mock_stream = MagicMock()
        mock_context_instance.pricing.stream.return_value = mock_stream

        streamer = MarketDataStreamer(mock_oanda_account)
        streamer.initialize_connection()
        streamer.start_stream(["EUR_USD"])

        # Stop the stream
        streamer.stop_stream()

        # Verify stream was terminated
        mock_stream.terminate.assert_called_once_with("User requested stop")
        assert streamer.stream is None
        assert streamer.is_connected is False

    def test_stop_stream_no_stream(self, mock_oanda_account):
        """Test stopping stream when no stream is active"""
        streamer = MarketDataStreamer(mock_oanda_account)

        # Should not raise exception
        streamer.stop_stream()

        assert streamer.stream is None
        assert streamer.is_connected is False

    @patch("trading.market_data_streamer.v20.Context")
    def test_get_connection_status(self, mock_v20_context, mock_oanda_account):
        """Test getting connection status"""
        mock_context_instance = MagicMock()
        mock_v20_context.return_value = mock_context_instance

        mock_response = MagicMock()
        mock_context_instance.pricing.stream.return_value = mock_response

        streamer = MarketDataStreamer(mock_oanda_account)
        streamer.initialize_connection()
        streamer.start_stream(["EUR_USD", "GBP_USD"])

        status = streamer.get_connection_status()

        assert status["is_connected"] is True
        assert status["account_id"] == "001-001-1234567-001"
        assert status["instruments"] == ["EUR_USD", "GBP_USD"]
        assert status["api_type"] == "practice"

    def test_get_connection_status_not_connected(self, mock_oanda_account):
        """Test getting connection status when not connected"""
        streamer = MarketDataStreamer(mock_oanda_account)

        status = streamer.get_connection_status()

        assert status["is_connected"] is False
        assert status["account_id"] == "001-001-1234567-001"
        assert status["instruments"] == []
        assert status["api_type"] == "practice"
