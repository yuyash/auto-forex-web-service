"""
URL configuration for accounts app.

This module defines URL patterns for authentication endpoints.
"""

from django.urls import path
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

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
)

app_name = "accounts"


class AccountsApiRootView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def get(self, _request: Request) -> Response:
        return Response(
            {
                "message": "Accounts API",
                "endpoints": {
                    "login": "/api/accounts/auth/login",
                    "logout": "/api/accounts/auth/logout",
                    "refresh": "/api/accounts/auth/refresh",
                    "register": "/api/accounts/auth/register",
                    "settings": "/api/accounts/settings/",
                    "settings_public": "/api/accounts/settings/public",
                    "notifications": "/api/accounts/notifications",
                },
            }
        )


urlpatterns = [
    path("", AccountsApiRootView.as_view(), name="api_root"),
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
