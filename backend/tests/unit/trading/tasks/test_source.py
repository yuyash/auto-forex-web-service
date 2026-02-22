"""Unit tests for tick data source module."""

from __future__ import annotations

from unittest.mock import MagicMock


class TestRedisTickDataSourceInit:
    """Tests for RedisTickDataSource.__init__."""

    def test_init_stores_attributes(self):
        from apps.trading.tasks.source import RedisTickDataSource

        callback = MagicMock()
        source = RedisTickDataSource(
            channel="market:backtest:ticks:123",
            batch_size=50,
            trigger_publisher=callback,
        )

        assert source.channel == "market:backtest:ticks:123"
        assert source.batch_size == 50
        assert source.trigger_publisher is callback
        assert source.client is None
        assert source.pubsub is None

    def test_init_defaults(self):
        from apps.trading.tasks.source import RedisTickDataSource

        source = RedisTickDataSource(channel="test:channel")

        assert source.channel == "test:channel"
        assert source.batch_size == 100
        assert source.trigger_publisher is None


class TestRedisTickDataSourceClose:
    """Tests for RedisTickDataSource.close."""

    def test_close_cleans_up_pubsub_and_client(self):
        from apps.trading.tasks.source import RedisTickDataSource

        source = RedisTickDataSource(channel="test:channel")
        source.pubsub = MagicMock()
        source.client = MagicMock()

        source.close()

        source.pubsub.close.assert_called_once()
        source.client.close.assert_called_once()

    def test_close_handles_none_gracefully(self):
        from apps.trading.tasks.source import RedisTickDataSource

        source = RedisTickDataSource(channel="test:channel")
        source.pubsub = None
        source.client = None

        # Should not raise
        source.close()

    def test_close_handles_pubsub_exception(self):
        from apps.trading.tasks.source import RedisTickDataSource

        source = RedisTickDataSource(channel="test:channel")
        source.pubsub = MagicMock()
        source.pubsub.close.side_effect = Exception("pubsub error")
        source.client = MagicMock()

        # Should not raise, just log
        source.close()
        source.client.close.assert_called_once()

    def test_close_handles_client_exception(self):
        from apps.trading.tasks.source import RedisTickDataSource

        source = RedisTickDataSource(channel="test:channel")
        source.pubsub = MagicMock()
        source.client = MagicMock()
        source.client.close.side_effect = Exception("client error")

        # Should not raise
        source.close()


class TestLiveTickDataSourceInit:
    """Tests for LiveTickDataSource.__init__."""

    def test_init_stores_channel_and_instrument(self):
        from apps.trading.tasks.source import LiveTickDataSource

        source = LiveTickDataSource(
            channel="live:001-001-123:EUR_USD",
            instrument="EUR_USD",
        )

        assert source.channel == "live:001-001-123:EUR_USD"
        assert source.instrument == "EUR_USD"
        assert source.client is None
        assert source.pubsub is None


class TestLiveTickDataSourceClose:
    """Tests for LiveTickDataSource.close."""

    def test_close_cleans_up_pubsub_and_client(self):
        from apps.trading.tasks.source import LiveTickDataSource

        source = LiveTickDataSource(channel="test:channel", instrument="EUR_USD")
        source.pubsub = MagicMock()
        source.client = MagicMock()

        source.close()

        source.pubsub.close.assert_called_once()
        source.client.close.assert_called_once()

    def test_close_handles_none_gracefully(self):
        from apps.trading.tasks.source import LiveTickDataSource

        source = LiveTickDataSource(channel="test:channel", instrument="EUR_USD")
        source.pubsub = None
        source.client = None

        # Should not raise
        source.close()

    def test_close_handles_pubsub_exception(self):
        from apps.trading.tasks.source import LiveTickDataSource

        source = LiveTickDataSource(channel="test:channel", instrument="EUR_USD")
        source.pubsub = MagicMock()
        source.pubsub.close.side_effect = Exception("pubsub error")
        source.client = MagicMock()

        # Should not raise
        source.close()
        source.client.close.assert_called_once()

    def test_close_handles_client_exception(self):
        from apps.trading.tasks.source import LiveTickDataSource

        source = LiveTickDataSource(channel="test:channel", instrument="EUR_USD")
        source.pubsub = MagicMock()
        source.client = MagicMock()
        source.client.close.side_effect = Exception("client error")

        # Should not raise
        source.close()
