"""Main Trading Engine that orchestrates all trading operations.

The TradingEngine is the top-level component that:
- Manages strategy instances
- Coordinates all trading operations
- Provides a unified interface for tasks
"""

from __future__ import annotations

from decimal import Decimal
from logging import Logger, getLogger
from typing import TYPE_CHECKING

from apps.trading.dataclasses import StrategyResult, Tick
from apps.trading.enums import StrategyType
from apps.trading.models.state import ExecutionState

if TYPE_CHECKING:
    from apps.trading.models import StrategyConfiguration
    from apps.trading.strategies.base import Strategy

logger: Logger = getLogger(__name__)


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
    ) -> None:
        """Initialize trading engine.

        Args:
            instrument: Trading instrument (e.g., "USD_JPY")
            pip_size: Pip size for instrument
            strategy_config: Strategy configuration
        """
        self.instrument = instrument
        self.pip_size = pip_size
        self.strategy_config = strategy_config

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
        return self.strategy.on_tick(tick=tick, state=state)

    def on_start(self, *, state: ExecutionState) -> StrategyResult:
        """Handle strategy start.

        Args:
            state: Current execution state

        Returns:
            Updated state
        """
        return self.strategy.on_start(state=state)

    def on_stop(self, *, state: ExecutionState) -> StrategyResult:
        """Handle strategy stop.

        Args:
            state: Current execution state

        Returns:
            Updated state
        """
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
