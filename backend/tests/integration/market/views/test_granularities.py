"""Integration tests for granularities views."""

from typing import Any

import pytest
from rest_framework import status
from rest_framework.test import APIClient


@pytest.mark.django_db
class TestSupportedGranularitiesView:
    """Test SupportedGranularitiesView."""

    def test_get_granularities_standard_list(self, user: Any) -> None:
        """Test getting standard granularities list."""
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get("/api/market/candles/granularities/")

        assert response.status_code == status.HTTP_200_OK
        assert "granularities" in response.data
        assert response.data["count"] > 0

        # Check some standard granularities
        granularities = [g["value"] for g in response.data["granularities"]]
        assert "M1" in granularities
        assert "H1" in granularities
        assert "D" in granularities

    def test_get_granularities_unauthenticated(self) -> None:
        """Test that unauthenticated users cannot access granularities."""
        client = APIClient()

        response = client.get("/api/market/candles/granularities/")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
