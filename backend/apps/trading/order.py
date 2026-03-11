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
from apps.trading.utils import quote_to_account_rate

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
        self.execution_id = getattr(task, "execution_id", None)

        # execution_id is required for all Position/Order/Trade records
        if not self.execution_id:
            raise OrderServiceError(
                "Task must have an execution_id before OrderService can be used"
            )

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
        tick_timestamp: datetime | None = None,
        retracement_count: int | None = None,
        planned_exit_price: Decimal | None = None,
        planned_exit_price_formula: str | None = None,
    ) -> tuple[Position, Order]:
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
            tick_timestamp: Optional tick timestamp to use for position/order times instead of wall clock.

        Returns:
            tuple[Position, Order]: Created or updated position and the order record

        Raises:
            OrderServiceError: If order execution fails

        Example:
            # Open long position
            long_pos, order = service.open_position("EUR_USD", 10000, Direction.LONG)

            # Open short position
            short_pos, order = service.open_position("USD_JPY", 5000, Direction.SHORT)
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
            tick_timestamp=tick_timestamp,
            retracement_count=retracement_count,
            planned_exit_price=planned_exit_price,
            planned_exit_price_formula=planned_exit_price_formula,
        )

    def close_position(
        self,
        position: Position,
        units: int | None = None,
        override_price: Decimal | None = None,
        tick_timestamp: datetime | None = None,
    ) -> tuple[Position, Decimal, Order | None]:
        """
        Close an existing position (full or partial).

        This closes a position by executing the opposite trade:
        - LONG position: Executes a sell order to close
        - SHORT position: Executes a buy order to close

        Args:
            position: Position to close
            units: Optional number of units to close (if None, closes all)
            override_price: Optional price to use for dry-run close instead of latest tick data.
            tick_timestamp: Optional tick timestamp to use for position/order times instead of wall clock.

        Returns:
            tuple[Position, Decimal, Order | None]: Updated position, realized pnl delta, and the order record

        Raises:
            OrderServiceError: If position close fails

        Example:
            # Close a long position (sells to close)
            long_position, _ = order_service.buy("EUR_USD", 10000)
            order_service.close_position(long_position)

            # Close a short position (buys to close)
            short_position, _ = order_service.sell("USD_JPY", 5000)
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
            # Determine close units
            close_units_int = units if units is not None else abs(position.units)
            close_units_decimal = Decimal(str(close_units_int))

            # Use trade ID-based close when available (required for hedging accounts)
            if position.oanda_trade_id and not self.dry_run:
                from apps.market.services.oanda import OpenTrade, OrderDirection

                oanda_direction = (
                    OrderDirection.LONG
                    if position.direction == Direction.LONG
                    else OrderDirection.SHORT
                )
                trade = OpenTrade(
                    trade_id=position.oanda_trade_id,
                    instrument=position.instrument,
                    direction=oanda_direction,
                    units=Decimal(str(abs(position.units))),
                    entry_price=position.entry_price,
                    unrealized_pnl=Decimal("0"),
                    open_time=position.entry_time,
                    state="OPEN",
                    account_id=str(self.account.account_id) if self.account else "",
                )
                oanda_order = self.oanda_service.close_trade(
                    trade=trade,
                    units=close_units_decimal if units is not None else None,
                )
            else:
                # Fallback: instrument-based close (dry-run or legacy positions without trade ID)
                oanda_position = self._position_to_oanda_position(position)
                oanda_order = self.oanda_service.close_position(
                    position=oanda_position,
                    units=close_units_decimal if units is not None else None,
                    override_price=override_price,
                )

            # Create order record for the closing trade
            order = self._create_order_record(
                instrument=position.instrument,
                order_type=OrderType.MARKET,
                direction=Direction(position.direction),
                units=close_units_int,
                oanda_order=oanda_order,
                requested_price=override_price,
                tick_timestamp=tick_timestamp,
                oanda_trade_id=position.oanda_trade_id,
                position=position,
                layer_index=position.layer_index,
                retracement_count=position.retracement_count,
            )

            # Update position
            if units is None or units >= abs(position.units):
                # Full close
                original_units = abs(position.units)
                exit_time_value = tick_timestamp or oanda_order.fill_time or timezone.now()
                position.close(
                    exit_price=oanda_order.price or Decimal("0"),
                    exit_time=exit_time_value,  # type: ignore[arg-type]
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
                conv = quote_to_account_rate(
                    position.instrument,
                    oanda_order.price or position.entry_price,
                    account_currency=self.account.currency if self.account else "",
                )
                realized_delta = realized_delta * Decimal(original_units) * conv
            else:
                # Partial close - reduce units
                close_price = oanda_order.price or Decimal("0")
                close_units_decimal = Decimal(units)
                realized_delta = close_price - position.entry_price
                if position.direction == Direction.SHORT:
                    realized_delta = -realized_delta
                conv = quote_to_account_rate(
                    position.instrument,
                    close_price or position.entry_price,
                    account_currency=self.account.currency if self.account else "",
                )
                realized_delta = realized_delta * close_units_decimal * conv

                position.units = position.units - units

                # If partial close reduced units to zero, treat as full close
                if position.units == 0:
                    exit_time_value = tick_timestamp or oanda_order.fill_time or timezone.now()
                    position.close(
                        exit_price=close_price,
                        exit_time=exit_time_value,  # type: ignore[arg-type]
                    )

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

            return position, realized_delta, order

        except Exception as e:
            error_msg = f"Failed to close position: {str(e)}"
            logger.error(
                "Failed to close position %s: %s",
                position.id,
                str(e),
                exc_info=True,
            )
            # Record the rejected order so the failure is visible in the UI
            close_units = units if units is not None else abs(position.units)
            try:
                rejected_order = Order.objects.create(
                    task_type=self.task_type,
                    task_id=self.task.id,
                    execution_id=self.execution_id,
                    instrument=position.instrument,
                    order_type=OrderType.MARKET,
                    direction=Direction(position.direction),
                    units=close_units,
                    requested_price=override_price,
                    oanda_trade_id=position.oanda_trade_id,
                    status=OrderStatus.PENDING,
                    is_dry_run=self.dry_run,
                    position=position,
                )
                rejected_order.mark_rejected(error_msg)
                rejected_order.save()
            except Exception:
                logger.warning(
                    "Failed to persist rejected order record for closing position %s",
                    position.id,
                    exc_info=True,
                )
            raise OrderServiceError(error_msg) from e

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
        tick_timestamp: datetime | None = None,
        retracement_count: int | None = None,
        planned_exit_price: Decimal | None = None,
        planned_exit_price_formula: str | None = None,
    ) -> tuple[Position, Order]:
        """
        Execute a market order and create/update position.

        Args:
            instrument: Trading instrument
            units: Signed units (positive for long, negative for short)
            direction: Order direction
            take_profit: Optional take profit price
            stop_loss: Optional stop loss price

        Returns:
            tuple[Position, Order]: Created or updated position and the order record

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

            # Create or update position first so we can link the order to it
            entry_time = tick_timestamp or oanda_order.fill_time or timezone.now()
            position = self._create_or_update_position(
                instrument=instrument,
                direction=direction,
                units=abs(units),
                entry_price=oanda_order.price or Decimal("0"),
                entry_time=entry_time,
                layer_index=layer_index,
                merge_with_existing=merge_with_existing,
                oanda_trade_id=getattr(oanda_order, "trade_id", None),
                retracement_count=retracement_count,
                planned_exit_price=planned_exit_price,
                planned_exit_price_formula=planned_exit_price_formula,
            )

            # Create order record linked to the position
            order = self._create_order_record(
                instrument=instrument,
                order_type=OrderType.MARKET,
                direction=direction,
                units=units,
                oanda_order=oanda_order,
                requested_price=override_price,
                stop_loss=stop_loss,
                tick_timestamp=tick_timestamp,
                oanda_trade_id=getattr(oanda_order, "trade_id", None),
                position=position,
                layer_index=layer_index,
                retracement_count=retracement_count,
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

            return position, order

        except Exception as e:
            error_msg = f"Failed to execute market order: {str(e)}"
            logger.error(
                "Failed to execute market order: %s %s %s - %s",
                direction,
                abs(units),
                instrument,
                str(e),
                exc_info=True,
            )
            # Record the rejected order so the failure is visible in the UI
            try:
                rejected_order = Order.objects.create(
                    task_type=self.task_type,
                    task_id=self.task.id,
                    execution_id=self.execution_id,
                    instrument=instrument,
                    order_type=OrderType.MARKET,
                    direction=direction,
                    units=units,
                    requested_price=override_price,
                    stop_loss=stop_loss,
                    status=OrderStatus.PENDING,
                    is_dry_run=self.dry_run,
                )
                rejected_order.mark_rejected(error_msg)
                rejected_order.save()
            except Exception:
                logger.warning(
                    "Failed to persist rejected order record for %s %s %s",
                    direction,
                    abs(units),
                    instrument,
                    exc_info=True,
                )
            raise OrderServiceError(error_msg) from e

    def _create_order_record(
        self,
        instrument: str,
        order_type: OrderType,
        direction: Direction | None,
        units: int,
        oanda_order: OandaMarketOrder,
        requested_price: Decimal | None = None,
        stop_loss: Decimal | None = None,
        tick_timestamp: datetime | None = None,
        oanda_trade_id: str | None = None,
        position: Position | None = None,
        layer_index: int | None = None,
        retracement_count: int | None = None,
    ) -> Order:
        """Create order database record."""
        order = Order.objects.create(
            task_type=self.task_type,
            task_id=self.task.id,
            execution_id=self.execution_id,
            broker_order_id=oanda_order.order_id,
            oanda_trade_id=oanda_trade_id,
            instrument=instrument,
            order_type=order_type,
            direction=direction,
            units=units,
            requested_price=requested_price,
            fill_price=oanda_order.price,
            status=OrderStatus.FILLED,
            filled_at=tick_timestamp or oanda_order.fill_time,
            stop_loss=stop_loss,
            is_dry_run=self.dry_run,
            position=position,
            layer_index=layer_index,
            retracement_count=retracement_count,
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
        oanda_trade_id: str | None = None,
        retracement_count: int | None = None,
        planned_exit_price: Decimal | None = None,
        planned_exit_price_formula: str | None = None,
    ) -> Position:
        """Create new position or update existing one."""
        if merge_with_existing:
            # Check for existing open position
            existing_position = (
                Position.objects.filter(
                    task_type=self.task_type,
                    task_id=self.task.id,
                    execution_id=self.execution_id,
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
                if oanda_trade_id is not None:
                    existing_position.oanda_trade_id = oanda_trade_id
                if retracement_count is not None:
                    existing_position.retracement_count = retracement_count
                if planned_exit_price is not None:
                    existing_position.planned_exit_price = planned_exit_price
                if planned_exit_price_formula is not None:
                    existing_position.planned_exit_price_formula = planned_exit_price_formula
                existing_position.execution_id = self.execution_id
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
            execution_id=self.execution_id,
            instrument=instrument,
            direction=direction,
            units=units,
            entry_price=entry_price,
            entry_time=entry_time,
            is_open=True,
            layer_index=layer_index,
            oanda_trade_id=oanda_trade_id,
            retracement_count=retracement_count,
            planned_exit_price=planned_exit_price,
            planned_exit_price_formula=planned_exit_price_formula,
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
            unrealized_pnl=Decimal("0"),
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
            execution_id=self.execution_id,
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
            execution_id=self.execution_id,
        )

        if instrument:
            queryset = queryset.filter(instrument=instrument)

        return list(queryset.order_by("-submitted_at")[:limit])
