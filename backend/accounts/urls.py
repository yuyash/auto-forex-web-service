"""
URL configuration for accounts app.

This module defines URL patterns for authentication endpoints.
"""

from django.urls import path

from trading.sync_views import AccountSyncView

from .views import (
    AdminAthenaImportProgressView,
    AdminSystemSettingsView,
    AdminTestAWSView,
    AdminTestEmailView,
    AdminTriggerAthenaImportView,
    EmailVerificationView,
    OandaAccountDetailView,
    OandaAccountListCreateView,
    PositionDifferentiationSuggestionView,
    PositionDifferentiationView,
    PublicSystemSettingsView,
    ResendVerificationEmailView,
    TokenRefreshView,
    UserLoginView,
    UserLogoutView,
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
        "system/settings/public",
        PublicSystemSettingsView.as_view(),
        name="public_system_settings",
    ),
    path(
        "admin/system/settings",
        AdminSystemSettingsView.as_view(),
        name="admin_system_settings",
    ),
    path(
        "admin/test-email",
        AdminTestEmailView.as_view(),
        name="admin_test_email",
    ),
    path(
        "admin/test-aws",
        AdminTestAWSView.as_view(),
        name="admin_test_aws",
    ),
    path(
        "admin/trigger-athena-import",
        AdminTriggerAthenaImportView.as_view(),
        name="admin_trigger_athena_import",
    ),
    path(
        "admin/athena-import-progress",
        AdminAthenaImportProgressView.as_view(),
        name="admin_athena_import_progress",
    ),
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
    path("accounts/", OandaAccountListCreateView.as_view(), name="oanda_accounts_list"),
    path(
        "accounts/<int:account_id>/", OandaAccountDetailView.as_view(), name="oanda_account_detail"
    ),
    path(
        "accounts/<int:account_id>/position-diff/",
        PositionDifferentiationView.as_view(),
        name="position_differentiation",
    ),
    path(
        "accounts/<int:account_id>/position-diff/suggest/",
        PositionDifferentiationSuggestionView.as_view(),
        name="position_differentiation_suggest",
    ),
    path(
        "accounts/<int:account_id>/sync/",
        AccountSyncView.as_view(),
        name="account_sync",
    ),
    path("settings/", UserSettingsView.as_view(), name="user_settings"),
]
