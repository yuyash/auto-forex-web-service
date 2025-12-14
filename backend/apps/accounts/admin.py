"""
Admin interface for accounts app.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import (
    AccountSecurityEvent,
    BlockedIP,
    PublicAccountSettings,
    User,
    UserNotification,
    UserSession,
    UserSettings,
    WhitelistedEmail,
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin interface for User model."""

    list_display = [
        "email",
        "username",
        "first_name",
        "last_name",
        "is_staff",
        "is_active",
        "is_locked",
        "failed_login_attempts",
        "created_at",
    ]
    list_filter = [
        "is_staff",
        "is_active",
        "is_locked",
        "language",
        "created_at",
    ]
    search_fields = ["email", "username", "first_name", "last_name"]
    ordering = ["-created_at"]

    fieldsets = BaseUserAdmin.fieldsets + (  # type: ignore[operator]
        (
            "Additional Info",
            {
                "fields": (
                    "timezone",
                    "language",
                    "is_locked",
                    "failed_login_attempts",
                    "last_login_attempt",
                )
            },
        ),
    )

    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        (
            "Additional Info",
            {"fields": ("email", "timezone", "language")},
        ),
    )


@admin.register(UserSettings)
class UserSettingsAdmin(admin.ModelAdmin):
    """Admin interface for UserSettings model."""

    list_display = [
        "user",
        "notification_enabled",
        "updated_at",
    ]
    list_filter = ["notification_enabled"]
    search_fields = ["user__email", "user__username"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    """Admin interface for UserSession model."""

    list_display = [
        "user",
        "ip_address",
        "login_time",
        "last_activity",
        "is_active",
    ]
    list_filter = ["is_active", "login_time"]
    search_fields = ["user__email", "ip_address", "session_key"]
    readonly_fields = ["login_time", "last_activity", "logout_time"]
    ordering = ["-login_time"]


@admin.register(UserNotification)
class UserNotificationAdmin(admin.ModelAdmin):
    """Admin interface for UserNotification model."""

    list_display = [
        "user",
        "notification_type",
        "severity",
        "title",
        "is_read",
        "timestamp",
    ]
    list_filter = ["severity", "is_read", "notification_type"]
    search_fields = ["user__email", "title", "message", "notification_type"]
    readonly_fields = ["timestamp", "created_at"]
    ordering = ["-timestamp"]


@admin.register(BlockedIP)
class BlockedIPAdmin(admin.ModelAdmin):
    """Admin interface for BlockedIP model."""

    list_display = [
        "ip_address",
        "reason",
        "failed_attempts",
        "blocked_at",
        "blocked_until",
        "is_permanent",
    ]
    list_filter = ["is_permanent", "blocked_at"]
    search_fields = ["ip_address", "reason"]
    readonly_fields = ["blocked_at"]
    ordering = ["-blocked_at"]


@admin.register(WhitelistedEmail)
class WhitelistedEmailAdmin(admin.ModelAdmin):
    """Admin interface for WhitelistedEmail model."""

    list_display = [
        "email_pattern",
        "is_active",
        "description",
        "created_by",
        "created_at",
        "updated_at",
    ]
    list_filter = ["is_active", "created_at", "updated_at"]
    search_fields = ["email_pattern", "description", "created_by__email"]
    readonly_fields = ["created_at", "updated_at"]
    ordering = ["email_pattern"]


@admin.register(PublicAccountSettings)
class PublicAccountSettingsAdmin(admin.ModelAdmin):
    """Admin interface for PublicAccountSettings singleton model."""

    list_display = [
        "registration_enabled",
        "login_enabled",
        "email_whitelist_enabled",
        "updated_at",
    ]
    readonly_fields = ["updated_at"]
    fieldsets = (
        (
            "Authentication",
            {
                "fields": (
                    "registration_enabled",
                    "login_enabled",
                    "email_whitelist_enabled",
                )
            },
        ),
        (
            "Timestamps",
            {"fields": ("updated_at",)},
        ),
    )

    def has_add_permission(self, request):  # type: ignore[no-untyped-def]
        """Allow add only if the singleton doesn't exist yet."""
        return not PublicAccountSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):  # type: ignore[no-untyped-def]
        """Prevent deleting the singleton settings."""
        return False


@admin.register(AccountSecurityEvent)
class AccountSecurityEventAdmin(admin.ModelAdmin):
    """Admin interface for AccountSecurityEvent."""

    list_display = [
        "created_at",
        "event_type",
        "severity",
        "user",
        "ip_address",
    ]
    list_filter = ["event_type", "severity", "created_at"]
    search_fields = ["description", "user__email", "user__username", "ip_address"]
    readonly_fields = ["created_at"]
    ordering = ["-created_at"]
