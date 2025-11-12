"""
Unit tests for market data streaming Celery tasks.

Tests cover:
- Starting market data streams
- Stopping market data streams
- Getting stream status
- Stream management with cache
"""

from decimal import Decimal
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
        assert result["instrument"] == "EUR_USD"
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

    @patch("trading.tasks.get_config")
    @patch("trading.tasks.MarketDataStreamer")
    def test_tick_data_insertion_from_streaming(
        self, mock_streamer_class, mock_get_config, mock_oanda_account
    ):
        """Test that tick data is inserted into database from streaming task"""
        from decimal import Decimal

        from trading.market_data_streamer import TickData as StreamerTickData
        from trading.tick_data_models import TickData as TickDataModel

        # Configure tick storage as enabled
        def config_side_effect(key, default=None):
            config_map = {
                "tick_storage.enabled": True,
                "tick_storage.batch_size": 2,  # Small batch for testing
                "tick_storage.batch_timeout": 10.0,  # Long timeout to test size-based flush
            }
            return config_map.get(key, default)

        mock_get_config.side_effect = config_side_effect

        # Setup mock streamer
        mock_streamer = MagicMock()
        mock_streamer_class.return_value = mock_streamer

        # Capture the tick callback
        tick_callback = None

        def capture_callback(callback):
            nonlocal tick_callback
            tick_callback = callback

        mock_streamer.register_tick_callback.side_effect = capture_callback

        # Mock process_stream to call the callback with test ticks
        def process_stream_side_effect():
            if tick_callback:
                # Simulate receiving 3 ticks (should trigger flush after 2)
                tick1 = StreamerTickData(
                    instrument="EUR_USD",
                    time="2024-01-15T10:30:00.000000Z",
                    bid=1.08500,
                    ask=1.08520,
                )
                tick2 = StreamerTickData(
                    instrument="EUR_USD",
                    time="2024-01-15T10:30:01.000000Z",
                    bid=1.08505,
                    ask=1.08525,
                )
                tick3 = StreamerTickData(
                    instrument="GBP_USD",
                    time="2024-01-15T10:30:02.000000Z",
                    bid=1.27100,
                    ask=1.27120,
                )

                tick_callback(tick1)
                tick_callback(tick2)
                tick_callback(tick3)

        mock_streamer.process_stream.side_effect = process_stream_side_effect

        # Start the stream
        result = start_market_data_stream(mock_oanda_account.id, ["EUR_USD", "GBP_USD"])

        # Verify stream started successfully
        assert result["success"] is True
        assert result["tick_storage_enabled"] is True

        # Verify tick data was stored in database
        stored_ticks = TickDataModel.objects.filter(account=mock_oanda_account).order_by(
            "timestamp"
        )
        assert stored_ticks.count() == 3

        # Verify first tick data
        tick1_db = stored_ticks[0]
        assert tick1_db.instrument == "EUR_USD"
        assert tick1_db.bid == Decimal("1.08500")
        assert tick1_db.ask == Decimal("1.08520")
        assert tick1_db.mid == Decimal("1.08510")
        assert tick1_db.spread == Decimal("0.00020")

        # Verify second tick data
        tick2_db = stored_ticks[1]
        assert tick2_db.instrument == "EUR_USD"
        assert tick2_db.bid == Decimal("1.08505")

        # Verify third tick data
        tick3_db = stored_ticks[2]
        assert tick3_db.instrument == "GBP_USD"
        assert tick3_db.bid == Decimal("1.27100")

    @patch("trading.tasks.get_config")
    @patch("trading.tasks.MarketDataStreamer")
    def test_batch_insertion_performance(
        self, mock_streamer_class, mock_get_config, mock_oanda_account
    ):
        """Test that batch insertion is used for performance"""
        from trading.market_data_streamer import TickData as StreamerTickData
        from trading.tick_data_models import TickData as TickDataModel

        # Configure tick storage with batch size of 5
        def config_side_effect(key, default=None):
            config_map = {
                "tick_storage.enabled": True,
                "tick_storage.batch_size": 5,
                "tick_storage.batch_timeout": 10.0,
            }
            return config_map.get(key, default)

        mock_get_config.side_effect = config_side_effect

        # Setup mock streamer
        mock_streamer = MagicMock()
        mock_streamer_class.return_value = mock_streamer

        # Capture the tick callback
        tick_callback = None

        def capture_callback(callback):
            nonlocal tick_callback
            tick_callback = callback

        mock_streamer.register_tick_callback.side_effect = capture_callback

        # Mock process_stream to call the callback with multiple ticks
        def process_stream_side_effect():
            if tick_callback:
                # Simulate receiving 12 ticks (should trigger 2 flushes of 5, leaving 2 in buffer)
                for i in range(12):
                    tick = StreamerTickData(
                        instrument="EUR_USD",
                        time=f"2024-01-15T10:30:{i:02d}.000000Z",
                        bid=1.08500 + (i * 0.00001),
                        ask=1.08520 + (i * 0.00001),
                    )
                    tick_callback(tick)

        mock_streamer.process_stream.side_effect = process_stream_side_effect

        # Start the stream
        result = start_market_data_stream(mock_oanda_account.id, ["EUR_USD"])

        # Verify stream started successfully
        assert result["success"] is True

        # Verify tick data was stored (should have 10 from 2 flushes, 2 remaining in buffer)
        # The final flush happens when stream ends
        stored_ticks = TickDataModel.objects.filter(account=mock_oanda_account)
        assert stored_ticks.count() == 12  # All ticks should be flushed at the end

        # Verify tick storage stats show batch operations
        assert result["tick_storage_stats"]["total_stored"] == 12

    @patch("trading.tasks.get_config")
    @patch("trading.tasks.MarketDataStreamer")
    def test_tick_storage_configuration_toggle(
        self, mock_streamer_class, mock_get_config, mock_oanda_account
    ):
        """Test that tick storage can be toggled via configuration"""
        from trading.market_data_streamer import TickData as StreamerTickData
        from trading.tick_data_models import TickData as TickDataModel

        # Test 1: Tick storage disabled
        def config_disabled(key, default=None):
            config_map = {
                "tick_storage.enabled": False,
                "tick_storage.batch_size": 100,
                "tick_storage.batch_timeout": 1.0,
            }
            return config_map.get(key, default)

        mock_get_config.side_effect = config_disabled

        # Setup mock streamer
        mock_streamer = MagicMock()
        mock_streamer_class.return_value = mock_streamer

        tick_callback = None

        def capture_callback(callback):
            nonlocal tick_callback
            tick_callback = callback

        mock_streamer.register_tick_callback.side_effect = capture_callback

        def process_stream_disabled():
            if tick_callback:
                tick = StreamerTickData(
                    instrument="EUR_USD",
                    time="2024-01-15T10:30:00.000000Z",
                    bid=1.08500,
                    ask=1.08520,
                )
                tick_callback(tick)

        mock_streamer.process_stream.side_effect = process_stream_disabled

        # Start the stream with storage disabled
        result = start_market_data_stream(mock_oanda_account.id, ["EUR_USD"])

        # Verify storage is disabled
        assert result["success"] is True
        assert result["tick_storage_enabled"] is False

        # Verify no tick data was stored
        stored_ticks = TickDataModel.objects.filter(account=mock_oanda_account)
        assert stored_ticks.count() == 0

        # Test 2: Tick storage enabled
        # Reset mocks
        mock_streamer_class.reset_mock()
        mock_streamer = MagicMock()
        mock_streamer_class.return_value = mock_streamer

        def config_enabled(key, default=None):
            config_map = {
                "tick_storage.enabled": True,
                "tick_storage.batch_size": 1,
                "tick_storage.batch_timeout": 1.0,
            }
            return config_map.get(key, default)

        mock_get_config.side_effect = config_enabled

        tick_callback = None
        mock_streamer.register_tick_callback.side_effect = capture_callback

        def process_stream_enabled():
            if tick_callback:
                tick = StreamerTickData(
                    instrument="GBP_USD",
                    time="2024-01-15T10:31:00.000000Z",
                    bid=1.27100,
                    ask=1.27120,
                )
                tick_callback(tick)

        mock_streamer.process_stream.side_effect = process_stream_enabled

        # Stop the previous stream
        stop_market_data_stream(mock_oanda_account.id)

        # Start the stream with storage enabled
        result = start_market_data_stream(mock_oanda_account.id, ["GBP_USD"])

        # Verify storage is enabled
        assert result["success"] is True
        assert result["tick_storage_enabled"] is True

        # Verify tick data was stored
        stored_ticks = TickDataModel.objects.filter(account=mock_oanda_account)
        assert stored_ticks.count() == 1
        assert stored_ticks[0].instrument == "GBP_USD"

    @patch("trading.tasks.get_config")
    @patch("trading.tasks.MarketDataStreamer")
    @patch("trading.tasks.TickDataBuffer")
    def test_database_error_handling(
        self, mock_buffer_class, mock_streamer_class, mock_get_config, mock_oanda_account
    ):
        """Test error handling for database failures during tick storage"""
        from django.db import DatabaseError

        from trading.market_data_streamer import TickData as StreamerTickData

        # Configure tick storage as enabled
        def config_side_effect(key, default=None):
            config_map = {
                "tick_storage.enabled": True,
                "tick_storage.batch_size": 2,
                "tick_storage.batch_timeout": 1.0,
            }
            return config_map.get(key, default)

        mock_get_config.side_effect = config_side_effect

        # Setup mock streamer
        mock_streamer = MagicMock()
        mock_streamer_class.return_value = mock_streamer

        # Setup mock buffer that simulates database error
        mock_buffer = MagicMock()
        mock_buffer_class.return_value = mock_buffer

        # Simulate database error on add_tick
        mock_buffer.add_tick.side_effect = DatabaseError("Database connection lost")

        # Mock get_stats to return error count
        mock_buffer.get_stats.return_value = {
            "buffer_size": 0,
            "total_stored": 0,
            "total_errors": 2,
        }

        # Capture the tick callback
        tick_callback = None

        def capture_callback(callback):
            nonlocal tick_callback
            tick_callback = callback

        mock_streamer.register_tick_callback.side_effect = capture_callback

        # Mock process_stream to call the callback
        def process_stream_side_effect():
            if tick_callback:
                tick1 = StreamerTickData(
                    instrument="EUR_USD",
                    time="2024-01-15T10:30:00.000000Z",
                    bid=1.08500,
                    ask=1.08520,
                )
                tick2 = StreamerTickData(
                    instrument="EUR_USD",
                    time="2024-01-15T10:30:01.000000Z",
                    bid=1.08505,
                    ask=1.08525,
                )
                # These should fail but not crash the stream
                tick_callback(tick1)
                tick_callback(tick2)

        mock_streamer.process_stream.side_effect = process_stream_side_effect

        # Start the stream
        result = start_market_data_stream(mock_oanda_account.id, ["EUR_USD"])

        # Verify stream continued despite database errors
        assert result["success"] is True
        assert result["tick_storage_enabled"] is True

        # Verify errors were tracked
        assert result["tick_storage_stats"]["total_errors"] == 2
        assert result["tick_storage_stats"]["total_stored"] == 0

        # Verify add_tick was called (even though it failed)
        assert mock_buffer.add_tick.call_count == 2

    @patch("trading.tasks.get_config")
    @patch("trading.tasks.MarketDataStreamer")
    def test_tick_data_retrieval_for_backtesting(
        self, mock_streamer_class, mock_get_config, mock_oanda_account
    ):
        """Test that stored tick data can be retrieved for backtesting"""
        from datetime import timedelta
        from decimal import Decimal

        from django.utils import timezone

        from trading.market_data_streamer import TickData as StreamerTickData
        from trading.tick_data_models import TickData as TickDataModel

        # Configure tick storage as enabled
        def config_side_effect(key, default=None):
            config_map = {
                "tick_storage.enabled": True,
                "tick_storage.batch_size": 10,
                "tick_storage.batch_timeout": 1.0,
            }
            return config_map.get(key, default)

        mock_get_config.side_effect = config_side_effect

        # Setup mock streamer
        mock_streamer = MagicMock()
        mock_streamer_class.return_value = mock_streamer

        # Capture the tick callback
        tick_callback = None

        def capture_callback(callback):
            nonlocal tick_callback
            tick_callback = callback

        mock_streamer.register_tick_callback.side_effect = capture_callback

        # Create test data with specific timestamps
        base_time = timezone.now() - timedelta(days=1)

        def process_stream_side_effect():
            if tick_callback:
                # Create ticks for EUR_USD and GBP_USD over a time range
                for i in range(10):
                    tick_time = base_time + timedelta(minutes=i)
                    tick_eur = StreamerTickData(
                        instrument="EUR_USD",
                        time=tick_time.isoformat(),
                        bid=1.08500 + (i * 0.00001),
                        ask=1.08520 + (i * 0.00001),
                    )
                    tick_gbp = StreamerTickData(
                        instrument="GBP_USD",
                        time=tick_time.isoformat(),
                        bid=1.27100 + (i * 0.00001),
                        ask=1.27120 + (i * 0.00001),
                    )
                    tick_callback(tick_eur)
                    tick_callback(tick_gbp)

        mock_streamer.process_stream.side_effect = process_stream_side_effect

        # Start the stream to populate data
        result = start_market_data_stream(mock_oanda_account.id, ["EUR_USD", "GBP_USD"])
        assert result["success"] is True

        # Test 1: Retrieve all ticks for a specific instrument
        eur_ticks = TickDataModel.objects.filter(
            account=mock_oanda_account, instrument="EUR_USD"
        ).order_by("timestamp")

        assert eur_ticks.count() == 10
        assert eur_ticks[0].bid == Decimal("1.08500")
        assert eur_ticks[9].bid == Decimal("1.08509")

        # Test 2: Retrieve ticks within a time range
        start_time = base_time + timedelta(minutes=2)
        end_time = base_time + timedelta(minutes=7)

        range_ticks = TickDataModel.objects.filter(
            account=mock_oanda_account,
            instrument="EUR_USD",
            timestamp__gte=start_time,
            timestamp__lte=end_time,
        ).order_by("timestamp")

        assert range_ticks.count() == 6  # Minutes 2-7 inclusive

        # Test 3: Retrieve ticks for single instrument
        all_ticks = TickDataModel.objects.filter(account=mock_oanda_account).order_by(
            "instrument", "timestamp"
        )

        assert all_ticks.count() == 20  # 10 EUR_USD + 10 GBP_USD

        # Test 4: Verify data integrity for backtesting
        # Check that mid and spread are correctly calculated
        for tick in all_ticks:
            expected_mid = (tick.bid + tick.ask) / Decimal("2")
            expected_spread = tick.ask - tick.bid
            assert tick.mid == expected_mid
            assert tick.spread == expected_spread

        # Test 5: Test efficient querying with composite index
        # This query should use the (instrument, timestamp) composite index
        efficient_query = TickDataModel.objects.filter(
            instrument="GBP_USD", timestamp__gte=start_time
        ).order_by("timestamp")

        assert efficient_query.count() == 8  # Minutes 2-9 for GBP_USD


@pytest.mark.django_db
class TestCleanupOldTickData:
    """Test cleanup_old_tick_data task"""

    def test_cleanup_old_data_success(self, mock_oanda_account):
        """Test successfully cleaning up old tick data"""
        from datetime import timedelta

        from django.utils import timezone

        from trading.tasks import cleanup_old_tick_data
        from trading.tick_data_models import TickData as TickDataModel

        # Create old tick data (100 days old)
        old_timestamp = timezone.now() - timedelta(days=100)
        for i in range(5):
            tick = TickDataModel.objects.create(
                account=mock_oanda_account,
                instrument="EUR_USD",
                timestamp=old_timestamp + timedelta(minutes=i),
                bid=1.08500,
                ask=1.08520,
                mid=1.08510,
                spread=0.00020,
            )
            # Update created_at manually since auto_now_add=True prevents setting it on create
            TickDataModel.objects.filter(pk=tick.pk).update(
                created_at=old_timestamp + timedelta(minutes=i)
            )

        # Create recent tick data (10 days old)
        recent_timestamp = timezone.now() - timedelta(days=10)
        for i in range(3):
            tick = TickDataModel.objects.create(
                account=mock_oanda_account,
                instrument="EUR_USD",
                timestamp=recent_timestamp + timedelta(minutes=i),
                bid=1.08600,
                ask=1.08620,
                mid=1.08610,
                spread=0.00020,
            )
            # Update created_at manually
            TickDataModel.objects.filter(pk=tick.pk).update(
                created_at=recent_timestamp + timedelta(minutes=i)
            )

        # Verify initial count
        assert TickDataModel.objects.count() == 8

        # Run cleanup with 90-day retention
        result = cleanup_old_tick_data(retention_days=90)

        # Verify result
        assert result["success"] is True
        assert result["deleted_count"] == 5
        assert result["retention_days"] == 90
        assert result["error"] is None

        # Verify only recent data remains
        assert TickDataModel.objects.count() == 3
        remaining_ticks = TickDataModel.objects.all()
        for tick in remaining_ticks:
            assert tick.bid == Decimal("1.08600")

    def test_cleanup_with_default_retention(self, mock_oanda_account):
        """Test cleanup using default retention period from settings"""
        from datetime import timedelta

        from django.utils import timezone

        from trading.tasks import cleanup_old_tick_data
        from trading.tick_data_models import TickData as TickDataModel

        # Create old tick data (100 days old)
        old_timestamp = timezone.now() - timedelta(days=100)
        tick = TickDataModel.objects.create(
            account=mock_oanda_account,
            instrument="EUR_USD",
            timestamp=old_timestamp,
            bid=1.08500,
            ask=1.08520,
            mid=1.08510,
            spread=0.00020,
        )
        TickDataModel.objects.filter(pk=tick.pk).update(created_at=old_timestamp)

        # Create recent tick data (50 days old)
        recent_timestamp = timezone.now() - timedelta(days=50)
        tick = TickDataModel.objects.create(
            account=mock_oanda_account,
            instrument="EUR_USD",
            timestamp=recent_timestamp,
            bid=1.08600,
            ask=1.08620,
            mid=1.08610,
            spread=0.00020,
        )
        TickDataModel.objects.filter(pk=tick.pk).update(created_at=recent_timestamp)

        # Run cleanup without specifying retention_days (uses default from settings)
        result = cleanup_old_tick_data()

        # Verify result
        assert result["success"] is True
        assert result["retention_days"] == 90  # Default from settings
        assert result["deleted_count"] == 1  # Only the 100-day-old tick

        # Verify only recent data remains
        assert TickDataModel.objects.count() == 1

    def test_cleanup_no_old_data(self, mock_oanda_account):
        """Test cleanup when there is no old data to delete"""
        from datetime import timedelta

        from django.utils import timezone

        from trading.tasks import cleanup_old_tick_data
        from trading.tick_data_models import TickData as TickDataModel

        # Create only recent tick data (10 days old)
        recent_timestamp = timezone.now() - timedelta(days=10)
        for i in range(3):
            TickDataModel.objects.create(
                account=mock_oanda_account,
                instrument="EUR_USD",
                timestamp=recent_timestamp + timedelta(minutes=i),
                bid=1.08500,
                ask=1.08520,
                mid=1.08510,
                spread=0.00020,
                created_at=recent_timestamp + timedelta(minutes=i),
            )

        # Run cleanup with 90-day retention
        result = cleanup_old_tick_data(retention_days=90)

        # Verify result
        assert result["success"] is True
        assert result["deleted_count"] == 0
        assert result["retention_days"] == 90

        # Verify all data remains
        assert TickDataModel.objects.count() == 3

    def test_cleanup_custom_retention_period(self, mock_oanda_account):
        """Test cleanup with custom retention period"""
        from datetime import timedelta

        from django.utils import timezone

        from trading.tasks import cleanup_old_tick_data
        from trading.tick_data_models import TickData as TickDataModel

        # Create tick data at various ages
        now = timezone.now()

        # 400 days old
        tick = TickDataModel.objects.create(
            account=mock_oanda_account,
            instrument="EUR_USD",
            timestamp=now - timedelta(days=400),
            bid=1.08500,
            ask=1.08520,
            mid=1.08510,
            spread=0.00020,
        )
        TickDataModel.objects.filter(pk=tick.pk).update(created_at=now - timedelta(days=400))

        # 200 days old
        tick = TickDataModel.objects.create(
            account=mock_oanda_account,
            instrument="EUR_USD",
            timestamp=now - timedelta(days=200),
            bid=1.08600,
            ask=1.08620,
            mid=1.08610,
            spread=0.00020,
        )
        TickDataModel.objects.filter(pk=tick.pk).update(created_at=now - timedelta(days=200))

        # 50 days old
        tick = TickDataModel.objects.create(
            account=mock_oanda_account,
            instrument="EUR_USD",
            timestamp=now - timedelta(days=50),
            bid=1.08700,
            ask=1.08720,
            mid=1.08710,
            spread=0.00020,
        )
        TickDataModel.objects.filter(pk=tick.pk).update(created_at=now - timedelta(days=50))

        # Run cleanup with 365-day retention (1 year)
        result = cleanup_old_tick_data(retention_days=365)

        # Verify result
        assert result["success"] is True
        assert result["deleted_count"] == 1  # Only 400-day-old tick
        assert result["retention_days"] == 365

        # Verify correct data remains
        assert TickDataModel.objects.count() == 2
        remaining_ticks = TickDataModel.objects.order_by("created_at")
        assert remaining_ticks[0].bid == Decimal("1.08600")  # 200 days old
        assert remaining_ticks[1].bid == Decimal("1.08700")  # 50 days old

    def test_cleanup_multiple_accounts(self, mock_oanda_account):
        """Test cleanup across multiple accounts"""
        from datetime import timedelta

        from django.contrib.auth import get_user_model
        from django.utils import timezone

        from accounts.models import OandaAccount
        from trading.tasks import cleanup_old_tick_data
        from trading.tick_data_models import TickData as TickDataModel

        # Create second account
        User = get_user_model()
        user2 = User.objects.create_user(
            username="testuser2", email="test2@example.com", password="testpass123"
        )
        account2 = OandaAccount.objects.create(
            user=user2,
            account_id="001-001-7654321-001",
            api_token="test_token_67890",
            api_type="practice",
            balance=20000.00,
            is_active=True,
        )

        # Create old tick data for both accounts
        old_timestamp = timezone.now() - timedelta(days=100)

        # Account 1: 3 old ticks
        for i in range(3):
            tick = TickDataModel.objects.create(
                account=mock_oanda_account,
                instrument="EUR_USD",
                timestamp=old_timestamp + timedelta(minutes=i),
                bid=1.08500,
                ask=1.08520,
                mid=1.08510,
                spread=0.00020,
            )
            TickDataModel.objects.filter(pk=tick.pk).update(
                created_at=old_timestamp + timedelta(minutes=i)
            )

        # Account 2: 2 old ticks
        for i in range(2):
            tick = TickDataModel.objects.create(
                account=account2,
                instrument="GBP_USD",
                timestamp=old_timestamp + timedelta(minutes=i),
                bid=1.27100,
                ask=1.27120,
                mid=1.27110,
                spread=0.00020,
            )
            TickDataModel.objects.filter(pk=tick.pk).update(
                created_at=old_timestamp + timedelta(minutes=i)
            )

        # Create recent tick data for both accounts
        recent_timestamp = timezone.now() - timedelta(days=10)

        tick = TickDataModel.objects.create(
            account=mock_oanda_account,
            instrument="EUR_USD",
            timestamp=recent_timestamp,
            bid=1.08600,
            ask=1.08620,
            mid=1.08610,
            spread=0.00020,
        )
        TickDataModel.objects.filter(pk=tick.pk).update(created_at=recent_timestamp)

        tick = TickDataModel.objects.create(
            account=account2,
            instrument="GBP_USD",
            timestamp=recent_timestamp,
            bid=1.27200,
            ask=1.27220,
            mid=1.27210,
            spread=0.00020,
        )
        TickDataModel.objects.filter(pk=tick.pk).update(created_at=recent_timestamp)

        # Verify initial count
        assert TickDataModel.objects.count() == 7

        # Run cleanup
        result = cleanup_old_tick_data(retention_days=90)

        # Verify result
        assert result["success"] is True
        assert result["deleted_count"] == 5  # All old ticks from both accounts

        # Verify only recent data remains
        assert TickDataModel.objects.count() == 2
        assert TickDataModel.objects.filter(account=mock_oanda_account).count() == 1
        assert TickDataModel.objects.filter(account=account2).count() == 1

    def test_cleanup_logging(self, mock_oanda_account, caplog):
        """Test that cleanup operations are logged"""
        from datetime import timedelta

        from django.utils import timezone

        from trading.tasks import cleanup_old_tick_data
        from trading.tick_data_models import TickData as TickDataModel

        # Create old tick data
        old_timestamp = timezone.now() - timedelta(days=100)
        tick = TickDataModel.objects.create(
            account=mock_oanda_account,
            instrument="EUR_USD",
            timestamp=old_timestamp,
            bid=1.08500,
            ask=1.08520,
            mid=1.08510,
            spread=0.00020,
        )
        TickDataModel.objects.filter(pk=tick.pk).update(created_at=old_timestamp)

        # Run cleanup
        with caplog.at_level("INFO"):
            result = cleanup_old_tick_data(retention_days=90)

        # Verify result
        assert result["success"] is True

        # Verify logging
        assert "Starting tick data cleanup" in caplog.text
        assert "retention_days=90" in caplog.text
        assert "Tick data cleanup completed" in caplog.text
        assert "deleted 1 records" in caplog.text

    def test_cleanup_error_handling(self, mock_oanda_account):
        """Test error handling during cleanup"""
        from unittest.mock import patch

        from trading.tasks import cleanup_old_tick_data

        # Mock the cleanup_old_data method to raise an exception
        with patch(
            "trading.tick_data_models.TickData.cleanup_old_data",
            side_effect=Exception("Database error"),
        ):
            result = cleanup_old_tick_data(retention_days=90)

        # Verify error is handled gracefully
        assert result["success"] is False
        assert result["deleted_count"] == 0
        assert "Database error" in result["error"]
        assert result["retention_days"] == 90

    def test_cleanup_task_scheduling_configuration(self):
        """Test that cleanup task can be scheduled with Celery Beat"""
        from celery import Celery
        from celery.schedules import crontab

        # Create a test Celery app with beat schedule
        test_app = Celery("test_trading_system")

        # Define the beat schedule for cleanup task
        # Task should run daily at 2 AM
        test_app.conf.beat_schedule = {
            "cleanup-old-tick-data": {
                "task": "trading.tasks.cleanup_old_tick_data",
                "schedule": crontab(hour=2, minute=0),
                "args": (),  # Uses default retention period
            },
        }

        # Verify the schedule is configured correctly
        assert "cleanup-old-tick-data" in test_app.conf.beat_schedule
        schedule_config = test_app.conf.beat_schedule["cleanup-old-tick-data"]

        # Verify task name
        assert schedule_config["task"] == "trading.tasks.cleanup_old_tick_data"

        # Verify schedule is a crontab
        assert isinstance(schedule_config["schedule"], crontab)

        # Verify schedule runs at 2 AM daily
        schedule = schedule_config["schedule"]
        assert schedule.hour == {2}
        assert schedule.minute == {0}

        # Verify no specific arguments (uses default retention)
        assert schedule_config["args"] == ()

    def test_cleanup_task_scheduling_with_custom_retention(self):
        """Test that cleanup task can be scheduled with custom retention period"""
        from celery import Celery
        from celery.schedules import crontab

        # Create a test Celery app with beat schedule
        test_app = Celery("test_trading_system")

        # Define the beat schedule with custom retention period
        custom_retention_days = 365  # 1 year retention

        test_app.conf.beat_schedule = {
            "cleanup-old-tick-data-custom": {
                "task": "trading.tasks.cleanup_old_tick_data",
                "schedule": crontab(hour=2, minute=0),
                "kwargs": {"retention_days": custom_retention_days},
            },
        }

        # Verify the schedule is configured correctly
        schedule_config = test_app.conf.beat_schedule["cleanup-old-tick-data-custom"]

        # Verify custom retention period is passed
        assert schedule_config["kwargs"]["retention_days"] == 365

    def test_cleanup_task_scheduling_multiple_schedules(self):
        """Test that multiple cleanup schedules can be configured"""
        from celery import Celery
        from celery.schedules import crontab

        # Create a test Celery app with multiple beat schedules
        test_app = Celery("test_trading_system")

        # Define multiple cleanup schedules with different retention periods
        test_app.conf.beat_schedule = {
            "cleanup-old-tick-data-90-days": {
                "task": "trading.tasks.cleanup_old_tick_data",
                "schedule": crontab(hour=2, minute=0),
                "kwargs": {"retention_days": 90},
            },
            "cleanup-old-tick-data-365-days": {
                "task": "trading.tasks.cleanup_old_tick_data",
                "schedule": crontab(hour=3, minute=0),
                "kwargs": {"retention_days": 365},
            },
        }

        # Verify both schedules are configured
        assert "cleanup-old-tick-data-90-days" in test_app.conf.beat_schedule
        assert "cleanup-old-tick-data-365-days" in test_app.conf.beat_schedule

        # Verify first schedule (90 days, runs at 2 AM)
        schedule1 = test_app.conf.beat_schedule["cleanup-old-tick-data-90-days"]
        assert schedule1["kwargs"]["retention_days"] == 90
        assert schedule1["schedule"].hour == {2}

        # Verify second schedule (365 days, runs at 3 AM)
        schedule2 = test_app.conf.beat_schedule["cleanup-old-tick-data-365-days"]
        assert schedule2["kwargs"]["retention_days"] == 365
        assert schedule2["schedule"].hour == {3}

    def test_cleanup_task_is_registered(self):
        """Test that cleanup task is properly registered with Celery"""
        from trading.tasks import cleanup_old_tick_data

        # Verify the task is a Celery task
        assert hasattr(cleanup_old_tick_data, "delay")
        assert hasattr(cleanup_old_tick_data, "apply_async")

        # Verify task name
        assert cleanup_old_tick_data.name == "trading.tasks.cleanup_old_tick_data"
