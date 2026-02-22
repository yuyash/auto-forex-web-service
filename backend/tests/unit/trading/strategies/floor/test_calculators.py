"""Unit tests for floor strategy calculators."""

from decimal import Decimal

from apps.trading.strategies.floor.calculators import (
    MarginCalculator,
    ProgressionCalculator,
    TrendDetector,
)
from apps.trading.strategies.floor.enums import Direction, Progression


class TestProgressionCalculator:
    def test_constant(self):
        assert ProgressionCalculator.calculate(
            Decimal("100"), 3, Progression.CONSTANT, Decimal("10")
        ) == Decimal("100")

    def test_additive(self):
        assert ProgressionCalculator.calculate(
            Decimal("100"), 2, Progression.ADDITIVE, Decimal("10")
        ) == Decimal("120")

    def test_subtractive(self):
        assert ProgressionCalculator.calculate(
            Decimal("100"), 2, Progression.SUBTRACTIVE, Decimal("10")
        ) == Decimal("80")

    def test_subtractive_floor_zero(self):
        assert ProgressionCalculator.calculate(
            Decimal("10"), 5, Progression.SUBTRACTIVE, Decimal("10")
        ) == Decimal("0")

    def test_multiplicative(self):
        assert ProgressionCalculator.calculate(
            Decimal("100"), 2, Progression.MULTIPLICATIVE, Decimal("0")
        ) == Decimal("400")

    def test_divisive(self):
        assert ProgressionCalculator.calculate(
            Decimal("100"), 2, Progression.DIVISIVE, Decimal("0")
        ) == Decimal("25")

    def test_divisive_index_zero(self):
        assert ProgressionCalculator.calculate(
            Decimal("100"), 0, Progression.DIVISIVE, Decimal("0")
        ) == Decimal("100")


class TestMarginCalculator:
    def test_required_margin(self):
        calc = MarginCalculator(Decimal("0.04"))
        result = calc.calculate_required_margin(Decimal("150"), Decimal("1000"))
        assert result == Decimal("6000")

    def test_margin_ratio(self):
        calc = MarginCalculator(Decimal("0.04"))
        assert calc.calculate_margin_ratio(Decimal("6000"), Decimal("10000")) == Decimal("0.6")

    def test_margin_ratio_zero_nav(self):
        calc = MarginCalculator(Decimal("0.04"))
        assert calc.calculate_margin_ratio(Decimal("6000"), Decimal("0")) == Decimal("999")


class TestTrendDetector:
    def test_uptrend(self):
        assert TrendDetector.detect_direction([Decimal("100"), Decimal("110")]) == Direction.LONG

    def test_downtrend(self):
        assert TrendDetector.detect_direction([Decimal("110"), Decimal("100")]) == Direction.SHORT

    def test_single_candle_default(self):
        assert TrendDetector.detect_direction([Decimal("100")]) == Direction.LONG
