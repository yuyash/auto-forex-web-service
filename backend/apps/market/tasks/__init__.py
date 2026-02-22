"""Market tasks package.

This package contains Celery task runners for market data streaming and persistence.
"""

from typing import List

from apps.market.tasks.backtest import (
    BacktestTickPublisherRunner,
    publish_ticks_for_backtest,
)
from apps.market.tasks.publisher import TickPublisherRunner, publish_oanda_ticks
from apps.market.tasks.subscriber import TickSubscriberRunner, subscribe_ticks_to_db
from apps.market.tasks.supervisor import TickSupervisorRunner, ensure_tick_pubsub_running

# Create singleton instances for runners that need them
supervisor_runner = TickSupervisorRunner()
publisher_runner = TickPublisherRunner()
subscriber_runner = TickSubscriberRunner()

__all__: List[str] = [
    # Runner classes
    "BacktestTickPublisherRunner",
    "TickPublisherRunner",
    "TickSubscriberRunner",
    "TickSupervisorRunner",
    # Runner instances
    "publisher_runner",
    "subscriber_runner",
    "supervisor_runner",
    # Task functions (for Celery autodiscovery)
    "ensure_tick_pubsub_running",
    "publish_oanda_ticks",
    "publish_ticks_for_backtest",
    "subscribe_ticks_to_db",
]
