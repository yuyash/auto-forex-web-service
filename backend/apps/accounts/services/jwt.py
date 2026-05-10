"""apps.accounts.services.jwt

JWT token generation and validation.

This module exposes a class-based API (instantiate where used).
"""

from __future__ import annotations

import logging
import secrets
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import TYPE_CHECKING, Any

import jwt
from django.conf import settings
from django.db import transaction

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class JWTService:
    """Service for generating and validating JWTs."""

    @staticmethod
    def hash_refresh_token(token: str) -> str:
        """Return a deterministic digest for refresh-token storage and lookup."""
        return sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _is_sha256_digest(value: str) -> bool:
        """Return True when the value matches the persisted digest format."""
        return len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)

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

    def generate_token(self, user: Any, *, session: Any | None = None) -> str:
        """Generate a JWT for the given user."""
        now = datetime.now(UTC)
        expiration = now + timedelta(seconds=int(self._expiration_delta_seconds))

        payload = {
            "user_id": user.id,
            "is_staff": user.is_staff,
            "jti": secrets.token_urlsafe(24),
            "auth_version": int(getattr(user, "auth_token_version", 0) or 0),
            "iat": int(now.timestamp()),
            "exp": int(expiration.timestamp()),
        }
        if session is not None and getattr(session, "pk", None):
            payload["sid"] = int(session.pk)

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
        return self.get_user_from_payload(payload)

    def get_user_from_payload(self, payload: dict[str, Any]) -> Any | None:
        """Return the token user after server-side revocation checks."""
        from apps.accounts.models import User
        from apps.accounts.models.security import UserSession

        user_id = payload.get("user_id")
        if user_id is None:
            return None

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return None

        auth_version = payload.get("auth_version")
        if auth_version is not None:
            try:
                token_version_matches = int(auth_version) == int(user.auth_token_version)
            except (TypeError, ValueError):
                return None
            if not token_version_matches:
                return None

        session_id = payload.get("sid")
        if session_id is not None:
            session_is_active = UserSession.objects.filter(
                pk=session_id,
                user=user,
                is_active=True,
            ).exists()
            if not session_is_active:
                return None

        return user

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
        session: Any | None = None,
        ip_address: str | None = None,
        user_agent: str = "",
    ) -> str:
        """Create an opaque refresh token stored in the database."""
        from apps.accounts.models import RefreshToken

        token_value = secrets.token_urlsafe(48)
        token_hash = self.hash_refresh_token(token_value)
        expires_at = datetime.now(UTC) + timedelta(
            seconds=int(getattr(settings, "REFRESH_TOKEN_EXPIRATION", 604800)),
        )

        RefreshToken.objects.create(
            user=user,
            session=session,
            token=token_hash,
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

        token_hash = self.hash_refresh_token(refresh_token_value)

        with transaction.atomic():
            rt = (
                RefreshToken.objects.select_for_update()
                .select_related("user", "session")
                .filter(token=token_hash)
                .first()
            )
            if rt is None:
                # Temporary rollout compatibility for rows created before the
                # hashing migration. Once all environments are migrated, these
                # rows should no longer exist.
                rt = (
                    RefreshToken.objects.select_for_update()
                    .select_related("user", "session")
                    .filter(token=refresh_token_value)
                    .first()
                )
            if rt is None:
                return None

            # --- Family revocation: detect reuse of a revoked token ----------
            if rt.revoked_at is not None:
                # Someone is replaying an already-used token -> compromise assumed.
                if rt.session_id:
                    self.revoke_refresh_tokens_for_session(rt.session)
                else:
                    self.revoke_all_refresh_tokens(rt.user)
                logger.warning(
                    "Refresh token reuse detected for user %s - refresh tokens revoked for %s",
                    rt.user_id,
                    f"session {rt.session_id}" if rt.session_id else "entire account",
                )
                return None

            # Normal expiry check
            if not rt.is_valid:
                return None

            user = rt.user
            if not user.is_active or getattr(user, "is_locked", False):
                return None
            if rt.session_id and not rt.session.is_active:
                return None

            # Revoke old token while the row lock is held to serialize rotation.
            rt.revoke()

            # Issue new pair within the same transaction so competing refreshes
            # observe the revoked state after the first rotation commits.
            new_access = self.generate_token(user, session=rt.session)
            new_refresh = self.create_refresh_token(
                user,
                session=rt.session,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            return new_access, new_refresh, user

    @staticmethod
    def revoke_refresh_tokens_for_session(session: Any | None) -> int:
        """Revoke all active refresh tokens bound to one UserSession."""
        from django.utils import timezone

        from apps.accounts.models import RefreshToken

        if session is None:
            return 0

        return RefreshToken.objects.filter(
            session=session,
            revoked_at__isnull=True,
        ).update(revoked_at=timezone.now())

    @staticmethod
    def revoke_all_refresh_tokens(user: Any) -> int:
        """Revoke all active refresh tokens for a user. Returns count revoked."""
        from django.utils import timezone

        from apps.accounts.models import RefreshToken

        return RefreshToken.objects.filter(
            user=user,
            revoked_at__isnull=True,
        ).update(revoked_at=timezone.now())
