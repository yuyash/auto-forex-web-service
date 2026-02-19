"""Main Trading Engine that orchestrates all trading operations.

The TradingEngine is the top-level component that:
- Manages strategy instances
- Coordinates all trading operations
- Provides a unified interface for tasks
"""

from __future__ import annotations

from decimal import Decimal
from logging import Logger, getLogger

from apps.trading.dataclasses import StrategyResult, Tick
from apps.trading.enums import StrategyType
from apps.trading.models import StrategyConfiguration
from apps.trading.models.state import ExecutionState
from apps.trading.strategies.base import Strategy

logger: Logger = getLogger(name=__name__)


class TradingEngine:
    """Main trading engine that orchestrates all trading operations.

    This is the top-level component that tasks interact with.
    It manages the strategy as one of its components.
    """

    def __init__(
        self,
        instrument: str,
        pip_size: Decimal,
        strategy_config: StrategyConfiguration,
        trading_mode: str = "hedging",
    ) -> None:
        """Initialize trading engine.

        Args:
            instrument: Trading instrument (e.g., "USD_JPY")
            pip_size: Pip size for instrument
            strategy_config: Strategy configuration
            trading_mode: "netting" (FIFO, US) or "hedging" (JP, etc.)
        """
        self.instrument = instrument
        self.pip_size = pip_size
        self.strategy_config = strategy_config
        self.trading_mode = trading_mode

        # Create strategy based on type
        self.strategy = self._create_strategy()

        logger.info(
            "Initialized TradingEngine: instrument=%s, pip_size=%s, strategy=%s",
            instrument,
            pip_size,
            strategy_config.strategy_type,
        )

    def _create_strategy(self) -> Strategy:
        """Create strategy instance based on configuration.

        Returns:
            Strategy instance

        Raises:
            ValueError: If strategy type is unknown
        """
        strategy_type = self.strategy_config.strategy_type

        if strategy_type == StrategyType.FLOOR.value:
            from apps.trading.strategies.floor.models import (
                FloorStrategyConfig,
            )
            from apps.trading.strategies.floor.strategy import (
                FloorStrategy,
            )

            config = FloorStrategyConfig.from_dict(self.strategy_config.config_dict)
            return FloorStrategy(
                instrument=self.instrument,
                pip_size=self.pip_size,
                config=config,
                trading_mode=self.trading_mode,
            )

        raise ValueError(f"Unknown strategy type: {strategy_type}")

    def on_tick(self, *, tick: Tick, state: ExecutionState) -> StrategyResult:
        """Process tick through strategy.

        Args:
            tick: Market tick data
            state: Current execution state

        Returns:
            Updated state and events
        """
        if state.ticks_processed % 10000 == 0:
            logger.debug(
                "Processing tick: timestamp=%s, bid=%s, ask=%s",
                tick.timestamp,
                tick.bid,
                tick.ask,
            )
        return self.strategy.on_tick(tick=tick, state=state)

    def on_start(self, *, state: ExecutionState) -> StrategyResult:
        """Handle strategy start.

        Args:
            state: Current execution state

        Returns:
            Updated state
        """
        logger.info("Strategy starting")
        return self.strategy.on_start(state=state)

    def on_stop(self, *, state: ExecutionState) -> StrategyResult:
        """Handle strategy stop.

        Args:
            state: Current execution state

        Returns:
            Updated state
        """
        logger.info("Strategy stopping")
        return self.strategy.on_stop(state=state)

    def on_resume(self, *, state: ExecutionState) -> StrategyResult:
        """Handle strategy resume.

        Args:
            state: Current execution state

        Returns:
            Updated state
        """
        return self.strategy.on_resume(state=state)

    @property
    def strategy_type(self) -> StrategyType:
        """Get strategy type.

        Returns:
            Strategy type enum
        """
        return StrategyType(self.strategy_config.strategy_type)
