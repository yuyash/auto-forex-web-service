"""
OANDA API direct client for fetching orders, positions, and account details.

This module provides direct API calls to OANDA without database caching,
replacing the sync-based approach with real-time API queries.

Requirements: 8.1, 8.2, 9.1
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

import v20

from accounts.models import OandaAccount

logger = logging.getLogger(__name__)


class OandaAPIError(Exception):
    """Exception raised when OANDA API call fails."""


class OandaAPIClient:
    """
    Direct client for OANDA v20 API.

    Provides methods to fetch orders, positions, and account details
    directly from OANDA without database caching.
    """

    def __init__(self, account: OandaAccount):
        """
        Initialize OANDA API client.

        Args:
            account: OandaAccount instance with API credentials
        """
        self.account = account
        self.api = v20.Context(
            hostname=account.api_hostname,
            token=account.get_api_token(),
            poll_timeout=10,
        )

    def get_account_details(self) -> Dict[str, Any]:
        """
        Fetch account details from OANDA API.

        Returns:
            Dictionary with account details including balance, margin, etc.

        Raises:
            OandaAPIError: If API call fails
        """
        try:
            response = self.api.account.get(self.account.account_id)

            if response.status != 200:
                raise OandaAPIError(f"Failed to fetch account details: status {response.status}")

            account_data = response.body.get("account", {})

            return {
                "account_id": self.account.account_id,
                "balance": Decimal(str(account_data.get("balance", "0"))),
                "unrealized_pl": Decimal(str(account_data.get("unrealizedPL", "0"))),
                "nav": Decimal(str(account_data.get("NAV", "0"))),
                "margin_used": Decimal(str(account_data.get("marginUsed", "0"))),
                "margin_available": Decimal(str(account_data.get("marginAvailable", "0"))),
                "position_value": Decimal(str(account_data.get("positionValue", "0"))),
                "open_trade_count": int(account_data.get("openTradeCount", 0)),
                "open_position_count": int(account_data.get("openPositionCount", 0)),
                "pending_order_count": int(account_data.get("pendingOrderCount", 0)),
                "currency": account_data.get("currency", "USD"),
                "last_transaction_id": account_data.get("lastTransactionID", ""),
            }

        except v20.V20Error as e:
            logger.error(
                "OANDA API error fetching account details for %s: %s",
                self.account.account_id,
                str(e),
            )
            raise OandaAPIError(f"OANDA API error: {str(e)}") from e
        except Exception as e:
            logger.error(
                "Error fetching account details for %s: %s",
                self.account.account_id,
                str(e),
                exc_info=True,
            )
            raise OandaAPIError(f"Error fetching account details: {str(e)}") from e

    def get_open_positions(self, instrument: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetch open positions from OANDA API.

        Args:
            instrument: Optional filter by instrument (e.g., 'EUR_USD')

        Returns:
            List of position dictionaries

        Raises:
            OandaAPIError: If API call fails
        """
        try:
            response = self.api.position.list_open(self.account.account_id)

            if response.status != 200:
                raise OandaAPIError(f"Failed to fetch positions: status {response.status}")

            positions = []
            oanda_positions = response.body.get("positions", [])

            for pos in oanda_positions:
                # OANDA returns positions with long and short sub-objects
                pos_instrument = pos.get("instrument", "")

                if instrument and pos_instrument != instrument:
                    continue

                # Process long position if exists
                long_data = pos.get("long", {})
                if long_data.get("units") and Decimal(str(long_data["units"])) > 0:
                    positions.append(self._format_position(pos_instrument, "long", long_data))

                # Process short position if exists
                short_data = pos.get("short", {})
                if short_data.get("units") and Decimal(str(short_data["units"])) < 0:
                    positions.append(self._format_position(pos_instrument, "short", short_data))

            logger.info(
                "Fetched %d open positions from OANDA for account %s",
                len(positions),
                self.account.account_id,
            )

            return positions

        except v20.V20Error as e:
            logger.error(
                "OANDA API error fetching positions for %s: %s",
                self.account.account_id,
                str(e),
            )
            raise OandaAPIError(f"OANDA API error: {str(e)}") from e
        except Exception as e:
            logger.error(
                "Error fetching positions for %s: %s",
                self.account.account_id,
                str(e),
                exc_info=True,
            )
            raise OandaAPIError(f"Error fetching positions: {str(e)}") from e

    def _format_position(
        self, instrument: str, direction: str, pos_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Format OANDA position data to standard format.

        Args:
            instrument: Currency pair
            direction: 'long' or 'short'
            pos_data: OANDA position data

        Returns:
            Formatted position dictionary
        """
        units = Decimal(str(pos_data.get("units", "0")))
        avg_price = Decimal(str(pos_data.get("averagePrice", "0")))
        unrealized_pl = Decimal(str(pos_data.get("unrealizedPL", "0")))

        # Get trade IDs for this position
        trade_ids = pos_data.get("tradeIDs", [])

        return {
            "instrument": instrument,
            "direction": direction,
            "units": abs(units),
            "average_price": avg_price,
            "unrealized_pnl": unrealized_pl,
            "trade_ids": trade_ids,
            "account_id": self.account.account_id,
        }

    def get_open_trades(self, instrument: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetch open trades from OANDA API.

        Trades are individual position entries, while positions are aggregated.

        Args:
            instrument: Optional filter by instrument

        Returns:
            List of trade dictionaries

        Raises:
            OandaAPIError: If API call fails
        """
        try:
            response = self.api.trade.list_open(self.account.account_id)

            if response.status != 200:
                raise OandaAPIError(f"Failed to fetch trades: status {response.status}")

            trades = []
            oanda_trades = response.body.get("trades", [])

            for trade in oanda_trades:
                trade_instrument = trade.get("instrument", "")

                if instrument and trade_instrument != instrument:
                    continue

                units = Decimal(str(trade.get("currentUnits", "0")))

                trades.append(
                    {
                        "id": trade.get("id", ""),
                        "instrument": trade_instrument,
                        "direction": "long" if units > 0 else "short",
                        "units": abs(units),
                        "entry_price": Decimal(str(trade.get("price", "0"))),
                        "unrealized_pnl": Decimal(str(trade.get("unrealizedPL", "0"))),
                        "open_time": trade.get("openTime", ""),
                        "state": trade.get("state", ""),
                        "account_id": self.account.account_id,
                    }
                )

            logger.info(
                "Fetched %d open trades from OANDA for account %s",
                len(trades),
                self.account.account_id,
            )

            return trades

        except v20.V20Error as e:
            logger.error(
                "OANDA API error fetching trades for %s: %s",
                self.account.account_id,
                str(e),
            )
            raise OandaAPIError(f"OANDA API error: {str(e)}") from e
        except Exception as e:
            logger.error(
                "Error fetching trades for %s: %s",
                self.account.account_id,
                str(e),
                exc_info=True,
            )
            raise OandaAPIError(f"Error fetching trades: {str(e)}") from e

    def get_pending_orders(self, instrument: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetch pending orders from OANDA API.

        Args:
            instrument: Optional filter by instrument

        Returns:
            List of order dictionaries

        Raises:
            OandaAPIError: If API call fails
        """
        try:
            response = self.api.order.list_pending(self.account.account_id)

            if response.status != 200:
                raise OandaAPIError(f"Failed to fetch pending orders: status {response.status}")

            orders = []
            oanda_orders = response.body.get("orders", [])

            for order in oanda_orders:
                order_instrument = order.get("instrument", "")

                if instrument and order_instrument != instrument:
                    continue

                orders.append(self._format_order(order))

            logger.info(
                "Fetched %d pending orders from OANDA for account %s",
                len(orders),
                self.account.account_id,
            )

            return orders

        except v20.V20Error as e:
            logger.error(
                "OANDA API error fetching pending orders for %s: %s",
                self.account.account_id,
                str(e),
            )
            raise OandaAPIError(f"OANDA API error: {str(e)}") from e
        except Exception as e:
            logger.error(
                "Error fetching pending orders for %s: %s",
                self.account.account_id,
                str(e),
                exc_info=True,
            )
            raise OandaAPIError(f"Error fetching pending orders: {str(e)}") from e

    def get_order_history(
        self,
        instrument: Optional[str] = None,
        count: int = 50,
        state: str = "ALL",
    ) -> List[Dict[str, Any]]:
        """
        Fetch order history from OANDA API.

        Args:
            instrument: Optional filter by instrument
            count: Maximum number of orders to return (default: 50)
            state: Order state filter ('ALL', 'PENDING', 'FILLED', 'CANCELLED')

        Returns:
            List of order dictionaries

        Raises:
            OandaAPIError: If API call fails
        """
        try:
            kwargs: Dict[str, Any] = {"count": count, "state": state}
            if instrument:
                kwargs["instrument"] = instrument

            response = self.api.order.list(self.account.account_id, **kwargs)

            if response.status != 200:
                raise OandaAPIError(f"Failed to fetch order history: status {response.status}")

            orders = []
            oanda_orders = response.body.get("orders", [])

            for order in oanda_orders:
                orders.append(self._format_order(order))

            logger.info(
                "Fetched %d orders from OANDA history for account %s",
                len(orders),
                self.account.account_id,
            )

            return orders

        except v20.V20Error as e:
            logger.error(
                "OANDA API error fetching order history for %s: %s",
                self.account.account_id,
                str(e),
            )
            raise OandaAPIError(f"OANDA API error: {str(e)}") from e
        except Exception as e:
            logger.error(
                "Error fetching order history for %s: %s",
                self.account.account_id,
                str(e),
                exc_info=True,
            )
            raise OandaAPIError(f"Error fetching order history: {str(e)}") from e

    def _format_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format OANDA order data to standard format.

        Args:
            order: OANDA order data

        Returns:
            Formatted order dictionary
        """
        order_type = order.get("type", "").lower()
        units = order.get("units", "0")

        # Handle different order types
        if units:
            units_decimal = Decimal(str(units))
            direction = "long" if units_decimal > 0 else "short"
            units_abs = abs(units_decimal)
        else:
            direction = "unknown"
            units_abs = Decimal("0")

        return {
            "id": order.get("id", ""),
            "instrument": order.get("instrument", ""),
            "type": order_type,
            "direction": direction,
            "units": units_abs,
            "price": Decimal(str(order.get("price", "0"))) if order.get("price") else None,
            "state": order.get("state", ""),
            "time_in_force": order.get("timeInForce", ""),
            "create_time": order.get("createTime", ""),
            "fill_time": order.get("filledTime"),
            "cancel_time": order.get("cancelledTime"),
            "filled_units": (
                Decimal(str(order.get("filledUnits", "0"))) if order.get("filledUnits") else None
            ),
            "account_id": self.account.account_id,
            "stop_loss_on_fill": order.get("stopLossOnFill"),
            "take_profit_on_fill": order.get("takeProfitOnFill"),
        }

    def get_transaction_history(
        self,
        from_time: Optional[datetime] = None,
        to_time: Optional[datetime] = None,
        page_size: int = 100,
        transaction_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch transaction history from OANDA API.

        Args:
            from_time: Start time for transactions
            to_time: End time for transactions
            page_size: Number of transactions per page
            transaction_type: Filter by transaction type

        Returns:
            List of transaction dictionaries

        Raises:
            OandaAPIError: If API call fails
        """
        try:
            kwargs: Dict[str, Any] = {"pageSize": page_size}
            if from_time:
                kwargs["from"] = from_time.isoformat()
            if to_time:
                kwargs["to"] = to_time.isoformat()
            if transaction_type:
                kwargs["type"] = transaction_type

            response = self.api.transaction.list(self.account.account_id, **kwargs)

            if response.status != 200:
                raise OandaAPIError(f"Failed to fetch transactions: status {response.status}")

            # Get transaction IDs and fetch details
            pages = response.body.get("pages", [])
            transactions = []

            for _page_url in pages[:5]:  # Limit to 5 pages to avoid too many API calls
                # Parse transaction IDs from page URL
                # The page URLs contain transaction ID ranges
                page_response = self.api.transaction.range(
                    self.account.account_id,
                    **kwargs,
                )
                if page_response.status == 200:
                    txns = page_response.body.get("transactions", [])
                    transactions.extend(txns)

            return transactions

        except v20.V20Error as e:
            logger.error(
                "OANDA API error fetching transactions for %s: %s",
                self.account.account_id,
                str(e),
            )
            raise OandaAPIError(f"OANDA API error: {str(e)}") from e
        except Exception as e:
            logger.error(
                "Error fetching transactions for %s: %s",
                self.account.account_id,
                str(e),
                exc_info=True,
            )
            raise OandaAPIError(f"Error fetching transactions: {str(e)}") from e

    def close_trade(self, trade_id: str, units: Optional[Decimal] = None) -> Dict[str, Any]:
        """
        Close a trade (position) via OANDA API.

        Args:
            trade_id: OANDA trade ID to close
            units: Optional number of units to close (partial close)

        Returns:
            Close transaction details

        Raises:
            OandaAPIError: If API call fails
        """
        try:
            kwargs: Dict[str, Any] = {}
            if units:
                kwargs["units"] = str(units)
            else:
                kwargs["units"] = "ALL"

            response = self.api.trade.close(
                self.account.account_id,
                trade_id,
                **kwargs,
            )

            if response.status not in (200, 201):
                raise OandaAPIError(f"Failed to close trade {trade_id}: status {response.status}")

            return dict(response.body) if response.body else {}

        except v20.V20Error as e:
            logger.error(
                "OANDA API error closing trade %s for %s: %s",
                trade_id,
                self.account.account_id,
                str(e),
            )
            raise OandaAPIError(f"OANDA API error: {str(e)}") from e
        except Exception as e:
            logger.error(
                "Error closing trade %s for %s: %s",
                trade_id,
                self.account.account_id,
                str(e),
                exc_info=True,
            )
            raise OandaAPIError(f"Error closing trade: {str(e)}") from e

    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """
        Cancel a pending order via OANDA API.

        Args:
            order_id: OANDA order ID to cancel

        Returns:
            Cancel transaction details

        Raises:
            OandaAPIError: If API call fails
        """
        try:
            response = self.api.order.cancel(self.account.account_id, order_id)

            if response.status not in (200, 201):
                raise OandaAPIError(f"Failed to cancel order {order_id}: status {response.status}")

            return dict(response.body) if response.body else {}

        except v20.V20Error as e:
            logger.error(
                "OANDA API error cancelling order %s for %s: %s",
                order_id,
                self.account.account_id,
                str(e),
            )
            raise OandaAPIError(f"OANDA API error: {str(e)}") from e
        except Exception as e:
            logger.error(
                "Error cancelling order %s for %s: %s",
                order_id,
                self.account.account_id,
                str(e),
                exc_info=True,
            )
            raise OandaAPIError(f"Error cancelling order: {str(e)}") from e


def get_oanda_client(account: OandaAccount) -> OandaAPIClient:
    """
    Factory function to create an OANDA API client.

    Args:
        account: OandaAccount instance

    Returns:
        OandaAPIClient instance
    """
    return OandaAPIClient(account)
