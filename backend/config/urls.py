"""URL configuration for auto_forex project."""

from typing import List

from django.conf import settings
from django.contrib import admin
from django.urls import URLResolver, include, path

urlpatterns: List[URLResolver] = [
    path(route="admin/", view=admin.site.urls),
    path(route="api/accounts/", view=include("apps.accounts.urls")),
    path(route="api/health/", view=include("apps.health.urls")),
    path(route="api/market/", view=include("apps.market.urls")),
    path(route="api/trading/", view=include("apps.trading.urls")),
]

if settings.DEBUG:
    from drf_spectacular.views import (
        SpectacularAPIView,
        SpectacularRedocView,
        SpectacularSwaggerView,
    )

    urlpatterns += [
        path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
        path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
        path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    ]
