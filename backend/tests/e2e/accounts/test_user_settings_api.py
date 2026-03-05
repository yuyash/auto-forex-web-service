"""E2E tests for /api/accounts/settings/ and /api/accounts/settings/public."""

import pytest


@pytest.mark.django_db
class TestUserSettings:
    def test_get_settings(self, authenticated_client):
        resp = authenticated_client.get("/api/accounts/settings/")
        assert resp.status_code == 200
        # Validate response structure
        assert "user" in resp.data
        assert "settings" in resp.data

    def test_update_settings(self, authenticated_client):
        resp = authenticated_client.put(
            "/api/accounts/settings/",
            {"timezone": "Asia/Tokyo", "language": "ja"},
            format="json",
        )
        assert resp.status_code == 200

    def test_update_and_verify_persistence(self, authenticated_client):
        """Update settings and verify the change persists on re-fetch."""
        authenticated_client.put(
            "/api/accounts/settings/",
            {"timezone": "US/Eastern", "language": "en"},
            format="json",
        )
        resp = authenticated_client.get("/api/accounts/settings/")
        assert resp.status_code == 200
        # timezone is on the user object, not settings
        assert resp.data["user"]["timezone"] == "US/Eastern"

    def test_get_settings_unauthenticated(self, api_client):
        resp = api_client.get("/api/accounts/settings/")
        assert resp.status_code == 401

    def test_get_public_settings(self, api_client):
        resp = api_client.get("/api/accounts/settings/public")
        assert resp.status_code == 200
