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
_MAX_BACKTEST_SPREAD_PIPS = Decimal(
    str(getattr(settings, "TRADING_MAX_BACKTEST_SPREAD_PIPS", "50"))
)


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
    """Legacy Redis Pub/Sub backtest tick data source.

    .. deprecated:: 0.x
        Pub/Sub is fire-and-forget and silently drops messages when the
        subscriber's Redis output buffer overflows (configured by
        ``client-output-buffer-limit pubsub``).  Historically this caused
        entire weeks of ticks to be lost mid-backtest, producing silently
        corrupted backtest results.  New code must use
        :class:`RedisStreamTickDataSource` instead, which reads from a
        persistent Redis Stream.

    Kept around for reference and for legacy callers that still subscribe
    to pub/sub channels (e.g. some test fixtures).
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
        # Initialize Redis connection FIRST before triggering publisher
        self.client = redis.Redis.from_url(settings.MARKET_REDIS_URL, decode_responses=True)
        self.pubsub = self.client.pubsub(ignore_subscribe_messages=True)
        self.pubsub.subscribe(self.channel)
        logger.info(f"RedisTickDataSource subscribed to channel: {self.channel}")

        # CRITICAL: Wait a moment to ensure subscription is fully established
        # This prevents race condition where publisher sends messages before we're ready
        import time

        time.sleep(0.1)

        # Drain any stale messages left on the channel by a previous publisher
        # (e.g. after a task restart while the old publisher was still running).
        # Without this, the new execution would process leftover ticks from a
        # different point in the historical timeline, causing timestamp inversions.
        drained = 0
        while True:
            stale = self.pubsub.get_message(timeout=0.05)
            if stale is None:
                break
            drained += 1
        if drained:
            logger.info(
                "RedisTickDataSource: drained %d stale messages from channel %s",
                drained,
                self.channel,
            )

        # Trigger the publisher AFTER subscription is established
        if self.trigger_publisher:
            logger.info(f"Triggering publisher for channel: {self.channel}")
            # In Celery eager mode, apply_async runs synchronously.  If the
            # publisher finishes before we start reading, all pub/sub messages
            # are lost.  Run the callback in a daemon thread so that the
            # iterator can consume messages as they arrive.
            from celery import current_app

            if getattr(current_app.conf, "task_always_eager", False):
                import threading

                threading.Thread(target=self.trigger_publisher, daemon=True).start()
            else:
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

                    if not self._is_valid_backtest_tick(tick):
                        continue

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

    @staticmethod
    def _is_valid_backtest_tick(tick: Tick) -> bool:
        """Return True when a replay tick has sane executable prices."""
        from apps.trading.utils import pip_size_for_instrument

        if tick.ask < tick.bid:
            logger.warning(
                "RedisTickDataSource: dropping invalid backtest tick with ask < bid "
                "(instrument=%s, timestamp=%s, bid=%s, ask=%s)",
                tick.instrument,
                tick.timestamp,
                tick.bid,
                tick.ask,
            )
            return False

        if tick.mid < tick.bid or tick.mid > tick.ask:
            logger.warning(
                "RedisTickDataSource: dropping invalid backtest tick with mid outside bid/ask "
                "(instrument=%s, timestamp=%s, bid=%s, ask=%s, mid=%s)",
                tick.instrument,
                tick.timestamp,
                tick.bid,
                tick.ask,
                tick.mid,
            )
            return False

        pip_size = pip_size_for_instrument(tick.instrument)
        if pip_size <= 0:
            return True

        spread_pips = (tick.ask - tick.bid) / pip_size
        if spread_pips > _MAX_BACKTEST_SPREAD_PIPS:
            logger.warning(
                "RedisTickDataSource: dropping anomalous backtest tick spread "
                "(instrument=%s, timestamp=%s, bid=%s, ask=%s, spread_pips=%s, max=%s)",
                tick.instrument,
                tick.timestamp,
                tick.bid,
                tick.ask,
                spread_pips,
                _MAX_BACKTEST_SPREAD_PIPS,
            )
            return False

        return True


class RedisStreamTickDataSource(TickDataSource):
    """Reliable backtest tick data source backed by a Redis Stream.

    Uses Redis **consumer groups** (``XREADGROUP`` + ``XACK``) rather than
    plain ``XREAD``.  This gives two important guarantees that the earlier
    pub/sub and naïve-stream versions could not provide:

    * The publisher can measure true consumer lag via ``XPENDING`` and
      apply backpressure based on unacknowledged entries.  Without a
      consumer group the publisher could only see ``XLEN``, which never
      decreases as entries are read, leading to a deadlock.
    * The subscriber distinguishes "no new entries available" from
      "publisher paused while consumer is still catching up" by comparing
      its last-read id with the stream's ``last-generated-id``.  Idle
      timeout only fires when the consumer is truly caught up, so the
      backpressure-pause-idle-timeout cascade can no longer kill a run.

    On reconnect the subscriber re-reads any previously delivered but
    not-yet-ACKed entries via ``XREADGROUP ... 0`` before switching back
    to ``>`` for new entries — so transient Redis disconnects resume
    from exactly the right point.
    """

    def __init__(
        self,
        stream_key: str,
        batch_size: int = 100,
        trigger_publisher: Callable[[], None] | None = None,
        *,
        block_ms: int | None = None,
        read_count: int | None = None,
        idle_timeout_reads: int | None = None,
        consumer_group: str | None = None,
        consumer_name: str | None = None,
    ) -> None:
        """Initialize the stream-backed tick data source.

        Args:
            stream_key: Redis stream key to read from.
            batch_size: Number of ticks to batch before yielding.
            trigger_publisher: Optional callback to trigger the publisher.
            block_ms: How long ``XREADGROUP`` blocks per iteration
                (milliseconds).  Shorter values improve stop-signal
                responsiveness.
            read_count: Maximum number of entries fetched per
                ``XREADGROUP`` call.
            idle_timeout_reads: Abort after this many consecutive empty
                reads **once the consumer is caught up with the
                publisher**.  Empty reads while the publisher is still
                producing (or is paused for backpressure) do not count.
            consumer_group: Name of the consumer group to read from.
                Defaults to ``MARKET_BACKTEST_STREAM_CONSUMER_GROUP``.
            consumer_name: Unique name for this consumer within the
                group.  Multiple consumers are not currently used but
                each run receives a distinct name so ``XPENDING`` can
                attribute work correctly.
        """
        self.stream_key = stream_key
        self.batch_size = batch_size
        self.trigger_publisher = trigger_publisher
        self.block_ms = (
            int(block_ms)
            if block_ms is not None
            else int(getattr(settings, "MARKET_BACKTEST_STREAM_BLOCK_MS", 1000))
        )
        self.read_count = (
            int(read_count)
            if read_count is not None
            else int(getattr(settings, "MARKET_BACKTEST_STREAM_READ_COUNT", 500))
        )
        self.idle_timeout_reads = (
            int(idle_timeout_reads)
            if idle_timeout_reads is not None
            else int(getattr(settings, "MARKET_BACKTEST_STREAM_IDLE_TIMEOUT_READS", 300))
        )
        self.consumer_group = consumer_group or str(
            getattr(settings, "MARKET_BACKTEST_STREAM_CONSUMER_GROUP", "backtest")
        )
        # A unique consumer name per run avoids XPENDING attribution
        # colliding with an earlier aborted run that still has pending
        # entries for the previous consumer.
        import os
        import uuid

        self.consumer_name = consumer_name or f"worker-{os.getpid()}-{uuid.uuid4().hex[:8]}"
        self.client = None
        # Track the last entry id we have received via ``>`` so that
        # XINFO STREAM's ``last-generated-id`` can be compared against
        # it to tell whether the publisher has really stopped or is
        # just between batches.
        self._last_seen_id: str = "0-0"

    def __iter__(self) -> Iterator[list[Tick]]:
        # Connect before triggering the publisher so we never miss entries.
        self.client = redis.Redis.from_url(settings.MARKET_REDIS_URL, decode_responses=True)
        logger.info(
            "RedisStreamTickDataSource opened stream=%s group=%s consumer=%s "
            "block_ms=%s read_count=%s",
            self.stream_key,
            self.consumer_group,
            self.consumer_name,
            self.block_ms,
            self.read_count,
        )

        # Trigger publisher after the client is ready.  The publisher is
        # responsible for creating the consumer group via XGROUP CREATE
        # MKSTREAM, so we don't need to do it ourselves.  In Celery eager
        # mode (used by some tests) ``apply_async`` runs synchronously,
        # so run the trigger in a background thread to avoid deadlocking.
        if self.trigger_publisher:
            logger.info(f"Triggering publisher for stream: {self.stream_key}")
            from celery import current_app

            if getattr(current_app.conf, "task_always_eager", False):
                import threading

                threading.Thread(target=self.trigger_publisher, daemon=True).start()
            else:
                self.trigger_publisher()

        # The publisher creates the consumer group; but if the subscriber
        # is racing ahead (eager-mode tests) or running stand-alone (unit
        # tests), ensure the group exists so the first XREADGROUP does
        # not fail with NOGROUP.
        self._ensure_consumer_group()

        batch: list[Tick] = []
        empty_reads_while_caught_up = 0
        reconnect_count = 0
        max_reconnect_attempts = 5
        total_ticks = 0
        # IDs that we have read from the group but not yet ACKed.  The
        # executor can still reject/drop ticks (invalid payloads etc.)
        # after we've consumed them from the stream; those entries must
        # still be ACKed so ``XPENDING`` reflects accurate progress.
        pending_ack: list = []

        def _flush_acks() -> None:
            """ACK all entries the subscriber has consumed so far."""
            nonlocal pending_ack
            if not pending_ack or self.client is None:
                pending_ack = []
                return
            try:
                self.client.xack(self.stream_key, self.consumer_group, *pending_ack)
            except Exception as exc:  # nosec B110
                logger.debug(
                    "RedisStreamTickDataSource: XACK failed (non-fatal) stream=%s group=%s err=%s",
                    self.stream_key,
                    self.consumer_group,
                    exc,
                )
            pending_ack = []

        try:
            while True:
                try:
                    entries = self.client.xreadgroup(
                        self.consumer_group,
                        self.consumer_name,
                        {self.stream_key: ">"},
                        count=self.read_count,
                        block=self.block_ms,
                    )
                    reconnect_count = 0  # reset on successful call
                except (redis.ConnectionError, ConnectionError) as exc:
                    reconnect_count += 1
                    if reconnect_count > max_reconnect_attempts:
                        raise RuntimeError(
                            "RedisStreamTickDataSource failed to reconnect after "
                            f"{max_reconnect_attempts} attempts"
                        ) from exc
                    import time

                    backoff = min(2 ** (reconnect_count - 1), 5)
                    logger.warning(
                        "RedisStreamTickDataSource reconnecting (%s/%s) after error: %s",
                        reconnect_count,
                        max_reconnect_attempts,
                        exc,
                    )
                    time.sleep(backoff)
                    try:
                        if self.client is not None:
                            self.client.close()
                    except Exception:  # nosec B110
                        pass
                    self.client = redis.Redis.from_url(
                        settings.MARKET_REDIS_URL, decode_responses=True
                    )
                    # Before switching back to "new entries only" (``>``),
                    # drain any entries that were delivered to this
                    # consumer but never ACKed.  ``0`` replays the
                    # consumer's pending-entries list.
                    self._drain_pending_history(batch, pending_ack)
                    continue

                if not entries:
                    # No new entries.  Decide whether this is a genuine
                    # idle (publisher done) or just a pause (publisher is
                    # still producing or is in backpressure).
                    if self._consumer_caught_up_with_publisher():
                        empty_reads_while_caught_up += 1
                        if empty_reads_while_caught_up >= self.idle_timeout_reads:
                            total_idle_ms = empty_reads_while_caught_up * self.block_ms
                            logger.warning(
                                "RedisStreamTickDataSource: idle timeout on stream %s "
                                "after %s ms (caught up with publisher). "
                                "Total messages received: %s",
                                self.stream_key,
                                total_idle_ms,
                                total_ticks,
                            )
                            _flush_acks()
                            if batch:
                                yield batch
                            break
                    else:
                        # Publisher has more entries to come (or is
                        # paused for backpressure).  Reset the idle
                        # counter and keep waiting.
                        empty_reads_while_caught_up = 0

                    # Yield pending batch during idle gaps so the
                    # executor can check stop signals.  ACK what we
                    # already consumed now that the executor is about
                    # to observe them.
                    if batch:
                        _flush_acks()
                        yield batch
                        batch = []
                    continue

                empty_reads_while_caught_up = 0

                # ``xreadgroup`` returns [(stream_key, [(entry_id, {field: value, ...}), ...])].
                should_stop = False
                for _stream, stream_entries in entries:
                    for entry_id, fields in stream_entries:
                        self._last_seen_id = entry_id
                        pending_ack.append(entry_id)
                        kind = str(fields.get("type") or "tick")

                        if kind == "eof":
                            logger.info(
                                "RedisStreamTickDataSource: received EOF on %s, total=%s",
                                self.stream_key,
                                total_ticks,
                            )
                            should_stop = True
                            break

                        if kind in {"stopped", "error"}:
                            logger.info(
                                "RedisStreamTickDataSource: received %s on %s, total=%s",
                                kind,
                                self.stream_key,
                                total_ticks,
                            )
                            should_stop = True
                            break

                        if kind != "tick":
                            continue

                        tick = self._build_tick_from_entry(fields)
                        if tick is None:
                            continue

                        if not self._is_valid_backtest_tick(tick):
                            continue

                        batch.append(tick)
                        total_ticks += 1

                        if len(batch) >= self.batch_size:
                            _flush_acks()
                            yield batch
                            batch = []
                    if should_stop:
                        break

                if should_stop:
                    _flush_acks()
                    if batch:
                        yield batch
                    break

        finally:
            _flush_acks()
            self.close()

    def _ensure_consumer_group(self) -> None:
        """Create the consumer group if it does not already exist.

        Called defensively on the subscriber side so tests and
        race-conditions where the subscriber outruns the publisher still
        work.  ``BUSYGROUP`` is ignored — the publisher may have already
        created it.
        """
        if self.client is None:
            return
        try:
            self.client.xgroup_create(self.stream_key, self.consumer_group, id="$", mkstream=True)
        except Exception as exc:
            if "BUSYGROUP" in str(exc):
                return
            logger.debug(
                "RedisStreamTickDataSource: XGROUP CREATE failed stream=%s group=%s err=%s",
                self.stream_key,
                self.consumer_group,
                exc,
            )

    def _consumer_caught_up_with_publisher(self) -> bool:
        """Return True when this consumer has received every entry the
        publisher has written so far.

        We compare our ``_last_seen_id`` with the stream's
        ``last-generated-id`` reported by ``XINFO STREAM``.  If they
        match, there is nothing left to deliver — a genuine idle state.
        If they differ there are still entries the publisher has added
        that we have not yet read, so we must keep waiting even though
        the last ``XREADGROUP`` returned empty (this happens briefly
        around consumer-group setup and is harmless).
        """
        if self.client is None:
            return True
        try:
            info = self.client.xinfo_stream(self.stream_key)
        except Exception:
            # If we cannot inspect the stream, assume we are caught up
            # to avoid hanging forever.
            return True

        if not isinstance(info, dict):
            return True

        # ``last-generated-id`` is the canonical field on modern Redis
        # servers.  fakeredis (used in tests) does not expose it but
        # does expose ``last-entry`` with the entry id, so fall back.
        last_generated = info.get("last-generated-id")
        if not last_generated:
            last_entry = info.get("last-entry")
            if isinstance(last_entry, (list, tuple)) and last_entry:
                last_generated = last_entry[0]
        if not last_generated:
            # Stream is empty — we are trivially caught up.
            return True
        return self._stream_id_ge(self._last_seen_id, str(last_generated))

    @staticmethod
    def _stream_id_ge(a: str, b: str) -> bool:
        """Return True when stream id ``a`` >= ``b`` (lexicographic on
        ``(ms, seq)`` integer tuple)."""

        def parse(x: str) -> tuple[int, int]:
            if "-" in x:
                ms_str, seq_str = x.split("-", 1)
            else:
                ms_str, seq_str = x, "0"
            try:
                return (int(ms_str), int(seq_str))
            except ValueError:
                return (0, 0)

        return parse(a) >= parse(b)

    def _drain_pending_history(self, batch: list, pending_ack: list) -> None:
        """Replay previously-delivered-but-unACKed entries after reconnect.

        ``XREADGROUP`` with id ``0`` replays the consumer's pending
        entries list so we never lose a delivered tick across a
        connection blip.  Entries read here are already counted in
        ``XPENDING`` from the publisher's viewpoint, so we do not need
        to do anything special for backpressure accounting — ACKing is
        sufficient.
        """
        if self.client is None:
            return
        try:
            replay = self.client.xreadgroup(
                self.consumer_group,
                self.consumer_name,
                {self.stream_key: "0"},
                count=self.read_count,
            )
        except Exception as exc:  # nosec B110
            logger.debug(
                "RedisStreamTickDataSource: replay failed stream=%s err=%s",
                self.stream_key,
                exc,
            )
            return

        if not replay:
            return

        for _stream, stream_entries in replay:
            for entry_id, fields in stream_entries:
                pending_ack.append(entry_id)
                kind = str(fields.get("type") or "tick")
                if kind != "tick":
                    continue
                tick = self._build_tick_from_entry(fields)
                if tick is None or not self._is_valid_backtest_tick(tick):
                    continue
                batch.append(tick)

    def close(self) -> None:
        """Close Redis connection."""
        if self.client is not None:
            try:
                self.client.close()
            except Exception as exc:  # nosec B110
                logger.debug("Failed to close Redis client: %s", exc)
            self.client = None

    @staticmethod
    def _build_tick_from_entry(fields: dict) -> Tick | None:
        """Parse a stream entry payload into a Tick instance."""
        from datetime import UTC, datetime

        instrument = str(fields.get("instrument") or "")
        timestamp_raw = str(fields.get("timestamp") or "")
        if not instrument or not timestamp_raw:
            return None

        try:
            timestamp_str = timestamp_raw.strip()
            if timestamp_str.endswith("Z"):
                timestamp_str = timestamp_str[:-1] + "+00:00"
            timestamp = datetime.fromisoformat(timestamp_str)
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=UTC)
        except (ValueError, AttributeError):
            return None

        bid_raw = fields.get("bid")
        ask_raw = fields.get("ask")
        mid_raw = fields.get("mid")
        if bid_raw is None or ask_raw is None:
            return None

        try:
            bid = Decimal(str(bid_raw))
            ask = Decimal(str(ask_raw))
            if mid_raw is None or str(mid_raw).lower() in {"none", "null", "nan", ""}:
                mid = (bid + ask) / Decimal("2")
            else:
                mid = Decimal(str(mid_raw))
        except (ValueError, InvalidOperation):
            return None

        return Tick(
            instrument=instrument,
            timestamp=timestamp,
            bid=bid,
            ask=ask,
            mid=mid,
        )

    # Reuse the same validation as the pub/sub source.  A class-level
    # attribute lookup keeps the method accessible without duplicating code.
    _is_valid_backtest_tick = staticmethod(RedisTickDataSource._is_valid_backtest_tick)


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
        logger.info("LiveTickDataSource subscribed to channel: %s", self.channel)

        # Give Redis a brief moment to establish the subscription before we
        # start relying on the stream. This mirrors the backtest source and
        # avoids missing the first tick when the publisher resumes immediately.
        import time

        time.sleep(0.1)

        try:
            idle_seconds = 0
            reconnect_attempts = 0
            max_reconnect_attempts = 5
            ticks_received = 0
            while True:
                try:
                    message = self.pubsub.get_message(timeout=1.0)
                    reconnect_attempts = 0
                except (redis.ConnectionError, ConnectionError) as exc:
                    reconnect_attempts += 1
                    if reconnect_attempts > max_reconnect_attempts:
                        raise RuntimeError(
                            f"LiveTickDataSource failed to reconnect after {max_reconnect_attempts} attempts"
                        ) from exc

                    # Exponential backoff capped at 5 seconds.
                    import time

                    backoff = min(2 ** (reconnect_attempts - 1), 5)
                    logger.warning(
                        "LiveTickDataSource reconnecting (%s/%s) after error: %s",
                        reconnect_attempts,
                        max_reconnect_attempts,
                        exc,
                    )
                    time.sleep(backoff)

                    try:
                        self.close()
                    except Exception:  # nosec
                        pass

                    self.client = redis.Redis.from_url(
                        settings.MARKET_REDIS_URL, decode_responses=True
                    )
                    self.pubsub = self.client.pubsub(ignore_subscribe_messages=True)
                    self.pubsub.subscribe(self.channel)
                    continue
                if not message:
                    idle_seconds += 1
                    # Yield empty batch every 5 seconds so the executor can
                    # check stop signals and send heartbeats during market close
                    if idle_seconds >= 5:
                        idle_seconds = 0
                        yield []
                    continue

                idle_seconds = 0
                ticks_received += 1
                if ticks_received == 1:
                    logger.info(
                        "LiveTickDataSource first tick received on channel %s",
                        self.channel,
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
