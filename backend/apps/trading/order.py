"""Order execution service for trading operations."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from logging import Logger, getLogger
from typing import TYPE_CHECKING

from django.utils import timezone

from apps.market.models import OandaAccounts
from apps.market.services.oanda import (
    MarketOrder as OandaMarketOrder,
)
from apps.market.services.oanda import (
    MarketOrderRequest,
    OandaService,
    OrderDirection,
)
from apps.market.services.oanda import (
    Position as OandaPosition,
)
from apps.trading.enums import Direction, TaskType
from apps.trading.models import Order, Position
from apps.trading.models.orders import OrderStatus, OrderType

if TYPE_CHECKING:
    from apps.trading.models import BacktestTask, TradingTask

logger: Logger = getLogger(__name__)


class OrderServiceError(Exception):
    """Exception raised when order service operations fail."""


class OrderService:
    """
    Service for executing orders and managing positions.

    Handles order submission to OANDA and database persistence.
    Supports both live trading and dry-run (backtest) modes.
    """

    def __init__(
        self,
        account: OandaAccounts | None,
        task: BacktestTask | TradingTask,
        dry_run: bool = False,
    ):
        """
        Initialize order service.

        Args:
            account: OANDA account to use for trading (optional for dry_run mode)
            task: Trading or backtest task
            dry_run: If True, simulate orders without actual execution
        """
        self.account = account
        self.task = task
        self.dry_run = dry_run
        self.oanda_service = OandaService(account=account, dry_run=dry_run)

        # Determine task type
        if hasattr(task, "__class__"):
            task_class_name = task.__class__.__name__
            if "Backtest" in task_class_name:
                self.task_type = TaskType.BACKTEST
            else:
                self.task_type = TaskType.TRADING
        else:
            self.task_type = TaskType.TRADING

        account_id = account.account_id if account else "DRY-RUN"
        logger.info(
            "OrderService initialized (account=%s, task=%s, task_type=%s, dry_run=%s)",
            account_id,
            task.id,
            self.task_type,
            dry_run,
        )

    def open_position(
        self,
        instrument: str,
        units: int,
        direction: Direction,
        take_profit: Decimal | None = None,
        stop_loss: Decimal | None = None,
        *,
        layer_index: int | None = None,
        merge_with_existing: bool = True,
        override_price: Decimal | None = None,
    ) -> Position:
        """
        Open a new position with specified direction.

        Args:
            instrument: Trading instrument (e.g., 'EUR_USD')
            units: Number of units (positive integer)
            direction: Position direction (Direction.LONG or Direction.SHORT)
            take_profit: Optional take profit price
            stop_loss: Optional stop loss price
            layer_index: Optional layer index for Floor strategy
            merge_with_existing: Whether to merge into existing same-direction position
            override_price: Optional price to use for dry-run open instead of latest tick data.

        Returns:
            Position: Created or updated position

        Raises:
            OrderServiceError: If order execution fails

        Example:
            # Open long position
            long_pos = service.open_position("EUR_USD", 10000, Direction.LONG)

            # Open short position
            short_pos = service.open_position("USD_JPY", 5000, Direction.SHORT)
        """
        if units <= 0:
            raise OrderServiceError("Units must be positive")

        # Convert to signed units based on direction
        signed_units = units if direction == Direction.LONG else -units

        return self._execute_market_order(
            instrument=instrument,
            units=signed_units,
            direction=direction,
            take_profit=take_profit,
            stop_loss=stop_loss,
            layer_index=layer_index,
            merge_with_existing=merge_with_existing,
            override_price=override_price,
        )

    def close_position(
        self,
        position: Position,
        units: int | None = None,
        override_price: Decimal | None = None,
    ) -> tuple[Position, Decimal]:
        """
        Close an existing position (full or partial).

        This closes a position by executing the opposite trade:
        - LONG position: Executes a sell order to close
        - SHORT position: Executes a buy order to close

        Args:
            position: Position to close
            units: Optional number of units to close (if None, closes all)
            override_price: Optional price to use for dry-run close instead of latest tick data.

        Returns:
            tuple[Position, Decimal]: Updated position and realized pnl delta for this close

        Raises:
            OrderServiceError: If position close fails

        Example:
            # Close a long position (sells to close)
            long_position = order_service.buy("EUR_USD", 10000)
            order_service.close_position(long_position)

            # Close a short position (buys to close)
            short_position = order_service.sell("USD_JPY", 5000)
            order_service.close_position(short_position)
        """
        if not position.is_open:
            raise OrderServiceError(f"Position {position.id} is already closed")

        if units is not None and units <= 0:
            raise OrderServiceError("Units must be positive for position close")

        if units is not None and units > abs(position.units):
            raise OrderServiceError(
                f"Cannot close {units} units, position only has {abs(position.units)} units"
            )

        try:
            # Get OANDA position representation
            oanda_position = self._position_to_oanda_position(position)

            # Close via OANDA service (executes opposite trade)
            close_units = Decimal(str(units)) if units is not None else None
            oanda_order = self.oanda_service.close_position(
                position=oanda_position,
                units=close_units,
                override_price=override_price,
            )

            # Create order record for the closing trade
            # The order direction is opposite to the position direction
            close_direction = (
                Direction.SHORT if position.direction == Direction.LONG else Direction.LONG
            )
            close_units_int = units if units is not None else abs(position.units)

            order = self._create_order_record(
                instrument=position.instrument,
                order_type=OrderType.MARKET,
                direction=close_direction,  # Opposite direction
                units=close_units_int,
                oanda_order=oanda_order,
            )

            # Update position
            if units is None or units >= abs(position.units):
                # Full close
                previous_realized = Decimal(str(position.realized_pnl or "0"))
                original_units = abs(position.units)
                exit_time_value = oanda_order.fill_time or timezone.now()
                position.close(
                    exit_price=oanda_order.price or Decimal("0"),
                    exit_time=exit_time_value,  # type: ignore[arg-type]
                )
                # Preserve previously realized pnl from prior partial closes.
                if previous_realized != Decimal("0"):
                    position.realized_pnl = (
                        Decimal(str(position.realized_pnl or "0")) + previous_realized
                    )
                position.save()

                logger.info(
                    "Position fully closed: %s %s position, %s units of %s @ %s (order=%s, dry_run=%s)",
                    position.direction,
                    position.id,
                    abs(position.units),
                    position.instrument,
                    oanda_order.price,
                    order.id,
                    self.dry_run,
                )
                realized_delta = (oanda_order.price or Decimal("0")) - position.entry_price
                if position.direction == Direction.SHORT:
                    realized_delta = -realized_delta
                realized_delta = realized_delta * Decimal(original_units)
            else:
                # Partial close - reduce units
                close_price = oanda_order.price or Decimal("0")
                close_units_decimal = Decimal(units)
                realized_delta = close_price - position.entry_price
                if position.direction == Direction.SHORT:
                    realized_delta = -realized_delta
                realized_delta = realized_delta * close_units_decimal

                if position.direction == Direction.LONG:
                    position.units = position.units - units
                else:
                    position.units = position.units + units
                position.realized_pnl = Decimal(str(position.realized_pnl or "0")) + realized_delta
                position.save()

                logger.info(
                    "Position partially closed: %s units of %s %s position (remaining: %s, "
                    "realized_delta=%s, order=%s, dry_run=%s)",
                    units,
                    position.direction,
                    position.instrument,
                    abs(position.units),
                    realized_delta,
                    order.id,
                    self.dry_run,
                )

            return position, realized_delta

        except Exception as e:
            logger.error(
                "Failed to close position %s: %s",
                position.id,
                str(e),
                exc_info=True,
            )
            raise OrderServiceError(f"Failed to close position: {str(e)}") from e

    def _execute_market_order(
        self,
        instrument: str,
        units: int,
        direction: Direction,
        take_profit: Decimal | None = None,
        stop_loss: Decimal | None = None,
        *,
        layer_index: int | None = None,
        merge_with_existing: bool = True,
        override_price: Decimal | None = None,
    ) -> Position:
        """
        Execute a market order and create/update position.

        Args:
            instrument: Trading instrument
            units: Signed units (positive for long, negative for short)
            direction: Order direction
            take_profit: Optional take profit price
            stop_loss: Optional stop loss price

        Returns:
            Position: Created or updated position

        Raises:
            OrderServiceError: If order execution fails
        """
        try:
            # Create market order request
            request = MarketOrderRequest(
                instrument=instrument,
                units=Decimal(str(units)),
                take_profit=take_profit,
                stop_loss=stop_loss,
            )

            # Execute via OANDA service
            oanda_order = self.oanda_service.create_market_order(
                request, override_price=override_price
            )

            # Create order record
            order = self._create_order_record(
                instrument=instrument,
                order_type=OrderType.MARKET,
                direction=direction,
                units=units,
                oanda_order=oanda_order,
                take_profit=take_profit,
                stop_loss=stop_loss,
            )

            # Create or update position
            position = self._create_or_update_position(
                instrument=instrument,
                direction=direction,
                units=abs(units),
                entry_price=oanda_order.price or Decimal("0"),
                entry_time=oanda_order.fill_time or timezone.now(),
                layer_index=layer_index,
                merge_with_existing=merge_with_existing,
            )

            logger.info(
                "Market order executed: %s %s %s @ %s (order=%s, position=%s, dry_run=%s)",
                direction,
                abs(units),
                instrument,
                oanda_order.price,
                order.id,
                position.id,
                self.dry_run,
            )

            return position

        except Exception as e:
            logger.error(
                "Failed to execute market order: %s %s %s - %s",
                direction,
                abs(units),
                instrument,
                str(e),
                exc_info=True,
            )
            raise OrderServiceError(f"Failed to execute market order: {str(e)}") from e

    def _create_order_record(
        self,
        instrument: str,
        order_type: OrderType,
        direction: Direction,
        units: int,
        oanda_order: OandaMarketOrder,
        requested_price: Decimal | None = None,
        take_profit: Decimal | None = None,
        stop_loss: Decimal | None = None,
    ) -> Order:
        """Create order database record."""
        order = Order.objects.create(
            task_type=self.task_type,
            task_id=self.task.id,
            broker_order_id=oanda_order.order_id,
            instrument=instrument,
            order_type=order_type,
            direction=direction,
            units=units,
            requested_price=requested_price,
            fill_price=oanda_order.price,
            status=OrderStatus.FILLED,
            filled_at=oanda_order.fill_time,
            take_profit=take_profit,
            stop_loss=stop_loss,
            is_dry_run=self.dry_run,
        )
        return order

    def _create_or_update_position(
        self,
        instrument: str,
        direction: Direction,
        units: int,
        entry_price: Decimal,
        entry_time: datetime,
        *,
        layer_index: int | None = None,
        merge_with_existing: bool = True,
    ) -> Position:
        """Create new position or update existing one."""
        if merge_with_existing:
            # Check for existing open position
            existing_position = (
                Position.objects.filter(
                    task_type=self.task_type,
                    task_id=self.task.id,
                    instrument=instrument,
                    direction=direction,
                    is_open=True,
                )
                .order_by("-entry_time")
                .first()
            )

            if existing_position:
                # Update existing position (weighted average)
                total_units = existing_position.units + units
                new_avg_price = (
                    (existing_position.entry_price * existing_position.units)
                    + (entry_price * units)
                ) / total_units

                existing_position.units = total_units
                existing_position.entry_price = new_avg_price
                if layer_index is not None:
                    existing_position.layer_index = layer_index
                existing_position.save()

                logger.debug(
                    "Updated existing position %s: %s units @ %s",
                    existing_position.id,
                    total_units,
                    new_avg_price,
                )

                return existing_position

        # Create new position
        position = Position.objects.create(
            task_type=self.task_type,
            task_id=self.task.id,
            instrument=instrument,
            direction=direction,
            units=units,
            entry_price=entry_price,
            entry_time=entry_time,
            is_open=True,
            layer_index=layer_index,
        )

        logger.debug(
            "Created new position %s: %s %s units @ %s",
            position.id,
            direction,
            units,
            entry_price,
        )

        return position

    def _position_to_oanda_position(self, position: Position) -> OandaPosition:
        """Convert database Position to OANDA Position."""
        from apps.market.services.oanda import Position as OandaPosition

        oanda_direction = (
            OrderDirection.LONG if position.direction == Direction.LONG else OrderDirection.SHORT
        )

        account_id = str(self.account.account_id) if self.account else "DRY-RUN-ACCOUNT"

        return OandaPosition(
            instrument=position.instrument,
            direction=oanda_direction,
            units=Decimal(str(abs(position.units))),
            average_price=position.entry_price,
            unrealized_pnl=position.unrealized_pnl,
            trade_ids=[],
            account_id=account_id,
        )

    def get_open_positions(self, instrument: str | None = None) -> list[Position]:
        """
        Get all open positions for this task.

        Args:
            instrument: Optional filter by instrument

        Returns:
            List of open positions
        """
        queryset = Position.objects.filter(
            task_type=self.task_type,
            task_id=self.task.id,
            is_open=True,
        )

        if instrument:
            queryset = queryset.filter(instrument=instrument)

        return list(queryset.order_by("-entry_time"))

    def get_order_history(self, instrument: str | None = None, limit: int = 100) -> list[Order]:
        """
        Get order history for this task.

        Args:
            instrument: Optional filter by instrument
            limit: Maximum number of orders to return

        Returns:
            List of orders
        """
        queryset = Order.objects.filter(
            task_type=self.task_type,
            task_id=self.task.id,
        )

        if instrument:
            queryset = queryset.filter(instrument=instrument)

        return list(queryset.order_by("-submitted_at")[:limit])
