"""Floor strategy implementation."""

from __future__ import annotations

from decimal import Decimal
from logging import Logger, getLogger
from typing import TYPE_CHECKING

from apps.trading.dataclasses import ExecutionState, StrategyResult, Tick
from apps.trading.enums import StrategyType, TradingMode
from apps.trading.events import StrategyEvent
from apps.trading.services.registry import register_strategy
from apps.trading.strategies.base import Strategy
from apps.trading.strategies.floor.calculators import IndicatorCalculator, PriceCalculator
from apps.trading.strategies.floor.components import (
    FloorDirectionDecider,
    FloorLayerManager,
    FloorVolatilityMonitor,
)
from apps.trading.strategies.floor.enums import StrategyStatus
from apps.trading.strategies.floor.history import PriceHistoryManager
from apps.trading.strategies.floor.models import FloorStrategyConfig, FloorStrategyState
from apps.trading.strategies.floor.monitors import MarginProtectionMonitor, VolatilityMonitor
from apps.trading.strategies.floor.trading import TradingEngine

if TYPE_CHECKING:
    from apps.trading.models import StrategyConfig


logger: Logger = getLogger(name=__name__)


@register_strategy(id="floor", schema="trading/schemas/floor.json", display_name="Floor Strategy")
class FloorStrategy(Strategy[FloorStrategyState]):
    """Floor strategy implementation."""

    config: FloorStrategyConfig

    # Components
    history_manager: PriceHistoryManager
    volatility_monitor: VolatilityMonitor
    margin_monitor: MarginProtectionMonitor
    trading_engine: TradingEngine

    def __init__(
        self,
        instrument: str,
        pip_size: Decimal,
        config: FloorStrategyConfig,
        trading_mode: TradingMode = TradingMode.NETTING,
    ) -> None:
        """Initialize the strategy with instrument, pip_size, and configuration.

        Args:
            instrument: Trading instrument (e.g., "USD_JPY")
            pip_size: Pip size for the instrument
            config: Parsed FloorStrategyConfig instance
            trading_mode: Trading mode (netting or hedging)
        """
        super().__init__(instrument, pip_size, config)

        # Initialize calculation components
        price_calc = PriceCalculator(pip_size, trading_mode)
        indicator_calc = IndicatorCalculator()
        direction_decider = FloorDirectionDecider(config, indicator_calc)
        volatility_monitor_component = FloorVolatilityMonitor(config, price_calc)
        layer_manager = FloorLayerManager(config, price_calc)
        history_manager = PriceHistoryManager(config)

        # Initialize high-level components
        self.history_manager = history_manager
        self.volatility_monitor = VolatilityMonitor(config, volatility_monitor_component)
        self.margin_monitor = MarginProtectionMonitor(config)
        self.trading_engine = TradingEngine(
            config,
            price_calc,
            direction_decider,
            layer_manager,
            history_manager,
            trading_mode,
        )

    @property
    def strategy_type(self) -> "StrategyType":
        """Return the strategy type enum value."""
        return StrategyType.FLOOR

    @staticmethod
    def parse_config(strategy_config: "StrategyConfig") -> FloorStrategyConfig:
        """Parse StrategyConfig to FloorStrategyConfig.

        Args:
            strategy_config: StrategyConfig model instance

        Returns:
            FloorStrategyConfig: Parsed and validated configuration
        """
        return FloorStrategyConfig.from_dict(strategy_config.config_dict)

    def get_state_class(self) -> type[FloorStrategyState]:
        """Return the strategy state class.

        Returns:
            FloorStrategyState class
        """
        return FloorStrategyState

    def on_tick(
        self, *, tick: Tick, state: ExecutionState[FloorStrategyState]
    ) -> StrategyResult[FloorStrategyState]:
        """Process a tick and return updated state and events.

        Args:
            tick: Tick dataclass containing market data
            state: Current execution state with FloorStrategyState

        Returns:
            StrategyResult: Updated state and list of emitted events
        """
        if state.ticks_processed % 10000 == 0:
            logger.info(f"FloorStrategy.on_tick called for tick {state.ticks_processed}")

        s = state.strategy_state
        events: list[StrategyEvent] = []

        # Update state from tick
        self.history_manager.update_from_tick(s, tick)

        # Monitor volatility
        if vol_event := self.volatility_monitor.check(s, tick.timestamp):
            events.append(vol_event)

        # If not running, skip trading logic
        if s.status != StrategyStatus.RUNNING:
            return StrategyResult.with_events(state.copy_with(strategy_state=s), events)

        # Execute trading logic (delegated)
        events.extend(self.trading_engine.process_initial_entry(s, tick))
        events.extend(self.trading_engine.process_take_profit(s, tick))
        events.extend(self.trading_engine.process_retracements(s, tick))

        # Monitor margin protection
        if margin_event := self.margin_monitor.check(s, tick.timestamp):
            events.append(margin_event)

        if state.ticks_processed % 10000 == 0:
            logger.info(f"FloorStrategy.on_tick completed, returning {len(events)} events")

        return StrategyResult.with_events(state.copy_with(strategy_state=s), events)

    def on_start(
        self, *, state: ExecutionState[FloorStrategyState]
    ) -> StrategyResult[FloorStrategyState]:
        """Called when strategy starts."""
        s: FloorStrategyState = state.strategy_state
        s.status = StrategyStatus.RUNNING
        return StrategyResult.from_state(state.copy_with(strategy_state=s))

    def on_stop(
        self, *, state: ExecutionState[FloorStrategyState]
    ) -> StrategyResult[FloorStrategyState]:
        """Called when strategy stops."""
        s: FloorStrategyState = state.strategy_state
        s.status = StrategyStatus.STOPPED
        return StrategyResult.from_state(state.copy_with(strategy_state=s))

    def on_resume(
        self, *, state: ExecutionState[FloorStrategyState]
    ) -> StrategyResult[FloorStrategyState]:
        """Called when strategy resumes."""
        s: FloorStrategyState = state.strategy_state
        s.status = StrategyStatus.RUNNING
        return StrategyResult.from_state(state.copy_with(strategy_state=s))
