"""Integration tests for accounts endpoints using production URL configuration.

These tests ensure accounts routes are mounted in `config.urls` (production wiring)
and that an authenticated-only accounts endpoint is actually protected.
"""

from __future__ import annotations

import pytest
from django.urls import clear_url_caches
from rest_framework.test import APIClient


@pytest.mark.django_db
class TestAccountsProdUrlconfAuth:
    def test_settings_requires_auth_in_prod_urlconf(self, settings):
        settings.ROOT_URLCONF = "config.urls"
        clear_url_caches()

        client = APIClient()
        resp = client.get("/api/settings/")
        assert resp.status_code in {401, 403}

    def test_settings_works_with_auth_in_prod_urlconf(self, settings, test_user):
        settings.ROOT_URLCONF = "config.urls"
        clear_url_caches()

        client = APIClient()
        client.force_authenticate(user=test_user)

        resp = client.get("/api/settings/")
        assert resp.status_code == 200
        data = resp.json()
        assert "user" in data
        assert "settings" in data
