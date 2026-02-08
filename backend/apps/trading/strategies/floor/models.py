"""Data models for Floor strategy."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

from apps.trading.strategies.floor.enums import Direction, Progression, StrategyStatus


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
class Position:
    """Individual position in FIFO order.

    Attributes:
        entry_price: Entry price
        units: Position size in units
        entry_time: Entry timestamp
        direction: LONG or SHORT
    """

    entry_price: Decimal
    units: Decimal
    entry_time: datetime
    direction: Direction

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "entry_price": str(self.entry_price),
            "units": str(self.units),
            "entry_time": self.entry_time.isoformat(),
            "direction": self.direction.value,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> Position:
        """Create from dictionary."""
        return Position(
            entry_price=Decimal(str(data["entry_price"])),
            units=Decimal(str(data["units"])),
            entry_time=datetime.fromisoformat(data["entry_time"]),
            direction=Direction(data["direction"]),
        )


@dataclass
class Layer:
    """Trading layer containing FIFO-ordered positions.

    Attributes:
        index: Layer index (0, 1, 2, ...)
        positions: FIFO-ordered list of positions
        retracement_count: Number of retracements in this layer
    """

    index: int
    positions: list[Position] = field(default_factory=list)
    retracement_count: int = 0

    @property
    def direction(self) -> Direction | None:
        """Get layer direction from first position."""
        return self.positions[0].direction if self.positions else None

    @property
    def total_units(self) -> Decimal:
        """Get total units across all positions."""
        return sum((p.units for p in self.positions), Decimal("0"))

    @property
    def average_entry_price(self) -> Decimal:
        """Calculate weighted average entry price."""
        if not self.positions:
            return Decimal("0")

        total_cost = sum((p.entry_price * p.units for p in self.positions), Decimal("0"))
        total_units = self.total_units

        return total_cost / total_units if total_units > 0 else Decimal("0")

    def add_position(self, position: Position) -> None:
        """Add position to end of FIFO queue."""
        self.positions.append(position)

    def close_units_fifo(self, units_to_close: Decimal) -> list[Position]:
        """Close units from oldest positions first (FIFO).

        Returns:
            List of closed positions (fully or partially)
        """
        closed: list[Position] = []
        remaining = units_to_close

        while remaining > 0 and self.positions:
            oldest = self.positions[0]

            if oldest.units <= remaining:
                # Close entire position
                closed.append(oldest)
                remaining -= oldest.units
                self.positions.pop(0)
            else:
                # Partial close
                closed_portion = Position(
                    entry_price=oldest.entry_price,
                    units=remaining,
                    entry_time=oldest.entry_time,
                    direction=oldest.direction,
                )
                closed.append(closed_portion)
                oldest.units -= remaining
                remaining = Decimal("0")

        return closed

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "index": self.index,
            "positions": [p.to_dict() for p in self.positions],
            "retracement_count": self.retracement_count,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> Layer:
        """Create from dictionary."""
        return Layer(
            index=data["index"],
            positions=[Position.from_dict(p) for p in data.get("positions", [])],
            retracement_count=data.get("retracement_count", 0),
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
        layers: List of active layers
        candles: Historical candle data
        current_candle_close: Current candle close price
        last_mid: Last mid price
        last_bid: Last bid price
        last_ask: Last ask price
        account_balance: Account balance for margin calculation
        account_nav: Net asset value (balance + unrealized P/L)
    """

    status: StrategyStatus = StrategyStatus.RUNNING
    layers: list[Layer] = field(default_factory=list)
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
            "layers": [layer.to_dict() for layer in self.layers],
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
            layers=[Layer.from_dict(layer) for layer in data.get("layers", [])],
            candles=[CandleData.from_dict(c) for c in data.get("candles", [])],
            current_candle_close=_decimal_or_none(data.get("current_candle_close")),
            last_mid=_decimal_or_none(data.get("last_mid")),
            last_bid=_decimal_or_none(data.get("last_bid")),
            last_ask=_decimal_or_none(data.get("last_ask")),
            account_balance=Decimal(str(data.get("account_balance", "0"))),
            account_nav=Decimal(str(data.get("account_nav", "0"))),
        )
