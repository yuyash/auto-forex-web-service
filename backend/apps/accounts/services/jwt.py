"""apps.accounts.services.jwt

JWT token generation and validation.

This module exposes a class-based API (instantiate where used).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from django.conf import settings

from apps.accounts.models import User


class JWTService:
    """Service for generating and validating JWTs."""

    def __init__(
        self,
        *,
        secret_key: str | None = None,
        algorithm: str | None = None,
        expiration_delta_seconds: int | None = None,
    ) -> None:
        self._secret_key = secret_key if secret_key is not None else settings.JWT_SECRET_KEY
        self._algorithm = algorithm if algorithm is not None else settings.JWT_ALGORITHM
        self._expiration_delta_seconds = (
            expiration_delta_seconds
            if expiration_delta_seconds is not None
            else settings.JWT_EXPIRATION_DELTA
        )

    def generate_token(self, user: Any) -> str:
        """Generate a JWT for the given user."""
        now = datetime.now(UTC)
        expiration = now + timedelta(seconds=int(self._expiration_delta_seconds))

        payload = {
            "user_id": user.id,
            "email": user.email,
            "username": user.username,
            "is_staff": user.is_staff,
            "iat": int(now.timestamp()),
            "exp": int(expiration.timestamp()),
        }

        token = jwt.encode(payload, self._secret_key, algorithm=self._algorithm)
        if isinstance(token, memoryview):
            token = token.tobytes()
        if isinstance(token, (bytes, bytearray)):
            return token.decode("utf-8")
        return token

    def decode_token(self, token: str) -> dict[str, Any] | None:
        """Decode and validate a JWT token."""
        try:
            payload: dict[str, Any] = jwt.decode(
                token, self._secret_key, algorithms=[self._algorithm]
            )
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    def get_user_from_token(self, token: str) -> Any | None:
        """Return user from token if valid."""
        payload = self.decode_token(token)
        if not payload:
            return None

        try:
            return User.objects.get(id=payload["user_id"])
        except User.DoesNotExist:
            return None

    def refresh_token(self, token: str) -> str | None:
        """Refresh an existing JWT token."""
        user = self.get_user_from_token(token)
        if not user:
            return None
        if not user.is_active:
            return None
        if getattr(user, "is_locked", False):
            return None
        return self.generate_token(user)
