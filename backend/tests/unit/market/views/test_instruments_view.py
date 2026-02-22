"""Unit tests for SupportedInstrumentsView and InstrumentDetailView."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from rest_framework import status as http_status
from rest_framework.permissions import IsAuthenticated
from rest_framework.test import APIRequestFactory

from apps.market.views.instruments import InstrumentDetailView, SupportedInstrumentsView

factory = APIRequestFactory()


class TestSupportedInstrumentsViewPermissions:
    """Tests for permission classes."""

    def test_requires_authentication(self):
        view = SupportedInstrumentsView()
        assert IsAuthenticated in view.permission_classes

    def test_has_fallback_instruments(self):
        view = SupportedInstrumentsView()
        assert len(view.FALLBACK_INSTRUMENTS) > 0
        assert "EUR_USD" in view.FALLBACK_INSTRUMENTS


class TestSupportedInstrumentsViewGet:
    """Tests for get method."""

    @patch.object(SupportedInstrumentsView, "_fetch_instruments_from_oanda")
    def test_returns_oanda_instruments(self, mock_fetch):
        mock_fetch.return_value = ["EUR_USD", "GBP_USD", "USD_JPY"]

        view = SupportedInstrumentsView()
        request = factory.get("/")
        request.user = MagicMock()

        response = view.get(request)

        assert response.status_code == http_status.HTTP_200_OK
        assert response.data["source"] == "oanda"
        assert response.data["count"] == 3
        assert "EUR_USD" in response.data["instruments"]

    @patch.object(SupportedInstrumentsView, "_fetch_instruments_from_oanda")
    def test_returns_fallback_when_oanda_fails(self, mock_fetch):
        mock_fetch.return_value = None

        view = SupportedInstrumentsView()
        request = factory.get("/")
        request.user = MagicMock()

        response = view.get(request)

        assert response.status_code == http_status.HTTP_200_OK
        assert response.data["source"] == "fallback"
        assert response.data["count"] == len(SupportedInstrumentsView.FALLBACK_INSTRUMENTS)


class TestFetchInstrumentsFromOanda:
    """Tests for _fetch_instruments_from_oanda."""

    @patch("apps.market.views.instruments.v20")
    @patch("apps.market.views.instruments.OandaAccounts")
    def test_no_active_account_returns_none(self, MockAccounts, mock_v20):
        MockAccounts.objects.filter.return_value.first.return_value = None

        view = SupportedInstrumentsView()
        result = view._fetch_instruments_from_oanda()

        assert result is None

    @patch("apps.market.views.instruments.v20")
    @patch("apps.market.views.instruments.OandaAccounts")
    def test_successful_fetch(self, MockAccounts, mock_v20):
        account = MagicMock()
        account.api_hostname = "api-fxpractice.oanda.com"
        account.get_api_token.return_value = "token"
        account.account_id = "001"
        MockAccounts.objects.filter.return_value.first.return_value = account

        instr1 = MagicMock()
        instr1.name = "EUR_USD"
        instr2 = MagicMock()
        instr2.name = "GBP_USD"
        instr3 = MagicMock()
        instr3.name = "CORN_USD_LONG_NAME"  # Should be filtered out (len != 7)

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.body = {"instruments": [instr1, instr2, instr3]}

        mock_context = MagicMock()
        mock_context.account.instruments.return_value = mock_response
        mock_v20.Context.return_value = mock_context

        view = SupportedInstrumentsView()
        result = view._fetch_instruments_from_oanda()

        assert result is not None
        assert "EUR_USD" in result
        assert "GBP_USD" in result
        assert "CORN_USD_LONG_NAME" not in result

    @patch("apps.market.views.instruments.v20")
    @patch("apps.market.views.instruments.OandaAccounts")
    def test_api_error_returns_none(self, MockAccounts, mock_v20):
        account = MagicMock()
        account.api_hostname = "api-fxpractice.oanda.com"
        account.get_api_token.return_value = "token"
        account.account_id = "001"
        MockAccounts.objects.filter.return_value.first.return_value = account

        mock_response = MagicMock()
        mock_response.status = 500
        mock_response.body = {}

        mock_context = MagicMock()
        mock_context.account.instruments.return_value = mock_response
        mock_v20.Context.return_value = mock_context

        view = SupportedInstrumentsView()
        result = view._fetch_instruments_from_oanda()

        assert result is None

    @patch("apps.market.views.instruments.v20")
    @patch("apps.market.views.instruments.OandaAccounts")
    def test_exception_returns_none(self, MockAccounts, mock_v20):
        account = MagicMock()
        account.api_hostname = "api-fxpractice.oanda.com"
        account.get_api_token.return_value = "token"
        account.account_id = "001"
        MockAccounts.objects.filter.return_value.first.return_value = account

        mock_v20.Context.side_effect = Exception("connection error")

        view = SupportedInstrumentsView()
        result = view._fetch_instruments_from_oanda()

        assert result is None


class TestInstrumentDetailViewPermissions:
    """Tests for InstrumentDetailView permissions."""

    def test_requires_authentication(self):
        view = InstrumentDetailView()
        assert IsAuthenticated in view.permission_classes


class TestInstrumentDetailViewGet:
    """Tests for InstrumentDetailView.get."""

    @patch.object(InstrumentDetailView, "_fetch_instrument_details")
    def test_returns_instrument_data(self, mock_fetch):
        mock_fetch.return_value = {
            "instrument": "EUR_USD",
            "display_name": "EUR/USD",
            "type": "CURRENCY",
        }

        view = InstrumentDetailView()
        request = factory.get("/")
        request.user = MagicMock(id=1)

        response = view.get(request, instrument="EUR_USD")

        assert response.status_code == http_status.HTTP_200_OK
        assert response.data["instrument"] == "EUR_USD"
        assert response.data["source"] == "oanda"

    @patch.object(InstrumentDetailView, "_fetch_instrument_details")
    def test_returns_404_when_not_found(self, mock_fetch):
        mock_fetch.return_value = None

        view = InstrumentDetailView()
        request = factory.get("/")
        request.user = MagicMock(id=1)

        response = view.get(request, instrument="INVALID")

        assert response.status_code == http_status.HTTP_404_NOT_FOUND

    @patch.object(InstrumentDetailView, "_fetch_instrument_details")
    def test_normalizes_instrument_name(self, mock_fetch):
        mock_fetch.return_value = {"instrument": "EUR_USD"}

        view = InstrumentDetailView()
        request = factory.get("/")
        request.user = MagicMock(id=1)

        view.get(request, instrument="eur-usd")

        # Should be called with normalized name
        mock_fetch.assert_called_once_with(request, "EUR_USD")


class TestFetchInstrumentDetails:
    """Tests for _fetch_instrument_details."""

    @patch("apps.market.views.instruments.v20")
    @patch("apps.market.views.instruments.OandaAccounts")
    def test_no_user_id_returns_none(self, MockAccounts, mock_v20):
        view = InstrumentDetailView()
        request = factory.get("/")
        request.user = MagicMock(id=None)

        result = view._fetch_instrument_details(request, "EUR_USD")
        assert result is None

    @patch("apps.market.views.instruments.v20")
    @patch("apps.market.views.instruments.OandaAccounts")
    def test_no_active_account_returns_none(self, MockAccounts, mock_v20):
        MockAccounts.objects.filter.return_value.first.return_value = None

        view = InstrumentDetailView()
        request = factory.get("/")
        request.user = MagicMock(id=1)

        result = view._fetch_instrument_details(request, "EUR_USD")
        assert result is None

    @patch("apps.market.views.instruments.v20")
    @patch("apps.market.views.instruments.OandaAccounts")
    def test_successful_fetch_returns_details(self, MockAccounts, mock_v20):
        account = MagicMock()
        account.api_hostname = "api-fxpractice.oanda.com"
        account.get_api_token.return_value = "token"
        account.account_id = "001"
        MockAccounts.objects.filter.return_value.first.return_value = account

        instr = MagicMock()
        instr.name = "EUR_USD"
        instr.displayName = "EUR/USD"
        instr.type = "CURRENCY"
        instr.pipLocation = -4
        instr.displayPrecision = 5
        instr.tradeUnitsPrecision = 0
        instr.minimumTradeSize = "1"
        instr.maximumTradeUnits = "100000000"
        instr.maximumPositionSize = "0"
        instr.maximumOrderUnits = "100000000"
        instr.marginRate = "0.02"
        instr.guaranteedStopLossOrderMode = "DISABLED"
        instr.tags = []
        instr.financing = MagicMock()
        instr.financing.longRate = "-0.0150"
        instr.financing.shortRate = "0.0050"

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.body = {"instruments": [instr]}

        mock_context = MagicMock()
        mock_context.account.instruments.return_value = mock_response
        mock_v20.Context.return_value = mock_context

        view = InstrumentDetailView()
        view._fetch_current_pricing = MagicMock(return_value=None)

        request = factory.get("/")
        request.user = MagicMock(id=1)

        result = view._fetch_instrument_details(request, "EUR_USD")

        assert result is not None
        assert result["instrument"] == "EUR_USD"
        assert result["display_name"] == "EUR/USD"
        assert result["pip_value"] == 0.0001
        assert result["leverage"] == "1:50"

    @patch("apps.market.views.instruments.v20")
    @patch("apps.market.views.instruments.OandaAccounts")
    def test_api_error_returns_none(self, MockAccounts, mock_v20):
        account = MagicMock()
        account.api_hostname = "api-fxpractice.oanda.com"
        account.get_api_token.return_value = "token"
        account.account_id = "001"
        MockAccounts.objects.filter.return_value.first.return_value = account

        mock_response = MagicMock()
        mock_response.status = 500

        mock_context = MagicMock()
        mock_context.account.instruments.return_value = mock_response
        mock_v20.Context.return_value = mock_context

        view = InstrumentDetailView()
        request = factory.get("/")
        request.user = MagicMock(id=1)

        result = view._fetch_instrument_details(request, "EUR_USD")
        assert result is None

    @patch("apps.market.views.instruments.v20")
    @patch("apps.market.views.instruments.OandaAccounts")
    def test_empty_instruments_returns_none(self, MockAccounts, mock_v20):
        account = MagicMock()
        account.api_hostname = "api-fxpractice.oanda.com"
        account.get_api_token.return_value = "token"
        account.account_id = "001"
        MockAccounts.objects.filter.return_value.first.return_value = account

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.body = {"instruments": []}

        mock_context = MagicMock()
        mock_context.account.instruments.return_value = mock_response
        mock_v20.Context.return_value = mock_context

        view = InstrumentDetailView()
        request = factory.get("/")
        request.user = MagicMock(id=1)

        result = view._fetch_instrument_details(request, "INVALID")
        assert result is None


class TestFetchCurrentPricing:
    """Tests for _fetch_current_pricing."""

    def test_returns_pricing_data(self):
        bid = MagicMock()
        bid.price = "1.10000"
        ask = MagicMock()
        ask.price = "1.10020"

        price = MagicMock()
        price.bids = [bid]
        price.asks = [ask]
        price.tradeable = True
        price.time = "2024-01-01T00:00:00Z"

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.body = {"prices": [price]}

        api = MagicMock()
        api.pricing.get.return_value = mock_response

        view = InstrumentDetailView()
        result = view._fetch_current_pricing(api, "001", "EUR_USD")

        assert result is not None
        assert result["bid"] == "1.1"
        assert result["ask"] == "1.1002"
        assert result["tradeable"] is True

    def test_api_error_returns_none(self):
        mock_response = MagicMock()
        mock_response.status = 500

        api = MagicMock()
        api.pricing.get.return_value = mock_response

        view = InstrumentDetailView()
        result = view._fetch_current_pricing(api, "001", "EUR_USD")

        assert result is None

    def test_no_prices_returns_none(self):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.body = {"prices": []}

        api = MagicMock()
        api.pricing.get.return_value = mock_response

        view = InstrumentDetailView()
        result = view._fetch_current_pricing(api, "001", "EUR_USD")

        assert result is None

    def test_exception_returns_none(self):
        api = MagicMock()
        api.pricing.get.side_effect = Exception("connection error")

        view = InstrumentDetailView()
        result = view._fetch_current_pricing(api, "001", "EUR_USD")

        assert result is None
