"""E2E tests for POST /api/accounts/auth/logout."""

import pytest


@pytest.mark.django_db
class TestAuthLogout:
    def test_logout_success(self, authenticated_client, auth_tokens):
        _, refresh_token = auth_tokens
        resp = authenticated_client.post(
            "/api/accounts/auth/logout",
            {"refresh_token": refresh_token},
            format="json",
        )
        assert resp.status_code == 200

    def test_logout_unauthenticated(self, api_client):
        resp = api_client.post("/api/accounts/auth/logout", format="json")
        assert resp.status_code == 401
