"""Unit tests for CandleDataView."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from rest_framework import status as http_status
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from apps.market.views.candles import CandleDataView

factory = APIRequestFactory()


def _build_view():
    return CandleDataView()


def _make_request(params=""):
    django_request = factory.get(f"/{params}")
    django_request.user = MagicMock(id=1, pk=1)
    return Request(django_request)


class TestCandleDataViewValidation:
    """Tests for parameter validation."""

    def test_missing_instrument_returns_400(self):
        view = _build_view()
        request = _make_request("?granularity=H1&count=100")

        response = view.get(request)

        assert response.status_code == http_status.HTTP_400_BAD_REQUEST
        assert "instrument" in response.data["error"]

    def test_invalid_count_string_returns_400(self):
        view = _build_view()
        request = _make_request("?instrument=EUR_USD&count=abc")

        response = view.get(request)

        assert response.status_code == http_status.HTTP_400_BAD_REQUEST
        assert "count" in response.data["error"]

    def test_count_too_low_returns_400(self):
        view = _build_view()
        request = _make_request("?instrument=EUR_USD&count=0")

        response = view.get(request)

        assert response.status_code == http_status.HTTP_400_BAD_REQUEST

    def test_count_too_high_returns_400(self):
        view = _build_view()
        request = _make_request("?instrument=EUR_USD&count=5001")

        response = view.get(request)

        assert response.status_code == http_status.HTTP_400_BAD_REQUEST


class TestCandleDataViewNoAccount:
    """Tests for missing OANDA account."""

    @patch("apps.market.views.candles.OandaAccounts")
    def test_no_account_returns_400(self, MockAccounts):
        MockAccounts.objects.filter.return_value.first.return_value = None
        MockAccounts.DoesNotExist = Exception

        view = _build_view()
        request = _make_request("?instrument=EUR_USD&count=100")

        response = view.get(request)

        assert response.status_code == http_status.HTTP_400_BAD_REQUEST
        assert (
            "NO_OANDA_ACCOUNT" in str(response.data.get("error_code", ""))
            or "account" in response.data["error"].lower()
        )

    @patch("apps.market.views.candles.OandaAccounts")
    def test_specific_account_not_found_returns_400(self, MockAccounts):
        from django.core.exceptions import ObjectDoesNotExist

        MockAccounts.objects.get.side_effect = ObjectDoesNotExist()

        view = _build_view()
        request = _make_request("?instrument=EUR_USD&count=100&account_id=999")

        response = view.get(request)

        assert response.status_code == http_status.HTTP_400_BAD_REQUEST


class TestCandleDataViewSuccess:
    """Tests for successful candle fetching."""

    @patch("apps.market.views.candles.v20")
    @patch("apps.market.views.candles.OandaAccounts")
    def test_default_fetch_returns_candles(self, MockAccounts, mock_v20):
        account = MagicMock()
        account.api_hostname = "api-fxpractice.oanda.com"
        account.get_api_token.return_value = "token"
        MockAccounts.objects.filter.return_value.first.return_value = account

        # Build mock candle
        mid = MagicMock()
        mid.o = "1.10000"
        mid.h = "1.10100"
        mid.l = "1.09900"
        mid.c = "1.10050"

        candle = MagicMock()
        candle.complete = True
        candle.mid = mid
        candle.time = "2024-01-01T00:00:00.000000000Z"
        candle.volume = 100

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.body = {"candles": [candle]}

        mock_context = MagicMock()
        mock_context.instrument.candles.return_value = mock_response
        mock_v20.Context.return_value = mock_context

        view = _build_view()
        request = _make_request("?instrument=EUR_USD&count=10")

        response = view.get(request)

        assert response.status_code == http_status.HTTP_200_OK
        assert response.data["instrument"] == "EUR_USD"
        assert len(response.data["candles"]) == 1
        assert response.data["candles"][0]["open"] == 1.10000

    @patch("apps.market.views.candles.v20")
    @patch("apps.market.views.candles.OandaAccounts")
    def test_skips_incomplete_candles(self, MockAccounts, mock_v20):
        account = MagicMock()
        account.api_hostname = "api-fxpractice.oanda.com"
        account.get_api_token.return_value = "token"
        MockAccounts.objects.filter.return_value.first.return_value = account

        incomplete_candle = MagicMock()
        incomplete_candle.complete = False

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.body = {"candles": [incomplete_candle]}

        mock_context = MagicMock()
        mock_context.instrument.candles.return_value = mock_response
        mock_v20.Context.return_value = mock_context

        view = _build_view()
        request = _make_request("?instrument=EUR_USD&count=10")

        response = view.get(request)

        assert response.status_code == http_status.HTTP_200_OK
        assert len(response.data["candles"]) == 0

    @patch("apps.market.views.candles.v20")
    @patch("apps.market.views.candles.OandaAccounts")
    def test_oanda_error_returns_500(self, MockAccounts, mock_v20):
        account = MagicMock()
        account.api_hostname = "api-fxpractice.oanda.com"
        account.get_api_token.return_value = "token"
        MockAccounts.objects.filter.return_value.first.return_value = account

        mock_response = MagicMock()
        mock_response.status = 400
        mock_response.body = {"errorMessage": "bad request"}

        mock_context = MagicMock()
        mock_context.instrument.candles.return_value = mock_response
        mock_v20.Context.return_value = mock_context

        view = _build_view()
        request = _make_request("?instrument=EUR_USD&count=10")

        response = view.get(request)

        assert response.status_code == http_status.HTTP_500_INTERNAL_SERVER_ERROR

    @patch("apps.market.views.candles.v20")
    @patch("apps.market.views.candles.OandaAccounts")
    def test_rate_limit_returns_429(self, MockAccounts, mock_v20):
        account = MagicMock()
        account.api_hostname = "api-fxpractice.oanda.com"
        account.get_api_token.return_value = "token"
        MockAccounts.objects.filter.return_value.first.return_value = account

        mock_context = MagicMock()
        mock_context.instrument.candles.side_effect = Exception("429 rate limit exceeded")
        mock_v20.Context.return_value = mock_context

        view = _build_view()
        request = _make_request("?instrument=EUR_USD&count=10")

        response = view.get(request)

        assert response.status_code == http_status.HTTP_429_TOO_MANY_REQUESTS


class TestGetGranularitySeconds:
    """Tests for _get_granularity_seconds."""

    def test_known_granularities(self):
        view = _build_view()

        assert view._get_granularity_seconds("M1") == 60
        assert view._get_granularity_seconds("H1") == 3600
        assert view._get_granularity_seconds("D") == 86400
        assert view._get_granularity_seconds("S5") == 5

    def test_unknown_granularity_defaults_to_3600(self):
        view = _build_view()
        assert view._get_granularity_seconds("UNKNOWN") == 3600
