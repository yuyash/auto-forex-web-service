"""
Smart position differentiation logic for FIFO flexibility.

This module provides intelligent position differentiation that:
- Detects when multiple positions exist in the same instrument
- Automatically suggests enabling position differentiation
- Calculates optimal increment to avoid collisions
- Handles edge cases (reaching min/max order sizes)
- Resets counter when no open positions exist

Requirements: 8.1, 9.1
"""

from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from django.db.models import Count, Q

from accounts.models import OandaAccount

if TYPE_CHECKING:
    from trading.models import Strategy


def _get_position_model() -> Any:
    """Get Position model with lazy import to avoid circular dependency."""
    # pylint: disable=import-outside-toplevel
    from trading.models import Position as PositionModel

    return PositionModel


class PositionDifferentiationManager:
    """
    Manages smart position differentiation for OANDA accounts.

    This class provides logic to automatically detect when position
    differentiation should be enabled and calculates optimal increments
    to avoid position collisions while respecting min/max order sizes.
    """

    # OANDA minimum and maximum order sizes (in units)
    MIN_ORDER_SIZE = 1
    MAX_ORDER_SIZE = 100000000  # 100 million units

    def __init__(self, account: OandaAccount, strategy: Optional["Strategy"] = None):
        """
        Initialize the position differentiation manager.

        Args:
            account: OANDA account to manage
            strategy: Optional Strategy instance for strategy-level settings
        """
        self.account = account
        self.strategy = strategy

    def _get_effective_enabled(self) -> bool:
        """
        Get effective position differentiation enabled setting.

        Strategy-level setting overrides account-level setting.

        Returns:
            True if position differentiation is enabled
        """
        if self.strategy is not None:
            return bool(self.strategy.get_position_diff_enabled())
        return bool(self.account.enable_position_differentiation)

    def _get_effective_increment(self) -> int:
        """
        Get effective position differentiation increment.

        Strategy-level setting overrides account-level setting.

        Returns:
            Increment amount
        """
        if self.strategy is not None:
            return int(self.strategy.get_position_diff_increment())
        return int(self.account.position_diff_increment)

    def _get_effective_pattern(self) -> str:
        """
        Get effective position differentiation pattern.

        Strategy-level setting overrides account-level setting.

        Returns:
            Pattern name
        """
        if self.strategy is not None:
            return str(self.strategy.get_position_diff_pattern())
        return str(self.account.position_diff_pattern)

    def get_pattern(self) -> str:
        """
        Get the current position differentiation pattern.

        Public accessor for the effective pattern setting.

        Returns:
            Pattern name ('increment', 'decrement', or 'alternating')
        """
        return self._get_effective_pattern()

    def get_increment_amount(self) -> int:
        """
        Get the current position differentiation increment amount.

        Public accessor for the effective increment setting.

        Returns:
            Increment amount (1-100)
        """
        return self._get_effective_increment()

    def should_suggest_differentiation(self, instrument: str) -> bool:
        """
        Check if position differentiation should be suggested for an instrument.

        Suggests differentiation when:
        - Multiple open positions exist in the same instrument
        - Position differentiation is not already enabled

        Args:
            instrument: Currency pair (e.g., 'EUR_USD')

        Returns:
            True if differentiation should be suggested, False otherwise
        """
        if self._get_effective_enabled():
            return False

        # Count open positions for this instrument
        PositionModel = _get_position_model()
        open_positions_count = PositionModel.objects.filter(
            account=self.account,
            instrument=instrument,
            closed_at__isnull=True,
        ).count()

        return open_positions_count > 1  # type: ignore[no-any-return]

    def detect_position_collisions(self, instrument: str) -> List[Decimal]:
        """
        Detect positions with identical unit sizes in the same instrument.

        Args:
            instrument: Currency pair (e.g., 'EUR_USD')

        Returns:
            List of unit sizes that have collisions (duplicates)
        """
        # Get all open positions for this instrument
        PositionModel = _get_position_model()
        positions = PositionModel.objects.filter(
            account=self.account,
            instrument=instrument,
            closed_at__isnull=True,
        ).values_list("units", flat=True)

        # Find duplicates
        unit_counts: Dict[Decimal, int] = {}
        for units in positions:
            unit_counts[units] = unit_counts.get(units, 0) + 1

        # Return sizes with collisions
        return [units for units, count in unit_counts.items() if count > 1]

    def calculate_optimal_increment(
        self,
        instrument: str,
        base_size: Decimal,
    ) -> int:
        """
        Calculate optimal increment to avoid position collisions.

        Analyzes existing positions and suggests an increment that:
        - Avoids collisions with existing position sizes
        - Stays within min/max order size boundaries
        - Is as small as possible for minimal impact

        Args:
            instrument: Currency pair (e.g., 'EUR_USD')
            base_size: Base order size in units

        Returns:
            Optimal increment amount (1-100)
        """
        # Get all open position sizes for this instrument
        PositionModel = _get_position_model()
        existing_sizes = set(
            PositionModel.objects.filter(
                account=self.account,
                instrument=instrument,
                closed_at__isnull=True,
            ).values_list("units", flat=True)
        )

        if not existing_sizes:
            # No existing positions, use default increment
            return 1

        # Try increments from 1 to 100
        for increment in range(1, 101):
            # Check if this increment would avoid collisions
            # for the next 10 positions
            collision_found = False
            for i in range(10):
                test_size = base_size + (increment * i)
                if test_size in existing_sizes:
                    collision_found = True
                    break

                # Check if we exceed max order size
                if test_size > self.MAX_ORDER_SIZE:
                    collision_found = True
                    break

            if not collision_found:
                return increment

        # If no optimal increment found, return default
        return 1

    def adjust_order_units(
        self,
        instrument: str,
        original_units: Decimal,
        min_units: Optional[Decimal] = None,
        max_units: Optional[Decimal] = None,
    ) -> Tuple[Decimal, bool]:
        """
        Adjust order units with position differentiation applied.

        This is an alias for get_next_order_size with additional boundary checks.

        Args:
            instrument: Currency pair (e.g., 'EUR_USD')
            original_units: Original order size in units
            min_units: Minimum allowed order size (optional)
            max_units: Maximum allowed order size (optional)

        Returns:
            Tuple of (adjusted_units, was_adjusted)
            - adjusted_units: Order size with differentiation applied
            - was_adjusted: True if size was adjusted, False otherwise
        """
        adjusted_units, was_adjusted = self.get_next_order_size(instrument, original_units)

        # Apply additional min/max constraints if provided
        if min_units is not None:
            adjusted_units = max(min_units, adjusted_units)
        if max_units is not None:
            adjusted_units = min(max_units, adjusted_units)

        return adjusted_units, was_adjusted

    def get_next_order_size(
        self,
        instrument: str,
        base_size: Decimal,
    ) -> Tuple[Decimal, bool]:
        """
        Calculate the next order size with position differentiation applied.

        Args:
            instrument: Currency pair (e.g., 'EUR_USD')
            base_size: Base order size in units

        Returns:
            Tuple of (adjusted_size, was_adjusted)
            - adjusted_size: Order size with differentiation applied
            - was_adjusted: True if size was adjusted, False otherwise
        """
        if not self._get_effective_enabled():
            return base_size, False

        # Get the count of open positions for this instrument
        PositionModel = _get_position_model()
        query_filter = {
            "account": self.account,
            "instrument": instrument,
            "closed_at__isnull": True,
        }

        # If strategy is specified, only count positions for this strategy
        if self.strategy is not None:
            query_filter["strategy"] = self.strategy

        position_count = PositionModel.objects.filter(**query_filter).count()

        # If no open positions, reset to base size
        if position_count == 0:
            return base_size, False

        increment = self._get_effective_increment()
        pattern = self._get_effective_pattern()

        # Calculate adjustment based on pattern
        if pattern == "increment":
            adjustment = increment * position_count
            adjusted_size = base_size + adjustment
        elif pattern == "decrement":
            adjustment = increment * position_count
            adjusted_size = base_size - adjustment
        elif pattern == "alternating":
            # Alternating: +1, -1, +2, -2, +3, -3, ...
            if position_count % 2 == 1:
                # Odd: add
                adjustment = increment * ((position_count + 1) // 2)
                adjusted_size = base_size + adjustment
            else:
                # Even: subtract
                adjustment = increment * (position_count // 2)
                adjusted_size = base_size - adjustment
        else:
            # Unknown pattern, use base size
            return base_size, False

        # Ensure we stay within min/max boundaries
        adjusted_size = max(Decimal(self.MIN_ORDER_SIZE), adjusted_size)
        adjusted_size = min(Decimal(self.MAX_ORDER_SIZE), adjusted_size)

        # Check if we hit a boundary
        if adjusted_size == base_size:
            # We hit a boundary, can't differentiate further
            return base_size, False

        return adjusted_size, True

    def check_boundary_reached(  # pylint: disable=too-many-return-statements
        self,
        instrument: str,
        base_size: Decimal,
    ) -> Optional[str]:
        """
        Check if position differentiation has reached min/max boundaries.

        Args:
            instrument: Currency pair (e.g., 'EUR_USD')
            base_size: Base order size in units

        Returns:
            Warning message if boundary reached, None otherwise
        """
        if not self._get_effective_enabled():
            return None

        next_size, was_adjusted = self.get_next_order_size(instrument, base_size)

        if not was_adjusted:
            return None

        # Check if we're approaching boundaries
        if next_size <= Decimal(self.MIN_ORDER_SIZE):
            return (
                f"Position differentiation has reached minimum order size "
                f"({self.MIN_ORDER_SIZE} units). Further positions will use "
                f"the minimum size."
            )

        if next_size >= Decimal(self.MAX_ORDER_SIZE):
            return (
                f"Position differentiation has reached maximum order size "
                f"({self.MAX_ORDER_SIZE} units). Further positions will use "
                f"the maximum size."
            )

        # Check if we're within 10% of boundaries
        if next_size <= Decimal(self.MIN_ORDER_SIZE * 1.1):
            return (
                f"Warning: Position differentiation is approaching minimum "
                f"order size. Next size: {next_size} units."
            )

        if next_size >= Decimal(self.MAX_ORDER_SIZE * 0.9):
            return (
                f"Warning: Position differentiation is approaching maximum "
                f"order size. Next size: {next_size} units."
            )

        return None

    def get_differentiation_suggestion(
        self,
        instrument: str,
        base_size: Decimal,
    ) -> Optional[Dict[str, Any]]:
        """
        Get a suggestion for enabling position differentiation.

        Args:
            instrument: Currency pair (e.g., 'EUR_USD')
            base_size: Base order size in units

        Returns:
            Dictionary with suggestion details, or None if no suggestion
        """
        if not self.should_suggest_differentiation(instrument):
            return None

        # Detect collisions
        collisions = self.detect_position_collisions(instrument)

        # Calculate optimal increment
        optimal_increment = self.calculate_optimal_increment(instrument, base_size)

        # Get position count
        PositionModel = _get_position_model()
        position_count = PositionModel.objects.filter(
            account=self.account,
            instrument=instrument,
            closed_at__isnull=True,
        ).count()

        return {
            "instrument": instrument,
            "position_count": position_count,
            "has_collisions": len(collisions) > 0,
            "collision_sizes": [float(size) for size in collisions],
            "suggested_increment": optimal_increment,
            "suggested_pattern": "increment",
            "message": (
                f"Multiple positions detected in {instrument}. "
                f"Enable position differentiation to allow selective closing? "
                f"Suggested increment: {optimal_increment} units."
            ),
        }

    def reset_counter_if_needed(self, instrument: str) -> bool:
        """
        Reset position counter if no open positions exist.

        This is called automatically when checking for the next order size.
        The counter is implicitly reset by returning the base size when
        position_count is 0.

        Args:
            instrument: Currency pair (e.g., 'EUR_USD')

        Returns:
            True if counter was reset (no open positions), False otherwise
        """
        PositionModel = _get_position_model()
        position_count = PositionModel.objects.filter(
            account=self.account,
            instrument=instrument,
            closed_at__isnull=True,
        ).count()

        return position_count == 0  # type: ignore[no-any-return]

    def get_statistics(self, instrument: Optional[str] = None) -> Dict[str, Any]:
        """
        Get position differentiation statistics.

        Args:
            instrument: Optional currency pair to filter by

        Returns:
            Dictionary with statistics
        """
        PositionModel = _get_position_model()
        query = Q(account=self.account, closed_at__isnull=True)
        if instrument:
            query &= Q(instrument=instrument)
        if self.strategy is not None:
            query &= Q(strategy=self.strategy)

        positions = PositionModel.objects.filter(query)

        # Count positions by instrument
        by_instrument = (
            positions.values("instrument").annotate(count=Count("id")).order_by("-count")
        )

        # Find instruments with collisions
        instruments_with_collisions = []
        for item in by_instrument:
            inst = item["instrument"]
            collisions = self.detect_position_collisions(inst)
            if collisions:
                instruments_with_collisions.append(
                    {
                        "instrument": inst,
                        "position_count": item["count"],
                        "collision_sizes": [float(size) for size in collisions],
                    }
                )

        return {
            "enabled": self._get_effective_enabled(),
            "increment": self._get_effective_increment(),
            "pattern": self._get_effective_pattern(),
            "strategy_level": self.strategy is not None,
            "total_open_positions": positions.count(),
            "positions_by_instrument": list(by_instrument),
            "instruments_with_collisions": instruments_with_collisions,
        }
