"""
Position management module.

This module provides the PositionManager class for managing trading positions,
including CRUD operations, position tracking, and integration with order fills.

Requirements: 9.1, 9.5
"""

from decimal import Decimal
from typing import List, Optional

from django.db import transaction

from accounts.models import OandaAccount
from trading.models import Order, Position, Strategy, Trade


class PositionManager:
    """
    Manages trading positions including creation, updates, and closure.

    This class provides methods for:
    - Creating positions from order fills
    - Updating position details
    - Closing positions and calculating realized P&L
    - Querying positions by various criteria

    Requirements: 9.1, 9.5
    """

    @staticmethod
    def create_position(  # pylint: disable=too-many-positional-arguments
        account: OandaAccount,
        order: Order,
        fill_price: Decimal,
        strategy: Optional[Strategy] = None,
        layer_number: int = 1,
        is_first_lot: bool = False,
    ) -> Position:
        """
        Create a new position from an order fill.

        Args:
            account: OANDA account associated with the position
            order: Order that was filled
            fill_price: Price at which the order was filled
            strategy: Strategy that generated the order (optional)
            layer_number: Layer number for multi-layer strategies
            is_first_lot: Whether this is the first lot of a layer

        Returns:
            Created Position instance

        Requirements: 9.1
        """
        position = Position.objects.create(
            account=account,
            strategy=strategy,
            position_id=f"{order.order_id}_POS",
            instrument=order.instrument,
            direction=order.direction,
            units=order.units,
            entry_price=fill_price,
            current_price=fill_price,
            unrealized_pnl=Decimal("0"),
            layer_number=layer_number,
            is_first_lot=is_first_lot,
        )
        return position

    @staticmethod
    def get_position(position_id: str) -> Optional[Position]:
        """
        Get a position by its ID.

        Args:
            position_id: Position ID

        Returns:
            Position instance or None if not found

        Requirements: 9.1
        """
        try:
            return Position.objects.get(position_id=position_id)
        except Position.DoesNotExist:
            return None

    @staticmethod
    def get_open_positions(
        account: Optional[OandaAccount] = None,
        strategy: Optional[Strategy] = None,
        instrument: Optional[str] = None,
    ) -> List[Position]:
        """
        Get all open positions with optional filtering.

        Args:
            account: Filter by OANDA account (optional)
            strategy: Filter by strategy (optional)
            instrument: Filter by instrument (optional)

        Returns:
            List of open Position instances

        Requirements: 9.1
        """
        queryset = Position.objects.filter(closed_at__isnull=True)

        if account:
            queryset = queryset.filter(account=account)
        if strategy:
            queryset = queryset.filter(strategy=strategy)
        if instrument:
            queryset = queryset.filter(instrument=instrument)

        return list(queryset.order_by("-opened_at"))

    @staticmethod
    def get_closed_positions(
        account: Optional[OandaAccount] = None,
        strategy: Optional[Strategy] = None,
        instrument: Optional[str] = None,
    ) -> List[Position]:
        """
        Get all closed positions with optional filtering.

        Args:
            account: Filter by OANDA account (optional)
            strategy: Filter by strategy (optional)
            instrument: Filter by instrument (optional)

        Returns:
            List of closed Position instances

        Requirements: 9.1
        """
        queryset = Position.objects.filter(closed_at__isnull=False)

        if account:
            queryset = queryset.filter(account=account)
        if strategy:
            queryset = queryset.filter(strategy=strategy)
        if instrument:
            queryset = queryset.filter(instrument=instrument)

        return list(queryset.order_by("-closed_at"))

    @staticmethod
    def update_position_price(position: Position, current_price: Decimal) -> Position:
        """
        Update position's current price and recalculate unrealized P&L.

        Args:
            position: Position to update
            current_price: Current market price

        Returns:
            Updated Position instance

        Requirements: 9.1
        """
        position.update_price(current_price)
        return position

    @staticmethod
    @transaction.atomic
    def close_position(
        position: Position,
        exit_price: Decimal,
        create_trade_record: bool = True,
    ) -> Position:
        """
        Close a position and optionally create a trade record.

        Args:
            position: Position to close
            exit_price: Exit price for the position
            create_trade_record: Whether to create a Trade record

        Returns:
            Closed Position instance

        Requirements: 9.1, 9.5
        """
        # Close the position and calculate realized P&L
        realized_pnl = position.close(exit_price)

        # Create trade record if requested
        if create_trade_record and position.closed_at:
            Trade.objects.create(
                account=position.account,
                strategy=position.strategy,
                instrument=position.instrument,
                direction=position.direction,
                units=position.units,
                entry_price=position.entry_price,
                exit_price=exit_price,
                pnl=realized_pnl,
                commission=Decimal("0"),  # Commission can be added later
                opened_at=position.opened_at,
                closed_at=position.closed_at,
            )

        return position

    @staticmethod
    @transaction.atomic
    def close_positions_by_instrument(
        account: OandaAccount,
        instrument: str,
        exit_price: Decimal,
    ) -> List[Position]:
        """
        Close all open positions for a specific instrument.

        Args:
            account: OANDA account
            instrument: Currency pair
            exit_price: Exit price for all positions

        Returns:
            List of closed Position instances

        Requirements: 9.1, 9.5
        """
        open_positions = PositionManager.get_open_positions(
            account=account,
            instrument=instrument,
        )

        closed_positions = []
        for position in open_positions:
            closed_position = PositionManager.close_position(
                position=position,
                exit_price=exit_price,
                create_trade_record=True,
            )
            closed_positions.append(closed_position)

        return closed_positions

    @staticmethod
    @transaction.atomic
    def close_all_positions(
        account: OandaAccount,
        exit_prices: dict[str, Decimal],
    ) -> List[Position]:
        """
        Close all open positions for an account.

        Args:
            account: OANDA account
            exit_prices: Dictionary mapping instrument to exit prices

        Returns:
            List of closed Position instances

        Requirements: 9.1, 9.5
        """
        open_positions = PositionManager.get_open_positions(account=account)

        closed_positions = []
        for position in open_positions:
            exit_price = exit_prices.get(position.instrument)
            if exit_price:
                closed_position = PositionManager.close_position(
                    position=position,
                    exit_price=exit_price,
                    create_trade_record=True,
                )
                closed_positions.append(closed_position)

        return closed_positions

    @staticmethod
    def get_position_count(
        account: Optional[OandaAccount] = None,
        strategy: Optional[Strategy] = None,
        instrument: Optional[str] = None,
        open_only: bool = True,
    ) -> int:
        """
        Get count of positions with optional filtering.

        Args:
            account: Filter by OANDA account (optional)
            strategy: Filter by strategy (optional)
            instrument: Filter by instrument (optional)
            open_only: Count only open positions (default: True)

        Returns:
            Count of positions

        Requirements: 9.1
        """
        queryset = Position.objects.all()

        if open_only:
            queryset = queryset.filter(closed_at__isnull=True)

        if account:
            queryset = queryset.filter(account=account)
        if strategy:
            queryset = queryset.filter(strategy=strategy)
        if instrument:
            queryset = queryset.filter(instrument=instrument)

        return queryset.count()

    @staticmethod
    def get_total_unrealized_pnl(
        account: Optional[OandaAccount] = None,
        strategy: Optional[Strategy] = None,
    ) -> Decimal:
        """
        Calculate total unrealized P&L for open positions.

        Args:
            account: Filter by OANDA account (optional)
            strategy: Filter by strategy (optional)

        Returns:
            Total unrealized P&L

        Requirements: 9.1
        """
        open_positions = PositionManager.get_open_positions(
            account=account,
            strategy=strategy,
        )

        total_pnl = Decimal("0")
        for position in open_positions:
            total_pnl += position.unrealized_pnl

        return total_pnl

    @staticmethod
    def get_positions_by_layer(
        account: OandaAccount,
        layer_number: int,
        open_only: bool = True,
    ) -> List[Position]:
        """
        Get positions for a specific layer.

        Args:
            account: OANDA account
            layer_number: Layer number
            open_only: Return only open positions (default: True)

        Returns:
            List of Position instances

        Requirements: 9.1
        """
        queryset = Position.objects.filter(
            account=account,
            layer_number=layer_number,
        )

        if open_only:
            queryset = queryset.filter(closed_at__isnull=True)

        return list(queryset.order_by("opened_at"))

    @staticmethod
    def get_first_lot_of_layer(
        account: OandaAccount,
        layer_number: int,
    ) -> Optional[Position]:
        """
        Get the first lot position of a specific layer.

        Args:
            account: OANDA account
            layer_number: Layer number

        Returns:
            First lot Position instance or None

        Requirements: 9.1
        """
        try:
            return Position.objects.get(
                account=account,
                layer_number=layer_number,
                is_first_lot=True,
                closed_at__isnull=True,
            )
        except Position.DoesNotExist:
            return None
        except Position.MultipleObjectsReturned:
            # If multiple first lots exist, return the oldest one
            return (
                Position.objects.filter(
                    account=account,
                    layer_number=layer_number,
                    is_first_lot=True,
                    closed_at__isnull=True,
                )
                .order_by("opened_at")
                .first()
            )
