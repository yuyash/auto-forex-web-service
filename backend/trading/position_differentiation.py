"""
Position differentiation module for FIFO flexibility.

This module provides automatic unit size adjustment to create unique position sizes,
allowing selective position closing in FIFO-compliant jurisdictions.

Requirements: 8.1, 9.1
"""

import logging
from decimal import Decimal
from typing import Dict, Optional, Tuple

from accounts.models import OandaAccount

logger = logging.getLogger(__name__)


class PositionDifferentiationManager:
    """
    Manage position differentiation for FIFO flexibility.

    This class automatically adjusts order unit sizes to create unique positions,
    allowing traders to selectively close positions even in FIFO jurisdictions.

    Requirements: 8.1, 9.1
    """

    # Pattern types
    PATTERN_INCREMENT = "increment"
    PATTERN_DECREMENT = "decrement"
    PATTERN_ALTERNATING = "alternating"

    # Default values
    DEFAULT_INCREMENT = 1
    MIN_INCREMENT = 1
    MAX_INCREMENT = 100

    def __init__(self, account: OandaAccount):
        """
        Initialize PositionDifferentiationManager.

        Args:
            account: OANDA account to manage position differentiation for
        """
        self.account = account
        self._last_order_sizes: Dict[str, Decimal] = {}
        self._alternating_direction: Dict[str, bool] = {}  # True = increment, False = decrement

    def is_enabled(self) -> bool:
        """
        Check if position differentiation is enabled for this account.

        Returns:
            True if enabled, False otherwise
        """
        return getattr(self.account, "enable_position_differentiation", False)

    def get_increment_amount(self) -> int:
        """
        Get the configured increment amount.

        Returns:
            Increment amount (default: 1)
        """
        increment = getattr(self.account, "position_diff_increment", self.DEFAULT_INCREMENT)
        return max(self.MIN_INCREMENT, min(self.MAX_INCREMENT, increment))

    def get_pattern(self) -> str:
        """
        Get the configured differentiation pattern.

        Returns:
            Pattern type ('increment', 'decrement', or 'alternating')
        """
        pattern = getattr(self.account, "position_diff_pattern", self.PATTERN_INCREMENT)
        if pattern not in [
            self.PATTERN_INCREMENT,
            self.PATTERN_DECREMENT,
            self.PATTERN_ALTERNATING,
        ]:
            return self.PATTERN_INCREMENT
        return pattern

    def adjust_order_units(
        self,
        instrument: str,
        original_units: Decimal,
        min_units: Optional[Decimal] = None,
        max_units: Optional[Decimal] = None,
    ) -> Tuple[Decimal, bool]:
        """
        Adjust order units to create a unique position size.

        Args:
            instrument: Currency pair (e.g., 'EUR_USD')
            original_units: Original order size
            min_units: Minimum allowed order size (optional)
            max_units: Maximum allowed order size (optional)

        Returns:
            Tuple of (adjusted_units, was_adjusted)
        """
        if not self.is_enabled():
            return original_units, False

        # Get configuration
        increment = Decimal(self.get_increment_amount())
        pattern = self.get_pattern()

        # Get last order size for this instrument
        last_size = self._last_order_sizes.get(instrument)

        # Calculate adjusted size based on pattern
        if pattern == self.PATTERN_INCREMENT:
            adjusted_units = self._apply_increment_pattern(original_units, last_size, increment)
        elif pattern == self.PATTERN_DECREMENT:
            adjusted_units = self._apply_decrement_pattern(original_units, last_size, increment)
        else:  # PATTERN_ALTERNATING
            adjusted_units = self._apply_alternating_pattern(
                instrument, original_units, last_size, increment
            )

        # Enforce min/max constraints
        if min_units is not None and adjusted_units < min_units:
            logger.warning(
                "Adjusted units %s below minimum %s for %s, using minimum",
                adjusted_units,
                min_units,
                instrument,
            )
            adjusted_units = min_units

        if max_units is not None and adjusted_units > max_units:
            logger.warning(
                "Adjusted units %s above maximum %s for %s, using maximum",
                adjusted_units,
                max_units,
                instrument,
            )
            adjusted_units = max_units

        # Store the adjusted size for next time
        self._last_order_sizes[instrument] = adjusted_units

        was_adjusted = adjusted_units != original_units

        if was_adjusted:
            logger.info(
                "Position differentiation: adjusted %s units to %s for %s (pattern: %s)",
                original_units,
                adjusted_units,
                instrument,
                pattern,
            )

        return adjusted_units, was_adjusted

    def _apply_increment_pattern(
        self,
        original_units: Decimal,
        last_size: Optional[Decimal],
        increment: Decimal,
    ) -> Decimal:
        """
        Apply increment pattern: each order increases by increment.

        Args:
            original_units: Original order size
            last_size: Last order size for this instrument
            increment: Increment amount

        Returns:
            Adjusted units
        """
        if last_size is None:
            # First order, use original size
            return original_units

        # Increment from last size
        return last_size + increment

    def _apply_decrement_pattern(
        self,
        original_units: Decimal,
        last_size: Optional[Decimal],
        increment: Decimal,
    ) -> Decimal:
        """
        Apply decrement pattern: each order decreases by increment.

        Args:
            original_units: Original order size
            last_size: Last order size for this instrument
            increment: Increment amount

        Returns:
            Adjusted units
        """
        if last_size is None:
            # First order, use original size
            return original_units

        # Decrement from last size
        return last_size - increment

    def _apply_alternating_pattern(
        self,
        instrument: str,
        original_units: Decimal,
        last_size: Optional[Decimal],
        increment: Decimal,
    ) -> Decimal:
        """
        Apply alternating pattern: alternates between increment and decrement.

        Args:
            instrument: Currency pair
            original_units: Original order size
            last_size: Last order size for this instrument
            increment: Increment amount

        Returns:
            Adjusted units
        """
        if last_size is None:
            # First order, use original size and set direction to increment
            self._alternating_direction[instrument] = True
            return original_units

        # Get current direction (True = increment, False = decrement)
        should_increment = self._alternating_direction.get(instrument, True)

        if should_increment:
            adjusted = last_size + increment
        else:
            adjusted = last_size - increment

        # Toggle direction for next time
        self._alternating_direction[instrument] = not should_increment

        return adjusted

    def reset_instrument(self, instrument: str) -> None:
        """
        Reset tracking for a specific instrument.

        This should be called when no open positions exist for the instrument.

        Args:
            instrument: Currency pair to reset
        """
        if instrument in self._last_order_sizes:
            del self._last_order_sizes[instrument]
            logger.info("Reset position differentiation tracking for %s", instrument)

        if instrument in self._alternating_direction:
            del self._alternating_direction[instrument]

    def reset_all(self) -> None:
        """Reset tracking for all instruments."""
        self._last_order_sizes.clear()
        self._alternating_direction.clear()
        logger.info("Reset all position differentiation tracking")

    def get_next_order_size(
        self,
        instrument: str,
        base_units: Decimal,
    ) -> Decimal:
        """
        Preview the next order size without applying it.

        Args:
            instrument: Currency pair
            base_units: Base order size

        Returns:
            Next order size that would be used
        """
        if not self.is_enabled():
            return base_units

        increment = Decimal(self.get_increment_amount())
        pattern = self.get_pattern()
        last_size = self._last_order_sizes.get(instrument)

        if pattern == self.PATTERN_INCREMENT:
            return self._apply_increment_pattern(base_units, last_size, increment)
        if pattern == self.PATTERN_DECREMENT:
            return self._apply_decrement_pattern(base_units, last_size, increment)
        # PATTERN_ALTERNATING
        return self._apply_alternating_pattern(instrument, base_units, last_size, increment)

    def get_last_order_size(self, instrument: str) -> Optional[Decimal]:
        """
        Get the last order size for an instrument.

        Args:
            instrument: Currency pair

        Returns:
            Last order size, or None if no orders yet
        """
        return self._last_order_sizes.get(instrument)
