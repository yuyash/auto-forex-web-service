from django.contrib import admin

from apps.trading.models import (
    BacktestTasks,
    CeleryTaskStatus,
    StrategyConfigurations,
    TaskLog,
    TaskMetric,
    TradingEvents,
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


@admin.register(TradingEvents)
class TradingEventsAdmin(admin.ModelAdmin):
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


@admin.register(TaskLog)
class TaskLogAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "task_type",
        "task_id",
        "timestamp",
        "level",
        "message",
    )
    list_filter = ("task_type", "level", "timestamp")
    search_fields = ("task_id", "message")
    ordering = ("-timestamp",)
    readonly_fields = ("task_type", "task_id", "timestamp", "level", "message", "details")


@admin.register(TaskMetric)
class TaskMetricAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "task_type",
        "task_id",
        "metric_name",
        "metric_value",
        "timestamp",
    )
    list_filter = ("task_type", "metric_name", "timestamp")
    search_fields = ("task_id", "metric_name")
    ordering = ("-timestamp",)
    readonly_fields = (
        "task_type",
        "task_id",
        "metric_name",
        "metric_value",
        "timestamp",
        "metadata",
    )
