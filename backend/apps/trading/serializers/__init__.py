"""Trading serializers package.

This package contains serializers for trading data.
"""

from apps.trading.serializers.backtest import (
    BacktestTaskCreateSerializer,
    BacktestTaskListSerializer,
    BacktestTaskSerializer,
)
from apps.trading.serializers.events import (
    StrategyEventsSerializer,
    StructuredLogSerializer,
)
from apps.trading.serializers.execution import (
    ExecutionsDetailSerializer,
    ExecutionsListSerializer,
    ExecutionsSerializer,
    ExecutionsWithStructuredDataSerializer,
)
from apps.trading.serializers.metrics import TradingMetricsSerializer
from apps.trading.serializers.strategy import (
    StrategyConfigCreateSerializer,
    StrategyConfigDetailSerializer,
    StrategyConfigListSerializer,
    StrategyConfigSerializer,
    StrategyListSerializer,
)
from apps.trading.serializers.tick import TickDataCSVSerializer, TickDataSerializer
from apps.trading.serializers.trading import (
    TradingTaskCreateSerializer,
    TradingTaskListSerializer,
    TradingTaskSerializer,
)

__all__ = [
    # Backtest task
    "BacktestTaskCreateSerializer",
    "BacktestTaskListSerializer",
    "BacktestTaskSerializer",
    # Events
    "StrategyEventsSerializer",
    "StructuredLogSerializer",
    # Execution
    "ExecutionsDetailSerializer",
    "ExecutionsListSerializer",
    "ExecutionsSerializer",
    "ExecutionsWithStructuredDataSerializer",
    # Metrics
    "TradingMetricsSerializer",
    # Strategy
    "StrategyConfigCreateSerializer",
    "StrategyConfigDetailSerializer",
    "StrategyConfigListSerializer",
    "StrategyConfigSerializer",
    "StrategyListSerializer",
    # Tick
    "TickDataCSVSerializer",
    "TickDataSerializer",
    # Trading task
    "TradingTaskCreateSerializer",
    "TradingTaskListSerializer",
    "TradingTaskSerializer",
]
