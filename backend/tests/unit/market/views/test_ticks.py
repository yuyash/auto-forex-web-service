"""Unit tests for market views ticks."""

from unittest.mock import MagicMock, patch

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from apps.market.views.ticks import TickDataRangeView, TickDataView

factory = APIRequestFactory()


def _drf_request(django_request):
    """Wrap a Django WSGIRequest into a DRF Request."""
    return Request(django_request)


class TestTickDataView:
    """Test TickDataView."""

    def test_permission_classes(self):
        assert IsAuthenticated in TickDataView.permission_classes

    def test_get_missing_instrument(self):
        request = _drf_request(factory.get("/api/market/ticks/"))
        request.user = MagicMock()
        view = TickDataView()
        response = view.get(request)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_get_invalid_count(self):
        request = _drf_request(factory.get("/api/market/ticks/?instrument=USD_JPY&count=abc"))
        request.user = MagicMock()
        view = TickDataView()
        response = view.get(request)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_get_count_out_of_range(self):
        request = _drf_request(factory.get("/api/market/ticks/?instrument=USD_JPY&count=99999"))
        request.user = MagicMock()
        view = TickDataView()
        response = view.get(request)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @patch("apps.market.views.ticks.TickData")
    def test_get_valid_request(self, mock_tick_data):
        request = _drf_request(factory.get("/api/market/ticks/?instrument=USD_JPY&count=10"))
        request.user = MagicMock()

        mock_qs = MagicMock()
        mock_tick_data.objects.filter.return_value = mock_qs
        mock_qs.filter.return_value = mock_qs
        mock_qs.order_by.return_value = mock_qs
        mock_qs.__getitem__ = MagicMock(return_value=[])

        view = TickDataView()
        response = view.get(request)
        assert response.status_code == status.HTTP_200_OK


class TestTickDataRangeView:
    """Test TickDataRangeView."""

    def test_permission_classes(self):
        assert IsAuthenticated in TickDataRangeView.permission_classes

    def test_get_missing_instrument(self):
        request = _drf_request(factory.get("/api/market/ticks/data-range/"))
        request.user = MagicMock()
        view = TickDataRangeView()
        response = view.get(request)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @patch("apps.market.views.ticks.TickData")
    def test_get_no_data(self, mock_tick_data):
        request = _drf_request(factory.get("/api/market/ticks/data-range/?instrument=USD_JPY"))
        request.user = MagicMock()

        mock_tick_data.objects.filter.return_value.aggregate.return_value = {
            "min_timestamp": None,
            "max_timestamp": None,
        }

        view = TickDataRangeView()
        response = view.get(request)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["has_data"] is False
