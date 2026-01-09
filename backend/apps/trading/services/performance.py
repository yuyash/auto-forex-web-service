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


__all__ = [
    "FloorUnrealizedSnapshot",
    "LivePerformanceService",
]
