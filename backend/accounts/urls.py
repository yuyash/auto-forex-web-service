"""
URL configuration for accounts app.

This module defines URL patterns for authentication endpoints.
"""

from django.urls import path

from .views import (
    AdminSystemSettingsView,
    OandaAccountDetailView,
    OandaAccountListCreateView,
    PositionDifferentiationView,
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
    path("accounts", OandaAccountListCreateView.as_view(), name="oanda_accounts_list"),
    path(
        "accounts/<int:account_id>", OandaAccountDetailView.as_view(), name="oanda_account_detail"
    ),
    path(
        "accounts/<int:account_id>/position-diff",
        PositionDifferentiationView.as_view(),
        name="position_differentiation",
    ),
]
