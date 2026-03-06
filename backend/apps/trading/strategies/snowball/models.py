"""Data models for Snowball strategy."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from apps.trading.strategies.snowball.enums import ProtectionLevel

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_decimal(value: Any, default: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)


def _to_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_str(value: Any, default: str) -> str:
    return str(value).strip().lower() if value is not None else default


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SnowballStrategyConfig:
    """Normalised Snowball strategy configuration.

    All pip values are stored as Decimal for precision.
    """

    # Core
    base_units: int
    m_pips: Decimal
    trend_lot_size: int
    r_max: int
    f_max: int
    post_r_max_base_factor: Decimal

    # Counter-trend interval formula
    n_pips_head: Decimal
    n_pips_tail: Decimal
    n_pips_flat_steps: int
    n_pips_gamma: Decimal
    interval_mode: str  # constant / additive / subtractive / multiplicative / divisive / manual
    manual_intervals: list[Decimal]

    # Counter-trend step TP
    counter_tp_mode: (
        str  # fixed / additive / subtractive / multiplicative / divisive / weighted_avg
    )
    counter_tp_pips: Decimal
    counter_tp_step_amount: Decimal
    counter_tp_multiplier: Decimal
    round_step_pips: Decimal

    # Dynamic TP (ATR)
    dynamic_tp_enabled: bool
    atr_period: int
    atr_timeframe: str
    atr_baseline_lookback: int
    m_pips_min: Decimal
    m_pips_max: Decimal

    # Margin protection
    margin_protection_enabled: bool
    m_th: Decimal
    n_th: Decimal
    spread_guard_pips: Decimal
    cooldown_sec: int
    rebalance_start_ratio: Decimal
    rebalance_end_ratio: Decimal

    pip_size: Decimal

    @staticmethod
    def from_dict(raw: dict[str, Any]) -> "SnowballStrategyConfig":
        """Create config from a parameters dictionary."""
        manual_raw = raw.get("manual_intervals", [])
        manual_intervals: list[Decimal] = []
        if isinstance(manual_raw, list):
            for v in manual_raw:
                manual_intervals.append(_to_decimal(v, "30"))

        return SnowballStrategyConfig(
            base_units=_to_int(raw.get("base_units", 1000), 1000),
            m_pips=_to_decimal(raw.get("m_pips", "50"), "50"),
            trend_lot_size=_to_int(raw.get("trend_lot_size", 1), 1),
            r_max=_to_int(raw.get("r_max", 7), 7),
            f_max=_to_int(raw.get("f_max", 3), 3),
            post_r_max_base_factor=_to_decimal(raw.get("post_r_max_base_factor", "1"), "1"),
            n_pips_head=_to_decimal(raw.get("n_pips_head", "30"), "30"),
            n_pips_tail=_to_decimal(raw.get("n_pips_tail", "14"), "14"),
            n_pips_flat_steps=_to_int(raw.get("n_pips_flat_steps", 2), 2),
            n_pips_gamma=_to_decimal(raw.get("n_pips_gamma", "1.4"), "1.4"),
            interval_mode=_to_str(raw.get("interval_mode"), "constant"),
            manual_intervals=manual_intervals,
            counter_tp_mode=_to_str(raw.get("counter_tp_mode"), "fixed"),
            counter_tp_pips=_to_decimal(raw.get("counter_tp_pips", "25"), "25"),
            counter_tp_step_amount=_to_decimal(raw.get("counter_tp_step_amount", "2.5"), "2.5"),
            counter_tp_multiplier=_to_decimal(raw.get("counter_tp_multiplier", "1.2"), "1.2"),
            round_step_pips=_to_decimal(raw.get("round_step_pips", "0.1"), "0.1"),
            dynamic_tp_enabled=bool(raw.get("dynamic_tp_enabled", False)),
            atr_period=_to_int(raw.get("atr_period", 14), 14),
            atr_timeframe=_to_str(raw.get("atr_timeframe"), "m1"),
            atr_baseline_lookback=_to_int(raw.get("atr_baseline_lookback", 96), 96),
            m_pips_min=_to_decimal(raw.get("m_pips_min", "12"), "12"),
            m_pips_max=_to_decimal(raw.get("m_pips_max", "45"), "45"),
            margin_protection_enabled=bool(raw.get("margin_protection_enabled", True)),
            m_th=_to_decimal(raw.get("m_th", "70"), "70"),
            n_th=_to_decimal(raw.get("n_th", "85"), "85"),
            spread_guard_pips=_to_decimal(raw.get("spread_guard_pips", "2.5"), "2.5"),
            cooldown_sec=_to_int(raw.get("cooldown_sec", 300), 300),
            rebalance_start_ratio=_to_decimal(raw.get("rebalance_start_ratio", "60"), "60"),
            rebalance_end_ratio=_to_decimal(raw.get("rebalance_end_ratio", "50"), "50"),
            pip_size=_to_decimal(raw.get("pip_size", "0.01"), "0.01"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialise to JSON-friendly dict."""
        return {
            "base_units": self.base_units,
            "m_pips": str(self.m_pips),
            "trend_lot_size": self.trend_lot_size,
            "r_max": self.r_max,
            "f_max": self.f_max,
            "post_r_max_base_factor": str(self.post_r_max_base_factor),
            "n_pips_head": str(self.n_pips_head),
            "n_pips_tail": str(self.n_pips_tail),
            "n_pips_flat_steps": self.n_pips_flat_steps,
            "n_pips_gamma": str(self.n_pips_gamma),
            "interval_mode": self.interval_mode,
            "manual_intervals": [str(v) for v in self.manual_intervals],
            "counter_tp_mode": self.counter_tp_mode,
            "counter_tp_pips": str(self.counter_tp_pips),
            "counter_tp_step_amount": str(self.counter_tp_step_amount),
            "counter_tp_multiplier": str(self.counter_tp_multiplier),
            "round_step_pips": str(self.round_step_pips),
            "dynamic_tp_enabled": self.dynamic_tp_enabled,
            "atr_period": self.atr_period,
            "atr_timeframe": self.atr_timeframe,
            "atr_baseline_lookback": self.atr_baseline_lookback,
            "m_pips_min": str(self.m_pips_min),
            "m_pips_max": str(self.m_pips_max),
            "margin_protection_enabled": self.margin_protection_enabled,
            "m_th": str(self.m_th),
            "n_th": str(self.n_th),
            "spread_guard_pips": str(self.spread_guard_pips),
            "cooldown_sec": self.cooldown_sec,
            "rebalance_start_ratio": str(self.rebalance_start_ratio),
            "rebalance_end_ratio": str(self.rebalance_end_ratio),
            "pip_size": str(self.pip_size),
        }

    def validate(self) -> None:
        """Raise ``ValueError`` on invalid parameter combinations."""
        if not self.m_th < self.n_th < Decimal("100"):
            raise ValueError("Must satisfy m_th < n_th < 100")
        if not self.m_pips_min <= self.m_pips <= self.m_pips_max:
            raise ValueError("Must satisfy m_pips_min <= m_pips <= m_pips_max")
        if not self.n_pips_head >= self.n_pips_tail > 0:
            raise ValueError("Must satisfy n_pips_head >= n_pips_tail > 0")
        if not self.n_pips_flat_steps < self.r_max:
            raise ValueError("n_pips_flat_steps must be < r_max")
        if self.counter_tp_mode != "weighted_avg" and self.counter_tp_pips <= 0:
            raise ValueError("counter_tp_pips must be > 0")
        if not self.rebalance_start_ratio > self.rebalance_end_ratio > 0:
            raise ValueError("rebalance_start_ratio > rebalance_end_ratio > 0")


# ---------------------------------------------------------------------------
# Basket entry
# ---------------------------------------------------------------------------


@dataclass
class BasketEntry:
    """A single position within a basket."""

    entry_id: int
    step: int  # 1-based step within the current cycle
    direction: str  # "long" or "short"
    entry_price: Decimal
    close_price: Decimal  # target close price
    units: int
    opened_at: str  # ISO timestamp
    position_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "step": self.step,
            "direction": self.direction,
            "entry_price": str(self.entry_price),
            "close_price": str(self.close_price),
            "units": self.units,
            "opened_at": self.opened_at,
            "position_id": self.position_id,
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "BasketEntry":
        return BasketEntry(
            entry_id=_to_int(d.get("entry_id", 0), 0),
            step=_to_int(d.get("step", 1), 1),
            direction=_to_str(d.get("direction"), "long"),
            entry_price=_to_decimal(d.get("entry_price", "0"), "0"),
            close_price=_to_decimal(d.get("close_price", "0"), "0"),
            units=_to_int(d.get("units", 0), 0),
            opened_at=str(d.get("opened_at", "")),
            position_id=d.get("position_id"),
        )


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


@dataclass
class SnowballStrategyState:
    """Mutable runtime state for Snowball strategy."""

    protection_level: ProtectionLevel = ProtectionLevel.NORMAL
    initialised: bool = False

    # Basket tracking
    trend_basket: list[dict[str, Any]] = field(default_factory=list)
    counter_basket: list[dict[str, Any]] = field(default_factory=list)

    # Counter-trend cycle tracking
    add_count: int = 0  # current adds within this cycle (max r_max - 1)
    freeze_count: int = 0  # how many times r_max has been reached
    cycle_base_units: int = 1000  # base units for current cycle

    # Next entry id
    next_entry_id: int = 1

    # Lock state
    lock_hedge_ids: list[int] = field(default_factory=list)
    lock_entered_at: str | None = None  # ISO timestamp when lock started
    cooldown_until: str | None = None  # ISO timestamp when cooldown expires

    # Price tracking
    last_bid: Decimal | None = None
    last_ask: Decimal | None = None
    last_mid: Decimal | None = None
    account_balance: Decimal = Decimal("0")
    account_nav: Decimal = Decimal("0")

    # Metrics
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "protection_level": self.protection_level.value,
            "initialised": self.initialised,
            "trend_basket": list(self.trend_basket),
            "counter_basket": list(self.counter_basket),
            "add_count": self.add_count,
            "freeze_count": self.freeze_count,
            "cycle_base_units": self.cycle_base_units,
            "next_entry_id": self.next_entry_id,
            "lock_hedge_ids": list(self.lock_hedge_ids),
            "lock_entered_at": self.lock_entered_at,
            "cooldown_until": self.cooldown_until,
            "last_bid": str(self.last_bid) if self.last_bid is not None else None,
            "last_ask": str(self.last_ask) if self.last_ask is not None else None,
            "last_mid": str(self.last_mid) if self.last_mid is not None else None,
            "account_balance": str(self.account_balance),
            "account_nav": str(self.account_nav),
            "metrics": dict(self.metrics),
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "SnowballStrategyState":
        def _dec_or_none(v: Any) -> Decimal | None:
            return _to_decimal(v, "0") if v is not None else None

        return SnowballStrategyState(
            protection_level=ProtectionLevel(
                data.get("protection_level", ProtectionLevel.NORMAL.value)
            ),
            initialised=bool(data.get("initialised", False)),
            trend_basket=list(data.get("trend_basket", [])),
            counter_basket=list(data.get("counter_basket", [])),
            add_count=_to_int(data.get("add_count", 0), 0),
            freeze_count=_to_int(data.get("freeze_count", 0), 0),
            cycle_base_units=_to_int(data.get("cycle_base_units", 1000), 1000),
            next_entry_id=max(1, _to_int(data.get("next_entry_id", 1), 1)),
            lock_hedge_ids=[_to_int(i, 0) for i in (data.get("lock_hedge_ids") or [])],
            lock_entered_at=data.get("lock_entered_at"),
            cooldown_until=data.get("cooldown_until"),
            last_bid=_dec_or_none(data.get("last_bid")),
            last_ask=_dec_or_none(data.get("last_ask")),
            last_mid=_dec_or_none(data.get("last_mid")),
            account_balance=_to_decimal(data.get("account_balance", "0"), "0"),
            account_nav=_to_decimal(data.get("account_nav", "0"), "0"),
            metrics=dict(data.get("metrics", {})) if isinstance(data.get("metrics"), dict) else {},
        )

    @classmethod
    def from_strategy_state(cls, raw: Any) -> "SnowballStrategyState":
        if not isinstance(raw, dict):
            return cls()
        return cls.from_dict(raw)
