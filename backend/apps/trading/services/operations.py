"""Operational metrics for trading runtime health."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apps.market.services.oanda_retry import OandaRetryMetricRecorder
from apps.trading.enums import TaskType
from apps.trading.models import ExecutionState, TradingTask


@dataclass(frozen=True, slots=True)
class BrokerReadOutageRecord:
    """Public record for a task parked after broker-read retry exhaustion."""

    task_id: str
    execution_id: str | None
    observed_at: str | None

    def to_dict(self) -> dict[str, str | None]:
        """Return API-safe outage fields."""
        return {
            "task_id": self.task_id,
            "execution_id": self.execution_id,
            "observed_at": self.observed_at,
        }


@dataclass(frozen=True, slots=True)
class BrokerReadOutageSnapshot:
    """Aggregate broker-read outage status."""

    parked_state_count: int
    states_scanned: int
    recent: list[BrokerReadOutageRecord]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable outage snapshot."""
        return {
            "parked_state_count": self.parked_state_count,
            "states_scanned": self.states_scanned,
            "recent": [record.to_dict() for record in self.recent],
        }


class BrokerReadOutageMetricsCollector:
    """Collect broker-read outage markers from execution state."""

    def __init__(
        self,
        *,
        state_model: type[ExecutionState] = ExecutionState,
        task_model: type[TradingTask] = TradingTask,
        scan_limit: int = 500,
    ) -> None:
        self.state_model = state_model
        self.task_model = task_model
        self.scan_limit = scan_limit

    def snapshot(self, *, user: Any | None = None) -> BrokerReadOutageSnapshot:
        """Return outage markers visible to the given user."""
        states = list(self._queryset(user=user)[: self.scan_limit])
        records = [
            record for state in states if (record := self._record_from_state(state)) is not None
        ]
        return BrokerReadOutageSnapshot(
            parked_state_count=len(records),
            states_scanned=len(states),
            recent=records[:20],
        )

    def _queryset(self, *, user: Any | None) -> Any:
        queryset = self.state_model.objects.filter(task_type=TaskType.TRADING).order_by(
            "-updated_at"
        )
        if user is None or getattr(user, "is_staff", False):
            return queryset
        task_ids = self.task_model.objects.filter(user=user).values_list("id", flat=True)
        return queryset.filter(task_id__in=task_ids)

    def _record_from_state(self, state: ExecutionState) -> BrokerReadOutageRecord | None:
        marker = self._marker_from_state(state)
        if marker is None:
            return None
        return BrokerReadOutageRecord(
            task_id=str(state.task_id),
            execution_id=str(state.execution_id) if state.execution_id else None,
            observed_at=self._safe_observed_at(marker),
        )

    def _marker_from_state(self, state: ExecutionState) -> dict[str, Any] | None:
        strategy_state = state.strategy_state if isinstance(state.strategy_state, dict) else {}
        marker = strategy_state.get("_broker_read_unavailable")
        return marker if isinstance(marker, dict) else None

    def _safe_observed_at(self, marker: dict[str, Any]) -> str | None:
        observed_at = marker.get("observed_at")
        return str(observed_at) if observed_at not in (None, "") else None


class TradingOperationsMetricsService:
    """Compose trading operations metrics for API and diagnostics."""

    def __init__(
        self,
        *,
        outage_collector: BrokerReadOutageMetricsCollector | None = None,
        retry_recorder: OandaRetryMetricRecorder | None = None,
    ) -> None:
        self.outage_collector = outage_collector or BrokerReadOutageMetricsCollector()
        self.retry_recorder = retry_recorder or OandaRetryMetricRecorder()

    def snapshot(self, *, user: Any | None = None) -> dict[str, Any]:
        """Return broker outage and OANDA retry metrics."""
        return {
            "broker_read_outage": self.outage_collector.snapshot(user=user).to_dict(),
            "oanda_retry": self.retry_recorder.snapshot().to_dict(),
        }
