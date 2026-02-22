"""URL configuration for auto_forex project."""

from typing import List

from django.conf import settings
from django.contrib import admin
from django.urls import URLResolver, include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

urlpatterns: List[URLResolver] = [
    path(route="admin/", view=admin.site.urls),
    path(route="api/accounts/", view=include("apps.accounts.urls")),
    path(route="api/health/", view=include("apps.health.urls")),
    path(route="api/market/", view=include("apps.market.urls")),
    path(route="api/trading/", view=include("apps.trading.urls")),
]

# OpenAPI schema endpoints - only available in development
if settings.DEBUG:
    urlpatterns += [
        path(route="api/schema/", view=SpectacularAPIView.as_view(), name="schema"),
        path(
            route="api/schema/swagger-ui/",
            view=SpectacularSwaggerView.as_view(url_name="schema"),
            name="swagger-ui",
        ),
        path(
            route="api/schema/redoc/",
            view=SpectacularRedocView.as_view(url_name="schema"),
            name="redoc",
        ),
    ]
