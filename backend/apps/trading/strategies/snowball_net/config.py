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
TRADE_DIRECTIONS = {"long", "short", "auto"}
CAPACITY_LIMIT_MODES = {"add_count", "max_net_units"}
ADD_UNIT_ALLOCATION_MODES = {"fixed", "remaining_linear"}
INCREASING_INTERVAL_MODES = {"additive", "multiplicative"}
DECREASING_INTERVAL_MODES = {"subtractive", "divisive"}
LOSS_CUT_MODES = {"full", "staged_margin"}


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
    auto_direction_fast_period: int
    auto_direction_slow_period: int
    auto_direction_min_samples: int
    auto_direction_threshold_pips: Decimal
    auto_direction_filter_enabled: bool
    auto_direction_max_spread_pips: Decimal
    auto_direction_max_volatility_pips: Decimal
    auto_direction_max_volatility_multiplier: Decimal
    auto_direction_max_slope_pips: Decimal
    base_units: int
    initial_lot_size: int
    add_lot_size: int
    capacity_limit_mode: str
    max_add_count: int
    max_net_units: int
    add_unit_allocation_mode: str
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
    atr_period: int
    atr_baseline_period: int
    adaptive_interval_enabled: bool
    adaptive_interval_reference_pips: Decimal
    adaptive_interval_min_multiplier: Decimal
    adaptive_interval_max_multiplier: Decimal
    volatility_guard_enabled: bool
    volatility_guard_max_atr_pips: Decimal
    volatility_guard_max_atr_multiplier: Decimal
    volatility_ema_period: int
    spread_guard_enabled: bool
    max_spread_pips: Decimal
    add_trend_guard_enabled: bool
    add_trend_ema_period: int
    add_trend_max_opposite_deviation_pips: Decimal
    add_trend_max_opposite_slope_pips: Decimal
    add_margin_guard_enabled: bool
    add_margin_guard_max_pct: Decimal
    margin_reduce_enabled: bool
    margin_reduce_threshold_pct: Decimal
    margin_reduce_target_pct: Decimal
    margin_reduce_ratio: Decimal
    loss_cut_enabled: bool
    loss_cut_mode: str
    loss_cut_threshold_pips: Decimal
    loss_cut_stage_threshold_pct: Decimal
    loss_cut_stage_target_pct: Decimal
    loss_cut_stage_ratio: Decimal
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
        if self.capacity_limit_mode == "max_net_units" and self.max_net_units > 0:
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
        interval = self.n_pips_head + (self.n_pips_tail - self.n_pips_head) * curved
        if self.n_pips_tail >= self.n_pips_head:
            interval = min(interval, self.n_pips_tail)
        else:
            interval = max(interval, self.n_pips_tail)
        return _round_to_step(interval, self.round_step_pips)

    def round_pips(self, value: Decimal) -> Decimal:
        """Round a pips value with the configured step."""
        return _round_to_step(value, self.round_step_pips)

    @staticmethod
    def from_dict(raw: dict[str, Any]) -> "SnowballNetConfig":
        manual_raw = raw.get("manual_intervals", [])
        manual_intervals: list[Decimal] = []
        if isinstance(manual_raw, list):
            manual_intervals = [_parse_decimal(value, "30") for value in manual_raw]

        capacity_limit_mode = _parse_str(raw.get("capacity_limit_mode"), "").lower()
        raw_max_net_units = _parse_int(raw.get("max_net_units"), 0)
        if raw.get("capacity_limit_mode") is None or capacity_limit_mode == "":
            capacity_limit_mode = "max_net_units" if raw_max_net_units > 0 else "add_count"
        max_net_units = raw_max_net_units if capacity_limit_mode == "max_net_units" else 0
        add_unit_allocation_mode = _parse_str(raw.get("add_unit_allocation_mode"), "fixed").lower()
        if capacity_limit_mode == "add_count":
            add_unit_allocation_mode = "fixed"

        return SnowballNetConfig(
            trade_direction=_parse_str(raw.get("trade_direction"), "long").lower(),
            auto_direction_fast_period=_parse_int(raw.get("auto_direction_fast_period"), 12),
            auto_direction_slow_period=_parse_int(raw.get("auto_direction_slow_period"), 48),
            auto_direction_min_samples=_parse_int(raw.get("auto_direction_min_samples"), 48),
            auto_direction_threshold_pips=_parse_decimal(
                raw.get("auto_direction_threshold_pips"), "0"
            ),
            auto_direction_filter_enabled=_parse_bool(
                raw.get("auto_direction_filter_enabled"), False
            ),
            auto_direction_max_spread_pips=_parse_decimal(
                raw.get("auto_direction_max_spread_pips"), "3"
            ),
            auto_direction_max_volatility_pips=_parse_decimal(
                raw.get("auto_direction_max_volatility_pips"), "25"
            ),
            auto_direction_max_volatility_multiplier=_parse_decimal(
                raw.get("auto_direction_max_volatility_multiplier"), "3"
            ),
            auto_direction_max_slope_pips=_parse_decimal(
                raw.get("auto_direction_max_slope_pips"), "5"
            ),
            base_units=_parse_int(raw.get("base_units"), 1000),
            initial_lot_size=_parse_int(raw.get("initial_lot_size"), 1),
            add_lot_size=_parse_int(raw.get("add_lot_size"), 1),
            capacity_limit_mode=capacity_limit_mode,
            max_add_count=_parse_int(raw.get("max_add_count"), 7),
            max_net_units=max_net_units,
            add_unit_allocation_mode=add_unit_allocation_mode,
            take_profit_pips=_parse_decimal(raw.get("take_profit_pips"), "25"),
            partial_close_ratio=_parse_decimal(raw.get("partial_close_ratio"), "0.5"),
            min_close_units=_parse_int(raw.get("min_close_units"), 1000),
            interval_mode=_parse_str(raw.get("interval_mode"), "constant").lower(),
            n_pips_head=_parse_decimal(raw.get("n_pips_head"), "30"),
            n_pips_tail=_parse_decimal(raw.get("n_pips_tail"), "30"),
            n_pips_flat_steps=_parse_int(raw.get("n_pips_flat_steps"), 2),
            n_pips_gamma=_parse_decimal(raw.get("n_pips_gamma"), "1.4"),
            manual_intervals=manual_intervals,
            round_step_pips=_parse_decimal(raw.get("round_step_pips"), "0.1"),
            atr_period=_parse_int(raw.get("atr_period"), 14),
            atr_baseline_period=_parse_int(raw.get("atr_baseline_period"), 96),
            adaptive_interval_enabled=_parse_bool(raw.get("adaptive_interval_enabled"), False),
            adaptive_interval_reference_pips=_parse_decimal(
                raw.get("adaptive_interval_reference_pips"), "10"
            ),
            adaptive_interval_min_multiplier=_parse_decimal(
                raw.get("adaptive_interval_min_multiplier"), "0.5"
            ),
            adaptive_interval_max_multiplier=_parse_decimal(
                raw.get("adaptive_interval_max_multiplier"), "2.5"
            ),
            volatility_guard_enabled=_parse_bool(raw.get("volatility_guard_enabled"), False),
            volatility_guard_max_atr_pips=_parse_decimal(
                raw.get("volatility_guard_max_atr_pips"), "25"
            ),
            volatility_guard_max_atr_multiplier=_parse_decimal(
                raw.get("volatility_guard_max_atr_multiplier"), "3"
            ),
            volatility_ema_period=_parse_int(raw.get("volatility_ema_period"), 60),
            spread_guard_enabled=_parse_bool(raw.get("spread_guard_enabled"), False),
            max_spread_pips=_parse_decimal(raw.get("max_spread_pips"), "3"),
            add_trend_guard_enabled=_parse_bool(raw.get("add_trend_guard_enabled"), False),
            add_trend_ema_period=_parse_int(raw.get("add_trend_ema_period"), 200),
            add_trend_max_opposite_deviation_pips=_parse_decimal(
                raw.get("add_trend_max_opposite_deviation_pips"), "50"
            ),
            add_trend_max_opposite_slope_pips=_parse_decimal(
                raw.get("add_trend_max_opposite_slope_pips"), "0"
            ),
            add_margin_guard_enabled=_parse_bool(raw.get("add_margin_guard_enabled"), False),
            add_margin_guard_max_pct=_parse_decimal(raw.get("add_margin_guard_max_pct"), "65"),
            margin_reduce_enabled=_parse_bool(raw.get("margin_reduce_enabled"), False),
            margin_reduce_threshold_pct=_parse_decimal(
                raw.get("margin_reduce_threshold_pct"), "70"
            ),
            margin_reduce_target_pct=_parse_decimal(raw.get("margin_reduce_target_pct"), "50"),
            margin_reduce_ratio=_parse_decimal(raw.get("margin_reduce_ratio"), "0.25"),
            loss_cut_enabled=_parse_bool(raw.get("loss_cut_enabled"), False),
            loss_cut_mode=_parse_str(raw.get("loss_cut_mode"), "full").lower(),
            loss_cut_threshold_pips=_parse_decimal(raw.get("loss_cut_threshold_pips"), "100"),
            loss_cut_stage_threshold_pct=_parse_decimal(
                raw.get("loss_cut_stage_threshold_pct"), "80"
            ),
            loss_cut_stage_target_pct=_parse_decimal(raw.get("loss_cut_stage_target_pct"), "60"),
            loss_cut_stage_ratio=_parse_decimal(raw.get("loss_cut_stage_ratio"), "0.25"),
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
            "auto_direction_fast_period": self.auto_direction_fast_period,
            "auto_direction_slow_period": self.auto_direction_slow_period,
            "auto_direction_min_samples": self.auto_direction_min_samples,
            "auto_direction_threshold_pips": str(self.auto_direction_threshold_pips),
            "auto_direction_filter_enabled": self.auto_direction_filter_enabled,
            "auto_direction_max_spread_pips": str(self.auto_direction_max_spread_pips),
            "auto_direction_max_volatility_pips": str(self.auto_direction_max_volatility_pips),
            "auto_direction_max_volatility_multiplier": str(
                self.auto_direction_max_volatility_multiplier
            ),
            "auto_direction_max_slope_pips": str(self.auto_direction_max_slope_pips),
            "base_units": self.base_units,
            "initial_lot_size": self.initial_lot_size,
            "add_lot_size": self.add_lot_size,
            "capacity_limit_mode": self.capacity_limit_mode,
            "max_add_count": self.max_add_count,
            "max_net_units": self.max_net_units,
            "add_unit_allocation_mode": self.add_unit_allocation_mode,
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
            "atr_period": self.atr_period,
            "atr_baseline_period": self.atr_baseline_period,
            "adaptive_interval_enabled": self.adaptive_interval_enabled,
            "adaptive_interval_reference_pips": str(self.adaptive_interval_reference_pips),
            "adaptive_interval_min_multiplier": str(self.adaptive_interval_min_multiplier),
            "adaptive_interval_max_multiplier": str(self.adaptive_interval_max_multiplier),
            "volatility_guard_enabled": self.volatility_guard_enabled,
            "volatility_guard_max_atr_pips": str(self.volatility_guard_max_atr_pips),
            "volatility_guard_max_atr_multiplier": str(self.volatility_guard_max_atr_multiplier),
            "volatility_ema_period": self.volatility_ema_period,
            "spread_guard_enabled": self.spread_guard_enabled,
            "max_spread_pips": str(self.max_spread_pips),
            "add_trend_guard_enabled": self.add_trend_guard_enabled,
            "add_trend_ema_period": self.add_trend_ema_period,
            "add_trend_max_opposite_deviation_pips": str(
                self.add_trend_max_opposite_deviation_pips
            ),
            "add_trend_max_opposite_slope_pips": str(self.add_trend_max_opposite_slope_pips),
            "add_margin_guard_enabled": self.add_margin_guard_enabled,
            "add_margin_guard_max_pct": str(self.add_margin_guard_max_pct),
            "margin_reduce_enabled": self.margin_reduce_enabled,
            "margin_reduce_threshold_pct": str(self.margin_reduce_threshold_pct),
            "margin_reduce_target_pct": str(self.margin_reduce_target_pct),
            "margin_reduce_ratio": str(self.margin_reduce_ratio),
            "loss_cut_enabled": self.loss_cut_enabled,
            "loss_cut_mode": self.loss_cut_mode,
            "loss_cut_threshold_pips": str(self.loss_cut_threshold_pips),
            "loss_cut_stage_threshold_pct": str(self.loss_cut_stage_threshold_pct),
            "loss_cut_stage_target_pct": str(self.loss_cut_stage_target_pct),
            "loss_cut_stage_ratio": str(self.loss_cut_stage_ratio),
            "emergency_enabled": self.emergency_enabled,
            "emergency_threshold_pct": str(self.emergency_threshold_pct),
            "margin_rate": str(self.margin_rate),
        }

    def validate(self) -> None:
        if self.trade_direction not in TRADE_DIRECTIONS:
            raise ValueError("trade_direction must be 'long', 'short', or 'auto'")
        if self.auto_direction_fast_period <= 0:
            raise ValueError("auto_direction_fast_period must be greater than 0")
        if self.auto_direction_slow_period <= self.auto_direction_fast_period:
            raise ValueError(
                "auto_direction_slow_period must be greater than auto_direction_fast_period"
            )
        if self.auto_direction_min_samples <= 0:
            raise ValueError("auto_direction_min_samples must be greater than 0")
        if self.auto_direction_threshold_pips < 0:
            raise ValueError("auto_direction_threshold_pips must be greater than or equal to 0")
        if self.base_units <= 0:
            raise ValueError("base_units must be greater than 0")
        if self.initial_lot_size <= 0:
            raise ValueError("initial_lot_size must be greater than 0")
        if self.add_lot_size <= 0:
            raise ValueError("add_lot_size must be greater than 0")
        if self.capacity_limit_mode not in CAPACITY_LIMIT_MODES:
            raise ValueError(f"capacity_limit_mode must be one of {sorted(CAPACITY_LIMIT_MODES)}")
        if self.max_add_count < 0:
            raise ValueError("max_add_count must be greater than or equal to 0")
        if self.max_net_units < 0:
            raise ValueError("max_net_units must be greater than or equal to 0")
        if self.capacity_limit_mode == "max_net_units":
            if self.max_net_units <= 0:
                raise ValueError(
                    "max_net_units must be set when capacity_limit_mode is max_net_units"
                )
            if self.max_net_units < self.initial_units:
                raise ValueError("max_net_units must be at least the initial units")
        if self.add_unit_allocation_mode not in ADD_UNIT_ALLOCATION_MODES:
            raise ValueError(
                f"add_unit_allocation_mode must be one of {sorted(ADD_UNIT_ALLOCATION_MODES)}"
            )
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
        if self.interval_mode in INCREASING_INTERVAL_MODES and (
            self.n_pips_tail < self.n_pips_head
        ):
            raise ValueError(
                "n_pips_tail must be greater than or equal to n_pips_head for additive "
                "or multiplicative interval modes"
            )
        if self.interval_mode in DECREASING_INTERVAL_MODES and (
            self.n_pips_tail > self.n_pips_head
        ):
            raise ValueError(
                "n_pips_tail must be less than or equal to n_pips_head for subtractive "
                "or divisive interval modes"
            )
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
        if self.atr_period <= 0:
            raise ValueError("atr_period must be greater than 0")
        if self.atr_baseline_period <= 0:
            raise ValueError("atr_baseline_period must be greater than 0")
        if self.adaptive_interval_reference_pips <= 0:
            raise ValueError("adaptive_interval_reference_pips must be greater than 0")
        if not (
            Decimal("0")
            < self.adaptive_interval_min_multiplier
            <= self.adaptive_interval_max_multiplier
        ):
            raise ValueError("adaptive interval multipliers must satisfy 0 < min <= max")
        if self.volatility_guard_max_atr_pips <= 0:
            raise ValueError("volatility_guard_max_atr_pips must be greater than 0")
        if self.volatility_guard_max_atr_multiplier <= 0:
            raise ValueError("volatility_guard_max_atr_multiplier must be greater than 0")
        if self.volatility_ema_period <= 0:
            raise ValueError("volatility_ema_period must be greater than 0")
        if self.max_spread_pips <= 0:
            raise ValueError("max_spread_pips must be greater than 0")
        if self.add_trend_ema_period <= 0:
            raise ValueError("add_trend_ema_period must be greater than 0")
        if self.add_trend_max_opposite_deviation_pips <= 0:
            raise ValueError("add_trend_max_opposite_deviation_pips must be greater than 0")
        if self.add_trend_max_opposite_slope_pips < 0:
            raise ValueError("add_trend_max_opposite_slope_pips must be greater than or equal to 0")
        if not (Decimal("0") < self.add_margin_guard_max_pct < Decimal("100")):
            raise ValueError("add_margin_guard_max_pct must be in the range (0, 100)")
        if self.auto_direction_max_spread_pips <= 0:
            raise ValueError("auto_direction_max_spread_pips must be greater than 0")
        if self.auto_direction_max_volatility_pips <= 0:
            raise ValueError("auto_direction_max_volatility_pips must be greater than 0")
        if self.auto_direction_max_volatility_multiplier <= 0:
            raise ValueError("auto_direction_max_volatility_multiplier must be greater than 0")
        if self.auto_direction_max_slope_pips <= 0:
            raise ValueError("auto_direction_max_slope_pips must be greater than 0")
        if not (Decimal("0") < self.margin_reduce_ratio <= Decimal("1")):
            raise ValueError("margin_reduce_ratio must be in the range (0, 1]")
        if self.loss_cut_mode not in LOSS_CUT_MODES:
            raise ValueError(f"loss_cut_mode must be one of {sorted(LOSS_CUT_MODES)}")
        if self.loss_cut_threshold_pips <= 0:
            raise ValueError("loss_cut_threshold_pips must be greater than 0")
        if not (Decimal("0") < self.loss_cut_stage_ratio <= Decimal("1")):
            raise ValueError("loss_cut_stage_ratio must be in the range (0, 1]")
        if not (
            Decimal("0")
            < self.loss_cut_stage_target_pct
            < self.loss_cut_stage_threshold_pct
            < Decimal("100")
        ):
            raise ValueError("loss_cut_stage_target_pct must be below loss_cut_stage_threshold_pct")
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
