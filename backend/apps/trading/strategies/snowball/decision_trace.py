"""Decision trace objects for Snowball tick processing."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from apps.trading.dataclasses.tick import Tick
from apps.trading.events import StrategyEvent
from apps.trading.strategies.snowball.models import SnowballCycle, SnowballStrategyState


@dataclass(frozen=True, slots=True)
class SnowballDecisionTraceRecord:
    """One phase-level Snowball decision trace record."""

    phase: str
    outcome: str
    reason: str
    cycle_id: int | None
    direction: str
    event_count: int

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable trace record."""
        return {
            "phase": self.phase,
            "outcome": self.outcome,
            "reason": self.reason,
            "cycle_id": self.cycle_id,
            "direction": self.direction,
            "event_count": self.event_count,
        }


@dataclass(slots=True)
class SnowballDecisionTrace:
    """Per-tick collection of Snowball phase decisions."""

    tick_timestamp: datetime
    records: list[SnowballDecisionTraceRecord] = field(default_factory=list)

    def record(
        self,
        *,
        phase: str,
        outcome: str,
        reason: str,
        cycle: SnowballCycle | None = None,
        event_count: int = 0,
    ) -> None:
        """Append one decision trace record."""
        self.records.append(
            SnowballDecisionTraceRecord(
                phase=phase,
                outcome=outcome,
                reason=reason,
                cycle_id=cycle.cycle_id if cycle is not None else None,
                direction=cycle.direction.value if cycle is not None else "",
                event_count=event_count,
            )
        )

    def record_events(
        self,
        *,
        phase: str,
        cycle: SnowballCycle,
        events: list[StrategyEvent],
        no_event_reason: str,
    ) -> None:
        """Record whether a phase mutated state or skipped with a reason."""
        if events:
            self.record(
                phase=phase,
                outcome="events",
                reason="phase_emitted_events",
                cycle=cycle,
                event_count=len(events),
            )
            return
        self.record(
            phase=phase,
            outcome="skipped",
            reason=no_event_reason,
            cycle=cycle,
            event_count=0,
        )

    def to_dict(self, *, max_records: int) -> dict[str, Any]:
        """Return the latest trace records as a JSON-serializable mapping."""
        records = self.records[-max_records:] if max_records > 0 else []
        return {
            "tick_timestamp": self.tick_timestamp.isoformat(),
            "records": [record.to_dict() for record in records],
        }


class SnowballDecisionTraceRecorder:
    """Persist the latest Snowball decision trace into strategy metrics."""

    def __init__(
        self,
        *,
        metrics_key: str = "snowball_decision_trace",
        max_records: int = 64,
    ) -> None:
        self.metrics_key = metrics_key
        self.max_records = max_records

    def start_tick(self, *, tick: Tick) -> SnowballDecisionTrace:
        """Create an empty trace for the tick being processed."""
        return SnowballDecisionTrace(tick_timestamp=tick.timestamp)

    def persist(self, *, ss: SnowballStrategyState, trace: SnowballDecisionTrace) -> None:
        """Store the latest trace as compact JSON in Snowball metrics."""
        ss.metrics[self.metrics_key] = json.dumps(
            trace.to_dict(max_records=self.max_records),
            separators=(",", ":"),
        )
