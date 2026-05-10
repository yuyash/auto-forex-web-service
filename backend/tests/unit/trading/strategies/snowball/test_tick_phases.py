"""Tests for the Snowball tick phase pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, cast

from apps.trading.dataclasses import StrategyResult
from apps.trading.dataclasses.tick import Tick
from apps.trading.enums import Direction
from apps.trading.strategies.snowball.cycle_state import SnowballStrategyState
from apps.trading.strategies.snowball.tick_phases import (
    SnowballExecutionStateBoundary,
    SnowballTickContext,
    SnowballTickPhaseOutcome,
    SnowballTickPipeline,
    SnowballTickStrategy,
)


@dataclass
class ExecutionStateDouble:
    """ExecutionState stand-in for phase tests."""

    strategy_state: dict[str, Any] = field(default_factory=dict)
    current_balance: Decimal = Decimal("10000")


@dataclass(frozen=True, slots=True)
class InvariantDecisionDouble:
    """Invariant decision stand-in."""

    should_stop: bool = False
    stop_reason: str = ""
    is_error: bool = False


class DecisionEngineDouble:
    """Decision engine that always allows pipeline execution."""

    def invariant_decision(self, _snowball_state: SnowballStrategyState) -> InvariantDecisionDouble:
        return InvariantDecisionDouble()


class StrategyDouble:
    """Minimal strategy surface required by SnowballTickPipeline."""

    def __init__(self) -> None:
        self.instrument = "USD_JPY"
        self.account_currency = "USD"
        self._hedging_enabled = False
        self._grid_order_violation: str | None = "previous-grid-error"
        self._close_order_violation: str | None = "previous-close-error"
        self.decision_engine = DecisionEngineDouble()

    def _create_cycle(
        self,
        _ss: SnowballStrategyState,
        _tick: Tick,
        _direction: Direction,
    ) -> tuple[list[Any], Any]:
        return [], None

    def _close_entry(self, *args: Any, **kwargs: Any) -> Any:
        _ = (args, kwargs)
        return None


class RecordingPhase:
    """Pipeline phase test double that records execution order."""

    def __init__(self, *, name: str, calls: list[str], stop: bool = False) -> None:
        self.name = name
        self.calls = calls
        self.stop = stop

    def run(self, context: SnowballTickContext) -> SnowballTickPhaseOutcome:
        self.calls.append(self.name)
        if not self.stop:
            return SnowballTickPhaseOutcome()
        return SnowballTickPhaseOutcome(
            result=StrategyResult(
                state=context.state,
                events=list(context.events),
                should_stop=True,
                stop_reason=f"{self.name} stopped",
            )
        )


class PipelineFixture:
    """Factory object for pipeline phase tests."""

    def strategy(self) -> SnowballTickStrategy:
        return cast(SnowballTickStrategy, StrategyDouble())

    def state(self) -> ExecutionStateDouble:
        return ExecutionStateDouble()

    def tick(self) -> Tick:
        return Tick.create(
            instrument="USD_JPY",
            timestamp=datetime(2026, 5, 8, tzinfo=UTC),
            bid=Decimal("155.00"),
            ask=Decimal("155.02"),
        )


class TestSnowballTickPipeline:
    """Verify pipeline phase ordering and stop behavior."""

    def test_runs_phases_in_configured_order(self) -> None:
        fixture = PipelineFixture()
        calls: list[str] = []
        pipeline = SnowballTickPipeline()
        pipeline.phases = (
            RecordingPhase(name="first", calls=calls),
            RecordingPhase(name="second", calls=calls),
            RecordingPhase(name="third", calls=calls),
        )

        result = pipeline.run(
            strategy=fixture.strategy(),
            tick=fixture.tick(),
            state=fixture.state(),
        )

        assert calls == ["first", "second", "third"]
        assert result.should_stop is False

    def test_stops_after_completed_phase(self) -> None:
        fixture = PipelineFixture()
        calls: list[str] = []
        pipeline = SnowballTickPipeline()
        pipeline.phases = (
            RecordingPhase(name="first", calls=calls),
            RecordingPhase(name="stop", calls=calls, stop=True),
            RecordingPhase(name="after", calls=calls),
        )

        result = pipeline.run(
            strategy=fixture.strategy(),
            tick=fixture.tick(),
            state=fixture.state(),
        )

        assert calls == ["first", "stop"]
        assert result.should_stop is True
        assert result.stop_reason == "stop stopped"

    def test_resets_strategy_violation_state_before_phases(self) -> None:
        fixture = PipelineFixture()
        strategy = fixture.strategy()
        pipeline = SnowballTickPipeline()
        pipeline.phases = (RecordingPhase(name="only", calls=[]),)

        pipeline.run(strategy=strategy, tick=fixture.tick(), state=fixture.state())

        assert strategy._grid_order_violation is None
        assert strategy._close_order_violation is None


class TestSnowballExecutionStateBoundary:
    """Verify the typed state boundary around ExecutionState.strategy_state."""

    def test_loads_and_persists_snowball_state(self) -> None:
        state = ExecutionStateDouble()
        boundary = SnowballExecutionStateBoundary(state=state)

        snowball_state = boundary.load()
        snowball_state.initialised = True
        boundary.persist(snowball_state)

        assert state.strategy_state["initialised"] is True
        assert state.strategy_state["cycles"] == []

    def test_loads_empty_state_when_raw_value_is_malformed(self) -> None:
        state = ExecutionStateDouble(strategy_state="invalid")  # type: ignore[arg-type]
        boundary = SnowballExecutionStateBoundary(state=state)

        snowball_state = boundary.load()

        assert snowball_state.initialised is False
        assert snowball_state.cycles == []
