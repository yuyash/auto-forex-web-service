"""E2E tests for POST /api/accounts/auth/refresh."""

import pytest


@pytest.mark.django_db
class TestAuthRefresh:
    def test_refresh_success(self, api_client, auth_tokens):
        _, refresh_token = auth_tokens
        api_client.cookies["refresh_token"] = refresh_token
        resp = api_client.post(
            "/api/accounts/auth/refresh",
            {},
            format="json",
        )
        assert resp.status_code == 200
        assert "token" in resp.data
        assert "refresh_token" not in resp.data
        assert resp.cookies["refresh_token"].value

    def test_refresh_rotates_tokens(self, api_client, auth_tokens):
        """Verify that refreshing produces a new, different refresh token."""
        _, old_refresh = auth_tokens
        api_client.cookies["refresh_token"] = old_refresh
        resp = api_client.post(
            "/api/accounts/auth/refresh",
            {},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.cookies["refresh_token"].value != old_refresh
        # Response should include user info
        assert "user" in resp.data

    def test_refresh_invalid_token(self, api_client):
        api_client.cookies["refresh_token"] = "invalid-token"
        resp = api_client.post(
            "/api/accounts/auth/refresh",
            {},
            format="json",
        )
        assert resp.status_code == 401
