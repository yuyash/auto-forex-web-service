"""Unit tests for TokenRefreshView (mocked dependencies)."""

from unittest.mock import MagicMock, patch

from rest_framework import status
from rest_framework.test import APIRequestFactory

from apps.accounts.views.refresh import TokenRefreshView


class TestTokenRefreshView:
    """Unit tests for TokenRefreshView."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.factory = APIRequestFactory()

    def test_post_missing_authorization_header(self) -> None:
        """Test token refresh without authorization header."""
        request = self.factory.post("/api/auth/refresh")
        view = TokenRefreshView()

        response = view.post(request)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_post_invalid_header_format(self) -> None:
        """Test token refresh with invalid authorization header format."""
        request = self.factory.post("/api/auth/refresh")
        request.META["HTTP_AUTHORIZATION"] = "InvalidFormat token"
        view = TokenRefreshView()

        response = view.post(request)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_post_empty_token(self) -> None:
        """Test token refresh with empty token."""
        request = self.factory.post("/api/auth/refresh")
        request.META["HTTP_AUTHORIZATION"] = "Bearer "
        view = TokenRefreshView()

        response = view.post(request)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_post_invalid_token(self) -> None:
        """Test token refresh with invalid token."""
        request = self.factory.post("/api/auth/refresh")
        request.META["HTTP_AUTHORIZATION"] = "Bearer invalid_token"
        view = TokenRefreshView()

        with patch("apps.accounts.views.refresh.JWTService") as mock_jwt:
            mock_jwt.return_value.refresh_token.return_value = None

            response = view.post(request)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_post_refresh_success_but_user_not_found(self) -> None:
        """Test token refresh succeeds but user retrieval fails."""
        request = self.factory.post("/api/auth/refresh")
        request.META["HTTP_AUTHORIZATION"] = "Bearer valid_token"
        view = TokenRefreshView()

        with patch("apps.accounts.views.refresh.JWTService") as mock_jwt:
            mock_jwt.return_value.refresh_token.return_value = "new_token"
            mock_jwt.return_value.get_user_from_token.return_value = None

            response = view.post(request)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_post_successful_refresh(self) -> None:
        """Test successful token refresh."""
        request = self.factory.post("/api/auth/refresh")
        request.META["HTTP_AUTHORIZATION"] = "Bearer valid_token"
        view = TokenRefreshView()

        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.email = "test@example.com"
        mock_user.username = "testuser"
        mock_user.is_staff = False
        mock_user.timezone = "UTC"
        mock_user.language = "en"

        with patch("apps.accounts.views.refresh.JWTService") as mock_jwt:
            mock_jwt.return_value.refresh_token.return_value = "new_token"
            mock_jwt.return_value.get_user_from_token.return_value = mock_user

            response = view.post(request)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["token"] == "new_token"  # type: ignore[index]
        assert response.data["user"]["email"] == "test@example.com"  # type: ignore[index]

    def test_permission_classes(self) -> None:
        """Test view has AllowAny permission."""
        from rest_framework.permissions import AllowAny

        view = TokenRefreshView()
        assert view.permission_classes == [AllowAny]

    def test_authentication_classes(self) -> None:
        """Test view has no authentication classes."""
        view = TokenRefreshView()
        assert view.authentication_classes == []
