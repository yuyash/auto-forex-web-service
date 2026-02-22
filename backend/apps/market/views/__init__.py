"""Market views package."""

from typing import List

from apps.market.views.candles import CandleDataView
from apps.market.views.granularities import SupportedGranularitiesView
from apps.market.views.health import OandaApiHealthView
from apps.market.views.instruments import InstrumentDetailView, SupportedInstrumentsView
from apps.market.views.market import MarketStatusView
from apps.market.views.oanda import OandaAccountDetailView, OandaAccountView
from apps.market.views.orders import OrderDetailView, OrderView
from apps.market.views.positions import PositionDetailView, PositionView
from apps.market.views.ticks import TickDataRangeView, TickDataView

__all__: List[str] = [
    "CandleDataView",
    "InstrumentDetailView",
    "MarketStatusView",
    "OandaAccountDetailView",
    "OandaAccountView",
    "OandaApiHealthView",
    "OrderDetailView",
    "OrderView",
    "PositionDetailView",
    "PositionView",
    "SupportedGranularitiesView",
    "SupportedInstrumentsView",
    "TickDataRangeView",
    "TickDataView",
]
