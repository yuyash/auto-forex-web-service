"""Context-related dataclasses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from apps.accounts.models import User
    from apps.market.models import OandaAccounts
    from apps.trading.enums import TaskType


@dataclass
class EventContext:
    """Context information for event emission.

    This dataclass provides the necessary context for emitting events
    during task execution. It identifies the user, account,
    and instrument involved.

    Attributes:
        user: User instance
        account: OandaAccounts instance (optional, None for backtests)
        instrument: Trading instrument (e.g., "USD_JPY")
        task_id: UUID of the task
        task_type: Type of task (BACKTEST or TRADING)"""

    user: "User"  # Forward reference to avoid circular import
    account: "OandaAccounts | None"  # Forward reference to avoid circular import
    instrument: str
    task_id: UUID
    task_type: "TaskType"  # Forward reference to avoid circular import
