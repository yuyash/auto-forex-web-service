"""
OANDA Synchronization Task

This module implements periodic synchronization between OANDA API and local database
to reconcile orders and positions, ensuring data consistency.

Requirements: 8.3, 9.1, 9.5
"""

# pylint: disable=too-many-lines

import logging
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List

from django.db import transaction
from django.utils import timezone

import v20
from celery import shared_task

from accounts.models import OandaAccount, SystemSettings
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
        self.orders_created = 0

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
            oanda_pending_orders = self._fetch_oanda_orders()

            # Fetch pending orders from database
            db_pending_orders = self._fetch_db_orders()

            # Create lookup dictionaries for pending orders
            oanda_orders_dict = {order["id"]: order for order in oanda_pending_orders}
            db_orders_dict = {order.order_id: order for order in db_pending_orders}

            # Reconcile pending orders
            self._reconcile_orders(oanda_orders_dict, db_orders_dict)

            # Fetch and sync completed orders from transaction history
            self._sync_completed_orders()

            logger.info(
                "Order reconciliation completed for account %s: "
                "%d discrepancies found, %d orders updated, %d orders created",
                self.account.account_id,
                self.discrepancies_found,
                self.orders_updated,
                self.orders_created,
            )

            return {
                "success": True,
                "discrepancies_found": self.discrepancies_found,
                "orders_updated": self.orders_updated,
                "orders_created": self.orders_created,
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
                "orders_created": self.orders_created,
                "error": error_msg,
            }

    def _fetch_oanda_orders(self) -> List[Dict[str, Any]]:
        """
        Fetch pending orders from OANDA API.

        Returns:
            List of order dictionaries from OANDA
        """
        try:
            logger.info("Fetching orders from OANDA for account %s", self.account.account_id)
            response = self.api.order.list_pending(self.account.account_id)

            if response.status != 200:
                logger.error(
                    "Failed to fetch orders from OANDA: status %d",
                    response.status,
                )
                return []

            orders = []
            # The response has a 'body' attribute that contains the orders
            oanda_orders = None
            if hasattr(response, "body") and isinstance(response.body, dict):
                oanda_orders = response.body.get("orders", [])
            elif hasattr(response, "orders"):
                oanda_orders = response.orders

            if oanda_orders:
                for order in oanda_orders:
                    # Handle both v20 Order objects and plain dicts
                    if hasattr(order, "dict"):
                        order_dict = order.dict()
                    elif isinstance(order, dict):
                        order_dict = order
                    else:
                        logger.warning("Unknown order type: %s", type(order))
                        continue

                    orders.append(order_dict)

            logger.info(
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

    def _sync_completed_orders(self) -> None:  # pylint: disable=too-many-branches
        """
        Fetch completed orders from OANDA transaction history and sync to database.

        This method fetches ORDER_FILL and ORDER_CANCEL transactions from OANDA
        and creates/updates corresponding order records in the database.
        """
        try:
            # Get system settings for fetch duration
            settings = SystemSettings.objects.first()
            fetch_days = settings.oanda_fetch_duration_days if settings else 365

            # Calculate from_time (fetch_days ago)
            from_time = timezone.now() - timedelta(days=fetch_days)
            from_time_str = from_time.strftime("%Y-%m-%dT%H:%M:%S.000000000Z")

            logger.info(
                "Fetching transaction history from OANDA for account %s (from %s)",
                self.account.account_id,
                from_time_str,
            )

            # Fetch transactions from OANDA using the list method with pagination
            # We'll fetch recent transactions and filter by time
            response = self.api.transaction.list(
                self.account.account_id,
                pageSize=1000,  # Max page size
            )

            if response.status != 200:
                logger.error(
                    "Failed to fetch transactions from OANDA: status %d",
                    response.status,
                )
                return

            all_transactions = []
            if hasattr(response, "body") and isinstance(response.body, dict):
                all_transactions = response.body.get("transactions", [])
            elif hasattr(response, "transactions"):
                all_transactions = response.transactions

            if not all_transactions:
                logger.info("No transactions found in OANDA response")
                return

            logger.info(
                "Fetched %d total transactions from OANDA",
                len(all_transactions),
            )

            # Filter transactions by time range
            transactions = []
            for txn in all_transactions:
                if hasattr(txn, "dict"):
                    txn_dict = txn.dict()
                elif isinstance(txn, dict):
                    txn_dict = txn
                else:
                    continue

                txn_time_str = txn_dict.get("time", "")
                try:
                    txn_time = datetime.fromisoformat(txn_time_str.replace("Z", "+00:00"))
                    if txn_time >= from_time:
                        transactions.append(txn)
                except (ValueError, AttributeError):
                    continue

            logger.info(
                "Filtered to %d transactions in time range",
                len(transactions),
            )

            # Filter for order-related transactions
            order_transactions = []
            for txn in transactions:
                # Handle both v20 Transaction objects and plain dicts
                if hasattr(txn, "dict"):
                    txn_dict = txn.dict()
                elif isinstance(txn, dict):
                    txn_dict = txn
                else:
                    continue

                txn_type = txn_dict.get("type", "")

                # Filter for order fill and cancel transactions
                if txn_type in ["ORDER_FILL", "ORDER_CANCEL", "ORDER_CANCEL_REJECT"]:
                    order_transactions.append(txn_dict)

            logger.info(
                "Found %d order-related transactions (ORDER_FILL, ORDER_CANCEL)",
                len(order_transactions),
            )

            # Process each transaction
            for txn in order_transactions:
                self._process_order_transaction(txn)

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(
                "Error syncing completed orders for account %s: %s",
                self.account.account_id,
                e,
                exc_info=True,
            )

    def _process_order_transaction(self, txn_data: Dict[str, Any]) -> None:
        """
        Process a single order transaction from OANDA.

        Args:
            txn_data: Transaction data from OANDA API
        """
        try:
            txn_type = txn_data.get("type", "")
            order_id = txn_data.get("orderID")

            if not order_id:
                return

            # Check if order already exists in database
            try:
                order = Order.objects.get(order_id=order_id)

                # Update existing order status
                if txn_type == "ORDER_FILL" and order.status != "filled":
                    order.status = "filled"
                    order.filled_at = datetime.fromisoformat(
                        txn_data.get("time", "").replace("Z", "+00:00")
                    )
                    order.save(update_fields=["status", "filled_at"])
                    self.orders_updated += 1

                    logger.info(
                        "Updated order %s status to filled",
                        order_id,
                    )

                elif txn_type == "ORDER_CANCEL" and order.status != "cancelled":
                    order.status = "cancelled"
                    order.save(update_fields=["status"])
                    self.orders_updated += 1

                    logger.info(
                        "Updated order %s status to cancelled",
                        order_id,
                    )

            except Order.DoesNotExist:
                # Order doesn't exist in database, create it
                self._create_order_from_transaction(txn_data)

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(
                "Error processing order transaction %s: %s",
                txn_data.get("id"),
                e,
                exc_info=True,
            )

    def _create_order_from_transaction(self, txn_data: Dict[str, Any]) -> None:
        """
        Create an order record from a transaction.

        Args:
            txn_data: Transaction data from OANDA API
        """
        try:
            txn_type = txn_data.get("type", "")
            order_id = txn_data.get("orderID")

            # Get order details from transaction
            instrument = txn_data.get("instrument", "")
            units = Decimal(str(txn_data.get("units", 0)))
            direction = "long" if units > 0 else "short"

            # Determine order type from transaction
            order_type = "market"  # Default to market
            if "ORDER_FILL" in txn_type:
                # Try to infer from transaction reason
                reason = txn_data.get("reason", "")
                if "LIMIT" in reason:
                    order_type = "limit"
                elif "STOP" in reason:
                    order_type = "stop"

            # Determine status
            status = "filled" if txn_type == "ORDER_FILL" else "cancelled"

            # Get price
            price = None
            if txn_type == "ORDER_FILL":
                price = Decimal(str(txn_data.get("price", 0)))

            # Get timestamp
            filled_at = None
            if txn_type == "ORDER_FILL":
                filled_at = datetime.fromisoformat(txn_data.get("time", "").replace("Z", "+00:00"))

            # Create order record
            Order.objects.create(
                account=self.account,
                order_id=str(order_id),  # Ensure order_id is a string
                instrument=instrument,
                order_type=order_type,
                direction=direction,
                units=abs(units),
                price=price,
                status=status,
                filled_at=filled_at,
            )

            self.orders_created += 1

            logger.info(
                "Created order record from transaction: %s (status: %s)",
                order_id,
                status,
            )

            # Log event
            Event.log_trading_event(
                event_type="order_reconciliation",
                description=f"Order {order_id} created from transaction history",
                severity="info",
                user=self.account.user,
                account=self.account,
                details={
                    "order_id": order_id,
                    "instrument": instrument,
                    "action": "created_from_transaction",
                    "order_type": order_type,
                    "direction": direction,
                    "status": status,
                    "units": str(abs(units)),
                },
            )

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(
                "Error creating order from transaction: %s",
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

            # Create lookup dictionaries
            # OANDA: one position per instrument+direction (aggregated)
            oanda_positions_dict = {
                f"{pos['instrument']}_{pos['direction']}": pos for pos in oanda_positions
            }

            # DB: group positions by instrument+direction (can have multiple per group)
            db_positions_grouped = defaultdict(list)
            for pos in db_positions:
                key = f"{pos.instrument}_{pos.direction}"
                db_positions_grouped[key].append(pos)

            # Find discrepancies
            self._reconcile_positions(oanda_positions_dict, db_positions_grouped)

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

    def _fetch_oanda_positions(self) -> List[Dict[str, Any]]:  # pylint: disable=too-many-branches
        """
        Fetch open positions from OANDA API.

        Returns:
            List of position dictionaries from OANDA
        """
        try:
            logger.info("Fetching positions from OANDA for account %s", self.account.account_id)
            response = self.api.position.list_open(self.account.account_id)

            if response.status != 200:
                logger.error(
                    "Failed to fetch positions from OANDA: status %d",
                    response.status,
                )
                return []

            positions = []
            # The response has a 'body' attribute that contains the positions
            oanda_positions = None
            if hasattr(response, "body") and isinstance(response.body, dict):
                oanda_positions = response.body.get("positions", [])
            elif hasattr(response, "positions"):
                oanda_positions = response.positions

            if oanda_positions:
                for position in oanda_positions:
                    # OANDA returns positions with long and short sides
                    # We need to extract the active side

                    # Handle both v20 Position objects and plain dicts
                    if hasattr(position, "dict"):
                        pos_dict = position.dict()
                    elif isinstance(position, dict):
                        pos_dict = position
                    else:
                        logger.warning("Unknown position type: %s", type(position))
                        continue

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

            logger.info(
                "Fetched %d open positions from OANDA for account %s: %s",
                len(positions),
                self.account.account_id,
                [p["instrument"] for p in positions],
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
        db_positions_grouped: Dict[str, List[Position]],
    ) -> None:
        """
        Reconcile positions between OANDA and database.

        OANDA aggregates all positions for an instrument+direction into one,
        while the database may have multiple positions (layers) for the same instrument+direction.

        Args:
            oanda_positions_dict: Dictionary of OANDA positions by instrument+direction key
            db_positions_grouped: Dictionary of database position lists by instrument+direction key
        """
        # Check for positions in database but not in OANDA (closed positions)
        for key, db_position_list in db_positions_grouped.items():
            if key not in oanda_positions_dict:
                # All positions for this instrument+direction are closed
                self.discrepancies_found += 1
                logger.warning(
                    "Positions for %s found in database but not in OANDA - "
                    "marking %d positions as closed",
                    key,
                    len(db_position_list),
                )

                # Close all positions for this instrument+direction
                for db_position in db_position_list:
                    with transaction.atomic():
                        db_position.closed_at = timezone.now()
                        db_position.realized_pnl = db_position.unrealized_pnl
                        db_position.save(update_fields=["closed_at", "realized_pnl"])

                    self.positions_updated += 1

                    # Log reconciliation event
                    Event.log_trading_event(
                        event_type="position_reconciliation",
                        description=(
                            f"Position {db_position.position_id} reconciled: " "marked as closed"
                        ),
                        severity="warning",
                        user=self.account.user,
                        account=self.account,
                        details={
                            "position_id": db_position.position_id,
                            "instrument": db_position.instrument,
                            "direction": db_position.direction,
                            "action": "marked_closed",
                            "reason": "not_found_in_oanda",
                            "realized_pnl": str(db_position.realized_pnl),
                        },
                    )

        # Check for positions in OANDA but not in database (missed position creation)
        logger.info(
            "Checking OANDA positions against DB: OANDA has %d, DB has %d",
            len(oanda_positions_dict),
            len(db_positions_grouped),
        )

        for key, oanda_position in oanda_positions_dict.items():
            logger.info(
                "Checking %s: in DB = %s",
                key,
                key in db_positions_grouped,
            )

            if key not in db_positions_grouped:
                # No positions in DB for this instrument+direction, create one
                self.discrepancies_found += 1
                logger.warning(
                    "Position for %s found in OANDA but not in database - creating database record",
                    key,
                )

                # Create missing position record
                self._create_missing_position(oanda_position)
                self.positions_updated += 1
            else:
                # Positions exist in both - verify total units match
                db_position_list = db_positions_grouped[key]
                total_db_units = sum(pos.units for pos in db_position_list)
                oanda_units = oanda_position["units"]

                # Check if units match (within tolerance)
                units_match = abs(total_db_units - oanda_units) < Decimal("0.01")

                if not units_match:
                    self.discrepancies_found += 1
                    logger.warning(
                        "Unit mismatch for %s: DB total=%s, OANDA=%s",
                        key,
                        total_db_units,
                        oanda_units,
                    )

                    # Log the discrepancy but don't auto-fix
                    # (could be due to partial fills, pending orders, etc.)
                    Event.log_trading_event(
                        event_type="position_reconciliation",
                        description=f"Unit mismatch detected for {key}",
                        severity="warning",
                        user=self.account.user,
                        account=self.account,
                        details={
                            "instrument_direction": key,
                            "db_total_units": str(total_db_units),
                            "oanda_units": str(oanda_units),
                            "db_position_count": len(db_position_list),
                            "action": "logged_discrepancy",
                        },
                    )

                # Update unrealized P&L for all positions in this group
                for db_position in db_position_list:
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

            logger.info("Created missing position record: %s", position.position_id)

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
def sync_account_task(
    self: Any, account_id: int  # pylint: disable=unused-argument
) -> Dict[str, Any]:
    """
    Periodic synchronization task for a single OANDA account.

    This task:
    - Polls OANDA API for current orders and positions for one account
    - Compares with database records
    - Reconciles any discrepancies (missed fills, cancellations)
    - Logs sync operations and discrepancies found
    - Scheduled to run every 5 minutes per account

    Args:
        account_id: ID of the OandaAccount to sync

    Returns:
        Dictionary containing sync results

    Requirements: 8.3, 9.1, 9.5
    """
    logger.info("Starting OANDA sync for account ID %d", account_id)

    results: Dict[str, Any] = {
        "success": True,
        "account_id": account_id,
        "order_discrepancies": 0,
        "position_discrepancies": 0,
        "total_updates": 0,
        "errors": [],
    }

    try:
        # Get the account
        try:
            account = OandaAccount.objects.select_related("user").get(id=account_id, is_active=True)
        except OandaAccount.DoesNotExist:
            error_msg = f"Account {account_id} not found or not active"
            logger.warning(error_msg)
            results["success"] = False
            results["errors"].append(error_msg)
            return results

        logger.info("Syncing account %s", account.account_id)

        # Reconcile orders
        order_reconciler = OrderReconciler(account)
        order_result = order_reconciler.reconcile()

        if order_result["success"]:
            results["order_discrepancies"] = order_result["discrepancies_found"]
            results["total_updates"] += order_result["orders_updated"]
            results["total_updates"] += order_result.get("orders_created", 0)
        else:
            results["errors"].append(f"Order reconciliation: {order_result['error']}")
            results["success"] = False

        # Reconcile positions
        position_reconciler = PositionReconciler(account)
        position_result = position_reconciler.reconcile()

        if position_result["success"]:
            results["position_discrepancies"] = position_result["discrepancies_found"]
            results["total_updates"] += position_result["positions_updated"]
        else:
            results["errors"].append(f"Position reconciliation: {position_result['error']}")
            results["success"] = False

        logger.info(
            "Completed sync for account %s: order discrepancies=%d, position discrepancies=%d",
            account.account_id,
            results["order_discrepancies"],
            results["position_discrepancies"],
        )

        # Log event
        Event.log_system_event(
            event_type="oanda_account_sync",
            description=f"Account {account.account_id} synced: "
            f"{results['total_updates']} updates",
            severity="info" if results["success"] else "warning",
            details=results,
        )

    except Exception as e:  # pylint: disable=broad-exception-caught
        error_msg = f"Error syncing account {account_id}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        results["errors"].append(error_msg)
        results["success"] = False

    return results


@shared_task(bind=True, max_retries=3)
def oanda_sync_task(self: Any) -> Dict[str, Any]:  # pylint: disable=unused-argument
    """
    Periodic synchronization task for all OANDA accounts.

    This task triggers individual sync tasks for each active account asynchronously.
    Does not wait for subtasks to complete (fire-and-forget pattern).
    Scheduled to run every 5 minutes.

    Returns:
        Dictionary containing:
            - success: Whether tasks were triggered successfully
            - accounts_synced: Number of account sync tasks triggered
            - tasks_triggered: Number of tasks started
            - task_ids: List of Celery task IDs
            - errors: List of error messages

    Requirements: 8.3, 9.1, 9.5
    """
    logger.info("Starting OANDA synchronization task for all accounts")

    results: Dict[str, Any] = {
        "success": True,
        "accounts_synced": 0,
        "tasks_triggered": 0,
        "errors": [],
    }

    try:
        # Get all active OANDA accounts
        active_accounts = OandaAccount.objects.filter(is_active=True).select_related("user")

        logger.info("Found %d active OANDA accounts to sync", active_accounts.count())

        # Trigger individual account sync tasks asynchronously
        task_ids = []
        for account in active_accounts:
            try:
                # Trigger individual account sync task (fire-and-forget)
                account_result = sync_account_task.apply_async(
                    args=[account.id],
                    expires=240,  # Task expires after 4 minutes
                )
                task_ids.append(account_result.id)
                results["accounts_synced"] += 1
                logger.info(
                    "Triggered sync for account %s (task: %s)",
                    account.account_id,
                    account_result.id,
                )

            except Exception as e:  # pylint: disable=broad-exception-caught
                error_msg = f"Error triggering sync for account {account.account_id}: {str(e)}"
                logger.error(error_msg, exc_info=True)
                results["errors"].append(error_msg)
                results["success"] = False

        # Store task IDs in results
        results["task_ids"] = task_ids
        results["tasks_triggered"] = len(task_ids)

        # Log system event
        Event.log_system_event(
            event_type="oanda_sync_triggered",
            description=(
                f"OANDA sync triggered: {results['accounts_synced']} " "account sync tasks started"
            ),
            severity="info" if results["success"] else "warning",
            details=results,
        )

        logger.info(
            "OANDA synchronization task completed: "
            "accounts_synced=%d, tasks_triggered=%d, errors=%d",
            results["accounts_synced"],
            results["tasks_triggered"],
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
