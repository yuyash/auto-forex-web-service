"""Market tasks package.

This package contains Celery task runners for market data streaming and persistence.
"""

from typing import List

from apps.market.tasks.backtest import BacktestTickPublisherRunner
from apps.market.tasks.publisher import TickPublisherRunner
from apps.market.tasks.subscriber import TickSubscriberRunner
from apps.market.tasks.supervisor import TickSupervisorRunner

# Create singleton instances
supervisor_runner = TickSupervisorRunner()
publisher_runner = TickPublisherRunner()
subscriber_runner = TickSubscriberRunner()
backtest_publisher_runner = BacktestTickPublisherRunner()

# Export task functions for Celery autodiscovery
ensure_tick_pubsub_running = supervisor_runner.run
publish_oanda_ticks = publisher_runner.run
subscribe_ticks_to_db = subscriber_runner.run
publish_ticks_for_backtest = backtest_publisher_runner.run

__all__: List[str] = [
    # Runner classes
    "BacktestTickPublisherRunner",
    "TickPublisherRunner",
    "TickSubscriberRunner",
    "TickSupervisorRunner",
    # Runner instances
    "backtest_publisher_runner",
    "publisher_runner",
    "subscriber_runner",
    "supervisor_runner",
    # Task functions (for Celery autodiscovery)
    "ensure_tick_pubsub_running",
    "publish_oanda_ticks",
    "publish_ticks_for_backtest",
    "subscribe_ticks_to_db",
]
