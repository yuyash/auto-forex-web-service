"""Enums for Floor strategy."""

from enum import StrEnum


class StrategyStatus(StrEnum):
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"


class Direction(StrEnum):
    LONG = "long"
    SHORT = "short"


class Progression(StrEnum):
    EQUAL = "equal"
    ADDITIVE = "additive"
    EXPONENTIAL = "exponential"
    INVERSE = "inverse"


class DirectionMethod(StrEnum):
    MOMENTUM = "momentum"
    SMA_CROSSOVER = "sma_crossover"
    EMA_CROSSOVER = "ema_crossover"
    PRICE_VS_SMA = "price_vs_sma"
    RSI = "rsi"
    OHLC_SMA_CROSSOVER = "ohlc_sma_crossover"
    OHLC_EMA_CROSSOVER = "ohlc_ema_crossover"
    OHLC_PRICE_VS_SMA = "ohlc_price_vs_sma"


class MomentumLookbackSource(StrEnum):
    TICKS = "ticks"
    CANDLES = "candles"


class LotMode(StrEnum):
    """Lot size calculation mode."""

    ADDITIVE = "additive"
    MULTIPLICATIVE = "multiplicative"
