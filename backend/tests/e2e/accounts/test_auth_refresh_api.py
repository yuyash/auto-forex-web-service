"""E2E tests for POST /api/accounts/auth/refresh."""

import pytest

CSRF_TOKEN = "a" * 32


def csrf_header(api_client):
    token = api_client.cookies.get("csrftoken")
    value = token.value if token else CSRF_TOKEN
    api_client.cookies["csrftoken"] = value
    return {"HTTP_X_CSRFTOKEN": value}


@pytest.mark.django_db
class TestAuthRefresh:
    def test_refresh_success(self, api_client, auth_tokens):
        _, refresh_token = auth_tokens
        api_client.cookies["refresh_token"] = refresh_token
        resp = api_client.post(
            "/api/accounts/auth/refresh",
            {},
            format="json",
            **csrf_header(api_client),
        )
        assert resp.status_code == 200
        assert resp.data["authenticated"] is True
        assert "token" not in resp.data
        assert "refresh_token" not in resp.data
        assert resp.cookies["access_token"].value
        assert resp.cookies["refresh_token"].value

    def test_refresh_rotates_tokens(self, api_client, auth_tokens):
        """Verify that refreshing produces a new, different refresh token."""
        _, old_refresh = auth_tokens
        api_client.cookies["refresh_token"] = old_refresh
        resp = api_client.post(
            "/api/accounts/auth/refresh",
            {},
            format="json",
            **csrf_header(api_client),
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
            **csrf_header(api_client),
        )
        assert resp.status_code == 401

    def test_refresh_requires_csrf(self, api_client, auth_tokens):
        _, refresh_token = auth_tokens
        api_client.cookies["refresh_token"] = refresh_token
        api_client.cookies.pop("csrftoken", None)

        resp = api_client.post(
            "/api/accounts/auth/refresh",
            {},
            format="json",
        )

        assert resp.status_code == 403
