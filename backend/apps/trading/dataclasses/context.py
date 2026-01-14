"""Context-related dataclasses."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from .trade import OpenPosition

if TYPE_CHECKING:
    from apps.accounts.models import User
    from apps.market.models import OandaAccount
    from apps.trading.models import TaskExecution


@dataclass
class EventContext:
    """Context information for event emission.

    This dataclass provides the necessary context for emitting events
    during task execution. It identifies the execution, user, account,
    and instrument involved.

    Attributes:
        execution: TaskExecution instance
        user: User instance
        account: OandaAccount instance (optional, None for backtests)
        instrument: Trading instrument (e.g., "USD_JPY")

    Requirements: 1.1, 1.2, 1.3
    """

    execution: "TaskExecution"  # Forward reference to avoid circular import
    user: "User"  # Forward reference to avoid circular import
    account: "OandaAccount | None"  # Forward reference to avoid circular import
    instrument: str


@dataclass
class StrategyContext:
    """Context provided to strategy methods.

    This dataclass provides the necessary context for strategy methods
    to make trading decisions. It includes current account state and
    instrument information.

    Attributes:
        current_balance: Current account balance
        open_positions: List of open positions
        instrument: Trading instrument (e.g., "USD_JPY")
        pip_size: Pip size for the instrument

    Requirements: 3.5
    """

    current_balance: Decimal
    open_positions: list[OpenPosition]
    instrument: str
    pip_size: Decimal
