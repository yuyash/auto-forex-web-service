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
    "dynamic_tp_enabled": False,
    "atr_timeframe": "M5",
    "shrink_enabled": True,
    "m_th": 70,
    "lock_enabled": True,
    "n_th": 85,
    "m_pips_min": 12,
    "m_pips_max": 55,
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
        assert defaults["atr_timeframe"] == "M1"

    def test_snowball_schema_has_atr_timeframe_enum(self, authenticated_client):
        resp = authenticated_client.get("/api/trading/strategies/")
        assert resp.status_code == 200
        strategies = resp.data["strategies"]
        snowball = next(s for s in strategies if s["id"] == "snowball")
        schema = snowball["config_schema"]
        atr_tf = schema["properties"]["atr_timeframe"]
        assert atr_tf["enum"] == ["M1", "M5", "M15", "M30", "H1", "H4"]


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
                "parameters": {"base_units": 1000, "m_pips": 50, "r_max": 7, "m_pips_max": 55},
            },
            format="json",
        )
        assert resp.status_code in (200, 201), resp.data
        params = resp.data["parameters"]
        assert params["interval_mode"] == "constant"
        assert params["atr_timeframe"] == "M1"

    def test_create_with_empty_params(self, authenticated_client):
        """Empty params should be accepted (needs m_pips_max >= default m_pips)."""
        resp = authenticated_client.post(
            "/api/trading/strategy-configs/",
            {
                "name": "E2E Snowball Empty",
                "strategy_type": "snowball",
                "parameters": {"m_pips_max": 55},
            },
            format="json",
        )
        assert resp.status_code in (200, 201), resp.data
        params = resp.data["parameters"]
        assert params["base_units"] == 1000
        assert params["atr_timeframe"] == "M1"

    def test_create_with_lowercase_timeframe(self, authenticated_client):
        """Regression: lowercase atr_timeframe must be accepted and normalised."""
        resp = authenticated_client.post(
            "/api/trading/strategy-configs/",
            {
                "name": "E2E Snowball Lowercase TF",
                "strategy_type": "snowball",
                "parameters": {"atr_timeframe": "m1", "m_pips_max": 55},
            },
            format="json",
        )
        assert resp.status_code in (200, 201), resp.data
        assert resp.data["parameters"]["atr_timeframe"] == "M1"

    @pytest.mark.parametrize("timeframe", ["m5", "M15", "h1", "H4", "m30"])
    def test_create_with_various_timeframes(self, authenticated_client, timeframe):
        resp = authenticated_client.post(
            "/api/trading/strategy-configs/",
            {
                "name": f"E2E Snowball TF {timeframe}",
                "strategy_type": "snowball",
                "parameters": {"atr_timeframe": timeframe, "m_pips_max": 55},
            },
            format="json",
        )
        assert resp.status_code in (200, 201), resp.data
        assert resp.data["parameters"]["atr_timeframe"] == timeframe.upper()

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

    def test_create_rejects_invalid_atr_timeframe(self, authenticated_client):
        resp = authenticated_client.post(
            "/api/trading/strategy-configs/",
            {
                "name": "E2E Snowball Bad TF",
                "strategy_type": "snowball",
                "parameters": {"atr_timeframe": "INVALID"},
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
                    "m_pips_max": 55,
                },
            },
            format="json",
        )
        assert resp.status_code in (200, 201), resp.data

    def test_m_th_n_th_ordering_rejected(self, authenticated_client):
        resp = authenticated_client.post(
            "/api/trading/strategy-configs/",
            {
                "name": "E2E Snowball Threshold Bad",
                "strategy_type": "snowball",
                "parameters": {
                    "shrink_enabled": True,
                    "lock_enabled": True,
                    "m_th": 90,
                    "n_th": 85,
                },
            },
            format="json",
        )
        assert resp.status_code == 400

    def test_rebalance_ratio_ordering_rejected(self, authenticated_client):
        resp = authenticated_client.post(
            "/api/trading/strategy-configs/",
            {
                "name": "E2E Snowball Rebalance Bad",
                "strategy_type": "snowball",
                "parameters": {
                    "rebalance_enabled": True,
                    "rebalance_start_ratio": 40,
                    "rebalance_end_ratio": 50,
                },
            },
            format="json",
        )
        assert resp.status_code == 400
