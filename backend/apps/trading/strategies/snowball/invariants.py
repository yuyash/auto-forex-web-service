"""Invariant validation for Snowball strategy state."""

from __future__ import annotations

from dataclasses import dataclass, field

from apps.trading.strategies.snowball.config import SnowballStrategyConfig
from apps.trading.strategies.snowball.cycle_state import SnowballStrategyState


@dataclass(frozen=True, slots=True)
class SnowballInvariantViolation:
    """A single structural state invariant violation."""

    message: str


@dataclass(frozen=True, slots=True)
class SnowballInvariantReport:
    """Result of validating Snowball runtime state."""

    violations: list[SnowballInvariantViolation] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """Return True when no invariant was violated."""
        return not self.violations

    def summary(self) -> str:
        """Return a compact violation summary."""
        return "; ".join(violation.message for violation in self.violations)


class SnowballInvariantValidator:
    """Validate Snowball state shape without mutating strategy state."""

    def __init__(self, *, config: SnowballStrategyConfig) -> None:
        self.config = config

    def validate(self, state: SnowballStrategyState) -> SnowballInvariantReport:
        """Return all structural violations found in *state*."""
        violations: list[SnowballInvariantViolation] = []
        self._validate_cycle_ids(state, violations)
        self._validate_entry_ids(state, violations)
        self._validate_grid_shape(state, violations)
        return SnowballInvariantReport(violations=violations)

    def _validate_cycle_ids(
        self,
        state: SnowballStrategyState,
        violations: list[SnowballInvariantViolation],
    ) -> None:
        seen: set[int] = set()
        for cycle in state.cycles:
            if cycle.cycle_id in seen:
                violations.append(
                    SnowballInvariantViolation(
                        message=f"Duplicate cycle_id {cycle.cycle_id}",
                    )
                )
            seen.add(cycle.cycle_id)

    def _validate_entry_ids(
        self,
        state: SnowballStrategyState,
        violations: list[SnowballInvariantViolation],
    ) -> None:
        seen: set[int] = set()
        for cycle in state.cycles:
            if cycle.completed:
                continue
            for entry in cycle.all_entries():
                if entry.entry_id in seen:
                    violations.append(
                        SnowballInvariantViolation(
                            message=f"Duplicate entry_id {entry.entry_id}",
                        )
                    )
                seen.add(entry.entry_id)

    def _validate_grid_shape(
        self,
        state: SnowballStrategyState,
        violations: list[SnowballInvariantViolation],
    ) -> None:
        expected_slots = self.config.r_max + 1
        for cycle in state.cycles:
            if cycle.completed:
                continue
            if cycle.layer_count > self.config.f_max:
                violations.append(
                    SnowballInvariantViolation(
                        message=(
                            f"Cycle {cycle.cycle_id} has {cycle.layer_count} layers "
                            f"above f_max {self.config.f_max}"
                        ),
                    )
                )
            for layer in cycle.layers:
                if len(layer.slots) != expected_slots:
                    violations.append(
                        SnowballInvariantViolation(
                            message=(
                                f"Cycle {cycle.cycle_id} layer {layer.layer_number} has "
                                f"{len(layer.slots)} slots, expected {expected_slots}"
                            ),
                        )
                    )
                self._validate_layer_slots(
                    cycle_id=cycle.cycle_id, layer=layer, violations=violations
                )

    def _validate_layer_slots(
        self,
        *,
        cycle_id: int,
        layer,
        violations: list[SnowballInvariantViolation],
    ) -> None:
        for slot in layer.slots:
            if slot.entry is not None and slot.pending_rebuild is not None:
                violations.append(
                    SnowballInvariantViolation(
                        message=(
                            f"Cycle {cycle_id} layer {layer.layer_number} slot {slot.index} "
                            "has both live entry and pending rebuild"
                        ),
                    )
                )
            if slot.entry is None:
                continue
            if slot.entry.layer_number != layer.layer_number:
                violations.append(
                    SnowballInvariantViolation(
                        message=(
                            f"Entry {slot.entry.entry_id} layer_number "
                            f"{slot.entry.layer_number} does not match slot layer "
                            f"{layer.layer_number}"
                        ),
                    )
                )
            if slot.entry.retracement_count != slot.index:
                violations.append(
                    SnowballInvariantViolation(
                        message=(
                            f"Entry {slot.entry.entry_id} retracement_count "
                            f"{slot.entry.retracement_count} does not match slot index {slot.index}"
                        ),
                    )
                )
