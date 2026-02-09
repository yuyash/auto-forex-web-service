"""apps.trading.services.data_source

Data source interfaces and implementations for tick data.

This module provides abstractions for tick data sources used by executors,
allowing different implementations (Redis, database, file, etc.) while
maintaining a consistent interface.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from decimal import Decimal, InvalidOperation
from logging import Logger, getLogger
from typing import Callable, Iterator

import redis
from django.conf import settings

from apps.trading.dataclasses import Tick

logger: Logger = getLogger(name=__name__)


class TickDataSource(ABC):
    """Abstract base class for tick data sources.

    A TickDataSource provides an iterator over batches of ticks for
    backtest or live trading execution. Different implementations can
    provide ticks from various sources (Redis pub/sub, database queries,
    file streams, etc.)."""

    @abstractmethod
    def __iter__(self) -> Iterator[list[Tick]]:
        """Return an iterator that yields batches of ticks.

        Yields:
            Batches of Tick objects"""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close the data source and release resources.

        This method should be called when the data source is no longer needed
        to properly clean up connections, file handles, etc.
        """
        pass


class RedisTickDataSource(TickDataSource):
    """Redis-based tick data source for backtests.

    This data source subscribes to a Redis pub/sub channel and yields
    batches of ticks published by the market service. It's used for
    backtests where historical ticks are published to a dedicated channel.
    """

    def __init__(
        self,
        channel: str,
        batch_size: int = 100,
        trigger_publisher: Callable[[], None] | None = None,
    ) -> None:
        """Initialize the Redis tick data source.

        Args:
            channel: Redis channel name to subscribe to
            batch_size: Number of ticks to batch before yielding (default: 100)
            trigger_publisher: Optional callback to trigger the tick publisher
        """
        self.channel = channel
        self.batch_size = batch_size
        self.trigger_publisher = trigger_publisher
        self.client = None
        self.pubsub = None

    def __iter__(self) -> Iterator[list[Tick]]:
        """Iterate over batches of ticks from Redis.

        Yields:
            Batches of Tick objects"""
        # Initialize Redis connection FIRST before triggering publisher
        self.client = redis.Redis.from_url(settings.MARKET_REDIS_URL, decode_responses=True)
        self.pubsub = self.client.pubsub(ignore_subscribe_messages=True)
        self.pubsub.subscribe(self.channel)
        logger.info(f"RedisTickDataSource subscribed to channel: {self.channel}")

        # CRITICAL: Wait a moment to ensure subscription is fully established
        # This prevents race condition where publisher sends messages before we're ready
        import time

        time.sleep(0.1)

        # Trigger the publisher AFTER subscription is established
        if self.trigger_publisher:
            logger.info(f"Triggering publisher for channel: {self.channel}")
            self.trigger_publisher()

        batch: list[Tick] = []
        max_reconnect_attempts = 3
        reconnect_count = 0
        messages_received = 0

        # Timeout mechanism to prevent infinite waiting
        consecutive_timeouts = 0
        max_consecutive_timeouts = 300  # 5 minutes of consecutive timeouts (300 * 1 second)

        try:
            while True:
                try:
                    message = self.pubsub.get_message(timeout=1.0)
                    reconnect_count = 0  # Reset on successful message
                except (redis.ConnectionError, ConnectionError) as e:
                    reconnect_count += 1
                    if reconnect_count > max_reconnect_attempts:
                        raise RuntimeError(
                            f"Failed to reconnect to Redis after {max_reconnect_attempts} attempts"
                        ) from e

                    # Reconnect on connection error
                    try:
                        self.pubsub.close()
                    except Exception as exc:  # pylint: disable=broad-exception-caught  # nosec B110
                        import logging

                        logger_local = logging.getLogger(__name__)
                        logger_local.debug("Failed to close pubsub on reconnect: %s", exc)

                    self.client = redis.Redis.from_url(
                        settings.MARKET_REDIS_URL, decode_responses=True
                    )
                    self.pubsub = self.client.pubsub(ignore_subscribe_messages=True)
                    self.pubsub.subscribe(self.channel)
                    continue

                if not message:
                    consecutive_timeouts += 1

                    # Check if we've been waiting too long without messages
                    if consecutive_timeouts >= max_consecutive_timeouts:
                        logger.warning(
                            f"RedisTickDataSource: No messages received for {max_consecutive_timeouts} seconds "
                            f"on channel {self.channel}. Assuming stream ended. "
                            f"Total messages received: {messages_received}"
                        )
                        # Yield any pending batch before exiting
                        if batch:
                            yield batch
                        break

                    # Yield any pending batch on timeout
                    if batch:
                        yield batch
                        batch = []
                    continue

                # Reset timeout counter when we receive a message
                consecutive_timeouts = 0

                messages_received += 1
                if messages_received % 10000 == 0:
                    logger.info(
                        f"RedisTickDataSource received {messages_received} messages from {self.channel}"
                    )

                if message.get("type") != "message":
                    continue

                payload_raw = message.get("data")
                try:
                    payload = json.loads(payload_raw) if isinstance(payload_raw, str) else {}
                except Exception as exc:  # pylint: disable=broad-exception-caught  # nosec B112
                    # Log parsing error but continue with next message
                    import logging

                    logger_local = logging.getLogger(__name__)
                    logger_local.warning("Failed to parse tick message: %s", exc)
                    continue

                kind = str(payload.get("type") or "tick")

                # Handle EOF - end of data stream
                if kind == "eof":
                    logger.info(
                        f"RedisTickDataSource: Received EOF on channel {self.channel}. "
                        f"Total messages received: {messages_received}"
                    )
                    # Yield any remaining ticks
                    if batch:
                        yield batch
                    break

                # Handle terminal messages
                if kind in {"stopped", "error"}:
                    logger.info(
                        f"RedisTickDataSource: Received {kind} signal on channel {self.channel}. "
                        f"Total messages received: {messages_received}"
                    )
                    if batch:
                        yield batch
                    break

                # Process tick
                if kind == "tick":
                    # Parse required fields
                    instrument = str(payload.get("instrument") or "")
                    timestamp_raw = str(payload.get("timestamp") or "")

                    if not instrument or not timestamp_raw:
                        continue  # Skip invalid ticks

                    # Parse timestamp
                    try:
                        from datetime import UTC, datetime

                        timestamp_str = timestamp_raw.strip()
                        if timestamp_str.endswith("Z"):
                            timestamp_str = timestamp_str[:-1] + "+00:00"
                        timestamp = datetime.fromisoformat(timestamp_str)
                        if timestamp.tzinfo is None:
                            timestamp = timestamp.replace(tzinfo=UTC)
                    except (ValueError, AttributeError):
                        continue  # Skip ticks with invalid timestamp

                    # Parse prices as Decimal
                    try:
                        bid_raw = payload.get("bid")
                        ask_raw = payload.get("ask")
                        mid_raw = payload.get("mid")

                        if bid_raw is None or ask_raw is None:
                            continue  # Skip ticks without bid/ask

                        bid = Decimal(str(bid_raw))
                        ask = Decimal(str(ask_raw))

                        # Calculate mid if missing
                        if mid_raw is None or str(mid_raw).lower() in {"none", "null", "nan", ""}:
                            mid = (bid + ask) / Decimal("2")
                        else:
                            mid = Decimal(str(mid_raw))

                        tick = Tick(
                            instrument=instrument,
                            timestamp=timestamp,
                            bid=bid,
                            ask=ask,
                            mid=mid,
                        )
                    except (ValueError, InvalidOperation):
                        continue  # Skip ticks with invalid prices

                    batch.append(tick)

                    # Yield batch when it reaches the target size
                    if len(batch) >= self.batch_size:
                        yield batch
                        batch = []

        finally:
            self.close()

    def close(self) -> None:
        """Close Redis connections."""
        import logging

        logger_local = logging.getLogger(__name__)

        if self.pubsub:
            try:
                self.pubsub.close()
            except Exception as exc:  # pylint: disable=broad-exception-caught  # nosec B110
                logger_local.debug("Failed to close pubsub: %s", exc)
        if self.client:
            try:
                self.client.close()
            except Exception as exc:  # pylint: disable=broad-exception-caught  # nosec B110
                logger_local.debug("Failed to close Redis client: %s", exc)


class LiveTickDataSource(TickDataSource):
    """Live tick data source for real-time trading.

    This data source subscribes to a Redis pub/sub channel for real-time
    market data and yields individual ticks as they arrive. It's used for
    live trading where ticks are streamed in real-time.
    """

    def __init__(self, channel: str, instrument: str) -> None:
        """Initialize the live tick data source.

        Args:
            channel: Redis channel name to subscribe to
            instrument: Trading instrument to filter for
        """
        self.channel = channel
        self.instrument = instrument
        self.client = None
        self.pubsub = None

    def __iter__(self) -> Iterator[list[Tick]]:
        """Iterate over ticks from real-time market data.

        Yields:
            Single-item batches containing one Tick object each"""
        import json

        import redis
        from django.conf import settings

        # Initialize Redis connection
        self.client = redis.Redis.from_url(settings.MARKET_REDIS_URL, decode_responses=True)
        self.pubsub = self.client.pubsub(ignore_subscribe_messages=True)
        self.pubsub.subscribe(self.channel)

        try:
            while True:
                message = self.pubsub.get_message(timeout=1.0)
                if not message:
                    continue

                if message.get("type") != "message":
                    continue

                payload_raw = message.get("data")
                try:
                    payload = json.loads(payload_raw) if isinstance(payload_raw, str) else {}
                except Exception as exc:  # pylint: disable=broad-exception-caught  # nosec B112
                    # Log parsing error but continue with next message
                    import logging

                    logger_local = logging.getLogger(__name__)
                    logger_local.warning("Failed to parse tick message: %s", exc)
                    continue

                # Parse tick data
                instrument = str(payload.get("instrument") or "")
                timestamp_raw = str(payload.get("timestamp") or "")

                if not instrument or not timestamp_raw:
                    continue  # Skip invalid ticks

                # Parse timestamp
                try:
                    from datetime import UTC, datetime

                    timestamp_str = timestamp_raw.strip()
                    if timestamp_str.endswith("Z"):
                        timestamp_str = timestamp_str[:-1] + "+00:00"
                    timestamp = datetime.fromisoformat(timestamp_str)
                    if timestamp.tzinfo is None:
                        timestamp = timestamp.replace(tzinfo=UTC)
                except (ValueError, AttributeError):
                    continue  # Skip ticks with invalid timestamp

                # Parse prices as Decimal
                try:
                    bid_raw = payload.get("bid")
                    ask_raw = payload.get("ask")
                    mid_raw = payload.get("mid")

                    if bid_raw is None or ask_raw is None:
                        continue  # Skip ticks without bid/ask

                    bid = Decimal(str(bid_raw))
                    ask = Decimal(str(ask_raw))

                    # Calculate mid if missing
                    if mid_raw is None or str(mid_raw).lower() in {"none", "null", "nan", ""}:
                        mid = (bid + ask) / Decimal("2")
                    else:
                        mid = Decimal(str(mid_raw))

                    tick = Tick(
                        instrument=instrument,
                        timestamp=timestamp,
                        bid=bid,
                        ask=ask,
                        mid=mid,
                    )
                except (ValueError, InvalidOperation):
                    continue  # Skip ticks with invalid prices

                # Yield single tick as a batch
                yield [tick]

        finally:
            self.close()

    def close(self) -> None:
        """Close Redis connections."""
        import logging

        logger_local = logging.getLogger(__name__)

        if self.pubsub:
            try:
                self.pubsub.close()
            except Exception as exc:  # pylint: disable=broad-exception-caught  # nosec B110
                logger_local.debug("Failed to close pubsub: %s", exc)
        if self.client:
            try:
                self.client.close()
            except Exception as exc:  # pylint: disable=broad-exception-caught  # nosec B110
                logger_local.debug("Failed to close Redis client: %s", exc)
