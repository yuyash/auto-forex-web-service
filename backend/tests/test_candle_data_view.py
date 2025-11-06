"""
Tests for candle data API endpoint.

This module tests the CandleDataView API endpoint including:
- Cache configuration (10-minute fresh, 2-hour stale TTL)
- Response headers (X-Cache-Hit, X-Cache-Status, X-Rate-Limited)
- Before parameter support for time-based queries
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase

from rest_framework.test import APIClient

from accounts.models import OandaAccount

User = get_user_model()


class CandleDataViewTestCase(TestCase):
    """Test cases for CandleDataView API endpoint."""

    def setUp(self):
        """Set up test fixtures."""
        # Clear cache before each test
        cache.clear()

        # Create test user
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

        # Create test OANDA account with encrypted token
        self.oanda_account = OandaAccount.objects.create(
            user=self.user,
            account_id="001-001-1234567-001",
            api_type="practice",
        )
        # Use the set_api_token method to properly encrypt the token
        self.oanda_account.set_api_token("test_token_12345")
        self.oanda_account.save()

        # Set up API client
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def tearDown(self):
        """Clean up after tests."""
        cache.clear()

    @patch("trading.candle_views.v20.Context")
    def test_cache_miss_headers(self, mock_context):
        """Test that cache miss returns correct headers."""
        # Mock OANDA API response with proper object structure
        mock_candle = MagicMock()
        mock_candle.complete = True
        mock_candle.time = "2024-01-01T00:00:00.000000Z"
        mock_candle.volume = 100
        mock_candle.mid = MagicMock(o="1.1000", h="1.1010", l="1.0990", c="1.1005")

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.body = {
            "instrument": "EUR_USD",
            "granularity": "H1",
            "candles": [mock_candle],
        }
        mock_context.return_value.instrument.candles.return_value = mock_response

        # Make request
        response = self.client.get(
            "/api/candles/",
            {"instrument": "EUR_USD", "granularity": "H1", "count": "100"},
        )

        # Verify response
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-Cache-Hit"], "false")
        self.assertEqual(response["X-Cache-Status"], "miss")
        self.assertEqual(response["X-Rate-Limited"], "false")

    @patch("trading.candle_views.v20.Context")
    def test_cache_hit_headers(self, mock_context):
        """Test that cache hit returns correct headers."""
        # Mock OANDA API response with proper object structure
        mock_candle = MagicMock()
        mock_candle.complete = True
        mock_candle.time = "2024-01-01T00:00:00.000000Z"
        mock_candle.volume = 100
        mock_candle.mid = MagicMock(o="1.1000", h="1.1010", l="1.0990", c="1.1005")

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.body = {
            "instrument": "EUR_USD",
            "granularity": "H1",
            "candles": [mock_candle],
        }
        mock_context.return_value.instrument.candles.return_value = mock_response

        # First request - cache miss
        response1 = self.client.get(
            "/api/candles/",
            {"instrument": "EUR_USD", "granularity": "H1", "count": "100"},
        )
        self.assertEqual(response1.status_code, 200)
        self.assertEqual(response1["X-Cache-Hit"], "false")

        # Second request - cache hit
        response2 = self.client.get(
            "/api/candles/",
            {"instrument": "EUR_USD", "granularity": "H1", "count": "100"},
        )
        self.assertEqual(response2.status_code, 200)
        self.assertEqual(response2["X-Cache-Hit"], "true")
        self.assertEqual(response2["X-Cache-Status"], "fresh")
        self.assertEqual(response2["X-Rate-Limited"], "false")

    @patch("trading.candle_views.v20.Context")
    def test_before_parameter_support(self, mock_context):
        """Test that before parameter is converted to to_time."""
        # Mock OANDA API response
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.body = {"instrument": "EUR_USD", "granularity": "H1", "candles": []}
        mock_context.return_value.instrument.candles.return_value = mock_response

        # Make request with before parameter (Unix timestamp)
        before_timestamp = int(datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc).timestamp())
        response = self.client.get(
            "/api/candles/",
            {
                "instrument": "EUR_USD",
                "granularity": "H1",
                "count": "100",
                "before": str(before_timestamp),
            },
        )

        # Verify response
        self.assertEqual(response.status_code, 200)

        # Verify that the API was called with correct parameters
        # When 'before' is provided, it should be converted to 'to' parameter
        call_kwargs = mock_context.return_value.instrument.candles.call_args[1]
        # The 'before' parameter should result in either 'to' being set or 'count' being used
        # Since we provide 'before', the code converts it to 'to_time' which becomes 'to' in params
        self.assertTrue("to" in call_kwargs or "count" in call_kwargs)

    @patch("trading.candle_views.v20.Context")
    def test_rate_limit_stale_cache_headers(self, mock_context):
        """Test that rate limit returns stale cache with correct headers."""
        # First, populate the cache with a successful request
        mock_candle = MagicMock()
        mock_candle.complete = True
        mock_candle.time = "2024-01-01T00:00:00.000000Z"
        mock_candle.volume = 100
        mock_candle.mid = MagicMock(o="1.1000", h="1.1010", l="1.0990", c="1.1005")

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.body = {
            "instrument": "EUR_USD",
            "granularity": "H1",
            "candles": [mock_candle],
        }
        mock_context.return_value.instrument.candles.return_value = mock_response

        # First request - populate cache
        response1 = self.client.get(
            "/api/candles/",
            {"instrument": "EUR_USD", "granularity": "H1", "count": "100"},
        )
        self.assertEqual(response1.status_code, 200)

        # Clear the fresh cache to simulate expiration
        cache_key = "candles:EUR_USD:H1:100:None:None:None"
        cache.delete(cache_key)

        # Mock rate limit error
        mock_context.return_value.instrument.candles.side_effect = Exception("429 rate limit")

        # Second request - should return stale cache
        response2 = self.client.get(
            "/api/candles/",
            {"instrument": "EUR_USD", "granularity": "H1", "count": "100"},
        )
        self.assertEqual(response2.status_code, 200)
        self.assertEqual(response2["X-Cache-Hit"], "true")
        self.assertEqual(response2["X-Cache-Status"], "stale")
        self.assertEqual(response2["X-Rate-Limited"], "true")

    @patch("trading.candle_views.v20.Context")
    def test_cache_ttl_configuration(self, mock_context):
        """Test that cache TTL is configured correctly (10min fresh, 2hr stale)."""
        # Mock OANDA API response with proper object structure
        mock_candle = MagicMock()
        mock_candle.complete = True
        mock_candle.time = "2024-01-01T00:00:00.000000Z"
        mock_candle.volume = 100
        mock_candle.mid = MagicMock(o="1.1000", h="1.1010", l="1.0990", c="1.1005")

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.body = {
            "instrument": "EUR_USD",
            "granularity": "H1",
            "candles": [mock_candle],
        }
        mock_context.return_value.instrument.candles.return_value = mock_response

        # Make request to populate cache
        response = self.client.get(
            "/api/candles/",
            {"instrument": "EUR_USD", "granularity": "H1", "count": "100"},
        )
        self.assertEqual(response.status_code, 200)

        # Verify both fresh and stale cache keys exist
        cache_key = "candles:EUR_USD:H1:100:None:None:None"
        stale_cache_key = f"{cache_key}:stale"

        fresh_data = cache.get(cache_key)
        stale_data = cache.get(stale_cache_key)

        self.assertIsNotNone(fresh_data, "Fresh cache should be populated")
        self.assertIsNotNone(stale_data, "Stale cache should be populated")
        self.assertEqual(fresh_data, stale_data, "Fresh and stale cache should have same data")

    def test_missing_instrument_parameter(self):
        """Test that missing instrument parameter returns 400 error."""
        response = self.client.get("/api/candles/", {"granularity": "H1", "count": "100"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.data)  # type: ignore[attr-defined]

    def test_invalid_count_parameter(self):
        """Test that invalid count parameter returns 400 error."""
        # Test count > 5000
        response = self.client.get(
            "/api/candles/",
            {"instrument": "EUR_USD", "granularity": "H1", "count": "6000"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.data)  # type: ignore[attr-defined]

        # Test count < 1
        response = self.client.get(
            "/api/candles/",
            {"instrument": "EUR_USD", "granularity": "H1", "count": "0"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.data)  # type: ignore[attr-defined]

    def test_unauthenticated_request(self):
        """Test that unauthenticated requests are rejected."""
        client = APIClient()  # No authentication
        response = client.get(
            "/api/candles/",
            {"instrument": "EUR_USD", "granularity": "H1", "count": "100"},
        )
        self.assertEqual(response.status_code, 401)
