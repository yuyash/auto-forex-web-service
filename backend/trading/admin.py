"""
Django admin configuration for trading models.
"""

from django.contrib import admin

from .models import Order, Position, Strategy, StrategyState, Trade


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
