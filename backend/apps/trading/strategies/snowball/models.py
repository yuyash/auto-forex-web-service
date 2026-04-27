"""Data models for Snowball strategy.

Hierarchy: StrategyState → Cycle → PositionGrid → Entry.

Design principles
-----------------
- **Unified grid**: Every position (including the cycle's first entry at L0/R0)
  lives in the same ``PositionGrid``.  There is no special ``initial_entry``
  field — the grid is the single source of truth.
- **Dynamic cycle head**: The cycle head (whose TP closes the cycle) is always
  the *oldest surviving position* in the grid, determined at query time.
- **Bidirectional close**: Normal TP closes from the back (newest → oldest).
  Shrink protection closes from the front (oldest → newest).
- **1-indexed addressing**: Layers are ``L1 … Lf`` (f_max layers total).
  Retracements within a layer are ``R0 … Rr`` (r_max + 1 slots per layer,
  where R0 is the layer-initial position).

Slot lifecycle
--------------
A slot transitions through: ``empty → occupied → closed``.
- ``closed`` with ``refillable=True`` → returns to ``empty`` (can be reused).
- ``closed`` with ``refillable=False`` → becomes ``sealed`` (blocks further
  filling in this layer, triggering a new layer).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any, Literal

from apps.trading.enums import Direction
from apps.trading.strategies.snowball.enums import CycleStatus, ProtectionLevel

if TYPE_CHECKING:
    from apps.trading.dataclasses.tick import Tick
    from apps.trading.events import (
        ClosePositionEvent,
        OpenPositionEvent,
        RebuildPositionEvent,
        StrategyEvent,
    )


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


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

        # Legacy Snowball stop-loss behaviour was derived from the next
        # counter interval and the slot TP, not from a dedicated flat
        # pip-distance progression.  Keep that behaviour as the default
        # ``auto`` mode when upgrading older configs that have no
        # explicit ``stop_loss_*`` fields.  Users opt into true fixed or
        # progressive pip-distance SLs via the dedicated stop-loss
        # fields below.
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


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------


@dataclass
class Entry:
    """A single position entry within a cycle.

    Every entry lives in a ``Slot`` inside the ``PositionGrid``.  The entry
    knows its own grid coordinates (``layer``, ``index``) and its ``role``
    which is purely descriptive — it does *not* affect close ordering.
    """

    entry_id: int
    step: int
    direction: Direction
    entry_price: Decimal
    close_price: Decimal
    units: int
    opened_at: datetime
    role: Literal["initial", "counter", "hedge", "layer_initial"]
    layer_number: int = 1
    retracement_count: int = 0
    root_entry_id: int | None = None
    parent_entry_id: int | None = None
    position_id: str | None = None
    stop_loss_price: Decimal | None = None
    is_rebuild: bool = False

    # Validation fields
    expected_interval_pips: Decimal | None = None
    actual_interval_pips: Decimal | None = None
    expected_tp_pips: Decimal | None = None
    validation_status: str = ""

    # Lifecycle P/L tracked across the full open → (optional stop-loss →
    # rebuild)+ → close chain of this grid slot.  Carried through rebuilds
    # via ``StopLossClosedEntry``.  Denominated in account currency.
    lifecycle_realized_pnl: Decimal = field(default_factory=lambda: Decimal("0"))
    lifecycle_stop_loss_count: int = 0

    @classmethod
    def open(
        cls,
        *,
        state: "SnowballStrategyState",
        tick: "Tick",
        direction: Direction,
        units: int,
        step: int,
        close_price: Decimal,
        role: Literal["initial", "counter", "hedge", "layer_initial"],
        layer_number: int = 1,
        retracement_count: int = 0,
        root_entry_id: int | None = None,
        parent_entry_id: int | None = None,
    ) -> "Entry":
        eid = state.allocate_id()
        price = tick.ask if direction == Direction.LONG else tick.bid
        if root_entry_id is None and role == "initial":
            root_entry_id = eid
        return cls(
            entry_id=eid,
            step=step,
            direction=direction,
            entry_price=price,
            close_price=close_price,
            units=units,
            opened_at=tick.timestamp,
            role=role,
            layer_number=layer_number,
            retracement_count=retracement_count,
            root_entry_id=root_entry_id,
            parent_entry_id=parent_entry_id,
        )

    # -- Convenience properties --

    @property
    def is_long(self) -> bool:
        return self.direction == Direction.LONG

    @property
    def is_short(self) -> bool:
        return self.direction == Direction.SHORT

    @property
    def is_initial(self) -> bool:
        return self.role == "initial"

    @property
    def is_layer_initial(self) -> bool:
        return self.role == "layer_initial"

    @property
    def is_counter(self) -> bool:
        return self.role == "counter"

    @property
    def is_hedge(self) -> bool:
        return self.role == "hedge"

    def exit_price(self, tick: "Tick") -> Decimal:
        return tick.bid if self.is_long else tick.ask

    def unrealised_loss_pips(self, mid_price: Decimal, pip_size: Decimal) -> Decimal:
        """Positive = losing."""
        if self.is_long:
            return (self.entry_price - mid_price) / pip_size
        return (mid_price - self.entry_price) / pip_size

    # -- Grid coordinate --

    @property
    def grid_key(self) -> tuple[int, int]:
        """(layer_number, retracement_count) — used for ordering."""
        return (self.layer_number, self.retracement_count)

    # -- Event generation --

    def apply_metadata_to(
        self,
        event: "StrategyEvent",
        *,
        close_reason: str = "",
        actual_tp_pips: Decimal | None = None,
        actual_exit_price: Decimal | None = None,
    ) -> None:
        event.strategy_type = "snowball"
        event.basket = self.role
        event.root_entry_id = self.root_entry_id
        event.parent_entry_id = self.parent_entry_id
        event.visual_group_id = str(self.root_entry_id) if self.root_entry_id is not None else ""
        event.step = self.step
        event.close_reason = close_reason
        event.validation_status = self.validation_status
        event.expected_interval_pips = self.expected_interval_pips
        event.actual_interval_pips = self.actual_interval_pips
        event.expected_tp_pips = self.expected_tp_pips
        event.actual_tp_pips = actual_tp_pips
        event.expected_exit_price = self.close_price
        event.actual_exit_price = actual_exit_price

    def to_open_event(
        self,
        *,
        timestamp: datetime,
        planned_exit_price_formula: str | None = None,
        description: str = "",
    ) -> "OpenPositionEvent":
        from apps.trading.enums import EventType
        from apps.trading.events import OpenPositionEvent

        event = OpenPositionEvent(
            event_type=EventType.OPEN_POSITION,
            timestamp=timestamp,
            layer_number=self.layer_number,
            direction=self.direction.value,
            price=self.entry_price,
            units=self.units,
            entry_id=self.entry_id,
            retracement_count=self.retracement_count,
            strategy_event_type=f"snowball_{self.role}",
            planned_exit_price=self.close_price,
            planned_exit_price_formula=planned_exit_price_formula,
            stop_loss_price=self.stop_loss_price,
            description=description,
        )
        self.apply_metadata_to(event)
        return event

    def to_rebuild_event(
        self,
        *,
        timestamp: datetime,
        original_position_id: str | None = None,
        description: str = "",
    ) -> "RebuildPositionEvent":
        from apps.trading.enums import EventType
        from apps.trading.events import RebuildPositionEvent

        event = RebuildPositionEvent(
            event_type=EventType.REBUILD_POSITION,
            timestamp=timestamp,
            layer_number=self.layer_number,
            direction=self.direction.value,
            price=self.entry_price,
            units=self.units,
            entry_id=self.entry_id,
            retracement_count=self.retracement_count,
            strategy_event_type=f"snowball_{self.role}",
            planned_exit_price=self.close_price,
            stop_loss_price=self.stop_loss_price,
            description=description,
            original_position_id=original_position_id,
        )
        self.apply_metadata_to(event)
        return event

    def to_close_event(
        self,
        tick: "Tick",
        *,
        instrument: str,
        pip_size: Decimal,
        account_currency: str,
        description: str = "",
        close_reason: str = "",
        actual_tp_pips: Decimal | None = None,
        validation_status: str = "",
    ) -> "ClosePositionEvent":
        from apps.trading.enums import EventType
        from apps.trading.events import ClosePositionEvent
        from apps.trading.utils import quote_to_account_rate

        exit_px = self.exit_price(tick)
        conv = quote_to_account_rate(instrument, tick.mid, account_currency)
        pnl = (exit_px - self.entry_price) * Decimal(str(self.units)) * conv
        if self.is_short:
            pnl = -pnl

        event = ClosePositionEvent(
            event_type=EventType.CLOSE_POSITION,
            timestamp=tick.timestamp,
            layer_number=self.layer_number,
            direction=self.direction.value,
            entry_price=self.entry_price,
            exit_price=exit_px,
            units=self.units,
            pnl=pnl,
            pips=abs(exit_px - self.entry_price) / pip_size,
            entry_id=self.entry_id,
            position_id=self.position_id,
            retracement_count=self.retracement_count,
            description=description,
        )
        orig_vs = self.validation_status
        if validation_status:
            self.validation_status = validation_status
        self.apply_metadata_to(
            event,
            close_reason=close_reason,
            actual_tp_pips=actual_tp_pips,
            actual_exit_price=exit_px,
        )
        self.validation_status = orig_vs
        return event

    # -- Serialisation --

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "step": self.step,
            "direction": self.direction.value,
            "entry_price": str(self.entry_price),
            "close_price": str(self.close_price),
            "units": self.units,
            "opened_at": self.opened_at.isoformat(),
            "role": self.role,
            "layer_number": self.layer_number,
            "retracement_count": self.retracement_count,
            "root_entry_id": self.root_entry_id,
            "parent_entry_id": self.parent_entry_id,
            "position_id": self.position_id,
            "expected_interval_pips": (
                str(self.expected_interval_pips)
                if self.expected_interval_pips is not None
                else None
            ),
            "actual_interval_pips": (
                str(self.actual_interval_pips) if self.actual_interval_pips is not None else None
            ),
            "expected_tp_pips": (
                str(self.expected_tp_pips) if self.expected_tp_pips is not None else None
            ),
            "validation_status": self.validation_status,
            "stop_loss_price": (
                str(self.stop_loss_price) if self.stop_loss_price is not None else None
            ),
            "is_rebuild": self.is_rebuild,
            "lifecycle_realized_pnl": str(self.lifecycle_realized_pnl),
            "lifecycle_stop_loss_count": self.lifecycle_stop_loss_count,
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "Entry":
        raw_direction = d.get("direction", "long")
        direction = (
            raw_direction
            if isinstance(raw_direction, Direction)
            else Direction(str(raw_direction).strip().lower())
        )
        raw_opened = d.get("opened_at", "")
        if isinstance(raw_opened, datetime):
            opened_at = raw_opened
        else:
            opened_str = str(raw_opened).strip()
            if not opened_str:
                from datetime import UTC

                opened_at = datetime(2000, 1, 1, tzinfo=UTC)
            else:
                if opened_str.endswith("Z"):
                    opened_str = opened_str[:-1] + "+00:00"
                opened_at = datetime.fromisoformat(opened_str)

        return Entry(
            entry_id=_parse_int(d.get("entry_id", 0), 0),
            step=_parse_int(d.get("step", 1), 1),
            direction=direction,
            entry_price=_parse_decimal(d.get("entry_price", "0"), "0"),
            close_price=_parse_decimal(d.get("close_price", "0"), "0"),
            units=_parse_int(d.get("units", 0), 0),
            opened_at=opened_at,
            role=d.get("role", "counter"),
            layer_number=_parse_int(d.get("layer_number", 1), 1),
            retracement_count=_parse_int(d.get("retracement_count", 0), 0),
            root_entry_id=(
                _parse_int(d["root_entry_id"], 0) if d.get("root_entry_id") is not None else None
            ),
            parent_entry_id=(
                _parse_int(d["parent_entry_id"], 0)
                if d.get("parent_entry_id") is not None
                else None
            ),
            position_id=d.get("position_id"),
            expected_interval_pips=(
                _parse_decimal(d["expected_interval_pips"], "0")
                if d.get("expected_interval_pips") not in (None, "")
                else None
            ),
            actual_interval_pips=(
                _parse_decimal(d["actual_interval_pips"], "0")
                if d.get("actual_interval_pips") not in (None, "")
                else None
            ),
            expected_tp_pips=(
                _parse_decimal(d["expected_tp_pips"], "0")
                if d.get("expected_tp_pips") not in (None, "")
                else None
            ),
            validation_status=str(d.get("validation_status", "")),
            stop_loss_price=(
                _parse_decimal(d["stop_loss_price"], "0")
                if d.get("stop_loss_price") not in (None, "")
                else None
            ),
            is_rebuild=bool(d.get("is_rebuild", False)),
            lifecycle_realized_pnl=_parse_decimal(d.get("lifecycle_realized_pnl", "0"), "0"),
            lifecycle_stop_loss_count=_parse_int(d.get("lifecycle_stop_loss_count", 0), 0),
        )


# Backward-compat alias
BasketEntry = Entry


# ---------------------------------------------------------------------------
# StopLossClosedEntry — tracks positions closed by stop-loss for rebuild
# ---------------------------------------------------------------------------


@dataclass
class StopLossClosedEntry:
    """Snapshot of a position closed by stop-loss, awaiting rebuild.

    When the market price returns to ``entry_price``, the position is
    re-opened with the same parameters.
    """

    entry_price: Decimal
    close_price: Decimal
    units: int
    direction: Direction
    role: Literal["initial", "counter", "hedge", "layer_initial"]
    layer_number: int
    retracement_count: int
    step: int
    root_entry_id: int | None = None
    parent_entry_id: int | None = None
    cycle_id: int = 0
    position_id: str | None = None
    stop_loss_price: Decimal | None = None

    # Running lifecycle P/L for the slot: accumulates every stop-loss
    # loss so the rebuilt entry can continue the chain and the final
    # close can compare net P/L against zero.  Denominated in account
    # currency.
    lifecycle_realized_pnl: Decimal = field(default_factory=lambda: Decimal("0"))
    lifecycle_stop_loss_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        result = {
            "entry_price": str(self.entry_price),
            "close_price": str(self.close_price),
            "units": self.units,
            "direction": self.direction.value,
            "role": self.role,
            "layer_number": self.layer_number,
            "retracement_count": self.retracement_count,
            "step": self.step,
            "root_entry_id": self.root_entry_id,
            "parent_entry_id": self.parent_entry_id,
            "cycle_id": self.cycle_id,
            "lifecycle_realized_pnl": str(self.lifecycle_realized_pnl),
            "lifecycle_stop_loss_count": self.lifecycle_stop_loss_count,
        }
        if self.position_id is not None:
            result["position_id"] = self.position_id
        if self.stop_loss_price is not None:
            result["stop_loss_price"] = str(self.stop_loss_price)
        return result

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "StopLossClosedEntry":
        raw_dir = d.get("direction", "long")
        direction = (
            raw_dir if isinstance(raw_dir, Direction) else Direction(str(raw_dir).strip().lower())
        )
        return StopLossClosedEntry(
            entry_price=_parse_decimal(d.get("entry_price", "0"), "0"),
            close_price=_parse_decimal(d.get("close_price", "0"), "0"),
            units=_parse_int(d.get("units", 0), 0),
            direction=direction,
            role=d.get("role", "counter"),
            layer_number=_parse_int(d.get("layer_number", 1), 1),
            retracement_count=_parse_int(d.get("retracement_count", 0), 0),
            step=_parse_int(d.get("step", 1), 1),
            root_entry_id=(
                _parse_int(d["root_entry_id"], 0) if d.get("root_entry_id") is not None else None
            ),
            parent_entry_id=(
                _parse_int(d["parent_entry_id"], 0)
                if d.get("parent_entry_id") is not None
                else None
            ),
            cycle_id=_parse_int(d.get("cycle_id", 0), 0),
            position_id=d.get("position_id"),
            stop_loss_price=(
                _parse_decimal(d.get("stop_loss_price", "0"), "0")
                if d.get("stop_loss_price") is not None
                else None
            ),
            lifecycle_realized_pnl=_parse_decimal(d.get("lifecycle_realized_pnl", "0"), "0"),
            lifecycle_stop_loss_count=_parse_int(d.get("lifecycle_stop_loss_count", 0), 0),
        )


# ---------------------------------------------------------------------------
# Slot
# ---------------------------------------------------------------------------


@dataclass
class Slot:
    """A numbered seat inside a layer.

    Addressing: ``(layer_number, index)`` where ``index`` is 0-based.
    R0 is the layer-initial position (or the cycle-initial for L0).
    R1…R(r_max) are counter-trend retracement positions.

    States:
    - empty + not ever_closed → available for a new entry
    - occupied → holds an open entry
    - pending_rebuild → entry was closed by stop-loss, awaiting rebuild.
      The slot is logically "present" (blocks counter adds and new layers)
      but has no live entry.
    - empty + ever_closed → sealed; triggers new layer on next adverse move
    """

    index: int  # 0-based (R0=0, R1=1, …)
    entry: Entry | None = None
    ever_closed: bool = False
    pending_rebuild: StopLossClosedEntry | None = None

    @property
    def is_occupied(self) -> bool:
        """True if a live entry is present."""
        return self.entry is not None

    @property
    def is_present(self) -> bool:
        """True if the slot holds a live entry OR is awaiting SL rebuild.

        Use this instead of ``is_occupied`` when you need to treat
        stop-loss-closed positions as still "there" (e.g. for counter-add
        distance calculations and layer-progression checks).
        """
        return self.entry is not None or self.pending_rebuild is not None

    @property
    def is_empty(self) -> bool:
        return self.entry is None

    @property
    def is_pending_rebuild(self) -> bool:
        """True if the slot is awaiting stop-loss rebuild."""
        return self.pending_rebuild is not None

    @property
    def is_available(self) -> bool:
        """True if this slot can accept a new entry.

        A slot with a pending rebuild is NOT available — it is reserved
        for the rebuild.
        """
        return self.entry is None and not self.ever_closed and self.pending_rebuild is None

    def fill(self, entry: Entry) -> None:
        self.entry = entry

    def close(self, *, refillable: bool) -> Entry | None:
        e = self.entry
        self.entry = None
        if not refillable:
            self.ever_closed = True
        return e

    def close_for_stop_loss(self, sl_snapshot: "StopLossClosedEntry") -> Entry | None:
        """Close the entry due to stop-loss and mark the slot for rebuild.

        The slot transitions to ``pending_rebuild`` state: no live entry,
        but logically present in the grid.
        """
        e = self.entry
        self.entry = None
        self.pending_rebuild = sl_snapshot
        # ever_closed stays False — the slot is reserved for rebuild
        return e

    def complete_rebuild(self, entry: Entry) -> None:
        """Fill the slot with a rebuilt entry, clearing the pending state."""
        self.entry = entry
        self.pending_rebuild = None
        self.ever_closed = False

    def reset(self) -> None:
        self.entry = None
        self.ever_closed = False
        self.pending_rebuild = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "index": self.index,
            "entry": self.entry.to_dict() if self.entry else None,
            "ever_closed": self.ever_closed,
        }
        if self.pending_rebuild is not None:
            d["pending_rebuild"] = self.pending_rebuild.to_dict()
        return d

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "Slot":
        raw_entry = d.get("entry")
        raw_pending = d.get("pending_rebuild")
        return Slot(
            index=_parse_int(d.get("index", 0), 0),
            entry=Entry.from_dict(raw_entry) if raw_entry else None,
            ever_closed=bool(d.get("ever_closed", False)),
            pending_rebuild=(StopLossClosedEntry.from_dict(raw_pending) if raw_pending else None),
        )


# ---------------------------------------------------------------------------
# Layer
# ---------------------------------------------------------------------------


@dataclass
class Layer:
    """A layer of ``r_max + 1`` slots (R0 … R(r_max)).

    R0 is the layer-initial (or cycle-initial for L1).
    R1…R(r_max) are counter-trend retracement slots.
    """

    layer_number: int  # 1-based
    slots: list[Slot] = field(default_factory=list)
    base_units: int = 1000
    refill_up_to: int = 2

    # -- Slot queries --

    def occupied_slots(self) -> list[Slot]:
        return [s for s in self.slots if s.is_occupied]

    def present_slots(self) -> list[Slot]:
        """Return slots that are occupied OR awaiting SL rebuild."""
        return [s for s in self.slots if s.is_present]

    def highest_occupied_slot(self) -> Slot | None:
        occupied = self.occupied_slots()
        return max(occupied, key=lambda s: s.index) if occupied else None

    def highest_present_slot(self) -> Slot | None:
        """Highest slot that is occupied or pending rebuild."""
        present = self.present_slots()
        return max(present, key=lambda s: s.index) if present else None

    def previous_present_slot(self, index: int) -> Slot | None:
        """Highest present slot with index lower than ``index``."""
        present = [s for s in self.present_slots() if s.index < index]
        return max(present, key=lambda s: s.index) if present else None

    def lowest_occupied_slot(self) -> Slot | None:
        occupied = self.occupied_slots()
        return min(occupied, key=lambda s: s.index) if occupied else None

    def slot_at(self, index: int) -> Slot | None:
        """Return the slot at *index* (0-based), or None."""
        for s in self.slots:
            if s.index == index:
                return s
        return None

    def next_available_counter_slot(self) -> Slot | None:
        """Return the next available slot with index >= 1 (counter slots).

        Walks counter slots in order.  Returns None if a sealed or
        pending-rebuild slot is encountered before an available one,
        or all are occupied.
        """
        highest_present = self.highest_present_slot()
        for s in self.slots:
            if s.index == 0:
                continue  # skip R0 (layer-initial)
            if s.is_available:
                # Do not refill a lower slot while any higher-numbered slot
                # is still logically present; that would invert the in-layer
                # entry/TP ordering (for example reopening R3 while R4 remains
                # open or pending rebuild).
                if highest_present is not None and highest_present.index > s.index:
                    return None
                return s
            if s.is_pending_rebuild:
                # Slot is reserved for SL rebuild — skip but keep looking
                # for higher-numbered available slots.
                continue
            if s.is_empty and s.ever_closed:
                return None  # sealed → new layer needed
        return None

    @property
    def needs_new_layer(self) -> bool:
        """True if counter slots cannot accept more entries."""
        return self.next_available_counter_slot() is None

    def has_open_entries(self) -> bool:
        """True if any slot has a live entry."""
        return any(s.is_occupied for s in self.slots)

    def has_present_entries(self) -> bool:
        """True if any slot is occupied or pending rebuild."""
        return any(s.is_present for s in self.slots)

    def all_entries(self) -> list[Entry]:
        return [s.entry for s in self.slots if s.entry is not None]

    # -- Close operations --

    def close_slot(self, slot_index: int, *, refillable: bool | None = None) -> Entry | None:
        """Close the entry in the slot at *slot_index*.

        If *refillable* is None, auto-determine from ``refill_up_to``:
        counter slots (index >= 1) with index <= refill_up_to are refillable.
        R0 is never auto-refillable (it's the layer-initial).
        """
        for s in self.slots:
            if s.index == slot_index and s.is_occupied:
                if refillable is None:
                    refillable = s.index >= 1 and s.index <= self.refill_up_to
                return s.close(refillable=refillable)
        return None

    def unseal_slots_above(self, index: int) -> None:
        """Reset ``ever_closed`` on slots above *index*.

        When a refillable slot is re-opened, any higher-numbered slots
        that were sealed by a previous TP close become reachable again.
        Without this reset, ``next_available_counter_slot`` would see
        the sealed slot and incorrectly trigger a new layer.
        """
        for s in self.slots:
            if s.index > index and s.ever_closed and s.entry is None and s.pending_rebuild is None:
                s.ever_closed = False

    def remove_entry(self, entry_id: int) -> None:
        """Remove an entry by ID (used by protection modes).  Seals the slot."""
        for s in self.slots:
            if s.entry is not None and s.entry.entry_id == entry_id:
                s.close(refillable=False)
                return

    # -- Weighted average helpers --

    def weighted_avg_close_price(
        self,
        new_price: Decimal,
        new_units: int,
        include_ref: Entry | None = None,
    ) -> tuple[Decimal, str]:
        """Compute weighted-average close price for a new entry in this layer.

        Includes: new entry + existing occupied slots + slots awaiting
        stop-loss rebuild + optional reference entry.

        Pending-rebuild slots are included because the position still
        logically belongs to the cycle — it was closed by stop-loss and
        will be re-opened when price returns.  Excluding them would
        collapse the weighted average toward the new entry's price,
        producing a TP that is too close to (or equal to) the entry
        price and causing immediate close-reopen churn.
        """
        total_cost = new_price * Decimal(str(new_units))
        total_units = new_units
        parts = [f"{new_price} * {new_units}"]

        for s in self.slots:
            if s.entry is not None and not s.entry.is_hedge:
                total_cost += s.entry.entry_price * Decimal(str(s.entry.units))
                total_units += s.entry.units
                parts.append(f"{s.entry.entry_price} * {s.entry.units}")
            elif s.pending_rebuild is not None:
                pr = s.pending_rebuild
                total_cost += pr.entry_price * Decimal(str(pr.units))
                total_units += pr.units
                parts.append(f"{pr.entry_price} * {pr.units}")

        if include_ref is not None:
            ref_units = abs(include_ref.units)
            if ref_units > 0:
                total_cost += include_ref.entry_price * Decimal(str(ref_units))
                total_units += ref_units
                parts.append(f"{include_ref.entry_price} * {ref_units}")

        close_price = total_cost / Decimal(str(total_units)) if total_units > 0 else new_price
        formula = f"({' + '.join(parts)}) / {total_units}"
        return close_price, formula

    def current_weighted_avg_close_price(self) -> tuple[Decimal, str] | None:
        """Compute the weighted-average close price from the layer's current state."""
        total_cost = Decimal("0")
        total_units = 0
        parts: list[str] = []

        for s in self.slots:
            if s.entry is not None and not s.entry.is_hedge:
                total_cost += s.entry.entry_price * Decimal(str(s.entry.units))
                total_units += s.entry.units
                parts.append(f"{s.entry.entry_price} * {s.entry.units}")
            elif s.pending_rebuild is not None:
                pr = s.pending_rebuild
                total_cost += pr.entry_price * Decimal(str(pr.units))
                total_units += pr.units
                parts.append(f"{pr.entry_price} * {pr.units}")

        if total_units <= 0:
            return None

        close_price = total_cost / Decimal(str(total_units))
        formula = f"({' + '.join(parts)}) / {total_units}"
        return close_price, formula

    def layer_initial_close_price(
        self,
        new_price: Decimal,
        new_units: int,
        prev_layer: "Layer",
        direction: Direction,
        pip_size: Decimal,
        m_pips: Decimal,
    ) -> tuple[Decimal, str]:
        """Compute close price for a layer-initial entry.

        Uses the close_price of the highest-numbered present slot
        (occupied or pending rebuild) in the previous layer.
        Falls back to m_pips from entry price.
        """
        highest = prev_layer.highest_present_slot()
        if highest is not None:
            if highest.entry is not None:
                close_price = highest.entry.close_price
                return close_price, f"{close_price:.5f}"
            if highest.pending_rebuild is not None:
                close_price = highest.pending_rebuild.close_price
                return close_price, f"{close_price:.5f}"

        if direction == Direction.LONG:
            close_price = new_price + m_pips * pip_size
        else:
            close_price = new_price - m_pips * pip_size
        op = "+" if direction == Direction.LONG else "-"
        return close_price, f"{new_price} {op} {m_pips} * {pip_size}"

    # -- Serialisation --

    def to_dict(self) -> dict[str, Any]:
        return {
            "layer_number": self.layer_number,
            "slots": [s.to_dict() for s in self.slots],
            "base_units": self.base_units,
            "refill_up_to": self.refill_up_to,
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "Layer":
        return Layer(
            layer_number=_parse_int(d.get("layer_number", 1), 1),
            slots=[Slot.from_dict(s) for s in d.get("slots", [])],
            base_units=_parse_int(d.get("base_units", 1000), 1000),
            refill_up_to=_parse_int(d.get("refill_up_to", 2), 2),
        )

    @staticmethod
    def create(
        layer_number: int,
        r_max: int,
        base_units: int,
        refill_up_to: int = 2,
    ) -> "Layer":
        """Create a layer with R0 … R(r_max) slots (r_max + 1 total)."""
        return Layer(
            layer_number=layer_number,
            slots=[Slot(index=i) for i in range(r_max + 1)],
            base_units=base_units,
            refill_up_to=refill_up_to,
        )


# ---------------------------------------------------------------------------
# PositionGrid
# ---------------------------------------------------------------------------


@dataclass
class PositionGrid:
    """Flat, ordered collection of all positions in a cycle.

    The grid is a list of ``Layer`` objects.  Every position — including the
    cycle's first entry at L0/R0 — lives in a slot.  This eliminates the
    need for a separate ``initial_entry`` field and makes close ordering
    uniform.

    Ordering convention (grid_key = (layer, index)):
    - Front (oldest): L0/R0
    - Back  (newest): highest layer, highest index

    Normal TP closes from the back.  Shrink closes from the front.
    """

    layers: list[Layer] = field(default_factory=list)

    # -- Layer management --

    @property
    def current_layer(self) -> Layer | None:
        return self.layers[-1] if self.layers else None

    @property
    def layer_count(self) -> int:
        return len(self.layers)

    def add_layer(self, layer: Layer) -> None:
        self.layers.append(layer)

    def find_layer(self, layer_number: int) -> Layer | None:
        for layer in self.layers:
            if layer.layer_number == layer_number:
                return layer
        return None

    # -- Entry queries --

    def all_entries(self) -> list[Entry]:
        entries: list[Entry] = []
        for layer in self.layers:
            entries.extend(layer.all_entries())
        return entries

    def head_entry(self) -> Entry | None:
        """Return the oldest surviving position (cycle head).

        This is the entry whose TP closes the cycle.  It is always the
        entry with the smallest grid_key among all occupied slots.
        """
        for layer in self.layers:
            lowest = layer.lowest_occupied_slot()
            if lowest is not None and lowest.entry is not None:
                return lowest.entry
        return None

    def tail_entry(self) -> Entry | None:
        """Return the newest position (highest grid_key)."""
        for layer in reversed(self.layers):
            highest = layer.highest_occupied_slot()
            if highest is not None and highest.entry is not None:
                return highest.entry
        return None

    def has_counter_entries(self) -> bool:
        """True if any position other than the head is open."""
        head = self.head_entry()
        if head is None:
            return False
        for layer in self.layers:
            for s in layer.slots:
                if s.entry is not None and s.entry.entry_id != head.entry_id:
                    return True
        return False

    def is_empty(self) -> bool:
        """True if no layer has live entries."""
        return all(not layer.has_open_entries() for layer in self.layers)

    def has_pending_rebuilds(self) -> bool:
        """True if any slot in the grid is awaiting SL rebuild."""
        return any(s.is_pending_rebuild for layer in self.layers for s in layer.slots)

    def is_fully_pending(self, f_max: int) -> bool:
        """True if the grid has all layers up to f_max and every slot is pending rebuild.

        The grid must contain exactly ``f_max`` layers (L1 … Lf)
        and every slot in every layer must be in ``pending_rebuild`` state.
        Returns False when layers have not been fully expanded yet.
        """
        if len(self.layers) < f_max:
            return False
        slots = [s for layer in self.layers for s in layer.slots]
        return len(slots) > 0 and all(s.is_pending_rebuild for s in slots)

    def pending_rebuild_slots(self) -> list[tuple["Layer", Slot]]:
        """Return all (layer, slot) pairs awaiting SL rebuild."""
        result: list[tuple[Layer, Slot]] = []
        for layer in self.layers:
            for s in layer.slots:
                if s.is_pending_rebuild:
                    result.append((layer, s))
        return result

    # -- Shrink: close from front --

    def front_entry(self) -> Entry | None:
        """Return the next shrink candidate respecting layer-preservation rules.

        Priority (within a single cycle):
        1. Lowest layer number first.
        2. Within a layer, lowest R index first.
        3. **Exception**: if a layer has exactly 1 occupied slot, check whether
           any *higher* layer has 2+ occupied slots.  If yes, skip this layer
           and let the higher layer yield a candidate (its lowest R).  If no
           higher layer has 2+ slots either, close this single position.

        This preserves the "last survivor" in a layer as long as there are
        still trimmable positions in upper layers.
        """
        layers = self.layers

        for i, layer in enumerate(layers):
            occupied = layer.occupied_slots()
            if not occupied:
                continue

            if len(occupied) >= 2:
                # Multiple positions → close the lowest R
                lowest = min(occupied, key=lambda s: s.index)
                return lowest.entry

            # Exactly 1 position in this layer.
            # Check if any higher layer has 2+ occupied slots.
            has_multi_above = any(len(upper.occupied_slots()) >= 2 for upper in layers[i + 1 :])

            if has_multi_above:
                # Skip — upper layers still have trimmable positions
                continue

            # All layers above also have ≤1 position. Close this one.
            return occupied[0].entry

        return None

    # -- Normal TP: close from back --

    def back_entry_for_tp(self) -> tuple[Entry | None, Layer | None]:
        """Return the newest counter entry eligible for TP close.

        Walks layers from newest to oldest, returning the highest occupied
        slot.  Skips the head entry (it closes via cycle TP, not counter TP).
        """
        head = self.head_entry()
        for layer in reversed(self.layers):
            highest = layer.highest_occupied_slot()
            if highest is None or highest.entry is None:
                continue
            if head is not None and highest.entry.entry_id == head.entry_id:
                continue  # don't close head via counter TP
            return highest.entry, layer
        return None, None

    # -- Remove entry (protection) --

    def remove_entry(self, entry_id: int) -> None:
        for layer in self.layers:
            layer.remove_entry(entry_id)

    # -- Serialisation --

    def to_dict(self) -> dict[str, Any]:
        return {"layers": [layer.to_dict() for layer in self.layers]}

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "PositionGrid":
        raw_layers = data.get("layers")
        layers = [Layer.from_dict(ld) for ld in raw_layers] if raw_layers else []
        return PositionGrid(layers=layers)


# ---------------------------------------------------------------------------
# Cycle
# ---------------------------------------------------------------------------


@dataclass
class SnowballCycle:
    """A single trading cycle: from first entry through to close.

    All positions live in ``grid``.  The cycle head is determined
    dynamically via ``grid.head_entry()``.
    """

    cycle_id: int
    direction: Direction
    grid: PositionGrid = field(default_factory=PositionGrid)
    hedge_entries: list[Entry] = field(default_factory=list)
    counter_close_count: int = 0
    status: CycleStatus = CycleStatus.ACTIVE
    trade_cycle_id: str | None = None

    # Realised P/L accumulated over every close that happened within this
    # cycle.  Used for end-of-cycle sanity logging (a completed cycle is
    # expected to finish non-negative).  Denominated in account currency.
    realized_pnl: Decimal = field(default_factory=lambda: Decimal("0"))

    # -- Status convenience --

    @property
    def completed(self) -> bool:
        return self.status == CycleStatus.COMPLETED

    @completed.setter
    def completed(self, value: bool) -> None:
        self.status = CycleStatus.COMPLETED if value else CycleStatus.ACTIVE

    @property
    def is_active(self) -> bool:
        return self.status == CycleStatus.ACTIVE

    @property
    def is_pending(self) -> bool:
        return self.status == CycleStatus.PENDING

    @property
    def is_fully_pending(self) -> bool:
        """True if the cycle is PENDING and every slot is awaiting rebuild.

        .. note:: This property cannot check ``f_max`` — use
           :meth:`is_grid_exhausted` when the config is available.
        """
        return self.is_pending and self.grid.is_fully_pending(f_max=0)

    def is_grid_exhausted(self, f_max: int) -> bool:
        """True if the cycle is PENDING and the grid is fully saturated.

        All ``f_max`` layers must exist and every slot in every
        layer must be in pending-rebuild state.
        """
        return self.is_pending and self.grid.is_fully_pending(f_max=f_max)

    # -- Convenience --

    @property
    def current_layer(self) -> Layer | None:
        return self.grid.current_layer

    @property
    def layer_count(self) -> int:
        return self.grid.layer_count

    @property
    def is_long(self) -> bool:
        return self.direction == Direction.LONG

    @property
    def is_short(self) -> bool:
        return self.direction == Direction.SHORT

    @property
    def initial_entry(self) -> Entry | None:
        """Dynamic cycle head — the oldest surviving position."""
        return self.grid.head_entry()

    def effective_head(self) -> tuple[Decimal | None, int | None]:
        """Return (entry_price, entry_id) for the cycle head.

        Falls back to the R0 pending-rebuild snapshot when no live entry
        exists, so callers can still compute adverse distance and loss
        checks even after all positions have been stop-loss closed.
        """
        head = self.initial_entry
        if head is not None:
            return head.entry_price, head.entry_id
        layer = self.current_layer
        if layer is None:
            return None, None
        r0 = layer.slot_at(0)
        if r0 is not None and r0.pending_rebuild is not None:
            return r0.pending_rebuild.entry_price, r0.pending_rebuild.root_entry_id
        return None, None

    def add_layer(self, layer: Layer) -> None:
        self.grid.add_layer(layer)

    def find_layer(self, layer_number: int) -> Layer | None:
        return self.grid.find_layer(layer_number)

    def all_entries(self) -> list[Entry]:
        entries = self.grid.all_entries()
        entries.extend(self.hedge_entries)
        return entries

    def counter_non_hedge(self) -> list[Entry]:
        head = self.grid.head_entry()
        entries: list[Entry] = []
        for e in self.grid.all_entries():
            if head is not None and e.entry_id == head.entry_id:
                continue
            if not e.is_hedge:
                entries.append(e)
        return entries

    @property
    def counter_entries(self) -> list[Entry]:
        return self.counter_non_hedge()

    @property
    def layers(self) -> list[Layer]:
        return self.grid.layers

    def initial_for_layer(self, layer_number: int) -> Entry | None:
        layer = self.grid.find_layer(layer_number)
        if layer is None:
            return None
        r0 = layer.slot_at(0)
        return r0.entry if r0 is not None else None

    def remove_entry(self, entry_id: int) -> None:
        self.grid.remove_entry(entry_id)
        self.hedge_entries = [e for e in self.hedge_entries if e.entry_id != entry_id]

    # -- Compat properties --

    @property
    def layer_index(self) -> int:
        return self.grid.layer_count - 1 if self.grid.layer_count > 0 else 0

    @property
    def layer_retracement_count(self) -> int:
        layer = self.grid.current_layer
        return len(layer.occupied_slots()) if layer else 0

    @property
    def layer_initial_entries(self) -> dict[int, Entry]:
        result: dict[int, Entry] = {}
        for layer in self.grid.layers:
            r0 = layer.slot_at(0)
            if r0 is not None and r0.entry is not None:
                result[layer.layer_number] = r0.entry
        return result

    # -- Serialisation --

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "direction": self.direction.value,
            "grid": self.grid.to_dict(),
            "hedge_entries": [e.to_dict() for e in self.hedge_entries],
            "counter_close_count": self.counter_close_count,
            "status": self.status.value,
            "trade_cycle_id": self.trade_cycle_id,
            "realized_pnl": str(self.realized_pnl),
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "SnowballCycle":
        raw_direction = data.get("direction", "long")
        direction = (
            raw_direction
            if isinstance(raw_direction, Direction)
            else Direction(str(raw_direction).strip().lower())
        )

        grid = PositionGrid.from_dict(data["grid"])

        raw_status = data.get("status")
        status = CycleStatus(str(raw_status).strip().lower())

        return SnowballCycle(
            cycle_id=_parse_int(data.get("cycle_id", 0), 0),
            direction=direction,
            grid=grid,
            hedge_entries=[Entry.from_dict(e) for e in data.get("hedge_entries", [])],
            counter_close_count=_parse_int(data.get("counter_close_count", 0), 0),
            status=status,
            trade_cycle_id=data.get("trade_cycle_id"),
            realized_pnl=_parse_decimal(data.get("realized_pnl", "0"), "0"),
        )


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


@dataclass
class SnowballStrategyState:
    """Mutable runtime state for Snowball strategy."""

    protection_level: ProtectionLevel = ProtectionLevel.NORMAL
    initialised: bool = False
    cycles: list[SnowballCycle] = field(default_factory=list)
    next_entry_id: int = 1

    # Lock state
    lock_hedge_ids: list[int] = field(default_factory=list)
    lock_entered_at: str | None = None
    cooldown_until: str | None = None

    # Price tracking
    last_bid: Decimal | None = None
    last_ask: Decimal | None = None
    last_mid: Decimal | None = None
    account_balance: Decimal = Decimal("0")
    account_nav: Decimal = Decimal("0")

    metrics: dict[str, str | int | float] = field(default_factory=dict)

    def allocate_id(self) -> int:
        eid = self.next_entry_id
        self.next_entry_id += 1
        return eid

    def active_cycles(self) -> list[SnowballCycle]:
        return [c for c in self.cycles if not c.completed]

    def tradable_cycles(self) -> list[SnowballCycle]:
        """Return only cycles that are actively trading (not pending or completed)."""
        return [c for c in self.cycles if c.is_active]

    def all_entries(self) -> list[Entry]:
        entries: list[Entry] = []
        for c in self.active_cycles():
            entries.extend(c.all_entries())
        return entries

    def find_cycle(self, cycle_id: int) -> SnowballCycle | None:
        for c in self.cycles:
            if c.cycle_id == cycle_id:
                return c
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "protection_level": self.protection_level.value,
            "initialised": self.initialised,
            "cycles": [c.to_dict() for c in self.cycles],
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
        def _dec_or_none(v: object) -> Decimal | None:
            return _parse_decimal(v, "0") if v is not None else None

        raw_cycles = data.get("cycles")
        cycles = [SnowballCycle.from_dict(c) for c in raw_cycles] if raw_cycles is not None else []

        return SnowballStrategyState(
            protection_level=ProtectionLevel(
                data.get("protection_level", ProtectionLevel.NORMAL.value)
            ),
            initialised=bool(data.get("initialised", False)),
            cycles=cycles,
            next_entry_id=max(1, _parse_int(data.get("next_entry_id", 1), 1)),
            lock_hedge_ids=[_parse_int(i, 0) for i in (data.get("lock_hedge_ids") or [])],
            lock_entered_at=data.get("lock_entered_at"),
            cooldown_until=data.get("cooldown_until"),
            last_bid=_dec_or_none(data.get("last_bid")),
            last_ask=_dec_or_none(data.get("last_ask")),
            last_mid=_dec_or_none(data.get("last_mid")),
            account_balance=_parse_decimal(data.get("account_balance", "0"), "0"),
            account_nav=_parse_decimal(data.get("account_nav", "0"), "0"),
            metrics=dict(data.get("metrics", {})) if isinstance(data.get("metrics"), dict) else {},
        )

    @classmethod
    def from_strategy_state(cls, raw: dict[str, Any] | None) -> "SnowballStrategyState":
        if not isinstance(raw, dict):
            return cls()
        return cls.from_dict(raw)


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _parse_decimal(value: object, default: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)


def _parse_int(value: object, default: int) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _parse_str(value: object, default: str) -> str:
    return str(value).strip().lower() if value is not None else default


def _parse_bool(value: object, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y", "on"}:
            return True
        if normalized in {"false", "0", "no", "n", "off", ""}:
            return False
    return default
