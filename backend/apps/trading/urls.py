"""
URL configuration for trading app.

This module defines URL patterns for trading data and strategy endpoints.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.trading.views import (
    BacktestTaskViewSet,
    StrategyConfigDetailView,
    StrategyConfigView,
    StrategyDefaultsView,
    StrategyView,
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
]
