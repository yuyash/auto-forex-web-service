from __future__ import annotations

from django.urls import path

from apps.health.views import HealthView

app_name = "health"

urlpatterns = [
    path("", HealthView.as_view(), name="health_check"),
]
