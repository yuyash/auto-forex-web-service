"""Trading engine for Floor strategy.

This is the main component that orchestrates all trading operations.
"""

from __future__ import annotations

from decimal import Decimal
from logging import Logger, getLogger

from apps.trading.enums import StrategyType
from apps.trading.strategies.base import Strategy
from apps.trading.strategies.floor.calculators import PnLCalculator, TrendDetector
from apps.trading.strategies.floor.candle import CandleManager
from apps.trading.strategies.floor.layer import LayerManager
from apps.trading.strategies.floor.margin import MarginMonitor
from apps.trading.strategies.floor.models import (
    FloorStrategyConfig,
)
from apps.trading.strategies.registry import register_strategy

logger: Logger = getLogger(name=__name__)


@register_strategy(
    id="floor",
    schema="trading/schemas/floor.json",
    display_name="Floor Strategy",
)
class FloorStrategy(Strategy):
    """Main trading engine for Floor strategy.

    This is the primary component that:
    - Manages all trading components (candles, layers, margin, etc.)
    - Implements strategy-specific decision logic
    - Orchestrates the complete trading flow
    - Processes ticks and generates events
    """

    def __init__(self, instrument: str, pip_size: Decimal, config: FloorStrategyConfig) -> None:
        """Initialize trading engine.

        Args:
            instrument: Trading instrument (e.g., "USD_JPY")
            pip_size: Pip size for instrument
            config: Strategy configuration
        """
        super().__init__(instrument, pip_size, config)

        # Components
        self.candle_manager = CandleManager(config)
        self.layer_manager = LayerManager(config)
        self.margin_monitor = MarginMonitor(config, pip_size)
        self.pnl_calc = PnLCalculator(pip_size)
        self.trend_detector = TrendDetector()

        logger.info(
            "Initialized Floor trading engine: instrument=%s, pip_size=%s, hedging=%s",
            instrument,
            pip_size,
            config.hedging_enabled,
        )

    @staticmethod
    def parse_config(strategy_config) -> FloorStrategyConfig:
        """Parse configuration from StrategyConfiguration model.

        Args:
            strategy_config: StrategyConfiguration model instance

        Returns:
            Parsed FloorStrategyConfig
        """
        return FloorStrategyConfig.from_dict(strategy_config.config_dict)

    @property
    def strategy_type(self) -> StrategyType:
        """Return strategy type."""
        return StrategyType.FLOOR
