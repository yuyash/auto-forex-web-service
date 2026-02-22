"""Integration tests for market status API."""

from typing import Any

import pytest
from rest_framework import status
from rest_framework.test import APIClient


@pytest.mark.django_db
class TestMarketStatusAPIIntegration:
    """Integration tests for market status API."""

    def test_get_market_status(self, user: Any) -> None:
        """Test getting market status."""
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get("/api/market/market/status/")

        assert response.status_code == status.HTTP_200_OK
        assert "is_open" in response.data
        assert "current_time_utc" in response.data
        assert "active_sessions" in response.data
        assert "sessions" in response.data
        assert "next_event" in response.data

    def test_market_status_sessions(self, user: Any) -> None:
        """Test that all trading sessions are included."""
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get("/api/market/market/status/")

        assert response.status_code == status.HTTP_200_OK
        sessions = response.data["sessions"]

        assert "sydney" in sessions
        assert "tokyo" in sessions
        assert "london" in sessions
        assert "new_york" in sessions

        # Each session should have required fields
        for session in sessions.values():
            assert "open_hour_utc" in session
            assert "close_hour_utc" in session
            assert "is_active" in session

    def test_market_status_unauthenticated(self) -> None:
        """Test that unauthenticated users cannot access market status."""
        client = APIClient()

        response = client.get("/api/market/market/status/")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
