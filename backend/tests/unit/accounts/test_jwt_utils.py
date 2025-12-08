"""
Unit tests for JWT utilities module.

Tests cover:
- JWT token generation
- JWT token decoding
- Token validation and expiry
- User retrieval from token
- Token refresh functionality
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from django.conf import settings

import jwt
import pytest

from apps.accounts.jwt_utils import (
    decode_jwt_token,
    generate_jwt_token,
    get_user_from_token,
    refresh_jwt_token,
)


class TestGenerateJwtToken:
    """Test cases for generate_jwt_token function."""

    def test_generate_token_returns_string(self) -> None:
        """Test that generate_jwt_token returns a string."""
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.email = "test@example.com"
        mock_user.username = "testuser"
        mock_user.is_staff = False

        token = generate_jwt_token(mock_user)

        assert isinstance(token, str)
        assert len(token) > 0

    def test_generate_token_contains_user_data(self) -> None:
        """Test that generated token contains correct user data."""
        mock_user = MagicMock()
        mock_user.id = 123
        mock_user.email = "user@example.com"
        mock_user.username = "myuser"
        mock_user.is_staff = True

        token = generate_jwt_token(mock_user)
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
        """Test that generated token has correct expiration."""
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.email = "test@example.com"
        mock_user.username = "testuser"
        mock_user.is_staff = False

        before = datetime.now(timezone.utc)
        token = generate_jwt_token(mock_user)
        after = datetime.now(timezone.utc)

        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )

        # Check that exp is within expected range
        expected_exp_min = int(
            (before + timedelta(seconds=settings.JWT_EXPIRATION_DELTA)).timestamp()
        )
        expected_exp_max = int(
            (after + timedelta(seconds=settings.JWT_EXPIRATION_DELTA)).timestamp()
        )

        assert expected_exp_min <= payload["exp"] <= expected_exp_max + 1

    def test_generate_token_has_issued_at(self) -> None:
        """Test that generated token has iat (issued at) claim."""
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.email = "test@example.com"
        mock_user.username = "testuser"
        mock_user.is_staff = False

        before = int(datetime.now(timezone.utc).timestamp())
        token = generate_jwt_token(mock_user)
        after = int(datetime.now(timezone.utc).timestamp())

        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )

        assert "iat" in payload
        assert before <= payload["iat"] <= after + 1


class TestDecodeJwtToken:
    """Test cases for decode_jwt_token function."""

    def test_decode_valid_token(self) -> None:
        """Test decoding a valid token."""
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.email = "test@example.com"
        mock_user.username = "testuser"
        mock_user.is_staff = False

        token = generate_jwt_token(mock_user)
        payload = decode_jwt_token(token)

        assert payload is not None
        assert payload["user_id"] == 1
        assert payload["email"] == "test@example.com"

    def test_decode_expired_token_returns_none(self) -> None:
        """Test that expired tokens return None."""
        # Create an expired token
        now = datetime.now(timezone.utc)
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
        result = decode_jwt_token(token)

        assert result is None

    def test_decode_invalid_token_returns_none(self) -> None:
        """Test that invalid tokens return None."""
        result = decode_jwt_token("invalid.token.string")
        assert result is None

    def test_decode_tampered_token_returns_none(self) -> None:
        """Test that tampered tokens return None."""
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.email = "test@example.com"
        mock_user.username = "testuser"
        mock_user.is_staff = False

        token = generate_jwt_token(mock_user)
        # Tamper with the token
        tampered_token = token[:-5] + "XXXXX"

        result = decode_jwt_token(tampered_token)
        assert result is None

    def test_decode_token_wrong_secret_returns_none(self) -> None:
        """Test that tokens signed with wrong secret return None."""
        payload = {
            "user_id": 1,
            "email": "test@example.com",
            "username": "testuser",
            "is_staff": False,
            "iat": int(datetime.now(timezone.utc).timestamp()),
            "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
        }

        token = jwt.encode(payload, "wrong-secret-key", algorithm=settings.JWT_ALGORITHM)
        result = decode_jwt_token(token)

        assert result is None

    def test_decode_empty_token_returns_none(self) -> None:
        """Test that empty token returns None."""
        result = decode_jwt_token("")
        assert result is None


@pytest.mark.django_db
class TestGetUserFromToken:
    """Test cases for get_user_from_token function."""

    def test_get_user_from_valid_token(self) -> None:
        """Test getting user from a valid token."""
        from apps.accounts.models import User

        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

        token = generate_jwt_token(user)
        retrieved_user = get_user_from_token(token)

        assert retrieved_user is not None
        assert retrieved_user.id == user.id
        assert retrieved_user.email == user.email

    def test_get_user_from_invalid_token_returns_none(self) -> None:
        """Test that invalid token returns None."""
        result = get_user_from_token("invalid.token.here")
        assert result is None

    def test_get_user_from_token_nonexistent_user(self) -> None:
        """Test that token for deleted user returns None."""
        from apps.accounts.models import User

        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

        token = generate_jwt_token(user)

        # Delete the user
        user.delete()

        result = get_user_from_token(token)
        assert result is None

    def test_get_user_from_expired_token_returns_none(self) -> None:
        """Test that expired token returns None."""
        from apps.accounts.models import User

        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

        # Create an expired token
        now = datetime.now(timezone.utc)
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
        result = get_user_from_token(token)

        assert result is None


@pytest.mark.django_db
class TestRefreshJwtToken:
    """Test cases for refresh_jwt_token function."""

    def test_refresh_valid_token(self) -> None:
        """Test refreshing a valid token returns a valid token."""
        from apps.accounts.models import User

        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

        original_token = generate_jwt_token(user)
        new_token = refresh_jwt_token(original_token)

        assert new_token is not None
        # Verify the new token is valid by decoding it
        decoded = decode_jwt_token(new_token)
        assert decoded is not None
        assert decoded["user_id"] == user.id

        # Verify new token is valid
        payload = decode_jwt_token(new_token)
        assert payload is not None
        assert payload["user_id"] == user.id

    def test_refresh_invalid_token_returns_none(self) -> None:
        """Test that invalid token returns None."""
        result = refresh_jwt_token("invalid.token.here")
        assert result is None

    def test_refresh_token_inactive_user_returns_none(self) -> None:
        """Test that inactive user's token cannot be refreshed."""
        from apps.accounts.models import User

        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        user.is_active = False
        user.save()

        token = generate_jwt_token(user)
        result = refresh_jwt_token(token)

        assert result is None

    def test_refresh_token_locked_user_returns_none(self) -> None:
        """Test that locked user's token cannot be refreshed."""
        from apps.accounts.models import User

        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        user.is_locked = True
        user.save()

        token = generate_jwt_token(user)
        result = refresh_jwt_token(token)

        assert result is None

    def test_refresh_token_generates_new_expiration(self) -> None:
        """Test that refreshed token has new expiration time."""
        from apps.accounts.models import User

        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

        original_token = generate_jwt_token(user)
        original_payload = decode_jwt_token(original_token)

        # Small delay to ensure different timestamps
        import time

        time.sleep(0.1)

        new_token = refresh_jwt_token(original_token)
        new_payload = decode_jwt_token(new_token)

        assert new_payload is not None
        assert original_payload is not None
        # New token should have equal or later expiration
        assert new_payload["exp"] >= original_payload["exp"]
