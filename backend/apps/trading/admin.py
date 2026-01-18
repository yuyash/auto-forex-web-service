from django.contrib import admin

from apps.trading.models import (
    BacktestTasks,
    CeleryTaskStatus,
    Executions,
    StrategyConfigurations,
    StrategyEvents,
    TaskExecutionResult,
    TradeLogs,
    TradingEvent,
    TradingMetrics,
    TradingTasks,
)


@admin.register(StrategyConfigurations)
class StrategyConfigurationsAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "name", "strategy_type", "created_at", "updated_at")
    list_filter = ("strategy_type", "created_at")
    search_fields = ("name", "strategy_type", "user__email", "user__username")
    ordering = ("-created_at",)


@admin.register(BacktestTasks)
class BacktestTasksAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "name",
        "status",
        "data_source",
        "start_time",
        "end_time",
        "created_at",
    )
    list_filter = ("status", "data_source", "created_at")
    search_fields = ("name", "user__email", "user__username")
    ordering = ("-created_at",)


@admin.register(TradingTasks)
class TradingTasksAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "name",
        "status",
        "oanda_account",
        "sell_on_stop",
        "created_at",
    )
    list_filter = ("status", "sell_on_stop", "created_at")
    search_fields = ("name", "user__email", "user__username", "oanda_account__account_id")
    ordering = ("-created_at",)


@admin.register(Executions)
class ExecutionsAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "task_type",
        "task_id",
        "execution_number",
        "status",
        "progress",
        "started_at",
        "completed_at",
        "created_at",
    )
    list_filter = ("task_type", "status", "created_at")
    search_fields = ("task_type", "task_id", "error_message")
    ordering = ("-created_at",)


@admin.register(TaskExecutionResult)
class TaskExecutionResultAdmin(admin.ModelAdmin):
    list_display = ("id", "task_type", "task_id", "success", "oanda_account_id", "created_at")
    list_filter = ("task_type", "success", "created_at")
    search_fields = ("task_type", "task_id", "oanda_account_id", "error")
    ordering = ("-created_at",)


@admin.register(CeleryTaskStatus)
class CeleryTaskStatusAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "task_name",
        "instance_key",
        "status",
        "celery_task_id",
        "worker",
        "last_heartbeat_at",
        "updated_at",
    )
    list_filter = ("status", "task_name", "updated_at")
    search_fields = ("task_name", "instance_key", "celery_task_id", "worker")
    ordering = ("-updated_at",)


@admin.register(TradingEvent)
class TradingEventAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "created_at",
        "severity",
        "event_type",
        "task_type",
        "task_id",
        "user",
        "account",
        "instrument",
    )
    list_filter = ("severity", "event_type", "task_type", "created_at")
    search_fields = ("event_type", "description", "instrument", "task_type", "task_id")
    ordering = ("-created_at",)


@admin.register(TradingMetrics)
class TradingMetricsAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "execution",
        "sequence",
        "timestamp",
        "realized_pnl",
        "unrealized_pnl",
        "total_pnl",
        "open_positions",
        "total_trades",
        "created_at",
    )
    list_filter = ("created_at", "timestamp")
    search_fields = ("execution__id", "sequence")
    ordering = ("-created_at",)
    readonly_fields = (
        "execution",
        "sequence",
        "timestamp",
        "realized_pnl",
        "unrealized_pnl",
        "total_pnl",
        "open_positions",
        "total_trades",
        "tick_ask_min",
        "tick_ask_max",
        "tick_ask_avg",
        "tick_bid_min",
        "tick_bid_max",
        "tick_bid_avg",
        "tick_mid_min",
        "tick_mid_max",
        "tick_mid_avg",
        "created_at",
        "updated_at",
    )
    fieldsets = (
        (
            "Execution Info",
            {
                "fields": ("execution", "sequence", "timestamp"),
            },
        ),
        (
            "PnL Metrics",
            {
                "fields": ("realized_pnl", "unrealized_pnl", "total_pnl"),
            },
        ),
        (
            "Position Metrics",
            {
                "fields": ("open_positions", "total_trades"),
            },
        ),
        (
            "Tick Statistics - Ask",
            {
                "fields": ("tick_ask_min", "tick_ask_max", "tick_ask_avg"),
            },
        ),
        (
            "Tick Statistics - Bid",
            {
                "fields": ("tick_bid_min", "tick_bid_max", "tick_bid_avg"),
            },
        ),
        (
            "Tick Statistics - Mid",
            {
                "fields": ("tick_mid_min", "tick_mid_max", "tick_mid_avg"),
            },
        ),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at"),
            },
        ),
    )


@admin.register(TradeLogs)
class TradeLogsAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "execution",
        "sequence",
        "created_at",
    )
    list_filter = ("created_at",)
    search_fields = ("execution__id", "sequence")
    ordering = ("-created_at",)
    readonly_fields = ("execution", "sequence", "trade", "created_at")


@admin.register(StrategyEvents)
class StrategyEventsAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "execution",
        "sequence",
        "event_type",
        "strategy_type",
        "timestamp",
        "created_at",
    )
    list_filter = ("event_type", "strategy_type", "created_at", "timestamp")
    search_fields = ("execution__id", "sequence", "event_type", "strategy_type")
    ordering = ("-created_at",)
    readonly_fields = (
        "execution",
        "sequence",
        "event_type",
        "strategy_type",
        "timestamp",
        "event",
        "created_at",
    )
