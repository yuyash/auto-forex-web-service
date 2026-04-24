"""
URL configuration for trading app.

This module defines URL patterns for trading data and strategy endpoints.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.trading.views import (
    BacktestTaskViewSet,
    StrategyConfigCopyView,
    StrategyConfigDetailView,
    StrategyConfigTasksView,
    StrategyConfigView,
    StrategyDefaultsView,
    StrategyView,
    RecoveryAttemptListView,
    TradingTaskViewSet,
)

app_name = "trading"

# Router for task-centric API viewsets
router = DefaultRouter()
router.register(r"tasks/backtest", BacktestTaskViewSet, basename="backtest-task")
router.register(r"tasks/trading", TradingTaskViewSet, basename="trading-task")

urlpatterns = [
    # Task-centric API endpoints
    path("", include(router.urls)),
    path("recovery-attempts/", RecoveryAttemptListView.as_view(), name="recovery_attempts"),
    # Strategy endpoints
    path("strategies/", StrategyView.as_view(), name="strategy_list"),
    path(
        "strategies/<str:strategy_id>/defaults/",
        StrategyDefaultsView.as_view(),
        name="strategy_defaults",
    ),
    # Strategy configuration endpoints
    path(
        "strategy-configs/",
        StrategyConfigView.as_view(),
        name="strategy_config_list_create",
    ),
    path(
        "strategy-configs/<uuid:config_id>/",
        StrategyConfigDetailView.as_view(),
        name="strategy_config_detail",
    ),
    path(
        "strategy-configs/<uuid:config_id>/tasks/",
        StrategyConfigTasksView.as_view(),
        name="strategy_config_tasks",
    ),
    path(
        "strategy-configs/<uuid:config_id>/copy/",
        StrategyConfigCopyView.as_view(),
        name="strategy_config_copy",
    ),
]
