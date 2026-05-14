"""Tests for Snowball backtest initial-position seeding."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from apps.trading.enums import Direction, TaskStatus, TaskType
from apps.trading.models import ExecutionState, Order, Position, Trade
from apps.trading.services.backtest_initial_positions import (
    BacktestInitialPositionService,
    InitialPositionValidationError,
    is_initial_position_preview_state,
    validate_initial_position_cycles,
)
from apps.trading.strategies.snowball.parameters import SNOWBALL_PARAMETER_SERVICE
from tests.integration.factories import (
    BacktestTaskFactory,
    StrategyConfigurationFactory,
    UserFactory,
)


def _snowball_config(user):
    parameters = SNOWBALL_PARAMETER_SERVICE.default_parameters()
    parameters.update(
        {
            "instrument": "USD_JPY",
            "base_units": 1000,
            "trend_lot_size": 1,
            "m_pips": 50,
            "r_max": 3,
            "f_max": 2,
            "stop_loss_enabled": True,
            "stop_loss_mode": "auto",
        }
    )
    return StrategyConfigurationFactory(
        user=user,
        strategy_type="snowball",
        parameters=parameters,
    )


def _task(*, initial_position_cycles):
    user = UserFactory()
    return BacktestTaskFactory(
        user=user,
        config=_snowball_config(user),
        instrument="USD_JPY",
        pip_size=Decimal("0.01"),
        account_currency="USD",
        initial_balance=Decimal("100000"),
        start_time=datetime(2026, 1, 2, tzinfo=UTC),
        end_time=datetime(2026, 1, 3, tzinfo=UTC),
        initial_positions_enabled=True,
        initial_position_cycles=initial_position_cycles,
    )


@pytest.mark.django_db
def test_validate_initial_position_cycles_requires_contiguous_slots_from_l1_r0():
    task = _task(
        initial_position_cycles=[
            {
                "direction": "long",
                "positions": [
                    {
                        "layer_number": 1,
                        "retracement_count": 1,
                        "units": 1000,
                        "entry_price": "149.70",
                    }
                ],
            }
        ]
    )

    with pytest.raises(InitialPositionValidationError) as exc_info:
        validate_initial_position_cycles(
            task=task,
            config=task.config,
            cycles=task.initial_position_cycles,
            pip_size=task.pip_size,
        )

    assert "initial_position_cycles[0].positions" in exc_info.value.errors
    assert "L1/R0" in exc_info.value.errors["initial_position_cycles[0].positions"]


@pytest.mark.django_db
def test_validate_initial_position_cycles_rejects_stop_loss_when_disabled():
    task = _task(
        initial_position_cycles=[
            {
                "direction": "long",
                "positions": [
                    {
                        "layer_number": 1,
                        "retracement_count": 0,
                        "units": 1000,
                        "entry_price": "150.00",
                        "stop_loss_price": "149.70",
                        "status": "pending_rebuild",
                    }
                ],
            }
        ]
    )
    task.config.parameters = {
        **task.config.parameters,
        "stop_loss_enabled": False,
    }
    task.config.save(update_fields=["parameters"])

    with pytest.raises(InitialPositionValidationError) as exc_info:
        validate_initial_position_cycles(
            task=task,
            config=task.config,
            cycles=task.initial_position_cycles,
            pip_size=task.pip_size,
        )

    assert (
        exc_info.value.errors["initial_position_cycles[0].positions[0].stop_loss_price"]
        == "Stop loss is disabled in the strategy configuration."
    )
    assert (
        exc_info.value.errors["initial_position_cycles[0].positions[0].status"]
        == "Pending rebuild positions require stop loss to be enabled."
    )


@pytest.mark.django_db
def test_sync_for_task_creates_preview_execution_records_before_start():
    task = _task(
        initial_position_cycles=[
            {
                "direction": "long",
                "positions": [
                    {
                        "layer_number": 1,
                        "retracement_count": 0,
                        "units": 1000,
                        "entry_price": "150.00",
                    },
                    {
                        "layer_number": 1,
                        "retracement_count": 1,
                        "units": 2000,
                        "entry_price": "149.70",
                    },
                ],
            }
        ]
    )

    BacktestInitialPositionService().sync_for_task(task)
    task.refresh_from_db()

    assert task.execution_id is not None
    state = ExecutionState.objects.get(
        task_type=TaskType.BACKTEST,
        task_id=task.pk,
        execution_id=task.execution_id,
    )
    assert is_initial_position_preview_state(state)
    assert state.last_tick_timestamp == task.start_time - timedelta(seconds=1)
    assert state.strategy_state["initialised"] is True
    assert len(state.strategy_state["cycles"]) == 1

    positions = Position.objects.filter(
        task_type=TaskType.BACKTEST,
        task_id=task.pk,
        execution_id=task.execution_id,
    ).order_by("retracement_count")
    assert positions.count() == 2
    assert [p.retracement_count for p in positions] == [0, 1]
    assert all(p.entry_time < task.start_time for p in positions)
    assert all(p.created_at < task.start_time for p in positions)

    assert (
        Order.objects.filter(
            task_type=TaskType.BACKTEST,
            task_id=task.pk,
            execution_id=task.execution_id,
        ).count()
        == 2
    )


@pytest.mark.django_db
def test_sync_for_task_creates_stopped_preview_without_deleting_previous_execution():
    task = _task(
        initial_position_cycles=[
            {
                "direction": "long",
                "positions": [
                    {
                        "layer_number": 1,
                        "retracement_count": 0,
                        "units": 1000,
                        "entry_price": "150.00",
                    },
                ],
            }
        ]
    )
    previous_execution_id = uuid4()
    task.status = TaskStatus.STOPPED
    task.execution_id = previous_execution_id
    task.started_at = task.start_time
    task.completed_at = task.start_time + timedelta(minutes=10)
    task.save(
        update_fields=[
            "status",
            "execution_id",
            "started_at",
            "completed_at",
            "updated_at",
        ]
    )
    previous_state = ExecutionState.objects.create(
        task_type=TaskType.BACKTEST,
        task_id=task.pk,
        execution_id=previous_execution_id,
        strategy_state={"cycles": []},
        current_balance=task.initial_balance,
        ticks_processed=10,
        last_tick_timestamp=task.start_time + timedelta(minutes=10),
    )
    previous_position = Position.objects.create(
        task_type=TaskType.BACKTEST,
        task_id=task.pk,
        execution_id=previous_execution_id,
        instrument=task.instrument,
        direction=Direction.LONG,
        units=1000,
        entry_price=Decimal("151.00"),
        entry_time=task.start_time + timedelta(minutes=1),
    )

    BacktestInitialPositionService().sync_for_task(task)
    task.refresh_from_db()

    assert task.execution_id is not None
    assert task.execution_id != previous_execution_id
    assert ExecutionState.objects.filter(pk=previous_state.pk).exists()
    assert Position.objects.filter(pk=previous_position.pk).exists()

    preview_state = ExecutionState.objects.get(
        task_type=TaskType.BACKTEST,
        task_id=task.pk,
        execution_id=task.execution_id,
    )
    assert is_initial_position_preview_state(preview_state)
    seed_position = Position.objects.get(
        task_type=TaskType.BACKTEST,
        task_id=task.pk,
        execution_id=task.execution_id,
    )
    assert seed_position.entry_time < task.start_time
    assert seed_position.entry_price == Decimal("150.0000000000")


@pytest.mark.django_db
def test_sync_for_task_clears_only_preview_execution_when_disabled():
    task = _task(
        initial_position_cycles=[
            {
                "direction": "long",
                "positions": [
                    {
                        "layer_number": 1,
                        "retracement_count": 0,
                        "units": 1000,
                        "entry_price": "150.00",
                    },
                ],
            }
        ]
    )

    BacktestInitialPositionService().sync_for_task(task)
    task.refresh_from_db()
    preview_execution_id = task.execution_id
    assert preview_execution_id is not None

    task.initial_positions_enabled = False
    task.save(update_fields=["initial_positions_enabled", "updated_at"])
    BacktestInitialPositionService().sync_for_task(task)
    task.refresh_from_db()

    assert task.execution_id is None
    assert not ExecutionState.objects.filter(
        task_type=TaskType.BACKTEST,
        task_id=task.pk,
        execution_id=preview_execution_id,
    ).exists()
    assert not Position.objects.filter(
        task_type=TaskType.BACKTEST,
        task_id=task.pk,
        execution_id=preview_execution_id,
    ).exists()


@pytest.mark.django_db
def test_sync_for_task_can_seed_pending_rebuild_positions():
    task = _task(
        initial_position_cycles=[
            {
                "direction": "long",
                "positions": [
                    {
                        "layer_number": 1,
                        "retracement_count": 0,
                        "units": 1000,
                        "entry_price": "150.00",
                        "planned_exit_price": "150.50",
                        "stop_loss_price": "149.70",
                        "status": "pending_rebuild",
                    },
                ],
            }
        ]
    )

    BacktestInitialPositionService().sync_for_task(task)
    task.refresh_from_db()

    state = ExecutionState.objects.get(
        task_type=TaskType.BACKTEST,
        task_id=task.pk,
        execution_id=task.execution_id,
    )
    cycle = state.strategy_state["cycles"][0]
    first_slot = cycle["grid"]["layers"][0]["slots"][0]
    position = Position.objects.get(
        task_type=TaskType.BACKTEST,
        task_id=task.pk,
        execution_id=task.execution_id,
    )

    assert cycle["status"] == "pending"
    assert first_slot["entry"] is None
    assert first_slot["pending_rebuild"]["stop_loss_price"] == "149.70"
    assert position.is_open is False
    assert position.exit_time is not None and position.exit_time < task.start_time
    assert (
        Trade.objects.filter(
            task_type=TaskType.BACKTEST,
            task_id=task.pk,
            execution_id=task.execution_id,
        ).count()
        == 2
    )
    assert (
        Trade.objects.filter(
            task_type=TaskType.BACKTEST,
            task_id=task.pk,
            execution_id=task.execution_id,
        ).count()
        == 2
    )
