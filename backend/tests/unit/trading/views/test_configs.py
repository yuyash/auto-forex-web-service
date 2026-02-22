"""Unit tests for trading views configs."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.test import APIRequestFactory

from apps.trading.views.configs import StrategyConfigDetailView, StrategyConfigView


class TestStrategyConfigView:
    """Test StrategyConfigView."""

    def test_permission_classes(self):
        assert IsAuthenticated in StrategyConfigView.permission_classes

    def test_has_get_and_post(self):
        view = StrategyConfigView()
        assert hasattr(view, "get")
        assert hasattr(view, "post")


class TestStrategyConfigDetailView:
    """Test StrategyConfigDetailView."""

    def test_permission_classes(self):
        assert IsAuthenticated in StrategyConfigDetailView.permission_classes

    @patch("apps.trading.views.configs.StrategyConfigDetailSerializer")
    @patch("apps.trading.views.configs.StrategyConfiguration")
    def test_get_existing_config(self, mock_model, mock_serializer):
        config_id = uuid4()
        factory = APIRequestFactory()
        request = factory.get(f"/api/trading/strategy-configs/{config_id}/")
        request.user = MagicMock()
        request.user.pk = 1

        mock_config = MagicMock()
        mock_model.objects.get.return_value = mock_config
        mock_model.DoesNotExist = Exception
        mock_serializer.return_value.data = {"id": str(config_id)}

        view = StrategyConfigDetailView()
        response = view.get(request, config_id=config_id)
        assert response.status_code == status.HTTP_200_OK

    @patch("apps.trading.views.configs.StrategyConfiguration")
    def test_get_nonexistent_config_returns_404(self, mock_model):
        from apps.trading.models import StrategyConfiguration

        mock_model.objects.get.side_effect = StrategyConfiguration.DoesNotExist
        mock_model.DoesNotExist = StrategyConfiguration.DoesNotExist

        config_id = uuid4()
        factory = APIRequestFactory()
        request = factory.get(f"/api/trading/strategy-configs/{config_id}/")
        request.user = MagicMock()
        request.user.pk = 1

        view = StrategyConfigDetailView()
        response = view.get(request, config_id=config_id)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch("apps.trading.views.configs.StrategyConfiguration")
    def test_delete_in_use_returns_400(self, mock_model):
        config_id = uuid4()
        factory = APIRequestFactory()
        request = factory.delete(f"/api/trading/strategy-configs/{config_id}/")
        request.user = MagicMock()
        request.user.pk = 1

        mock_config = MagicMock()
        mock_config.is_in_use.return_value = True
        mock_model.objects.get.return_value = mock_config
        mock_model.DoesNotExist = Exception

        view = StrategyConfigDetailView()
        response = view.delete(request, config_id=config_id)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
