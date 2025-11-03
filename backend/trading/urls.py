"""
URL configuration for trading app.

This module defines URL patterns for trading data and strategy endpoints.

Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 7.1, 7.2, 12.1, 12.2, 12.4, 12.5
"""

from django.urls import path

from .backtest_views import BacktestListCreateView, BacktestResultsView, BacktestStatusView
from .event_views import EventDetailView, EventExportView, EventListView
from .order_views import OrderDetailView, OrderListCreateView
from .position_views import PositionCloseView, PositionDetailView, PositionListView
from .strategy_views import (
    AccountStrategyConfigView,
    AccountStrategyStartView,
    AccountStrategyStatusView,
    AccountStrategyStopView,
    StrategyConfigView,
    StrategyListView,
)
from .views import TickDataListView

app_name = "trading"

urlpatterns = [
    # Event endpoints
    path("events/", EventListView.as_view(), name="event_list"),
    path("events/export/", EventExportView.as_view(), name="event_export"),
    path("events/<int:event_id>/", EventDetailView.as_view(), name="event_detail"),
    # Tick data endpoints
    path("tick-data/", TickDataListView.as_view(), name="tick_data_list"),
    # Order endpoints
    path("orders/", OrderListCreateView.as_view(), name="order_list_create"),
    path("orders/<int:order_id>/", OrderDetailView.as_view(), name="order_detail"),
    # Position endpoints
    path("positions/", PositionListView.as_view(), name="position_list"),
    path("positions/<int:position_id>/", PositionDetailView.as_view(), name="position_detail"),
    path(
        "positions/<int:position_id>/close/",
        PositionCloseView.as_view(),
        name="position_close",
    ),
    # Strategy endpoints
    path("strategies/", StrategyListView.as_view(), name="strategy_list"),
    path(
        "strategies/<str:strategy_id>/config/",
        StrategyConfigView.as_view(),
        name="strategy_config",
    ),
    path(
        "accounts/<int:account_id>/strategy/start/",
        AccountStrategyStartView.as_view(),
        name="account_strategy_start",
    ),
    path(
        "accounts/<int:account_id>/strategy/stop/",
        AccountStrategyStopView.as_view(),
        name="account_strategy_stop",
    ),
    path(
        "accounts/<int:account_id>/strategy/status/",
        AccountStrategyStatusView.as_view(),
        name="account_strategy_status",
    ),
    path(
        "accounts/<int:account_id>/strategy/config/",
        AccountStrategyConfigView.as_view(),
        name="account_strategy_config",
    ),
    # Backtest endpoints
    path("backtest/", BacktestListCreateView.as_view(), name="backtest_list_create"),
    path("backtest/start/", BacktestListCreateView.as_view(), name="backtest_start"),
    path(
        "backtest/<int:backtest_id>/status/",
        BacktestStatusView.as_view(),
        name="backtest_status",
    ),
    path(
        "backtest/<int:backtest_id>/results/",
        BacktestResultsView.as_view(),
        name="backtest_results",
    ),
]
