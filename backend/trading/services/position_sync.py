"""
Position synchronization service for trading tasks.

This module provides functionality to verify and sync positions stored
in the database with the actual positions on OANDA.

Requirements: 9.1, 9.5
"""

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone

from trading.models import Position
from trading.oanda_api import OandaAPIClient, OandaAPIError
from trading.trading_task_models import TradingTask

logger = logging.getLogger(__name__)


@dataclass
class PositionSyncResult:
    """Result of a position synchronization operation."""

    synced: bool
    positions_checked: int
    positions_updated: int
    positions_closed: int
    positions_missing: int
    errors: list[str]
    details: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "synced": self.synced,
            "positions_checked": self.positions_checked,
            "positions_updated": self.positions_updated,
            "positions_closed": self.positions_closed,
            "positions_missing": self.positions_missing,
            "errors": self.errors,
            "details": self.details,
        }


class PositionSyncService:
    """
    Service for synchronizing positions between database and OANDA.

    This service verifies that open positions in the database are still
    open in OANDA, and updates position data (current_price, unrealized_pnl)
    to match the actual values from OANDA.

    Requirements: 9.1, 9.5
    """

    def __init__(self, trading_task: TradingTask):
        """
        Initialize the position sync service.

        Args:
            trading_task: The trading task to sync positions for
        """
        self.trading_task = trading_task
        self.account = trading_task.oanda_account
        self.oanda_client = OandaAPIClient(self.account)

    def sync_positions(self) -> PositionSyncResult:
        """
        Synchronize positions for the trading task with OANDA.

        This method:
        1. Fetches open trades from OANDA
        2. Compares with open positions in database for this task
        3. Updates position data if changed
        4. Marks positions as closed if they no longer exist in OANDA

        Returns:
            PositionSyncResult with sync statistics and details
        """
        errors: list[str] = []
        details: list[dict[str, Any]] = []
        positions_updated = 0
        positions_closed = 0
        positions_missing = 0

        # Get open positions from database for this task
        db_positions = Position.objects.filter(
            trading_task=self.trading_task,
            closed_at__isnull=True,
        )
        positions_checked = db_positions.count()

        if positions_checked == 0:
            logger.info(
                "No open positions in database for trading task %d",
                self.trading_task.pk,
            )
            return PositionSyncResult(
                synced=True,
                positions_checked=0,
                positions_updated=0,
                positions_closed=0,
                positions_missing=0,
                errors=[],
                details=[{"message": "No open positions to sync"}],
            )

        # Fetch open trades from OANDA
        try:
            oanda_trades = self.oanda_client.get_open_trades()
        except OandaAPIError as e:
            error_msg = f"Failed to fetch trades from OANDA: {str(e)}"
            logger.error(error_msg)
            return PositionSyncResult(
                synced=False,
                positions_checked=positions_checked,
                positions_updated=0,
                positions_closed=0,
                positions_missing=0,
                errors=[error_msg],
                details=[],
            )

        # Build a map of OANDA trade IDs to trade data
        oanda_trade_map: dict[str, dict[str, Any]] = {trade["id"]: trade for trade in oanda_trades}

        logger.info(
            "Syncing %d DB positions against %d OANDA trades for task %d",
            positions_checked,
            len(oanda_trades),
            self.trading_task.pk,
        )

        # Process each database position
        with transaction.atomic():
            for position in db_positions:
                # Extract the OANDA trade ID from position_id (format: "123_POS")
                oanda_trade_id = self._extract_trade_id(position.position_id)

                if oanda_trade_id in oanda_trade_map:
                    # Position exists in OANDA - update if needed
                    oanda_trade = oanda_trade_map[oanda_trade_id]
                    update_result = self._update_position_from_oanda(position, oanda_trade)

                    if update_result["updated"]:
                        positions_updated += 1
                        details.append(update_result)
                else:
                    # Position not found in OANDA - it may have been closed
                    close_result = self._mark_position_closed(position)
                    positions_closed += 1
                    details.append(close_result)
                    logger.warning(
                        "Position %s not found in OANDA, marking as closed",
                        position.position_id,
                    )

        # Check for positions in OANDA that are not in our database
        db_trade_ids = {self._extract_trade_id(p.position_id) for p in db_positions}
        for oanda_trade in oanda_trades:
            if oanda_trade["id"] not in db_trade_ids:
                # This trade exists in OANDA but not in our database for this task
                positions_missing += 1
                details.append(
                    {
                        "action": "missing",
                        "oanda_trade_id": oanda_trade["id"],
                        "instrument": oanda_trade.get("instrument"),
                        "units": str(oanda_trade.get("units")),
                        "message": "Trade exists in OANDA but not in database for this task",
                    }
                )

        sync_success = len(errors) == 0

        logger.info(
            "Position sync completed for task %d: checked=%d, updated=%d, "
            "closed=%d, missing=%d, success=%s",
            self.trading_task.pk,
            positions_checked,
            positions_updated,
            positions_closed,
            positions_missing,
            sync_success,
        )

        return PositionSyncResult(
            synced=sync_success,
            positions_checked=positions_checked,
            positions_updated=positions_updated,
            positions_closed=positions_closed,
            positions_missing=positions_missing,
            errors=errors,
            details=details,
        )

    def _extract_trade_id(self, position_id: str) -> str:
        """
        Extract the OANDA trade ID from the position_id.

        Position IDs are stored as "{trade_id}_POS", so we extract the trade_id.

        Args:
            position_id: Database position ID (e.g., "12345_POS")

        Returns:
            OANDA trade ID (e.g., "12345")
        """
        if position_id.endswith("_POS"):
            return position_id[:-4]
        return position_id

    def _update_position_from_oanda(
        self, position: Position, oanda_trade: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Update a position with data from OANDA if there are differences.

        Args:
            position: Database Position instance
            oanda_trade: Trade data from OANDA API

        Returns:
            Dictionary with update details
        """
        updated_fields: list[str] = []
        changes: dict[str, dict[str, str]] = {}

        # Note: OANDA trades return entry_price, not current_price
        # For current price we'd need to fetch from pricing API
        # We use unrealized_pnl and units to validate position state

        # Check and update unrealized_pnl
        oanda_pnl = oanda_trade.get("unrealized_pnl", Decimal("0"))
        if position.unrealized_pnl != oanda_pnl:
            changes["unrealized_pnl"] = {
                "old": str(position.unrealized_pnl),
                "new": str(oanda_pnl),
            }
            position.unrealized_pnl = oanda_pnl
            updated_fields.append("unrealized_pnl")

        # Check and update units (might change due to partial close)
        oanda_units = oanda_trade.get("units", Decimal("0"))
        if position.units != oanda_units:
            changes["units"] = {
                "old": str(position.units),
                "new": str(oanda_units),
            }
            position.units = oanda_units
            updated_fields.append("units")

        # Check direction
        oanda_direction = oanda_trade.get("direction", "")
        if position.direction != oanda_direction:
            changes["direction"] = {
                "old": position.direction,
                "new": oanda_direction,
            }
            position.direction = oanda_direction
            updated_fields.append("direction")

        if updated_fields:
            position.save(update_fields=updated_fields)
            logger.info(
                "Updated position %s: %s",
                position.position_id,
                changes,
            )

        return {
            "action": "updated" if updated_fields else "unchanged",
            "position_id": position.position_id,
            "updated": len(updated_fields) > 0,
            "changes": changes,
        }

    def _mark_position_closed(self, position: Position) -> dict[str, Any]:
        """
        Mark a position as closed (no longer exists in OANDA).

        This typically happens when a position was closed outside our system
        (e.g., manually via OANDA platform or stop-loss/take-profit triggered).

        Args:
            position: Position to mark as closed

        Returns:
            Dictionary with close details
        """
        old_values = {
            "units": str(position.units),
            "unrealized_pnl": str(position.unrealized_pnl),
        }

        position.closed_at = timezone.now()
        # We don't know the actual exit price, so we leave current_price as is
        # and calculate realized_pnl from current data
        position.realized_pnl = position.unrealized_pnl
        position.save(update_fields=["closed_at", "realized_pnl"])

        logger.info(
            "Marked position %s as closed (not found in OANDA)",
            position.position_id,
        )

        return {
            "action": "closed",
            "position_id": position.position_id,
            "reason": "Position not found in OANDA (may have been closed externally)",
            "previous_values": old_values,
        }


def sync_trading_task_positions(trading_task: TradingTask) -> PositionSyncResult:
    """
    Convenience function to sync positions for a trading task.

    Args:
        trading_task: The trading task to sync positions for

    Returns:
        PositionSyncResult with sync statistics and details
    """
    service = PositionSyncService(trading_task)
    return service.sync_positions()
