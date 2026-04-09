"""Execution feedback dataclasses for event processing."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class EntryExecutionBinding:
    """Binding between strategy entry ID and persisted position ID."""

    entry_id: int | None
    position_id: str
    cycle_id: str | None = None


@dataclass(frozen=True, slots=True)
class EventExecutionResult:
    """Result of executing a single persisted trading event."""

    realized_pnl_delta: Decimal = Decimal("0")
    realized_pnl_delta_quote: Decimal = Decimal("0")
    entry_binding: EntryExecutionBinding | None = None
