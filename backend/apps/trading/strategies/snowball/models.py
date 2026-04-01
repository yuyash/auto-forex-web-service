"""Data models for Snowball strategy.

The core abstraction is a hierarchy: Cycle → Layer → Slot → Entry.

- A **Cycle** represents one directional trade from initial entry to close.
- A **Layer** holds up to ``r_max`` retracement slots plus a layer-initial entry.
  When all slots fill, a new layer is created (up to ``f_max``).
- A **Slot** is a numbered seat (R1..R_max) that can hold an open Entry or be empty.
- An **Entry** is a single position with entry price, close price, units, etc.

When price moves adversely, slots fill sequentially.  When price reverses and
a slot's entry hits its TP, the entry is closed and the slot becomes empty.
If price reverses again past the *next* unfilled slot's threshold, a new layer
begins instead of refilling the same slot.
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
    refill_up_to: int  # slots R1..R(refill_up_to) are refillable after close (0 = none)

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
        """Create config from a parameters dictionary."""
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
            refill_up_to=_parse_int(raw.get("refill_up_to", 0), 0),
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
        """Serialise to JSON-friendly dict."""
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
        """Raise ``ValueError`` on invalid parameter combinations."""
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
    step: int  # 1-based step within the current cycle
    direction: Direction
    entry_price: Decimal
    close_price: Decimal  # target close price
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

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

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
        """Factory: allocate an ID from state and build an Entry at the tick price."""
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

    # ------------------------------------------------------------------
    # Computed properties
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Price helpers
    # ------------------------------------------------------------------

    def exit_price(self, tick: Tick) -> Decimal:
        """Return the exit price for this entry given a tick."""
        return tick.bid if self.is_long else tick.ask

    def unrealised_loss_pips(self, mid_price: Decimal, pip_size: Decimal) -> Decimal:
        """Return unrealised loss in pips (positive = losing)."""
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
        """Write snowball-specific metadata from this entry onto a strategy event."""
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
        """Create an OpenPositionEvent from this entry."""
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
        """Create a ClosePositionEvent from this entry."""
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
    # Entry serialisation
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


# Backward-compatible alias
BasketEntry = Entry


# ---------------------------------------------------------------------------
# Slot — a numbered seat within a Layer that can hold an Entry
# ---------------------------------------------------------------------------


@dataclass
class Slot:
    """A retracement seat within a layer.

    ``index`` is 1-based (R1, R2, ...).  ``entry`` is the open position
    occupying this slot, or ``None`` when the slot is empty.
    ``ever_closed`` is ``True`` once an entry in this slot has been closed
    at least once — this prevents the slot from being refilled and instead
    triggers a new layer.
    """

    index: int  # 1-based (R1 = 1, R2 = 2, ...)
    entry: Entry | None = None
    ever_closed: bool = False

    @property
    def is_occupied(self) -> bool:
        return self.entry is not None

    @property
    def is_empty(self) -> bool:
        return self.entry is None

    def fill(self, entry: Entry) -> None:
        self.entry = entry

    def vacate(self, *, refillable: bool = False) -> Entry | None:
        """Remove and return the entry.

        When *refillable* is ``True`` the slot stays available for a new
        entry (``ever_closed`` remains ``False``).  Otherwise the slot is
        permanently sealed.
        """
        e = self.entry
        self.entry = None
        if not refillable:
            self.ever_closed = True
        return e

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
# Layer — a group of r_max slots plus an optional layer-initial entry
# ---------------------------------------------------------------------------


@dataclass
class Layer:
    """A single layer of retracement slots.

    ``layer_number`` is 1-based (L1, L2, ...).
    ``initial_entry`` is the layer-initial position (L1 uses the cycle initial;
    L2+ have their own layer-initial entry).
    ``slots`` is a list of ``r_max`` Slot objects.
    """

    layer_number: int  # 1-based
    slots: list[Slot] = field(default_factory=list)
    initial_entry: Entry | None = None  # layer-initial entry (None for L1)
    base_units: int = 1000
    completed: bool = False  # True once the layer-initial entry has been closed

    # ------------------------------------------------------------------
    # Slot queries
    # ------------------------------------------------------------------

    def occupied_slots(self) -> list[Slot]:
        """Return slots that currently hold an entry."""
        return [s for s in self.slots if s.is_occupied]

    def highest_occupied_slot(self) -> Slot | None:
        """Return the occupied slot with the highest index, or None."""
        occupied = self.occupied_slots()
        return max(occupied, key=lambda s: s.index) if occupied else None

    def next_slot_to_fill(self) -> Slot | None:
        """Return the next empty slot that has never been closed.

        Returns None when the layer is completed, the next empty slot has
        ``ever_closed=True``, or all slots are full.
        """
        if self.completed:
            return None
        for s in self.slots:
            if s.is_empty and not s.ever_closed:
                return s
            if s.is_empty and s.ever_closed:
                return None  # trigger new layer
            # occupied — skip
        return None  # all slots full

    def should_start_new_layer(self) -> bool:
        """True if the next empty slot has been previously closed (reversal),
        all slots are full, or the layer has been completed."""
        if self.completed:
            return True
        for s in self.slots:
            if s.is_empty and not s.ever_closed:
                return False
            if s.is_empty and s.ever_closed:
                return True
        return True  # all slots full

    def has_open_entries(self) -> bool:
        """True if any slot has an open entry or the layer initial is present."""
        if self.completed:
            return False
        if self.initial_entry is not None:
            return True
        return any(s.is_occupied for s in self.slots)

    def all_entries(self) -> list[Entry]:
        """Return all open entries in this layer (initial + slots)."""
        entries: list[Entry] = []
        if self.initial_entry is not None:
            entries.append(self.initial_entry)
        for s in self.slots:
            if s.entry is not None:
                entries.append(s.entry)
        return entries

    def remove_entry(self, entry_id: int) -> None:
        """Remove an entry by ID from slots or initial."""
        if self.initial_entry is not None and self.initial_entry.entry_id == entry_id:
            self.initial_entry = None
            return
        for s in self.slots:
            if s.entry is not None and s.entry.entry_id == entry_id:
                s.vacate()
                return

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "layer_number": self.layer_number,
            "slots": [s.to_dict() for s in self.slots],
            "initial_entry": self.initial_entry.to_dict() if self.initial_entry else None,
            "base_units": self.base_units,
            "completed": self.completed,
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> Layer:
        raw_initial = d.get("initial_entry")
        return Layer(
            layer_number=_parse_int(d.get("layer_number", 1), 1),
            slots=[Slot.from_dict(s) for s in d.get("slots", [])],
            initial_entry=Entry.from_dict(raw_initial) if raw_initial else None,
            base_units=_parse_int(d.get("base_units", 1000), 1000),
            completed=bool(d.get("completed", False)),
        )

    @staticmethod
    def create(layer_number: int, r_max: int, base_units: int) -> Layer:
        """Create a new layer with ``r_max`` empty slots."""
        return Layer(
            layer_number=layer_number,
            slots=[Slot(index=i + 1) for i in range(r_max)],
            base_units=base_units,
        )


# ---------------------------------------------------------------------------
# Cycle
# ---------------------------------------------------------------------------


@dataclass
class SnowballCycle:
    """A single trading cycle: one initial entry through to its close.

    Each cycle tracks layers of retracement slots and hedge entries.
    """

    cycle_id: int  # = initial entry's entry_id
    direction: Direction
    initial_entry: Entry | None = None
    layers: list[Layer] = field(default_factory=list)
    hedge_entries: list[Entry] = field(default_factory=list)
    counter_close_count: int = 0
    completed: bool = False

    # ------------------------------------------------------------------
    # Layer accessors
    # ------------------------------------------------------------------

    @property
    def current_layer(self) -> Layer | None:
        """Return the most recent (highest-numbered) layer, or None."""
        return self.layers[-1] if self.layers else None

    @property
    def layer_index(self) -> int:
        """0-based index of the current layer (for compatibility)."""
        return len(self.layers) - 1 if self.layers else 0

    def add_layer(self, layer: Layer) -> None:
        self.layers.append(layer)

    # ------------------------------------------------------------------
    # Computed properties
    # ------------------------------------------------------------------

    @property
    def is_long(self) -> bool:
        return self.direction == Direction.LONG

    @property
    def is_short(self) -> bool:
        return self.direction == Direction.SHORT

    # ------------------------------------------------------------------
    # Entry accessors
    # ------------------------------------------------------------------

    def all_entries(self) -> list[Entry]:
        """Return all entries in this cycle (initial + layers + hedge)."""
        entries: list[Entry] = []
        if self.initial_entry is not None:
            entries.append(self.initial_entry)
        for layer in self.layers:
            # layer initial (L2+)
            if layer.initial_entry is not None:
                entries.append(layer.initial_entry)
            for s in layer.slots:
                if s.entry is not None:
                    entries.append(s.entry)
        entries.extend(self.hedge_entries)
        return entries

    def counter_non_hedge(self) -> list[Entry]:
        """Return all counter entries (slot entries) excluding hedges."""
        entries: list[Entry] = []
        for layer in self.layers:
            for s in layer.slots:
                if s.entry is not None and not s.entry.is_hedge:
                    entries.append(s.entry)
        return entries

    def initial_for_layer(self, layer_number: int) -> Entry | None:
        """Return the initial entry for the given layer number."""
        if layer_number == 1:
            return self.initial_entry
        for layer in self.layers:
            if layer.layer_number == layer_number and layer.initial_entry is not None:
                return layer.initial_entry
        return None

    def remove_entry(self, entry_id: int) -> None:
        """Remove an entry by entry_id from layers or hedge lists."""
        for layer in self.layers:
            layer.remove_entry(entry_id)
        self.hedge_entries = [e for e in self.hedge_entries if e.entry_id != entry_id]

    # ------------------------------------------------------------------
    # Backward-compatible properties
    # ------------------------------------------------------------------

    @property
    def counter_entries(self) -> list[Entry]:
        """All slot entries across all layers (for backward compat)."""
        return self.counter_non_hedge()

    @property
    def layer_initial_entries(self) -> dict[int, Entry]:
        """Map of layer_number → layer initial entry (for backward compat)."""
        result: dict[int, Entry] = {}
        for layer in self.layers:
            if layer.initial_entry is not None:
                result[layer.layer_number] = layer.initial_entry
        return result

    @property
    def layer_retracement_count(self) -> int:
        """Number of occupied slots in the current layer."""
        layer = self.current_layer
        if layer is None:
            return 0
        return len(layer.occupied_slots())

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
        initial_entry: Entry | None = None
        if raw_initial:
            initial_entry = Entry.from_dict(raw_initial)

        # New format: layers list
        raw_layers = data.get("layers")
        if raw_layers is not None:
            layers = [Layer.from_dict(ld) for ld in raw_layers]
        else:
            # Legacy format migration: convert counter_entries + layer_initial_entries
            layers = _migrate_legacy_cycle(data)

        return SnowballCycle(
            cycle_id=_parse_int(data.get("cycle_id", 0), 0),
            direction=direction,
            initial_entry=initial_entry,
            layers=layers,
            hedge_entries=[Entry.from_dict(e) for e in data.get("hedge_entries", [])],
            counter_close_count=_parse_int(data.get("counter_close_count", 0), 0),
            completed=bool(data.get("completed", False)),
        )


def _migrate_legacy_cycle(data: dict[str, Any]) -> list[Layer]:
    """Convert old-format cycle data (counter_entries + layer_initial_entries) to layers."""
    counter_entries = [Entry.from_dict(e) for e in data.get("counter_entries", [])]
    raw_layer_initials = data.get("layer_initial_entries", {})
    layer_initials: dict[int, Entry] = {}
    for k, v in raw_layer_initials.items():
        if v:
            layer_initials[int(k)] = Entry.from_dict(v)

    # Group counter entries by layer_number
    by_layer: dict[int, list[Entry]] = {}
    for e in counter_entries:
        ln = e.layer_number
        by_layer.setdefault(ln, []).append(e)

    # Determine all layer numbers
    all_layer_nums = set(by_layer.keys()) | set(layer_initials.keys())
    if not all_layer_nums:
        # At least L1 exists
        r_max = _parse_int(data.get("layer_retracement_count", 0), 0) or 7
        return [Layer.create(1, r_max, _parse_int(data.get("cycle_base_units", 1000), 1000))]

    layers: list[Layer] = []
    for ln in sorted(all_layer_nums):
        entries_for_layer = by_layer.get(ln, [])
        max_ret = max((e.retracement_count for e in entries_for_layer), default=0)
        r_max = max(max_ret, 7)
        layer = Layer.create(ln, r_max, _parse_int(data.get("cycle_base_units", 1000), 1000))
        layer.initial_entry = layer_initials.get(ln)
        # Fill slots
        for e in entries_for_layer:
            idx = e.retracement_count
            if 1 <= idx <= len(layer.slots):
                layer.slots[idx - 1].fill(e)
        layers.append(layer)

    return layers


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


@dataclass
class SnowballStrategyState:
    """Mutable runtime state for Snowball strategy."""

    protection_level: ProtectionLevel = ProtectionLevel.NORMAL
    initialised: bool = False

    # Cycle-based tracking
    cycles: list[SnowballCycle] = field(default_factory=list)

    # Next entry id
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

    # Metrics
    metrics: dict[str, str | int | float] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Convenience accessors
    # ------------------------------------------------------------------

    def allocate_id(self) -> int:
        """Allocate and return the next entry ID."""
        eid = self.next_entry_id
        self.next_entry_id += 1
        return eid

    def active_cycles(self) -> list[SnowballCycle]:
        """Return cycles that are not yet completed."""
        return [c for c in self.cycles if not c.completed]

    def all_entries(self) -> list[Entry]:
        """Return every entry across all active cycles."""
        entries: list[Entry] = []
        for c in self.active_cycles():
            entries.extend(c.all_entries())
        return entries

    def find_cycle(self, cycle_id: int) -> SnowballCycle | None:
        """Find a cycle by its cycle_id."""
        for c in self.cycles:
            if c.cycle_id == cycle_id:
                return c
        return None

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

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
# Private parsing helpers (used only within this module)
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
