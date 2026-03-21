"""E2E tests for POST /api/accounts/auth/logout."""

import pytest


@pytest.mark.django_db
class TestAuthLogout:
    def test_logout_success(self, authenticated_client, auth_tokens):
        _, refresh_token = auth_tokens
        authenticated_client.cookies["refresh_token"] = refresh_token
        resp = authenticated_client.post("/api/accounts/auth/logout", {}, format="json")
        assert resp.status_code == 200
        assert resp.cookies["refresh_token"].value == ""

    def test_logout_unauthenticated(self, api_client):
        resp = api_client.post("/api/accounts/auth/logout", format="json")
        assert resp.status_code == 401
