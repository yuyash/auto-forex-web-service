"""Unit tests for JWT service."""

from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import jwt
import pytest
from django.conf import settings
from django.contrib.auth import get_user_model

from apps.accounts.services.jwt import JWTService

User = get_user_model()


class TestJWTService:
    """Test JWTService class."""

    def test_generate_token(self):
        """Test generating token."""
        user = Mock(spec=User)
        user.id = 1
        user.email = "test@example.com"
        user.username = "testuser"
        user.is_staff = False

        service = JWTService()
        token = service.generate_token(user)

        assert isinstance(token, str)
        assert len(token) > 0

    def test_decode_token_valid(self):
        """Test decoding valid token."""
        user = Mock(spec=User)
        user.id = 1
        user.email = "test@example.com"
        user.username = "testuser"
        user.is_staff = False

        service = JWTService()
        token = service.generate_token(user)
        payload = service.decode_token(token)

        assert payload is not None
        assert payload["user_id"] == 1
        assert payload["email"] == "test@example.com"

    def test_decode_token_expired(self):
        """Test decoding expired token."""
        service = JWTService()

        # Create an expired token
        payload = {
            "user_id": 1,
            "email": "test@example.com",
            "username": "testuser",
            "is_staff": False,
            "exp": int((datetime.now(UTC) - timedelta(hours=1)).timestamp()),
            "iat": int((datetime.now(UTC) - timedelta(hours=2)).timestamp()),
        }
        token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        if isinstance(token, bytes):
            token = token.decode("utf-8")

        result = service.decode_token(token)
        assert result is None

    def test_decode_token_invalid(self):
        """Test decoding invalid token."""
        service = JWTService()
        result = service.decode_token("invalid_token")
        assert result is None

    @pytest.mark.django_db
    def test_get_user_from_token_valid(self):
        """Test getting user from valid token."""
        user = User.objects.create_user(  # type: ignore[attr-defined]
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

        service = JWTService()
        token = service.generate_token(user)
        retrieved_user = service.get_user_from_token(token)

        assert retrieved_user is not None
        assert retrieved_user.id == user.id
        assert retrieved_user.email == user.email

    def test_get_user_from_token_invalid(self):
        """Test getting user from invalid token."""
        service = JWTService()
        user = service.get_user_from_token("invalid_token")
        assert user is None

    @pytest.mark.django_db
    def test_refresh_token_valid(self):
        """Test refreshing valid token."""
        user = User.objects.create_user(  # type: ignore[attr-defined]
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

        service = JWTService()
        token = service.generate_token(user)
        new_token = service.refresh_token(token)

        assert new_token is not None
        assert isinstance(new_token, str)
        # Tokens will be different due to different timestamps
        # Just verify new token is valid
        payload = service.decode_token(new_token)
        assert payload is not None
        assert payload["user_id"] == user.id

    def test_refresh_token_invalid(self):
        """Test refreshing invalid token."""
        service = JWTService()
        new_token = service.refresh_token("invalid_token")
        assert new_token is None

    @pytest.mark.django_db
    def test_refresh_token_inactive_user(self):
        """Test refreshing token for inactive user."""
        user = User.objects.create_user(  # type: ignore[attr-defined]
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        user.is_active = False
        user.save()

        service = JWTService()
        token = service.generate_token(user)
        new_token = service.refresh_token(token)

        assert new_token is None
