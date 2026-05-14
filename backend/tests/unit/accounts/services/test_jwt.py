"""Unit tests for JWTService (mocked dependencies)."""

import contextlib
import threading
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
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
        mock_user.is_staff = False
        mock_user.auth_token_version = 3

        with patch("apps.accounts.services.jwt.jwt.encode") as mock_encode:
            mock_encode.return_value = "test_token"

            token = service.generate_token(mock_user)

        assert token == "test_token"
        mock_encode.assert_called_once()
        payload = mock_encode.call_args.args[0]
        assert payload["user_id"] == 1
        assert payload["auth_version"] == 3
        assert isinstance(payload["jti"], str)

    def test_generate_token_includes_session_id(self) -> None:
        """Session-bound tokens include the tracked user-session id."""
        service = JWTService()
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.is_staff = False
        mock_user.auth_token_version = 0
        mock_session = MagicMock()
        mock_session.pk = 42

        with patch("apps.accounts.services.jwt.jwt.encode") as mock_encode:
            mock_encode.return_value = "test_token"

            token = service.generate_token(mock_user, session=mock_session)

        assert token == "test_token"
        payload = mock_encode.call_args.args[0]
        assert payload["sid"] == 42

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

            with patch("apps.accounts.models.User.objects.get") as mock_get:
                mock_user = MagicMock()
                mock_get.return_value = mock_user

                user = service.get_user_from_token("valid_token")

        assert user == mock_user

    def test_get_user_from_token_rejects_stale_auth_version(self) -> None:
        """Access tokens are rejected after the user's auth version changes."""
        service = JWTService()

        with patch.object(service, "decode_token") as mock_decode:
            mock_decode.return_value = {"user_id": 1, "auth_version": 1}

            with patch("apps.accounts.models.User.objects.get") as mock_get:
                mock_user = MagicMock()
                mock_user.auth_token_version = 2
                mock_get.return_value = mock_user

                user = service.get_user_from_token("stale_token")

        assert user is None

    def test_get_user_from_token_rejects_inactive_session(self) -> None:
        """Session-bound access tokens are rejected after session termination."""
        service = JWTService()

        with patch.object(service, "decode_token") as mock_decode:
            mock_decode.return_value = {"user_id": 1, "auth_version": 2, "sid": 42}

            with (
                patch("apps.accounts.models.User.objects.get") as mock_get,
                patch("apps.accounts.models.security.UserSession.objects.filter") as mock_filter,
            ):
                mock_user = MagicMock()
                mock_user.auth_token_version = 2
                mock_get.return_value = mock_user
                mock_filter.return_value.exists.return_value = False

                user = service.get_user_from_token("terminated_session_token")

        assert user is None
        mock_filter.assert_called_once_with(pk=42, user=mock_user, is_active=True)

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

    def test_hash_refresh_token_is_deterministic(self) -> None:
        """Test refresh-token hashing is stable."""
        token = "refresh-token-value"

        hashed = JWTService.hash_refresh_token(token)

        assert hashed == sha256(token.encode("utf-8")).hexdigest()

    def test_create_refresh_token_stores_hashed_value(self) -> None:
        """Test DB storage uses a digest instead of the raw token."""
        service = JWTService()
        mock_user = MagicMock()
        mock_user.id = 1
        mock_session = MagicMock()

        with patch("apps.accounts.models.RefreshToken.objects.create") as mock_create:
            refresh_token = service.create_refresh_token(mock_user, session=mock_session)

        assert isinstance(refresh_token, str)
        assert refresh_token
        mock_create.assert_called_once()
        assert mock_create.call_args.kwargs["session"] == mock_session
        assert mock_create.call_args.kwargs["token"] == JWTService.hash_refresh_token(refresh_token)
        assert mock_create.call_args.kwargs["token"] != refresh_token

    def test_rotate_refresh_token_allows_only_one_success_during_overlap(self) -> None:
        """Overlapping refresh attempts should yield one success and one replay failure."""

        class FakeRefreshToken:
            def __init__(self, user: MagicMock) -> None:
                self.user = user
                self.user_id = user.id
                self.session = MagicMock()
                self.session_id = 99
                self.revoked_at = None

            @property
            def is_valid(self) -> bool:
                return self.revoked_at is None

            def revoke(self) -> None:
                self.revoked_at = object()
                revoke_event.set()

        service = JWTService()
        user = MagicMock()
        user.id = 1
        user.is_active = True
        user.is_locked = False
        refresh_token = "shared-refresh-token"
        fake_rt = FakeRefreshToken(user)
        revoke_event = threading.Event()
        lookup_lock = threading.Lock()
        lookup_count = 0

        lookup_qs = MagicMock()
        lookup_qs.select_related.return_value = lookup_qs
        lookup_qs.filter.return_value = lookup_qs

        def first_side_effect() -> FakeRefreshToken:
            nonlocal lookup_count
            with lookup_lock:
                lookup_count += 1
                current_lookup = lookup_count

            if current_lookup == 2:
                assert revoke_event.wait(timeout=1), "first refresh attempt never revoked the token"
            return fake_rt

        lookup_qs.first.side_effect = first_side_effect
        manager = MagicMock()
        manager.select_for_update.return_value = lookup_qs

        with (
            patch(
                "apps.accounts.services.jwt.transaction.atomic",
                return_value=contextlib.nullcontext(),
            ),
            patch("apps.accounts.models.RefreshToken.objects", manager),
            patch.object(service, "generate_token", return_value="new-access") as mock_access,
            patch.object(
                service,
                "create_refresh_token",
                return_value="new-refresh",
            ) as mock_refresh,
            patch.object(service, "revoke_refresh_tokens_for_session") as mock_revoke_session,
        ):
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [
                    executor.submit(service.rotate_refresh_token, refresh_token),
                    executor.submit(service.rotate_refresh_token, refresh_token),
                ]
                results = [future.result() for future in futures]

        assert results.count(("new-access", "new-refresh", user)) == 1
        assert results.count(None) == 1
        assert manager.select_for_update.call_count == 2
        assert all(
            call.kwargs == {"of": ("self",)} for call in manager.select_for_update.call_args_list
        )
        assert mock_access.call_count == 1
        assert mock_refresh.call_count == 1
        mock_revoke_session.assert_called_once_with(fake_rt.session)
