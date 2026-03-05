"""E2E tests for /api/market/accounts/ (OANDA account CRUD)."""

import pytest

from tests.e2e.helpers import skip_without_oanda


@pytest.mark.django_db
class TestOandaAccounts:
    def test_list_accounts(self, authenticated_client, oanda_account):
        resp = authenticated_client.get("/api/market/accounts/")
        assert resp.status_code == 200
        assert len(resp.data) >= 1
        # Validate response structure of first account
        account = resp.data[0]
        assert "id" in account
        assert "account_id" in account
        assert "api_type" in account

    def test_create_account(self, authenticated_client):
        resp = authenticated_client.post(
            "/api/market/accounts/",
            {
                "account_id": "101-999-00000000-001",
                "api_token": "test-token-value",
                "api_type": "practice",
            },
            format="json",
        )
        assert resp.status_code in (200, 201), resp.data

    @skip_without_oanda
    def test_get_account_detail_with_live_data(self, authenticated_client, oanda_account):
        resp = authenticated_client.get(f"/api/market/accounts/{oanda_account.id}/")
        assert resp.status_code == 200
        assert "balance" in resp.data

    def test_delete_account(self, authenticated_client, oanda_account):
        resp = authenticated_client.delete(f"/api/market/accounts/{oanda_account.id}/")
        assert resp.status_code in (200, 204)

    def test_accounts_unauthenticated(self, api_client):
        resp = api_client.get("/api/market/accounts/")
        assert resp.status_code == 401
