"""
Admin interface for market app.
"""

from django.contrib import admin

from apps.market.models import CeleryTaskStatus, MarketEvent, OandaAccount


@admin.register(OandaAccount)
class OandaAccountAdmin(admin.ModelAdmin):
    """Admin interface for OandaAccount model."""

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
    list_filter = ["task_name", "status"]
    search_fields = ["task_name", "instance_key", "celery_task_id", "worker"]
    readonly_fields = ["created_at", "updated_at"]
    ordering = ["-updated_at"]
