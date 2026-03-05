"""E2E tests for /api/market/ticks/ and /api/market/ticks/range/."""

import pytest


@pytest.mark.django_db
class TestMarketTicks:
    def test_get_ticks(self, authenticated_client):
        resp = authenticated_client.get(
            "/api/market/ticks/",
            {"instrument": "USD_JPY", "limit": 10},
        )
        assert resp.status_code == 200

    def test_tick_cursor_pagination(self, authenticated_client):
        """Verify cursor-based pagination returns non-overlapping pages."""
        resp1 = authenticated_client.get(
            "/api/market/ticks/", {"instrument": "USD_JPY", "limit": 10}
        )
        assert resp1.status_code == 200
        assert resp1.data["count"] == 10
        assert resp1.data["next_cursor"] is not None

        # Fetch next page using cursor
        resp2 = authenticated_client.get(
            "/api/market/ticks/",
            {"instrument": "USD_JPY", "limit": 10, "cursor": resp1.data["next_cursor"]},
        )
        assert resp2.status_code == 200

        # Verify no overlap between pages
        ts1 = {t["timestamp"] for t in resp1.data["ticks"]}
        ts2 = {t["timestamp"] for t in resp2.data["ticks"]}
        assert ts1.isdisjoint(ts2)

    def test_tick_response_structure(self, authenticated_client):
        """Verify tick list response has expected cursor-based structure."""
        resp = authenticated_client.get("/api/market/ticks/", {"instrument": "USD_JPY", "limit": 5})
        assert resp.status_code == 200
        assert "count" in resp.data
        assert "instrument" in resp.data
        assert "next_cursor" in resp.data
        assert "ticks" in resp.data
        assert len(resp.data["ticks"]) <= 5

    def test_get_tick_range(self, authenticated_client):
        resp = authenticated_client.get(
            "/api/market/ticks/range/",
            {
                "instrument": "USD_JPY",
                "start": "2026-01-02T00:00:00Z",
                "end": "2026-01-02T00:05:00Z",
            },
        )
        assert resp.status_code == 200

    def test_tick_range_response_structure(self, authenticated_client):
        """Verify tick range endpoint returns expected fields."""
        resp = authenticated_client.get("/api/market/ticks/range/", {"instrument": "USD_JPY"})
        assert resp.status_code == 200
        assert "has_data" in resp.data
        assert "min_timestamp" in resp.data
        assert "max_timestamp" in resp.data

    def test_ticks_unauthenticated(self, api_client):
        resp = api_client.get("/api/market/ticks/")
        assert resp.status_code == 401
