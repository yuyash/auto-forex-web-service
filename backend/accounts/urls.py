"""
URL configuration for accounts app.

This module defines URL patterns for authentication endpoints.
"""

from django.urls import path

from .views import (
    AdminSystemSettingsView,
    PublicSystemSettingsView,
    TokenRefreshView,
    UserLoginView,
    UserLogoutView,
    UserRegistrationView,
)

app_name = "accounts"

urlpatterns = [
    path("auth/register", UserRegistrationView.as_view(), name="register"),
    path("auth/login", UserLoginView.as_view(), name="login"),
    path("auth/logout", UserLogoutView.as_view(), name="logout"),
    path("auth/refresh", TokenRefreshView.as_view(), name="token_refresh"),
    path(
        "system/settings/public",
        PublicSystemSettingsView.as_view(),
        name="public_system_settings",
    ),
    path(
        "admin/system/settings",
        AdminSystemSettingsView.as_view(),
        name="admin_system_settings",
    ),
]
