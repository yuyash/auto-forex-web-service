"""E2E tests for POST /api/accounts/auth/register."""

import pytest


@pytest.mark.django_db
class TestAuthRegister:
    def test_register_success(self, api_client):
        resp = api_client.post(
            "/api/accounts/auth/register",
            {
                "username": "newuser",
                "email": "newuser@example.com",
                "password": "StrongPass!123",
                "password_confirm": "StrongPass!123",
            },
            format="json",
        )
        assert resp.status_code in (200, 201), resp.data
        # Validate response structure
        assert "message" in resp.data
        assert "user" in resp.data
        assert "email" in resp.data["user"]

    def test_register_duplicate_email(self, api_client, test_user):
        resp = api_client.post(
            "/api/accounts/auth/register",
            {
                "username": "another",
                "email": test_user.email,
                "password": "StrongPass!123",
                "password_confirm": "StrongPass!123",
            },
            format="json",
        )
        assert resp.status_code == 400

    def test_register_weak_password(self, api_client):
        resp = api_client.post(
            "/api/accounts/auth/register",
            {
                "username": "weakpw",
                "email": "weakpw@example.com",
                "password": "123",
                "password_confirm": "123",
            },
            format="json",
        )
        assert resp.status_code == 400

    def test_register_password_mismatch(self, api_client):
        resp = api_client.post(
            "/api/accounts/auth/register",
            {
                "username": "mismatch",
                "email": "mismatch@example.com",
                "password": "StrongPass!123",
                "password_confirm": "DifferentPass!456",
            },
            format="json",
        )
        assert resp.status_code == 400

    def test_register_missing_fields(self, api_client):
        resp = api_client.post(
            "/api/accounts/auth/register",
            {"email": "partial@example.com"},
            format="json",
        )
        assert resp.status_code == 400
