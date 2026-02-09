"""Data models for Floor strategy."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from apps.trading.strategies.floor.enums import Progression, StrategyStatus


@dataclass(frozen=True, slots=True)
class FloorStrategyConfig:
    """Configuration for Floor strategy.

    Attributes:
        # Candle settings for trend detection
        candle_granularity_seconds: Candle granularity in seconds
        candle_lookback_count: Number of candles to analyze for trend

        # Position sizing
        initial_units: Initial position size in units
        unit_progression: How units change with retracements
        unit_increment: Increment value for unit progression

        # Profit and retracement
        profit_pips: Profit target in pips
        initial_retracement_pips: Initial retracement trigger distance
        retracement_progression: How retracement distance changes
        retracement_increment: Increment value for retracement progression

        # Layer limits
        max_retracements_per_layer: Maximum retracements in one layer
        max_layers: Maximum number of layers

        # Margin protection
        margin_closeout_threshold: Margin ratio threshold (e.g., 0.8 for 80%)

        # Account settings
        hedging_enabled: Whether hedging is enabled on account
        leverage: Account leverage (e.g., 25 for 25x)
        margin_rate: Margin rate (e.g., 0.04 for 4%)
    """

    # Candle settings
    candle_granularity_seconds: int
    candle_lookback_count: int

    # Position sizing
    initial_units: Decimal
    unit_progression: Progression
    unit_increment: Decimal

    # Profit and retracement
    profit_pips: Decimal
    initial_retracement_pips: Decimal
    retracement_progression: Progression
    retracement_increment: Decimal

    # Layer limits
    max_retracements_per_layer: int
    max_layers: int

    # Margin protection
    margin_closeout_threshold: Decimal

    # Account settings
    hedging_enabled: bool
    leverage: Decimal
    margin_rate: Decimal

    @staticmethod
    def from_dict(raw: dict[str, Any]) -> FloorStrategyConfig:
        """Create config from dictionary."""

        def _decimal(key: str, default: str = "0") -> Decimal:
            val = raw.get(key, default)
            return Decimal(str(val))

        def _int(key: str, default: int = 0) -> int:
            return int(raw.get(key, default))

        def _bool(key: str, default: bool = False) -> bool:
            return bool(raw.get(key, default))

        def _progression(key: str, default: Progression = Progression.CONSTANT) -> Progression:
            val = raw.get(key, default.value)
            try:
                return Progression(val)
            except ValueError:
                return default

        return FloorStrategyConfig(
            candle_granularity_seconds=_int("candle_granularity_seconds", 60),
            candle_lookback_count=_int("candle_lookback_count", 20),
            initial_units=_decimal("initial_units", "1000"),
            unit_progression=_progression("unit_progression", Progression.CONSTANT),
            unit_increment=_decimal("unit_increment", "1000"),
            profit_pips=_decimal("profit_pips", "10"),
            initial_retracement_pips=_decimal("initial_retracement_pips", "5"),
            retracement_progression=_progression("retracement_progression", Progression.CONSTANT),
            retracement_increment=_decimal("retracement_increment", "5"),
            max_retracements_per_layer=_int("max_retracements_per_layer", 5),
            max_layers=_int("max_layers", 3),
            margin_closeout_threshold=_decimal("margin_closeout_threshold", "0.8"),
            hedging_enabled=_bool("hedging_enabled", False),
            leverage=_decimal("leverage", "25"),
            margin_rate=_decimal("margin_rate", "0.04"),
        )


@dataclass
class CandleData:
    """Candle data for trend detection."""

    bucket_start_epoch: int
    close_price: Decimal

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "bucket_start_epoch": self.bucket_start_epoch,
            "close_price": str(self.close_price),
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> CandleData:
        """Create from dictionary."""
        return CandleData(
            bucket_start_epoch=data["bucket_start_epoch"],
            close_price=Decimal(str(data["close_price"])),
        )


@dataclass
class FloorStrategyState:
    """State for Floor strategy.

    Attributes:
        status: Strategy status
        candles: Historical candle data
        current_candle_close: Current candle close price
        last_mid: Last mid price
        last_bid: Last bid price
        last_ask: Last ask price
        account_balance: Account balance for margin calculation
        account_nav: Net asset value (balance + unrealized P/L)
    """

    status: StrategyStatus = StrategyStatus.RUNNING
    candles: list[CandleData] = field(default_factory=list)
    current_candle_close: Decimal | None = None
    last_mid: Decimal | None = None
    last_bid: Decimal | None = None
    last_ask: Decimal | None = None
    account_balance: Decimal = Decimal("0")
    account_nav: Decimal = Decimal("0")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "status": self.status.value,
            "candles": [c.to_dict() for c in self.candles],
            "current_candle_close": str(self.current_candle_close)
            if self.current_candle_close
            else None,
            "last_mid": str(self.last_mid) if self.last_mid else None,
            "last_bid": str(self.last_bid) if self.last_bid else None,
            "last_ask": str(self.last_ask) if self.last_ask else None,
            "account_balance": str(self.account_balance),
            "account_nav": str(self.account_nav),
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> FloorStrategyState:
        """Create from dictionary."""

        def _decimal_or_none(val: Any) -> Decimal | None:
            return Decimal(str(val)) if val is not None else None

        return FloorStrategyState(
            status=StrategyStatus(data.get("status", StrategyStatus.RUNNING.value)),
            candles=[CandleData.from_dict(c) for c in data.get("candles", [])],
            current_candle_close=_decimal_or_none(data.get("current_candle_close")),
            last_mid=_decimal_or_none(data.get("last_mid")),
            last_bid=_decimal_or_none(data.get("last_bid")),
            last_ask=_decimal_or_none(data.get("last_ask")),
            account_balance=Decimal(str(data.get("account_balance", "0"))),
            account_nav=Decimal(str(data.get("account_nav", "0"))),
        )
