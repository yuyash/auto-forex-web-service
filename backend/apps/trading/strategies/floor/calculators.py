"""Calculation utilities for Floor strategy."""

from decimal import Decimal

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
