from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal

from apps.trading.strategies.adaptive_net.models import MetricContext, MetricSignal


def clamp(value: Decimal, minimum: Decimal, maximum: Decimal) -> Decimal:
    return max(minimum, min(maximum, value))


def mean(values: tuple[Decimal, ...]) -> Decimal:
    if not values:
        return Decimal("0")
    return sum(values, Decimal("0")) / Decimal(len(values))


def average_abs_return(prices: tuple[Decimal, ...]) -> Decimal:
    if len(prices) < 2:
        return Decimal("0")
    returns = [abs(prices[i] - prices[i - 1]) for i in range(1, len(prices))]
    return sum(returns, Decimal("0")) / Decimal(len(returns))


class SignalMetric(ABC):
    name: str

    @abstractmethod
    def evaluate(self, context: MetricContext) -> MetricSignal:
        raise NotImplementedError


class TrendMomentumMetric(SignalMetric):
    name = "trend_momentum"

    def evaluate(self, context: MetricContext) -> MetricSignal:
        prices = context.prices
        if len(prices) < 10:
            return MetricSignal(self.name, Decimal("0"), Decimal("0"), reason="warming_up")
        window = min(20, len(prices) - 1)
        momentum = prices[-1] - prices[-window]
        noise = average_abs_return(prices[-window:]) or context.pip_size
        raw = momentum / (noise * Decimal(window).sqrt())
        score = clamp(raw / Decimal("4"), Decimal("-1"), Decimal("1"))
        confidence = clamp(abs(raw) / Decimal("3"), Decimal("0"), Decimal("1"))
        return MetricSignal(
            self.name,
            score,
            confidence,
            reason="recent directional move normalized by realized noise",
        )


class MeanReversionMetric(SignalMetric):
    name = "mean_reversion"

    def evaluate(self, context: MetricContext) -> MetricSignal:
        prices = context.prices
        if len(prices) < 20:
            return MetricSignal(self.name, Decimal("0"), Decimal("0"), reason="warming_up")
        window = prices[-min(40, len(prices)) :]
        baseline = mean(window)
        avg_dev = mean(tuple(abs(price - baseline) for price in window)) or context.pip_size
        z_score = (prices[-1] - baseline) / avg_dev
        score = clamp(-z_score / Decimal("3"), Decimal("-1"), Decimal("1"))
        confidence = clamp(abs(z_score) / Decimal("3"), Decimal("0"), Decimal("1"))
        return MetricSignal(
            self.name,
            score,
            confidence,
            reason="distance from rolling mean converted to contrarian pressure",
        )


class RegimeMetric(SignalMetric):
    name = "regime"

    def evaluate(self, context: MetricContext) -> MetricSignal:
        prices = context.prices
        if len(prices) < 30:
            return MetricSignal(self.name, Decimal("0"), Decimal("0"), reason="warming_up")
        recent = prices[-20:]
        longer = prices[-min(80, len(prices)) :]
        trend = recent[-1] - recent[0]
        recent_noise = average_abs_return(recent) or context.pip_size
        long_noise = average_abs_return(longer) or recent_noise
        volatility_ratio = recent_noise / long_noise if long_noise else Decimal("1")
        trend_strength = abs(trend) / (recent_noise * Decimal(len(recent)).sqrt())
        direction = Decimal("1") if trend > 0 else Decimal("-1") if trend < 0 else Decimal("0")
        if volatility_ratio > context.config.high_volatility_ratio:
            return MetricSignal(
                self.name,
                Decimal("0"),
                Decimal("1"),
                Decimal("0.35"),
                reason="high volatility regime reduces directional risk",
            )
        score = direction * clamp(trend_strength / Decimal("4"), Decimal("0"), Decimal("1"))
        confidence = clamp(trend_strength / Decimal("3"), Decimal("0"), Decimal("1"))
        return MetricSignal(
            self.name,
            score,
            confidence,
            reason="regime favors directional exposure when trend strength is persistent",
        )


class RiskConditionMetric(SignalMetric):
    name = "risk_condition"

    def evaluate(self, context: MetricContext) -> MetricSignal:
        spread_ratio = (
            context.spread_pips / context.config.max_spread_pips
            if context.config.max_spread_pips > 0
            else Decimal("0")
        )
        if spread_ratio >= 1:
            return MetricSignal(
                self.name,
                Decimal("0"),
                Decimal("1"),
                Decimal("0"),
                reason="spread above configured maximum",
            )
        multiplier = clamp(Decimal("1") - spread_ratio * Decimal("0.5"), Decimal("0"), Decimal("1"))
        return MetricSignal(
            self.name,
            Decimal("0"),
            Decimal("1") - spread_ratio,
            multiplier,
            reason="spread and execution cost gate",
        )


class InventoryExposureMetric(SignalMetric):
    name = "inventory_exposure"

    def evaluate(self, context: MetricContext) -> MetricSignal:
        if context.max_net_units <= 0:
            return MetricSignal(self.name, Decimal("0"), Decimal("0"), reason="no_limit")
        exposure = Decimal(context.current_net_units) / Decimal(context.max_net_units)
        score = clamp(-exposure, Decimal("-1"), Decimal("1"))
        confidence = clamp(abs(exposure), Decimal("0"), Decimal("1"))
        multiplier = clamp(
            Decimal("1") - abs(exposure) * Decimal("0.35"), Decimal("0.25"), Decimal("1")
        )
        return MetricSignal(
            self.name,
            score,
            confidence,
            multiplier,
            reason="existing net exposure penalizes adding in the same direction",
        )


class TimesFMForecastMetric(SignalMetric):
    name = "timesfm_forecast"

    def evaluate(self, context: MetricContext) -> MetricSignal:
        _ = context
        return MetricSignal(
            self.name,
            Decimal("0"),
            Decimal("0"),
            Decimal("1"),
            reason="neutral placeholder until a TimesFM forecast provider is connected",
        )


def default_metrics(*, include_timesfm: bool) -> list[SignalMetric]:
    metrics: list[SignalMetric] = [
        RegimeMetric(),
        TrendMomentumMetric(),
        MeanReversionMetric(),
        RiskConditionMetric(),
        InventoryExposureMetric(),
    ]
    if include_timesfm:
        metrics.append(TimesFMForecastMetric())
    return metrics
