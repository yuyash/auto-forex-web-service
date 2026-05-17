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
    OandaAccountFactory,
    StrategyConfigurationFactory,
    TradingTaskFactory,
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
def test_validate_initial_position_cycles_allows_sparse_layers():
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
                        "planned_exit_price": "150.20",
                        "stop_loss_price": "149.40",
                    },
                    {
                        "layer_number": 2,
                        "retracement_count": 0,
                        "units": 1000,
                        "entry_price": "149.30",
                    },
                ],
            }
        ]
    )

    normalized = validate_initial_position_cycles(
        task=task,
        config=task.config,
        cycles=task.initial_position_cycles,
        pip_size=task.pip_size,
    )

    assert [(p.layer_number, p.retracement_count) for p in normalized[0].positions] == [
        (1, 0),
        (1, 1),
        (2, 0),
    ]


@pytest.mark.django_db
def test_validate_initial_position_cycles_allows_sparse_layer_numbers():
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
                        "layer_number": 2,
                        "retracement_count": 0,
                        "units": 1000,
                        "entry_price": "149.40",
                    },
                    {
                        "layer_number": 4,
                        "retracement_count": 0,
                        "units": 1000,
                        "entry_price": "148.80",
                    },
                ],
            }
        ]
    )
    task.config.parameters = {
        **task.config.parameters,
        "f_max": 4,
    }
    task.config.save(update_fields=["parameters"])

    normalized = validate_initial_position_cycles(
        task=task,
        config=task.config,
        cycles=task.initial_position_cycles,
        pip_size=task.pip_size,
    )

    assert [(p.layer_number, p.retracement_count) for p in normalized[0].positions] == [
        (1, 0),
        (2, 0),
        (4, 0),
    ]


@pytest.mark.django_db
def test_validate_initial_position_cycles_rejects_missing_layer_r0():
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
                    {
                        "layer_number": 2,
                        "retracement_count": 2,
                        "units": 3000,
                        "entry_price": "149.30",
                    },
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

    assert (
        exc_info.value.errors["initial_position_cycles[0].positions[2].retracement_count"]
        == "Layer L2 must start at R0."
    )


@pytest.mark.django_db
def test_validate_initial_position_cycles_rejects_missing_retracement_prefix():
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
                        "retracement_count": 4,
                        "units": 3000,
                        "entry_price": "149.40",
                    },
                ],
            }
        ]
    )
    task.config.parameters = {
        **task.config.parameters,
        "r_max": 4,
        "refill_up_to": 2,
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
        exc_info.value.errors["initial_position_cycles[0].positions[1].retracement_count"]
        == "Layer L1 cannot skip R3 before R4."
    )


@pytest.mark.django_db
def test_validate_initial_position_cycles_allows_closed_slot_placeholders_without_prices():
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
                    {
                        "layer_number": 1,
                        "retracement_count": 1,
                        "status": "closed_slot",
                    },
                    {
                        "layer_number": 2,
                        "retracement_count": 0,
                        "units": 1000,
                        "entry_price": "149.30",
                    },
                ],
            }
        ]
    )

    normalized = validate_initial_position_cycles(
        task=task,
        config=task.config,
        cycles=task.initial_position_cycles,
        pip_size=task.pip_size,
    )

    closed_slot = normalized[0].positions[1]
    assert closed_slot.status == "closed_slot"
    assert closed_slot.units is None
    assert closed_slot.entry_price is None


@pytest.mark.django_db
def test_validate_initial_position_cycles_allows_refillable_empty_gaps_before_closed_slots():
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
                    {"layer_number": 1, "retracement_count": 1, "status": "closed_slot"},
                    {"layer_number": 1, "retracement_count": 2, "status": "closed_slot"},
                    {"layer_number": 1, "retracement_count": 4, "status": "closed_slot"},
                    {"layer_number": 2, "retracement_count": 0, "status": "closed_slot"},
                    {
                        "layer_number": 3,
                        "retracement_count": 0,
                        "units": 1000,
                        "entry_price": "149.20",
                        "planned_exit_price": "149.70",
                        "stop_loss_price": "148.90",
                        "status": "pending_rebuild",
                    },
                ],
            }
        ]
    )
    task.config.parameters = {
        **task.config.parameters,
        "r_max": 5,
        "f_max": 3,
        "refill_up_to": 3,
    }
    task.config.save(update_fields=["parameters"])

    normalized = validate_initial_position_cycles(
        task=task,
        config=task.config,
        cycles=task.initial_position_cycles,
        pip_size=task.pip_size,
    )

    assert [(p.layer_number, p.retracement_count, p.status) for p in normalized[0].positions] == [
        (1, 0, "pending_rebuild"),
        (1, 1, "closed_slot"),
        (1, 2, "closed_slot"),
        (1, 4, "closed_slot"),
        (2, 0, "closed_slot"),
        (3, 0, "pending_rebuild"),
    ]


@pytest.mark.django_db
def test_validate_initial_position_cycles_rejects_closed_slot_with_position_values():
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
                        "status": "closed_slot",
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

    assert (
        exc_info.value.errors["initial_position_cycles[0].positions[0].units"]
        == "Closed slot placeholders cannot define units."
    )
    assert (
        exc_info.value.errors["initial_position_cycles[0].positions[0].entry_price"]
        == "Closed slot placeholders cannot define an entry price."
    )


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
def test_validate_initial_position_cycles_rejects_contradictory_prices():
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
                        "planned_exit_price": "149.90",
                        "stop_loss_price": "150.10",
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

    assert (
        exc_info.value.errors["initial_position_cycles[0].positions[0].planned_exit_price"]
        == "Long position planned exit must be above entry price."
    )
    assert (
        exc_info.value.errors["initial_position_cycles[0].positions[0].stop_loss_price"]
        == "Long position stop loss must be below entry price."
    )


@pytest.mark.django_db
def test_validate_initial_position_cycles_rejects_contradictory_slot_progression():
    task = _task(
        initial_position_cycles=[
            {
                "direction": "short",
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
                        "entry_price": "149.90",
                    },
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

    assert (
        exc_info.value.errors["initial_position_cycles[0].positions[1].entry_price"]
        == "Entry price for L1/R1 must be higher than L1/R0 in a short cycle."
    )


@pytest.mark.django_db
def test_validate_initial_position_cycles_rejects_open_position_with_close_fields():
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
                        "status": "open",
                        "exit_price": "150.50",
                        "close_reason": "tp",
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

    assert (
        exc_info.value.errors["initial_position_cycles[0].positions[0].exit_price"]
        == "Open positions cannot have an exit price."
    )
    assert (
        exc_info.value.errors["initial_position_cycles[0].positions[0].close_reason"]
        == "Open positions cannot have a close reason."
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
    assert state.strategy_state["cycles"][0]["is_initial_position_seed"] is True

    positions = Position.objects.filter(
        task_type=TaskType.BACKTEST,
        task_id=task.pk,
        execution_id=task.execution_id,
    ).order_by("retracement_count")
    assert positions.count() == 2
    assert [p.retracement_count for p in positions] == [0, 1]
    assert all(p.entry_time < task.start_time for p in positions)
    assert all(p.created_at < task.start_time for p in positions)
    assert all(p.is_initial_position_seed for p in positions)

    assert (
        Order.objects.filter(
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
            is_initial_position_seed=True,
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
    assert position.is_initial_position_seed is True
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
            is_initial_position_seed=True,
        ).count()
        == 2
    )


@pytest.mark.django_db
def test_sync_for_task_seeds_closed_slot_placeholders_without_position_records():
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
                        "status": "closed_slot",
                    },
                    {
                        "layer_number": 2,
                        "retracement_count": 0,
                        "units": 1000,
                        "entry_price": "149.30",
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
    l1r1 = cycle["grid"]["layers"][0]["slots"][1]

    assert cycle["is_initial_position_seed"] is True
    assert l1r1["entry"] is None
    assert l1r1["ever_closed"] is True
    assert "pending_rebuild" not in l1r1
    assert (
        Position.objects.filter(
            task_type=TaskType.BACKTEST,
            task_id=task.pk,
            execution_id=task.execution_id,
        ).count()
        == 2
    )


@pytest.mark.django_db
def test_sync_for_trading_task_creates_preview_with_external_oanda_trade_id():
    user = UserFactory()
    account = OandaAccountFactory(
        user=user,
        balance=Decimal("100000"),
        currency="USD",
    )
    task = TradingTaskFactory(
        user=user,
        oanda_account=account,
        config=_snowball_config(user),
        instrument="USD_JPY",
        pip_size=Decimal("0.01"),
        hedging_enabled=True,
        initial_positions_enabled=True,
        initial_position_cycles=[
            {
                "direction": "long",
                "positions": [
                    {
                        "layer_number": 1,
                        "retracement_count": 0,
                        "units": 1000,
                        "entry_price": "150.00",
                        "oanda_trade_id": "OANDA-123",
                    },
                ],
            }
        ],
    )

    BacktestInitialPositionService().sync_for_task(task)
    task.refresh_from_db()

    state = ExecutionState.objects.get(
        task_type=TaskType.TRADING,
        task_id=task.pk,
        execution_id=task.execution_id,
    )
    position = Position.objects.get(
        task_type=TaskType.TRADING,
        task_id=task.pk,
        execution_id=task.execution_id,
    )

    assert is_initial_position_preview_state(state)
    assert state.last_tick_timestamp is None
    assert state.resume_cursor_timestamp is None
    assert position.oanda_trade_id == "OANDA-123"
    assert position.is_initial_position_seed is True
    assert Trade.objects.filter(
        task_type=TaskType.TRADING,
        task_id=task.pk,
        execution_id=task.execution_id,
        oanda_trade_id="OANDA-123",
        is_initial_position_seed=True,
    ).exists()
