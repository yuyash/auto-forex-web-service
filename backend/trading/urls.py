"""
URL configuration for trading app.

This module defines URL patterns for trading data and strategy endpoints.

Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 7.1, 7.2, 12.1
"""

from django.urls import path

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
]
