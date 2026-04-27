"""Per-cycle orchestration for the Snowball strategy."""

from __future__ import annotations

from dataclasses import dataclass, field
from logging import getLogger
from typing import Protocol

from apps.trading.dataclasses.tick import Tick
from apps.trading.enums import Direction
from apps.trading.events import StrategyEvent
from apps.trading.strategies.snowball.config import SnowballStrategyConfig
from apps.trading.strategies.snowball.enums import CycleStatus
from apps.trading.strategies.snowball.models import SnowballCycle, SnowballStrategyState

logger = getLogger(__name__)


class CycleOrchestratorStrategy(Protocol):
    config: SnowballStrategyConfig
    _close_order_violation: str | None
    _grid_order_violation: str | None
    _hedging_enabled: bool

    def _process_stop_loss_rebuilds(
        self,
        ss: SnowballStrategyState,
        tick: Tick,
        cycle: SnowballCycle,
    ) -> list[StrategyEvent]: ...

    def _process_cycle_counter_closes(
        self,
        ss: SnowballStrategyState,
        tick: Tick,
        cycle: SnowballCycle,
    ) -> list[StrategyEvent]: ...

    def _process_cycle_tp(
        self,
        ss: SnowballStrategyState,
        tick: Tick,
        cycle: SnowballCycle,
        *,
        allow_reentry: bool,
    ) -> list[StrategyEvent]: ...

    def _process_stop_loss_closes(
        self,
        ss: SnowballStrategyState,
        tick: Tick,
        cycle: SnowballCycle,
    ) -> list[StrategyEvent]: ...

    def _process_cycle_counter_adds(
        self,
        ss: SnowballStrategyState,
        tick: Tick,
        cycle: SnowballCycle,
    ) -> list[StrategyEvent]: ...

    def _validate_grid_ordering(self, cycle: SnowballCycle) -> None: ...

    def _create_cycle(
        self,
        ss: SnowballStrategyState,
        tick: Tick,
        direction: Direction,
    ) -> tuple[list[StrategyEvent], SnowballCycle]: ...


@dataclass
class CycleProcessingResult:
    events: list[StrategyEvent] = field(default_factory=list)
    stop_reason: str | None = None
    is_error: bool = False


def process_active_cycles(
    strategy: CycleOrchestratorStrategy,
    ss: SnowballStrategyState,
    tick: Tick,
    *,
    allow_new_positions: bool,
) -> CycleProcessingResult:
    """Process every active Snowball cycle for the current tick."""
    events: list[StrategyEvent] = []
    for cycle in list(ss.active_cycles()):
        if cycle.grid.is_empty() and cycle.grid.has_pending_rebuilds():
            cycle.status = CycleStatus.PENDING
            if allow_new_positions:
                events.extend(strategy._process_stop_loss_rebuilds(ss, tick, cycle))
            if cycle.grid.is_empty():
                strategy._validate_grid_ordering(cycle)
                continue
            cycle.status = CycleStatus.ACTIVE

        counter_close_events = strategy._process_cycle_counter_closes(ss, tick, cycle)
        events.extend(counter_close_events)

        events.extend(
            strategy._process_cycle_tp(
                ss,
                tick,
                cycle,
                allow_reentry=allow_new_positions,
            )
        )

        if strategy._close_order_violation:
            return CycleProcessingResult(
                events=events,
                stop_reason=f"Close order violation: {strategy._close_order_violation}",
                is_error=True,
            )

        events.extend(strategy._process_stop_loss_closes(ss, tick, cycle))

        if allow_new_positions:
            events.extend(strategy._process_stop_loss_rebuilds(ss, tick, cycle))

        if allow_new_positions and not counter_close_events:
            max_iterations = max(1, strategy.config.f_max * (strategy.config.r_max + 1))
            for _ in range(max_iterations):
                add_events = strategy._process_cycle_counter_adds(ss, tick, cycle)
                if not add_events:
                    break
                events.extend(add_events)

        strategy._validate_grid_ordering(cycle)
        if strategy._grid_order_violation and strategy.config.grid_order_validation_enabled:
            return CycleProcessingResult(
                events=events,
                stop_reason=f"Grid ordering violation: {strategy._grid_order_violation}",
                is_error=True,
            )
        if strategy._grid_order_violation:
            logger.error(
                "Grid ordering violation ignored because grid_order_validation_enabled=false: %s",
                strategy._grid_order_violation,
            )
            strategy._grid_order_violation = None

        _refresh_cycle_status(cycle)

    return CycleProcessingResult(events=events)


def reseed_missing_directions(
    strategy: CycleOrchestratorStrategy,
    ss: SnowballStrategyState,
    tick: Tick,
    *,
    allow_new_positions: bool,
) -> list[StrategyEvent]:
    """Create fresh cycles for directions that no longer have a tradable cycle."""
    events: list[StrategyEvent] = []
    active = ss.active_cycles()
    for direction in (Direction.LONG, Direction.SHORT):
        if not allow_new_positions:
            break
        if not strategy._hedging_enabled and direction == Direction.SHORT:
            continue
        dir_cycles = [cycle for cycle in active if cycle.direction == direction]
        if not dir_cycles:
            if (
                strategy.config.stop_loss_enabled
                and not strategy.config.rebuild_enabled
                and not strategy.config.complete_cycle_when_empty
            ):
                logger.debug(
                    "No active %s cycle but auto re-seed disabled; staying idle "
                    "(stop_loss_enabled, rebuild_enabled=False, complete_cycle_when_empty=False)",
                    direction.value.upper(),
                )
                continue
            logger.info("No active %s cycle; creating new cycle", direction.value.upper())
            new_events, _ = strategy._create_cycle(ss, tick, direction)
            events.extend(new_events)
        elif strategy.config.reseed_on_all_pending and all(
            cycle.is_pending for cycle in dir_cycles
        ):
            logger.info(
                "All %s cycles pending; creating new cycle (reseed_on_all_pending)",
                direction.value.upper(),
            )
            new_events, _ = strategy._create_cycle(ss, tick, direction)
            events.extend(new_events)
        elif strategy.config.reseed_on_grid_exhausted and all(
            cycle.is_grid_exhausted(strategy.config.f_max) for cycle in dir_cycles
        ):
            logger.info(
                "All %s cycle grids exhausted; creating new cycle (reseed_on_grid_exhausted)",
                direction.value.upper(),
            )
            new_events, _ = strategy._create_cycle(ss, tick, direction)
            events.extend(new_events)
    return events


def _refresh_cycle_status(cycle: SnowballCycle) -> None:
    if not cycle.is_active and not cycle.is_pending:
        return

    has_open = not cycle.grid.is_empty()
    has_pending = cycle.grid.has_pending_rebuilds()
    if has_open:
        if cycle.is_pending:
            cycle.status = CycleStatus.ACTIVE
    elif has_pending:
        if cycle.is_active:
            cycle.status = CycleStatus.PENDING
    else:
        cycle.status = CycleStatus.COMPLETED
        if cycle.realized_pnl < 0:
            logger.warning(
                "Cycle %d (%s) completed with negative realised P/L: %s",
                cycle.cycle_id,
                cycle.direction.value.upper(),
                cycle.realized_pnl,
            )
