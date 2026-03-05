"""E2E tests for POST /api/accounts/auth/login."""

import pytest

from tests.e2e.helpers import E2E_PASSWORD


@pytest.mark.django_db
class TestAuthLogin:
    def test_login_success(self, api_client, test_user):
        resp = api_client.post(
            "/api/accounts/auth/login",
            {"email": test_user.email, "password": E2E_PASSWORD},
            format="json",
        )
        assert resp.status_code == 200
        # Validate response structure
        assert "token" in resp.data
        assert "refresh_token" in resp.data
        assert "user" in resp.data
        user = resp.data["user"]
        assert "id" in user
        assert "email" in user
        assert "username" in user

    def test_login_wrong_password(self, api_client, test_user):
        resp = api_client.post(
            "/api/accounts/auth/login",
            {"email": test_user.email, "password": "wrong"},
            format="json",
        )
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, api_client):
        resp = api_client.post(
            "/api/accounts/auth/login",
            {"email": "nobody@example.com", "password": "whatever"},
            format="json",
        )
        assert resp.status_code == 401

    def test_login_missing_fields(self, api_client):
        resp = api_client.post(
            "/api/accounts/auth/login",
            {"email": "test@example.com"},
            format="json",
        )
        assert resp.status_code in (400, 401)
