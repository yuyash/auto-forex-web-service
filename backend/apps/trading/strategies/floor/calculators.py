"""Calculator components for Floor strategy."""

from decimal import Decimal

from apps.trading.strategies.floor.enums import Direction
from apps.trading.strategies.floor.models import LayerState


class PriceCalculator:
    """Handles price and P&L calculations."""

    def __init__(self, pip_size: Decimal) -> None:
        self.pip_size = pip_size

    def pips_between(self, price_a: Decimal, price_b: Decimal) -> Decimal:
        """Calculate pips between two prices."""
        return (price_b - price_a) / self.pip_size

    def calculate_pnl(self, layers: list[LayerState], bid: Decimal, ask: Decimal) -> Decimal:
        """Calculate net P&L in pips, weighted by lot size."""
        total = Decimal("0")
        weight = Decimal("0")

        for layer in layers:
            if layer.lot_size <= 0:
                continue

            mark = bid if layer.direction == Direction.LONG else ask
            pips = self.pips_between(layer.entry_price, mark)

            if layer.direction == Direction.SHORT:
                pips = -pips

            total += pips * layer.lot_size
            weight += layer.lot_size

        return total / weight if weight > 0 else Decimal("0")

    def against_position_pips(self, layer: LayerState, bid: Decimal, ask: Decimal) -> Decimal:
        """Calculate adverse movement in pips for a layer."""
        mark = bid if layer.direction == Direction.LONG else ask

        if layer.direction == Direction.LONG:
            if mark >= layer.entry_price:
                return Decimal("0")
            return abs(self.pips_between(layer.entry_price, mark))
        else:
            if mark <= layer.entry_price:
                return Decimal("0")
            return abs(self.pips_between(layer.entry_price, mark))


class IndicatorCalculator:
    """Handles technical indicator calculations."""

    @staticmethod
    def sma(values: list[Decimal]) -> Decimal:
        """Calculate Simple Moving Average."""
        return sum(values) / Decimal(len(values)) if values else Decimal("0")

    @staticmethod
    def ema(values: list[Decimal], period: int) -> Decimal:
        """Calculate Exponential Moving Average."""
        if not values:
            return Decimal("0")

        k = Decimal("2") / (Decimal(period) + Decimal("1"))
        ema_val = values[0]

        for v in values[1:]:
            ema_val = (v * k) + (ema_val * (Decimal("1") - k))

        return ema_val

    @staticmethod
    def rsi(values: list[Decimal], period: int) -> Decimal:
        """Calculate Relative Strength Index."""
        if len(values) < period + 1:
            return Decimal("50")

        gains: list[Decimal] = []
        losses: list[Decimal] = []

        for i in range(-period, 0):
            delta = values[i] - values[i - 1]
            if delta >= 0:
                gains.append(delta)
                losses.append(Decimal("0"))
            else:
                gains.append(Decimal("0"))
                losses.append(-delta)

        avg_gain = sum(gains) / Decimal(period)
        avg_loss = sum(losses) / Decimal(period)

        if avg_loss == 0:
            return Decimal("100")

        rs = avg_gain / avg_loss
        return Decimal("100") - (Decimal("100") / (Decimal("1") + rs))
