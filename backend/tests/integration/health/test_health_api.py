"""Integration tests for backend health endpoint.

Tests the following endpoint using live_server:
- GET /api/health/
"""

import pytest
import requests


@pytest.mark.django_db(transaction=True)
class TestHealthGet:
    def test_health_no_auth_required(self, live_server):
        url = f"{live_server.url}/api/health/"

        response = requests.get(url, timeout=10)

        assert response.status_code == 200
        json_data = response.json()

        assert json_data["overall_status"] in {"healthy", "unhealthy"}
        assert "timestamp" in json_data
        assert "response_time_ms" in json_data
        assert "checks" in json_data
        assert "database" in json_data["checks"]
        assert "redis" in json_data["checks"]

    def test_health_reports_database_check(self, live_server):
        url = f"{live_server.url}/api/health/"

        response = requests.get(url, timeout=10)

        assert response.status_code == 200
        json_data = response.json()
        assert json_data["checks"]["database"]["status"] == "healthy"

    def test_health_redis_is_skipped_in_tests(self, live_server):
        url = f"{live_server.url}/api/health/"

        response = requests.get(url, timeout=10)

        assert response.status_code == 200
        json_data = response.json()
        # tests/settings_test.py uses DummyCache by default
        assert json_data["checks"]["redis"]["status"] == "skipped"
