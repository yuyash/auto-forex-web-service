"""
Unit tests for market data streaming Celery tasks.

Tests cover:
- Starting market data streams
- Stopping market data streams
- Getting stream status
- Stream management with cache
"""

from unittest.mock import MagicMock, patch

from django.core.cache import cache

import pytest

from accounts.models import OandaAccount
from trading.tasks import (
    STREAM_CACHE_PREFIX,
    get_stream_status,
    start_market_data_stream,
    stop_market_data_stream,
)


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
        is_active=True,
    )
    return account


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear cache before and after each test"""
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
class TestStartMarketDataStream:
    """Test start_market_data_stream task"""

    @patch("trading.tasks.MarketDataStreamer")
    def test_start_stream_success(self, mock_streamer_class, mock_oanda_account):
        """Test successfully starting a market data stream"""
        # Setup mock streamer
        mock_streamer = MagicMock()
        mock_streamer_class.return_value = mock_streamer

        # Mock process_stream to return immediately (don't block)
        mock_streamer.process_stream.return_value = None

        # Start the stream
        result = start_market_data_stream(mock_oanda_account.id, ["EUR_USD", "GBP_USD"])

        # Verify result
        assert result["success"] is True
        assert result["account_id"] == "001-001-1234567-001"
        assert result["instruments"] == ["EUR_USD", "GBP_USD"]
        assert result["error"] is None

        # Verify streamer methods were called
        mock_streamer.initialize_connection.assert_called_once()
        mock_streamer.register_tick_callback.assert_called_once()
        mock_streamer.start_stream.assert_called_once_with(["EUR_USD", "GBP_USD"])
        mock_streamer.process_stream.assert_called_once()

    def test_start_stream_account_not_found(self):
        """Test starting stream for non-existent account"""
        result = start_market_data_stream(99999, ["EUR_USD"])

        assert result["success"] is False
        assert "does not exist" in result["error"]
        assert result["account_id"] is None

    def test_start_stream_inactive_account(self, mock_oanda_account):
        """Test starting stream for inactive account"""
        mock_oanda_account.is_active = False
        mock_oanda_account.save()

        result = start_market_data_stream(mock_oanda_account.id, ["EUR_USD"])

        assert result["success"] is False
        assert "not active" in result["error"]
        assert result["account_id"] == "001-001-1234567-001"

    @patch("trading.tasks.MarketDataStreamer")
    def test_start_stream_already_running(self, mock_streamer_class, mock_oanda_account):
        """Test starting stream when one is already running"""
        # Set cache to indicate stream is running
        cache_key = f"{STREAM_CACHE_PREFIX}{mock_oanda_account.id}"
        cache.set(cache_key, True, timeout=3600)

        result = start_market_data_stream(mock_oanda_account.id, ["EUR_USD"])

        assert result["success"] is True
        assert "already running" in result["message"]
        # Streamer should not be created
        mock_streamer_class.assert_not_called()

    @patch("trading.tasks.MarketDataStreamer")
    def test_start_stream_connection_error(self, mock_streamer_class, mock_oanda_account):
        """Test handling connection errors"""
        # Setup mock streamer to raise error
        mock_streamer = MagicMock()
        mock_streamer_class.return_value = mock_streamer
        mock_streamer.initialize_connection.side_effect = Exception("Connection failed")

        result = start_market_data_stream(mock_oanda_account.id, ["EUR_USD"])

        assert result["success"] is False
        assert "Connection failed" in result["error"]

        # Verify cache was cleaned up
        cache_key = f"{STREAM_CACHE_PREFIX}{mock_oanda_account.id}"
        assert cache.get(cache_key) is None

    @patch("trading.tasks.MarketDataStreamer")
    def test_start_stream_sets_cache(self, mock_streamer_class, mock_oanda_account):
        """Test that starting stream sets cache entry"""
        # Setup mock streamer
        mock_streamer = MagicMock()
        mock_streamer_class.return_value = mock_streamer
        mock_streamer.process_stream.return_value = None

        # Start the stream
        start_market_data_stream(mock_oanda_account.id, ["EUR_USD"])

        # Verify cache was set
        cache_key = f"{STREAM_CACHE_PREFIX}{mock_oanda_account.id}"
        assert cache.get(cache_key) is True

    @patch("trading.tasks.MarketDataStreamer")
    def test_start_stream_reconnection_success(self, mock_streamer_class, mock_oanda_account):
        """Test successful reconnection after stream error"""
        # Setup mock streamer
        mock_streamer = MagicMock()
        mock_streamer_class.return_value = mock_streamer

        # First process_stream fails, reconnect succeeds
        mock_streamer.process_stream.side_effect = [
            Exception("Stream error"),
            None,  # Success after reconnection
        ]
        mock_streamer.reconnect.return_value = True

        result = start_market_data_stream(mock_oanda_account.id, ["EUR_USD"])

        # Verify reconnection was attempted
        mock_streamer.reconnect.assert_called_once()
        # process_stream should be called twice (initial + after reconnect)
        assert mock_streamer.process_stream.call_count == 2

        assert result["success"] is True

    @patch("trading.tasks.MarketDataStreamer")
    def test_start_stream_reconnection_failure(self, mock_streamer_class, mock_oanda_account):
        """Test failed reconnection after stream error"""
        # Setup mock streamer
        mock_streamer = MagicMock()
        mock_streamer_class.return_value = mock_streamer

        # process_stream fails, reconnect fails
        mock_streamer.process_stream.side_effect = Exception("Stream error")
        mock_streamer.reconnect.return_value = False

        result = start_market_data_stream(mock_oanda_account.id, ["EUR_USD"])

        # Verify reconnection was attempted
        mock_streamer.reconnect.assert_called_once()

        assert result["success"] is False
        assert "Stream error" in result["error"]

        # Verify cache was cleaned up
        cache_key = f"{STREAM_CACHE_PREFIX}{mock_oanda_account.id}"
        assert cache.get(cache_key) is None


@pytest.mark.django_db
class TestStopMarketDataStream:
    """Test stop_market_data_stream task"""

    def test_stop_stream_success(self, mock_oanda_account):
        """Test successfully stopping a market data stream"""
        # Set cache to indicate stream is running
        cache_key = f"{STREAM_CACHE_PREFIX}{mock_oanda_account.id}"
        cache.set(cache_key, True, timeout=3600)

        result = stop_market_data_stream(mock_oanda_account.id)

        assert result["success"] is True
        assert result["account_id"] == "001-001-1234567-001"
        assert result["error"] is None

        # Verify cache was cleared
        assert cache.get(cache_key) is None

    def test_stop_stream_account_not_found(self):
        """Test stopping stream for non-existent account"""
        result = stop_market_data_stream(99999)

        assert result["success"] is False
        assert "does not exist" in result["error"]
        assert result["account_id"] is None

    def test_stop_stream_not_running(self, mock_oanda_account):
        """Test stopping stream when none is running"""
        result = stop_market_data_stream(mock_oanda_account.id)

        assert result["success"] is True
        assert "No active stream" in result["message"]
        assert result["account_id"] == "001-001-1234567-001"


@pytest.mark.django_db
class TestGetStreamStatus:
    """Test get_stream_status task"""

    def test_get_status_stream_active(self, mock_oanda_account):
        """Test getting status when stream is active"""
        # Set cache to indicate stream is running
        cache_key = f"{STREAM_CACHE_PREFIX}{mock_oanda_account.id}"
        cache.set(cache_key, True, timeout=3600)

        result = get_stream_status(mock_oanda_account.id)

        assert result["is_active"] is True
        assert result["account_id"] == "001-001-1234567-001"
        assert result["error"] is None

    def test_get_status_stream_inactive(self, mock_oanda_account):
        """Test getting status when stream is not active"""
        result = get_stream_status(mock_oanda_account.id)

        assert result["is_active"] is False
        assert result["account_id"] == "001-001-1234567-001"
        assert result["error"] is None

    def test_get_status_account_not_found(self):
        """Test getting status for non-existent account"""
        result = get_stream_status(99999)

        assert result["is_active"] is False
        assert "does not exist" in result["error"]
        assert result["account_id"] is None


@pytest.mark.django_db
class TestTickDataStorage:
    """Test tick data storage functionality in market data streaming"""

    @patch("trading.tasks.get_config")
    @patch("trading.tasks.MarketDataStreamer")
    def test_tick_storage_enabled(self, mock_streamer_class, mock_get_config, mock_oanda_account):
        """Test that tick storage is enabled when configured"""

        # Configure tick storage as enabled
        def config_side_effect(key, default=None):
            config_map = {
                "tick_storage.enabled": True,
                "tick_storage.batch_size": 100,
                "tick_storage.batch_timeout": 1.0,
            }
            return config_map.get(key, default)

        mock_get_config.side_effect = config_side_effect

        # Setup mock streamer
        mock_streamer = MagicMock()
        mock_streamer_class.return_value = mock_streamer
        mock_streamer.process_stream.return_value = None

        # Start the stream
        result = start_market_data_stream(mock_oanda_account.id, ["EUR_USD"])

        # Verify tick storage is enabled in result
        assert result["success"] is True
        assert result["tick_storage_enabled"] is True
        assert result["tick_storage_stats"] is not None

    @patch("trading.tasks.get_config")
    @patch("trading.tasks.MarketDataStreamer")
    def test_tick_storage_disabled(self, mock_streamer_class, mock_get_config, mock_oanda_account):
        """Test that tick storage is disabled when configured"""

        # Configure tick storage as disabled
        def config_side_effect(key, default=None):
            config_map = {
                "tick_storage.enabled": False,
                "tick_storage.batch_size": 100,
                "tick_storage.batch_timeout": 1.0,
            }
            return config_map.get(key, default)

        mock_get_config.side_effect = config_side_effect

        # Setup mock streamer
        mock_streamer = MagicMock()
        mock_streamer_class.return_value = mock_streamer
        mock_streamer.process_stream.return_value = None

        # Start the stream
        result = start_market_data_stream(mock_oanda_account.id, ["EUR_USD"])

        # Verify tick storage is disabled in result
        assert result["success"] is True
        assert result["tick_storage_enabled"] is False

    @patch("trading.tasks.get_config")
    @patch("trading.tasks.MarketDataStreamer")
    @patch("trading.tasks.TickDataBuffer")
    def test_tick_buffer_initialization(
        self, mock_buffer_class, mock_streamer_class, mock_get_config, mock_oanda_account
    ):
        """Test that TickDataBuffer is initialized with correct parameters"""

        # Configure tick storage
        def config_side_effect(key, default=None):
            config_map = {
                "tick_storage.enabled": True,
                "tick_storage.batch_size": 50,
                "tick_storage.batch_timeout": 2.0,
            }
            return config_map.get(key, default)

        mock_get_config.side_effect = config_side_effect

        # Setup mocks
        mock_streamer = MagicMock()
        mock_streamer_class.return_value = mock_streamer
        mock_streamer.process_stream.return_value = None

        mock_buffer = MagicMock()
        mock_buffer.get_stats.return_value = {
            "buffer_size": 0,
            "total_stored": 0,
            "total_errors": 0,
        }
        mock_buffer_class.return_value = mock_buffer

        # Start the stream
        start_market_data_stream(mock_oanda_account.id, ["EUR_USD"])

        # Verify buffer was initialized with correct parameters
        mock_buffer_class.assert_called_once_with(
            account=mock_oanda_account, batch_size=50, batch_timeout=2.0
        )

    @patch("trading.tasks.get_config")
    @patch("trading.tasks.MarketDataStreamer")
    @patch("trading.tasks.TickDataBuffer")
    def test_tick_buffer_flush_on_error(
        self, mock_buffer_class, mock_streamer_class, mock_get_config, mock_oanda_account
    ):
        """Test that tick buffer is flushed when stream encounters an error"""

        # Configure tick storage
        def config_side_effect(key, default=None):
            config_map = {
                "tick_storage.enabled": True,
                "tick_storage.batch_size": 100,
                "tick_storage.batch_timeout": 1.0,
            }
            return config_map.get(key, default)

        mock_get_config.side_effect = config_side_effect

        # Setup mocks
        mock_streamer = MagicMock()
        mock_streamer_class.return_value = mock_streamer
        mock_streamer.process_stream.side_effect = Exception("Stream error")
        mock_streamer.reconnect.return_value = False

        mock_buffer = MagicMock()
        mock_buffer.get_stats.return_value = {
            "buffer_size": 0,
            "total_stored": 10,
            "total_errors": 0,
        }
        mock_buffer_class.return_value = mock_buffer

        # Start the stream (will fail)
        result = start_market_data_stream(mock_oanda_account.id, ["EUR_USD"])

        # Verify buffer was flushed before cleanup
        assert mock_buffer.flush.call_count >= 1
        assert result["success"] is False
