from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

import redis
from django.conf import settings
from django.utils import timezone


@dataclass(frozen=True)
class FloorUnrealizedSnapshot:
    open_layers: int
    unrealized_pips: Decimal
    last_mid: Decimal | None


class LivePerformanceService:
    _TRADING_KEY_PREFIX = "trading:live_results:trading:"
    _BACKTEST_KEY_PREFIX = "trading:live_results:backtest:"
    _DEFAULT_TTL_SECONDS = 60 * 60  # 1 hour

    @staticmethod
    def _redis_client() -> redis.Redis:
        return redis.Redis.from_url(settings.MARKET_REDIS_URL, decode_responses=True)

    @classmethod
    def _key_for_trading(cls, task_id: int) -> str:
        return f"{cls._TRADING_KEY_PREFIX}{int(task_id)}"

    @classmethod
    def _key_for_backtest(cls, task_id: int) -> str:
        return f"{cls._BACKTEST_KEY_PREFIX}{int(task_id)}"

    @staticmethod
    def _to_decimal(value: Any) -> Decimal | None:
        if value is None:
            return None
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
            return None

    @staticmethod
    def _pip_size_for_instrument(instrument: str) -> Decimal:
        inst = str(instrument).upper()
        return Decimal("0.01") if "JPY" in inst else Decimal("0.0001")

    @classmethod
    def compute_floor_unrealized_snapshot(
        cls, *, instrument: str, strategy_state: dict[str, Any]
    ) -> FloorUnrealizedSnapshot:
        """Best-effort unrealized snapshot for the floor strategy.

        Uses the persisted JSON strategy_state shape produced by `FloorStrategyService`.
        """

        last_mid = cls._to_decimal(strategy_state.get("last_mid"))
        layers = strategy_state.get("active_layers")
        if not isinstance(layers, list) or last_mid is None:
            return FloorUnrealizedSnapshot(
                open_layers=0,
                unrealized_pips=Decimal("0"),
                last_mid=last_mid,
            )

        pip_size = cls._pip_size_for_instrument(instrument)

        total = Decimal("0")
        weight = Decimal("0")
        for layer in layers:
            if not isinstance(layer, dict):
                continue

            entry_price = cls._to_decimal(layer.get("entry_price"))
            lot_size = cls._to_decimal(layer.get("lot_size"))
            direction = str(layer.get("direction") or "").lower()

            if entry_price is None or lot_size is None or lot_size <= 0:
                continue

            if direction == "long":
                pips = (last_mid - entry_price) / pip_size
            else:
                # short
                pips = (entry_price - last_mid) / pip_size

            total += pips * lot_size
            weight += lot_size

        unrealized = (total / weight) if weight != 0 else Decimal("0")
        return FloorUnrealizedSnapshot(
            open_layers=len(layers),
            unrealized_pips=unrealized,
            last_mid=last_mid,
        )

    @classmethod
    def store_trading_intermediate_results(
        cls, task_id: int, results: dict[str, Any], *, ttl_seconds: int = _DEFAULT_TTL_SECONDS
    ) -> None:
        payload = dict(results)
        payload.setdefault("updated_at", timezone.now().isoformat())
        cls._redis_client().setex(
            cls._key_for_trading(task_id),
            int(ttl_seconds),
            json.dumps(payload),
        )

    @classmethod
    def get_trading_intermediate_results(cls, task_id: int) -> dict[str, Any] | None:
        raw = cls._redis_client().get(cls._key_for_trading(task_id))
        if not raw:
            return None
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) else None

    @classmethod
    def store_backtest_intermediate_results(
        cls, task_id: int, results: dict[str, Any], *, ttl_seconds: int = _DEFAULT_TTL_SECONDS
    ) -> None:
        payload = dict(results)
        payload.setdefault("updated_at", timezone.now().isoformat())
        cls._redis_client().setex(
            cls._key_for_backtest(task_id),
            int(ttl_seconds),
            json.dumps(payload),
        )

    @classmethod
    def get_backtest_intermediate_results(cls, task_id: int) -> dict[str, Any] | None:
        raw = cls._redis_client().get(cls._key_for_backtest(task_id))
        if not raw:
            return None
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) else None


class PerformanceTracker:
    """Tracks performance metrics during task execution.

    The PerformanceTracker is responsible for tracking real-time performance
    metrics as a task executes. It updates metrics after each tick and trade,
    and calculates unrealized PnL.

    Attributes:
        execution: The TaskExecution instance being tracked
        initial_balance: Initial account balance for the execution
        ticks_processed: Number of ticks processed so far
        trades_executed: Number of trades executed so far
        current_balance: Current account balance
        realized_pnl: Realized profit/loss from closed trades
        unrealized_pnl: Unrealized profit/loss from open positions
        open_positions_count: Number of currently open positions

    Requirements: 5.5, 7.1, 7.3, 13.1, 13.2
    """

    def __init__(self, execution: Any, initial_balance: Decimal) -> None:
        """Initialize the PerformanceTracker.

        Args:
            execution: TaskExecution instance to track metrics for
            initial_balance: Initial account balance
        """
        self.execution = execution
        self.initial_balance = initial_balance
        self.ticks_processed = 0
        self.trades_executed = 0
        self.current_balance = initial_balance
        self.realized_pnl = Decimal("0")
        self.unrealized_pnl = Decimal("0")
        self.open_positions_count = 0

        # Track trade history for metrics calculation
        self._trade_pnls: list[Decimal] = []
        self._winning_trades = 0
        self._losing_trades = 0

    def on_tick_processed(self) -> None:
        """Update metrics after processing a tick.

        Increments the tick counter. This should be called after each
        tick is successfully processed by the strategy.

        Requirements: 5.5
        """
        self.ticks_processed += 1

    def on_trade_executed(
        self,
        pnl: Decimal | None = None,
        is_opening: bool = True,
    ) -> None:
        """Update metrics after executing a trade.

        Updates trade counters and PnL tracking. For opening trades,
        increments the open positions count. For closing trades,
        updates realized PnL and trade statistics.

        Args:
            pnl: Profit/loss for closing trades (None for opening trades)
            is_opening: True if opening a position, False if closing

        Requirements: 7.1, 13.1, 13.2
        """
        self.trades_executed += 1

        if is_opening:
            # Opening a new position
            self.open_positions_count += 1
        else:
            # Closing a position
            self.open_positions_count = max(0, self.open_positions_count - 1)

            if pnl is not None:
                # Update realized PnL
                self.realized_pnl += pnl
                self.current_balance = self.initial_balance + self.realized_pnl

                # Track trade statistics
                self._trade_pnls.append(pnl)
                if pnl > 0:
                    self._winning_trades += 1
                elif pnl < 0:
                    self._losing_trades += 1

    def update_unrealized_pnl(self, unrealized_pnl: Decimal) -> None:
        """Update the unrealized PnL from open positions.

        This should be called periodically to update the unrealized PnL
        based on current market prices and open positions.

        Args:
            unrealized_pnl: Current unrealized profit/loss

        Requirements: 7.3, 13.2
        """
        self.unrealized_pnl = unrealized_pnl

    def get_metrics(self) -> dict[str, Any]:
        """Get current metrics as a dictionary.

        Returns a dictionary containing all current performance metrics.
        This is useful for progress updates and real-time monitoring.

        Returns:
            dict: Dictionary containing current metrics

        Requirements: 5.5, 7.3
        """
        total_pnl = self.realized_pnl + self.unrealized_pnl
        total_return = (
            (
                (self.current_balance + self.unrealized_pnl - self.initial_balance)
                / self.initial_balance
            )
            * 100
            if self.initial_balance > 0
            else Decimal("0")
        )

        total_trades = len(self._trade_pnls)
        win_rate = (
            (Decimal(self._winning_trades) / Decimal(total_trades)) * 100
            if total_trades > 0
            else Decimal("0")
        )

        return {
            "ticks_processed": self.ticks_processed,
            "trades_executed": self.trades_executed,
            "current_balance": self.current_balance,
            "current_pnl": total_pnl,
            "realized_pnl": self.realized_pnl,
            "unrealized_pnl": self.unrealized_pnl,
            "open_positions": self.open_positions_count,
            "total_return": total_return,
            "total_trades": total_trades,
            "winning_trades": self._winning_trades,
            "losing_trades": self._losing_trades,
            "win_rate": win_rate,
        }


__all__ = [
    "FloorUnrealizedSnapshot",
    "LivePerformanceService",
    "PerformanceTracker",
]
