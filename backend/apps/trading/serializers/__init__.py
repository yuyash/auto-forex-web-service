"""Trading serializers package.

This package contains serializers for trading data.
"""

from apps.trading.serializers.backtest import (
    BacktestTaskCreateSerializer,
    BacktestTaskListSerializer,
    BacktestTaskSerializer,
)
from apps.trading.serializers.events import (
    EquityPointSerializer,
    TradeSerializer,
    TradingEventSerializer,
)
from apps.trading.serializers.strategy import (
    StrategyConfigCreateSerializer,
    StrategyConfigDetailSerializer,
    StrategyConfigListSerializer,
    StrategyConfigSerializer,
    StrategyListSerializer,
)
from apps.trading.serializers.task import (
    BacktestTaskSerializer as BacktestTaskSerializerNew,
)
from apps.trading.serializers.task import (
    TaskLogSerializer,
    TaskSerializer,
)
from apps.trading.serializers.task import (
    TradingTaskSerializer as TradingTaskSerializerNew,
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
    # Events, Trades, Equity
    "TradingEventSerializer",
    "TradeSerializer",
    "EquityPointSerializer",
    # Strategy
    "StrategyConfigCreateSerializer",
    "StrategyConfigDetailSerializer",
    "StrategyConfigListSerializer",
    "StrategyConfigSerializer",
    "StrategyListSerializer",
    # Task (new unified serializers)
    "BacktestTaskSerializerNew",
    "TaskLogSerializer",
    "TaskSerializer",
    "TradingTaskSerializerNew",
    # Tick
    "TickDataCSVSerializer",
    "TickDataSerializer",
    # Trading task
    "TradingTaskCreateSerializer",
    "TradingTaskListSerializer",
    "TradingTaskSerializer",
]
