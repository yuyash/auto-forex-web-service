"""Unit tests for the Adaptive Net strategy."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from apps.trading.dataclasses.tick import Tick
from apps.trading.models.state import ExecutionState
from apps.trading.strategies.adaptive_net.models import AdaptiveNetConfig
from apps.trading.strategies.adaptive_net.strategy import AdaptiveNetStrategy


def _state(*, ticks_processed: int = 0) -> ExecutionState:
    return ExecutionState(
        task_type="backtest",
        task_id=uuid4(),
        execution_id=uuid4(),
        current_balance=Decimal("100000"),
        ticks_processed=ticks_processed,
        strategy_state={},
    )


def _tick(index: int) -> Tick:
    mid = Decimal("150") + Decimal(index) * Decimal("0.001")
    return Tick(
        instrument="USD_JPY",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=index),
        bid=mid - Decimal("0.001"),
        ask=mid + Decimal("0.001"),
        mid=mid,
    )


def test_disabled_metrics_are_not_published_or_used() -> None:
    config = AdaptiveNetConfig(
        lookback_ticks=20,
        lookback_window_seconds=0,
        rebalance_interval_ticks=1,
        rebalance_interval_seconds=0,
        metric_publish_interval_ticks=1,
        metric_publish_interval_seconds=0,
        decision_interval_metric_publishes=1,
        decision_interval_seconds=0,
        enable_regime_metric=False,
        enable_trend_momentum_metric=True,
        enable_mean_reversion_metric=False,
        enable_risk_condition_metric=False,
        enable_inventory_exposure_metric=False,
    )
    strategy = AdaptiveNetStrategy("USD_JPY", Decimal("0.01"), config)
    state = _state()

    for index in range(21):
        state.ticks_processed = index
        state = strategy.on_tick(tick=_tick(index), state=state).state

    strategy_state = state.strategy_state
    assert strategy_state["published_metric_names"] == ["trend_momentum"]
    assert [m["name"] for m in strategy_state["metric_signals"]] == ["trend_momentum"]
    assert "adaptive_net_trend_momentum_direction_score" in strategy_state["metrics"]
    assert "adaptive_net_regime_direction_score" not in strategy_state["metrics"]
    assert "adaptive_net_decision_edge" in strategy_state["metrics"]
    assert "adaptive_net_position_after_net_units" in strategy_state["metrics"]


def test_metric_publish_interval_is_independent_from_rebalance_interval() -> None:
    config = AdaptiveNetConfig(
        lookback_ticks=20,
        lookback_window_seconds=0,
        rebalance_interval_ticks=100,
        rebalance_interval_seconds=0,
        metric_publish_interval_ticks=5,
        metric_publish_interval_seconds=0,
        decision_interval_metric_publishes=2,
        decision_interval_seconds=0,
        enable_regime_metric=False,
        enable_trend_momentum_metric=True,
        enable_mean_reversion_metric=False,
        enable_risk_condition_metric=False,
        enable_inventory_exposure_metric=False,
    )
    strategy = AdaptiveNetStrategy("USD_JPY", Decimal("0.01"), config)
    state = _state()

    for index in range(21):
        state.ticks_processed = index
        state = strategy.on_tick(tick=_tick(index), state=state).state

    first_publish_tick = state.strategy_state["last_metric_publish_tick"]
    first_decision_count = len(state.strategy_state.get("decision_history", []))
    state.ticks_processed = 22
    state = strategy.on_tick(tick=_tick(22), state=state).state
    assert state.strategy_state["last_metric_publish_tick"] == first_publish_tick

    state.ticks_processed = 25
    state = strategy.on_tick(tick=_tick(25), state=state).state
    assert state.strategy_state["last_metric_publish_tick"] == 25
    assert len(state.strategy_state.get("decision_history", [])) == first_decision_count

    state.ticks_processed = 30
    state = strategy.on_tick(tick=_tick(30), state=state).state
    assert state.strategy_state["last_metric_publish_tick"] == 30
    assert len(state.strategy_state.get("decision_history", [])) == first_decision_count + 1
