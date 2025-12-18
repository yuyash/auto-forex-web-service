"""
URL configuration for market app.

This module defines URL patterns for market data endpoints.

Requirements: 7.1, 7.2, 8.1, 8.2, 9.1, 9.2, 12.1
"""

from django.urls import path

from .views import (
    CandleDataView,
    InstrumentDetailView,
    MarketStatusView,
    OandaApiHealthView,
    OandaAccountDetailView,
    OandaAccountView,
    OrderDetailView,
    OrderView,
    PositionDetailView,
    PositionView,
    SupportedGranularitiesView,
    SupportedInstrumentsView,
)

app_name = "market"

urlpatterns = [
    path("accounts/", OandaAccountView.as_view(), name="oanda_accounts_list"),
    path(
        "accounts/<int:account_id>/", OandaAccountDetailView.as_view(), name="oanda_account_detail"
    ),
    path("candles/", CandleDataView.as_view(), name="candle_data"),
    path(
        "candles/granularities/",
        SupportedGranularitiesView.as_view(),
        name="supported_granularities",
    ),
    path("instruments/", SupportedInstrumentsView.as_view(), name="supported_instruments"),
    path(
        "instruments/<str:instrument>/",
        InstrumentDetailView.as_view(),
        name="instrument_detail",
    ),
    path("market/status/", MarketStatusView.as_view(), name="market_status"),
    path("health/oanda/", OandaApiHealthView.as_view(), name="oanda_api_health"),
    path("orders/", OrderView.as_view(), name="order_list_create"),
    path("orders/<str:order_id>/", OrderDetailView.as_view(), name="order_detail"),
    path("positions/", PositionView.as_view(), name="position_list"),
    path("positions/<str:position_id>/", PositionDetailView.as_view(), name="position_detail"),
]
