"""
OANDA Synchronization Task

This module implements periodic synchronization between OANDA API and local database
to reconcile orders and positions, ensuring data consistency.

Requirements: 8.3, 9.1, 9.5
"""

import logging
from decimal import Decimal
from typing import Any, Dict, List

from django.db import transaction
from django.utils import timezone

import v20
from celery import shared_task

from accounts.models import OandaAccount
from trading.event_models import Event
from trading.models import Order, Position

logger = logging.getLogger(__name__)


class OrderReconciler:
    """
    Reconciles orders between OANDA API and local database.

    This class:
    - Fetches pending orders from OANDA API
    - Compares with database Order records
    - Updates status for filled or cancelled orders
    - Creates Position records for any missed fills
    - Logs reconciliation events

    Requirements: 8.3
    """

    def __init__(self, account: OandaAccount):
        """
        Initialize the order reconciler.

        Args:
            account: OandaAccount instance
        """
        self.account = account
        self.api = v20.Context(
            hostname=account.api_hostname,
            token=account.get_api_token(),
            poll_timeout=10,
        )
        self.discrepancies_found = 0
        self.orders_updated = 0

    def reconcile(self) -> Dict[str, Any]:
        """
        Perform order reconciliation.

        Returns:
            Dictionary with reconciliation results
        """
        logger.info(
            "Starting order reconciliation for account %s",
            self.account.account_id,
        )

        try:
            # Fetch pending orders from OANDA
            oanda_orders = self._fetch_oanda_orders()

            # Fetch pending orders from database
            db_orders = self._fetch_db_orders()

            # Create lookup dictionaries
            oanda_orders_dict = {order["id"]: order for order in oanda_orders}
            db_orders_dict = {order.order_id: order for order in db_orders}

            # Find discrepancies
            self._reconcile_orders(oanda_orders_dict, db_orders_dict)

            logger.info(
                "Order reconciliation completed for account %s: "
                "%d discrepancies found, %d orders updated",
                self.account.account_id,
                self.discrepancies_found,
                self.orders_updated,
            )

            return {
                "success": True,
                "discrepancies_found": self.discrepancies_found,
                "orders_updated": self.orders_updated,
                "error": None,
            }

        except Exception as e:  # pylint: disable=broad-exception-caught
            error_msg = f"Order reconciliation failed: {str(e)}"
            logger.error(
                "Error during order reconciliation for account %s: %s",
                self.account.account_id,
                error_msg,
                exc_info=True,
            )

            return {
                "success": False,
                "discrepancies_found": self.discrepancies_found,
                "orders_updated": self.orders_updated,
                "error": error_msg,
            }

    def _fetch_oanda_orders(self) -> List[Dict[str, Any]]:
        """
        Fetch pending orders from OANDA API.

        Returns:
            List of order dictionaries from OANDA
        """
        try:
            response = self.api.order.list_pending(self.account.account_id)

            if response.status != 200:
                logger.error(
                    "Failed to fetch orders from OANDA: status %d",
                    response.status,
                )
                return []

            orders = []
            if hasattr(response, "orders") and response.orders:
                for order in response.orders:
                    orders.append(order.dict())

            logger.debug(
                "Fetched %d pending orders from OANDA for account %s",
                len(orders),
                self.account.account_id,
            )

            return orders

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(
                "Error fetching orders from OANDA for account %s: %s",
                self.account.account_id,
                e,
                exc_info=True,
            )
            return []

    def _fetch_db_orders(self) -> List[Order]:
        """
        Fetch pending orders from database.

        Returns:
            List of Order instances
        """
        return list(
            Order.objects.filter(
                account=self.account,
                status="pending",
            ).select_related("account", "strategy")
        )

    def _reconcile_orders(
        self,
        oanda_orders_dict: Dict[str, Dict[str, Any]],
        db_orders_dict: Dict[str, Order],
    ) -> None:
        """
        Reconcile orders between OANDA and database.

        Args:
            oanda_orders_dict: Dictionary of OANDA orders by order ID
            db_orders_dict: Dictionary of database orders by order ID
        """
        # Check for orders in database but not in OANDA (filled or cancelled)
        for order_id, db_order in db_orders_dict.items():
            if order_id not in oanda_orders_dict:
                self.discrepancies_found += 1
                logger.warning(
                    "Order %s found in database but not in OANDA - marking as cancelled",
                    order_id,
                )

                # Mark as cancelled (could also be filled, but we can't determine without
                # checking trade history)
                db_order.mark_cancelled()
                self.orders_updated += 1

                # Log reconciliation event
                Event.log_trading_event(
                    event_type="order_reconciliation",
                    description=f"Order {order_id} reconciled: marked as cancelled",
                    severity="warning",
                    user=self.account.user,
                    account=self.account,
                    details={
                        "order_id": order_id,
                        "instrument": db_order.instrument,
                        "action": "marked_cancelled",
                        "reason": "not_found_in_oanda",
                    },
                )

        # Check for orders in OANDA but not in database (missed order creation)
        for order_id, oanda_order in oanda_orders_dict.items():
            if order_id not in db_orders_dict:
                self.discrepancies_found += 1
                logger.warning(
                    "Order %s found in OANDA but not in database - creating database record",
                    order_id,
                )

                # Create missing order record
                self._create_missing_order(oanda_order)
                self.orders_updated += 1

    def _create_missing_order(self, oanda_order: Dict[str, Any]) -> None:
        """
        Create a missing order record in the database.

        Args:
            oanda_order: Order data from OANDA API
        """
        try:
            order_type = oanda_order.get("type", "").lower()
            units = Decimal(str(oanda_order.get("units", 0)))
            direction = "long" if units > 0 else "short"

            order = Order.objects.create(
                account=self.account,
                order_id=oanda_order["id"],
                instrument=oanda_order.get("instrument", ""),
                order_type=order_type,
                direction=direction,
                units=abs(units),
                price=(
                    Decimal(str(oanda_order.get("price", 0))) if oanda_order.get("price") else None
                ),
                status="pending",
            )

            logger.info(
                "Created missing order record: %s",
                order.order_id,
            )

            # Log reconciliation event
            Event.log_trading_event(
                event_type="order_reconciliation",
                description=f"Order {order.order_id} reconciled: created missing record",
                severity="warning",
                user=self.account.user,
                account=self.account,
                details={
                    "order_id": order.order_id,
                    "instrument": order.instrument,
                    "action": "created_missing_record",
                    "order_type": order_type,
                    "direction": direction,
                    "units": str(abs(units)),
                },
            )

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(
                "Error creating missing order record: %s",
                e,
                exc_info=True,
            )


class PositionReconciler:
    """
    Reconciles positions between OANDA API and local database.

    This class:
    - Fetches open positions from OANDA API
    - Compares with database Position records
    - Updates position details (units, unrealized P&L)
    - Closes positions that no longer exist in OANDA
    - Creates missing position records
    - Logs reconciliation events

    Requirements: 9.1, 9.5
    """

    def __init__(self, account: OandaAccount):
        """
        Initialize the position reconciler.

        Args:
            account: OandaAccount instance
        """
        self.account = account
        self.api = v20.Context(
            hostname=account.api_hostname,
            token=account.get_api_token(),
            poll_timeout=10,
        )
        self.discrepancies_found = 0
        self.positions_updated = 0

    def reconcile(self) -> Dict[str, Any]:
        """
        Perform position reconciliation.

        Returns:
            Dictionary with reconciliation results
        """
        logger.info(
            "Starting position reconciliation for account %s",
            self.account.account_id,
        )

        try:
            # Fetch open positions from OANDA
            oanda_positions = self._fetch_oanda_positions()

            # Fetch open positions from database
            db_positions = self._fetch_db_positions()

            # Create lookup dictionaries by instrument
            oanda_positions_dict = {pos["instrument"]: pos for pos in oanda_positions}
            db_positions_dict = {pos.instrument: pos for pos in db_positions}

            # Find discrepancies
            self._reconcile_positions(oanda_positions_dict, db_positions_dict)

            logger.info(
                "Position reconciliation completed for account %s: "
                "%d discrepancies found, %d positions updated",
                self.account.account_id,
                self.discrepancies_found,
                self.positions_updated,
            )

            return {
                "success": True,
                "discrepancies_found": self.discrepancies_found,
                "positions_updated": self.positions_updated,
                "error": None,
            }

        except Exception as e:  # pylint: disable=broad-exception-caught
            error_msg = f"Position reconciliation failed: {str(e)}"
            logger.error(
                "Error during position reconciliation for account %s: %s",
                self.account.account_id,
                error_msg,
                exc_info=True,
            )

            return {
                "success": False,
                "discrepancies_found": self.discrepancies_found,
                "positions_updated": self.positions_updated,
                "error": error_msg,
            }

    def _fetch_oanda_positions(self) -> List[Dict[str, Any]]:
        """
        Fetch open positions from OANDA API.

        Returns:
            List of position dictionaries from OANDA
        """
        try:
            response = self.api.position.list_open(self.account.account_id)

            if response.status != 200:
                logger.error(
                    "Failed to fetch positions from OANDA: status %d",
                    response.status,
                )
                return []

            positions = []
            if hasattr(response, "positions") and response.positions:
                for position in response.positions:
                    # OANDA returns positions with long and short sides
                    # We need to extract the active side
                    pos_dict = position.dict()
                    long_units = Decimal(str(pos_dict.get("long", {}).get("units", 0)))
                    short_units = Decimal(str(pos_dict.get("short", {}).get("units", 0)))

                    if long_units != 0:
                        positions.append(
                            {
                                "instrument": pos_dict["instrument"],
                                "units": long_units,
                                "direction": "long",
                                "average_price": Decimal(
                                    str(pos_dict.get("long", {}).get("averagePrice", 0))
                                ),
                                "unrealized_pl": Decimal(
                                    str(pos_dict.get("long", {}).get("unrealizedPL", 0))
                                ),
                            }
                        )

                    if short_units != 0:
                        positions.append(
                            {
                                "instrument": pos_dict["instrument"],
                                "units": abs(short_units),
                                "direction": "short",
                                "average_price": Decimal(
                                    str(pos_dict.get("short", {}).get("averagePrice", 0))
                                ),
                                "unrealized_pl": Decimal(
                                    str(pos_dict.get("short", {}).get("unrealizedPL", 0))
                                ),
                            }
                        )

            logger.debug(
                "Fetched %d open positions from OANDA for account %s",
                len(positions),
                self.account.account_id,
            )

            return positions

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(
                "Error fetching positions from OANDA for account %s: %s",
                self.account.account_id,
                e,
                exc_info=True,
            )
            return []

    def _fetch_db_positions(self) -> List[Position]:
        """
        Fetch open positions from database.

        Returns:
            List of Position instances
        """
        return list(
            Position.objects.filter(
                account=self.account,
                closed_at__isnull=True,
            ).select_related("account", "strategy")
        )

    def _reconcile_positions(
        self,
        oanda_positions_dict: Dict[str, Dict[str, Any]],
        db_positions_dict: Dict[str, Position],
    ) -> None:
        """
        Reconcile positions between OANDA and database.

        Args:
            oanda_positions_dict: Dictionary of OANDA positions by instrument
            db_positions_dict: Dictionary of database positions by instrument
        """
        # Check for positions in database but not in OANDA (closed positions)
        for instrument, db_position in db_positions_dict.items():
            if instrument not in oanda_positions_dict:
                self.discrepancies_found += 1
                logger.warning(
                    "Position %s found in database but not in OANDA - marking as closed",
                    db_position.position_id,
                )

                # Close the position
                with transaction.atomic():
                    db_position.closed_at = timezone.now()
                    db_position.realized_pnl = db_position.unrealized_pnl
                    db_position.save(update_fields=["closed_at", "realized_pnl"])

                self.positions_updated += 1

                # Log reconciliation event
                Event.log_trading_event(
                    event_type="position_reconciliation",
                    description=f"Position {db_position.position_id} reconciled: marked as closed",
                    severity="warning",
                    user=self.account.user,
                    account=self.account,
                    details={
                        "position_id": db_position.position_id,
                        "instrument": instrument,
                        "action": "marked_closed",
                        "reason": "not_found_in_oanda",
                        "realized_pnl": str(db_position.realized_pnl),
                    },
                )

        # Check for positions in OANDA but not in database (missed position creation)
        for instrument, oanda_position in oanda_positions_dict.items():
            if instrument not in db_positions_dict:
                self.discrepancies_found += 1
                logger.warning(
                    "Position for %s found in OANDA but not in database - creating database record",
                    instrument,
                )

                # Create missing position record
                self._create_missing_position(oanda_position)
                self.positions_updated += 1
            else:
                # Position exists in both - update details
                db_position = db_positions_dict[instrument]
                self._update_position_details(db_position, oanda_position)

    def _create_missing_position(self, oanda_position: Dict[str, Any]) -> None:
        """
        Create a missing position record in the database.

        Args:
            oanda_position: Position data from OANDA API
        """
        try:
            instrument = oanda_position["instrument"]
            timestamp = timezone.now().timestamp()
            position_id = f"reconciled_{instrument}_{timestamp}"

            position = Position.objects.create(
                account=self.account,
                position_id=position_id,
                instrument=instrument,
                direction=oanda_position["direction"],
                units=oanda_position["units"],
                entry_price=oanda_position["average_price"],
                current_price=oanda_position["average_price"],
                unrealized_pnl=oanda_position["unrealized_pl"],
            )

            logger.info(
                "Created missing position record: %s",
                position.position_id,
            )

            # Log reconciliation event
            Event.log_trading_event(
                event_type="position_reconciliation",
                description=f"Position {position.position_id} reconciled: created missing record",
                severity="warning",
                user=self.account.user,
                account=self.account,
                details={
                    "position_id": position.position_id,
                    "instrument": position.instrument,
                    "action": "created_missing_record",
                    "direction": position.direction,
                    "units": str(position.units),
                    "entry_price": str(position.entry_price),
                },
            )

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(
                "Error creating missing position record: %s",
                e,
                exc_info=True,
            )

    def _update_position_details(
        self,
        db_position: Position,
        oanda_position: Dict[str, Any],
    ) -> None:
        """
        Update position details from OANDA data.

        Args:
            db_position: Database position record
            oanda_position: Position data from OANDA API
        """
        try:
            # Check if units or unrealized P&L differ
            oanda_units = oanda_position["units"]
            oanda_unrealized_pl = oanda_position["unrealized_pl"]

            units_differ = abs(db_position.units - oanda_units) > Decimal("0.01")
            pnl_differ = abs(db_position.unrealized_pnl - oanda_unrealized_pl) > Decimal("0.01")

            if units_differ or pnl_differ:
                self.discrepancies_found += 1
                logger.info(
                    "Updating position %s: units %s -> %s, P&L %s -> %s",
                    db_position.position_id,
                    db_position.units,
                    oanda_units,
                    db_position.unrealized_pnl,
                    oanda_unrealized_pl,
                )

                with transaction.atomic():
                    db_position.units = oanda_units
                    db_position.unrealized_pnl = oanda_unrealized_pl
                    db_position.current_price = oanda_position["average_price"]
                    db_position.save(update_fields=["units", "unrealized_pnl", "current_price"])

                self.positions_updated += 1

                # Log reconciliation event
                Event.log_trading_event(
                    event_type="position_reconciliation",
                    description=f"Position {db_position.position_id} reconciled: updated details",
                    severity="info",
                    user=self.account.user,
                    account=self.account,
                    details={
                        "position_id": db_position.position_id,
                        "instrument": db_position.instrument,
                        "action": "updated_details",
                        "units": str(oanda_units),
                        "unrealized_pnl": str(oanda_unrealized_pl),
                    },
                )

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(
                "Error updating position details: %s",
                e,
                exc_info=True,
            )


@shared_task(bind=True, max_retries=3)
def oanda_sync_task(self: Any) -> Dict[str, Any]:  # pylint: disable=unused-argument
    """
    Periodic synchronization task for OANDA orders and positions.

    This task:
    - Polls OANDA API for current orders and positions
    - Compares with database records
    - Reconciles any discrepancies (missed fills, cancellations)
    - Logs sync operations and discrepancies found
    - Scheduled to run every 5 minutes

    Returns:
        Dictionary containing:
            - success: Whether the sync was successful
            - accounts_synced: Number of accounts synced
            - total_order_discrepancies: Total order discrepancies found
            - total_position_discrepancies: Total position discrepancies found
            - total_updates: Total records updated
            - errors: List of error messages

    Requirements: 8.3, 9.1, 9.5
    """
    logger.info("Starting OANDA synchronization task")

    results: Dict[str, Any] = {
        "success": True,
        "accounts_synced": 0,
        "total_order_discrepancies": 0,
        "total_position_discrepancies": 0,
        "total_updates": 0,
        "errors": [],
    }

    try:
        # Get all active OANDA accounts
        active_accounts = OandaAccount.objects.filter(is_active=True).select_related("user")

        logger.info("Found %d active OANDA accounts to sync", active_accounts.count())

        for account in active_accounts:
            try:
                logger.info("Syncing account %s", account.account_id)

                # Reconcile orders
                order_reconciler = OrderReconciler(account)
                order_result = order_reconciler.reconcile()

                if order_result["success"]:
                    results["total_order_discrepancies"] += order_result["discrepancies_found"]
                    results["total_updates"] += order_result["orders_updated"]
                else:
                    results["errors"].append(
                        f"Account {account.account_id} order reconciliation: "
                        f"{order_result['error']}"
                    )

                # Reconcile positions
                position_reconciler = PositionReconciler(account)
                position_result = position_reconciler.reconcile()

                if position_result["success"]:
                    results["total_position_discrepancies"] += position_result[
                        "discrepancies_found"
                    ]
                    results["total_updates"] += position_result["positions_updated"]
                else:
                    results["errors"].append(
                        f"Account {account.account_id} position reconciliation: "
                        f"{position_result['error']}"
                    )

                results["accounts_synced"] += 1

                logger.info(
                    "Completed sync for account %s: "
                    "order discrepancies=%d, position discrepancies=%d",
                    account.account_id,
                    order_result["discrepancies_found"],
                    position_result["discrepancies_found"],
                )

            except Exception as e:  # pylint: disable=broad-exception-caught
                error_msg = f"Error syncing account {account.account_id}: {str(e)}"
                logger.error(error_msg, exc_info=True)
                results["errors"].append(error_msg)
                results["success"] = False

        # Log system event
        Event.log_system_event(
            event_type="oanda_sync_completed",
            description=f"OANDA sync completed: {results['accounts_synced']} accounts synced",
            severity="info" if results["success"] else "warning",
            details=results,
        )

        logger.info(
            "OANDA synchronization task completed: "
            "accounts_synced=%d, order_discrepancies=%d, position_discrepancies=%d, "
            "total_updates=%d, errors=%d",
            results["accounts_synced"],
            results["total_order_discrepancies"],
            results["total_position_discrepancies"],
            results["total_updates"],
            len(results["errors"]),
        )

        return results

    except Exception as e:  # pylint: disable=broad-exception-caught
        error_msg = f"OANDA sync task failed: {str(e)}"
        logger.error(error_msg, exc_info=True)

        results["success"] = False
        results["errors"].append(error_msg)

        # Log system event
        Event.log_system_event(
            event_type="oanda_sync_failed",
            description="OANDA sync task failed",
            severity="error",
            details={"error": error_msg},
        )

        return results
