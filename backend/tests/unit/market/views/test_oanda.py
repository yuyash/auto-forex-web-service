"""Pure unit tests for OANDA views (with mocks, no DB)."""

from unittest.mock import MagicMock, patch

from rest_framework import status
from rest_framework.test import APIRequestFactory

from apps.market.views.oanda import OandaAccountView


class TestOandaAccountViewUnit:
    """Pure unit tests for OandaAccountView."""

    def test_get_requires_authentication(self) -> None:
        """Test that GET requires authentication."""
        factory = APIRequestFactory()
        request = factory.get("/api/market/accounts/")
        request.user = MagicMock(is_authenticated=False)

        view = OandaAccountView()
        response = view.get(request)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_post_requires_authentication(self) -> None:
        """Test that POST requires authentication."""
        factory = APIRequestFactory()
        request = factory.post("/api/market/accounts/", {})
        request.user = MagicMock(is_authenticated=False)

        view = OandaAccountView()
        response = view.post(request)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @patch("apps.market.views.oanda.OandaAccounts")
    def test_get_with_authentication(self, mock_accounts: MagicMock) -> None:
        """Test GET with authenticated user."""
        # Mock user
        mock_user = MagicMock()
        mock_user.is_authenticated = True
        mock_user.id = 1
        mock_user.email = "test@example.com"

        # Mock queryset
        mock_qs = MagicMock()
        mock_qs.count.return_value = 0
        mock_accounts.objects.filter.return_value.order_by.return_value = mock_qs

        factory = APIRequestFactory()
        request = factory.get("/api/market/accounts/")
        request.user = mock_user

        view = OandaAccountView()
        response = view.get(request)

        assert response.status_code == status.HTTP_200_OK
        if response.data:
            assert response.data["count"] == 0
