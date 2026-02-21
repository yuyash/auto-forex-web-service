from __future__ import annotations

from typing import List

from django.urls import URLPattern, path

from apps.health.views import HealthView

app_name = "health"

urlpatterns: List[URLPattern] = [
    path(route="", view=HealthView.as_view(), name="health_check"),
]
