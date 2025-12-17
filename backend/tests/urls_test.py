"""Test URL configuration.

This is used by tests.settings_test to expose all APIs needed by integration tests
without depending on production URL wiring.
"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("apps.accounts.urls")),
    path("api/market/", include("apps.market.urls")),
]
