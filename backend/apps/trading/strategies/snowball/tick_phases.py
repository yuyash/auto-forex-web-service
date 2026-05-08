"""Object-oriented tick pipeline for the Snowball strategy."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Protocol

from apps.trading.dataclasses import StrategyResult
from apps.trading.dataclasses.tick import Tick
from apps.trading.enums import Direction
from apps.trading.events import StrategyEvent
from apps.trading.strategies.snowball.accounting import SnowballAccountMetricsUpdater
from apps.trading.strategies.snowball.cycle_orchestrator import (
    CycleOrchestratorStrategy,
    SnowballActiveCycleProcessor,
    SnowballCycleReseeder,
)
from apps.trading.strategies.snowball.enums import ProtectionLevel
from apps.trading.strategies.snowball.models import SnowballStrategyState
from apps.trading.strategies.snowball.protection import SNOWBALL_PROTECTION, ProtectionStrategy


class SnowballTickStrategy(CycleOrchestratorStrategy, ProtectionStrategy, Protocol):
    """Runtime surface the tick pipeline needs from SnowballStrategy."""

    instrument: str
    account_currency: str
    _hedging_enabled: bool
    _grid_order_violation: str | None
    _close_order_violation: str | None
    decision_engine: Any

    def _create_cycle(
        self,
        ss: SnowballStrategyState,
        tick: Tick,
        direction: Direction,
    ) -> tuple[list[StrategyEvent], Any]: ...

    def _close_entry(self, *args: Any, **kwargs: Any) -> Any: ...


@dataclass
class SnowballTickContext:
    """Mutable execution context shared by Snowball tick phases."""

    strategy: SnowballTickStrategy
    state: Any
    tick: Tick
    snowball_state: SnowballStrategyState
    events: list[StrategyEvent] = field(default_factory=list)
    ratio: Decimal = Decimal("0")
    allow_new_positions: bool = True


@dataclass(frozen=True, slots=True)
class SnowballTickPhaseOutcome:
    """Result returned by a pipeline phase."""

    result: StrategyResult | None = None

    @property
    def completed(self) -> bool:
        """Return True when the pipeline should stop."""
        return self.result is not None


class SnowballTickStateSerializer:
    """Persist SnowballStrategyState back into the task state object."""

    def persist(self, context: SnowballTickContext) -> None:
        """Write the Snowball state dictionary to the execution state."""
        context.state.strategy_state = context.snowball_state.to_dict()

    def result(
        self,
        context: SnowballTickContext,
        *,
        events: list[StrategyEvent] | None = None,
        should_stop: bool = False,
        stop_reason: str | None = None,
        is_error: bool = False,
    ) -> StrategyResult:
        """Persist context and build a StrategyResult."""
        self.persist(context)
        return StrategyResult(
            state=context.state,
            events=context.events if events is None else events,
            should_stop=should_stop,
            stop_reason=stop_reason or "",
            is_error=is_error,
        )


class SnowballInitialInvariantPhase:
    """Stop before mutations when the loaded state is structurally invalid."""

    def __init__(self, *, serializer: SnowballTickStateSerializer | None = None) -> None:
        self.serializer = serializer or SnowballTickStateSerializer()

    def run(self, context: SnowballTickContext) -> SnowballTickPhaseOutcome:
        """Evaluate the pre-tick invariant decision."""
        decision = context.strategy.decision_engine.invariant_decision(context.snowball_state)
        if not decision.should_stop:
            return SnowballTickPhaseOutcome()
        return SnowballTickPhaseOutcome(
            result=self.serializer.result(
                context,
                should_stop=True,
                stop_reason=decision.stop_reason,
                is_error=decision.is_error,
            )
        )


class SnowballAccountMetricsPhase:
    """Refresh account metrics before protection logic runs."""

    def __init__(
        self,
        *,
        updater: SnowballAccountMetricsUpdater | None = None,
    ) -> None:
        self.updater = updater or SnowballAccountMetricsUpdater()

    def run(self, context: SnowballTickContext) -> SnowballTickPhaseOutcome:
        """Update metrics and store the protection ratio on the context."""
        context.ratio = self.updater.update(
            state=context.state,
            ss=context.snowball_state,
            tick=context.tick,
            instrument=context.strategy.instrument,
            account_currency=context.strategy.account_currency,
        )
        return SnowballTickPhaseOutcome()


class SnowballProtectionPhase:
    """Apply emergency, lock, lock-release, and shrink protection."""

    def __init__(self, *, serializer: SnowballTickStateSerializer | None = None) -> None:
        self.serializer = serializer or SnowballTickStateSerializer()

    def run(self, context: SnowballTickContext) -> SnowballTickPhaseOutcome:
        """Run the protection ladder for the current tick."""
        emergency = SNOWBALL_PROTECTION.handle_emergency(
            strategy=context.strategy,
            ss=context.snowball_state,
            tick=context.tick,
            ratio=context.ratio,
        )
        if emergency is not None:
            emergency_events, stop_reason = emergency
            return SnowballTickPhaseOutcome(
                result=self.serializer.result(
                    context,
                    events=emergency_events,
                    should_stop=True,
                    stop_reason=stop_reason,
                    is_error=True,
                )
            )

        lock_events = SNOWBALL_PROTECTION.handle_lock(
            strategy=context.strategy,
            ss=context.snowball_state,
            tick=context.tick,
            ratio=context.ratio,
        )
        if lock_events is not None:
            context.events.extend(lock_events)
        context.allow_new_positions = (
            lock_events is None
            and context.snowball_state.protection_level != ProtectionLevel.LOCKED
        )

        lock_release_result = self._handle_lock_release(context, lock_events=lock_events)
        if lock_release_result.completed:
            return lock_release_result

        shrink_result = self._handle_shrink(context, lock_events=lock_events)
        if shrink_result.completed:
            return shrink_result

        if (
            lock_events is None
            and context.snowball_state.protection_level != ProtectionLevel.NORMAL
        ):
            context.snowball_state.protection_level = ProtectionLevel.NORMAL
        return SnowballTickPhaseOutcome()

    def _handle_lock_release(
        self,
        context: SnowballTickContext,
        *,
        lock_events: list[StrategyEvent] | None,
    ) -> SnowballTickPhaseOutcome:
        if (
            lock_events is not None
            or context.snowball_state.protection_level != ProtectionLevel.LOCKED
        ):
            return SnowballTickPhaseOutcome()

        release_events = SNOWBALL_PROTECTION.handle_lock_release(
            strategy=context.strategy,
            close_entry=context.strategy._close_entry,
            ss=context.snowball_state,
            tick=context.tick,
            ratio=context.ratio,
        )
        return SnowballTickPhaseOutcome(
            result=self.serializer.result(context, events=release_events)
        )

    def _handle_shrink(
        self,
        context: SnowballTickContext,
        *,
        lock_events: list[StrategyEvent] | None,
    ) -> SnowballTickPhaseOutcome:
        if lock_events is not None:
            return SnowballTickPhaseOutcome()

        shrink_events = SNOWBALL_PROTECTION.handle_shrink(
            strategy=context.strategy,
            close_entry=context.strategy._close_entry,
            state=context.state,
            ss=context.snowball_state,
            tick=context.tick,
            ratio=context.ratio,
        )
        if shrink_events is None:
            return SnowballTickPhaseOutcome()

        context.events.extend(shrink_events.events)
        if shrink_events.close_order_violation:
            context.strategy._close_order_violation = shrink_events.close_order_violation
            return SnowballTickPhaseOutcome(
                result=self.serializer.result(
                    context,
                    should_stop=True,
                    stop_reason=(f"Close order violation: {shrink_events.close_order_violation}"),
                    is_error=True,
                )
            )
        return SnowballTickPhaseOutcome(result=self.serializer.result(context))


class SnowballInitialisationPhase:
    """Create first long and optional short cycles."""

    def __init__(self, *, serializer: SnowballTickStateSerializer | None = None) -> None:
        self.serializer = serializer or SnowballTickStateSerializer()

    def run(self, context: SnowballTickContext) -> SnowballTickPhaseOutcome:
        """Initialise the strategy once and complete the tick."""
        if context.snowball_state.initialised:
            return SnowballTickPhaseOutcome()

        init_events, _ = context.strategy._create_cycle(
            context.snowball_state,
            context.tick,
            Direction.LONG,
        )
        context.events.extend(init_events)
        if context.strategy._hedging_enabled:
            short_events, _ = context.strategy._create_cycle(
                context.snowball_state,
                context.tick,
                Direction.SHORT,
            )
            context.events.extend(short_events)
        context.snowball_state.initialised = True
        return SnowballTickPhaseOutcome(result=self.serializer.result(context))


class SnowballActiveCyclePhase:
    """Delegate active cycle processing to a cycle processor object."""

    def __init__(
        self,
        *,
        processor: SnowballActiveCycleProcessor | None = None,
        serializer: SnowballTickStateSerializer | None = None,
    ) -> None:
        self.processor = processor or SnowballActiveCycleProcessor()
        self.serializer = serializer or SnowballTickStateSerializer()

    def run(self, context: SnowballTickContext) -> SnowballTickPhaseOutcome:
        """Process existing active cycles."""
        cycle_result = self.processor.process(
            context.strategy,
            context.snowball_state,
            context.tick,
            allow_new_positions=context.allow_new_positions,
        )
        context.events.extend(cycle_result.events)
        if not cycle_result.stop_reason:
            return SnowballTickPhaseOutcome()
        return SnowballTickPhaseOutcome(
            result=self.serializer.result(
                context,
                should_stop=True,
                stop_reason=cycle_result.stop_reason,
                is_error=cycle_result.is_error,
            )
        )


class SnowballReseedPhase:
    """Reseed long or short directions after all active cycle work."""

    def __init__(self, *, reseeder: SnowballCycleReseeder | None = None) -> None:
        self.reseeder = reseeder or SnowballCycleReseeder()

    def run(self, context: SnowballTickContext) -> SnowballTickPhaseOutcome:
        """Create new cycles when configured conditions are met."""
        context.events.extend(
            self.reseeder.reseed(
                context.strategy,
                context.snowball_state,
                context.tick,
                allow_new_positions=context.allow_new_positions,
            )
        )
        return SnowballTickPhaseOutcome()


class SnowballFinalInvariantPhase:
    """Validate the post-tick Snowball state before returning."""

    def __init__(self, *, serializer: SnowballTickStateSerializer | None = None) -> None:
        self.serializer = serializer or SnowballTickStateSerializer()

    def run(self, context: SnowballTickContext) -> SnowballTickPhaseOutcome:
        """Persist the state and stop if post-mutation invariants are invalid."""
        self.serializer.persist(context)
        decision = context.strategy.decision_engine.invariant_decision(context.snowball_state)
        if not decision.should_stop:
            return SnowballTickPhaseOutcome()
        return SnowballTickPhaseOutcome(
            result=StrategyResult(
                state=context.state,
                events=context.events,
                should_stop=True,
                stop_reason=decision.stop_reason,
                is_error=decision.is_error,
            )
        )


class SnowballTickPipeline:
    """Run Snowball tick processing as named, testable phase objects."""

    def __init__(self, *, serializer: SnowballTickStateSerializer | None = None) -> None:
        serializer = serializer or SnowballTickStateSerializer()
        self.serializer = serializer
        self.phases = (
            SnowballInitialInvariantPhase(serializer=serializer),
            SnowballAccountMetricsPhase(),
            SnowballProtectionPhase(serializer=serializer),
            SnowballInitialisationPhase(serializer=serializer),
            SnowballActiveCyclePhase(serializer=serializer),
            SnowballReseedPhase(),
            SnowballFinalInvariantPhase(serializer=serializer),
        )

    def run(
        self,
        *,
        strategy: SnowballTickStrategy,
        tick: Tick,
        state: Any,
    ) -> StrategyResult:
        """Process a single tick through the Snowball phase pipeline."""
        strategy._grid_order_violation = None
        strategy._close_order_violation = None
        context = self._context(strategy=strategy, tick=tick, state=state)
        for phase in self.phases:
            outcome = phase.run(context)
            if outcome.result is not None:
                return outcome.result
        return self.serializer.result(context)

    def _context(
        self,
        *,
        strategy: SnowballTickStrategy,
        tick: Tick,
        state: Any,
    ) -> SnowballTickContext:
        snowball_state = SnowballStrategyState.from_strategy_state(state.strategy_state)
        snowball_state.last_bid = tick.bid
        snowball_state.last_ask = tick.ask
        snowball_state.last_mid = tick.mid
        return SnowballTickContext(
            strategy=strategy,
            state=state,
            tick=tick,
            snowball_state=snowball_state,
        )
