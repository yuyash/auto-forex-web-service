"""apps.trading.services.data_source

Data source interfaces and implementations for tick data.

This module provides abstractions for tick data sources used by executors,
allowing different implementations (Redis, database, file, etc.) while
maintaining a consistent interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal, InvalidOperation
from typing import Callable, Iterator

from apps.trading.dataclasses import Tick


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

    Attributes:
        channel: Redis channel name
        batch_size: Number of ticks to batch before yielding
        trigger_publisher: Optional callback to trigger tick publisher
        client: Redis client instance
        pubsub: Redis pub/sub instance
    Example:
        >>> data_source = RedisTickDataSource(
        ...     channel="market:backtest:ticks:12345",
        ...     batch_size=100
        ... )
        >>> for tick_batch in data_source:
        ...     for tick in tick_batch:
        ...         print(f"Tick: {tick.instrument} @ {tick.timestamp}")
        >>> data_source.close()
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
        import json
        import logging

        import redis
        from django.conf import settings

        logger = logging.getLogger(__name__)

        # Initialize Redis connection
        self.client = redis.Redis.from_url(settings.MARKET_REDIS_URL, decode_responses=True)
        self.pubsub = self.client.pubsub(ignore_subscribe_messages=True)
        self.pubsub.subscribe(self.channel)
        logger.info(f"RedisTickDataSource subscribed to channel: {self.channel}")

        # Trigger the publisher if callback provided
        if self.trigger_publisher:
            logger.info(f"Triggering publisher for channel: {self.channel}")
            self.trigger_publisher()

        batch: list[Tick] = []
        max_reconnect_attempts = 3
        reconnect_count = 0
        messages_received = 0

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
                    except Exception:  # pylint: disable=broad-exception-caught
                        pass

                    self.client = redis.Redis.from_url(
                        settings.MARKET_REDIS_URL, decode_responses=True
                    )
                    self.pubsub = self.client.pubsub(ignore_subscribe_messages=True)
                    self.pubsub.subscribe(self.channel)
                    continue

                if not message:
                    # Yield any pending batch on timeout
                    if batch:
                        yield batch
                        batch = []
                    continue

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
                except Exception:  # pylint: disable=broad-exception-caught
                    continue

                kind = str(payload.get("type") or "tick")

                # Handle EOF - end of data stream
                if kind == "eof":
                    # Yield any remaining ticks
                    if batch:
                        yield batch
                    break

                # Handle terminal messages
                if kind in {"stopped", "error"}:
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
        if self.pubsub:
            try:
                self.pubsub.close()
            except Exception:  # pylint: disable=broad-exception-caught
                pass
        if self.client:
            try:
                self.client.close()
            except Exception:  # pylint: disable=broad-exception-caught
                pass


class LiveTickDataSource(TickDataSource):
    """Live tick data source for real-time trading.

    This data source subscribes to a Redis pub/sub channel for real-time
    market data and yields individual ticks as they arrive. It's used for
    live trading where ticks are streamed in real-time.

    Attributes:
        channel: Redis channel name
        instrument: Trading instrument to filter for
        client: Redis client instance
        pubsub: Redis pub/sub instance
    Example:
        >>> data_source = LiveTickDataSource(
        ...     channel="market:ticks",
        ...     instrument="USD_JPY"
        ... )
        >>> for tick_batch in data_source:
        ...     for tick in tick_batch:
        ...         print(f"Live tick: {tick.instrument} @ {tick.mid}")
        >>> data_source.close()
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
                except Exception:  # pylint: disable=broad-exception-caught
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
        if self.pubsub:
            try:
                self.pubsub.close()
            except Exception:  # pylint: disable=broad-exception-caught
                pass
        if self.client:
            try:
                self.client.close()
            except Exception:  # pylint: disable=broad-exception-caught
                pass
