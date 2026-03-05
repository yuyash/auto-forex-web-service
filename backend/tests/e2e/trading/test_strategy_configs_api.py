"""E2E tests for /api/trading/strategy-configs/."""

import pytest


@pytest.mark.django_db
class TestStrategyConfigs:
    def test_list_configs(self, authenticated_client):
        resp = authenticated_client.get("/api/trading/strategy-configs/")
        assert resp.status_code == 200

    def test_list_configs_response_structure(self, authenticated_client, strategy_config):
        """Verify paginated response structure."""
        resp = authenticated_client.get("/api/trading/strategy-configs/")
        assert resp.status_code == 200
        assert "count" in resp.data
        assert "next" in resp.data
        assert "previous" in resp.data
        assert "results" in resp.data
        assert resp.data["count"] >= 1

    def test_list_configs_pagination(self, authenticated_client, strategy_config):
        """Verify page_size limits results."""
        resp = authenticated_client.get("/api/trading/strategy-configs/", {"page_size": 1})
        assert resp.status_code == 200
        assert "count" in resp.data
        assert "results" in resp.data
        assert len(resp.data["results"]) <= 1

    def test_list_configs_search(self, authenticated_client, strategy_config):
        """Verify search filter finds configs by name."""
        resp = authenticated_client.get("/api/trading/strategy-configs/", {"search": "Floor"})
        assert resp.status_code == 200
        assert resp.data["count"] >= 1

    def test_create_config(self, authenticated_client):
        resp = authenticated_client.post(
            "/api/trading/strategy-configs/",
            {
                "name": "E2E New Config",
                "strategy_type": "floor",
                "parameters": {
                    "instrument": "USD_JPY",
                    "base_lot_size": 1.0,
                    "retracement_pips": 30.0,
                    "take_profit_pips": 25.0,
                    "max_layers": 3,
                    "max_retracements_per_layer": 10,
                },
            },
            format="json",
        )
        assert resp.status_code in (200, 201), resp.data

    def test_get_config_detail(self, authenticated_client, strategy_config):
        resp = authenticated_client.get(f"/api/trading/strategy-configs/{strategy_config.id}/")
        assert resp.status_code == 200
        assert resp.data["name"] == strategy_config.name

    def test_delete_config(self, authenticated_client, strategy_config):
        resp = authenticated_client.delete(f"/api/trading/strategy-configs/{strategy_config.id}/")
        assert resp.status_code in (200, 204)

    def test_configs_unauthenticated(self, api_client):
        resp = api_client.get("/api/trading/strategy-configs/")
        assert resp.status_code == 401
