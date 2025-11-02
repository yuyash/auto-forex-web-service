"""
URL configuration for trading app.

This module defines URL patterns for trading data endpoints.

Requirements: 7.1, 7.2, 12.1
"""

from django.urls import path

from .views import TickDataListView

app_name = "trading"

urlpatterns = [
    path("tick-data/", TickDataListView.as_view(), name="tick_data_list"),
]
