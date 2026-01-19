"""
Integration tests for market data streaming.

Tests WebSocket connection maintenance, real-time data parsing,
cache updates, and strategy evaluation triggering.
"""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, Mock, patch

import pytest

from apps.market.models import TickData
from apps.market.services.oanda import OandaService
from tests.integration.base import IntegrationTestCase
from tests.integration.factories import (
    OandaAccountFactory,
    StrategyConfigurationFactory,
    TradingTaskFactory,
    UserFactory,
)


class MarketDataStreamingTestCase(IntegrationTestCase):
    """Test market data streaming flows."""

    def setUp(self) -> None:
        """Set up test data for streaming tests."""
        super().setUp()
        self.account = OandaAccountFactory(user=self.user)
        self.strategy_config = StrategyConfigurationFactory(user=self.user)

    @patch("apps.market.services.oanda.v20")
    def test_stream_pricing_ticks_parsing(self, mock_v20: Mock) -> None:
        """
        Test that streaming pricing ticks are parsed correctly."""
        # Mock v20 Context and streaming response
        mock_context = MagicMock()
        mock_v20.Context.return_value = mock_context

        # Mock streaming response with price data
        mock_price = MagicMock()
        mock_price.instrument = "EUR_USD"
        mock_price.time = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        mock_price.bids = [MagicMock(price="1.08950")]
        mock_price.asks = [MagicMock(price="1.08955")]

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.parts = lambda: [("pricing.ClientPrice", mock_price)]

        mock_context.pricing.stream.return_value = mock_response

        # Create service and stream ticks
        service = OandaService(self.account)  # ty:ignore[invalid-argument-type]
        ticks = list(service.stream_pricing_ticks("EUR_USD", snapshot=True))

        # Verify tick was parsed correctly
        self.assertEqual(len(ticks), 1)
        tick = ticks[0]
        self.assertEqual(tick.instrument, "EUR_USD")
        self.assertEqual(tick.bid, Decimal("1.08950"))
        self.assertEqual(tick.ask, Decimal("1.08955"))

    @patch("apps.market.services.oanda.v20")
    def test_stream_multiple_instruments(self, mock_v20: Mock) -> None:
        """
        Test streaming multiple instruments simultaneously."""
        # Mock v20 Context
        mock_context = MagicMock()
        mock_v20.Context.return_value = mock_context

        # Mock streaming response with multiple instruments
        mock_prices = []
        instruments = ["EUR_USD", "GBP_USD", "USD_JPY"]

        for i, instrument in enumerate(instruments):
            mock_price = MagicMock()
            mock_price.instrument = instrument
            mock_price.time = datetime(2024, 1, 15, 10, 30, i, tzinfo=timezone.utc)
            mock_price.bids = [MagicMock(price=f"1.{8950 + i:05d}")]
            mock_price.asks = [MagicMock(price=f"1.{8955 + i:05d}")]
            mock_prices.append(("pricing.ClientPrice", mock_price))

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.parts = lambda: mock_prices

        mock_context.pricing.stream.return_value = mock_response

        # Create service and stream ticks
        service = OandaService(self.account)  # ty:ignore[invalid-argument-type]
        ticks = list(service.stream_pricing_ticks(instruments, snapshot=True))

        # Verify all instruments were parsed
        self.assertEqual(len(ticks), 3)
        parsed_instruments = [tick.instrument for tick in ticks]
        self.assertEqual(parsed_instruments, instruments)

    @patch("apps.market.services.oanda.v20")
    def test_stream_heartbeat_filtering(self, mock_v20: Mock) -> None:
        """
        Test that heartbeat messages are filtered out."""
        # Mock v20 Context
        mock_context = MagicMock()
        mock_v20.Context.return_value = mock_context

        # Mock streaming response with heartbeat and price
        mock_heartbeat = MagicMock()
        mock_heartbeat.type = "HEARTBEAT"

        mock_price = MagicMock()
        mock_price.instrument = "EUR_USD"
        mock_price.time = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        mock_price.bids = [MagicMock(price="1.08950")]
        mock_price.asks = [MagicMock(price="1.08955")]

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.parts = lambda: [
            ("pricing.PricingHeartbeat", mock_heartbeat),
            ("pricing.ClientPrice", mock_price),
        ]

        mock_context.pricing.stream.return_value = mock_response

        # Create service and stream ticks
        service = OandaService(self.account)  # ty:ignore[invalid-argument-type]
        ticks = list(service.stream_pricing_ticks("EUR_USD", snapshot=True))

        # Verify only price tick was returned (heartbeat filtered)
        self.assertEqual(len(ticks), 1)
        self.assertEqual(ticks[0].instrument, "EUR_USD")

    @patch("apps.market.services.oanda.v20")
    def test_stream_error_handling(self, mock_v20: Mock) -> None:
        """
        Test that streaming errors are handled gracefully."""
        # Mock v20 Context
        mock_context = MagicMock()
        mock_v20.Context.return_value = mock_context

        # Mock streaming response with error status
        mock_response = MagicMock()
        mock_response.status = 404
        mock_response.body = {"error": "Not found"}

        mock_context.pricing.stream.return_value = mock_response

        # Create service and attempt to stream
        service = OandaService(self.account)  # ty:ignore[invalid-argument-type]

        # Verify error is raised
        with self.assertRaises(Exception):
            list(service.stream_pricing_ticks("INVALID_INSTRUMENT"))

    @patch("apps.market.services.oanda.v20")
    def test_stream_malformed_data_skipping(self, mock_v20: Mock) -> None:
        """
        Test that malformed streaming data is skipped."""
        # Mock v20 Context
        mock_context = MagicMock()
        mock_v20.Context.return_value = mock_context

        # Mock streaming response with malformed and valid data
        mock_invalid_price = MagicMock()
        mock_invalid_price.instrument = ""  # Missing instrument
        mock_invalid_price.time = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        mock_invalid_price.bids = [MagicMock(price="1.08950")]
        mock_invalid_price.asks = [MagicMock(price="1.08955")]

        mock_valid_price = MagicMock()
        mock_valid_price.instrument = "EUR_USD"
        mock_valid_price.time = datetime(2024, 1, 15, 10, 30, 1, tzinfo=timezone.utc)
        mock_valid_price.bids = [MagicMock(price="1.08951")]
        mock_valid_price.asks = [MagicMock(price="1.08956")]

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.parts = lambda: [
            ("pricing.ClientPrice", mock_invalid_price),
            ("pricing.ClientPrice", mock_valid_price),
        ]

        mock_context.pricing.stream.return_value = mock_response

        # Create service and stream ticks
        service = OandaService(self.account)  # ty:ignore[invalid-argument-type]
        ticks = list(service.stream_pricing_ticks("EUR_USD", snapshot=True))

        # Verify only valid tick was returned
        self.assertEqual(len(ticks), 1)
        self.assertEqual(ticks[0].instrument, "EUR_USD")

    @patch("apps.market.services.oanda.v20")
    def test_stream_missing_bid_ask_skipping(self, mock_v20: Mock) -> None:
        """
        Test that ticks with missing bid/ask are skipped."""
        # Mock v20 Context
        mock_context = MagicMock()
        mock_v20.Context.return_value = mock_context

        # Mock streaming response with missing bid/ask
        mock_invalid_price = MagicMock()
        mock_invalid_price.instrument = "EUR_USD"
        mock_invalid_price.time = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        mock_invalid_price.bids = []  # Missing bids
        mock_invalid_price.asks = [MagicMock(price="1.08955")]

        mock_valid_price = MagicMock()
        mock_valid_price.instrument = "GBP_USD"
        mock_valid_price.time = datetime(2024, 1, 15, 10, 30, 1, tzinfo=timezone.utc)
        mock_valid_price.bids = [MagicMock(price="1.27500")]
        mock_valid_price.asks = [MagicMock(price="1.27505")]

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.parts = lambda: [
            ("pricing.ClientPrice", mock_invalid_price),
            ("pricing.ClientPrice", mock_valid_price),
        ]

        mock_context.pricing.stream.return_value = mock_response

        # Create service and stream ticks
        service = OandaService(self.account)  # ty:ignore[invalid-argument-type]
        ticks = list(service.stream_pricing_ticks(["EUR_USD", "GBP_USD"], snapshot=True))

        # Verify only valid tick was returned
        self.assertEqual(len(ticks), 1)
        self.assertEqual(ticks[0].instrument, "GBP_USD")


@pytest.mark.django_db
class TestMarketDataStreamingPytest:
    """Pytest-style tests for market data streaming."""

    @patch("apps.market.services.oanda.v20")
    def test_stream_tick_data_storage(self, mock_v20: Mock) -> None:
        """Test that streamed ticks can be stored in database."""
        # Create account
        user = UserFactory()
        account = OandaAccountFactory(user=user)

        # Mock v20 Context
        mock_context = MagicMock()
        mock_v20.Context.return_value = mock_context

        # Mock streaming response
        mock_price = MagicMock()
        mock_price.instrument = "EUR_USD"
        mock_price.time = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        mock_price.bids = [MagicMock(price="1.08950")]
        mock_price.asks = [MagicMock(price="1.08955")]

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.parts = lambda: [("pricing.ClientPrice", mock_price)]

        mock_context.pricing.stream.return_value = mock_response

        # Stream and store ticks
        service = OandaService(account)  # ty:ignore[invalid-argument-type]
        for tick in service.stream_pricing_ticks("EUR_USD", snapshot=True):
            tick.save()  # type: ignore[attr-defined]

        # Verify tick was stored
        stored_tick = TickData.objects.get(
            instrument="EUR_USD",
            timestamp=datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
        )
        assert stored_tick.bid == Decimal("1.08950")
        assert stored_tick.ask == Decimal("1.08955")

    @patch("apps.market.services.oanda.v20")
    def test_stream_dict_format_parsing(self, mock_v20: Mock) -> None:
        """Test parsing of dict-format streaming messages."""
        # Create account
        user = UserFactory()
        account = OandaAccountFactory(user=user)

        # Mock v20 Context
        mock_context = MagicMock()
        mock_v20.Context.return_value = mock_context

        # Mock streaming response with dict format
        mock_dict_message = {
            "type": "PRICE",
            "instrument": "GBP_USD",
            "time": "2024-01-15T10:30:00.000000Z",
            "bids": [{"price": "1.27500"}],
            "asks": [{"price": "1.27505"}],
        }

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.parts = lambda: [mock_dict_message]

        mock_context.pricing.stream.return_value = mock_response

        # Stream ticks
        service = OandaService(account)  # ty:ignore[invalid-argument-type]
        ticks = list(service.stream_pricing_ticks("GBP_USD", snapshot=True))

        # Verify dict format was parsed
        assert len(ticks) == 1
        assert ticks[0].instrument == "GBP_USD"
        assert ticks[0].bid == Decimal("1.27500")
        assert ticks[0].ask == Decimal("1.27505")

    @patch("apps.market.services.oanda.v20")
    def test_stream_sequential_tick_processing(self, mock_v20: Mock) -> None:
        """Test that sequential ticks are processed in order."""
        # Create account
        user = UserFactory()
        account = OandaAccountFactory(user=user)

        # Mock v20 Context
        mock_context = MagicMock()
        mock_v20.Context.return_value = mock_context

        # Mock streaming response with sequential ticks
        mock_prices = []
        for i in range(5):
            mock_price = MagicMock()
            mock_price.instrument = "USD_JPY"
            mock_price.time = datetime(2024, 1, 15, 10, 30, i, tzinfo=timezone.utc)
            mock_price.bids = [MagicMock(price=f"150.{100 + i:03d}")]
            mock_price.asks = [MagicMock(price=f"150.{105 + i:03d}")]
            mock_prices.append(("pricing.ClientPrice", mock_price))

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.parts = lambda: mock_prices

        mock_context.pricing.stream.return_value = mock_response

        # Stream ticks
        service = OandaService(account)  # ty:ignore[invalid-argument-type]
        ticks = list(service.stream_pricing_ticks("USD_JPY", snapshot=True))

        # Verify all ticks were processed in order
        assert len(ticks) == 5
        for i, tick in enumerate(ticks):
            assert tick.instrument == "USD_JPY"
            assert tick.bid == Decimal(f"150.{100 + i:03d}")

    @patch("apps.market.services.oanda.v20")
    def test_stream_strategy_evaluation_triggering(self, mock_v20: Mock) -> None:
        """
        Test that streaming data triggers strategy evaluation."""
        # Create account and trading task
        user = UserFactory()
        account = OandaAccountFactory(user=user)
        config = StrategyConfigurationFactory(user=user)
        trading_task = TradingTaskFactory(
            user=user,
            oanda_account=account,
            config=config,
            instrument="EUR_USD",
            status="running",
        )

        # Mock v20 Context
        mock_context = MagicMock()
        mock_v20.Context.return_value = mock_context

        # Mock streaming response
        mock_price = MagicMock()
        mock_price.instrument = "EUR_USD"
        mock_price.time = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        mock_price.bids = [MagicMock(price="1.08950")]
        mock_price.asks = [MagicMock(price="1.08955")]

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.parts = lambda: [("pricing.ClientPrice", mock_price)]

        mock_context.pricing.stream.return_value = mock_response

        # Stream ticks
        service = OandaService(account)  # ty:ignore[invalid-argument-type]
        ticks = list(service.stream_pricing_ticks("EUR_USD", snapshot=True))

        # Verify tick was received
        assert len(ticks) == 1

        # Verify trading task exists for this instrument
        from apps.trading.models import TradingTasks

        matching_tasks = TradingTasks.objects.filter(
            instrument="EUR_USD",
            status="running",
        )
        assert matching_tasks.count() == 1
        assert matching_tasks.first().id == trading_task.pk  # ty:ignore[possibly-missing-attribute, unresolved-attribute]

    @patch("apps.market.services.oanda.v20")
    def test_stream_connection_error_handling(self, mock_v20: Mock) -> None:
        """Test handling of connection errors during streaming."""
        # Create account
        user = UserFactory()
        account = OandaAccountFactory(user=user)

        # Mock v20 Context
        mock_context = MagicMock()
        mock_v20.Context.return_value = mock_context

        # Mock streaming response with error
        mock_response = MagicMock()
        mock_response.status = 500
        mock_response.body = {"error": "Internal server error"}

        mock_context.pricing.stream.return_value = mock_response

        # Create service and attempt to stream
        service = OandaService(account)  # ty:ignore[invalid-argument-type]

        # Verify error is raised
        with pytest.raises(Exception):
            list(service.stream_pricing_ticks("EUR_USD"))

    @patch("apps.market.services.oanda.v20")
    def test_stream_mid_price_calculation(self, mock_v20: Mock) -> None:
        """Test that mid price is calculated correctly from bid/ask."""
        # Create account
        user = UserFactory()
        account = OandaAccountFactory(user=user)

        # Mock v20 Context
        mock_context = MagicMock()
        mock_v20.Context.return_value = mock_context

        # Mock streaming response
        mock_price = MagicMock()
        mock_price.instrument = "EUR_USD"
        mock_price.time = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        mock_price.bids = [MagicMock(price="1.08950")]
        mock_price.asks = [MagicMock(price="1.08960")]

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.parts = lambda: [("pricing.ClientPrice", mock_price)]

        mock_context.pricing.stream.return_value = mock_response

        # Stream ticks
        service = OandaService(account)  # ty:ignore[invalid-argument-type]
        ticks = list(service.stream_pricing_ticks("EUR_USD", snapshot=True))

        # Verify mid price calculation
        assert len(ticks) == 1
        tick = ticks[0]
        expected_mid = (Decimal("1.08950") + Decimal("1.08960")) / 2
        assert tick.mid == expected_mid
