"""Unit tests for JWTAuthMiddleware (mocked dependencies)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apps.accounts.middlewares.jwt import JWTAuthMiddleware, jwt_auth_middleware_stack


class TestJWTAuthMiddleware:
    """Unit tests for JWTAuthMiddleware."""

    def test_init(self) -> None:
        """Test middleware initialization."""
        inner = MagicMock()
        middleware = JWTAuthMiddleware(inner)

        assert middleware.inner == inner

    @pytest.mark.asyncio
    async def test_call_non_websocket(self) -> None:
        """Test middleware passes through non-websocket connections."""
        inner = AsyncMock()
        middleware = JWTAuthMiddleware(inner)

        scope = {"type": "http"}
        receive = MagicMock()
        send = MagicMock()

        # Should pass through to parent
        await middleware(scope, receive, send)

    @pytest.mark.asyncio
    async def test_call_websocket_with_token_in_query(self) -> None:
        """Test middleware authenticates WebSocket with token in query string."""
        inner = AsyncMock()
        middleware = JWTAuthMiddleware(inner)

        scope = {
            "type": "websocket",
            "query_string": b"token=test_token",
            "headers": [],
        }
        receive = MagicMock()
        send = MagicMock()

        mock_user = MagicMock()
        mock_user.username = "testuser"

        with patch.object(middleware, "get_user_from_token", return_value=mock_user):
            await middleware(scope, receive, send)

        assert scope["user"] == mock_user

    @pytest.mark.asyncio
    async def test_call_websocket_without_token(self) -> None:
        """Test middleware handles WebSocket without token."""
        from django.contrib.auth.models import AnonymousUser

        inner = AsyncMock()
        middleware = JWTAuthMiddleware(inner)

        scope = {
            "type": "websocket",
            "query_string": b"",
            "headers": [],
        }
        receive = MagicMock()
        send = MagicMock()

        await middleware(scope, receive, send)

        assert isinstance(scope["user"], AnonymousUser)


class TestJWTAuthMiddlewareStack:
    """Unit tests for jwt_auth_middleware_stack function."""

    def test_jwt_auth_middleware_stack(self) -> None:
        """Test jwt_auth_middleware_stack wraps inner application."""
        inner = MagicMock()
        result = jwt_auth_middleware_stack(inner)

        assert isinstance(result, JWTAuthMiddleware)
        assert result.inner == inner
