"""
P&L calculation module.

This module provides the PnLCalculator class for calculating profit and loss
for trading positions, including unrealized P&L on tick updates and realized
P&L on position closure.

Requirements: 9.1, 9.2
"""

from decimal import Decimal
from typing import List

from trading.models import Position


class PnLCalculator:
    """
    Calculates profit and loss for trading positions.

    This class provides methods for:
    - Calculating unrealized P&L based on current market prices
    - Calculating realized P&L when positions are closed
    - Batch P&L calculations for multiple positions

    Requirements: 9.1, 9.2
    """

    @staticmethod
    def calculate_unrealized_pnl(
        position: Position,
        current_price: Decimal,
    ) -> Decimal:
        """
        Calculate unrealized P&L for a position based on current price.

        Args:
            position: Position to calculate P&L for
            current_price: Current market price

        Returns:
            Unrealized P&L

        Requirements: 9.1, 9.2
        """
        return position.calculate_unrealized_pnl(current_price)

    @staticmethod
    def calculate_realized_pnl(
        position: Position,
        exit_price: Decimal,
    ) -> Decimal:
        """
        Calculate realized P&L for a position at exit price in USD.

        For USD/JPY:
        - 1 lot = 1,000 USD
        - P&L in JPY = price_diff × units × 1000
        - P&L in USD = P&L_JPY / exit_price

        Args:
            position: Position to calculate P&L for
            exit_price: Exit price for the position

        Returns:
            Realized P&L in USD

        Requirements: 9.1, 9.2
        """
        price_diff = exit_price - position.entry_price

        if position.direction == "short":
            price_diff = -price_diff

        # Convert lot size to base currency amount (1 lot = 1,000 units)
        base_currency_amount = position.units * Decimal("1000")
        realized_pnl = price_diff * base_currency_amount

        # For JPY pairs, convert from JPY to USD
        if "JPY" in position.instrument:
            realized_pnl = realized_pnl / exit_price

        return realized_pnl

    @staticmethod
    def calculate_batch_unrealized_pnl(
        positions: List[Position],
        prices: dict[str, Decimal],
    ) -> dict[str, Decimal]:
        """
        Calculate unrealized P&L for multiple positions.

        Args:
            positions: List of positions to calculate P&L for
            prices: Dictionary mapping instrument to current prices

        Returns:
            Dictionary mapping position IDs to unrealized P&L values

        Requirements: 9.1, 9.2
        """
        pnl_results = {}

        for position in positions:
            current_price = prices.get(position.instrument)
            if current_price:
                pnl = PnLCalculator.calculate_unrealized_pnl(
                    position=position,
                    current_price=current_price,
                )
                pnl_results[position.position_id] = pnl

        return pnl_results

    @staticmethod
    def calculate_total_unrealized_pnl(
        positions: List[Position],
        prices: dict[str, Decimal],
    ) -> Decimal:
        """
        Calculate total unrealized P&L for multiple positions.

        Args:
            positions: List of positions to calculate P&L for
            prices: Dictionary mapping instrument to current prices

        Returns:
            Total unrealized P&L

        Requirements: 9.1, 9.2
        """
        total_pnl = Decimal("0")

        for position in positions:
            current_price = prices.get(position.instrument)
            if current_price:
                pnl = PnLCalculator.calculate_unrealized_pnl(
                    position=position,
                    current_price=current_price,
                )
                total_pnl += pnl

        return total_pnl

    @staticmethod
    def calculate_pnl_percentage(
        position: Position,
        current_price: Decimal,
    ) -> Decimal:
        """
        Calculate P&L as a percentage of entry value.

        Args:
            position: Position to calculate P&L percentage for
            current_price: Current market price

        Returns:
            P&L percentage

        Requirements: 9.1, 9.2
        """
        pnl = PnLCalculator.calculate_unrealized_pnl(position, current_price)
        entry_value = position.entry_price * position.units

        if entry_value == 0:
            return Decimal("0")

        pnl_percentage = (pnl / entry_value) * Decimal("100")
        return pnl_percentage

    @staticmethod
    def calculate_pip_value(
        instrument: str,
        units: Decimal,
        pip_location: int = 4,
    ) -> Decimal:
        """
        Calculate the value of one pip for a position.

        Args:
            instrument: Currency pair (e.g., 'EUR_USD')
            units: Number of units
            pip_location: Decimal place of pip (default: 4 for most pairs)

        Returns:
            Value of one pip

        Requirements: 9.1, 9.2
        """
        # For JPY pairs, pip is at 2nd decimal place
        if "JPY" in instrument:
            pip_location = 2

        pip_value = units * Decimal(10) ** (-pip_location)
        return pip_value

    @staticmethod
    def calculate_pips_profit(
        position: Position,
        current_price: Decimal,
    ) -> Decimal:
        """
        Calculate profit/loss in pips.

        Args:
            position: Position to calculate pips for
            current_price: Current market price

        Returns:
            Profit/loss in pips

        Requirements: 9.1, 9.2
        """
        price_diff = current_price - position.entry_price

        if position.direction == "short":
            price_diff = -price_diff

        # Determine pip location based on instrument
        pip_location = 4
        if "JPY" in position.instrument:
            pip_location = 2

        pips = price_diff * Decimal(10) ** pip_location
        return pips

    @staticmethod
    def calculate_break_even_price(
        position: Position,
        commission: Decimal | None = None,
    ) -> Decimal:
        """
        Calculate break-even price including commission.

        Args:
            position: Position to calculate break-even for
            commission: Commission paid for the trade (optional, defaults to 0)

        Returns:
            Break-even price

        Requirements: 9.1, 9.2
        """
        if commission is None:
            commission = Decimal("0")

        if position.units == 0:
            return position.entry_price

        commission_per_unit = commission / position.units

        if position.direction == "long":
            break_even = position.entry_price + commission_per_unit
        else:  # short
            break_even = position.entry_price - commission_per_unit

        return break_even

    @staticmethod
    def calculate_required_price_for_target(
        position: Position,
        target_pnl: Decimal,
    ) -> Decimal:
        """
        Calculate the price required to achieve a target P&L.

        Args:
            position: Position to calculate target price for
            target_pnl: Target profit/loss amount

        Returns:
            Required price to achieve target P&L

        Requirements: 9.1, 9.2
        """
        if position.units == 0:
            return position.entry_price

        price_diff_needed = target_pnl / position.units

        if position.direction == "long":
            required_price = position.entry_price + price_diff_needed
        else:  # short
            required_price = position.entry_price - price_diff_needed

        return required_price
