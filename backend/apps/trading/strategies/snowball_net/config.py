"""Configuration model for the SnowballNet strategy."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any


INTERVAL_MODES = {
    "constant",
    "additive",
    "subtractive",
    "multiplicative",
    "divisive",
    "manual",
}


def _parse_decimal(value: Any, default: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)


def _parse_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _parse_str(value: Any, default: str) -> str:
    text = str(value if value is not None else default).strip()
    return text or default


def _round_to_step(value: Decimal, step: Decimal) -> Decimal:
    if step <= 0:
        return value
    return (value / step).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * step


@dataclass(frozen=True, slots=True)
class SnowballNetConfig:
    """Normalised SnowballNet strategy configuration."""

    trade_direction: str
    base_units: int
    initial_lot_size: int
    add_lot_size: int
    max_add_count: int
    max_net_units: int
    take_profit_pips: Decimal
    partial_close_ratio: Decimal
    min_close_units: int
    interval_mode: str
    n_pips_head: Decimal
    n_pips_tail: Decimal
    n_pips_flat_steps: int
    n_pips_gamma: Decimal
    manual_intervals: list[Decimal]
    round_step_pips: Decimal
    margin_reduce_enabled: bool
    margin_reduce_threshold_pct: Decimal
    margin_reduce_target_pct: Decimal
    margin_reduce_ratio: Decimal
    emergency_enabled: bool
    emergency_threshold_pct: Decimal
    margin_rate: Decimal

    @property
    def initial_units(self) -> int:
        return self.base_units * self.initial_lot_size

    @property
    def add_units(self) -> int:
        return self.base_units * self.add_lot_size

    @property
    def effective_max_net_units(self) -> int:
        if self.max_net_units > 0:
            return self.max_net_units
        return self.initial_units + self.add_units * self.max_add_count

    def add_interval_pips(self, step: int) -> Decimal:
        """Return the adverse-distance threshold for a 1-based add step."""
        safe_step = max(1, int(step))
        mode = self.interval_mode
        if mode == "manual":
            if not self.manual_intervals:
                return self.n_pips_head
            index = min(safe_step - 1, len(self.manual_intervals) - 1)
            return _round_to_step(self.manual_intervals[index], self.round_step_pips)

        if mode == "constant" or self.max_add_count <= 1:
            return _round_to_step(self.n_pips_head, self.round_step_pips)

        if safe_step <= self.n_pips_flat_steps:
            return _round_to_step(self.n_pips_head, self.round_step_pips)

        denominator = max(1, self.max_add_count - self.n_pips_flat_steps)
        progress = Decimal(safe_step - self.n_pips_flat_steps) / Decimal(denominator)
        curved = progress**self.n_pips_gamma
        interval = self.n_pips_head - (self.n_pips_head - self.n_pips_tail) * curved
        if interval < self.n_pips_tail:
            interval = self.n_pips_tail
        return _round_to_step(interval, self.round_step_pips)

    @staticmethod
    def from_dict(raw: dict[str, Any]) -> "SnowballNetConfig":
        manual_raw = raw.get("manual_intervals", [])
        manual_intervals: list[Decimal] = []
        if isinstance(manual_raw, list):
            manual_intervals = [_parse_decimal(value, "30") for value in manual_raw]

        return SnowballNetConfig(
            trade_direction=_parse_str(raw.get("trade_direction"), "long").lower(),
            base_units=_parse_int(raw.get("base_units"), 1000),
            initial_lot_size=_parse_int(raw.get("initial_lot_size"), 1),
            add_lot_size=_parse_int(raw.get("add_lot_size"), 1),
            max_add_count=_parse_int(raw.get("max_add_count"), 7),
            max_net_units=_parse_int(raw.get("max_net_units"), 0),
            take_profit_pips=_parse_decimal(raw.get("take_profit_pips"), "25"),
            partial_close_ratio=_parse_decimal(raw.get("partial_close_ratio"), "0.5"),
            min_close_units=_parse_int(raw.get("min_close_units"), 1000),
            interval_mode=_parse_str(raw.get("interval_mode"), "constant").lower(),
            n_pips_head=_parse_decimal(raw.get("n_pips_head"), "30"),
            n_pips_tail=_parse_decimal(raw.get("n_pips_tail"), "14"),
            n_pips_flat_steps=_parse_int(raw.get("n_pips_flat_steps"), 2),
            n_pips_gamma=_parse_decimal(raw.get("n_pips_gamma"), "1.4"),
            manual_intervals=manual_intervals,
            round_step_pips=_parse_decimal(raw.get("round_step_pips"), "0.1"),
            margin_reduce_enabled=_parse_bool(raw.get("margin_reduce_enabled"), False),
            margin_reduce_threshold_pct=_parse_decimal(
                raw.get("margin_reduce_threshold_pct"), "70"
            ),
            margin_reduce_target_pct=_parse_decimal(raw.get("margin_reduce_target_pct"), "50"),
            margin_reduce_ratio=_parse_decimal(raw.get("margin_reduce_ratio"), "0.25"),
            emergency_enabled=_parse_bool(raw.get("emergency_enabled"), True),
            emergency_threshold_pct=_parse_decimal(raw.get("emergency_threshold_pct"), "95"),
            margin_rate=_parse_decimal(raw.get("margin_rate"), "0.04"),
        )

    @staticmethod
    def strict_from_dict(raw: dict[str, Any]) -> "SnowballNetConfig":
        return SnowballNetConfig.from_dict(raw)

    def to_dict(self) -> dict[str, Any]:
        return {
            "trade_direction": self.trade_direction,
            "base_units": self.base_units,
            "initial_lot_size": self.initial_lot_size,
            "add_lot_size": self.add_lot_size,
            "max_add_count": self.max_add_count,
            "max_net_units": self.max_net_units,
            "take_profit_pips": str(self.take_profit_pips),
            "partial_close_ratio": str(self.partial_close_ratio),
            "min_close_units": self.min_close_units,
            "interval_mode": self.interval_mode,
            "n_pips_head": str(self.n_pips_head),
            "n_pips_tail": str(self.n_pips_tail),
            "n_pips_flat_steps": self.n_pips_flat_steps,
            "n_pips_gamma": str(self.n_pips_gamma),
            "manual_intervals": [str(value) for value in self.manual_intervals],
            "round_step_pips": str(self.round_step_pips),
            "margin_reduce_enabled": self.margin_reduce_enabled,
            "margin_reduce_threshold_pct": str(self.margin_reduce_threshold_pct),
            "margin_reduce_target_pct": str(self.margin_reduce_target_pct),
            "margin_reduce_ratio": str(self.margin_reduce_ratio),
            "emergency_enabled": self.emergency_enabled,
            "emergency_threshold_pct": str(self.emergency_threshold_pct),
            "margin_rate": str(self.margin_rate),
        }

    def validate(self) -> None:
        if self.trade_direction not in {"long", "short"}:
            raise ValueError("trade_direction must be 'long' or 'short'")
        if self.base_units <= 0:
            raise ValueError("base_units must be greater than 0")
        if self.initial_lot_size <= 0:
            raise ValueError("initial_lot_size must be greater than 0")
        if self.add_lot_size <= 0:
            raise ValueError("add_lot_size must be greater than 0")
        if self.max_add_count < 0:
            raise ValueError("max_add_count must be greater than or equal to 0")
        if self.max_net_units < 0:
            raise ValueError("max_net_units must be greater than or equal to 0")
        if self.effective_max_net_units < self.initial_units:
            raise ValueError("max_net_units must be 0 or at least the initial units")
        if self.take_profit_pips <= 0:
            raise ValueError("take_profit_pips must be greater than 0")
        if not (Decimal("0") < self.partial_close_ratio <= Decimal("1")):
            raise ValueError("partial_close_ratio must be in the range (0, 1]")
        if self.min_close_units <= 0:
            raise ValueError("min_close_units must be greater than 0")
        if self.interval_mode not in INTERVAL_MODES:
            raise ValueError(f"interval_mode must be one of {sorted(INTERVAL_MODES)}")
        if self.n_pips_head <= 0 or self.n_pips_tail <= 0:
            raise ValueError("n_pips_head and n_pips_tail must be greater than 0")
        if self.n_pips_head < self.n_pips_tail:
            raise ValueError("n_pips_head must be greater than or equal to n_pips_tail")
        if self.n_pips_flat_steps < 0:
            raise ValueError("n_pips_flat_steps must be greater than or equal to 0")
        if self.max_add_count > 0 and self.n_pips_flat_steps >= self.max_add_count:
            raise ValueError("n_pips_flat_steps must be smaller than max_add_count")
        if self.n_pips_gamma <= 0:
            raise ValueError("n_pips_gamma must be greater than 0")
        if self.interval_mode == "manual":
            if len(self.manual_intervals) != self.max_add_count:
                raise ValueError("manual_intervals length must match max_add_count")
            if any(value <= 0 for value in self.manual_intervals):
                raise ValueError("manual_intervals values must be greater than 0")
        if self.round_step_pips <= 0:
            raise ValueError("round_step_pips must be greater than 0")
        if not (Decimal("0") < self.margin_reduce_ratio <= Decimal("1")):
            raise ValueError("margin_reduce_ratio must be in the range (0, 1]")
        if self.margin_reduce_enabled:
            if not (
                Decimal("0")
                < self.margin_reduce_target_pct
                < self.margin_reduce_threshold_pct
                < Decimal("100")
            ):
                raise ValueError(
                    "margin_reduce_target_pct must be below margin_reduce_threshold_pct"
                )
        if self.emergency_enabled and not (
            Decimal("0") < self.emergency_threshold_pct <= Decimal("100")
        ):
            raise ValueError("emergency_threshold_pct must be in the range (0, 100]")
        if self.margin_rate <= 0:
            raise ValueError("margin_rate must be greater than 0")
