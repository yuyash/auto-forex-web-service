"""apps.accounts.services.jwt

JWT token generation and validation.

This module exposes a class-based API (instantiate where used).
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import jwt
from django.conf import settings

if TYPE_CHECKING:
    pass


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
        from apps.accounts.models import User

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

    # ------------------------------------------------------------------
    # Refresh token (opaque, DB-backed)
    # ------------------------------------------------------------------

    def create_refresh_token(
        self,
        user: Any,
        *,
        ip_address: str | None = None,
        user_agent: str = "",
    ) -> str:
        """Create an opaque refresh token stored in the database."""
        from apps.accounts.models import RefreshToken

        token_value = secrets.token_urlsafe(48)
        expires_at = datetime.now(UTC) + timedelta(
            seconds=int(getattr(settings, "REFRESH_TOKEN_EXPIRATION", 604800)),
        )

        RefreshToken.objects.create(
            user=user,
            token=token_value,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent or "",
        )
        return token_value

    def rotate_refresh_token(
        self,
        refresh_token_value: str,
        *,
        ip_address: str | None = None,
        user_agent: str = "",
    ) -> tuple[str, str, Any] | None:
        """Validate a refresh token, revoke it, and issue new access + refresh tokens.

        If the token has already been revoked (replay attack), all of the
        user's refresh tokens are revoked as a safety measure (family
        revocation).

        Returns ``(new_access_token, new_refresh_token, user)`` or ``None``.
        """
        from apps.accounts.models import RefreshToken

        try:
            rt = RefreshToken.objects.select_related("user").get(token=refresh_token_value)
        except RefreshToken.DoesNotExist:
            return None

        # --- Family revocation: detect reuse of a revoked token ----------
        if rt.revoked_at is not None:
            # Someone is replaying an already-used token → compromise assumed.
            self.revoke_all_refresh_tokens(rt.user)
            import logging

            logging.getLogger(__name__).warning(
                "Refresh token reuse detected for user %s — all tokens revoked",
                rt.user_id,
            )
            return None

        # Normal expiry check
        if not rt.is_valid:
            return None

        user = rt.user
        if not user.is_active or getattr(user, "is_locked", False):
            return None

        # Revoke old token
        rt.revoke()

        # Issue new pair
        new_access = self.generate_token(user)
        new_refresh = self.create_refresh_token(
            user,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return new_access, new_refresh, user

    @staticmethod
    def revoke_all_refresh_tokens(user: Any) -> int:
        """Revoke all active refresh tokens for a user. Returns count revoked."""
        from django.utils import timezone

        from apps.accounts.models import RefreshToken

        return RefreshToken.objects.filter(
            user=user,
            revoked_at__isnull=True,
        ).update(revoked_at=timezone.now())
