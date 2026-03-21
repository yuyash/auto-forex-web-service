"""Integration tests for Snowball backtest tick simulations via BacktestExecutor."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from apps.trading.dataclasses import Tick
from apps.trading.engine import TradingEngine
from apps.trading.models import ExecutionState, Position, Trade, TradingEvent
from apps.trading.tasks.executor import BacktestExecutor
from apps.trading.tasks.source import TickDataSource
from tests.integration.factories import (
    BacktestTaskFactory,
    StrategyConfigurationFactory,
    UserFactory,
)


class StaticTickDataSource(TickDataSource):
    """Simple tick source that yields a fixed batch once."""

    def __init__(self, ticks: list[Tick]) -> None:
        self._ticks = ticks

    def __iter__(self):
        yield self._ticks

    def close(self) -> None:
        """Release resources."""


def _tick(ts: datetime, bid: str, ask: str) -> Tick:
    return Tick.create(
        instrument="USD_JPY",
        timestamp=ts,
        bid=Decimal(bid),
        ask=Decimal(ask),
    )


def _normalize_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """Normalize strategy-state entries for stable comparisons."""
    normalized = {
        key: entry.get(key)
        for key in (
            "step",
            "direction",
            "entry_price",
            "close_price",
            "units",
            "layer_number",
            "retracement_count",
            "basket",
            "root_entry_id",
            "parent_entry_id",
            "visual_group_id",
            "expected_interval_pips",
            "actual_interval_pips",
            "expected_tp_pips",
            "validation_status",
        )
    }
    for key in (
        "entry_price",
        "close_price",
        "expected_interval_pips",
        "actual_interval_pips",
        "expected_tp_pips",
    ):
        value = normalized.get(key)
        if value not in (None, ""):
            normalized[key] = str(Decimal(str(value)).normalize())
    return normalized


def _run_snowball_backtest(
    *,
    parameters: dict[str, Any],
    ticks: list[Tick],
    initial_balance: Decimal = Decimal("100000"),
) -> tuple[Any, ExecutionState]:
    """Run a Snowball backtest through the real executor and return final state."""
    user = UserFactory()
    config = StrategyConfigurationFactory(
        user=user,
        strategy_type="snowball",
        parameters=parameters,
    )
    task = BacktestTaskFactory(
        user=user,
        config=config,
        instrument="USD_JPY",
        initial_balance=initial_balance,
        status="running",
    )
    task.execution_id = uuid4()
    task.save(update_fields=["execution_id"])

    engine = TradingEngine(task.instrument, task.pip_size, task.config)
    data_source = StaticTickDataSource(ticks)

    with patch("apps.trading.tasks.executor.StateManager") as mock_state_manager_cls:
        state_manager = MagicMock()
        state_manager.check_control.return_value = MagicMock(should_stop=False)
        mock_state_manager_cls.return_value = state_manager

        BacktestExecutor(
            task=task,
            engine=engine,
            data_source=data_source,
        ).execute()

    state = ExecutionState.objects.get(
        task_type="backtest",
        task_id=task.pk,
        execution_id=task.execution_id,
    )
    return task, state


def _execute_existing_backtest_task(
    *,
    task: Any,
    ticks: list[Tick],
) -> ExecutionState:
    """Execute additional ticks for an existing backtest task/execution."""
    engine = TradingEngine(task.instrument, task.pip_size, task.config)
    data_source = StaticTickDataSource(ticks)

    with patch("apps.trading.tasks.executor.StateManager") as mock_state_manager_cls:
        state_manager = MagicMock()
        state_manager.check_control.return_value = MagicMock(should_stop=False)
        mock_state_manager_cls.return_value = state_manager

        BacktestExecutor(
            task=task,
            engine=engine,
            data_source=data_source,
        ).execute()

    return ExecutionState.objects.get(
        task_type="backtest",
        task_id=task.pk,
        execution_id=task.execution_id,
    )


@pytest.mark.django_db
class TestSnowballBacktestSimulation:
    """Executor-level Snowball simulations driven by fixed tick sequences."""

    def test_reversal_sequence_persists_expected_events_and_state(self) -> None:
        base = datetime(2026, 1, 1, tzinfo=UTC)
        task, state = _run_snowball_backtest(
            parameters={
                "base_units": 1000,
                "m_pips": "20",
                "r_max": 4,
                "f_max": 3,
                "n_pips_head": "10",
                "n_pips_tail": "10",
                "n_pips_flat_steps": 1,
                "interval_mode": "constant",
                "counter_tp_mode": "fixed",
                "counter_tp_pips": "8",
                "spread_guard_enabled": False,
                "shrink_enabled": False,
                "lock_enabled": False,
                "rebalance_enabled": False,
                "m_pips_max": "55",
            },
            ticks=[
                _tick(base, "150.00", "150.02"),
                _tick(base + timedelta(seconds=60), "149.89", "149.91"),
                _tick(base + timedelta(seconds=120), "149.79", "149.81"),
                _tick(base + timedelta(seconds=180), "149.90", "149.92"),
                _tick(base + timedelta(seconds=240), "149.68", "149.70"),
            ],
        )

        events = list(
            TradingEvent.objects.filter(
                task_id=task.pk,
                execution_id=task.execution_id,
            ).order_by("created_at", "id")
        )
        event_summary = [
            (
                event.event_type,
                event.details.get("strategy_event_type"),
                event.details.get("retracement_count"),
            )
            for event in events
        ]

        assert state.ticks_processed == 5
        assert state.strategy_state["add_count"] == 1
        assert state.strategy_state["freeze_count"] == 0
        assert state.current_balance > task.initial_balance
        assert (
            Position.objects.filter(
                task_id=task.pk,
                execution_id=task.execution_id,
                is_open=True,
            ).count()
            == 4
        )
        assert (
            Trade.objects.filter(
                task_id=task.pk,
                execution_id=task.execution_id,
            ).count()
            == 8
        )
        assert event_summary == [
            ("strategy_started", None, None),
            ("open_position", "snowball_trend", 1),
            ("open_position", "snowball_trend", 1),
            ("open_position", "snowball_counter", 2),
            ("open_position", "snowball_counter", 3),
            ("close_position", None, 3),
            ("close_position", None, 1),
            ("open_position", "snowball_trend", 1),
            ("open_position", "snowball_counter", 1),
            ("strategy_stopped", None, None),
        ]

    def test_r_max_reset_updates_cycle_base_units(self) -> None:
        base = datetime(2026, 1, 1, tzinfo=UTC)
        task, state = _run_snowball_backtest(
            parameters={
                "base_units": 1000,
                "m_pips": "50",
                "r_max": 2,
                "f_max": 5,
                "post_r_max_base_factor": "1.5",
                "n_pips_head": "5",
                "n_pips_tail": "5",
                "n_pips_flat_steps": 1,
                "interval_mode": "constant",
                "counter_tp_mode": "fixed",
                "counter_tp_pips": "20",
                "spread_guard_enabled": False,
                "shrink_enabled": False,
                "lock_enabled": False,
                "rebalance_enabled": False,
                "m_pips_max": "55",
            },
            ticks=[
                _tick(base, "150.00", "150.02"),
                _tick(base + timedelta(seconds=60), "149.94", "149.96"),
                _tick(base + timedelta(seconds=120), "149.89", "149.91"),
                _tick(base + timedelta(seconds=180), "149.80", "149.82"),
            ],
        )

        counter_add_retracements = list(
            TradingEvent.objects.filter(
                task_id=task.pk,
                execution_id=task.execution_id,
                event_type="open_position",
            )
            .exclude(details__strategy_event_type="snowball_trend")
            .order_by("created_at", "id")
            .values_list("details__retracement_count", flat=True)
        )

        assert state.ticks_processed == 4
        assert state.strategy_state["add_count"] == 0
        assert state.strategy_state["freeze_count"] == 1
        assert state.strategy_state["cycle_base_units"] == 1500
        assert counter_add_retracements == [2, 3]

    def test_spread_guard_blocks_initialisation_through_executor(self) -> None:
        base = datetime(2026, 1, 1, tzinfo=UTC)
        task, state = _run_snowball_backtest(
            parameters={
                "base_units": 1000,
                "m_pips": "50",
                "r_max": 7,
                "f_max": 3,
                "n_pips_head": "30",
                "n_pips_tail": "14",
                "n_pips_flat_steps": 2,
                "interval_mode": "constant",
                "counter_tp_mode": "weighted_avg",
                "spread_guard_enabled": True,
                "spread_guard_pips": "1",
                "shrink_enabled": False,
                "lock_enabled": False,
                "rebalance_enabled": False,
                "m_pips_max": "55",
            },
            ticks=[
                _tick(base, "150.00", "150.05"),
                _tick(base + timedelta(seconds=60), "150.01", "150.06"),
            ],
        )

        events = list(
            TradingEvent.objects.filter(
                task_id=task.pk,
                execution_id=task.execution_id,
            )
            .order_by("created_at", "id")
            .values_list("event_type", flat=True)
        )

        assert state.ticks_processed == 2
        assert state.strategy_state["initialised"] is False
        assert state.strategy_state["trend_basket"] == []
        assert state.strategy_state["counter_basket"] == []
        assert Position.objects.filter(task_id=task.pk, execution_id=task.execution_id).count() == 0
        assert Trade.objects.filter(task_id=task.pk, execution_id=task.execution_id).count() == 0
        assert events == ["strategy_started", "strategy_stopped"]

    def test_resume_run_matches_continuous_run_for_same_tick_sequence(self) -> None:
        base = datetime(2026, 1, 1, tzinfo=UTC)
        parameters = {
            "base_units": 1000,
            "m_pips": "20",
            "r_max": 4,
            "f_max": 3,
            "n_pips_head": "10",
            "n_pips_tail": "10",
            "n_pips_flat_steps": 1,
            "interval_mode": "constant",
            "counter_tp_mode": "fixed",
            "counter_tp_pips": "8",
            "spread_guard_enabled": False,
            "shrink_enabled": False,
            "lock_enabled": False,
            "rebalance_enabled": False,
            "m_pips_max": "55",
        }
        all_ticks = [
            _tick(base, "150.00", "150.02"),
            _tick(base + timedelta(seconds=60), "149.89", "149.91"),
            _tick(base + timedelta(seconds=120), "149.79", "149.81"),
            _tick(base + timedelta(seconds=180), "149.90", "149.92"),
            _tick(base + timedelta(seconds=240), "149.68", "149.70"),
        ]

        full_task, full_state = _run_snowball_backtest(
            parameters=parameters,
            ticks=all_ticks,
        )

        user = UserFactory()
        config = StrategyConfigurationFactory(
            user=user,
            strategy_type="snowball",
            parameters=parameters,
        )
        resumed_task = BacktestTaskFactory(
            user=user,
            config=config,
            instrument="USD_JPY",
            initial_balance=Decimal("100000"),
            status="running",
        )
        resumed_task.execution_id = uuid4()
        resumed_task.save(update_fields=["execution_id"])

        _execute_existing_backtest_task(
            task=resumed_task,
            ticks=all_ticks[:3],
        )
        resumed_state = _execute_existing_backtest_task(
            task=resumed_task,
            ticks=all_ticks[3:],
        )

        assert resumed_state.ticks_processed == full_state.ticks_processed
        assert resumed_state.current_balance == full_state.current_balance
        assert resumed_state.strategy_state["add_count"] == full_state.strategy_state["add_count"]
        assert (
            resumed_state.strategy_state["freeze_count"]
            == full_state.strategy_state["freeze_count"]
        )
        assert (
            resumed_state.strategy_state["cycle_base_units"]
            == full_state.strategy_state["cycle_base_units"]
        )
        assert resumed_state.strategy_state["metrics"] == full_state.strategy_state["metrics"]
        assert [
            _normalize_entry(entry) for entry in resumed_state.strategy_state["trend_basket"]
        ] == [_normalize_entry(entry) for entry in full_state.strategy_state["trend_basket"]]
        assert [
            _normalize_entry(entry) for entry in resumed_state.strategy_state["counter_basket"]
        ] == [_normalize_entry(entry) for entry in full_state.strategy_state["counter_basket"]]
        assert (
            Position.objects.filter(
                task_id=resumed_task.pk,
                execution_id=resumed_task.execution_id,
                is_open=True,
            ).count()
            == Position.objects.filter(
                task_id=full_task.pk,
                execution_id=full_task.execution_id,
                is_open=True,
            ).count()
        )
        assert (
            Trade.objects.filter(
                task_id=resumed_task.pk,
                execution_id=resumed_task.execution_id,
            ).count()
            == Trade.objects.filter(
                task_id=full_task.pk,
                execution_id=full_task.execution_id,
            ).count()
        )
        resumed_lifecycle = list(
            TradingEvent.objects.filter(
                task_id=resumed_task.pk,
                execution_id=resumed_task.execution_id,
            )
            .filter(event_type__in=["strategy_started", "strategy_resumed", "strategy_stopped"])
            .order_by("created_at", "id")
            .values_list("event_type", flat=True)
        )
        assert resumed_lifecycle == [
            "strategy_started",
            "strategy_stopped",
            "strategy_resumed",
            "strategy_stopped",
        ]

    def test_manual_intervals_control_adverse_pip_gap_for_counter_adds(self) -> None:
        base = datetime(2026, 1, 1, tzinfo=UTC)
        task, state = _run_snowball_backtest(
            parameters={
                "base_units": 1000,
                "m_pips": "50",
                "r_max": 4,
                "f_max": 3,
                "n_pips_head": "30",
                "n_pips_tail": "14",
                "n_pips_flat_steps": 2,
                "interval_mode": "manual",
                "manual_intervals": ["5", "10", "15", "20"],
                "counter_tp_mode": "fixed",
                "counter_tp_pips": "25",
                "spread_guard_enabled": False,
                "shrink_enabled": False,
                "lock_enabled": False,
                "rebalance_enabled": False,
                "m_pips_max": "55",
            },
            ticks=[
                _tick(base, "150.00", "150.02"),
                _tick(base + timedelta(seconds=60), "149.94", "149.96"),
                _tick(base + timedelta(seconds=120), "149.86", "149.88"),
                _tick(base + timedelta(seconds=180), "149.84", "149.86"),
            ],
        )

        counter_adds = list(
            TradingEvent.objects.filter(
                task_id=task.pk,
                execution_id=task.execution_id,
                event_type="open_position",
                details__strategy_event_type="snowball_counter",
            )
            .order_by("created_at", "id")
            .values_list(
                "details__retracement_count",
                "details__actual_interval_pips",
                "details__expected_interval_pips",
            )
        )

        assert state.ticks_processed == 4
        assert state.strategy_state["add_count"] == 2
        assert counter_adds == [
            (2, 7, 5.0),
            (3, 11, 10.0),
        ]
