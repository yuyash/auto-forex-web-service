"""
URL configuration for accounts app.

This module defines URL patterns for authentication endpoints.
"""

from django.urls import path

from .views import UserRegistrationView

app_name = "accounts"

urlpatterns = [
    path("auth/register", UserRegistrationView.as_view(), name="register"),
]
