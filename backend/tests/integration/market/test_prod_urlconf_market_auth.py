"""Integration tests for market endpoints using production URL configuration.

These tests ensure market routes are mounted in `config.urls` (production wiring)
and that they are authentication-protected.
"""

from __future__ import annotations

import pytest
from django.urls import clear_url_caches
from rest_framework.test import APIClient


@pytest.mark.django_db
class TestMarketProdUrlconfAuth:
    def test_market_status_requires_auth_in_prod_urlconf(self, settings):
        settings.ROOT_URLCONF = "config.urls"
        clear_url_caches()

        client = APIClient()
        resp = client.get("/api/market/market/status/")
        assert resp.status_code in {401, 403}

    def test_market_status_works_with_auth_in_prod_urlconf(self, settings, test_user):
        settings.ROOT_URLCONF = "config.urls"
        clear_url_caches()

        client = APIClient()
        client.force_authenticate(user=test_user)

        resp = client.get("/api/market/market/status/")
        assert resp.status_code == 200
        data = resp.json()
        assert "is_open" in data
        assert "active_sessions" in data
        assert "next_event" in data
