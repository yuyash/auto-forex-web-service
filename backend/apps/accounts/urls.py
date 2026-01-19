"""
URL configuration for accounts app.

This module defines URL patterns for authentication endpoints.
"""

from typing import List

from django.urls import URLPattern, path

from apps.accounts.views import (
    EmailVerificationView,
    PublicAccountSettingsView,
    ResendVerificationEmailView,
    TokenRefreshView,
    UserLoginView,
    UserLogoutView,
    UserNotificationListView,
    UserNotificationMarkAllReadView,
    UserNotificationMarkReadView,
    UserRegistrationView,
    UserSettingsView,
)

app_name = "accounts"


urlpatterns: List[URLPattern] = [
    path(route="auth/register", view=UserRegistrationView.as_view(), name="register"),
    path(route="auth/verify-email", view=EmailVerificationView.as_view(), name="verify_email"),
    path(
        route="auth/resend-verification",
        view=ResendVerificationEmailView.as_view(),
        name="resend_verification",
    ),
    path(route="auth/login", view=UserLoginView.as_view(), name="login"),
    path(route="auth/logout", view=UserLogoutView.as_view(), name="logout"),
    path(route="auth/refresh", view=TokenRefreshView.as_view(), name="token_refresh"),
    path(route="settings/", view=UserSettingsView.as_view(), name="user_settings"),
    path(
        route="settings/public",
        view=PublicAccountSettingsView.as_view(),
        name="public_account_settings",
    ),
    path(route="notifications", view=UserNotificationListView.as_view(), name="notifications"),
    path(
        route="notifications/<int:notification_id>/read",
        view=UserNotificationMarkReadView.as_view(),
        name="notification_read",
    ),
    path(
        route="notifications/read-all",
        view=UserNotificationMarkAllReadView.as_view(),
        name="notifications_read_all",
    ),
]
