"""
Integration tests for market data API endpoints.

Tests market data query endpoints and historical data retrieval.
"""

import re

import responses
from django.urls import reverse

from tests.integration.base import APIIntegrationTestCase
from tests.integration.factories import OandaAccountFactory


class CandleDataEndpointTests(APIIntegrationTestCase):
    """Tests for candle data endpoint."""

    def setUp(self) -> None:
        """Set up test data."""
        super().setUp()
        self.account = OandaAccountFactory(user=self.user)
        self.url = reverse("market:candle_data")

    @responses.activate
    def test_fetch_candles_success(self) -> None:
        """Test fetching candle data with valid parameters."""
        # Mock OANDA API response - use regex to match with or without port
        responses.add(
            responses.GET,
            re.compile(
                rf"https://{re.escape(self.account.api_hostname)}(:\d+)?/v3/instruments/EUR_USD/candles.*"  # ty:ignore[possibly-missing-attribute]
            ),
            json={
                "instrument": "EUR_USD",
                "granularity": "H1",
                "candles": [
                    {
                        "time": "2024-01-15T10:00:00.000000Z",
                        "volume": 1000,
                        "complete": True,
                        "mid": {
                            "o": "1.08950",
                            "h": "1.08980",
                            "l": "1.08940",
                            "c": "1.08970",
                        },
                    },
                    {
                        "time": "2024-01-15T11:00:00.000000Z",
                        "volume": 1200,
                        "complete": True,
                        "mid": {
                            "o": "1.08970",
                            "h": "1.09000",
                            "l": "1.08960",
                            "c": "1.08990",
                        },
                    },
                ],
            },
            status=200,
        )

        response = self.client.get(
            self.url,
            {
                "instrument": "EUR_USD",
                "granularity": "H1",
                "count": "2",
            },
        )

        self.assert_response_success(response)  # type: ignore[arg-type]
        self.assertIn("candles", response.data)  # ty:ignore[possibly-missing-attribute]
        self.assertEqual(len(response.data["candles"]), 2)  # ty:ignore[possibly-missing-attribute]
        self.assertEqual(response.data["instrument"], "EUR_USD")  # ty:ignore[possibly-missing-attribute]
        self.assertEqual(response.data["granularity"], "H1")  # ty:ignore[possibly-missing-attribute]

    def test_fetch_candles_missing_instrument(self) -> None:
        """Test that missing instrument parameter returns error."""
        response = self.client.get(
            self.url,
            {
                "granularity": "H1",
                "count": "100",
            },
        )

        self.assert_response_error(response, status_code=400)  # ty:ignore[invalid-argument-type]
        self.assertIn("error", response.data)  # ty:ignore[possibly-missing-attribute]
        self.assertIn("instrument", response.data["error"].lower())  # ty:ignore[possibly-missing-attribute]

    def test_fetch_candles_invalid_count(self) -> None:
        """Test that invalid count parameter returns error."""
        response = self.client.get(
            self.url,
            {
                "instrument": "EUR_USD",
                "granularity": "H1",
                "count": "10000",  # Exceeds max of 5000
            },
        )

        self.assert_response_error(response, status_code=400)  # ty:ignore[invalid-argument-type]
        self.assertIn("error", response.data)  # ty:ignore[possibly-missing-attribute]
        self.assertIn("count", response.data["error"].lower())  # ty:ignore[possibly-missing-attribute]

    def test_fetch_candles_no_account(self) -> None:
        """Test that request without OANDA account returns error."""
        # Delete the account
        self.account.delete()  # ty:ignore[possibly-missing-attribute]

        response = self.client.get(
            self.url,
            {
                "instrument": "EUR_USD",
                "granularity": "H1",
                "count": "100",
            },
        )

        self.assert_response_error(response, status_code=400)  # ty:ignore[invalid-argument-type]
        self.assertIn("error", response.data)  # ty:ignore[possibly-missing-attribute]

    @responses.activate
    def test_fetch_candles_with_time_range(self) -> None:
        """Test fetching candles with from_time and to_time parameters."""
        # Mock OANDA API response - use regex to match with or without port
        responses.add(
            responses.GET,
            re.compile(
                rf"https://{re.escape(self.account.api_hostname)}(:\d+)?/v3/instruments/EUR_USD/candles.*"  # ty:ignore[possibly-missing-attribute]
            ),
            json={
                "instrument": "EUR_USD",
                "granularity": "M5",
                "candles": [
                    {
                        "time": "2024-01-15T10:00:00.000000Z",
                        "volume": 500,
                        "complete": True,
                        "mid": {
                            "o": "1.08950",
                            "h": "1.08960",
                            "l": "1.08945",
                            "c": "1.08955",
                        },
                    },
                ],
            },
            status=200,
        )

        response = self.client.get(
            self.url,
            {
                "instrument": "EUR_USD",
                "granularity": "M5",
                "from_time": "2024-01-15T10:00:00Z",
                "to_time": "2024-01-15T11:00:00Z",
            },
        )

        self.assert_response_success(response)  # type: ignore[arg-type]
        self.assertIn("candles", response.data)  # ty:ignore[possibly-missing-attribute]

    @responses.activate
    def test_fetch_candles_with_specific_account(self) -> None:
        """Test fetching candles with specific account_id parameter."""
        # Create another account
        other_account = OandaAccountFactory(user=self.user)

        # Mock OANDA API response - use regex to match with or without port
        responses.add(
            responses.GET,
            re.compile(
                rf"https://{re.escape(other_account.api_hostname)}(:\d+)?/v3/instruments/GBP_USD/candles.*"  # ty:ignore[unresolved-attribute]
            ),
            json={
                "instrument": "GBP_USD",
                "granularity": "H1",
                "candles": [
                    {
                        "time": "2024-01-15T10:00:00.000000Z",
                        "volume": 800,
                        "complete": True,
                        "mid": {
                            "o": "1.27000",
                            "h": "1.27050",
                            "l": "1.26980",
                            "c": "1.27020",
                        },
                    },
                ],
            },
            status=200,
        )

        response = self.client.get(
            self.url,
            {
                "instrument": "GBP_USD",
                "granularity": "H1",
                "count": "1",
                "account_id": other_account.account_id,
            },  # ty:ignore[invalid-argument-type]
        )

        self.assert_response_success(response)  # type: ignore[arg-type]
        self.assertIn("candles", response.data)  # ty:ignore[possibly-missing-attribute]


class SupportedInstrumentsEndpointTests(APIIntegrationTestCase):
    """Tests for supported instruments endpoint."""

    def setUp(self) -> None:
        """Set up test data."""
        super().setUp()
        self.account = OandaAccountFactory(user=self.user, is_active=True)
        self.url = reverse("market:supported_instruments")

    @responses.activate
    def test_fetch_instruments_from_oanda(self) -> None:
        """Test fetching instruments from OANDA API."""
        # Mock OANDA API response - use regex to match with or without port
        responses.add(
            responses.GET,
            re.compile(
                rf"https://{re.escape(self.account.api_hostname)}(:\d+)?/v3/accounts/{re.escape(self.account.account_id)}/instruments.*"  # ty:ignore[invalid-argument-type, possibly-missing-attribute]
            ),
            json={
                "instruments": [
                    {"name": "EUR_USD", "displayName": "EUR/USD", "type": "CURRENCY"},
                    {"name": "GBP_USD", "displayName": "GBP/USD", "type": "CURRENCY"},
                    {"name": "USD_JPY", "displayName": "USD/JPY", "type": "CURRENCY"},
                ]
            },
            status=200,
        )

        response = self.client.get(self.url)

        self.assert_response_success(response)  # type: ignore[arg-type]
        self.assertIn("instruments", response.data)  # ty:ignore[possibly-missing-attribute]
        self.assertIn("count", response.data)  # ty:ignore[possibly-missing-attribute]
        self.assertIn("source", response.data)  # ty:ignore[possibly-missing-attribute]
        self.assertEqual(response.data["source"], "oanda")  # ty:ignore[possibly-missing-attribute]
        self.assertIsInstance(response.data["instruments"], list)  # ty:ignore[possibly-missing-attribute]
        self.assertGreater(response.data["count"], 0)  # ty:ignore[possibly-missing-attribute]

    def test_fetch_instruments_fallback(self) -> None:
        """Test that fallback instruments are returned when OANDA API fails."""
        # Delete account to trigger fallback
        self.account.delete()  # ty:ignore[possibly-missing-attribute]

        response = self.client.get(self.url)

        self.assert_response_success(response)  # type: ignore[arg-type]
        self.assertIn("instruments", response.data)  # ty:ignore[possibly-missing-attribute]
        self.assertEqual(response.data["source"], "fallback")  # ty:ignore[possibly-missing-attribute]
        self.assertIsInstance(response.data["instruments"], list)  # ty:ignore[possibly-missing-attribute]
        self.assertGreater(len(response.data["instruments"]), 0)  # ty:ignore[possibly-missing-attribute]


class SupportedGranularitiesEndpointTests(APIIntegrationTestCase):
    """Tests for supported granularities endpoint."""

    def setUp(self) -> None:
        """Set up test data."""
        super().setUp()
        self.url = reverse("market:supported_granularities")

    def test_fetch_granularities(self) -> None:
        """Test fetching supported granularities."""
        response = self.client.get(self.url)

        self.assert_response_success(response)  # type: ignore[arg-type]
        self.assertIn("granularities", response.data)  # ty:ignore[possibly-missing-attribute]
        self.assertIn("count", response.data)  # ty:ignore[possibly-missing-attribute]
        self.assertIn("source", response.data)  # ty:ignore[possibly-missing-attribute]
        self.assertIsInstance(response.data["granularities"], list)  # ty:ignore[possibly-missing-attribute]
        self.assertGreater(response.data["count"], 0)  # ty:ignore[possibly-missing-attribute]

        # Verify granularity structure
        if response.data["granularities"]:  # ty:ignore[possibly-missing-attribute]
            granularity = response.data["granularities"][0]  # ty:ignore[possibly-missing-attribute]
            self.assertIn("value", granularity)
            self.assertIn("label", granularity)


class MarketStatusEndpointTests(APIIntegrationTestCase):
    """Tests for market status endpoint."""

    def setUp(self) -> None:
        """Set up test data."""
        super().setUp()
        self.url = reverse("market:market_status")

    def test_fetch_market_status(self) -> None:
        """Test fetching current market status."""
        response = self.client.get(self.url)

        self.assert_response_success(response)  # type: ignore[arg-type]
        self.assertIn("is_open", response.data)  # ty:ignore[possibly-missing-attribute]
        self.assertIn("current_time_utc", response.data)  # ty:ignore[possibly-missing-attribute]
        self.assertIn("active_sessions", response.data)  # ty:ignore[possibly-missing-attribute]
        self.assertIn("sessions", response.data)  # ty:ignore[possibly-missing-attribute]
        self.assertIsInstance(response.data["is_open"], bool)  # ty:ignore[possibly-missing-attribute]
        self.assertIsInstance(response.data["active_sessions"], list)  # ty:ignore[possibly-missing-attribute]
        self.assertIsInstance(response.data["sessions"], dict)  # ty:ignore[possibly-missing-attribute]


class InstrumentDetailEndpointTests(APIIntegrationTestCase):
    """Tests for instrument detail endpoint."""

    def setUp(self) -> None:
        """Set up test data."""
        super().setUp()
        self.account = OandaAccountFactory(user=self.user, is_active=True)

    @responses.activate
    def test_fetch_instrument_detail_success(self) -> None:
        """Test fetching detailed information for a specific instrument."""
        instrument = "EUR_USD"
        url = reverse("market:instrument_detail", kwargs={"instrument": instrument})

        # Mock OANDA API responses - use regex to match with or without port
        # Use minimal required fields that v20 library expects
        responses.add(
            responses.GET,
            re.compile(
                rf"https://{re.escape(self.account.api_hostname)}(:\d+)?/v3/accounts/{re.escape(self.account.account_id)}/instruments.*"  # ty:ignore[invalid-argument-type, possibly-missing-attribute]
            ),
            json={
                "instruments": [
                    {
                        "name": "EUR_USD",
                        "displayName": "EUR/USD",
                        "type": "CURRENCY",
                        "pipLocation": -4,
                        "displayPrecision": 5,
                        "tradeUnitsPrecision": 0,
                        "minimumTradeSize": "1",
                        "marginRate": "0.0333",
                    }
                ]
            },
            status=200,
        )

        # Mock pricing response
        responses.add(
            responses.GET,
            re.compile(
                rf"https://{re.escape(self.account.api_hostname)}(:\d+)?/v3/accounts/{re.escape(self.account.account_id)}/pricing.*"  # ty:ignore[invalid-argument-type, possibly-missing-attribute]
            ),
            json={
                "prices": [
                    {
                        "instrument": "EUR_USD",
                        "time": "2024-01-15T10:30:00.000000Z",
                        "bids": [{"price": "1.08950"}],
                        "asks": [{"price": "1.08955"}],
                    }
                ]
            },
            status=200,
        )

        response = self.client.get(url)

        self.assert_response_success(response)  # type: ignore[arg-type]
        self.assertIn("instrument", response.data)  # ty:ignore[possibly-missing-attribute]
        self.assertIn("display_name", response.data)  # ty:ignore[possibly-missing-attribute]
        self.assertIn("pip_location", response.data)  # ty:ignore[possibly-missing-attribute]
        self.assertIn("pip_value", response.data)  # ty:ignore[possibly-missing-attribute]
        self.assertIn("margin_rate", response.data)  # ty:ignore[possibly-missing-attribute]
        self.assertIn("source", response.data)  # ty:ignore[possibly-missing-attribute]
        self.assertEqual(response.data["instrument"], "EUR_USD")  # ty:ignore[possibly-missing-attribute]
        self.assertEqual(response.data["source"], "oanda")  # ty:ignore[possibly-missing-attribute]

    def test_fetch_instrument_detail_not_found(self) -> None:
        """Test that requesting non-existent instrument returns 404."""
        # Delete account to trigger error
        self.account.delete()  # ty:ignore[possibly-missing-attribute]

        url = reverse("market:instrument_detail", kwargs={"instrument": "INVALID_PAIR"})
        response = self.client.get(url)

        self.assert_response_error(response, status_code=404)  # ty:ignore[invalid-argument-type]
        self.assertIn("error", response.data)  # ty:ignore[possibly-missing-attribute]

    @responses.activate
    def test_fetch_instrument_detail_with_pricing(self) -> None:
        """Test that instrument detail includes current pricing data."""
        instrument = "GBP_USD"
        url = reverse("market:instrument_detail", kwargs={"instrument": instrument})

        # Mock OANDA API responses - use regex to match with or without port
        # Use minimal required fields that v20 library expects
        responses.add(
            responses.GET,
            re.compile(
                rf"https://{re.escape(self.account.api_hostname)}(:\d+)?/v3/accounts/{re.escape(self.account.account_id)}/instruments.*"  # ty:ignore[invalid-argument-type, possibly-missing-attribute]
            ),
            json={
                "instruments": [
                    {
                        "name": "GBP_USD",
                        "displayName": "GBP/USD",
                        "type": "CURRENCY",
                        "pipLocation": -4,
                        "displayPrecision": 5,
                        "tradeUnitsPrecision": 0,
                        "minimumTradeSize": "1",
                        "marginRate": "0.0333",
                    }
                ]
            },
            status=200,
        )

        responses.add(
            responses.GET,
            re.compile(
                rf"https://{re.escape(self.account.api_hostname)}(:\d+)?/v3/accounts/{re.escape(self.account.account_id)}/pricing.*"  # ty:ignore[invalid-argument-type, possibly-missing-attribute]
            ),
            json={
                "prices": [
                    {
                        "instrument": "GBP_USD",
                        "time": "2024-01-15T10:30:00.000000Z",
                        "bids": [{"price": "1.27000"}],
                        "asks": [{"price": "1.27005"}],
                    }
                ]
            },
            status=200,
        )

        response = self.client.get(url)

        self.assert_response_success(response)  # type: ignore[arg-type]
        self.assertIn("current_pricing", response.data)  # ty:ignore[possibly-missing-attribute]
        if response.data["current_pricing"]:  # ty:ignore[possibly-missing-attribute]
            pricing = response.data["current_pricing"]  # ty:ignore[possibly-missing-attribute]
            self.assertIn("bid", pricing)
            self.assertIn("ask", pricing)
            self.assertIn("spread", pricing)
