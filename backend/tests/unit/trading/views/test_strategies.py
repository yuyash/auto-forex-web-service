"""Unit tests for trading views strategies."""

from unittest.mock import MagicMock, patch

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.test import APIRequestFactory

from apps.trading.views.strategies import StrategyDefaultsView, StrategyView


class TestStrategyView:
    """Test StrategyView."""

    def test_permission_classes(self):
        assert IsAuthenticated in StrategyView.permission_classes

    @patch("apps.trading.strategies.registry.registry")
    def test_get_returns_strategies(self, mock_registry):
        mock_registry.get_all_strategies_info.return_value = {
            "floor": {
                "config_schema": {"display_name": "Floor Strategy"},
                "description": "A floor strategy",
            }
        }
        factory = APIRequestFactory()
        request = factory.get("/api/trading/strategies/")
        request.user = MagicMock()

        view = StrategyView()
        response = view.get(request)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert len(response.data["strategies"]) == 1
        assert response.data["strategies"][0]["id"] == "floor"


class TestStrategyDefaultsView:
    """Test StrategyDefaultsView."""

    def test_permission_classes(self):
        assert IsAuthenticated in StrategyDefaultsView.permission_classes

    @patch("apps.trading.strategies.registry.registry")
    def test_get_unknown_strategy_returns_404(self, mock_registry):
        mock_registry.is_registered.return_value = False
        factory = APIRequestFactory()
        request = factory.get("/api/trading/strategies/unknown/defaults/")
        request.user = MagicMock()

        view = StrategyDefaultsView()
        response = view.get(request, strategy_id="unknown")

        assert response.status_code == status.HTTP_404_NOT_FOUND
