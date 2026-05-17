"""Tests for initial-position import payload builders."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from apps.market.services.oanda import OpenTrade, OrderDirection
from apps.trading.enums import TaskStatus, TaskType
from apps.trading.models import ExecutionState
from apps.trading.services.backtest_initial_positions import BacktestInitialPositionService
from apps.trading.services.initial_position_imports import InitialPositionImportService
from apps.trading.strategies.snowball.parameters import SNOWBALL_PARAMETER_SERVICE
from tests.integration.factories import (
    BacktestTaskFactory,
    OandaAccountFactory,
    StrategyConfigurationFactory,
    UserFactory,
)


def _snowball_config(user, *, r_max: int = 3):
    parameters = SNOWBALL_PARAMETER_SERVICE.default_parameters()
    parameters.update(
        {
            "instrument": "USD_JPY",
            "base_units": 1000,
            "trend_lot_size": 1,
            "m_pips": 50,
            "r_max": r_max,
            "f_max": 3,
            "stop_loss_enabled": True,
            "stop_loss_mode": "auto",
        }
    )
    return StrategyConfigurationFactory(
        user=user,
        strategy_type="snowball",
        parameters=parameters,
    )


def _source_task_with_open_and_pending_positions():
    user = UserFactory()
    task = BacktestTaskFactory(
        user=user,
        config=_snowball_config(user),
        instrument="USD_JPY",
        pip_size=Decimal("0.01"),
        account_currency="USD",
        initial_balance=Decimal("100000"),
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
                    },
                    {
                        "layer_number": 1,
                        "retracement_count": 1,
                        "units": 2000,
                        "entry_price": "149.70",
                        "planned_exit_price": "150.20",
                        "stop_loss_price": "149.40",
                        "status": "pending_rebuild",
                    },
                ],
            }
        ],
    )
    BacktestInitialPositionService().sync_for_task(task)
    task.status = TaskStatus.STOPPED
    task.save(update_fields=["status", "updated_at"])
    return task


@pytest.mark.django_db
def test_import_from_task_includes_open_and_pending_for_backtest_but_only_pending_for_trading():
    source_task = _source_task_with_open_and_pending_positions()
    service = InitialPositionImportService()

    backtest_result = service.import_from_task(
        user=source_task.user,
        source_task_type=TaskType.BACKTEST.value,
        source_task_id=str(source_task.pk),
        target_task_type=TaskType.BACKTEST.value,
    )
    trading_result = service.import_from_task(
        user=source_task.user,
        source_task_type=TaskType.BACKTEST.value,
        source_task_id=str(source_task.pk),
        target_task_type=TaskType.TRADING.value,
    )

    backtest_positions = backtest_result["cycles"][0]["positions"]
    trading_positions = trading_result["cycles"][0]["positions"]
    assert [position["status"] for position in backtest_positions] == [
        "open",
        "pending_rebuild",
    ]
    assert [position["status"] for position in trading_positions] == [
        "pending_rebuild",
    ]
    assert backtest_result["summary"] == {
        "cycles": 1,
        "positions": 2,
        "open": 1,
        "pending": 1,
        "closed_slots": 0,
    }
    assert trading_result["summary"] == {
        "cycles": 1,
        "positions": 1,
        "open": 0,
        "pending": 1,
        "closed_slots": 0,
    }


@pytest.mark.django_db
def test_import_from_task_includes_closed_slot_placeholders_for_active_cycles():
    user = UserFactory()
    task = BacktestTaskFactory(
        user=user,
        config=_snowball_config(user),
        instrument="USD_JPY",
        pip_size=Decimal("0.01"),
        account_currency="USD",
        initial_balance=Decimal("100000"),
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
                    },
                    {
                        "layer_number": 1,
                        "retracement_count": 1,
                        "units": 2000,
                        "entry_price": "149.70",
                        "planned_exit_price": "150.20",
                        "exit_price": "150.20",
                        "status": "closed",
                    },
                    {
                        "layer_number": 2,
                        "retracement_count": 0,
                        "units": 1000,
                        "entry_price": "149.30",
                    },
                ],
            }
        ],
    )
    BacktestInitialPositionService().sync_for_task(task)
    task.status = TaskStatus.STOPPED
    task.save(update_fields=["status", "updated_at"])

    result = InitialPositionImportService().import_from_task(
        user=task.user,
        source_task_type=TaskType.BACKTEST.value,
        source_task_id=str(task.pk),
        target_task_type=TaskType.BACKTEST.value,
    )

    positions = result["cycles"][0]["positions"]
    assert [position["status"] for position in positions] == [
        "open",
        "closed_slot",
        "open",
    ]
    assert "entry_price" not in positions[1]
    assert "units" not in positions[1]
    assert result["summary"] == {
        "cycles": 1,
        "positions": 3,
        "open": 2,
        "pending": 0,
        "closed_slots": 1,
    }


@pytest.mark.django_db
def test_import_from_task_sorts_cycles_by_original_creation_order():
    user = UserFactory()
    task = BacktestTaskFactory(
        user=user,
        config=_snowball_config(user),
        instrument="USD_JPY",
        pip_size=Decimal("0.01"),
        account_currency="USD",
        initial_balance=Decimal("100000"),
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
                    }
                ],
            },
            {
                "direction": "short",
                "positions": [
                    {
                        "layer_number": 1,
                        "retracement_count": 0,
                        "units": 1000,
                        "entry_price": "151.00",
                    }
                ],
            },
        ],
    )
    BacktestInitialPositionService().sync_for_task(task)
    task.status = TaskStatus.STOPPED
    task.save(update_fields=["status", "updated_at"])
    state = ExecutionState.objects.get(
        task_type=TaskType.BACKTEST.value,
        task_id=task.pk,
    )
    state.strategy_state["cycles"] = list(reversed(state.strategy_state["cycles"]))
    state.save(update_fields=["strategy_state", "updated_at"])

    result = InitialPositionImportService().import_from_task(
        user=task.user,
        source_task_type=TaskType.BACKTEST.value,
        source_task_id=str(task.pk),
        target_task_type=TaskType.BACKTEST.value,
    )

    assert [cycle["direction"] for cycle in result["cycles"]] == ["long", "short"]
    assert [cycle["positions"][0]["entry_price"] for cycle in result["cycles"]] == [
        "150.00",
        "151.00",
    ]


@pytest.mark.django_db
def test_import_from_oanda_builds_direction_cycles(monkeypatch):
    user = UserFactory()
    account = OandaAccountFactory(user=user)
    config = _snowball_config(user, r_max=1)
    open_time = datetime(2026, 1, 1, tzinfo=UTC)
    trades = [
        OpenTrade(
            trade_id="2",
            instrument="USD_JPY",
            direction=OrderDirection.SHORT,
            units=Decimal("2000"),
            entry_price=Decimal("151.20"),
            unrealized_pnl=Decimal("0"),
            open_time=open_time,
            state="OPEN",
            account_id=account.account_id,
        ),
        OpenTrade(
            trade_id="1",
            instrument="USD_JPY",
            direction=OrderDirection.LONG,
            units=Decimal("1000"),
            entry_price=Decimal("150.10"),
            unrealized_pnl=Decimal("0"),
            open_time=open_time,
            state="OPEN",
            account_id=account.account_id,
        ),
        OpenTrade(
            trade_id="3",
            instrument="USD_JPY",
            direction=OrderDirection.SHORT,
            units=Decimal("3000"),
            entry_price=Decimal("151.40"),
            unrealized_pnl=Decimal("0"),
            open_time=open_time,
            state="OPEN",
            account_id=account.account_id,
        ),
    ]

    class FakeOandaService:
        def __init__(self, *, account, retry_policy):
            self.account = account
            self.retry_policy = retry_policy

        def get_open_trades(self, *, instrument):
            assert instrument == "USD_JPY"
            return trades

    monkeypatch.setattr(
        "apps.trading.services.initial_position_imports.OandaService",
        FakeOandaService,
    )

    result = InitialPositionImportService().import_from_oanda(
        user=user,
        account_id=account.pk,
        config_id=str(config.pk),
        instrument="USD_JPY",
    )

    assert result["summary"] == {
        "cycles": 2,
        "positions": 3,
        "open": 3,
        "pending": 0,
        "closed_slots": 0,
    }
    long_cycle, short_cycle = result["cycles"]
    assert long_cycle["direction"] == "long"
    assert short_cycle["direction"] == "short"
    assert long_cycle["positions"][0]["oanda_trade_id"] == "1"
    assert [position["oanda_trade_id"] for position in short_cycle["positions"]] == [
        "2",
        "3",
    ]
    assert [
        (position["layer_number"], position["retracement_count"])
        for position in short_cycle["positions"]
    ] == [(1, 0), (1, 1)]
