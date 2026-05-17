"""E2E tests for Snowball strategy via /api/trading/ endpoints.

Covers strategy-configs CRUD and strategy listing/defaults for snowball.
"""

from __future__ import annotations

import pytest

SNOWBALL_FULL_PARAMS = {
    "base_units": 2000,
    "m_pips": 40,
    "trend_lot_size": 2,
    "r_max": 5,
    "f_max": 2,
    "post_r_max_base_factor": 1.5,
    "refill_limit_enabled": True,
    "refill_up_to": 1,
    "n_pips_head": 25,
    "n_pips_tail": 10,
    "n_pips_flat_steps": 1,
    "n_pips_gamma": 1.2,
    "interval_mode": "additive",
    "counter_tp_mode": "fixed",
    "counter_tp_pips": 20,
    "counter_tp_step_amount": 3,
    "counter_tp_multiplier": 1.5,
    "round_step_pips": 0.5,
    "shrink_enabled": True,
    "m_th": 70,
    "m1_th": 50,
    "rebuild_entry_price_mode": "stop_loss_exit",
}


# ===================================================================
# Strategy listing & defaults
# ===================================================================


@pytest.mark.django_db
class TestSnowballStrategyEndpoints:
    """Test /api/trading/strategies/ endpoints for snowball."""

    def test_snowball_in_strategy_list(self, authenticated_client):
        resp = authenticated_client.get("/api/trading/strategies/")
        assert resp.status_code == 200
        strategies = resp.data["strategies"]
        snowball = next((s for s in strategies if s["id"] == "snowball"), None)
        assert snowball is not None
        assert snowball["name"] == "Snowball Strategy"
        assert "config_schema" in snowball

    def test_snowball_defaults(self, authenticated_client):
        resp = authenticated_client.get("/api/trading/strategies/snowball/defaults/")
        assert resp.status_code == 200
        defaults = resp.data["defaults"]
        assert defaults["base_units"] == 1000
        assert defaults["refill_limit_enabled"] is True
        assert defaults["refill_up_to"] == 2

    def test_snowball_schema_has_interval_mode_enum(self, authenticated_client):
        resp = authenticated_client.get("/api/trading/strategies/")
        assert resp.status_code == 200
        strategies = resp.data["strategies"]
        snowball = next(s for s in strategies if s["id"] == "snowball")
        schema = snowball["config_schema"]
        im = schema["properties"]["interval_mode"]
        assert "constant" in im["enum"]
        assert "manual" in im["enum"]
        assert schema["properties"]["refill_limit_enabled"]["group"] == "Rebuild"
        assert schema["properties"]["refill_up_to"]["group"] == "Rebuild"
        assert schema["properties"]["refill_up_to"]["dependsOn"]["field"] == "refill_limit_enabled"
        assert schema["properties"]["refill_up_to"]["minimum"] == 1
        assert schema["properties"]["refill_up_to"]["comparisonRules"][0]["field"] == "r_max"
        assert schema["properties"]["refill_up_to"]["comparisonRules"][0]["operator"] == "lte"


# ===================================================================
# Strategy config CRUD
# ===================================================================


@pytest.mark.django_db
class TestSnowballConfigCRUD:
    """Test CRUD operations for snowball strategy configurations."""

    def test_create_with_full_params(self, authenticated_client):
        resp = authenticated_client.post(
            "/api/trading/strategy-configs/",
            {
                "name": "E2E Snowball Full",
                "strategy_type": "snowball",
                "parameters": SNOWBALL_FULL_PARAMS,
            },
            format="json",
        )
        assert resp.status_code in (200, 201), resp.data
        assert resp.data["strategy_type"] == "snowball"
        assert resp.data["parameters"]["base_units"] == 2000

    def test_create_with_minimal_params(self, authenticated_client):
        """Only required schema fields; rest should default."""
        resp = authenticated_client.post(
            "/api/trading/strategy-configs/",
            {
                "name": "E2E Snowball Minimal",
                "strategy_type": "snowball",
                "parameters": {"base_units": 1000, "m_pips": 50, "r_max": 7},
            },
            format="json",
        )
        assert resp.status_code in (200, 201), resp.data
        params = resp.data["parameters"]
        assert params["interval_mode"] == "constant"

    def test_create_with_empty_params(self, authenticated_client):
        """Empty params should be accepted with defaults."""
        resp = authenticated_client.post(
            "/api/trading/strategy-configs/",
            {
                "name": "E2E Snowball Empty",
                "strategy_type": "snowball",
            },
            format="json",
        )
        assert resp.status_code in (200, 201), resp.data
        params = resp.data["parameters"]
        assert params["base_units"] == 1000

    def test_create_rejects_invalid_base_units(self, authenticated_client):
        resp = authenticated_client.post(
            "/api/trading/strategy-configs/",
            {
                "name": "E2E Snowball Bad Units",
                "strategy_type": "snowball",
                "parameters": {"base_units": 0},
            },
            format="json",
        )
        assert resp.status_code == 400

    def test_create_rejects_invalid_interval_mode(self, authenticated_client):
        resp = authenticated_client.post(
            "/api/trading/strategy-configs/",
            {
                "name": "E2E Snowball Bad Mode",
                "strategy_type": "snowball",
                "parameters": {"interval_mode": "nonexistent"},
            },
            format="json",
        )
        assert resp.status_code == 400

    def test_get_detail(self, authenticated_client):
        create_resp = authenticated_client.post(
            "/api/trading/strategy-configs/",
            {
                "name": "E2E Snowball Detail",
                "strategy_type": "snowball",
                "parameters": SNOWBALL_FULL_PARAMS,
            },
            format="json",
        )
        assert create_resp.status_code in (200, 201)
        config_id = create_resp.data["id"]

        detail_resp = authenticated_client.get(f"/api/trading/strategy-configs/{config_id}/")
        assert detail_resp.status_code == 200
        assert detail_resp.data["name"] == "E2E Snowball Detail"
        assert detail_resp.data["strategy_type"] == "snowball"

    def test_update_params(self, authenticated_client):
        create_resp = authenticated_client.post(
            "/api/trading/strategy-configs/",
            {
                "name": "E2E Snowball Update",
                "strategy_type": "snowball",
                "parameters": SNOWBALL_FULL_PARAMS,
            },
            format="json",
        )
        assert create_resp.status_code in (200, 201)
        config_id = create_resp.data["id"]

        update_resp = authenticated_client.put(
            f"/api/trading/strategy-configs/{config_id}/",
            {
                "name": "E2E Snowball Update",
                "strategy_type": "snowball",
                "parameters": {**SNOWBALL_FULL_PARAMS, "base_units": 5000},
            },
            format="json",
        )
        assert update_resp.status_code == 200
        assert update_resp.data["parameters"]["base_units"] == 5000

    def test_delete(self, authenticated_client):
        create_resp = authenticated_client.post(
            "/api/trading/strategy-configs/",
            {
                "name": "E2E Snowball Delete",
                "strategy_type": "snowball",
                "parameters": SNOWBALL_FULL_PARAMS,
            },
            format="json",
        )
        assert create_resp.status_code in (200, 201)
        config_id = create_resp.data["id"]

        del_resp = authenticated_client.delete(f"/api/trading/strategy-configs/{config_id}/")
        assert del_resp.status_code in (200, 204)

        get_resp = authenticated_client.get(f"/api/trading/strategy-configs/{config_id}/")
        assert get_resp.status_code == 404

    def test_list_includes_snowball(self, authenticated_client):
        authenticated_client.post(
            "/api/trading/strategy-configs/",
            {
                "name": "E2E Snowball List",
                "strategy_type": "snowball",
                "parameters": SNOWBALL_FULL_PARAMS,
            },
            format="json",
        )
        resp = authenticated_client.get(
            "/api/trading/strategy-configs/",
            {"search": "Snowball List"},
        )
        assert resp.status_code == 200
        assert resp.data["count"] >= 1

    def test_unauthenticated_rejected(self, api_client):
        resp = api_client.post(
            "/api/trading/strategy-configs/",
            {
                "name": "Unauth Snowball",
                "strategy_type": "snowball",
                "parameters": {},
            },
            format="json",
        )
        assert resp.status_code == 401


# ===================================================================
# Validation edge cases
# ===================================================================


@pytest.mark.django_db
class TestSnowballValidationEdgeCases:
    """Test parameter validation edge cases through the API."""

    def test_manual_intervals_count_mismatch(self, authenticated_client):
        resp = authenticated_client.post(
            "/api/trading/strategy-configs/",
            {
                "name": "E2E Snowball Manual Bad",
                "strategy_type": "snowball",
                "parameters": {
                    "interval_mode": "manual",
                    "manual_intervals": [10, 20],
                    "r_max": 5,
                },
            },
            format="json",
        )
        assert resp.status_code == 400

    def test_manual_intervals_valid(self, authenticated_client):
        resp = authenticated_client.post(
            "/api/trading/strategy-configs/",
            {
                "name": "E2E Snowball Manual OK",
                "strategy_type": "snowball",
                "parameters": {
                    "interval_mode": "manual",
                    "manual_intervals": [10, 20, 30],
                    "r_max": 3,
                    "n_pips_flat_steps": 1,
                },
            },
            format="json",
        )
        assert resp.status_code in (200, 201), resp.data

    def test_invalid_rebuild_entry_price_mode_rejected(self, authenticated_client):
        resp = authenticated_client.post(
            "/api/trading/strategy-configs/",
            {
                "name": "E2E Snowball Rebuild Mode Bad",
                "strategy_type": "snowball",
                "parameters": {
                    "stop_loss_enabled": True,
                    "rebuild_entry_price_mode": "unknown",
                },
            },
            format="json",
        )
        assert resp.status_code == 400
