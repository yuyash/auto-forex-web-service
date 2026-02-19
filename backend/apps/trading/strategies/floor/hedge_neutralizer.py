"""Hedge neutralization logic for Floor strategy volatility protection.

When hedging mode is enabled and ATR spikes above the lock threshold,
instead of closing all positions (which realizes losses), this component
calculates the exact opposite positions needed to bring net exposure to
zero.  The strategy then pauses until volatility subsides, at which point
the hedge pairs are unwound.

Separation of concerns: this module owns *only* the neutralization math.
The strategy decides *when* to call it; the event handler decides *how*
to execute the resulting orders.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class HedgeInstruction:
    """A single hedge order to open."""

    direction: str  # "long" or "short"
    units: int
    layer_index: int
    source_entry_id: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "direction": self.direction,
            "units": self.units,
            "layer_index": self.layer_index,
            "source_entry_id": self.source_entry_id,
        }


class HedgeNeutralizer:
    """Calculate hedge positions needed to neutralize net exposure.

    Given a list of open entries (the ``open_entries`` dicts stored in
    ``FloorStrategyState``), this class computes the minimal set of
    opposite-direction positions that bring the theoretical PnL delta to
    zero for any subsequent price movement.

    The algorithm is intentionally simple: for every open entry, open an
    equal-and-opposite position.  This guarantees that each original
    position is individually hedged, making the unwind on unlock
    straightforward.
    """

    @staticmethod
    def compute_hedge_instructions(
        open_entries: list[dict[str, Any]],
    ) -> list[HedgeInstruction]:
        """Return hedge instructions for each open entry.

        Each open entry gets a mirror position in the opposite direction
        with the same unit size, tagged with the source entry id so the
        unwind logic can pair them.

        Args:
            open_entries: The ``open_entries`` list from FloorStrategyState.

        Returns:
            List of HedgeInstruction, one per open entry.
        """
        instructions: list[HedgeInstruction] = []
        for entry in open_entries:
            direction = str(entry.get("direction", "long")).lower()
            units = abs(int(entry.get("units", 0)))
            if units <= 0:
                continue
            opposite = "short" if direction == "long" else "long"
            instructions.append(
                HedgeInstruction(
                    direction=opposite,
                    units=units,
                    layer_index=int(entry.get("floor_index", 0)),
                    source_entry_id=int(entry.get("entry_id", 0)),
                )
            )
        return instructions

    @staticmethod
    def compute_net_exposure(open_entries: list[dict[str, Any]]) -> Decimal:
        """Return net signed unit exposure (long positive, short negative).

        Useful for diagnostics / assertions after neutralization.
        """
        net = Decimal("0")
        for entry in open_entries:
            direction = str(entry.get("direction", "long")).lower()
            units = abs(int(entry.get("units", 0)))
            if direction == "long":
                net += units
            else:
                net -= units
        return net
