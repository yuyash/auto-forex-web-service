"""Decision objects for Snowball tick processing."""

from __future__ import annotations

from dataclasses import dataclass

from apps.trading.strategies.snowball.cycle_state import SnowballStrategyState
from apps.trading.strategies.snowball.invariants import SnowballInvariantValidator


@dataclass(frozen=True, slots=True)
class SnowballDecision:
    """A strategy-level decision made before or after tick processing."""

    should_stop: bool = False
    stop_reason: str = ""
    is_error: bool = False


class SnowballDecisionEngine:
    """Centralize Snowball stop decisions that are not tied to one grid action."""

    fatal_invariant_markers = (
        "Duplicate cycle_id",
        "has both live entry and pending rebuild",
    )

    def __init__(self, *, invariant_validator: SnowballInvariantValidator) -> None:
        self.invariant_validator = invariant_validator

    def invariant_decision(self, state: SnowballStrategyState) -> SnowballDecision:
        """Return a stop decision when strategy state violates structural invariants."""
        report = self.invariant_validator.validate(state)
        if report.ok:
            return SnowballDecision()
        fatal_violations = [
            violation
            for violation in report.violations
            if any(marker in violation.message for marker in self.fatal_invariant_markers)
        ]
        if not fatal_violations:
            return SnowballDecision()
        return SnowballDecision(
            should_stop=True,
            stop_reason=(
                "Snowball state invariant violation: "
                + "; ".join(violation.message for violation in fatal_violations)
            ),
            is_error=True,
        )
