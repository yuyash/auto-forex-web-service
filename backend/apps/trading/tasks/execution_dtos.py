"""Typed execution payloads persisted inside strategy state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast

from apps.trading.models.state import ExecutionState


@dataclass(frozen=True, slots=True)
class LiveTickDeliveryState:
    """Live tick delivery diagnostics stored in strategy_state."""

    status: str
    tick_timestamp: str | None
    observed_at: str
    age_seconds: float | None
    max_age_seconds: int
    message: str

    @classmethod
    def from_observation(
        cls,
        *,
        status: str,
        tick_ts: datetime | None,
        observed_at: datetime,
        age_seconds: float | None,
        max_age_seconds: int,
        message: str,
    ) -> "LiveTickDeliveryState":
        """Build delivery diagnostics from a live tick observation."""
        return cls(
            status=status,
            tick_timestamp=tick_ts.isoformat() if tick_ts else None,
            observed_at=observed_at.isoformat(),
            age_seconds=round(age_seconds, 3) if age_seconds is not None else None,
            max_age_seconds=max_age_seconds,
            message=message,
        )

    @classmethod
    def from_state(cls, state: ExecutionState) -> "LiveTickDeliveryState | None":
        """Read delivery diagnostics from an execution state."""
        strategy_state = state.strategy_state if isinstance(state.strategy_state, dict) else {}
        delivery = strategy_state.get("live_tick_delivery")
        if not isinstance(delivery, dict):
            return None
        raw = cast(dict[str, Any], delivery)
        return cls(
            status=str(raw.get("status") or ""),
            tick_timestamp=_optional_str(raw.get("tick_timestamp")),
            observed_at=str(raw.get("observed_at") or ""),
            age_seconds=_optional_float(raw.get("age_seconds")),
            max_age_seconds=_optional_int(raw.get("max_age_seconds")) or 0,
            message=str(raw.get("message") or ""),
        )

    def to_dict(self) -> dict[str, object]:
        """Return the JSON-compatible strategy_state payload."""
        return {
            "status": self.status,
            "tick_timestamp": self.tick_timestamp,
            "observed_at": self.observed_at,
            "age_seconds": self.age_seconds,
            "max_age_seconds": self.max_age_seconds,
            "message": self.message,
        }

    def apply_to(self, state: ExecutionState) -> None:
        """Persist this delivery payload onto an execution state."""
        strategy_state = state.strategy_state if isinstance(state.strategy_state, dict) else {}
        strategy_state = dict(strategy_state)
        strategy_state["live_tick_delivery"] = self.to_dict()
        state.strategy_state = strategy_state


def _optional_str(value: object) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _optional_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        if isinstance(value, (int, float)):
            return float(value)
        return float(str(value))
    except (TypeError, ValueError):
        return None


def _optional_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        return int(str(value))
    except (TypeError, ValueError):
        return None
