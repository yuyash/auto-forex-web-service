"""Persisted state helpers for SnowballNet."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any


def _decimal_or_none(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _int_or_default(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@dataclass(slots=True)
class SnowballNetState:
    """State persisted inside ExecutionState.strategy_state."""

    version: int = 1
    initialised: bool = False
    direction: str = "long"
    direction_mode: str = "fixed"
    auto_direction_samples: int = 0
    auto_direction_fast_ema: Decimal | None = None
    auto_direction_slow_ema: Decimal | None = None
    auto_direction_slope_pips: Decimal | None = None
    auto_direction_signal: str | None = None
    auto_direction_last_decision: dict[str, Any] = field(default_factory=dict)
    risk_trend_ema: Decimal | None = None
    risk_trend_slope_pips: Decimal | None = None
    volatility_ema_pips: Decimal | None = None
    net_units: int = 0
    average_price: Decimal | None = None
    position_id: str | None = None
    add_count: int = 0
    max_net_units_seen: int = 0
    max_consecutive_add_count: int = 0
    max_margin_ratio_pct: Decimal = Decimal("0")
    max_unrealized_loss: Decimal = Decimal("0")
    current_trend_realized_pnl: Decimal = Decimal("0")
    max_trend_loss: Decimal = Decimal("0")
    next_entry_id: int = 1
    last_bid: Decimal | None = None
    last_ask: Decimal | None = None
    last_mid: Decimal | None = None
    last_tick_timestamp: str | None = None
    last_action: dict[str, Any] = field(default_factory=dict)
    pending_action: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_strategy_state(cls, raw: dict[str, Any] | None) -> "SnowballNetState":
        if not isinstance(raw, dict):
            return cls()
        return cls(
            version=_int_or_default(raw.get("version"), 1),
            initialised=bool(raw.get("initialised", False)),
            direction=str(raw.get("direction") or "long"),
            direction_mode=str(raw.get("direction_mode") or "fixed"),
            auto_direction_samples=max(0, _int_or_default(raw.get("auto_direction_samples"), 0)),
            auto_direction_fast_ema=_decimal_or_none(raw.get("auto_direction_fast_ema")),
            auto_direction_slow_ema=_decimal_or_none(raw.get("auto_direction_slow_ema")),
            auto_direction_slope_pips=_decimal_or_none(raw.get("auto_direction_slope_pips")),
            auto_direction_signal=(
                str(raw["auto_direction_signal"]) if raw.get("auto_direction_signal") else None
            ),
            auto_direction_last_decision=dict(raw.get("auto_direction_last_decision") or {}),
            risk_trend_ema=_decimal_or_none(raw.get("risk_trend_ema")),
            risk_trend_slope_pips=_decimal_or_none(raw.get("risk_trend_slope_pips")),
            volatility_ema_pips=_decimal_or_none(raw.get("volatility_ema_pips")),
            net_units=_int_or_default(raw.get("net_units"), 0),
            average_price=_decimal_or_none(raw.get("average_price")),
            position_id=str(raw["position_id"]) if raw.get("position_id") else None,
            add_count=max(0, _int_or_default(raw.get("add_count"), 0)),
            max_net_units_seen=max(0, _int_or_default(raw.get("max_net_units_seen"), 0)),
            max_consecutive_add_count=max(
                0, _int_or_default(raw.get("max_consecutive_add_count"), 0)
            ),
            max_margin_ratio_pct=_decimal_or_none(raw.get("max_margin_ratio_pct")) or Decimal("0"),
            max_unrealized_loss=_decimal_or_none(raw.get("max_unrealized_loss")) or Decimal("0"),
            current_trend_realized_pnl=_decimal_or_none(raw.get("current_trend_realized_pnl"))
            or Decimal("0"),
            max_trend_loss=_decimal_or_none(raw.get("max_trend_loss")) or Decimal("0"),
            next_entry_id=max(1, _int_or_default(raw.get("next_entry_id"), 1)),
            last_bid=_decimal_or_none(raw.get("last_bid")),
            last_ask=_decimal_or_none(raw.get("last_ask")),
            last_mid=_decimal_or_none(raw.get("last_mid")),
            last_tick_timestamp=(
                str(raw["last_tick_timestamp"]) if raw.get("last_tick_timestamp") else None
            ),
            last_action=dict(raw.get("last_action") or {}),
            pending_action=dict(raw.get("pending_action") or {}),
            metrics=dict(raw.get("metrics") or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "version": self.version,
            "initialised": self.initialised,
            "direction": self.direction,
            "direction_mode": self.direction_mode,
            "auto_direction_samples": self.auto_direction_samples,
            "auto_direction_fast_ema": (
                str(self.auto_direction_fast_ema)
                if self.auto_direction_fast_ema is not None
                else None
            ),
            "auto_direction_slow_ema": (
                str(self.auto_direction_slow_ema)
                if self.auto_direction_slow_ema is not None
                else None
            ),
            "auto_direction_slope_pips": (
                str(self.auto_direction_slope_pips)
                if self.auto_direction_slope_pips is not None
                else None
            ),
            "auto_direction_signal": self.auto_direction_signal,
            "auto_direction_last_decision": dict(self.auto_direction_last_decision),
            "risk_trend_ema": (
                str(self.risk_trend_ema) if self.risk_trend_ema is not None else None
            ),
            "risk_trend_slope_pips": (
                str(self.risk_trend_slope_pips) if self.risk_trend_slope_pips is not None else None
            ),
            "volatility_ema_pips": (
                str(self.volatility_ema_pips) if self.volatility_ema_pips is not None else None
            ),
            "net_units": self.net_units,
            "average_price": str(self.average_price) if self.average_price is not None else None,
            "position_id": self.position_id,
            "add_count": self.add_count,
            "max_net_units_seen": self.max_net_units_seen,
            "max_consecutive_add_count": self.max_consecutive_add_count,
            "max_margin_ratio_pct": str(self.max_margin_ratio_pct),
            "max_unrealized_loss": str(self.max_unrealized_loss),
            "current_trend_realized_pnl": str(self.current_trend_realized_pnl),
            "max_trend_loss": str(self.max_trend_loss),
            "next_entry_id": self.next_entry_id,
            "last_bid": str(self.last_bid) if self.last_bid is not None else None,
            "last_ask": str(self.last_ask) if self.last_ask is not None else None,
            "last_mid": str(self.last_mid) if self.last_mid is not None else None,
            "last_tick_timestamp": self.last_tick_timestamp,
            "last_action": dict(self.last_action),
            "pending_action": dict(self.pending_action),
            "metrics": dict(self.metrics),
        }
        return result

    def allocate_entry_id(self) -> int:
        entry_id = self.next_entry_id
        self.next_entry_id += 1
        return entry_id

    @property
    def has_pending_action(self) -> bool:
        return bool(self.pending_action)

    def clear_pending_action(self) -> None:
        self.pending_action = {}
