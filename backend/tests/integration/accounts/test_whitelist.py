"""
Integration tests for email whitelist admin endpoints.

Tests the following endpoints using live_server:
- GET /api/admin/whitelist/emails
- POST /api/admin/whitelist/emails
- GET /api/admin/whitelist/emails/<id>
- PUT /api/admin/whitelist/emails/<id>
- DELETE /api/admin/whitelist/emails/<id>
"""

from django.contrib.auth import get_user_model

import pytest
import requests

from apps.accounts.models import WhitelistedEmail

User = get_user_model()


@pytest.fixture
def whitelist_entry(db, admin_user):
    """Create a test whitelist entry."""
    return WhitelistedEmail.objects.create(
        email_pattern="*@example.com",
        description="Test domain whitelist",
        is_active=True,
        created_by=admin_user,
    )


@pytest.mark.django_db(transaction=True)
class TestWhitelistList:
    """Integration tests for GET whitelist emails endpoint."""

    def test_list_whitelist_as_admin(self, live_server, admin_user, admin_auth_headers):
        """Test listing whitelist entries as admin."""
        url = f"{live_server.url}/api/admin/whitelist/emails"

        response = requests.get(url, headers=admin_auth_headers, timeout=10)

        assert response.status_code == 200
        json_data = response.json()
        assert isinstance(json_data, list)

    def test_list_whitelist_unauthenticated(self, live_server):
        """Test listing whitelist fails when not authenticated."""
        url = f"{live_server.url}/api/admin/whitelist/emails"

        response = requests.get(url, timeout=10)

        assert response.status_code == 401

    def test_list_whitelist_as_non_admin(self, live_server, test_user, auth_headers):
        """Test listing whitelist fails for non-admin users."""
        url = f"{live_server.url}/api/admin/whitelist/emails"

        response = requests.get(url, headers=auth_headers, timeout=10)

        assert response.status_code == 403

    def test_list_whitelist_filter_active(
        self, live_server, admin_user, admin_auth_headers, whitelist_entry
    ):
        """Test filtering whitelist by active status."""
        url = f"{live_server.url}/api/admin/whitelist/emails?is_active=true"

        response = requests.get(url, headers=admin_auth_headers, timeout=10)

        assert response.status_code == 200
        json_data = response.json()
        for entry in json_data:
            assert entry["is_active"] is True

    def test_list_whitelist_with_entries(
        self, live_server, admin_user, admin_auth_headers, whitelist_entry
    ):
        """Test listing whitelist returns existing entries."""
        url = f"{live_server.url}/api/admin/whitelist/emails"

        response = requests.get(url, headers=admin_auth_headers, timeout=10)

        assert response.status_code == 200
        json_data = response.json()
        assert len(json_data) >= 1
        # Find our test entry
        patterns = [entry["email_pattern"] for entry in json_data]
        assert "*@example.com" in patterns


@pytest.mark.django_db(transaction=True)
class TestWhitelistCreate:
    """Integration tests for POST whitelist emails endpoint."""

    def test_create_whitelist_entry_as_admin(self, live_server, admin_user, admin_auth_headers):
        """Test creating a whitelist entry as admin."""
        url = f"{live_server.url}/api/admin/whitelist/emails"
        data = {
            "email_pattern": "*@newdomain.com",
            "description": "New domain whitelist",
            "is_active": True,
        }

        response = requests.post(url, json=data, headers=admin_auth_headers, timeout=10)

        assert response.status_code == 201
        json_data = response.json()
        assert json_data["email_pattern"] == "*@newdomain.com"
        assert json_data["description"] == "New domain whitelist"
        assert json_data["is_active"] is True

    def test_create_whitelist_unauthenticated(self, live_server):
        """Test creating whitelist fails when not authenticated."""
        url = f"{live_server.url}/api/admin/whitelist/emails"
        data = {"email_pattern": "*@test.com"}

        response = requests.post(url, json=data, timeout=10)

        assert response.status_code == 401

    def test_create_whitelist_as_non_admin(self, live_server, test_user, auth_headers):
        """Test creating whitelist fails for non-admin users."""
        url = f"{live_server.url}/api/admin/whitelist/emails"
        data = {"email_pattern": "*@test.com"}

        response = requests.post(url, json=data, headers=auth_headers, timeout=10)

        assert response.status_code == 403

    def test_create_whitelist_exact_email(self, live_server, admin_user, admin_auth_headers):
        """Test creating whitelist with exact email pattern."""
        url = f"{live_server.url}/api/admin/whitelist/emails"
        data = {
            "email_pattern": "specific@example.com",
            "description": "Specific user whitelist",
        }

        response = requests.post(url, json=data, headers=admin_auth_headers, timeout=10)

        assert response.status_code == 201
        json_data = response.json()
        assert json_data["email_pattern"] == "specific@example.com"

    def test_create_whitelist_duplicate_pattern(
        self, live_server, admin_user, admin_auth_headers, whitelist_entry
    ):
        """Test creating whitelist with duplicate pattern fails."""
        url = f"{live_server.url}/api/admin/whitelist/emails"
        data = {
            "email_pattern": whitelist_entry.email_pattern,
            "description": "Duplicate",
        }

        response = requests.post(url, json=data, headers=admin_auth_headers, timeout=10)

        assert response.status_code == 400

    def test_create_whitelist_without_pattern(self, live_server, admin_user, admin_auth_headers):
        """Test creating whitelist without email pattern fails."""
        url = f"{live_server.url}/api/admin/whitelist/emails"
        data = {"description": "No pattern"}

        response = requests.post(url, json=data, headers=admin_auth_headers, timeout=10)

        assert response.status_code == 400


@pytest.mark.django_db(transaction=True)
class TestWhitelistDetail:
    """Integration tests for whitelist detail endpoints (GET, PUT, DELETE by ID)."""

    def test_get_whitelist_entry_as_admin(
        self, live_server, admin_user, admin_auth_headers, whitelist_entry
    ):
        """Test getting a specific whitelist entry as admin."""
        url = f"{live_server.url}/api/admin/whitelist/emails/{whitelist_entry.id}"

        response = requests.get(url, headers=admin_auth_headers, timeout=10)

        assert response.status_code == 200
        json_data = response.json()
        assert json_data["email_pattern"] == whitelist_entry.email_pattern

    def test_get_whitelist_entry_not_found(self, live_server, admin_user, admin_auth_headers):
        """Test getting non-existent whitelist entry returns 404."""
        url = f"{live_server.url}/api/admin/whitelist/emails/99999"

        response = requests.get(url, headers=admin_auth_headers, timeout=10)

        assert response.status_code == 404

    def test_update_whitelist_entry_as_admin(
        self, live_server, admin_user, admin_auth_headers, whitelist_entry
    ):
        """Test updating a whitelist entry as admin."""
        url = f"{live_server.url}/api/admin/whitelist/emails/{whitelist_entry.id}"
        data = {
            "description": "Updated description",
            "is_active": False,
        }

        response = requests.put(url, json=data, headers=admin_auth_headers, timeout=10)

        assert response.status_code == 200
        json_data = response.json()
        assert json_data["description"] == "Updated description"
        assert json_data["is_active"] is False

    def test_update_whitelist_unauthenticated(self, live_server, whitelist_entry):
        """Test updating whitelist fails when not authenticated."""
        url = f"{live_server.url}/api/admin/whitelist/emails/{whitelist_entry.id}"
        data = {"description": "New description"}

        response = requests.put(url, json=data, timeout=10)

        assert response.status_code == 401

    def test_update_whitelist_as_non_admin(
        self, live_server, test_user, auth_headers, whitelist_entry
    ):
        """Test updating whitelist fails for non-admin users."""
        url = f"{live_server.url}/api/admin/whitelist/emails/{whitelist_entry.id}"
        data = {"description": "New description"}

        response = requests.put(url, json=data, headers=auth_headers, timeout=10)

        assert response.status_code == 403

    def test_delete_whitelist_entry_as_admin(
        self, live_server, admin_user, admin_auth_headers, whitelist_entry
    ):
        """Test deleting a whitelist entry as admin."""
        url = f"{live_server.url}/api/admin/whitelist/emails/{whitelist_entry.id}"

        response = requests.delete(url, headers=admin_auth_headers, timeout=10)

        # API returns 200 with success message
        assert response.status_code == 200
        json_data = response.json()
        assert "message" in json_data

        # Verify it's deleted
        get_response = requests.get(url, headers=admin_auth_headers, timeout=10)
        assert get_response.status_code == 404

    def test_delete_whitelist_unauthenticated(self, live_server, whitelist_entry):
        """Test deleting whitelist fails when not authenticated."""
        url = f"{live_server.url}/api/admin/whitelist/emails/{whitelist_entry.id}"

        response = requests.delete(url, timeout=10)

        assert response.status_code == 401

    def test_delete_whitelist_as_non_admin(
        self, live_server, test_user, auth_headers, whitelist_entry
    ):
        """Test deleting whitelist fails for non-admin users."""
        url = f"{live_server.url}/api/admin/whitelist/emails/{whitelist_entry.id}"

        response = requests.delete(url, headers=auth_headers, timeout=10)

        assert response.status_code == 403

    def test_delete_nonexistent_whitelist(self, live_server, admin_user, admin_auth_headers):
        """Test deleting non-existent whitelist entry returns 404."""
        url = f"{live_server.url}/api/admin/whitelist/emails/99999"

        response = requests.delete(url, headers=admin_auth_headers, timeout=10)

        assert response.status_code == 404
