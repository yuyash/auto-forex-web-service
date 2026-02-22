"""Unit tests for market status views."""

from typing import Any
from unittest.mock import patch

import pytest
from rest_framework import status
from rest_framework.test import APIClient


@pytest.mark.django_db
class TestMarketStatusView:
    """Test MarketStatusView."""

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

    @patch("apps.market.views.market.datetime")
    def test_market_status_weekend_closed(self, mock_datetime: Any, user: Any) -> None:
        """Test market status during weekend."""
        from datetime import UTC, datetime

        # Mock Saturday
        mock_now = datetime(2024, 1, 13, 12, 0, 0, tzinfo=UTC)  # Saturday
        mock_datetime.now.return_value = mock_now
        mock_datetime.fromtimestamp = datetime.fromtimestamp

        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get("/api/market/market/status/")

        assert response.status_code == status.HTTP_200_OK
        # Market should be closed on Saturday
        assert response.data["is_weekend"] is True

    def test_market_status_unauthenticated(self) -> None:
        """Test that unauthenticated users cannot access market status."""
        client = APIClient()

        response = client.get("/api/market/market/status/")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
