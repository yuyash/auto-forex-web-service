"""Unit tests for apps.accounts.services.jwt (JWTService)."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import jwt
import pytest
from django.conf import settings

from apps.accounts.services.jwt import JWTService


class TestGenerateJwtToken:
    """Test cases for JWTService.generate_token."""

    def test_generate_token_returns_string(self) -> None:
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.email = "test@example.com"
        mock_user.username = "testuser"
        mock_user.is_staff = False

        token = JWTService().generate_token(mock_user)

        assert isinstance(token, str)
        assert len(token) > 0

    def test_generate_token_contains_user_data(self) -> None:
        mock_user = MagicMock()
        mock_user.id = 123
        mock_user.email = "user@example.com"
        mock_user.username = "myuser"
        mock_user.is_staff = True

        token = JWTService().generate_token(mock_user)
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )

        assert payload["user_id"] == 123
        assert payload["email"] == "user@example.com"
        assert payload["username"] == "myuser"
        assert payload["is_staff"] is True

    def test_generate_token_has_expiration(self) -> None:
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.email = "test@example.com"
        mock_user.username = "testuser"
        mock_user.is_staff = False

        before = datetime.now(UTC)
        token = JWTService().generate_token(mock_user)
        after = datetime.now(UTC)

        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )

        expected_exp_min = int(
            (before + timedelta(seconds=settings.JWT_EXPIRATION_DELTA)).timestamp()
        )
        expected_exp_max = int(
            (after + timedelta(seconds=settings.JWT_EXPIRATION_DELTA)).timestamp()
        )

        assert expected_exp_min <= payload["exp"] <= expected_exp_max + 1

    def test_generate_token_has_issued_at(self) -> None:
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.email = "test@example.com"
        mock_user.username = "testuser"
        mock_user.is_staff = False

        before = int(datetime.now(UTC).timestamp())
        token = JWTService().generate_token(mock_user)
        after = int(datetime.now(UTC).timestamp())

        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )

        assert "iat" in payload
        assert before <= payload["iat"] <= after + 1


class TestDecodeJwtToken:
    """Test cases for JWTService.decode_token."""

    def test_decode_valid_token(self) -> None:
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.email = "test@example.com"
        mock_user.username = "testuser"
        mock_user.is_staff = False

        token = JWTService().generate_token(mock_user)
        payload = JWTService().decode_token(token)

        assert payload is not None
        assert payload["user_id"] == 1
        assert payload["email"] == "test@example.com"

    def test_decode_expired_token_returns_none(self) -> None:
        now = datetime.now(UTC)
        expired_time = now - timedelta(hours=1)

        payload = {
            "user_id": 1,
            "email": "test@example.com",
            "username": "testuser",
            "is_staff": False,
            "iat": int(expired_time.timestamp()),
            "exp": int((expired_time + timedelta(seconds=1)).timestamp()),
        }

        token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        result = JWTService().decode_token(token.decode() if isinstance(token, bytes) else token)

        assert result is None

    def test_decode_invalid_token_returns_none(self) -> None:
        result = JWTService().decode_token("invalid.token.string")
        assert result is None

    def test_decode_tampered_token_returns_none(self) -> None:
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.email = "test@example.com"
        mock_user.username = "testuser"
        mock_user.is_staff = False

        token = JWTService().generate_token(mock_user)
        tampered_token = token[:-5] + "XXXXX"

        result = JWTService().decode_token(tampered_token)
        assert result is None

    def test_decode_token_wrong_secret_returns_none(self) -> None:
        payload = {
            "user_id": 1,
            "email": "test@example.com",
            "username": "testuser",
            "is_staff": False,
            "iat": int(datetime.now(UTC).timestamp()),
            "exp": int((datetime.now(UTC) + timedelta(hours=1)).timestamp()),
        }

        token = jwt.encode(payload, "wrong-secret-key", algorithm=settings.JWT_ALGORITHM)
        result = JWTService().decode_token(token.decode() if isinstance(token, bytes) else token)

        assert result is None

    def test_decode_empty_token_returns_none(self) -> None:
        result = JWTService().decode_token("")
        assert result is None


@pytest.mark.django_db
class TestGetUserFromToken:
    """Test cases for JWTService.get_user_from_token."""

    def test_get_user_from_valid_token(self) -> None:
        from apps.accounts.models import User

        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

        token = JWTService().generate_token(user)
        retrieved_user = JWTService().get_user_from_token(token)

        assert retrieved_user is not None
        assert retrieved_user.id == user.id
        assert retrieved_user.email == user.email

    def test_get_user_from_invalid_token_returns_none(self) -> None:
        result = JWTService().get_user_from_token("invalid.token.here")
        assert result is None

    def test_get_user_from_token_nonexistent_user(self) -> None:
        from apps.accounts.models import User

        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

        token = JWTService().generate_token(user)
        user.delete()

        result = JWTService().get_user_from_token(token)
        assert result is None

    def test_get_user_from_expired_token_returns_none(self) -> None:
        from apps.accounts.models import User

        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

        now = datetime.now(UTC)
        expired_time = now - timedelta(hours=1)

        payload = {
            "user_id": user.id,
            "email": user.email,
            "username": user.username,
            "is_staff": user.is_staff,
            "iat": int(expired_time.timestamp()),
            "exp": int((expired_time + timedelta(seconds=1)).timestamp()),
        }

        token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        result = JWTService().get_user_from_token(
            token.decode() if isinstance(token, bytes) else token
        )

        assert result is None
