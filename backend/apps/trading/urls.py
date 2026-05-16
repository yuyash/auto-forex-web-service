"""
URL configuration for trading app.

This module defines URL patterns for trading data and strategy endpoints.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.trading.views.backtest import BacktestTaskViewSet
from apps.trading.views.configs import (
    StrategyConfigCopyView,
    StrategyConfigDetailView,
    StrategyConfigTasksView,
    StrategyConfigView,
)
from apps.trading.views.fx import FxRateView
from apps.trading.views.initial_positions import (
    InitialPositionImportFromOandaView,
    InitialPositionImportFromTaskView,
    InitialPositionImportSourcesView,
)
from apps.trading.views.operations import TradingOperationsMetricsView
from apps.trading.views.recovery import RecoveryAttemptListView
from apps.trading.views.strategies import StrategyDefaultsView, StrategyView
from apps.trading.views.stream import TaskEventStreamView
from apps.trading.views.trading import TradingTaskViewSet

app_name = "trading"

# Router for task-centric API viewsets
router = DefaultRouter()
router.register(r"tasks/backtest", BacktestTaskViewSet, basename="backtest-task")
router.register(r"tasks/trading", TradingTaskViewSet, basename="trading-task")

urlpatterns = [
    # Task-centric API endpoints
    path("", include(router.urls)),
    path(
        "tasks/<str:task_type>/<uuid:task_id>/stream/",
        TaskEventStreamView.as_view(),
        name="task_event_stream",
    ),
    path("recovery-attempts/", RecoveryAttemptListView.as_view(), name="recovery_attempts"),
    path(
        "tasks/initial-position-import-sources/",
        InitialPositionImportSourcesView.as_view(),
        name="initial_position_import_sources",
    ),
    path(
        "tasks/initial-positions/import-from-task/",
        InitialPositionImportFromTaskView.as_view(),
        name="initial_position_import_from_task",
    ),
    path(
        "tasks/initial-positions/import-from-oanda/",
        InitialPositionImportFromOandaView.as_view(),
        name="initial_position_import_from_oanda",
    ),
    path("fx/rate/", FxRateView.as_view(), name="fx_rate"),
    path(
        "operations/metrics/",
        TradingOperationsMetricsView.as_view(),
        name="operations_metrics",
    ),
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
