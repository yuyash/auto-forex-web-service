"""Integration tests for trading endpoints using production URL configuration.

These tests ensure trading routes are mounted in `config.urls` (production wiring)
and that an authenticated-only trading endpoint is actually protected.
"""

from __future__ import annotations

import pytest
from django.urls import clear_url_caches
from rest_framework.test import APIClient


@pytest.mark.django_db
class TestTradingProdUrlconfAuth:
    def test_strategies_requires_auth_in_prod_urlconf(self, settings):
        settings.ROOT_URLCONF = "config.urls"
        clear_url_caches()

        client = APIClient()
        resp = client.get("/api/strategies/")
        assert resp.status_code in {401, 403}

    def test_strategies_works_with_auth_in_prod_urlconf(self, settings, test_user):
        settings.ROOT_URLCONF = "config.urls"
        clear_url_caches()

        client = APIClient()
        client.force_authenticate(user=test_user)

        resp = client.get("/api/strategies/")
        assert resp.status_code == 200
        data = resp.json()
        assert "strategies" in data
        assert "count" in data
