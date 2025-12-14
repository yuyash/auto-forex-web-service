"""
URL configuration for accounts app.

This module defines URL patterns for authentication endpoints.
"""

from django.urls import path

from .views import (
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
    WhitelistedEmailDetailView,
    WhitelistedEmailListCreateView,
)

app_name = "accounts"

urlpatterns = [
    path("auth/register", UserRegistrationView.as_view(), name="register"),
    path("auth/verify-email", EmailVerificationView.as_view(), name="verify_email"),
    path(
        "auth/resend-verification",
        ResendVerificationEmailView.as_view(),
        name="resend_verification",
    ),
    path("auth/login", UserLoginView.as_view(), name="login"),
    path("auth/logout", UserLogoutView.as_view(), name="logout"),
    path("auth/refresh", TokenRefreshView.as_view(), name="token_refresh"),
    path(
        "admin/whitelist/emails",
        WhitelistedEmailListCreateView.as_view(),
        name="whitelist_emails_list",
    ),
    path(
        "admin/whitelist/emails/<int:whitelist_id>",
        WhitelistedEmailDetailView.as_view(),
        name="whitelist_email_detail",
    ),
    path("settings/", UserSettingsView.as_view(), name="user_settings"),
    path(
        "settings/public",
        PublicAccountSettingsView.as_view(),
        name="public_account_settings",
    ),
    path("notifications", UserNotificationListView.as_view(), name="notifications"),
    path(
        "notifications/<int:notification_id>/read",
        UserNotificationMarkReadView.as_view(),
        name="notification_read",
    ),
    path(
        "notifications/read-all",
        UserNotificationMarkAllReadView.as_view(),
        name="notifications_read_all",
    ),
]
