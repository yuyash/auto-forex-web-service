"""Tests for trading operations metrics services."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from apps.market.services.oanda_retry import OandaRetryMetricRecorder
from apps.trading.enums import TaskType
from apps.trading.models import ExecutionState
from apps.trading.services.operations import TradingOperationsMetricsService
from tests.integration.factories import TradingTaskFactory, UserFactory


@pytest.mark.django_db
class TestTradingOperationsMetricsService:
    """Validate trading operations metrics composition."""

    def test_snapshot_filters_outages_and_includes_retry_counters(self):
        owner = UserFactory()
        other = UserFactory()
        owner_task = TradingTaskFactory(user=owner)
        other_task = TradingTaskFactory(user=other)
        owner_execution_id = uuid4()
        self._create_state(
            task_id=owner_task.id,
            execution_id=owner_execution_id,
            observed_at="2026-05-08T07:00:00+00:00",
        )
        self._create_state(
            task_id=other_task.id,
            execution_id=uuid4(),
            observed_at="2026-05-08T07:01:00+00:00",
        )
        recorder = OandaRetryMetricRecorder(key_prefix=f"test:oanda:{uuid4()}")
        recorder.reset()
        recorder.record_retry_scheduled(label="Fetch pending orders")
        recorder.record_recovered(label="Fetch pending orders", attempts_used=3)

        snapshot = TradingOperationsMetricsService(retry_recorder=recorder).snapshot(user=owner)

        outage = snapshot["broker_read_outage"]
        assert outage["parked_state_count"] == 1
        assert outage["recent"] == [
            {
                "task_id": str(owner_task.id),
                "execution_id": str(owner_execution_id),
                "observed_at": "2026-05-08T07:00:00+00:00",
            }
        ]
        assert "reason" not in outage["recent"][0]
        assert snapshot["oanda_retry"]["retry_scheduled"] == 1
        assert snapshot["oanda_retry"]["recovered"] == 1

    def _create_state(self, *, task_id, execution_id, observed_at: str) -> None:
        ExecutionState.objects.create(
            task_type=TaskType.TRADING,
            task_id=task_id,
            execution_id=execution_id,
            strategy_state={
                "_broker_read_unavailable": {
                    "observed_at": observed_at,
                    "reason": "raw upstream failure text stays internal",
                }
            },
            current_balance=Decimal("10000"),
        )
