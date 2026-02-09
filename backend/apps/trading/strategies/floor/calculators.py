"""Calculation utilities for Floor strategy."""

from decimal import Decimal

from apps.trading.models import Layer
from apps.trading.strategies.floor.enums import Direction, Progression


class ProgressionCalculator:
    """Calculate progressive values."""

    @staticmethod
    def calculate(
        base: Decimal,
        index: int,
        mode: Progression,
        increment: Decimal,
    ) -> Decimal:
        """Calculate progressive value.

        Args:
            base: Base value
            index: Current index (0, 1, 2, ...)
            mode: Progression mode
            increment: Increment value

        Returns:
            Calculated value
        """
        if mode == Progression.CONSTANT:
            return base

        if mode == Progression.ADDITIVE:
            return base + (increment * Decimal(index))

        if mode == Progression.SUBTRACTIVE:
            result = base - (increment * Decimal(index))
            return max(result, Decimal("0"))  # Never go negative

        if mode == Progression.MULTIPLICATIVE:
            # 2の累乗をかける: base * (2 ^ index)
            multiplier = Decimal(2**index)
            return base * multiplier

        if mode == Progression.DIVISIVE:
            # 2の累乗で割る: base / (2 ^ index)
            if index == 0:
                return base
            divisor = Decimal(2**index)
            return base / divisor

        return base


class PnLCalculator:
    """Calculate profit and loss."""

    def __init__(self, pip_size: Decimal) -> None:
        """Initialize calculator.

        Args:
            pip_size: Pip size for the instrument
        """
        self.pip_size = pip_size

    def pips_between(self, price1: Decimal, price2: Decimal) -> Decimal:
        """Calculate pips between two prices.

        Args:
            price1: First price
            price2: Second price

        Returns:
            Pips difference (positive if price2 > price1)
        """
        return (price2 - price1) / self.pip_size

    def calculate_layer_pnl_pips(
        self,
        layer: Layer,
        current_bid: Decimal,
        current_ask: Decimal,
    ) -> Decimal:
        """Calculate layer P&L in pips.

        Args:
            layer: Layer to calculate
            current_bid: Current bid price
            current_ask: Current ask price

        Returns:
            P&L in pips (positive for profit, negative for loss)
        """
        if layer.position_count == 0 or not layer.direction:
            return Decimal("0")

        avg_entry = layer.average_entry_price

        if layer.direction == Direction.LONG:
            # LONGの場合、bidで決済
            return self.pips_between(avg_entry, current_bid)
        else:
            # SHORTの場合、askで決済
            return self.pips_between(current_ask, avg_entry)

    def calculate_unrealized_pnl(
        self,
        layer: Layer,
        current_bid: Decimal,
        current_ask: Decimal,
    ) -> Decimal:
        """Calculate unrealized P&L in quote currency.

        Args:
            layer: Layer to calculate
            current_bid: Current bid price
            current_ask: Current ask price

        Returns:
            Unrealized P&L in quote currency
        """
        if layer.position_count == 0 or not layer.direction:
            return Decimal("0")

        pnl_pips = self.calculate_layer_pnl_pips(layer, current_bid, current_ask)
        return pnl_pips * self.pip_size * layer.total_units


class MarginCalculator:
    """Calculate margin requirements."""

    def __init__(self, margin_rate: Decimal) -> None:
        """Initialize calculator.

        Args:
            margin_rate: Margin rate (e.g., 0.04 for 4%)
        """
        self.margin_rate = margin_rate

    def calculate_required_margin(
        self,
        current_price: Decimal,
        total_units: Decimal,
    ) -> Decimal:
        """Calculate required margin.

        Formula: current_price * total_units * margin_rate

        Args:
            current_price: Current market price
            total_units: Total position size

        Returns:
            Required margin
        """
        return current_price * total_units * self.margin_rate

    def calculate_margin_ratio(
        self,
        required_margin: Decimal,
        nav: Decimal,
    ) -> Decimal:
        """Calculate margin ratio (証拠金清算割合).

        Formula: required_margin / nav

        Args:
            required_margin: Required margin
            nav: Net asset value (有効証拠金)

        Returns:
            Margin ratio (1.0 = 100%)
        """
        if nav <= 0:
            return Decimal("999")  # Extremely high ratio

        return required_margin / nav


class TrendDetector:
    """Detect trend from candle data."""

    @staticmethod
    def detect_direction(candle_closes: list[Decimal]) -> Direction:
        """Detect trend direction from candle closes.

        Simple momentum: compare first and last candle.

        Args:
            candle_closes: List of candle close prices

        Returns:
            Direction.LONG if uptrend, Direction.SHORT if downtrend
        """
        if len(candle_closes) < 2:
            return Direction.LONG  # Default

        first = candle_closes[0]
        last = candle_closes[-1]

        return Direction.LONG if last >= first else Direction.SHORT
