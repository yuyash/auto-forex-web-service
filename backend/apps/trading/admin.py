from django.contrib import admin

from apps.trading.models import (
    BacktestTask,
    CeleryTaskStatus,
    ExecutionMetrics,
    StrategyConfig,
    TaskExecution,
    TaskExecutionResult,
    TradingEvent,
    TradingTask,
)


@admin.register(StrategyConfig)
class StrategyConfigAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "name", "strategy_type", "created_at", "updated_at")
    list_filter = ("strategy_type", "created_at")
    search_fields = ("name", "strategy_type", "user__email", "user__username")
    ordering = ("-created_at",)


@admin.register(BacktestTask)
class BacktestTaskAdmin(admin.ModelAdmin):
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


@admin.register(TradingTask)
class TradingTaskAdmin(admin.ModelAdmin):
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


@admin.register(TaskExecution)
class TaskExecutionAdmin(admin.ModelAdmin):
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


@admin.register(ExecutionMetrics)
class ExecutionMetricsAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "execution",
        "total_return",
        "total_pnl",
        "realized_pnl",
        "unrealized_pnl",
        "total_trades",
        "win_rate",
        "created_at",
    )
    list_filter = ("created_at",)
    search_fields = ("execution__id",)
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
