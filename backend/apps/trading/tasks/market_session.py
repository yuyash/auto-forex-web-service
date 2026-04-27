"""Compatibility helpers for task-level market session checks."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.trading.services.market_schedule import MarketSessionConfig


def is_forex_market_closed(
    now: datetime | None = None,
    *,
    config: MarketSessionConfig | None = None,
) -> bool:
    """Check whether the forex market is closed for task execution.

    Delegates to :mod:`apps.trading.services.market_schedule`, keeping the
    schedule rule in one module while preserving the historical task-level API.
    """

    from apps.trading.services.market_schedule import is_forex_market_closed as _impl

    return _impl(now, config=config)
