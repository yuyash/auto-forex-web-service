"""
Position P&L Updater Module

This module provides utilities for batch updating position P&L calculations
based on current market prices.

Requirements: 9.1, 9.4
"""

import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.db import transaction

from accounts.models import OandaAccount

from .models import Position

logger = logging.getLogger(__name__)


class PositionPnLUpdater:
    """
    Batch updater for position P&L calculations.

    This class:
    - Fetches all open positions for active accounts
    - Calculates P&L based on current market prices
    - Batch updates positions in database
    - Handles multiple currency pair efficiently

    Requirements: 9.1, 9.4
    """

    def __init__(self, account: Optional[OandaAccount] = None):
        """
        Initialize the P&L updater.

        Args:
            account: Optional specific account to update. If None, updates all active accounts.
        """
        self.account = account
        self.updated_count = 0
        self.error_count = 0

    def update_all_positions(self, price_data: Dict[str, Dict[str, Decimal]]) -> Dict[str, Any]:
        """
        Update P&L for all open positions based on current market prices.

        Args:
            price_data: Dictionary mapping instrument to price data
                       Format: {'EUR_USD': {'bid': Decimal('1.1234'), 'ask': Decimal('1.1235')}}

        Returns:
            Dictionary with update statistics and results

        Requirements: 9.1, 9.4
        """
        try:
            # Get all open positions
            if self.account:
                positions = Position.objects.filter(
                    account=self.account, closed_at__isnull=True
                ).select_related("account")
            else:
                positions = Position.objects.filter(closed_at__isnull=True).select_related(
                    "account"
                )

            if not positions.exists():
                logger.debug("No open positions to update")
                return {"success": True, "updated_count": 0, "error_count": 0, "positions": []}

            # Group positions by instrument for efficient processing
            positions_by_instrument: Dict[str, List[Position]] = {}
            for position in positions:
                if position.instrument not in positions_by_instrument:
                    positions_by_instrument[position.instrument] = []
                positions_by_instrument[position.instrument].append(position)

            # Update positions in batch
            updated_positions = []

            with transaction.atomic():
                for instrument, instrument_positions in positions_by_instrument.items():
                    if instrument not in price_data:
                        logger.warning(
                            "No price data available for %s, skipping %d positions",
                            instrument,
                            len(instrument_positions),
                        )
                        continue

                    prices = price_data[instrument]
                    bid = prices.get("bid")
                    ask = prices.get("ask")

                    if not bid or not ask:
                        logger.warning("Invalid price data for %s", instrument)
                        self.error_count += len(instrument_positions)
                        continue

                    # Update each position
                    for position in instrument_positions:
                        try:
                            updated_position = self._update_position_pnl(position, bid, ask)
                            if updated_position:
                                updated_positions.append(updated_position)
                                self.updated_count += 1
                        except Exception as e:  # pylint: disable=broad-exception-caught
                            logger.error("Error updating position %s: %s", position.position_id, e)
                            self.error_count += 1

            logger.info(
                "Updated P&L for %d positions (%d errors)", self.updated_count, self.error_count
            )

            return {
                "success": True,
                "updated_count": self.updated_count,
                "error_count": self.error_count,
                "positions": updated_positions,
            }

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error in batch P&L update: %s", e)
            return {
                "success": False,
                "error": str(e),
                "updated_count": self.updated_count,
                "error_count": self.error_count,
            }

    def _update_position_pnl(
        self, position: Position, bid: Decimal, ask: Decimal
    ) -> Optional[Dict[str, Any]]:
        """
        Update P&L for a single position.

        Args:
            position: Position instance to update
            bid: Current bid price
            ask: Current ask price

        Returns:
            Dictionary with updated position data, or None if no update needed

        Requirements: 9.1, 9.4
        """
        try:
            # Determine the appropriate price for P&L calculation
            # For long positions, use bid (exit price when selling)
            # For short positions, use ask (exit price when buying back)
            current_price = bid if position.direction == "long" else ask

            # Store old P&L for comparison
            old_pnl = position.unrealized_pnl

            # Calculate new unrealized P&L
            position.calculate_unrealized_pnl(current_price)

            # Only save if P&L changed significantly (avoid unnecessary DB writes)
            if abs(position.unrealized_pnl - old_pnl) >= Decimal("0.01"):
                position.save(update_fields=["current_price", "unrealized_pnl"])

                return {
                    "position_id": position.position_id,
                    "instrument": position.instrument,
                    "direction": position.direction,
                    "units": str(position.units),
                    "entry_price": str(position.entry_price),
                    "current_price": str(position.current_price),
                    "unrealized_pnl": str(position.unrealized_pnl),
                    "pnl_change": str(position.unrealized_pnl - old_pnl),
                }

            return None

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error updating position %s: %s", position.position_id, e)
            raise

    def update_positions_for_instrument(
        self, instrument: str, bid: Decimal, ask: Decimal
    ) -> List[Dict[str, Any]]:
        """
        Update P&L for all open positions of a specific instrument.

        This is an optimized method for updating positions when receiving
        a single instrument's price update.

        Args:
            instrument: Currency pair (e.g., 'EUR_USD')
            bid: Current bid price
            ask: Current ask price

        Returns:
            List of updated position data dictionaries

        Requirements: 9.1, 9.4
        """
        try:
            # Get all open positions for this instrument
            if self.account:
                positions = Position.objects.filter(
                    account=self.account, instrument=instrument, closed_at__isnull=True
                )
            else:
                positions = Position.objects.filter(instrument=instrument, closed_at__isnull=True)

            if not positions.exists():
                return []

            updated_positions = []

            with transaction.atomic():
                for position in positions:
                    try:
                        updated_position = self._update_position_pnl(position, bid, ask)
                        if updated_position:
                            updated_positions.append(updated_position)
                            self.updated_count += 1
                    except Exception as e:  # pylint: disable=broad-exception-caught
                        logger.error("Error updating position %s: %s", position.position_id, e)
                        self.error_count += 1

            logger.debug("Updated P&L for %d positions on %s", len(updated_positions), instrument)

            return updated_positions

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error updating positions for %s: %s", instrument, e)
            return []

    def get_statistics(self) -> Dict[str, int]:
        """
        Get update statistics.

        Returns:
            Dictionary with update counts
        """
        return {"updated_count": self.updated_count, "error_count": self.error_count}

    def reset_statistics(self) -> None:
        """
        Reset update statistics.
        """
        self.updated_count = 0
        self.error_count = 0
