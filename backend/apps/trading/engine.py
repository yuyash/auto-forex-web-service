"""Main Trading Engine that orchestrates all trading operations.

The TradingEngine is the top-level component that:
- Manages strategy instances
- Coordinates all trading operations
- Provides a unified interface for tasks
"""

from __future__ import annotations

from decimal import Decimal
from logging import Logger, getLogger

from apps.trading.dataclasses import EventExecutionResult, StrategyResult, Tick
from apps.trading.enums import StrategyType
from apps.trading.events.handler import EventHandler
from apps.trading.models import StrategyConfiguration
from apps.trading.models.state import ExecutionState
from apps.trading.order import OrderService
from apps.trading.strategies.base import Strategy
from apps.trading.strategies.registry import register_all_strategies, registry

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
        account_currency: str = "",
    ) -> None:
        """Initialize trading engine.

        Args:
            instrument: Trading instrument (e.g., "USD_JPY")
            pip_size: Pip size for instrument
            strategy_config: Strategy configuration
            account_currency: Account base currency (e.g., "JPY", "USD")
        """
        self.instrument = instrument
        self.pip_size = pip_size
        self.strategy_config = strategy_config
        self.account_currency = account_currency

        # Create strategy based on type
        self.strategy = self._create_strategy()
        self.strategy.account_currency = account_currency

        logger.info(
            "Initialized TradingEngine: instrument=%s, pip_size=%s, strategy=%s",
            instrument,
            pip_size,
            strategy_config.strategy_type,
        )

    def _create_strategy(self) -> Strategy:
        """Create strategy instance based on configuration.

        Uses the StrategyRegistry to instantiate the correct strategy class.
        New strategies only need to use the @register_strategy decorator
        to be automatically available here.

        Returns:
            Strategy instance

        Raises:
            ValueError: If strategy type is unknown
        """
        register_all_strategies()
        return registry.create(
            instrument=self.instrument,
            pip_size=self.pip_size,
            strategy_config=self.strategy_config,
        )

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
        try:
            return StrategyType(self.strategy_config.strategy_type)
        except ValueError:
            return StrategyType.CUSTOM

    def apply_event_execution_result(
        self,
        *,
        state: ExecutionState,
        execution_result: EventExecutionResult,
    ) -> None:
        """Apply event execution feedback to strategy state."""
        self.strategy.apply_event_execution_result(
            state=state,
            execution_result=execution_result,
        )

    def create_event_handler(self, *, order_service: OrderService, instrument: str) -> EventHandler:
        """Create event handler for this strategy."""
        return self.strategy.create_event_handler(
            order_service=order_service,
            instrument=instrument,
        )
