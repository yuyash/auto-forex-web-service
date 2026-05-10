"""Unit tests for task summary PnL source selection."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.trading.enums import Direction, TaskType
from apps.trading.models import BacktestTask, StrategyConfiguration, TaskExecutionSnapshot
from apps.trading.models.positions import Position
from apps.trading.models.state import ExecutionState
from apps.trading.models.trades import Trade
from apps.trading.services.summary import compute_cached_task_summary, compute_task_summary


def _make_task(*, strategy_type: str, display_currency: str = "JPY") -> BacktestTask:
    user = get_user_model().objects.create_user(
        username=f"user-{uuid4()}",
        email=f"{uuid4()}@example.com",
        password="testpass123",
    )
    config = StrategyConfiguration.objects.create(
        user=user,
        name=f"config-{uuid4()}",
        strategy_type=strategy_type,
        parameters={},
    )
    return BacktestTask.objects.create(
        user=user,
        config=config,
        name=f"task-{uuid4()}",
        instrument="USD_JPY",
        account_currency="USD",
        display_currency=display_currency,
        initial_balance=Decimal("10000"),
        start_time=datetime(2026, 1, 1, tzinfo=UTC),
        end_time=datetime(2026, 1, 2, tzinfo=UTC),
    )


def _create_closed_position(*, task: BacktestTask, execution_id, quote_pnl: Decimal) -> None:
    entry_time = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    Position.objects.create(
        task_type=TaskType.BACKTEST,
        task_id=task.pk,
        execution_id=execution_id,
        instrument=task.instrument,
        direction=Direction.LONG,
        units=1000,
        entry_price=Decimal("150"),
        entry_time=entry_time,
        exit_price=Decimal("150") + quote_pnl / Decimal("1000"),
        exit_time=entry_time + timedelta(minutes=5),
        is_open=False,
    )


def _create_state(
    *,
    task: BacktestTask,
    execution_id,
    realized_account: Decimal,
    realized_quote: Decimal,
) -> None:
    tick_time = datetime(2026, 1, 1, 13, 0, tzinfo=UTC)
    ExecutionState.objects.create(
        task_type=TaskType.BACKTEST,
        task_id=task.pk,
        execution_id=execution_id,
        current_balance=Decimal("10000") + realized_account,
        ticks_processed=10,
        last_tick_timestamp=tick_time,
        last_tick_price=Decimal("150"),
        last_tick_bid=Decimal("149.99"),
        last_tick_ask=Decimal("150.01"),
        strategy_state={
            "metrics": {
                "realized_pnl": str(realized_account),
                "realized_pnl_quote": str(realized_quote),
                "unrealized_pnl": "0",
                "unrealized_pnl_quote": "0",
            }
        },
    )


@pytest.mark.django_db
def test_snowball_net_summary_uses_runtime_pnl_for_partial_close_accounting():
    task = _make_task(strategy_type="snowball_net")
    execution_id = uuid4()
    _create_closed_position(
        task=task,
        execution_id=execution_id,
        quote_pnl=Decimal("85000"),
    )
    _create_state(
        task=task,
        execution_id=execution_id,
        realized_account=Decimal("5000"),
        realized_quote=Decimal("750000"),
    )

    summary = compute_task_summary(
        task_type=TaskType.BACKTEST,
        task_id=str(task.pk),
        execution_id=execution_id,
    )

    assert summary.pnl.realized == Decimal("750000")
    assert summary.pnl.realized_display_money == {
        "amount": "750000",
        "currency": "JPY",
    }
    assert summary.execution.current_balance == Decimal("15000")
    assert summary.execution.current_balance_display == Decimal("2250000")


@pytest.mark.django_db
def test_non_net_summary_keeps_closed_position_pnl_as_authoritative():
    task = _make_task(strategy_type="snowball")
    execution_id = uuid4()
    _create_closed_position(
        task=task,
        execution_id=execution_id,
        quote_pnl=Decimal("85000"),
    )
    _create_state(
        task=task,
        execution_id=execution_id,
        realized_account=Decimal("5000"),
        realized_quote=Decimal("750000"),
    )

    summary = compute_task_summary(
        task_type=TaskType.BACKTEST,
        task_id=str(task.pk),
        execution_id=execution_id,
    )

    assert summary.pnl.realized == Decimal("85000")


@pytest.mark.django_db
def test_task_summary_has_serializer_ready_dto_payload():
    task = _make_task(strategy_type="snowball")
    execution_id = uuid4()
    _create_state(
        task=task,
        execution_id=execution_id,
        realized_account=Decimal("5"),
        realized_quote=Decimal("5"),
    )

    summary = compute_task_summary(
        task_type=TaskType.BACKTEST,
        task_id=str(task.pk),
        execution_id=execution_id,
    )
    payload = summary.to_dict()

    assert payload["pnl"]["realized"] == Decimal("0")
    assert payload["pnl"]["unrealized"] == Decimal("0")
    assert payload["pnl"]["currency"] == "JPY"
    assert payload["pnl"]["total_money"] == {"amount": "0", "currency": "JPY"}
    assert payload["pnl"]["total_display_money"] == {"amount": "0", "currency": "JPY"}
    assert payload["execution"]["ticks_processed"] == 10


@pytest.mark.django_db
def test_backtest_summary_defaults_display_currency_to_account_currency():
    task = _make_task(strategy_type="snowball", display_currency="")
    execution_id = uuid4()
    _create_state(
        task=task,
        execution_id=execution_id,
        realized_account=Decimal("5"),
        realized_quote=Decimal("5"),
    )

    summary = compute_task_summary(
        task_type=TaskType.BACKTEST,
        task_id=str(task.pk),
        execution_id=execution_id,
    )

    assert summary.execution.display_currency == "USD"
    assert summary.execution.current_balance_display_money == {
        "amount": "10005",
        "currency": "USD",
    }
    assert summary.pnl.total_display_money == {"amount": "0", "currency": "USD"}


@pytest.mark.django_db
def test_task_summary_query_count_stays_bounded_for_overview_api():
    task = _make_task(strategy_type="snowball")
    execution_id = uuid4()
    _create_closed_position(
        task=task,
        execution_id=execution_id,
        quote_pnl=Decimal("10"),
    )
    _create_state(
        task=task,
        execution_id=execution_id,
        realized_account=Decimal("10"),
        realized_quote=Decimal("10"),
    )
    Trade.objects.create(
        task_type=TaskType.BACKTEST,
        task_id=task.pk,
        execution_id=execution_id,
        timestamp=datetime(2026, 1, 1, 12, 1, tzinfo=UTC),
        direction=Direction.LONG,
        units=1000,
        instrument=task.instrument,
        price=Decimal("150.01"),
        execution_method="close_position",
    )

    with CaptureQueriesContext(connection) as queries:
        summary = compute_task_summary(
            task_type=TaskType.BACKTEST,
            task_id=str(task.pk),
            execution_id=execution_id,
        )

    assert summary.counts.total_trades == 1
    assert len(queries) <= 9


@pytest.mark.django_db
def test_snowball_net_cached_summary_recomputes_stale_terminal_snapshot():
    task = _make_task(strategy_type="snowball_net")
    execution_id = uuid4()
    task.execution_id = execution_id
    task.save(update_fields=["execution_id"])
    _create_closed_position(
        task=task,
        execution_id=execution_id,
        quote_pnl=Decimal("85000"),
    )
    _create_state(
        task=task,
        execution_id=execution_id,
        realized_account=Decimal("5000"),
        realized_quote=Decimal("750000"),
    )
    TaskExecutionSnapshot.objects.create(
        task_type=TaskType.BACKTEST,
        task_id=task.pk,
        execution_id=execution_id,
        summary={
            "timestamp": "2026-01-01T13:00:00+00:00",
            "pnl": {"realized": "85000", "unrealized": "0"},
            "counts": {},
            "execution": {"current_balance": "15000", "ticks_processed": 10},
            "tick": {"timestamp": None},
            "task": {},
        },
    )

    summary = compute_cached_task_summary(
        task_type=TaskType.BACKTEST,
        task_id=str(task.pk),
        execution_id=execution_id,
    )

    assert summary.pnl.realized == Decimal("750000")
