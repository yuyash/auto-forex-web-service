"""
Django admin configuration for trading models.
"""

from django.contrib import admin

from .event_models import Event, Notification
from .models import Order, Position, Strategy, StrategyState, Trade
from .tick_data_models import TickData


@admin.register(Strategy)
class StrategyAdmin(admin.ModelAdmin):
    """Admin interface for Strategy model."""

    list_display = [
        "id",
        "strategy_type",
        "account",
        "is_active",
        "started_at",
        "created_at",
    ]
    list_filter = ["is_active", "strategy_type", "created_at"]
    search_fields = ["strategy_type", "account__account_id", "account__user__email"]
    readonly_fields = ["created_at", "updated_at"]
    date_hierarchy = "created_at"


@admin.register(StrategyState)
class StrategyStateAdmin(admin.ModelAdmin):
    """Admin interface for StrategyState model."""

    list_display = ["id", "strategy", "current_layer", "last_tick_time", "updated_at"]
    search_fields = ["strategy__strategy_type", "strategy__account__account_id"]
    readonly_fields = ["updated_at"]


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """Admin interface for Order model."""

    list_display = [
        "order_id",
        "instrument",
        "order_type",
        "direction",
        "units",
        "status",
        "created_at",
    ]
    list_filter = ["status", "order_type", "direction", "instrument", "created_at"]
    search_fields = ["order_id", "instrument", "account__account_id"]
    readonly_fields = ["created_at", "filled_at"]
    date_hierarchy = "created_at"


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    """Admin interface for Position model."""

    list_display = [
        "position_id",
        "instrument",
        "direction",
        "units",
        "entry_price",
        "unrealized_pnl",
        "opened_at",
        "closed_at",
    ]
    list_filter = ["direction", "instrument", "opened_at", "closed_at"]
    search_fields = ["position_id", "instrument", "account__account_id"]
    readonly_fields = ["opened_at", "closed_at"]
    date_hierarchy = "opened_at"


@admin.register(Trade)
class TradeAdmin(admin.ModelAdmin):
    """Admin interface for Trade model."""

    list_display = [
        "id",
        "instrument",
        "direction",
        "units",
        "entry_price",
        "exit_price",
        "pnl",
        "closed_at",
    ]
    list_filter = ["direction", "instrument", "closed_at"]
    search_fields = ["instrument", "account__account_id"]
    readonly_fields = ["created_at"]
    date_hierarchy = "closed_at"


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    """Admin interface for Event model."""

    list_display = [
        "id",
        "timestamp",
        "category",
        "event_type",
        "severity",
        "user",
        "description",
    ]
    list_filter = ["category", "severity", "event_type", "timestamp"]
    search_fields = [
        "event_type",
        "description",
        "user__email",
        "account__account_id",
        "ip_address",
    ]
    readonly_fields = ["timestamp"]
    date_hierarchy = "timestamp"
    fieldsets = (
        (
            "Event Information",
            {
                "fields": (
                    "timestamp",
                    "category",
                    "event_type",
                    "severity",
                )
            },
        ),
        (
            "Associated Entities",
            {
                "fields": (
                    "user",
                    "account",
                )
            },
        ),
        (
            "Event Details",
            {
                "fields": (
                    "description",
                    "details",
                )
            },
        ),
        (
            "Request Information",
            {
                "fields": (
                    "ip_address",
                    "user_agent",
                )
            },
        ),
    )


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """Admin interface for Notification model."""

    list_display = [
        "id",
        "timestamp",
        "notification_type",
        "title",
        "severity",
        "is_read",
    ]
    list_filter = ["severity", "is_read", "notification_type", "timestamp"]
    search_fields = ["title", "message", "notification_type"]
    readonly_fields = ["timestamp", "created_at"]
    date_hierarchy = "timestamp"
    actions = ["mark_as_read", "mark_as_unread"]

    @admin.action(description="Mark selected notifications as read")
    def mark_as_read(self, request, queryset):  # type: ignore[no-untyped-def]
        """Mark selected notifications as read."""
        queryset.update(is_read=True)
        self.message_user(request, f"{queryset.count()} notifications marked as read.")

    @admin.action(description="Mark selected notifications as unread")
    def mark_as_unread(self, request, queryset):  # type: ignore[no-untyped-def]
        """Mark selected notifications as unread."""
        queryset.update(is_read=False)
        self.message_user(request, f"{queryset.count()} notifications marked as unread.")


@admin.register(TickData)
class TickDataAdmin(admin.ModelAdmin):
    """Admin interface for TickData model."""

    list_display = [
        "id",
        "instrument",
        "timestamp",
        "bid",
        "ask",
        "mid",
        "spread",
        "account",
    ]
    list_filter = ["instrument", "timestamp", "account"]
    search_fields = ["instrument", "account__account_id"]
    readonly_fields = ["created_at", "mid", "spread"]
    date_hierarchy = "timestamp"
    ordering = ["-timestamp"]

    def has_add_permission(self, request):  # type: ignore[no-untyped-def]
        """Disable manual addition of tick data through admin."""
        return False
