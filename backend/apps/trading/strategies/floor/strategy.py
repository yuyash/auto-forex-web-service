"""Floor strategy implementation."""

from __future__ import annotations

from decimal import Decimal
from logging import Logger, getLogger
from typing import TYPE_CHECKING

from apps.trading.dataclasses import StrategyResult, Tick
from apps.trading.enums import StrategyType, TradingMode
from apps.trading.events import StrategyEvent
from apps.trading.models.state import ExecutionState
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
    from apps.trading.models import StrategyConfigurations


logger: Logger = getLogger(name=__name__)


@register_strategy(id="floor", schema="trading/schemas/floor.json", display_name="Floor Strategy")
class FloorStrategy(Strategy):
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
    def parse_config(strategy_config: "StrategyConfigurations") -> FloorStrategyConfig:
        """Parse StrategyConfig to FloorStrategyConfig.

        Args:
            strategy_config: StrategyConfig model instance

        Returns:
            FloorStrategyConfig: Parsed and validated configuration
        """
        return FloorStrategyConfig.from_dict(strategy_config.config_dict)

    def on_tick(self, *, tick: Tick, state: ExecutionState) -> StrategyResult:
        """Process a tick and return updated state and events.

        Args:
            tick: Tick dataclass containing market data
            state: Current execution state

        Returns:
            StrategyResult: Updated state and list of emitted events
        """
        if state.ticks_processed % 10000 == 0:
            logger.info(f"FloorStrategy.on_tick called for tick {state.ticks_processed}")

        # Get strategy state from model's JSONField
        s = FloorStrategyState.from_dict(state.strategy_state)
        events: list[StrategyEvent] = []

        # Update state from tick
        self.history_manager.update_from_tick(s, tick)

        # Monitor volatility
        if vol_event := self.volatility_monitor.check(s, tick.timestamp):
            events.append(vol_event)

        # If not running, skip trading logic
        if s.status != StrategyStatus.RUNNING:
            # Update model's strategy_state
            state.strategy_state = s.to_dict()
            return StrategyResult.with_events(state, events)

        # Execute trading logic (delegated)
        events.extend(self.trading_engine.process_initial_entry(s, tick))
        events.extend(self.trading_engine.process_take_profit(s, tick))
        events.extend(self.trading_engine.process_retracements(s, tick))

        # Monitor margin protection
        if margin_event := self.margin_monitor.check(s, tick.timestamp):
            events.append(margin_event)

        if state.ticks_processed % 10000 == 0:
            logger.info(f"FloorStrategy.on_tick completed, returning {len(events)} events")

        # Update model's strategy_state
        state.strategy_state = s.to_dict()
        return StrategyResult.with_events(state, events)

    def on_start(self, *, state: ExecutionState) -> StrategyResult:
        """Called when strategy starts."""
        s = FloorStrategyState.from_dict(state.strategy_state)
        s.status = StrategyStatus.RUNNING
        state.strategy_state = s.to_dict()
        return StrategyResult.from_state(state)

    def on_stop(self, *, state: ExecutionState) -> StrategyResult:
        """Called when strategy stops."""
        s = FloorStrategyState.from_dict(state.strategy_state)
        s.status = StrategyStatus.STOPPED
        state.strategy_state = s.to_dict()
        return StrategyResult.from_state(state)

    def on_resume(self, *, state: ExecutionState) -> StrategyResult:
        """Called when strategy resumes."""
        s = FloorStrategyState.from_dict(state.strategy_state)
        s.status = StrategyStatus.RUNNING
        state.strategy_state = s.to_dict()
        return StrategyResult.from_state(state)
