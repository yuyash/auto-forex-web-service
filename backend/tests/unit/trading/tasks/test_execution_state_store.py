"""Tests for execution state persistence helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from apps.trading.tasks.execution_state_store import (
    ExecutionStateConflict,
    ExecutionStateStore,
)


class StateDouble(SimpleNamespace):
    """Lightweight state object with a patchable manager."""


class TestExecutionStateStore:
    """Tests for optimistic execution state persistence."""

    def test_save_updates_expected_columns_and_bumps_version(self):
        manager = MagicMock()
        manager.filter.return_value.update.return_value = 1
        StateDouble.objects = manager

        timestamp = datetime(2024, 6, 1, 12, 0, tzinfo=timezone.utc)
        state = StateDouble(
            pk=uuid4(),
            task_id=uuid4(),
            execution_id=uuid4(),
            state_version=3,
            strategy_state={"grid": []},
            current_balance=Decimal("10000"),
            ticks_processed=25,
            last_tick_timestamp=timestamp,
            resume_cursor_timestamp=None,
            last_tick_price=Decimal("1.2500"),
            last_tick_bid=Decimal("1.2499"),
            last_tick_ask=Decimal("1.2501"),
        )

        ExecutionStateStore().save(state)

        manager.filter.assert_called_once_with(pk=state.pk, state_version=3)
        update_kwargs = manager.filter.return_value.update.call_args.kwargs
        assert update_kwargs["strategy_state"] == {"grid": []}
        assert update_kwargs["resume_cursor_timestamp"] == timestamp
        assert state.state_version == 4

    def test_save_raises_on_optimistic_lock_conflict(self):
        manager = MagicMock()
        manager.filter.return_value.update.return_value = 0
        StateDouble.objects = manager

        state = StateDouble(
            pk=uuid4(),
            task_id=uuid4(),
            execution_id=uuid4(),
            state_version=3,
            strategy_state={},
            current_balance=Decimal("10000"),
            ticks_processed=0,
            last_tick_timestamp=None,
            resume_cursor_timestamp=None,
            last_tick_price=None,
            last_tick_bid=None,
            last_tick_ask=None,
        )

        with pytest.raises(ExecutionStateConflict):
            ExecutionStateStore().save(state)
