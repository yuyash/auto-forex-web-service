"""
URL configuration for market app.

This module defines URL patterns for market data endpoints.
"""

from typing import List

from django.urls import URLPattern, path

from apps.market.views import (
    CandleDataView,
    InstrumentDetailView,
    MarketStatusView,
    OandaAccountDetailView,
    OandaAccountView,
    OandaApiHealthView,
    OrderDetailView,
    OrderView,
    PositionDetailView,
    PositionView,
    SupportedGranularitiesView,
    SupportedInstrumentsView,
    TickDataView,
)

app_name = "market"

urlpatterns: List[URLPattern] = [
    path(route="accounts/", view=OandaAccountView.as_view(), name="oanda_accounts_list"),
    path(
        route="accounts/<int:account_id>/",
        view=OandaAccountDetailView.as_view(),
        name="oanda_account_detail",
    ),
    path(route="candles/", view=CandleDataView.as_view(), name="candle_data"),
    path(route="ticks/", view=TickDataView.as_view(), name="tick_data"),
    path(
        route="candles/granularities/",
        view=SupportedGranularitiesView.as_view(),
        name="supported_granularities",
    ),
    path(
        route="instruments/", view=SupportedInstrumentsView.as_view(), name="supported_instruments"
    ),
    path(
        route="instruments/<str:instrument>/",
        view=InstrumentDetailView.as_view(),
        name="instrument_detail",
    ),
    path(route="market/status/", view=MarketStatusView.as_view(), name="market_status"),
    path(route="health/oanda/", view=OandaApiHealthView.as_view(), name="oanda_api_health"),
    path(route="orders/", view=OrderView.as_view(), name="order_list_create"),
    path(route="orders/<str:order_id>/", view=OrderDetailView.as_view(), name="order_detail"),
    path(route="positions/", view=PositionView.as_view(), name="position_list"),
    path(
        route="positions/<str:position_id>/",
        view=PositionDetailView.as_view(),
        name="position_detail",
    ),
]
