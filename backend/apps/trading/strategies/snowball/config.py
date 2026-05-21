"""Configuration model for the Snowball strategy."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_FLOOR
from typing import Any

from apps.trading.strategies.snowball.parsing import (
    _parse_bool,
    _parse_decimal,
    _parse_int,
    _parse_str,
)

WARMUP_OPTIONAL_KEYS = (
    "warmup_enabled",
    "warmup_initial_unit_ratio_pct",
    "warmup_unit_ramp_steps",
    "warmup_start_gate_enabled",
    "warmup_gate_spread_enabled",
    "warmup_gate_max_spread_pips",
    "warmup_gate_volatility_enabled",
    "warmup_gate_volatility_window_ticks",
    "warmup_gate_max_volatility_pips",
    "warmup_gate_trend_enabled",
    "warmup_gate_trend_window_ticks",
    "warmup_gate_max_trend_pips",
    "warmup_position_limit_enabled",
    "warmup_max_positions",
    "warmup_rebuild_limit_enabled",
    "warmup_max_rebuilds_per_tick",
    "warmup_completion_mode",
    "warmup_min_elapsed_minutes",
    "warmup_required_tp_closes",
)


@dataclass(frozen=True, slots=True)
class GridConfig:
    base_units: int
    m_pips: Decimal
    trend_lot_size: int
    r_max: int
    f_max: int
    post_r_max_base_factor: Decimal
    refill_limit_enabled: bool
    refill_up_to: int


@dataclass(frozen=True, slots=True)
class CounterIntervalConfig:
    """Counter-entry interval progression settings."""

    head: Decimal
    tail: Decimal
    flat_steps: int
    gamma: Decimal
    mode: str
    manual_intervals: list[Decimal]


@dataclass(frozen=True, slots=True)
class CounterTakeProfitConfig:
    """Counter-entry take-profit policy settings."""

    mode: str
    pips: Decimal
    step_amount: Decimal
    multiplier: Decimal
    round_step_pips: Decimal


@dataclass(frozen=True, slots=True)
class StopLossConfig:
    enabled: bool
    mode: str
    pips_head: Decimal
    pips_tail: Decimal
    pips_flat_steps: int
    pips_gamma: Decimal
    manual_pips: list[Decimal]
    preserve_highest_retracement_enabled: bool
    preserve_highest_r_from: int


@dataclass(frozen=True, slots=True)
class RebuildConfig:
    enabled: bool
    refill_limit_enabled: bool
    refill_up_to: int
    entry_price_mode: str
    stop_loss_mode: str
    stop_loss_manual_pips: list[Decimal]
    take_profit_mode: str
    take_profit_pips_head: Decimal
    take_profit_pips_tail: Decimal
    take_profit_pips_flat_steps: int
    take_profit_pips_gamma: Decimal
    take_profit_manual_pips: list[Decimal]


@dataclass(frozen=True, slots=True)
class RebuildPolicyConfig:
    """High-level rebuild and reseed policy settings."""

    enabled: bool
    entry_price_mode: str
    reseed_on_all_pending: bool


@dataclass(frozen=True, slots=True)
class WarmupConfig:
    """Cold-start warmup controls for Snowball trading."""

    enabled: bool
    initial_unit_ratio_pct: Decimal
    unit_ramp_steps: int
    start_gate_enabled: bool
    gate_spread_enabled: bool
    gate_max_spread_pips: Decimal
    gate_volatility_enabled: bool
    gate_volatility_window_ticks: int
    gate_max_volatility_pips: Decimal
    gate_trend_enabled: bool
    gate_trend_window_ticks: int
    gate_max_trend_pips: Decimal
    position_limit_enabled: bool
    max_positions: int
    rebuild_limit_enabled: bool
    max_rebuilds_per_tick: int
    completion_mode: str
    min_elapsed_minutes: int
    required_tp_closes: int


@dataclass(frozen=True, slots=True)
class ProtectionConfig:
    shrink_enabled: bool
    m_th: Decimal
    m1_th: Decimal
    emergency_enabled: bool
    emergency_threshold: Decimal


@dataclass(frozen=True, slots=True)
class RiskLimitConfig:
    """Risk and margin-protection thresholds."""

    shrink_enabled: bool
    margin_shrink_threshold: Decimal
    margin_shrink_target: Decimal
    emergency_enabled: bool
    emergency_threshold: Decimal
    stop_loss_enabled: bool


@dataclass(frozen=True, slots=True)
class SnowballStrategyConfig:
    """Normalised Snowball strategy configuration."""

    # Core
    base_units: int
    base_units_auto_adjust_enabled: bool
    base_units_balance_ratio: Decimal
    base_units_step: int
    base_units_auto_adjust_floor_enabled: bool
    m_pips: Decimal
    trend_lot_size: int
    r_max: int
    f_max: int
    post_r_max_base_factor: Decimal

    # Slot refill after normal close
    refill_limit_enabled: bool
    refill_up_to: int  # R1..R(refill_up_to) refillable when limit is enabled

    # Counter-trend interval formula
    n_pips_head: Decimal
    n_pips_tail: Decimal
    n_pips_flat_steps: int
    n_pips_gamma: Decimal
    interval_mode: str
    manual_intervals: list[Decimal]

    # Stop-loss pip distance formula.  Mirrors the counter-trend
    # interval progression (``stop_loss_mode`` accepts the same values
    # as ``interval_mode``) but is configured independently so the SL
    # distance can be tuned separately from the averaging grid.  For
    # example, a strategy can use a gentle interval progression but a
    # uniform, tight SL on every slot.
    stop_loss_mode: str
    stop_loss_pips_head: Decimal
    stop_loss_pips_tail: Decimal
    stop_loss_pips_flat_steps: int
    stop_loss_pips_gamma: Decimal
    stop_loss_manual_pips: list[Decimal]

    # Counter-trend step TP
    counter_tp_mode: str
    counter_tp_pips: Decimal
    counter_tp_step_amount: Decimal
    counter_tp_multiplier: Decimal
    round_step_pips: Decimal

    # Margin protection
    shrink_enabled: bool
    m_th: Decimal
    m1_th: Decimal
    stop_loss_enabled: bool
    rebuild_entry_price_mode: str
    rebuild_entry_buffer_pips: Decimal
    rebuild_cooldown_seconds: Decimal
    rebuild_stop_loss_mode: str
    rebuild_stop_loss_manual_pips: list[Decimal]
    rebuild_take_profit_mode: str
    rebuild_take_profit_pips_head: Decimal
    rebuild_take_profit_pips_tail: Decimal
    rebuild_take_profit_pips_flat_steps: int
    rebuild_take_profit_pips_gamma: Decimal
    rebuild_take_profit_manual_pips: list[Decimal]
    preserve_highest_retracement_enabled: bool
    preserve_highest_r_from: int
    # When ``stop_loss_enabled`` is True, controls whether a stopped-out
    # slot is rebuilt (re-opened) once price reaches the configured
    # rebuild entry price. Historical behaviour is ``True`` — stop-losses
    # create a pending_rebuild snapshot and the slot comes back when
    # price revisits.  Setting this to ``False`` makes a stop-loss close
    # the slot permanently (no pending_rebuild snapshot is retained),
    # so the grid shrinks on each SL instead of recovering.
    rebuild_enabled: bool
    emergency_enabled: bool
    emergency_threshold: Decimal

    pip_size: Decimal

    # Cycle re-seed: create a new cycle when all positions in a direction
    # are pending stop-loss rebuild (no open positions).
    reseed_on_all_pending: bool

    # Warmup / cold-start risk controls.
    warmup_enabled: bool
    warmup_initial_unit_ratio_pct: Decimal
    warmup_unit_ramp_steps: int
    warmup_start_gate_enabled: bool
    warmup_gate_spread_enabled: bool
    warmup_gate_max_spread_pips: Decimal
    warmup_gate_volatility_enabled: bool
    warmup_gate_volatility_window_ticks: int
    warmup_gate_max_volatility_pips: Decimal
    warmup_gate_trend_enabled: bool
    warmup_gate_trend_window_ticks: int
    warmup_gate_max_trend_pips: Decimal
    warmup_position_limit_enabled: bool
    warmup_max_positions: int
    warmup_rebuild_limit_enabled: bool
    warmup_max_rebuilds_per_tick: int
    warmup_completion_mode: str
    warmup_min_elapsed_minutes: int
    warmup_required_tp_closes: int

    @property
    def grid(self) -> GridConfig:
        return GridConfig(
            base_units=self.base_units,
            m_pips=self.m_pips,
            trend_lot_size=self.trend_lot_size,
            r_max=self.r_max,
            f_max=self.f_max,
            post_r_max_base_factor=self.post_r_max_base_factor,
            refill_limit_enabled=self.refill_limit_enabled,
            refill_up_to=self.effective_refill_up_to,
        )

    def effective_base_units(self, account_balance: Any | None = None) -> int:
        """Return the base units used for newly created Snowball layers."""
        if not self.base_units_auto_adjust_enabled:
            return self.base_units

        balance = _optional_decimal(account_balance)
        if balance is None or balance <= 0:
            return self.base_units
        if self.base_units_balance_ratio <= 0:
            return self.base_units

        step = max(1, self.base_units_step)
        raw_units = balance / self.base_units_balance_ratio
        stepped_units = (raw_units / Decimal(step)).to_integral_value(
            rounding=ROUND_FLOOR
        ) * Decimal(step)
        floor = self.base_units if self.base_units_auto_adjust_floor_enabled else step
        return max(floor, int(stepped_units))

    def warmup_scaled_base_units(
        self,
        account_balance: Any | None = None,
        *,
        ratio_pct: Decimal,
    ) -> int:
        """Return base units reduced by the current warmup unit ratio."""
        base_units = self.effective_base_units(account_balance)
        ratio = max(Decimal("0.01"), min(Decimal("100"), ratio_pct)) / Decimal("100")
        raw_units = Decimal(base_units) * ratio
        step = Decimal(max(1, self.base_units_step if self.base_units_auto_adjust_enabled else 1))
        stepped_units = (raw_units / step).to_integral_value(rounding=ROUND_FLOOR) * step
        return max(1, int(stepped_units))

    @property
    def effective_refill_up_to(self) -> int:
        """Return the runtime refill slot limit after the limit toggle."""
        return self.refill_up_to if self.refill_limit_enabled else self.r_max

    @property
    def intervals(self) -> CounterIntervalConfig:
        return CounterIntervalConfig(
            head=self.n_pips_head,
            tail=self.n_pips_tail,
            flat_steps=self.n_pips_flat_steps,
            gamma=self.n_pips_gamma,
            mode=self.interval_mode,
            manual_intervals=self.manual_intervals,
        )

    @property
    def take_profit(self) -> CounterTakeProfitConfig:
        return CounterTakeProfitConfig(
            mode=self.counter_tp_mode,
            pips=self.counter_tp_pips,
            step_amount=self.counter_tp_step_amount,
            multiplier=self.counter_tp_multiplier,
            round_step_pips=self.round_step_pips,
        )

    @property
    def stop_loss(self) -> StopLossConfig:
        return StopLossConfig(
            enabled=self.stop_loss_enabled,
            mode=self.stop_loss_mode,
            pips_head=self.stop_loss_pips_head,
            pips_tail=self.stop_loss_pips_tail,
            pips_flat_steps=self.stop_loss_pips_flat_steps,
            pips_gamma=self.stop_loss_pips_gamma,
            manual_pips=self.stop_loss_manual_pips,
            preserve_highest_retracement_enabled=self.preserve_highest_retracement_enabled,
            preserve_highest_r_from=self.preserve_highest_r_from,
        )

    @property
    def rebuild(self) -> RebuildConfig:
        return RebuildConfig(
            enabled=self.rebuild_enabled,
            refill_limit_enabled=self.refill_limit_enabled,
            refill_up_to=self.refill_up_to,
            entry_price_mode=self.rebuild_entry_price_mode,
            stop_loss_mode=self.rebuild_stop_loss_mode,
            stop_loss_manual_pips=self.rebuild_stop_loss_manual_pips,
            take_profit_mode=self.rebuild_take_profit_mode,
            take_profit_pips_head=self.rebuild_take_profit_pips_head,
            take_profit_pips_tail=self.rebuild_take_profit_pips_tail,
            take_profit_pips_flat_steps=self.rebuild_take_profit_pips_flat_steps,
            take_profit_pips_gamma=self.rebuild_take_profit_pips_gamma,
            take_profit_manual_pips=self.rebuild_take_profit_manual_pips,
        )

    @property
    def rebuild_policy(self) -> RebuildPolicyConfig:
        return RebuildPolicyConfig(
            enabled=self.rebuild_enabled,
            entry_price_mode=self.rebuild_entry_price_mode,
            reseed_on_all_pending=self.reseed_on_all_pending,
        )

    @property
    def protection(self) -> ProtectionConfig:
        return ProtectionConfig(
            shrink_enabled=self.shrink_enabled,
            m_th=self.m_th,
            m1_th=self.m1_th,
            emergency_enabled=self.emergency_enabled,
            emergency_threshold=self.emergency_threshold,
        )

    @property
    def risk_limits(self) -> RiskLimitConfig:
        return RiskLimitConfig(
            shrink_enabled=self.shrink_enabled,
            margin_shrink_threshold=self.m_th,
            margin_shrink_target=self.m1_th,
            emergency_enabled=self.emergency_enabled,
            emergency_threshold=self.emergency_threshold,
            stop_loss_enabled=self.stop_loss_enabled,
        )

    @property
    def warmup(self) -> WarmupConfig:
        return WarmupConfig(
            enabled=self.warmup_enabled,
            initial_unit_ratio_pct=self.warmup_initial_unit_ratio_pct,
            unit_ramp_steps=self.warmup_unit_ramp_steps,
            start_gate_enabled=self.warmup_start_gate_enabled,
            gate_spread_enabled=self.warmup_gate_spread_enabled,
            gate_max_spread_pips=self.warmup_gate_max_spread_pips,
            gate_volatility_enabled=self.warmup_gate_volatility_enabled,
            gate_volatility_window_ticks=self.warmup_gate_volatility_window_ticks,
            gate_max_volatility_pips=self.warmup_gate_max_volatility_pips,
            gate_trend_enabled=self.warmup_gate_trend_enabled,
            gate_trend_window_ticks=self.warmup_gate_trend_window_ticks,
            gate_max_trend_pips=self.warmup_gate_max_trend_pips,
            position_limit_enabled=self.warmup_position_limit_enabled,
            max_positions=self.warmup_max_positions,
            rebuild_limit_enabled=self.warmup_rebuild_limit_enabled,
            max_rebuilds_per_tick=self.warmup_max_rebuilds_per_tick,
            completion_mode=self.warmup_completion_mode,
            min_elapsed_minutes=self.warmup_min_elapsed_minutes,
            required_tp_closes=self.warmup_required_tp_closes,
        )

    @staticmethod
    def from_dict(raw: dict[str, Any]) -> SnowballStrategyConfig:
        manual_raw = raw.get("manual_intervals", [])
        manual_intervals: list[Decimal] = []
        if isinstance(manual_raw, list):
            for v in manual_raw:
                manual_intervals.append(_parse_decimal(v, "30"))

        sl_manual_raw = raw.get("stop_loss_manual_pips", [])
        stop_loss_manual_pips: list[Decimal] = []
        if isinstance(sl_manual_raw, list):
            for v in sl_manual_raw:
                stop_loss_manual_pips.append(_parse_decimal(v, "30"))

        rebuild_sl_manual_raw = raw.get("rebuild_stop_loss_manual_pips", [])
        rebuild_stop_loss_manual_pips: list[Decimal] = []
        if isinstance(rebuild_sl_manual_raw, list):
            for v in rebuild_sl_manual_raw:
                rebuild_stop_loss_manual_pips.append(_parse_decimal(v, "30"))

        rebuild_tp_manual_raw = raw.get("rebuild_take_profit_manual_pips", [])
        rebuild_take_profit_manual_pips: list[Decimal] = []
        if isinstance(rebuild_tp_manual_raw, list):
            for v in rebuild_tp_manual_raw:
                rebuild_take_profit_manual_pips.append(_parse_decimal(v, "25"))

        n_pips_head = _parse_decimal(raw.get("n_pips_head", "30"), "30")
        n_pips_tail = _parse_decimal(raw.get("n_pips_tail", "14"), "14")
        n_pips_flat_steps = _parse_int(raw.get("n_pips_flat_steps", 2), 2)
        n_pips_gamma = _parse_decimal(raw.get("n_pips_gamma", "1.4"), "1.4")
        interval_mode = _parse_str(raw.get("interval_mode"), "constant")
        rebuild_take_profit_mode = _parse_str(raw.get("rebuild_take_profit_mode"), "same_pips")
        raw_refill_up_to = raw.get("refill_up_to", 2)
        refill_up_to = _parse_int(raw_refill_up_to, 2)
        if "refill_limit_enabled" in raw:
            refill_limit_enabled = _parse_bool(raw.get("refill_limit_enabled"), True)
        elif "refill_enabled" in raw:
            legacy_refill_enabled = _parse_bool(raw.get("refill_enabled"), True)
            refill_limit_enabled = True
            if not legacy_refill_enabled:
                refill_up_to = 0
        else:
            refill_limit_enabled = True

        return SnowballStrategyConfig(
            base_units=_parse_int(raw.get("base_units", 1000), 1000),
            base_units_auto_adjust_enabled=_parse_bool(
                raw.get("base_units_auto_adjust_enabled", False), False
            ),
            base_units_balance_ratio=_parse_decimal(
                raw.get("base_units_balance_ratio", "1000"), "1000"
            ),
            base_units_step=_parse_int(raw.get("base_units_step", 100), 100),
            base_units_auto_adjust_floor_enabled=_parse_bool(
                raw.get("base_units_auto_adjust_floor_enabled", False), False
            ),
            m_pips=_parse_decimal(raw.get("m_pips", "50"), "50"),
            trend_lot_size=_parse_int(raw.get("trend_lot_size", 1), 1),
            r_max=_parse_int(raw.get("r_max", 7), 7),
            f_max=_parse_int(raw.get("f_max", 3), 3),
            post_r_max_base_factor=_parse_decimal(raw.get("post_r_max_base_factor", "1"), "1"),
            refill_limit_enabled=refill_limit_enabled,
            refill_up_to=refill_up_to,
            n_pips_head=n_pips_head,
            n_pips_tail=n_pips_tail,
            n_pips_flat_steps=n_pips_flat_steps,
            n_pips_gamma=n_pips_gamma,
            interval_mode=interval_mode,
            manual_intervals=manual_intervals,
            stop_loss_mode=_parse_str(raw.get("stop_loss_mode"), "auto"),
            stop_loss_pips_head=_parse_decimal(raw.get("stop_loss_pips_head"), str(n_pips_head)),
            stop_loss_pips_tail=_parse_decimal(raw.get("stop_loss_pips_tail"), str(n_pips_tail)),
            stop_loss_pips_flat_steps=_parse_int(
                raw.get("stop_loss_pips_flat_steps"), n_pips_flat_steps
            ),
            stop_loss_pips_gamma=_parse_decimal(raw.get("stop_loss_pips_gamma"), str(n_pips_gamma)),
            stop_loss_manual_pips=stop_loss_manual_pips,
            counter_tp_mode=_parse_str(raw.get("counter_tp_mode"), "weighted_avg"),
            counter_tp_pips=_parse_decimal(raw.get("counter_tp_pips", "25"), "25"),
            counter_tp_step_amount=_parse_decimal(raw.get("counter_tp_step_amount", "2.5"), "2.5"),
            counter_tp_multiplier=_parse_decimal(raw.get("counter_tp_multiplier", "1.2"), "1.2"),
            round_step_pips=_parse_decimal(raw.get("round_step_pips", "0.1"), "0.1"),
            shrink_enabled=_parse_bool(raw.get("shrink_enabled", False), False),
            m_th=_parse_decimal(raw.get("m_th", "70"), "70"),
            m1_th=_parse_decimal(raw.get("m1_th", "50"), "50"),
            stop_loss_enabled=_parse_bool(raw.get("stop_loss_enabled", False), False),
            rebuild_entry_price_mode=_parse_str(
                raw.get("rebuild_entry_price_mode"), "original_entry"
            ),
            rebuild_entry_buffer_pips=_parse_decimal(
                raw.get("rebuild_entry_buffer_pips", "0"), "0"
            ),
            rebuild_cooldown_seconds=_parse_decimal(raw.get("rebuild_cooldown_seconds", "0"), "0"),
            rebuild_stop_loss_mode=_parse_str(raw.get("rebuild_stop_loss_mode"), "same_pips"),
            rebuild_stop_loss_manual_pips=rebuild_stop_loss_manual_pips,
            rebuild_take_profit_mode=rebuild_take_profit_mode,
            rebuild_take_profit_pips_head=_parse_decimal(
                raw.get("rebuild_take_profit_pips_head", "25"), "25"
            ),
            rebuild_take_profit_pips_tail=_parse_decimal(
                raw.get("rebuild_take_profit_pips_tail", "10"), "10"
            ),
            rebuild_take_profit_pips_flat_steps=_parse_int(
                raw.get("rebuild_take_profit_pips_flat_steps", 0), 0
            ),
            rebuild_take_profit_pips_gamma=_parse_decimal(
                raw.get("rebuild_take_profit_pips_gamma", "1.4"), "1.4"
            ),
            rebuild_take_profit_manual_pips=rebuild_take_profit_manual_pips,
            preserve_highest_retracement_enabled=_parse_bool(
                raw.get("preserve_highest_retracement_enabled", False), False
            ),
            preserve_highest_r_from=(
                _parse_int(raw.get("preserve_highest_r_from", 1), 1)
                if _parse_bool(raw.get("preserve_highest_retracement_enabled", False), False)
                else 0
            ),
            rebuild_enabled=_parse_bool(raw.get("rebuild_enabled", True), True),
            emergency_enabled=_parse_bool(raw.get("emergency_enabled", True), True),
            emergency_threshold=_parse_decimal(raw.get("emergency_threshold", "95"), "95"),
            pip_size=_parse_decimal(raw.get("pip_size", "0.01"), "0.01"),
            reseed_on_all_pending=_parse_bool(raw.get("reseed_on_all_pending", False), False),
            warmup_enabled=_parse_bool(raw.get("warmup_enabled", False), False),
            warmup_initial_unit_ratio_pct=_parse_decimal(
                raw.get("warmup_initial_unit_ratio_pct", "50"), "50"
            ),
            warmup_unit_ramp_steps=_parse_int(raw.get("warmup_unit_ramp_steps", 3), 3),
            warmup_start_gate_enabled=_parse_bool(raw.get("warmup_start_gate_enabled", True), True),
            warmup_gate_spread_enabled=_parse_bool(
                raw.get("warmup_gate_spread_enabled", True), True
            ),
            warmup_gate_max_spread_pips=_parse_decimal(
                raw.get("warmup_gate_max_spread_pips", "3"), "3"
            ),
            warmup_gate_volatility_enabled=_parse_bool(
                raw.get("warmup_gate_volatility_enabled", False), False
            ),
            warmup_gate_volatility_window_ticks=_parse_int(
                raw.get("warmup_gate_volatility_window_ticks", 60), 60
            ),
            warmup_gate_max_volatility_pips=_parse_decimal(
                raw.get("warmup_gate_max_volatility_pips", "80"), "80"
            ),
            warmup_gate_trend_enabled=_parse_bool(
                raw.get("warmup_gate_trend_enabled", False), False
            ),
            warmup_gate_trend_window_ticks=_parse_int(
                raw.get("warmup_gate_trend_window_ticks", 60), 60
            ),
            warmup_gate_max_trend_pips=_parse_decimal(
                raw.get("warmup_gate_max_trend_pips", "60"), "60"
            ),
            warmup_position_limit_enabled=_parse_bool(
                raw.get("warmup_position_limit_enabled", True), True
            ),
            warmup_max_positions=_parse_int(raw.get("warmup_max_positions", 4), 4),
            warmup_rebuild_limit_enabled=_parse_bool(
                raw.get("warmup_rebuild_limit_enabled", True), True
            ),
            warmup_max_rebuilds_per_tick=_parse_int(raw.get("warmup_max_rebuilds_per_tick", 0), 0),
            warmup_completion_mode=_parse_str(raw.get("warmup_completion_mode"), "duration"),
            warmup_min_elapsed_minutes=_parse_int(
                raw.get("warmup_min_elapsed_minutes", 1440), 1440
            ),
            warmup_required_tp_closes=_parse_int(raw.get("warmup_required_tp_closes", 3), 3),
        )

    @classmethod
    def strict_from_dict(cls, raw: dict[str, Any]) -> SnowballStrategyConfig:
        """Parse a persisted config without silently filling missing fields."""
        defaults = cls.from_dict({}).to_dict()
        missing = sorted(key for key in defaults if key not in raw)
        if "rebuild_entry_price_mode" in missing:
            missing.remove("rebuild_entry_price_mode")
        if "rebuild_entry_buffer_pips" in missing:
            missing.remove("rebuild_entry_buffer_pips")
        if "rebuild_cooldown_seconds" in missing:
            missing.remove("rebuild_cooldown_seconds")
        if "refill_limit_enabled" in missing:
            missing.remove("refill_limit_enabled")
        if "preserve_highest_r_from" in missing and not _parse_bool(
            raw.get("preserve_highest_retracement_enabled", False), False
        ):
            missing.remove("preserve_highest_r_from")
        for optional_key in (
            "base_units_auto_adjust_enabled",
            "base_units_balance_ratio",
            "base_units_step",
            "base_units_auto_adjust_floor_enabled",
            *WARMUP_OPTIONAL_KEYS,
        ):
            if optional_key in missing:
                missing.remove(optional_key)
        if missing:
            raise ValueError(f"Snowball config is missing required field(s): {', '.join(missing)}")

        list_fields = {
            "manual_intervals",
            "stop_loss_manual_pips",
            "rebuild_stop_loss_manual_pips",
            "rebuild_take_profit_manual_pips",
        }
        for key in list_fields:
            if not isinstance(raw[key], list):
                raise ValueError(f"Snowball config field {key} must be a list")

        return cls.from_dict(raw)

    def to_dict(self) -> dict[str, Any]:
        return {
            "base_units": self.base_units,
            "base_units_auto_adjust_enabled": self.base_units_auto_adjust_enabled,
            "base_units_balance_ratio": str(self.base_units_balance_ratio),
            "base_units_step": self.base_units_step,
            "base_units_auto_adjust_floor_enabled": self.base_units_auto_adjust_floor_enabled,
            "m_pips": str(self.m_pips),
            "trend_lot_size": self.trend_lot_size,
            "r_max": self.r_max,
            "f_max": self.f_max,
            "post_r_max_base_factor": str(self.post_r_max_base_factor),
            "refill_limit_enabled": self.refill_limit_enabled,
            "refill_up_to": self.refill_up_to,
            "n_pips_head": str(self.n_pips_head),
            "n_pips_tail": str(self.n_pips_tail),
            "n_pips_flat_steps": self.n_pips_flat_steps,
            "n_pips_gamma": str(self.n_pips_gamma),
            "interval_mode": self.interval_mode,
            "manual_intervals": [str(v) for v in self.manual_intervals],
            "stop_loss_mode": self.stop_loss_mode,
            "stop_loss_pips_head": str(self.stop_loss_pips_head),
            "stop_loss_pips_tail": str(self.stop_loss_pips_tail),
            "stop_loss_pips_flat_steps": self.stop_loss_pips_flat_steps,
            "stop_loss_pips_gamma": str(self.stop_loss_pips_gamma),
            "stop_loss_manual_pips": [str(v) for v in self.stop_loss_manual_pips],
            "counter_tp_mode": self.counter_tp_mode,
            "counter_tp_pips": str(self.counter_tp_pips),
            "counter_tp_step_amount": str(self.counter_tp_step_amount),
            "counter_tp_multiplier": str(self.counter_tp_multiplier),
            "round_step_pips": str(self.round_step_pips),
            "shrink_enabled": self.shrink_enabled,
            "m_th": str(self.m_th),
            "m1_th": str(self.m1_th),
            "stop_loss_enabled": self.stop_loss_enabled,
            "rebuild_entry_price_mode": self.rebuild_entry_price_mode,
            "rebuild_entry_buffer_pips": str(self.rebuild_entry_buffer_pips),
            "rebuild_cooldown_seconds": str(self.rebuild_cooldown_seconds),
            "rebuild_stop_loss_mode": self.rebuild_stop_loss_mode,
            "rebuild_stop_loss_manual_pips": [str(v) for v in self.rebuild_stop_loss_manual_pips],
            "rebuild_take_profit_mode": self.rebuild_take_profit_mode,
            "rebuild_take_profit_pips_head": str(self.rebuild_take_profit_pips_head),
            "rebuild_take_profit_pips_tail": str(self.rebuild_take_profit_pips_tail),
            "rebuild_take_profit_pips_flat_steps": self.rebuild_take_profit_pips_flat_steps,
            "rebuild_take_profit_pips_gamma": str(self.rebuild_take_profit_pips_gamma),
            "rebuild_take_profit_manual_pips": [
                str(v) for v in self.rebuild_take_profit_manual_pips
            ],
            "preserve_highest_retracement_enabled": self.preserve_highest_retracement_enabled,
            "preserve_highest_r_from": self.preserve_highest_r_from,
            "rebuild_enabled": self.rebuild_enabled,
            "emergency_enabled": self.emergency_enabled,
            "emergency_threshold": str(self.emergency_threshold),
            "pip_size": str(self.pip_size),
            "reseed_on_all_pending": self.reseed_on_all_pending,
            "warmup_enabled": self.warmup_enabled,
            "warmup_initial_unit_ratio_pct": str(self.warmup_initial_unit_ratio_pct),
            "warmup_unit_ramp_steps": self.warmup_unit_ramp_steps,
            "warmup_start_gate_enabled": self.warmup_start_gate_enabled,
            "warmup_gate_spread_enabled": self.warmup_gate_spread_enabled,
            "warmup_gate_max_spread_pips": str(self.warmup_gate_max_spread_pips),
            "warmup_gate_volatility_enabled": self.warmup_gate_volatility_enabled,
            "warmup_gate_volatility_window_ticks": self.warmup_gate_volatility_window_ticks,
            "warmup_gate_max_volatility_pips": str(self.warmup_gate_max_volatility_pips),
            "warmup_gate_trend_enabled": self.warmup_gate_trend_enabled,
            "warmup_gate_trend_window_ticks": self.warmup_gate_trend_window_ticks,
            "warmup_gate_max_trend_pips": str(self.warmup_gate_max_trend_pips),
            "warmup_position_limit_enabled": self.warmup_position_limit_enabled,
            "warmup_max_positions": self.warmup_max_positions,
            "warmup_rebuild_limit_enabled": self.warmup_rebuild_limit_enabled,
            "warmup_max_rebuilds_per_tick": self.warmup_max_rebuilds_per_tick,
            "warmup_completion_mode": self.warmup_completion_mode,
            "warmup_min_elapsed_minutes": self.warmup_min_elapsed_minutes,
            "warmup_required_tp_closes": self.warmup_required_tp_closes,
        }

    def validate(self) -> None:
        """Raise ``ValueError`` on invalid combinations."""
        SNOWBALL_CONFIG_VALIDATION_POLICY.validate(self)

    def _validate_constraints(self) -> None:
        """Run concrete config consistency checks."""
        if self.base_units <= 0:
            raise ValueError("base_units must be greater than 0")
        if self.base_units_balance_ratio <= 0:
            raise ValueError("base_units_balance_ratio must be greater than 0")
        if self.base_units_step <= 0:
            raise ValueError("base_units_step must be greater than 0")
        if not Decimal("0") < self.warmup_initial_unit_ratio_pct <= Decimal("100"):
            raise ValueError("warmup_initial_unit_ratio_pct must be between 0 and 100")
        if self.warmup_unit_ramp_steps <= 0:
            raise ValueError("warmup_unit_ramp_steps must be greater than 0")
        if self.warmup_gate_max_spread_pips <= 0:
            raise ValueError("warmup_gate_max_spread_pips must be greater than 0")
        if self.warmup_gate_volatility_window_ticks <= 1:
            raise ValueError("warmup_gate_volatility_window_ticks must be greater than 1")
        if self.warmup_gate_max_volatility_pips <= 0:
            raise ValueError("warmup_gate_max_volatility_pips must be greater than 0")
        if self.warmup_gate_trend_window_ticks <= 1:
            raise ValueError("warmup_gate_trend_window_ticks must be greater than 1")
        if self.warmup_gate_max_trend_pips <= 0:
            raise ValueError("warmup_gate_max_trend_pips must be greater than 0")
        if self.warmup_max_positions <= 0:
            raise ValueError("warmup_max_positions must be greater than 0")
        if self.warmup_max_rebuilds_per_tick < 0:
            raise ValueError("warmup_max_rebuilds_per_tick must be greater than or equal to 0")
        if self.warmup_completion_mode not in {
            "duration",
            "tp_closes",
            "duration_and_tp_closes",
            "duration_or_tp_closes",
        }:
            raise ValueError(
                "warmup_completion_mode must be one of 'duration', 'tp_closes', "
                "'duration_and_tp_closes', or 'duration_or_tp_closes'"
            )
        if self.warmup_min_elapsed_minutes < 0:
            raise ValueError("warmup_min_elapsed_minutes must be greater than or equal to 0")
        if self.warmup_required_tp_closes < 0:
            raise ValueError("warmup_required_tp_closes must be greater than or equal to 0")
        if self.stop_loss_enabled and self.shrink_enabled:
            raise ValueError("stop_loss_enabled and shrink_enabled cannot both be true")
        if self.preserve_highest_retracement_enabled:
            if not 1 <= self.preserve_highest_r_from <= self.r_max:
                raise ValueError(
                    f"preserve_highest_r_from must be >= 1 and <= r_max ({self.r_max})"
                )
        elif self.preserve_highest_r_from != 0:
            raise ValueError(
                "preserve_highest_r_from must be 0 when preserve_highest_retracement_enabled is false"
            )
        if self.shrink_enabled and not Decimal("0") < self.m_th < Decimal("100"):
            raise ValueError("m_th must be between 0 and 100")
        if self.shrink_enabled and not Decimal("0") < self.m1_th < self.m_th:
            raise ValueError("m1_th must be between 0 and m_th")
        if not self.n_pips_head >= self.n_pips_tail > 0:
            raise ValueError("Must satisfy n_pips_head >= n_pips_tail > 0")
        if not self.n_pips_flat_steps < self.r_max:
            raise ValueError("n_pips_flat_steps must be < r_max")
        if self.counter_tp_mode != "weighted_avg" and self.counter_tp_pips <= 0:
            raise ValueError("counter_tp_pips must be > 0")
        if self.emergency_enabled and not Decimal("0") < self.emergency_threshold <= Decimal("100"):
            raise ValueError("emergency_threshold must be between 0 (exclusive) and 100")
        if self.interval_mode == "manual":
            if len(self.manual_intervals) != self.r_max:
                raise ValueError(
                    f"manual_intervals must have exactly {self.r_max} entries for r_max={self.r_max}"
                )
            if any(v < 1 for v in self.manual_intervals):
                raise ValueError("All manual_intervals values must be >= 1")
        if self.refill_up_to < 0:
            raise ValueError("refill_up_to must be >= 0")
        if self.refill_limit_enabled and self.refill_up_to > self.r_max:
            raise ValueError(
                f"refill_up_to must be <= r_max ({self.r_max}) when refill limit is enabled"
            )
        if self.rebuild_entry_price_mode not in {"original_entry", "stop_loss_exit"}:
            raise ValueError(
                "rebuild_entry_price_mode must be either 'original_entry' or 'stop_loss_exit'"
            )
        if self.rebuild_entry_buffer_pips < 0:
            raise ValueError("rebuild_entry_buffer_pips must be greater than or equal to 0")
        if self.rebuild_cooldown_seconds < 0:
            raise ValueError("rebuild_cooldown_seconds must be greater than or equal to 0")
        # Stop-loss progression.
        if not self.stop_loss_pips_head >= self.stop_loss_pips_tail > 0:
            raise ValueError("Must satisfy stop_loss_pips_head >= stop_loss_pips_tail > 0")
        if not 0 <= self.stop_loss_pips_flat_steps < max(self.r_max, 1):
            raise ValueError("stop_loss_pips_flat_steps must be >= 0 and < r_max")
        if self.stop_loss_pips_gamma <= 0:
            raise ValueError("stop_loss_pips_gamma must be > 0")
        if self.stop_loss_mode == "manual":
            # R0 uses k=1 and R(r_max) uses k=r_max+1 in the SL formula,
            # so the manual list needs one slot more than the interval
            # list.  A shorter list is permitted because the progression
            # clamps to the last value, but we forbid shorter-than-r_max
            # to catch accidental misconfiguration.
            if len(self.stop_loss_manual_pips) < self.r_max:
                raise ValueError(
                    "stop_loss_manual_pips must have at least r_max entries "
                    f"(got {len(self.stop_loss_manual_pips)}, need {self.r_max})"
                )
            if any(v <= 0 for v in self.stop_loss_manual_pips):
                raise ValueError("All stop_loss_manual_pips values must be > 0")
        if self.rebuild_stop_loss_mode not in {"same", "same_pips", "manual"}:
            raise ValueError(
                "rebuild_stop_loss_mode must be either 'same', 'same_pips', or 'manual'"
            )
        if self.rebuild_stop_loss_mode == "manual":
            if len(self.rebuild_stop_loss_manual_pips) < self.r_max + 1:
                raise ValueError(
                    "rebuild_stop_loss_manual_pips must have at least r_max + 1 entries "
                    f"(got {len(self.rebuild_stop_loss_manual_pips)}, need {self.r_max + 1})"
                )
            if any(v <= 0 for v in self.rebuild_stop_loss_manual_pips):
                raise ValueError("All rebuild_stop_loss_manual_pips values must be > 0")
        if self.rebuild_take_profit_mode not in {
            "same",
            "same_pips",
            "constant",
            "additive",
            "subtractive",
            "multiplicative",
            "divisive",
            "manual",
        }:
            raise ValueError(
                "rebuild_take_profit_mode must be one of 'same', 'same_pips', "
                "'constant', 'additive', 'subtractive', 'multiplicative', 'divisive', "
                "or 'manual'"
            )
        if not self.rebuild_take_profit_pips_head >= self.rebuild_take_profit_pips_tail > 0:
            raise ValueError(
                "Must satisfy rebuild_take_profit_pips_head >= rebuild_take_profit_pips_tail > 0"
            )
        if not 0 <= self.rebuild_take_profit_pips_flat_steps < max(self.r_max, 1):
            raise ValueError("rebuild_take_profit_pips_flat_steps must be >= 0 and < r_max")
        if self.rebuild_take_profit_pips_gamma <= 0:
            raise ValueError("rebuild_take_profit_pips_gamma must be > 0")
        if self.rebuild_take_profit_mode == "manual":
            if len(self.rebuild_take_profit_manual_pips) < self.r_max + 1:
                raise ValueError(
                    "rebuild_take_profit_manual_pips must have at least r_max + 1 entries "
                    f"(got {len(self.rebuild_take_profit_manual_pips)}, need {self.r_max + 1})"
                )
            if any(v <= 0 for v in self.rebuild_take_profit_manual_pips):
                raise ValueError("All rebuild_take_profit_manual_pips values must be > 0")
        if not self.stop_loss_enabled and not self.rebuild_enabled:
            raise ValueError("rebuild_enabled=false requires stop_loss_enabled to be true")


@dataclass(frozen=True, slots=True)
class SnowballConfigValidationPolicy:
    """Own public Snowball configuration validation orchestration."""

    def validate(self, config: SnowballStrategyConfig) -> None:
        """Validate one normalized Snowball config object."""
        config._validate_constraints()


SNOWBALL_CONFIG_VALIDATION_POLICY = SnowballConfigValidationPolicy()


def _optional_decimal(value: Any | None) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
