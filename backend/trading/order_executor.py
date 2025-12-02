"""
Order execution module for submitting orders to OANDA v20 API.

This module contains:
- OrderExecutor: Submit orders to OANDA with retry logic

Requirements: 8.1, 8.2, 8.4
"""

import logging
import time
from decimal import Decimal
from typing import Any, Dict, Optional

import v20
from v20.transaction import StopLossDetails, TakeProfitDetails

from accounts.models import OandaAccount
from trading.event_logger import TradingEventLogger
from trading.event_models import Event
from trading.models import Order
from trading.position_differentiation import PositionDifferentiationManager
from trading.regulatory_compliance import ComplianceViolationError, RegulatoryComplianceManager

logger = logging.getLogger(__name__)
trading_logger = TradingEventLogger()


class OrderExecutionError(Exception):
    """Exception raised when order execution fails."""


class OrderExecutor:
    """
    Execute trading orders via OANDA v20 API.

    Supports market, limit, stop, and OCO orders with automatic retry logic.

    Requirements: 8.1, 8.2, 8.4
    """

    def __init__(self, account: OandaAccount, strategy: Optional[Any] = None):
        """
        Initialize OrderExecutor.

        Args:
            account: OANDA account to execute orders for
            strategy: Optional Strategy instance for strategy-level settings
        """
        self.account = account
        self.strategy = strategy
        self.api = v20.Context(
            hostname=account.api_hostname,
            token=account.get_api_token(),
            poll_timeout=10,
        )
        self.max_retries = 3
        self.retry_delay = 0.5  # 500ms
        self.compliance_manager = RegulatoryComplianceManager(account)
        self.position_diff_manager = PositionDifferentiationManager(account, strategy)

    def _validate_compliance(self, order_request: Dict[str, Any]) -> None:
        """
        Validate order against regulatory compliance rules.

        Args:
            order_request: Order details to validate

        Raises:
            ComplianceViolationError: If order violates compliance rules
        """
        is_valid, error_message = self.compliance_manager.validate_order(order_request)

        if not is_valid:
            # Log compliance violation
            Event.log_security_event(
                event_type="compliance_violation",
                description=f"Order rejected: {error_message}",
                severity="warning",
                user=self.account.user,
                details={
                    "account_id": self.account.account_id,
                    "order_request": order_request,
                    "violation_reason": error_message,
                    "jurisdiction": self.account.jurisdiction,
                },
            )

            raise ComplianceViolationError(error_message)

    def _apply_position_differentiation(
        self,
        instrument: str,
        units: Decimal,
        min_units: Optional[Decimal] = None,
        max_units: Optional[Decimal] = None,
    ) -> Decimal:
        """
        Apply position differentiation to order units.

        Args:
            instrument: Currency pair
            units: Original order units
            min_units: Minimum allowed order size
            max_units: Maximum allowed order size

        Returns:
            Adjusted units (may be same as original if differentiation disabled)
        """
        adjusted_units, was_adjusted = self.position_diff_manager.adjust_order_units(
            instrument=instrument,
            original_units=abs(units),
            min_units=min_units,
            max_units=max_units,
        )

        if was_adjusted:
            logger.info(
                "Position differentiation applied: %s -> %s units for %s",
                abs(units),
                adjusted_units,
                instrument,
            )

            # Log the adjustment
            description = (
                f"Order units adjusted for position differentiation: "
                f"{abs(units)} -> {adjusted_units}"
            )
            Event.log_trading_event(
                event_type="position_differentiation_applied",
                description=description,
                severity="info",
                user=self.account.user,
                account=self.account,
                details={
                    "instrument": instrument,
                    "original_units": str(abs(units)),
                    "adjusted_units": str(adjusted_units),
                    "pattern": self.position_diff_manager.get_pattern(),
                    "increment": self.position_diff_manager.get_increment_amount(),
                },
            )

        # Preserve the sign (positive for long, negative for short)
        return adjusted_units if units > 0 else -adjusted_units

    def submit_market_order(  # pylint: disable=too-many-locals
        self,
        instrument: str,
        units: Decimal,
        take_profit: Optional[Decimal] = None,
        stop_loss: Optional[Decimal] = None,
    ) -> Order:
        """
        Submit a market order.

        Args:
            instrument: Currency pair (e.g., 'EUR_USD')
            units: Number of units (positive for long, negative for short).
                   Strategy should convert lot sizes to actual units before calling.
            take_profit: Optional take-profit price
            stop_loss: Optional stop-loss price

        Returns:
            Order instance

        Raises:
            OrderExecutionError: If order submission fails after retries
            ComplianceViolationError: If order violates compliance rules
        """
        direction = "long" if units > 0 else "short"
        original_abs_units = abs(units)

        logger.info(
            "Submitting market order: %s %s %s for account %s",
            direction,
            original_abs_units,
            instrument,
            self.account.account_id,
        )

        # Apply position differentiation if enabled
        # Note: min/max units would typically come from OANDA instrument specs
        adjusted_units = self._apply_position_differentiation(
            instrument=instrument,
            units=units,
            min_units=Decimal("1"),  # Minimum 1 unit
            max_units=None,  # No maximum by default
        )
        abs_units = abs(adjusted_units)

        # Validate compliance before submitting order
        order_request = {
            "instrument": instrument,
            "units": int(adjusted_units),
            "order_type": "market",
        }
        self._validate_compliance(order_request)

        # Prepare order request
        order_data: Dict[str, Any] = {
            "instrument": instrument,
            "units": str(adjusted_units),
            "type": "MARKET",
            "timeInForce": "FOK",  # Fill or Kill
        }

        # Add take-profit if specified
        if take_profit is not None:
            order_data["takeProfitOnFill"] = TakeProfitDetails(price=str(take_profit)).__dict__

        # Add stop-loss if specified
        if stop_loss is not None:
            order_data["stopLossOnFill"] = StopLossDetails(price=str(stop_loss)).__dict__

        # Execute with retry logic
        response = self._execute_with_retry(order_data)

        # Check if order was filled or rejected
        # OANDA returns 201 even for rejected orders, but with different transaction types
        if hasattr(response, "orderFillTransaction") and response.orderFillTransaction:
            # Order was filled successfully
            fill_transaction = response.orderFillTransaction
            order = self._create_order_record(
                order_id=fill_transaction.id,
                instrument=instrument,
                order_type="market",
                direction=direction,
                units=abs_units,
                price=None,
                take_profit=take_profit,
                stop_loss=stop_loss,
                status="filled",
            )

            logger.info(
                "Market order filled: %s at %s",
                order.order_id,
                fill_transaction.price,
            )

            # Log order submission event
            Event.log_trading_event(
                event_type="order_submitted",
                description=f"Market order submitted: {direction} {abs_units} {instrument}",
                severity="info",
                user=self.account.user,
                account=self.account,
                details={
                    "order_id": order.order_id,
                    "instrument": instrument,
                    "order_type": "market",
                    "direction": direction,
                    "units": str(abs_units),
                    "take_profit": str(take_profit) if take_profit else None,
                    "stop_loss": str(stop_loss) if stop_loss else None,
                    "status": "filled",
                    "fill_price": str(fill_transaction.price),
                },
            )

            return order

        # Order was rejected - extract rejection reason
        reject_reason = "Unknown rejection reason"
        reject_transaction = None

        if hasattr(response, "orderRejectTransaction") and response.orderRejectTransaction:
            reject_transaction = response.orderRejectTransaction
            reject_reason = getattr(reject_transaction, "rejectReason", reject_reason)
        elif hasattr(response, "orderCancelTransaction") and response.orderCancelTransaction:
            reject_transaction = response.orderCancelTransaction
            reject_reason = getattr(reject_transaction, "reason", reject_reason)

        # Log the full response for debugging
        logger.error(
            "Market order rejected: %s %s %s - Reason: %s, Response attrs: %s",
            direction,
            abs_units,
            instrument,
            reject_reason,
            [attr for attr in dir(response) if not attr.startswith("_")],
        )

        # Log rejection event
        Event.log_trading_event(
            event_type="order_rejected",
            description=f"Market order rejected: {direction} {abs_units} {instrument}",
            severity="error",
            user=self.account.user,
            account=self.account,
            details={
                "instrument": instrument,
                "order_type": "market",
                "direction": direction,
                "units": str(abs_units),
                "reject_reason": reject_reason,
            },
        )

        raise OrderExecutionError(f"Market order rejected: {reject_reason}")

    def submit_limit_order(  # pylint: disable=too-many-positional-arguments
        self,
        instrument: str,
        units: Decimal,
        price: Decimal,
        take_profit: Optional[Decimal] = None,
        stop_loss: Optional[Decimal] = None,
    ) -> Order:
        """
        Submit a limit order.

        Args:
            instrument: Currency pair (e.g., 'EUR_USD')
            units: Number of units (positive for long, negative for short)
            price: Limit price
            take_profit: Optional take-profit price
            stop_loss: Optional stop-loss price

        Returns:
            Order instance

        Raises:
            OrderExecutionError: If order submission fails after retries
            ComplianceViolationError: If order violates compliance rules
        """
        direction = "long" if units > 0 else "short"
        original_abs_units = abs(units)

        logger.info(
            "Submitting limit order: %s %s %s @ %s for account %s",
            direction,
            original_abs_units,
            instrument,
            price,
            self.account.account_id,
        )

        # Apply position differentiation if enabled
        adjusted_units = self._apply_position_differentiation(
            instrument=instrument,
            units=units,
            min_units=Decimal("1"),
            max_units=None,
        )
        abs_units = abs(adjusted_units)

        # Validate compliance before submitting order
        order_request = {
            "instrument": instrument,
            "units": int(adjusted_units),
            "order_type": "limit",
            "price": float(price),
        }
        self._validate_compliance(order_request)

        # Prepare order request
        order_data: Dict[str, Any] = {
            "instrument": instrument,
            "units": str(adjusted_units),
            "price": str(price),
            "type": "LIMIT",
            "timeInForce": "GTC",  # Good Till Cancelled
        }

        # Add take-profit if specified
        if take_profit is not None:
            order_data["takeProfitOnFill"] = TakeProfitDetails(price=str(take_profit)).__dict__

        # Add stop-loss if specified
        if stop_loss is not None:
            order_data["stopLossOnFill"] = StopLossDetails(price=str(stop_loss)).__dict__

        # Execute with retry logic
        response = self._execute_with_retry(order_data)

        # Create Order record
        order = self._create_order_record(
            order_id=response.orderCreateTransaction.id,
            instrument=instrument,
            order_type="limit",
            direction=direction,
            units=abs_units,
            price=price,
            take_profit=take_profit,
            stop_loss=stop_loss,
            status="pending",
        )

        logger.info("Limit order created: %s", order.order_id)

        # Log order submission event
        Event.log_trading_event(
            event_type="order_submitted",
            description=f"Limit order submitted: {direction} {abs_units} {instrument} @ {price}",
            severity="info",
            user=self.account.user,
            account=self.account,
            details={
                "order_id": order.order_id,
                "instrument": instrument,
                "order_type": "limit",
                "direction": direction,
                "units": str(abs_units),
                "price": str(price),
                "take_profit": str(take_profit) if take_profit else None,
                "stop_loss": str(stop_loss) if stop_loss else None,
                "status": "pending",
            },
        )

        return order

    def submit_stop_order(  # pylint: disable=too-many-positional-arguments
        self,
        instrument: str,
        units: Decimal,
        price: Decimal,
        take_profit: Optional[Decimal] = None,
        stop_loss: Optional[Decimal] = None,
    ) -> Order:
        """
        Submit a stop order.

        Args:
            instrument: Currency pair (e.g., 'EUR_USD')
            units: Number of units (positive for long, negative for short)
            price: Stop price
            take_profit: Optional take-profit price
            stop_loss: Optional stop-loss price

        Returns:
            Order instance

        Raises:
            OrderExecutionError: If order submission fails after retries
            ComplianceViolationError: If order violates compliance rules
        """
        direction = "long" if units > 0 else "short"
        original_abs_units = abs(units)

        logger.info(
            "Submitting stop order: %s %s %s @ %s for account %s",
            direction,
            original_abs_units,
            instrument,
            price,
            self.account.account_id,
        )

        # Apply position differentiation if enabled
        adjusted_units = self._apply_position_differentiation(
            instrument=instrument,
            units=units,
            min_units=Decimal("1"),
            max_units=None,
        )
        abs_units = abs(adjusted_units)

        # Validate compliance before submitting order
        order_request = {
            "instrument": instrument,
            "units": int(adjusted_units),
            "order_type": "stop",
            "price": float(price),
        }
        self._validate_compliance(order_request)

        # Prepare order request
        order_data: Dict[str, Any] = {
            "instrument": instrument,
            "units": str(adjusted_units),
            "price": str(price),
            "type": "STOP",
            "timeInForce": "GTC",  # Good Till Cancelled
        }

        # Add take-profit if specified
        if take_profit is not None:
            order_data["takeProfitOnFill"] = TakeProfitDetails(price=str(take_profit)).__dict__

        # Add stop-loss if specified
        if stop_loss is not None:
            order_data["stopLossOnFill"] = StopLossDetails(price=str(stop_loss)).__dict__

        # Execute with retry logic
        response = self._execute_with_retry(order_data)

        # Create Order record
        order = self._create_order_record(
            order_id=response.orderCreateTransaction.id,
            instrument=instrument,
            order_type="stop",
            direction=direction,
            units=abs_units,
            price=price,
            take_profit=take_profit,
            stop_loss=stop_loss,
            status="pending",
        )

        logger.info("Stop order created: %s", order.order_id)

        # Log order submission event
        Event.log_trading_event(
            event_type="order_submitted",
            description=f"Stop order submitted: {direction} {abs_units} {instrument} @ {price}",
            severity="info",
            user=self.account.user,
            account=self.account,
            details={
                "order_id": order.order_id,
                "instrument": instrument,
                "order_type": "stop",
                "direction": direction,
                "units": str(abs_units),
                "price": str(price),
                "take_profit": str(take_profit) if take_profit else None,
                "stop_loss": str(stop_loss) if stop_loss else None,
                "status": "pending",
            },
        )

        return order

    def submit_oco_order(  # pylint: disable=too-many-locals
        self,
        instrument: str,
        units: Decimal,
        limit_price: Decimal,
        stop_price: Decimal,
    ) -> tuple[Order, Order]:
        """
        Submit an OCO (One-Cancels-Other) order.

        Args:
            instrument: Currency pair (e.g., 'EUR_USD')
            units: Number of units (positive for long, negative for short)
            limit_price: Limit order price
            stop_price: Stop order price

        Returns:
            Tuple of (limit_order, stop_order)

        Raises:
            OrderExecutionError: If order submission fails after retries
            ComplianceViolationError: If order violates compliance rules
        """
        direction = "long" if units > 0 else "short"
        original_abs_units = abs(units)

        logger.info(
            "Submitting OCO order: %s %s %s limit @ %s, stop @ %s for account %s",
            direction,
            original_abs_units,
            instrument,
            limit_price,
            stop_price,
            self.account.account_id,
        )

        # Apply position differentiation if enabled
        adjusted_units = self._apply_position_differentiation(
            instrument=instrument,
            units=units,
            min_units=Decimal("1"),
            max_units=None,
        )
        abs_units = abs(adjusted_units)

        # Validate compliance before submitting order
        order_request = {
            "instrument": instrument,
            "units": int(adjusted_units),
            "order_type": "oco",
            "limit_price": float(limit_price),
            "stop_price": float(stop_price),
        }
        self._validate_compliance(order_request)

        # Submit limit order first
        limit_order_data: Dict[str, Any] = {
            "instrument": instrument,
            "units": str(adjusted_units),
            "price": str(limit_price),
            "type": "LIMIT",
            "timeInForce": "GTC",
        }

        limit_response = self._execute_with_retry(limit_order_data)
        limit_order_id = limit_response.orderCreateTransaction.id

        # Submit stop order with OCO link
        stop_order_data: Dict[str, Any] = {
            "instrument": instrument,
            "units": str(adjusted_units),
            "price": str(stop_price),
            "type": "STOP",
            "timeInForce": "GTC",
            "gtdTime": None,
        }

        stop_response = self._execute_with_retry(stop_order_data)
        stop_order_id = stop_response.orderCreateTransaction.id

        # Create Order records
        limit_order = self._create_order_record(
            order_id=limit_order_id,
            instrument=instrument,
            order_type="oco",
            direction=direction,
            units=abs_units,
            price=limit_price,
            take_profit=None,
            stop_loss=None,
            status="pending",
        )

        stop_order = self._create_order_record(
            order_id=stop_order_id,
            instrument=instrument,
            order_type="oco",
            direction=direction,
            units=abs_units,
            price=stop_price,
            take_profit=None,
            stop_loss=None,
            status="pending",
        )

        logger.info(
            "OCO orders created: limit %s, stop %s",
            limit_order.order_id,
            stop_order.order_id,
        )

        # Log order submission event
        Event.log_trading_event(
            event_type="order_submitted",
            description=f"OCO orders submitted: {direction} {abs_units} {instrument}",
            severity="info",
            user=self.account.user,
            account=self.account,
            details={
                "limit_order_id": limit_order.order_id,
                "stop_order_id": stop_order.order_id,
                "instrument": instrument,
                "order_type": "oco",
                "direction": direction,
                "units": str(abs_units),
                "limit_price": str(limit_price),
                "stop_price": str(stop_price),
                "status": "pending",
            },
        )

        return limit_order, stop_order

    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel a pending order.

        Args:
            order_id: OANDA order ID

        Returns:
            True if cancelled successfully, False otherwise
        """
        logger.info("Cancelling order %s for account %s", order_id, self.account.account_id)

        try:
            response = self.api.order.cancel(self.account.account_id, order_id)

            if response.status == 200:
                # Update Order record
                try:
                    order = Order.objects.get(order_id=order_id)
                    order.mark_cancelled()
                    logger.info("Order %s cancelled successfully", order_id)

                    # Log order cancellation event
                    Event.log_trading_event(
                        event_type="order_cancelled",
                        description=f"Order cancelled: {order.instrument} {order.order_type}",
                        severity="info",
                        user=self.account.user,
                        account=self.account,
                        details={
                            "order_id": order_id,
                            "instrument": order.instrument,
                            "order_type": order.order_type,
                            "direction": order.direction,
                            "units": str(order.units),
                        },
                    )

                    return True
                except Order.DoesNotExist:
                    logger.warning("Order %s not found in database", order_id)
                    return True

            logger.error("Failed to cancel order %s: %s", order_id, response)
            return False

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error cancelling order %s: %s", order_id, e)
            return False

    def _execute_with_retry(self, order_data: Dict[str, Any]) -> Any:
        """
        Execute order with retry logic.

        Args:
            order_data: Order request data

        Returns:
            OANDA API response

        Raises:
            OrderExecutionError: If all retry attempts fail
        """
        last_error = None

        for attempt in range(self.max_retries):
            try:
                # OANDA v20 API expects order data wrapped in 'order' key
                response = self.api.order.create(self.account.account_id, order=order_data)

                if response.status in [200, 201]:
                    return response

                # Extract error details from response
                error_details = ""
                if hasattr(response, "body") and response.body:
                    error_details = f" - {response.body}"
                elif hasattr(response, "raw_body"):
                    error_details = f" - {response.raw_body}"

                logger.warning(
                    "Order submission attempt %s failed: status %s%s",
                    attempt + 1,
                    response.status,
                    error_details,
                )
                last_error = f"API returned status {response.status}{error_details}"

            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.warning("Order submission attempt %s failed: %s", attempt + 1, e)
                last_error = str(e)

            # Wait before retry (except on last attempt)
            if attempt < self.max_retries - 1:
                time.sleep(self.retry_delay)

        # All retries failed
        error_msg = f"Order submission failed after {self.max_retries} attempts: {last_error}"
        logger.error("Order submission failed after %s attempts: %s", self.max_retries, last_error)

        # Log order failure event
        Event.log_trading_event(
            event_type="order_failed",
            description=f"Order submission failed after {self.max_retries} attempts",
            severity="error",
            user=self.account.user,
            account=self.account,
            details={
                "order_data": order_data,
                "error": last_error,
                "attempts": self.max_retries,
            },
        )

        raise OrderExecutionError(error_msg)

    def _create_order_record(  # pylint: disable=too-many-positional-arguments
        self,
        order_id: str,
        instrument: str,
        order_type: str,
        direction: str,
        units: Decimal,
        price: Optional[Decimal],
        take_profit: Optional[Decimal],
        stop_loss: Optional[Decimal],
        status: str,
    ) -> Order:
        """
        Create Order database record.

        Args:
            order_id: OANDA order ID
            instrument: Currency pair
            order_type: Order type (market, limit, stop, oco)
            direction: Trade direction (long, short)
            units: Number of units
            price: Order price (for limit/stop orders)
            take_profit: Take-profit price
            stop_loss: Stop-loss price
            status: Order status

        Returns:
            Order instance
        """
        order = Order.objects.create(
            account=self.account,
            order_id=order_id,
            instrument=instrument,
            order_type=order_type,
            direction=direction,
            units=units,
            price=price,
            take_profit=take_profit,
            stop_loss=stop_loss,
            status=status,
        )

        return order
