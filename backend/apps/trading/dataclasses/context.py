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

    Attributes:
        user: User instance
        account: OandaAccounts instance (optional, None for backtests)
        instrument: Trading instrument (e.g., "USD_JPY")
        task_id: UUID of the task
        execution_id: UUID of the current execution run
        task_type: Type of task (BACKTEST or TRADING)
    """

    user: "User"
    account: "OandaAccounts | None"
    instrument: str
    task_id: UUID
    execution_id: UUID | None
    task_type: "TaskType"
