"""E2E tests for POST /api/accounts/auth/refresh."""

import pytest


@pytest.mark.django_db
class TestAuthRefresh:
    def test_refresh_success(self, api_client, auth_tokens):
        _, refresh_token = auth_tokens
        resp = api_client.post(
            "/api/accounts/auth/refresh",
            {"refresh_token": refresh_token},
            format="json",
        )
        assert resp.status_code == 200
        assert "token" in resp.data
        assert "refresh_token" in resp.data

    def test_refresh_rotates_tokens(self, api_client, auth_tokens):
        """Verify that refreshing produces a new, different refresh token."""
        _, old_refresh = auth_tokens
        resp = api_client.post(
            "/api/accounts/auth/refresh",
            {"refresh_token": old_refresh},
            format="json",
        )
        assert resp.status_code == 200
        # Refresh token is opaque/random, so it must always differ
        assert resp.data["refresh_token"] != old_refresh
        # Response should include user info
        assert "user" in resp.data

    def test_refresh_invalid_token(self, api_client):
        resp = api_client.post(
            "/api/accounts/auth/refresh",
            {"refresh_token": "invalid-token"},
            format="json",
        )
        assert resp.status_code == 401
