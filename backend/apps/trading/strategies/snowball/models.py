"""Data models for Snowball strategy.

Hierarchy: Cycle → Layer → Slot → Entry.

- A **Cycle** is one directional trade from initial entry to close.
- A **Layer** holds up to ``r_max`` retracement slots plus a layer-initial entry.
- A **Slot** is a numbered seat (R1..R_max) that holds an Entry or is empty.
- An **Entry** is a single position with entry price, close price, units, etc.

Key rules encoded in the model:
- L1/R0 close always ends the cycle.
- L2+ R0 close resets the layer (refillable by default).
- Slot close with index <= refill_up_to keeps the slot refillable.
- Slot close with index > refill_up_to seals the slot, triggering a new layer.
- Closes proceed from the newest layer's highest R down to L1/R0.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any, Literal

from apps.trading.enums import Direction
from apps.trading.strategies.snowball.enums import ProtectionLevel

if TYPE_CHECKING:
    from apps.trading.dataclasses.tick import Tick
    from apps.trading.events import ClosePositionEvent, OpenPositionEvent, StrategyEvent


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

    # Counter-trend step TP
    counter_tp_mode: str
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
    rebalance_enabled: bool
    rebalance_start_ratio: Decimal
    rebalance_end_ratio: Decimal
    shrink_enabled: bool
    m_th: Decimal
    lock_enabled: bool
    n_th: Decimal
    cooldown_sec: int

    # Spread guard
    spread_guard_enabled: bool
    spread_guard_pips: Decimal

    pip_size: Decimal

    @staticmethod
    def from_dict(raw: dict[str, Any]) -> SnowballStrategyConfig:
        manual_raw = raw.get("manual_intervals", [])
        manual_intervals: list[Decimal] = []
        if isinstance(manual_raw, list):
            for v in manual_raw:
                manual_intervals.append(_parse_decimal(v, "30"))

        return SnowballStrategyConfig(
            base_units=_parse_int(raw.get("base_units", 1000), 1000),
            m_pips=_parse_decimal(raw.get("m_pips", "50"), "50"),
            trend_lot_size=_parse_int(raw.get("trend_lot_size", 1), 1),
            r_max=_parse_int(raw.get("r_max", 7), 7),
            f_max=_parse_int(raw.get("f_max", 3), 3),
            post_r_max_base_factor=_parse_decimal(raw.get("post_r_max_base_factor", "1"), "1"),
            refill_up_to=_parse_int(raw.get("refill_up_to", 2), 2),
            n_pips_head=_parse_decimal(raw.get("n_pips_head", "30"), "30"),
            n_pips_tail=_parse_decimal(raw.get("n_pips_tail", "14"), "14"),
            n_pips_flat_steps=_parse_int(raw.get("n_pips_flat_steps", 2), 2),
            n_pips_gamma=_parse_decimal(raw.get("n_pips_gamma", "1.4"), "1.4"),
            interval_mode=_parse_str(raw.get("interval_mode"), "constant"),
            manual_intervals=manual_intervals,
            counter_tp_mode=_parse_str(raw.get("counter_tp_mode"), "weighted_avg"),
            counter_tp_pips=_parse_decimal(raw.get("counter_tp_pips", "25"), "25"),
            counter_tp_step_amount=_parse_decimal(raw.get("counter_tp_step_amount", "2.5"), "2.5"),
            counter_tp_multiplier=_parse_decimal(raw.get("counter_tp_multiplier", "1.2"), "1.2"),
            round_step_pips=_parse_decimal(raw.get("round_step_pips", "0.1"), "0.1"),
            dynamic_tp_enabled=bool(raw.get("dynamic_tp_enabled", False)),
            atr_period=_parse_int(raw.get("atr_period", 14), 14),
            atr_timeframe=_parse_str(raw.get("atr_timeframe"), "M1").upper(),
            atr_baseline_lookback=_parse_int(raw.get("atr_baseline_lookback", 96), 96),
            m_pips_min=_parse_decimal(raw.get("m_pips_min", "12"), "12"),
            m_pips_max=_parse_decimal(raw.get("m_pips_max", "80"), "80"),
            rebalance_enabled=bool(raw.get("rebalance_enabled", False)),
            rebalance_start_ratio=_parse_decimal(raw.get("rebalance_start_ratio", "60"), "60"),
            rebalance_end_ratio=_parse_decimal(raw.get("rebalance_end_ratio", "50"), "50"),
            shrink_enabled=bool(raw.get("shrink_enabled", True)),
            m_th=_parse_decimal(raw.get("m_th", "70"), "70"),
            lock_enabled=bool(raw.get("lock_enabled", True)),
            n_th=_parse_decimal(raw.get("n_th", "85"), "85"),
            cooldown_sec=_parse_int(raw.get("cooldown_sec", 300), 300),
            spread_guard_enabled=bool(raw.get("spread_guard_enabled", False)),
            spread_guard_pips=_parse_decimal(raw.get("spread_guard_pips", "2.5"), "2.5"),
            pip_size=_parse_decimal(raw.get("pip_size", "0.01"), "0.01"),
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
            "rebalance_enabled": self.rebalance_enabled,
            "rebalance_start_ratio": str(self.rebalance_start_ratio),
            "rebalance_end_ratio": str(self.rebalance_end_ratio),
            "shrink_enabled": self.shrink_enabled,
            "m_th": str(self.m_th),
            "lock_enabled": self.lock_enabled,
            "n_th": str(self.n_th),
            "cooldown_sec": self.cooldown_sec,
            "spread_guard_enabled": self.spread_guard_enabled,
            "spread_guard_pips": str(self.spread_guard_pips),
            "pip_size": str(self.pip_size),
        }

    def validate(self) -> None:
        if self.shrink_enabled and self.lock_enabled and not self.m_th < self.n_th < Decimal("100"):
            raise ValueError("Must satisfy m_th < n_th < 100")
        if self.shrink_enabled and not Decimal("0") < self.m_th < Decimal("100"):
            raise ValueError("m_th must be between 0 and 100")
        if self.lock_enabled and not Decimal("0") < self.n_th < Decimal("100"):
            raise ValueError("n_th must be between 0 and 100")
        if self.dynamic_tp_enabled and not self.m_pips_min <= self.m_pips <= self.m_pips_max:
            raise ValueError("Must satisfy m_pips_min <= m_pips <= m_pips_max")
        if not self.n_pips_head >= self.n_pips_tail > 0:
            raise ValueError("Must satisfy n_pips_head >= n_pips_tail > 0")
        if not self.n_pips_flat_steps < self.r_max:
            raise ValueError("n_pips_flat_steps must be < r_max")
        if self.counter_tp_mode != "weighted_avg" and self.counter_tp_pips <= 0:
            raise ValueError("counter_tp_pips must be > 0")
        if self.rebalance_enabled and not self.rebalance_start_ratio > self.rebalance_end_ratio > 0:
            raise ValueError("rebalance_start_ratio > rebalance_end_ratio > 0")
        if self.interval_mode == "manual":
            if len(self.manual_intervals) != self.r_max:
                raise ValueError(
                    f"manual_intervals must have exactly {self.r_max} entries for r_max={self.r_max}"
                )
            if any(v < 1 for v in self.manual_intervals):
                raise ValueError("All manual_intervals values must be >= 1")
        if not 0 <= self.refill_up_to < self.r_max:
            raise ValueError(f"refill_up_to must be >= 0 and < r_max ({self.r_max})")


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------


@dataclass
class Entry:
    """A single position entry within a cycle."""

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

    # Validation fields
    expected_interval_pips: Decimal | None = None
    actual_interval_pips: Decimal | None = None
    expected_tp_pips: Decimal | None = None
    validation_status: str = ""

    @classmethod
    def open(
        cls,
        *,
        state: SnowballStrategyState,
        tick: Tick,
        direction: Direction,
        units: int,
        step: int,
        close_price: Decimal,
        role: Literal["initial", "counter", "hedge", "layer_initial"],
        layer_number: int = 1,
        retracement_count: int = 0,
        root_entry_id: int | None = None,
        parent_entry_id: int | None = None,
    ) -> Entry:
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

    def exit_price(self, tick: Tick) -> Decimal:
        return tick.bid if self.is_long else tick.ask

    def unrealised_loss_pips(self, mid_price: Decimal, pip_size: Decimal) -> Decimal:
        """Positive = losing."""
        if self.is_long:
            return (self.entry_price - mid_price) / pip_size
        return (mid_price - self.entry_price) / pip_size

    # ------------------------------------------------------------------
    # Event generation
    # ------------------------------------------------------------------

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
            description=description,
        )
        self.apply_metadata_to(event)
        return event

    def to_close_event(
        self,
        tick: Tick,
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

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

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
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> Entry:
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
        )


BasketEntry = Entry


# ---------------------------------------------------------------------------
# Slot
# ---------------------------------------------------------------------------


@dataclass
class Slot:
    """A retracement seat (R1, R2, ...) within a Layer.

    States:
    - empty + not ever_closed → available for a new entry
    - occupied → holds an open entry
    - empty + ever_closed → sealed; triggers new layer on next adverse move
    """

    index: int  # 1-based (R1=1, R2=2, ...)
    entry: Entry | None = None
    ever_closed: bool = False

    @property
    def is_occupied(self) -> bool:
        return self.entry is not None

    @property
    def is_empty(self) -> bool:
        return self.entry is None

    @property
    def is_available(self) -> bool:
        """True if this slot can accept a new entry."""
        return self.entry is None and not self.ever_closed

    def fill(self, entry: Entry) -> None:
        self.entry = entry

    def close(self, *, refillable: bool) -> Entry | None:
        """Close the entry in this slot.

        If *refillable*, the slot remains available for re-entry.
        Otherwise it is sealed (ever_closed=True).
        """
        e = self.entry
        self.entry = None
        if not refillable:
            self.ever_closed = True
        return e

    def reset(self) -> None:
        """Reset to fresh empty state."""
        self.entry = None
        self.ever_closed = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "entry": self.entry.to_dict() if self.entry else None,
            "ever_closed": self.ever_closed,
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> Slot:
        raw_entry = d.get("entry")
        return Slot(
            index=_parse_int(d.get("index", 1), 1),
            entry=Entry.from_dict(raw_entry) if raw_entry else None,
            ever_closed=bool(d.get("ever_closed", False)),
        )


# ---------------------------------------------------------------------------
# Layer
# ---------------------------------------------------------------------------


@dataclass
class Layer:
    """A layer of r_max retracement slots.

    L1 uses the cycle's initial_entry as its reference.
    L2+ have their own initial_entry (layer_initial).

    The layer knows its ``refill_up_to`` threshold so it can decide
    whether a closed slot should be refillable or sealed.
    """

    layer_number: int  # 1-based
    slots: list[Slot] = field(default_factory=list)
    initial_entry: Entry | None = None
    base_units: int = 1000
    refill_up_to: int = 2  # slots R1..R(refill_up_to) are refillable

    # ------------------------------------------------------------------
    # Slot queries
    # ------------------------------------------------------------------

    def occupied_slots(self) -> list[Slot]:
        return [s for s in self.slots if s.is_occupied]

    def highest_occupied_slot(self) -> Slot | None:
        occupied = self.occupied_slots()
        return max(occupied, key=lambda s: s.index) if occupied else None

    def next_available_slot(self) -> Slot | None:
        """Return the next slot that can accept an entry.

        Walks slots in order.  Returns None if:
        - A sealed (ever_closed) slot is encountered before an available one
        - All slots are occupied
        """
        for s in self.slots:
            if s.is_available:
                return s
            if s.is_empty and s.ever_closed:
                return None  # sealed slot blocks further filling → new layer
        return None  # all occupied

    @property
    def needs_new_layer(self) -> bool:
        """True if this layer cannot accept more entries and a new layer is needed."""
        return self.next_available_slot() is None

    @property
    def needs_initial_rebuild(self) -> bool:
        """True if this is L2+ and the initial entry needs to be (re)built."""
        return self.layer_number > 1 and self.initial_entry is None

    def has_open_entries(self) -> bool:
        if self.initial_entry is not None:
            return True
        return any(s.is_occupied for s in self.slots)

    def all_entries(self) -> list[Entry]:
        entries: list[Entry] = []
        if self.initial_entry is not None:
            entries.append(self.initial_entry)
        for s in self.slots:
            if s.entry is not None:
                entries.append(s.entry)
        return entries

    # ------------------------------------------------------------------
    # Close operations
    # ------------------------------------------------------------------

    def close_slot(self, slot_index: int) -> Entry | None:
        """Close the entry in the slot at *slot_index* (1-based).

        Refillability is determined by comparing slot_index to refill_up_to.
        For L2+, R0 (initial_entry) is always refillable — handled separately.
        """
        for s in self.slots:
            if s.index == slot_index and s.is_occupied:
                refillable = s.index <= self.refill_up_to
                return s.close(refillable=refillable)
        return None

    def close_initial(self) -> Entry | None:
        """Close the layer-initial entry and reset the layer for reuse.

        Only applicable to L2+.  Resets all slots so the layer can be
        re-entered on the next adverse move.
        """
        e = self.initial_entry
        self.initial_entry = None
        for s in self.slots:
            s.reset()
        return e

    def remove_entry(self, entry_id: int) -> None:
        """Remove an entry by ID (used by protection modes)."""
        if self.initial_entry is not None and self.initial_entry.entry_id == entry_id:
            self.initial_entry = None
            return
        for s in self.slots:
            if s.entry is not None and s.entry.entry_id == entry_id:
                s.close(refillable=False)
                return

    # ------------------------------------------------------------------
    # Weighted average helpers
    # ------------------------------------------------------------------

    def weighted_avg_close_price(
        self,
        new_price: Decimal,
        new_units: int,
        include_initial: Entry | None = None,
    ) -> tuple[Decimal, str]:
        """Compute weighted-average close price for a new entry in this layer.

        Includes: new entry + existing slot entries + layer initial (or cycle initial).
        Returns (close_price, formula_string).
        """
        total_cost = new_price * Decimal(str(new_units))
        total_units = new_units
        parts = [f"{new_price} * {new_units}"]

        for s in self.slots:
            if s.entry is not None and not s.entry.is_hedge:
                total_cost += s.entry.entry_price * Decimal(str(s.entry.units))
                total_units += s.entry.units
                parts.append(f"{s.entry.entry_price} * {s.entry.units}")

        ref = include_initial or self.initial_entry
        if ref is not None:
            ref_units = abs(ref.units)
            if ref_units > 0:
                total_cost += ref.entry_price * Decimal(str(ref_units))
                total_units += ref_units
                parts.append(f"{ref.entry_price} * {ref_units}")

        close_price = total_cost / Decimal(str(total_units)) if total_units > 0 else new_price
        formula = f"({' + '.join(parts)}) / {total_units}"
        return close_price, formula

    def layer_initial_close_price(
        self,
        new_price: Decimal,
        new_units: int,
        prev_layer: Layer,
        prev_layer_initial: Entry | None,
        direction: Direction,
        pip_size: Decimal,
        m_pips: Decimal,
    ) -> tuple[Decimal, str]:
        """Compute close price for a layer-initial entry (L2+).

        Uses the close_price of the highest-numbered occupied slot in the
        previous layer.  This guarantees L2/R0 closes before any L1
        retracement, preserving the correct close order.

        Falls back to m_pips from entry price if no previous slot is occupied.
        """
        # Find the highest occupied slot in the previous layer
        highest = prev_layer.highest_occupied_slot()
        if highest is not None and highest.entry is not None:
            close_price = highest.entry.close_price
            formula = f"{close_price:.5f}"
            return close_price, formula

        # Fallback: use m_pips from entry price (same as L1/R0)
        if direction == Direction.LONG:
            close_price = new_price + m_pips * pip_size
        else:
            close_price = new_price - m_pips * pip_size
        op = "+" if direction == Direction.LONG else "-"
        formula = f"{new_price} {op} {m_pips} * {pip_size}"
        return close_price, formula

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "layer_number": self.layer_number,
            "slots": [s.to_dict() for s in self.slots],
            "initial_entry": self.initial_entry.to_dict() if self.initial_entry else None,
            "base_units": self.base_units,
            "refill_up_to": self.refill_up_to,
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> Layer:
        raw_initial = d.get("initial_entry")
        return Layer(
            layer_number=_parse_int(d.get("layer_number", 1), 1),
            slots=[Slot.from_dict(s) for s in d.get("slots", [])],
            initial_entry=Entry.from_dict(raw_initial) if raw_initial else None,
            base_units=_parse_int(d.get("base_units", 1000), 1000),
            refill_up_to=_parse_int(d.get("refill_up_to", 2), 2),
        )

    @staticmethod
    def create(layer_number: int, r_max: int, base_units: int, refill_up_to: int = 2) -> Layer:
        return Layer(
            layer_number=layer_number,
            slots=[Slot(index=i + 1) for i in range(r_max)],
            base_units=base_units,
            refill_up_to=refill_up_to,
        )


# ---------------------------------------------------------------------------
# Cycle
# ---------------------------------------------------------------------------


@dataclass
class SnowballCycle:
    """A single trading cycle: initial entry through to close."""

    cycle_id: int
    direction: Direction
    initial_entry: Entry | None = None
    layers: list[Layer] = field(default_factory=list)
    hedge_entries: list[Entry] = field(default_factory=list)
    counter_close_count: int = 0
    completed: bool = False

    @property
    def current_layer(self) -> Layer | None:
        return self.layers[-1] if self.layers else None

    @property
    def layer_count(self) -> int:
        return len(self.layers)

    @property
    def is_long(self) -> bool:
        return self.direction == Direction.LONG

    @property
    def is_short(self) -> bool:
        return self.direction == Direction.SHORT

    def add_layer(self, layer: Layer) -> None:
        self.layers.append(layer)

    def all_entries(self) -> list[Entry]:
        entries: list[Entry] = []
        if self.initial_entry is not None:
            entries.append(self.initial_entry)
        for layer in self.layers:
            entries.extend(layer.all_entries())
        entries.extend(self.hedge_entries)
        return entries

    def counter_non_hedge(self) -> list[Entry]:
        entries: list[Entry] = []
        for layer in self.layers:
            for s in layer.slots:
                if s.entry is not None and not s.entry.is_hedge:
                    entries.append(s.entry)
        return entries

    # Backward compat
    @property
    def counter_entries(self) -> list[Entry]:
        return self.counter_non_hedge()

    def initial_for_layer(self, layer_number: int) -> Entry | None:
        if layer_number == 1:
            return self.initial_entry
        for layer in self.layers:
            if layer.layer_number == layer_number:
                return layer.initial_entry
        return None

    def remove_entry(self, entry_id: int) -> None:
        for layer in self.layers:
            layer.remove_entry(entry_id)
        self.hedge_entries = [e for e in self.hedge_entries if e.entry_id != entry_id]

    def find_layer(self, layer_number: int) -> Layer | None:
        for layer in self.layers:
            if layer.layer_number == layer_number:
                return layer
        return None

    # Compat properties
    @property
    def layer_index(self) -> int:
        return len(self.layers) - 1 if self.layers else 0

    @property
    def layer_retracement_count(self) -> int:
        layer = self.current_layer
        return len(layer.occupied_slots()) if layer else 0

    @property
    def layer_initial_entries(self) -> dict[int, Entry]:
        result: dict[int, Entry] = {}
        for layer in self.layers:
            if layer.initial_entry is not None:
                result[layer.layer_number] = layer.initial_entry
        return result

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "direction": self.direction.value,
            "initial_entry": self.initial_entry.to_dict() if self.initial_entry is not None else {},
            "layers": [layer.to_dict() for layer in self.layers],
            "hedge_entries": [e.to_dict() for e in self.hedge_entries],
            "counter_close_count": self.counter_close_count,
            "completed": self.completed,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> SnowballCycle:
        raw_direction = data.get("direction", "long")
        direction = (
            raw_direction
            if isinstance(raw_direction, Direction)
            else Direction(str(raw_direction).strip().lower())
        )
        raw_initial = data.get("initial_entry", {})
        initial_entry: Entry | None = Entry.from_dict(raw_initial) if raw_initial else None

        raw_layers = data.get("layers")
        layers = [Layer.from_dict(ld) for ld in raw_layers] if raw_layers is not None else []

        return SnowballCycle(
            cycle_id=_parse_int(data.get("cycle_id", 0), 0),
            direction=direction,
            initial_entry=initial_entry,
            layers=layers,
            hedge_entries=[Entry.from_dict(e) for e in data.get("hedge_entries", [])],
            counter_close_count=_parse_int(data.get("counter_close_count", 0), 0),
            completed=bool(data.get("completed", False)),
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
    def from_dict(data: dict[str, Any]) -> SnowballStrategyState:
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
    def from_strategy_state(cls, raw: dict[str, Any] | None) -> SnowballStrategyState:
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
