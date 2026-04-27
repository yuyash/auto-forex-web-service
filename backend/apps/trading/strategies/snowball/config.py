"""Configuration model for the Snowball strategy."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from apps.trading.strategies.snowball.parsing import (
    _parse_bool,
    _parse_decimal,
    _parse_int,
    _parse_str,
)


@dataclass(frozen=True, slots=True)
class SnowballStrategyConfig:
    """Normalised Snowball strategy configuration."""

    # Core
    base_units: int
    m_pips: Decimal
    trend_lot_size: int
    r_max: int
    f_max: int
    post_r_max_base_factor: Decimal
    refill_up_to: int  # R1..R(refill_up_to) refillable after close; 0 = none

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
    lock_enabled: bool
    n_th: Decimal
    cooldown_sec: int
    stop_loss_enabled: bool
    disable_loss_cut_after_rebuild: bool
    rebuild_stop_loss_mode: str
    rebuild_stop_loss_manual_pips: list[Decimal]
    rebuild_take_profit_mode: str
    rebuild_take_profit_pips_head: Decimal
    rebuild_take_profit_pips_tail: Decimal
    rebuild_take_profit_pips_flat_steps: int
    rebuild_take_profit_pips_gamma: Decimal
    rebuild_take_profit_manual_pips: list[Decimal]
    grid_order_validation_enabled: bool
    preserve_highest_retracement_enabled: bool
    preserve_highest_r_from: int
    # When ``stop_loss_enabled`` is True, controls whether a stopped-out
    # slot is rebuilt (re-opened) once price returns to the original
    # entry.  Historical behaviour is ``True`` — stop-losses always
    # create a pending_rebuild snapshot and the slot comes back when
    # price revisits.  Setting this to ``False`` makes a stop-loss close
    # the slot permanently (no pending_rebuild snapshot is retained),
    # so the grid shrinks on each SL instead of recovering.
    rebuild_enabled: bool
    # When True, a cycle that loses its last live entry is immediately
    # moved to COMPLETED so the re-seed logic can start a fresh cycle
    # on the next tick.  Intended for the ``stop_loss_enabled=True,
    # rebuild_enabled=False`` combination, where pending_rebuild
    # snapshots do not exist and the only way for a cycle to hold state
    # is as COMPLETED (already the default in that combination, but
    # this flag keeps the semantics explicit at the config layer).
    complete_cycle_when_empty: bool
    emergency_enabled: bool
    emergency_threshold: Decimal

    pip_size: Decimal

    # Cycle re-seed: create a new cycle when all positions in a direction
    # are pending stop-loss rebuild (no open positions).
    # - reseed_on_all_pending: triggers as soon as every cycle for the
    #   direction has zero live entries (some slots may still be empty).
    # - reseed_on_grid_exhausted: triggers only when every slot in every
    #   layer is in pending-rebuild state (the grid is fully saturated
    #   with stop-loss closures).
    # At most one of these may be True.
    reseed_on_all_pending: bool
    reseed_on_grid_exhausted: bool

    # Rebuild price adjustment: when a stop-loss fires and the position
    # is later rebuilt, the rebuilt position inherits the original TP.
    # When ``rebuild_price_adjustment_enabled`` is true, two optional
    # buffers (in pips) can shift the rebuild trigger/TP slightly in the
    # favourable direction while grid-ordering constraints remain
    # enforced:
    # - ``rebuild_entry_price_buffer_pips``: shifts the rebuild trigger
    #   price in the favourable direction (requires a slightly better
    #   entry than the original).
    # - ``rebuild_exit_price_buffer_pips``: shifts the inherited rebuild
    #   TP in the favourable direction.
    rebuild_price_adjustment_enabled: bool
    rebuild_entry_price_buffer_pips: Decimal
    rebuild_exit_price_buffer_pips: Decimal

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
        rebuild_take_profit_mode = _parse_str(raw.get("rebuild_take_profit_mode"), "same")
        rebuild_price_adjustment_enabled = _parse_bool(
            raw.get("rebuild_price_adjustment_enabled", True), True
        )
        if rebuild_take_profit_mode != "same":
            rebuild_price_adjustment_enabled = False
        grid_order_validation_enabled = _parse_bool(
            raw.get("grid_order_validation_enabled", True), True
        )
        if rebuild_take_profit_mode == "manual":
            grid_order_validation_enabled = False

        return SnowballStrategyConfig(
            base_units=_parse_int(raw.get("base_units", 1000), 1000),
            m_pips=_parse_decimal(raw.get("m_pips", "50"), "50"),
            trend_lot_size=_parse_int(raw.get("trend_lot_size", 1), 1),
            r_max=_parse_int(raw.get("r_max", 7), 7),
            f_max=_parse_int(raw.get("f_max", 3), 3),
            post_r_max_base_factor=_parse_decimal(raw.get("post_r_max_base_factor", "1"), "1"),
            refill_up_to=_parse_int(raw.get("refill_up_to", 2), 2),
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
            lock_enabled=_parse_bool(raw.get("lock_enabled", False), False),
            n_th=_parse_decimal(raw.get("n_th", "85"), "85"),
            cooldown_sec=_parse_int(raw.get("cooldown_sec", 300), 300),
            stop_loss_enabled=_parse_bool(raw.get("stop_loss_enabled", False), False),
            disable_loss_cut_after_rebuild=_parse_bool(
                raw.get("disable_loss_cut_after_rebuild", False), False
            ),
            rebuild_stop_loss_mode=_parse_str(raw.get("rebuild_stop_loss_mode"), "same"),
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
            grid_order_validation_enabled=grid_order_validation_enabled,
            preserve_highest_retracement_enabled=_parse_bool(
                raw.get("preserve_highest_retracement_enabled", False), False
            ),
            preserve_highest_r_from=(
                _parse_int(raw.get("preserve_highest_r_from", 1), 1)
                if _parse_bool(raw.get("preserve_highest_retracement_enabled", False), False)
                else 0
            ),
            rebuild_enabled=_parse_bool(raw.get("rebuild_enabled", True), True),
            complete_cycle_when_empty=_parse_bool(
                raw.get("complete_cycle_when_empty", False), False
            ),
            emergency_enabled=_parse_bool(raw.get("emergency_enabled", True), True),
            emergency_threshold=_parse_decimal(raw.get("emergency_threshold", "95"), "95"),
            pip_size=_parse_decimal(raw.get("pip_size", "0.01"), "0.01"),
            reseed_on_all_pending=_parse_bool(raw.get("reseed_on_all_pending", False), False),
            reseed_on_grid_exhausted=_parse_bool(raw.get("reseed_on_grid_exhausted", False), False),
            rebuild_price_adjustment_enabled=rebuild_price_adjustment_enabled,
            rebuild_entry_price_buffer_pips=_parse_decimal(
                raw.get("rebuild_entry_price_buffer_pips", "0"), "0"
            ),
            rebuild_exit_price_buffer_pips=_parse_decimal(
                raw.get("rebuild_exit_price_buffer_pips", "0"), "0"
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "base_units": self.base_units,
            "m_pips": str(self.m_pips),
            "trend_lot_size": self.trend_lot_size,
            "r_max": self.r_max,
            "f_max": self.f_max,
            "post_r_max_base_factor": str(self.post_r_max_base_factor),
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
            "lock_enabled": self.lock_enabled,
            "n_th": str(self.n_th),
            "cooldown_sec": self.cooldown_sec,
            "stop_loss_enabled": self.stop_loss_enabled,
            "disable_loss_cut_after_rebuild": self.disable_loss_cut_after_rebuild,
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
            "grid_order_validation_enabled": self.grid_order_validation_enabled,
            "preserve_highest_retracement_enabled": self.preserve_highest_retracement_enabled,
            "preserve_highest_r_from": self.preserve_highest_r_from,
            "rebuild_enabled": self.rebuild_enabled,
            "complete_cycle_when_empty": self.complete_cycle_when_empty,
            "emergency_enabled": self.emergency_enabled,
            "emergency_threshold": str(self.emergency_threshold),
            "pip_size": str(self.pip_size),
            "reseed_on_all_pending": self.reseed_on_all_pending,
            "reseed_on_grid_exhausted": self.reseed_on_grid_exhausted,
            "rebuild_price_adjustment_enabled": self.rebuild_price_adjustment_enabled,
            "rebuild_entry_price_buffer_pips": str(self.rebuild_entry_price_buffer_pips),
            "rebuild_exit_price_buffer_pips": str(self.rebuild_exit_price_buffer_pips),
        }

    def validate(self) -> None:
        """Raise ``ValueError`` on invalid combinations."""
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
        if self.shrink_enabled and self.lock_enabled and not self.m_th < self.n_th < Decimal("100"):
            raise ValueError("Must satisfy m_th < n_th < 100")
        if self.shrink_enabled and not Decimal("0") < self.m_th < Decimal("100"):
            raise ValueError("m_th must be between 0 and 100")
        if self.shrink_enabled and not Decimal("0") < self.m1_th < self.m_th:
            raise ValueError("m1_th must be between 0 and m_th")
        if self.lock_enabled and not Decimal("0") < self.n_th < Decimal("100"):
            raise ValueError("n_th must be between 0 and 100")
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
        if not 0 <= self.refill_up_to < self.r_max:
            raise ValueError(f"refill_up_to must be >= 0 and < r_max ({self.r_max})")
        if self.reseed_on_all_pending and self.reseed_on_grid_exhausted:
            raise ValueError(
                "reseed_on_all_pending and reseed_on_grid_exhausted cannot both be true"
            )
        if self.rebuild_entry_price_buffer_pips < 0:
            raise ValueError("rebuild_entry_price_buffer_pips must be >= 0")
        if self.rebuild_exit_price_buffer_pips < 0:
            raise ValueError("rebuild_exit_price_buffer_pips must be >= 0")
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
        if self.rebuild_stop_loss_mode not in {"same", "manual"}:
            raise ValueError("rebuild_stop_loss_mode must be either 'same' or 'manual'")
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
            "constant",
            "additive",
            "subtractive",
            "multiplicative",
            "divisive",
            "manual",
        }:
            raise ValueError(
                "rebuild_take_profit_mode must be one of 'same', 'constant', "
                "'additive', 'subtractive', 'multiplicative', 'divisive', or 'manual'"
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
        if self.rebuild_take_profit_mode != "same" and self.rebuild_price_adjustment_enabled:
            raise ValueError(
                "rebuild_price_adjustment_enabled must be false when "
                "rebuild_take_profit_mode is not 'same'"
            )
        if self.rebuild_take_profit_mode == "manual" and self.grid_order_validation_enabled:
            raise ValueError(
                "grid_order_validation_enabled must be false when "
                "rebuild_take_profit_mode is 'manual'"
            )
        # rebuild_enabled is only meaningful when stop_loss is on.  We
        # silently ignore the flag when SL is off — it simply does not
        # apply.  complete_cycle_when_empty likewise only does anything
        # when rebuilds are disabled.
        if self.complete_cycle_when_empty and not self.stop_loss_enabled:
            raise ValueError("complete_cycle_when_empty requires stop_loss_enabled to be true")
        if self.complete_cycle_when_empty and self.rebuild_enabled:
            raise ValueError("complete_cycle_when_empty requires rebuild_enabled to be false")
