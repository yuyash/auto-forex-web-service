"""URL configuration for auto_forex project."""

from typing import List

from django.contrib import admin
from django.urls import URLResolver, include, path

urlpatterns: List[URLResolver] = [
    path(route="admin/", view=admin.site.urls),
    path(route="api/accounts/", view=include("apps.accounts.urls")),
    path(route="api/health/", view=include("apps.health.urls")),
    path(route="api/market/", view=include("apps.market.urls")),
    path(route="api/trading/", view=include("apps.trading.urls")),
]
