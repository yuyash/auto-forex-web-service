"""Unit tests for JWTService (mocked dependencies)."""

from unittest.mock import MagicMock, patch

from apps.accounts.services.jwt import JWTService


class TestJWTService:
    """Unit tests for JWTService."""

    def test_generate_token(self) -> None:
        """Test generating JWT token."""
        service = JWTService()
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.email = "test@example.com"

        with patch("apps.accounts.services.jwt.jwt.encode") as mock_encode:
            mock_encode.return_value = "test_token"

            token = service.generate_token(mock_user)

        assert token == "test_token"
        mock_encode.assert_called_once()

    def test_decode_token_valid(self) -> None:
        """Test decoding valid token."""
        service = JWTService()

        with patch("apps.accounts.services.jwt.jwt.decode") as mock_decode:
            mock_decode.return_value = {"user_id": 1}

            payload = service.decode_token("valid_token")

        assert payload == {"user_id": 1}

    def test_decode_token_expired(self) -> None:
        """Test decoding expired token."""
        import jwt

        service = JWTService()

        with patch("apps.accounts.services.jwt.jwt.decode") as mock_decode:
            mock_decode.side_effect = jwt.ExpiredSignatureError()

            payload = service.decode_token("expired_token")

        assert payload is None

    def test_decode_token_invalid(self) -> None:
        """Test decoding invalid token."""
        import jwt

        service = JWTService()

        with patch("apps.accounts.services.jwt.jwt.decode") as mock_decode:
            mock_decode.side_effect = jwt.InvalidTokenError()

            payload = service.decode_token("invalid_token")

        assert payload is None

    def test_get_user_from_token_valid(self) -> None:
        """Test getting user from valid token."""
        service = JWTService()

        with patch.object(service, "decode_token") as mock_decode:
            mock_decode.return_value = {"user_id": 1}

            with patch("apps.accounts.services.jwt.User.objects.get") as mock_get:
                mock_user = MagicMock()
                mock_get.return_value = mock_user

                user = service.get_user_from_token("valid_token")

        assert user == mock_user

    def test_get_user_from_token_invalid(self) -> None:
        """Test getting user from invalid token."""
        service = JWTService()

        with patch.object(service, "decode_token") as mock_decode:
            mock_decode.return_value = None

            user = service.get_user_from_token("invalid_token")

        assert user is None

    def test_refresh_token_valid(self) -> None:
        """Test refreshing valid token."""
        service = JWTService()

        mock_user = MagicMock()
        mock_user.is_active = True
        mock_user.is_locked = False

        with patch.object(service, "get_user_from_token") as mock_get_user:
            mock_get_user.return_value = mock_user

            with patch.object(service, "generate_token") as mock_generate:
                mock_generate.return_value = "new_token"

                new_token = service.refresh_token("old_token")

        assert new_token == "new_token"

    def test_refresh_token_invalid(self) -> None:
        """Test refreshing invalid token."""
        service = JWTService()

        with patch.object(service, "get_user_from_token") as mock_get_user:
            mock_get_user.return_value = None

            new_token = service.refresh_token("invalid_token")

        assert new_token is None

    def test_refresh_token_inactive_user(self) -> None:
        """Test refreshing token for inactive user."""
        service = JWTService()

        mock_user = MagicMock()
        mock_user.is_active = False

        with patch.object(service, "get_user_from_token") as mock_get_user:
            mock_get_user.return_value = mock_user

            new_token = service.refresh_token("token")

        assert new_token is None

    def test_refresh_token_locked_user(self) -> None:
        """Test refreshing token for locked user."""
        service = JWTService()

        mock_user = MagicMock()
        mock_user.is_active = True
        mock_user.is_locked = True

        with patch.object(service, "get_user_from_token") as mock_get_user:
            mock_get_user.return_value = mock_user

            new_token = service.refresh_token("token")

        assert new_token is None
