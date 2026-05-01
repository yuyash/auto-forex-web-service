"""Unit tests for TokenRefreshView (mocked dependencies)."""

import json
from unittest.mock import MagicMock, patch

from rest_framework import status
from rest_framework.test import APIRequestFactory

from apps.accounts.views.refresh import TokenRefreshView


class TestTokenRefreshView:
    """Unit tests for TokenRefreshView."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.factory = APIRequestFactory()

    def test_post_missing_refresh_token(self) -> None:
        """Test token refresh without refresh_token in body."""
        request = self.factory.post(
            "/api/accounts/auth/refresh",
            data=json.dumps({}),
            content_type="application/json",
        )
        view = TokenRefreshView.as_view()

        response = view(request)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_post_empty_refresh_token(self) -> None:
        """Test token refresh with empty refresh_token."""
        request = self.factory.post(
            "/api/accounts/auth/refresh",
            data=json.dumps({"refresh_token": ""}),
            content_type="application/json",
        )
        view = TokenRefreshView.as_view()

        response = view(request)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_post_invalid_refresh_token(self) -> None:
        """Test token refresh ignores body tokens and requires cookie token."""
        request = self.factory.post(
            "/api/accounts/auth/refresh",
            data=json.dumps({"refresh_token": "invalid_token"}),
            content_type="application/json",
        )
        view = TokenRefreshView.as_view()

        response = view(request)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_post_successful_refresh(self) -> None:
        """Test successful token refresh with rotation."""
        request = self.factory.post(
            "/api/accounts/auth/refresh",
            data=json.dumps({}),
            content_type="application/json",
            HTTP_COOKIE="refresh_token=valid_refresh_token",
        )
        view = TokenRefreshView.as_view()

        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.email = "test@example.com"
        mock_user.username = "testuser"
        mock_user.is_staff = False
        mock_user.timezone = "UTC"
        mock_user.language = "en"

        with patch("apps.accounts.views.refresh.JWTService") as mock_jwt:
            mock_jwt.return_value.rotate_refresh_token.return_value = (
                "new_access_token",
                "new_refresh_token",
                mock_user,
            )

            response = view(request)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["authenticated"] is True  # type: ignore[index]
        assert "token" not in response.data  # type: ignore[operator]
        assert "refresh_token" not in response.data  # type: ignore[operator]
        assert response.data["user"]["email"] == "test@example.com"  # type: ignore[index]
        assert response.cookies["refresh_token"].value == "new_refresh_token"
        assert response.cookies["access_token"].value == "new_access_token"

    def test_post_invalid_refresh_token_clears_cookie(self) -> None:
        """Test invalid refresh token clears the cookie."""
        request = self.factory.post(
            "/api/accounts/auth/refresh",
            data=json.dumps({}),
            content_type="application/json",
            HTTP_COOKIE="refresh_token=invalid_token",
        )
        view = TokenRefreshView.as_view()

        with patch("apps.accounts.views.refresh.JWTService") as mock_jwt:
            mock_jwt.return_value.rotate_refresh_token.return_value = None

            response = view(request)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.cookies["refresh_token"].value == ""
        assert response.cookies["access_token"].value == ""

    def test_permission_classes(self) -> None:
        """Test view has AllowAny permission."""
        from rest_framework.permissions import AllowAny

        view = TokenRefreshView()
        assert view.permission_classes == [AllowAny]

    def test_authentication_classes(self) -> None:
        """Test view has no authentication classes."""
        view = TokenRefreshView()
        assert view.authentication_classes == []
