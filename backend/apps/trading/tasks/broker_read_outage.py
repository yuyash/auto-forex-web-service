"""Runtime handling for temporary broker read outages."""

from __future__ import annotations

from datetime import datetime
from logging import Logger
from typing import Any

from django.utils import timezone as dj_timezone

from apps.trading.enums import TaskStatus, TaskType


class BrokerReadOutageCoordinator:
    """Park a live task when broker drift reads are unavailable after retries."""

    def __init__(
        self, *, task: Any, task_type: TaskType, state_manager: Any, logger: Logger
    ) -> None:
        self.task = task
        self.task_type = task_type
        self.state_manager = state_manager
        self.logger = logger

    def park(self, *, state: Any, reason: str) -> None:
        """Switch the task to IDLE and persist a broker-read outage marker."""
        if self.task_type != TaskType.TRADING:
            return
        now = dj_timezone.now()
        type(self.task).objects.filter(
            pk=self.task.pk,
            status__in=(TaskStatus.RUNNING, TaskStatus.IDLE),
        ).update(status=TaskStatus.IDLE, updated_at=now)
        self.task.refresh_from_db(fields=["status"])
        self.record_marker(state=state, observed_at=now, reason=reason)
        self.state_manager.heartbeat(
            status_message="Broker read unavailable after retries; task parked in IDLE"
        )
        self.logger.warning(
            "Trading task parked in IDLE after broker read retry exhaustion - "
            "task_id=%s, execution_id=%s, reason=%s",
            self.task.pk,
            getattr(self.task, "execution_id", None),
            reason,
        )

    def record_marker(self, *, state: Any, observed_at: datetime, reason: str) -> None:
        """Persist the broker-read outage marker in execution state."""
        strategy_state = state.strategy_state if isinstance(state.strategy_state, dict) else {}
        strategy_state["_broker_read_unavailable"] = {
            "observed_at": observed_at.isoformat(),
            "reason": reason,
        }
        state.strategy_state = strategy_state
        try:
            state.save(update_fields=["strategy_state", "updated_at"])
        except Exception:
            self.logger.debug("Failed to persist broker read outage marker", exc_info=True)


class BrokerReadOutageState:
    """Read broker-read outage markers from execution state."""

    def active(self, state: Any) -> bool:
        """Return True when the state is parked due to broker read outage."""
        strategy_state = state.strategy_state if isinstance(state.strategy_state, dict) else {}
        return isinstance(strategy_state.get("_broker_read_unavailable"), dict)
