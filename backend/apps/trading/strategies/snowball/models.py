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
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Literal

from apps.trading.enums import Direction
from apps.trading.strategies.snowball.enums import CycleStatus, ProtectionLevel
from apps.trading.strategies.snowball.state_parsing import (
    optional_decimal,
    optional_int,
    optional_str,
    parse_datetime,
    require,
    require_dict,
    require_list,
    strict_bool,
    strict_decimal,
    strict_int,
)

if TYPE_CHECKING:
    from apps.trading.dataclasses.tick import Tick


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
        d = require_dict(d, field_name="entry")
        raw_direction = require(d, "direction")
        direction = (
            raw_direction
            if isinstance(raw_direction, Direction)
            else Direction(str(raw_direction).strip().lower())
        )
        opened_at = parse_datetime(require(d, "opened_at"), field_name="opened_at")

        return Entry(
            entry_id=strict_int(require(d, "entry_id"), field_name="entry_id"),
            step=strict_int(require(d, "step"), field_name="step"),
            direction=direction,
            entry_price=strict_decimal(require(d, "entry_price"), field_name="entry_price"),
            close_price=strict_decimal(require(d, "close_price"), field_name="close_price"),
            units=strict_int(require(d, "units"), field_name="units"),
            opened_at=opened_at,
            role=require(d, "role"),
            layer_number=strict_int(require(d, "layer_number"), field_name="layer_number"),
            retracement_count=strict_int(
                require(d, "retracement_count"),
                field_name="retracement_count",
            ),
            root_entry_id=optional_int(d, "root_entry_id"),
            parent_entry_id=optional_int(d, "parent_entry_id"),
            position_id=optional_str(d, "position_id"),
            expected_interval_pips=optional_decimal(d, "expected_interval_pips"),
            actual_interval_pips=optional_decimal(d, "actual_interval_pips"),
            expected_tp_pips=optional_decimal(d, "expected_tp_pips"),
            validation_status=str(require(d, "validation_status")),
            stop_loss_price=optional_decimal(d, "stop_loss_price"),
            is_rebuild=strict_bool(require(d, "is_rebuild"), field_name="is_rebuild"),
            lifecycle_realized_pnl=strict_decimal(
                require(d, "lifecycle_realized_pnl"),
                field_name="lifecycle_realized_pnl",
            ),
            lifecycle_stop_loss_count=strict_int(
                require(d, "lifecycle_stop_loss_count"),
                field_name="lifecycle_stop_loss_count",
            ),
        )


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
        d = require_dict(d, field_name="pending_rebuild")
        raw_dir = require(d, "direction")
        direction = (
            raw_dir if isinstance(raw_dir, Direction) else Direction(str(raw_dir).strip().lower())
        )
        return StopLossClosedEntry(
            entry_price=strict_decimal(require(d, "entry_price"), field_name="entry_price"),
            close_price=strict_decimal(require(d, "close_price"), field_name="close_price"),
            units=strict_int(require(d, "units"), field_name="units"),
            direction=direction,
            role=require(d, "role"),
            layer_number=strict_int(require(d, "layer_number"), field_name="layer_number"),
            retracement_count=strict_int(
                require(d, "retracement_count"),
                field_name="retracement_count",
            ),
            step=strict_int(require(d, "step"), field_name="step"),
            root_entry_id=optional_int(d, "root_entry_id"),
            parent_entry_id=optional_int(d, "parent_entry_id"),
            cycle_id=strict_int(require(d, "cycle_id"), field_name="cycle_id"),
            position_id=optional_str(d, "position_id"),
            stop_loss_price=optional_decimal(d, "stop_loss_price"),
            lifecycle_realized_pnl=strict_decimal(
                require(d, "lifecycle_realized_pnl"),
                field_name="lifecycle_realized_pnl",
            ),
            lifecycle_stop_loss_count=strict_int(
                require(d, "lifecycle_stop_loss_count"),
                field_name="lifecycle_stop_loss_count",
            ),
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
        d = require_dict(d, field_name="slot")
        raw_entry = d.get("entry")
        raw_pending = d.get("pending_rebuild")
        return Slot(
            index=strict_int(require(d, "index"), field_name="index"),
            entry=Entry.from_dict(raw_entry) if raw_entry else None,
            ever_closed=strict_bool(require(d, "ever_closed"), field_name="ever_closed"),
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
        d = require_dict(d, field_name="layer")
        return Layer(
            layer_number=strict_int(require(d, "layer_number"), field_name="layer_number"),
            slots=[
                Slot.from_dict(s) for s in require_list(require(d, "slots"), field_name="slots")
            ],
            base_units=strict_int(require(d, "base_units"), field_name="base_units"),
            refill_up_to=strict_int(require(d, "refill_up_to"), field_name="refill_up_to"),
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
        data = require_dict(data, field_name="grid")
        raw_layers = require_list(require(data, "layers"), field_name="layers")
        layers = [Layer.from_dict(ld) for ld in raw_layers]
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
        data = require_dict(data, field_name="cycle")
        raw_direction = require(data, "direction")
        direction = (
            raw_direction
            if isinstance(raw_direction, Direction)
            else Direction(str(raw_direction).strip().lower())
        )

        grid = PositionGrid.from_dict(require(data, "grid"))

        raw_status = require(data, "status")
        status = CycleStatus(str(raw_status).strip().lower())

        return SnowballCycle(
            cycle_id=strict_int(require(data, "cycle_id"), field_name="cycle_id"),
            direction=direction,
            grid=grid,
            hedge_entries=[
                Entry.from_dict(e)
                for e in require_list(require(data, "hedge_entries"), field_name="hedge_entries")
            ],
            counter_close_count=strict_int(
                require(data, "counter_close_count"),
                field_name="counter_close_count",
            ),
            status=status,
            trade_cycle_id=optional_str(data, "trade_cycle_id"),
            realized_pnl=strict_decimal(require(data, "realized_pnl"), field_name="realized_pnl"),
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
        data = require_dict(data, field_name="strategy_state")
        raw_cycles = require_list(require(data, "cycles"), field_name="cycles")
        cycles = [SnowballCycle.from_dict(c) for c in raw_cycles]
        raw_metrics = require(data, "metrics")
        if not isinstance(raw_metrics, dict):
            raise ValueError("Snowball state field metrics must be an object")

        return SnowballStrategyState(
            protection_level=ProtectionLevel(require(data, "protection_level")),
            initialised=strict_bool(require(data, "initialised"), field_name="initialised"),
            cycles=cycles,
            next_entry_id=max(
                1, strict_int(require(data, "next_entry_id"), field_name="next_entry_id")
            ),
            lock_hedge_ids=[
                strict_int(i, field_name="lock_hedge_ids")
                for i in require_list(require(data, "lock_hedge_ids"), field_name="lock_hedge_ids")
            ],
            lock_entered_at=optional_str(data, "lock_entered_at"),
            cooldown_until=optional_str(data, "cooldown_until"),
            last_bid=optional_decimal(data, "last_bid"),
            last_ask=optional_decimal(data, "last_ask"),
            last_mid=optional_decimal(data, "last_mid"),
            account_balance=strict_decimal(
                require(data, "account_balance"),
                field_name="account_balance",
            ),
            account_nav=strict_decimal(require(data, "account_nav"), field_name="account_nav"),
            metrics=dict(raw_metrics),
        )

    @classmethod
    def from_strategy_state(cls, raw: dict[str, Any] | None) -> "SnowballStrategyState":
        if raw is None or raw == {}:
            return cls()
        if not isinstance(raw, dict):
            raise ValueError("Snowball strategy_state must be an object")
        return cls.from_dict(raw)
