"""Integration tests for the paginated strategy-events (cycle list) endpoint."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import cast
from uuid import UUID, uuid4

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.trading.enums import Direction, TaskType
from apps.trading.models import (
    BacktestTask,
    ExecutionState,
    Position,
    Trade,
)
from tests.integration.factories import (
    BacktestTaskFactory,
    StrategyConfigurationFactory,
    UserFactory,
)


def _auth_client(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _make_task(user=None, *, strategy_type: str = "snowball") -> BacktestTask:
    """Create a backtest task with execution_id set for filtering."""
    if user is None:
        user = UserFactory()
    config = StrategyConfigurationFactory(user=user, strategy_type=strategy_type)
    task = cast(
        BacktestTask,
        BacktestTaskFactory(user=user, config=config, status="running"),
    )
    task.execution_id = uuid4()
    task.save()
    return task


def _seed_cycles(task, count: int, start: datetime) -> list[UUID]:
    """Insert ``count`` cycles with two trades each, increasing start times."""
    cycle_ids: list[UUID] = []
    for index in range(count):
        cycle_id = uuid4()
        position_id = uuid4()
        open_trade_id = uuid4()
        close_trade_id = uuid4()
        open_ts = start + timedelta(minutes=index * 2)
        close_ts = open_ts + timedelta(minutes=1)

        Position.objects.create(
            id=position_id,
            task_type=TaskType.BACKTEST,
            task_id=task.pk,
            execution_id=task.execution_id,
            instrument="USD_JPY",
            direction=Direction.LONG,
            units=1000,
            entry_price="150.000",
            entry_time=open_ts,
            exit_price="150.500",
            exit_time=close_ts,
            is_open=False,
        )
        Trade.objects.create(
            id=open_trade_id,
            task_type=TaskType.BACKTEST,
            task_id=task.pk,
            execution_id=task.execution_id,
            timestamp=open_ts,
            direction="long",
            units=1000,
            instrument="USD_JPY",
            price="150.000",
            execution_method="open_position",
            cycle_id=cycle_id,
            position_id=position_id,
        )
        Trade.objects.create(
            id=close_trade_id,
            task_type=TaskType.BACKTEST,
            task_id=task.pk,
            execution_id=task.execution_id,
            timestamp=close_ts,
            direction="long",
            units=-1000,
            instrument="USD_JPY",
            price="150.500",
            execution_method="close_position",
            cycle_id=cycle_id,
            position_id=position_id,
        )
        cycle_ids.append(cycle_id)
    return cycle_ids


def _snowball_state_with_closed_slot_initial_cycle() -> dict:
    return {
        "protection_level": "normal",
        "initialised": True,
        "cycles": [
            {
                "cycle_id": 1,
                "direction": "long",
                "grid": {
                    "layers": [
                        {
                            "layer_number": 1,
                            "slots": [
                                {
                                    "index": 0,
                                    "entry": None,
                                    "ever_closed": True,
                                }
                            ],
                            "base_units": 1000,
                            "refill_up_to": 3,
                        }
                    ]
                },
                "hedge_entries": [],
                "counter_close_count": 0,
                "status": "completed",
                "trade_cycle_id": None,
                "is_initial_position_seed": True,
                "realized_pnl": "0",
            }
        ],
        "next_entry_id": 2,
        "last_bid": None,
        "last_ask": None,
        "last_mid": None,
        "account_balance": "100000",
        "account_nav": "100000",
        "metrics": {},
    }


@pytest.mark.django_db
class TestStrategyEventsPagination:
    """GET /api/trading/tasks/backtest/{id}/strategy-events/ list mode."""

    def test_default_page_returns_first_50_cycles(self):
        task = _make_task()
        client = _auth_client(task.user)
        cycle_ids = _seed_cycles(task, count=120, start=datetime(2024, 6, 1, tzinfo=timezone.utc))

        response = client.get(f"/api/trading/tasks/backtest/{task.pk}/strategy-events/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["pagination"]["page"] == 1
        assert response.data["pagination"]["page_size"] == 50
        assert response.data["pagination"]["total_count"] == 120
        assert response.data["pagination"]["total_pages"] == 3
        assert len(response.data["cycles"]) == 50
        # asc sort by started_at: first returned should be the earliest cycle
        assert response.data["cycles"][0]["cycle_id"] == str(cycle_ids[0])

    def test_second_page_returns_the_next_slice(self):
        task = _make_task()
        client = _auth_client(task.user)
        cycle_ids = _seed_cycles(task, count=120, start=datetime(2024, 6, 1, tzinfo=timezone.utc))

        response = client.get(
            f"/api/trading/tasks/backtest/{task.pk}/strategy-events/",
            {"cycle_page": 2, "cycle_page_size": 50},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["pagination"]["page"] == 2
        assert len(response.data["cycles"]) == 50
        assert response.data["cycles"][0]["cycle_id"] == str(cycle_ids[50])

    def test_descending_sort_reverses_cycle_order(self):
        task = _make_task()
        client = _auth_client(task.user)
        cycle_ids = _seed_cycles(task, count=10, start=datetime(2024, 6, 1, tzinfo=timezone.utc))

        response = client.get(
            f"/api/trading/tasks/backtest/{task.pk}/strategy-events/",
            {"cycle_sort": "desc"},
        )

        assert response.status_code == status.HTTP_200_OK
        returned_ids = [c["cycle_id"] for c in response.data["cycles"]]
        assert returned_ids[0] == str(cycle_ids[-1])
        assert returned_ids[-1] == str(cycle_ids[0])

    def test_status_filter_returns_only_requested_cycles(self):
        task = _make_task()
        client = _auth_client(task.user)

        # seeded cycles are all completed (open + close with no lingering positions)
        _seed_cycles(task, count=3, start=datetime(2024, 6, 1, tzinfo=timezone.utc))
        # Add one active cycle (open but no close)
        active_cycle_id = uuid4()
        active_pos_id = uuid4()
        open_ts = datetime(2024, 6, 1, 10, 0, tzinfo=timezone.utc)
        Position.objects.create(
            id=active_pos_id,
            task_type=TaskType.BACKTEST,
            task_id=task.pk,
            execution_id=task.execution_id,
            instrument="USD_JPY",
            direction=Direction.LONG,
            units=1000,
            entry_price="150.000",
            entry_time=open_ts,
            is_open=True,
        )
        Trade.objects.create(
            id=active_cycle_id,
            task_type=TaskType.BACKTEST,
            task_id=task.pk,
            execution_id=task.execution_id,
            timestamp=open_ts,
            direction="long",
            units=1000,
            instrument="USD_JPY",
            price="150.000",
            execution_method="open_position",
            cycle_id=active_cycle_id,
            position_id=active_pos_id,
        )

        response = client.get(
            f"/api/trading/tasks/backtest/{task.pk}/strategy-events/",
            {"cycle_status": "active"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["pagination"]["total_count"] == 1
        assert response.data["cycles"][0]["cycle_id"] == str(active_cycle_id)
        # Summary reflects the filtered universe
        assert response.data["summary"]["cycle_count"] == 1
        assert response.data["summary"]["active_count"] == 1
        assert response.data["summary"]["completed_count"] == 0

    def test_status_filter_completed_only(self):
        task = _make_task()
        client = _auth_client(task.user)
        _seed_cycles(task, count=2, start=datetime(2024, 6, 1, tzinfo=timezone.utc))

        response = client.get(
            f"/api/trading/tasks/backtest/{task.pk}/strategy-events/",
            {"cycle_status": "completed"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["pagination"]["total_count"] == 2
        assert response.data["summary"]["completed_count"] == 2

    def test_position_id_filter_limits_cycles_to_matching_positions(self):
        task = _make_task()
        client = _auth_client(task.user)
        _seed_cycles(task, count=5, start=datetime(2024, 6, 1, tzinfo=timezone.utc))
        # Snapshot the first cycle's position id to use as a prefix filter
        first_cycle_position_id = (
            Trade.objects.filter(
                task_id=task.pk,
                execution_id=task.execution_id,
                execution_method="open_position",
            )
            .order_by("timestamp")
            .first()
            .position_id
        )
        needle = str(first_cycle_position_id)[:8]

        response = client.get(
            f"/api/trading/tasks/backtest/{task.pk}/strategy-events/",
            {"position_id": needle},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["pagination"]["total_count"] == 1
        assert response.data["cycles"][0]["position_ids"] == [str(first_cycle_position_id)]

    def test_position_id_filter_ignores_needles_shorter_than_three_chars(self):
        task = _make_task()
        client = _auth_client(task.user)
        _seed_cycles(task, count=3, start=datetime(2024, 6, 1, tzinfo=timezone.utc))

        response = client.get(
            f"/api/trading/tasks/backtest/{task.pk}/strategy-events/",
            {"position_id": "ab"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["pagination"]["total_count"] == 3

    def test_trade_id_filter_selects_only_cycles_with_matching_trade(self):
        task = _make_task()
        client = _auth_client(task.user)
        _seed_cycles(task, count=4, start=datetime(2024, 6, 1, tzinfo=timezone.utc))
        target_trade = Trade.objects.filter(
            task_id=task.pk,
            execution_id=task.execution_id,
        ).first()
        needle = str(target_trade.id)[:8]

        response = client.get(
            f"/api/trading/tasks/backtest/{task.pk}/strategy-events/",
            {"trade_id": needle},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["pagination"]["total_count"] == 1
        assert response.data["cycles"][0]["cycle_id"] == str(target_trade.cycle_id)

    def test_list_mode_omits_trades_field_content(self):
        task = _make_task()
        client = _auth_client(task.user)
        _seed_cycles(task, count=2, start=datetime(2024, 6, 1, tzinfo=timezone.utc))

        response = client.get(f"/api/trading/tasks/backtest/{task.pk}/strategy-events/")

        assert response.status_code == status.HTTP_200_OK
        for cycle in response.data["cycles"]:
            assert cycle["trades"] == []
            # Aggregates that feed the sidebar must still be present.
            assert "realized_pnl" in cycle
            assert "unrealized_pnl" in cycle
            assert "trade_count" in cycle
            assert "open_count" in cycle
            assert "close_count" in cycle

    def test_detail_mode_returns_full_trade_ledger(self):
        task = _make_task()
        client = _auth_client(task.user)
        cycle_ids = _seed_cycles(task, count=3, start=datetime(2024, 6, 1, tzinfo=timezone.utc))

        response = client.get(
            f"/api/trading/tasks/backtest/{task.pk}/strategy-events/",
            {"cycle_id": str(cycle_ids[1]), "include_trades": "true"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["pagination"] is None
        assert len(response.data["cycles"]) == 1
        assert len(response.data["cycles"][0]["trades"]) == 2

    def test_detail_mode_omits_trade_ledger_by_default(self):
        task = _make_task()
        client = _auth_client(task.user)
        cycle_ids = _seed_cycles(task, count=1, start=datetime(2024, 6, 1, tzinfo=timezone.utc))

        response = client.get(
            f"/api/trading/tasks/backtest/{task.pk}/strategy-events/",
            {"cycle_id": str(cycle_ids[0])},
        )

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["cycles"]) == 1
        assert response.data["cycles"][0]["trade_count"] == 2
        assert response.data["cycles"][0]["trades"] == []

    def test_initial_position_seed_flag_is_returned_for_cycles_and_trades(self):
        task = _make_task()
        client = _auth_client(task.user)
        cycle_id = _seed_cycles(
            task,
            count=1,
            start=datetime(2024, 6, 1, tzinfo=timezone.utc),
        )[0]
        Trade.objects.filter(task_id=task.pk, execution_id=task.execution_id).update(
            is_initial_position_seed=True
        )

        list_response = client.get(f"/api/trading/tasks/backtest/{task.pk}/strategy-events/")
        detail_response = client.get(
            f"/api/trading/tasks/backtest/{task.pk}/strategy-events/",
            {"cycle_id": str(cycle_id), "include_trades": "true"},
        )

        assert list_response.status_code == status.HTTP_200_OK
        assert list_response.data["cycles"][0]["is_initial_position_seed"] is True
        assert list_response.data["cycles"][0]["initial_position_seed_count"] == 2
        assert detail_response.status_code == status.HTTP_200_OK
        assert detail_response.data["cycles"][0]["is_initial_position_seed"] is True
        assert all(
            trade["is_initial_position_seed"]
            for trade in detail_response.data["cycles"][0]["trades"]
        )

    def test_closed_slot_initial_state_cycle_is_returned_and_marked(self):
        task = _make_task()
        task.initial_positions_enabled = True
        task.initial_position_cycles = [
            {
                "direction": "long",
                "positions": [
                    {
                        "layer_number": 1,
                        "retracement_count": 0,
                        "status": "closed_slot",
                    }
                ],
            }
        ]
        task.save(update_fields=["initial_positions_enabled", "initial_position_cycles"])
        ExecutionState.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=task.pk,
            execution_id=task.execution_id,
            strategy_state=_snowball_state_with_closed_slot_initial_cycle(),
            current_balance=Decimal("100000"),
            last_tick_timestamp=task.start_time,
        )
        client = _auth_client(task.user)

        list_response = client.get(f"/api/trading/tasks/backtest/{task.pk}/strategy-events/")

        assert list_response.status_code == status.HTTP_200_OK
        assert list_response.data["pagination"]["total_count"] == 1
        cycle = list_response.data["cycles"][0]
        assert UUID(cycle["cycle_id"])
        assert cycle["direction"] == "long"
        assert cycle["status"] == "completed"
        assert cycle["trade_count"] == 0
        assert cycle["is_initial_position_seed"] is True
        assert cycle["grid_state"]["summary"]["empty"] == 1

        detail_response = client.get(
            f"/api/trading/tasks/backtest/{task.pk}/strategy-events/",
            {"cycle_id": cycle["cycle_id"]},
        )

        assert detail_response.status_code == status.HTTP_200_OK
        assert detail_response.data["cycles"][0]["cycle_id"] == cycle["cycle_id"]
        assert detail_response.data["cycles"][0]["is_initial_position_seed"] is True
        assert detail_response.data["cycles"][0]["trades"] == []

    def test_summary_reflects_filtered_universe(self):
        task = _make_task()
        client = _auth_client(task.user)
        _seed_cycles(task, count=10, start=datetime(2024, 6, 1, tzinfo=timezone.utc))

        response = client.get(
            f"/api/trading/tasks/backtest/{task.pk}/strategy-events/",
            {"cycle_page_size": 3},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["summary"]["cycle_count"] == 10
        # total_trades counts every trade in the filtered universe, not just
        # the page's slice.
        assert response.data["summary"]["total_trades"] == 20
        assert response.data["pagination"]["total_count"] == 10
        assert response.data["pagination"]["total_pages"] == 4
        assert len(response.data["cycles"]) == 3

    def test_empty_execution_returns_empty_pagination(self):
        task = _make_task()
        client = _auth_client(task.user)

        response = client.get(f"/api/trading/tasks/backtest/{task.pk}/strategy-events/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["cycles"] == []
        assert response.data["pagination"]["total_count"] == 0
        assert response.data["pagination"]["total_pages"] == 0

    def test_realized_pnl_calculated_for_list_cycles(self):
        task = _make_task()
        client = _auth_client(task.user)
        # Each seeded cycle opens at 150.000 and closes at 150.500, so PnL
        # should be 0.500 * 1000 = 500 per cycle.
        _seed_cycles(task, count=2, start=datetime(2024, 6, 1, tzinfo=timezone.utc))

        response = client.get(f"/api/trading/tasks/backtest/{task.pk}/strategy-events/")

        assert response.status_code == status.HTTP_200_OK
        for cycle in response.data["cycles"]:
            # Decimal stringification may include trailing zeros.
            assert Decimal(cycle["realized_pnl"]) == Decimal("500.000")

    def test_unrealized_pnl_picked_up_from_positions(self):
        task = _make_task()
        client = _auth_client(task.user)
        cycle_id = uuid4()
        position_id = uuid4()
        open_ts = datetime(2024, 6, 1, 12, 0, tzinfo=timezone.utc)
        Position.objects.create(
            id=position_id,
            task_type=TaskType.BACKTEST,
            task_id=task.pk,
            execution_id=task.execution_id,
            instrument="USD_JPY",
            direction=Direction.LONG,
            units=1000,
            entry_price="150.000",
            entry_time=open_ts,
            is_open=True,
            unrealized_pnl=Decimal("123.45"),
        )
        Trade.objects.create(
            id=cycle_id,
            task_type=TaskType.BACKTEST,
            task_id=task.pk,
            execution_id=task.execution_id,
            timestamp=open_ts,
            direction="long",
            units=1000,
            instrument="USD_JPY",
            price="150.000",
            execution_method="open_position",
            cycle_id=cycle_id,
            position_id=position_id,
        )

        response = client.get(f"/api/trading/tasks/backtest/{task.pk}/strategy-events/")

        assert response.status_code == status.HTTP_200_OK
        assert Decimal(response.data["cycles"][0]["unrealized_pnl"]) == Decimal("123.45")

    def test_grid_state_still_returned_in_list_mode(self):
        task = _make_task()
        client = _auth_client(task.user)
        cycle_id = uuid4()
        position_id = uuid4()
        open_ts = datetime(2024, 6, 1, 12, 0, tzinfo=timezone.utc)
        Position.objects.create(
            id=position_id,
            task_type=TaskType.BACKTEST,
            task_id=task.pk,
            execution_id=task.execution_id,
            instrument="USD_JPY",
            direction=Direction.LONG,
            units=1000,
            entry_price="150.100",
            entry_time=open_ts,
            is_open=True,
        )
        Trade.objects.create(
            id=cycle_id,
            task_type=TaskType.BACKTEST,
            task_id=task.pk,
            execution_id=task.execution_id,
            timestamp=open_ts,
            direction="long",
            units=1000,
            instrument="USD_JPY",
            price="150.100",
            execution_method="open_position",
            cycle_id=cycle_id,
            position_id=position_id,
        )
        ExecutionState.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=task.pk,
            execution_id=task.execution_id,
            current_balance=Decimal("10000"),
            ticks_processed=1,
            strategy_state={
                "cycles": [
                    {
                        "cycle_id": 1,
                        "direction": "long",
                        "status": "active",
                        "trade_cycle_id": str(cycle_id),
                        "grid": {
                            "layers": [
                                {
                                    "layer_number": 1,
                                    "base_units": 1000,
                                    "refill_up_to": 1,
                                    "slots": [
                                        {
                                            "index": 0,
                                            "entry": {
                                                "entry_id": 1,
                                                "step": 1,
                                                "direction": "long",
                                                "entry_price": "150.1",
                                                "close_price": "150.3",
                                                "units": 1000,
                                                "opened_at": open_ts.isoformat(),
                                                "role": "initial",
                                                "layer_number": 1,
                                                "retracement_count": 0,
                                                "root_entry_id": 1,
                                                "parent_entry_id": 1,
                                                "position_id": str(position_id),
                                                "expected_interval_pips": None,
                                                "actual_interval_pips": None,
                                                "expected_tp_pips": None,
                                                "validation_status": "",
                                                "stop_loss_price": None,
                                                "is_rebuild": False,
                                                "lifecycle_realized_pnl": "0",
                                                "lifecycle_stop_loss_count": 0,
                                            },
                                            "ever_closed": False,
                                        },
                                    ],
                                }
                            ]
                        },
                        "hedge_entries": [],
                        "counter_close_count": 0,
                        "realized_pnl": "0",
                    }
                ],
                "protection_level": "normal",
                "initialised": True,
                "next_entry_id": 2,
                "last_bid": None,
                "last_ask": None,
                "last_mid": None,
                "account_balance": "10000",
                "account_nav": "10000",
                "metrics": {},
            },
        )

        response = client.get(f"/api/trading/tasks/backtest/{task.pk}/strategy-events/")

        assert response.status_code == status.HTTP_200_OK
        cycle = response.data["cycles"][0]
        assert cycle["grid_state"] is not None
        assert cycle["grid_state"]["summary"]["filled"] == 1
        assert cycle["trades"] == []
