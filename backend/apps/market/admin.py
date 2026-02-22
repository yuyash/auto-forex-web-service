"""
Admin interface for market app.
"""

from django.contrib import admin

from apps.market.models import (
    CeleryTaskStatus,
    MarketEvent,
    OandaAccounts,
    OandaApiHealthStatus,
)


@admin.register(OandaAccounts)
class OandaAccountAdmin(admin.ModelAdmin):
    """Admin interface for OandaAccounts model."""

    list_display = [
        "user",
        "account_id",
        "api_type",
        "jurisdiction",
        "balance",
        "is_active",
        "created_at",
    ]
    list_filter = ["api_type", "jurisdiction", "is_active", "created_at"]
    search_fields = ["user__email", "account_id"]
    readonly_fields = ["created_at", "updated_at"]
    ordering = ["-created_at"]

    fieldsets = (
        (
            "Account Information",
            {
                "fields": (
                    "user",
                    "account_id",
                    "api_type",
                    "jurisdiction",
                    "currency",
                )
            },
        ),
        (
            "Balance & Margin",
            {
                "fields": (
                    "balance",
                    "margin_used",
                    "margin_available",
                    "unrealized_pnl",
                )
            },
        ),
        (
            "Status",
            {"fields": ("is_active",)},
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    # Don't show api_token in admin for security
    exclude = ["api_token"]


@admin.register(MarketEvent)
class MarketEventAdmin(admin.ModelAdmin):
    """Admin interface for MarketEvent model."""

    list_display = [
        "id",
        "created_at",
        "category",
        "severity",
        "event_type",
        "instrument",
        "account",
        "user",
    ]
    list_filter = ["category", "severity", "event_type", "instrument", "created_at"]
    search_fields = [
        "event_type",
        "description",
        "instrument",
        "account__account_id",
        "user__email",
    ]
    readonly_fields = ["created_at"]
    ordering = ["-created_at"]


@admin.register(CeleryTaskStatus)
class CeleryTaskStatusAdmin(admin.ModelAdmin):
    """Admin interface for CeleryTaskStatus model."""

    list_display = [
        "id",
        "task_name",
        "instance_key",
        "status",
        "celery_task_id",
        "worker",
        "started_at",
        "last_heartbeat_at",
        "stopped_at",
        "updated_at",
    ]
    list_filter = ["task_name", "status", "started_at", "stopped_at"]
    search_fields = ["task_name", "instance_key", "celery_task_id", "worker"]
    readonly_fields = ["created_at", "updated_at"]
    ordering = ["-updated_at"]

    fieldsets = (
        (
            "Task Information",
            {
                "fields": (
                    "task_name",
                    "instance_key",
                    "celery_task_id",
                    "worker",
                )
            },
        ),
        (
            "Status",
            {
                "fields": (
                    "status",
                    "status_message",
                )
            },
        ),
        (
            "Metadata",
            {"fields": ("meta",)},
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "started_at",
                    "last_heartbeat_at",
                    "stopped_at",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )


@admin.register(OandaApiHealthStatus)
class OandaApiHealthStatusAdmin(admin.ModelAdmin):
    """Admin interface for OandaApiHealthStatus model."""

    list_display = [
        "id",
        "account",
        "is_available",
        "checked_at",
        "latency_ms",
        "http_status",
        "created_at",
    ]
    list_filter = ["is_available", "http_status", "checked_at", "created_at"]
    search_fields = ["account__account_id", "account__user__email", "error_message"]
    readonly_fields = [
        "account",
        "is_available",
        "checked_at",
        "latency_ms",
        "http_status",
        "error_message",
        "created_at",
    ]
    ordering = ["-checked_at"]
    date_hierarchy = "checked_at"

    fieldsets = (
        (
            "Account",
            {"fields": ("account",)},
        ),
        (
            "Health Status",
            {
                "fields": (
                    "is_available",
                    "http_status",
                    "latency_ms",
                    "checked_at",
                )
            },
        ),
        (
            "Error Details",
            {"fields": ("error_message",)},
        ),
        (
            "Metadata",
            {"fields": ("created_at",)},
        ),
    )

    def has_add_permission(self, request):
        """Disable manual creation of health status records."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Allow deletion for cleanup purposes."""
        return True
