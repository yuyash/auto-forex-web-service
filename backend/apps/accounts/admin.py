"""
Admin interface for accounts app.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import BlockedIP, User, UserSession, UserSettings


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin interface for User model."""

    list_display = [
        "email",
        "username",
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
    search_fields = ["email", "username"]
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
