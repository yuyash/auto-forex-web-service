"""
Fundamental + Technical Strategy implementation.

This module implements a Fundamental + Technical Strategy that:
- Integrates economic calendar events (placeholder for news events)
- Implements technical confirmation (trend, support/resistance)
- Implements position sizing based on event importance
- Implements pre-event and post-event trading logic

Requirements: 5.1, 5.3
"""

from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any

from .base_strategy import BaseStrategy
from .models import Order, Position
from .strategy_registry import register_strategy
from .tick_data_models import TickData


class EventImportance(Enum):
    """Economic event importance levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TrendDirection(Enum):
    """Market trend direction."""

    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class EconomicEvent:
    """
    Represents an economic calendar event.

    This is a placeholder implementation. In production, this would integrate
    with an economic calendar API.

    Requirements: 5.1, 5.3
    """

    def __init__(
        self,
        event_time: datetime,
        currency: str,
        importance: EventImportance,
        event_name: str,
    ) -> None:
        """
        Initialize economic event.

        Args:
            event_time: Time of the event
            currency: Currency affected (e.g., 'USD', 'EUR')
            importance: Event importance level
            event_name: Name of the event
        """
        self.event_time = event_time
        self.currency = currency
        self.importance = importance
        self.event_name = event_name


class EconomicCalendar:
    """
    Economic calendar manager.

    Placeholder implementation for economic event tracking.
    In production, this would fetch events from an external API.

    Requirements: 5.1, 5.3
    """

    def __init__(self) -> None:
        """Initialize economic calendar."""
        self.events: list[EconomicEvent] = []

    def add_event(self, event: EconomicEvent) -> None:
        """
        Add an event to the calendar.

        Args:
            event: Economic event to add
        """
        self.events.append(event)

    def get_upcoming_events(
        self, instrument: str, current_time: datetime, lookforward_minutes: int = 60
    ) -> list[EconomicEvent]:
        """
        Get upcoming events for an instrument.

        Args:
            instrument: Currency pair (e.g., 'EUR_USD')
            current_time: Current time
            lookforward_minutes: Minutes to look forward

        Returns:
            List of upcoming events
        """
        # Extract currencies from instrument
        currencies = instrument.split("_")

        upcoming: list[EconomicEvent] = []
        end_time = current_time + timedelta(minutes=lookforward_minutes)

        for event in self.events:
            if current_time <= event.event_time <= end_time and event.currency in currencies:
                upcoming.append(event)

        return sorted(upcoming, key=lambda e: e.event_time)

    def get_recent_events(
        self, instrument: str, current_time: datetime, lookback_minutes: int = 30
    ) -> list[EconomicEvent]:
        """
        Get recent events for an instrument.

        Args:
            instrument: Currency pair (e.g., 'EUR_USD')
            current_time: Current time
            lookback_minutes: Minutes to look back

        Returns:
            List of recent events
        """
        # Extract currencies from instrument
        currencies = instrument.split("_")

        recent: list[EconomicEvent] = []
        start_time = current_time - timedelta(minutes=lookback_minutes)

        for event in self.events:
            if start_time <= event.event_time <= current_time and event.currency in currencies:
                recent.append(event)

        return sorted(recent, key=lambda e: e.event_time, reverse=True)


class TechnicalAnalyzer:
    """
    Technical analysis component for trend and support/resistance detection.

    Requirements: 5.1, 5.3
    """

    def __init__(self, ma_short_period: int = 20, ma_long_period: int = 50) -> None:
        """
        Initialize technical analyzer.

        Args:
            ma_short_period: Short moving average period
            ma_long_period: Long moving average period
        """
        self.ma_short_period = ma_short_period
        self.ma_long_period = ma_long_period
        self.price_history: dict[str, list[tuple[datetime, Decimal]]] = {}

    def add_price(self, instrument: str, timestamp: datetime, price: Decimal) -> None:
        """
        Add price to history.

        Args:
            instrument: Currency pair
            timestamp: Price timestamp
            price: Price value
        """
        if instrument not in self.price_history:
            self.price_history[instrument] = []

        self.price_history[instrument].append((timestamp, price))

        # Keep only necessary history (2x long period)
        max_history = self.ma_long_period * 2
        if len(self.price_history[instrument]) > max_history:
            self.price_history[instrument] = self.price_history[instrument][-max_history:]

    def calculate_ma(self, instrument: str, period: int) -> Decimal | None:
        """
        Calculate moving average.

        Args:
            instrument: Currency pair
            period: MA period

        Returns:
            Moving average or None if insufficient data
        """
        if instrument not in self.price_history:
            return None

        history = self.price_history[instrument]
        if len(history) < period:
            return None

        recent_prices = [price for _, price in history[-period:]]
        return sum(recent_prices) / Decimal(str(period))

    def detect_trend(self, instrument: str) -> TrendDirection:
        """
        Detect market trend using moving averages.

        Args:
            instrument: Currency pair

        Returns:
            Trend direction
        """
        ma_short = self.calculate_ma(instrument, self.ma_short_period)
        ma_long = self.calculate_ma(instrument, self.ma_long_period)

        if ma_short is None or ma_long is None:
            return TrendDirection.NEUTRAL

        if ma_short > ma_long:
            return TrendDirection.BULLISH
        if ma_short < ma_long:
            return TrendDirection.BEARISH

        return TrendDirection.NEUTRAL

    def find_support_resistance(
        self, instrument: str, lookback_periods: int = 50
    ) -> tuple[Decimal | None, Decimal | None]:
        """
        Find support and resistance levels.

        Args:
            instrument: Currency pair
            lookback_periods: Number of periods to analyze

        Returns:
            Tuple of (support, resistance) or (None, None)
        """
        if instrument not in self.price_history:
            return None, None

        history = self.price_history[instrument]
        if len(history) < lookback_periods:
            return None, None

        recent_prices = [price for _, price in history[-lookback_periods:]]

        # Simple support/resistance: min and max of recent prices
        support = min(recent_prices)
        resistance = max(recent_prices)

        return support, resistance


class FundamentalTechnicalStrategy(BaseStrategy):
    """
    Fundamental + Technical Strategy.

    This strategy combines economic event analysis with technical confirmation:
    - Monitors economic calendar for high-impact events
    - Confirms entry with technical trend and support/resistance
    - Sizes positions based on event importance
    - Implements pre-event and post-event trading logic

    Requirements: 5.1, 5.3
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the Fundamental + Technical Strategy."""
        super().__init__(*args, **kwargs)

        # Configuration
        self.base_units = Decimal(str(self.get_config_value("base_units", 1000)))
        self.high_importance_multiplier = Decimal(
            str(self.get_config_value("high_importance_multiplier", 2.0))
        )
        self.medium_importance_multiplier = Decimal(
            str(self.get_config_value("medium_importance_multiplier", 1.5))
        )
        self.low_importance_multiplier = Decimal(
            str(self.get_config_value("low_importance_multiplier", 1.0))
        )
        self.pre_event_minutes = int(self.get_config_value("pre_event_minutes", 30))
        self.post_event_minutes = int(self.get_config_value("post_event_minutes", 60))
        self.take_profit_pips = Decimal(str(self.get_config_value("take_profit_pips", 30)))
        self.stop_loss_pips = Decimal(str(self.get_config_value("stop_loss_pips", 20)))
        self.require_trend_confirmation = bool(
            self.get_config_value("require_trend_confirmation", True)
        )

        # Components
        self.economic_calendar = EconomicCalendar()
        self.technical_analyzer = TechnicalAnalyzer(
            ma_short_period=int(self.get_config_value("ma_short_period", 20)),
            ma_long_period=int(self.get_config_value("ma_long_period", 50)),
        )

        # Track event-based positions
        self.event_positions: dict[str, str] = {}  # position_id -> event_name

    def on_tick(self, tick_data: TickData) -> list[Order]:
        """
        Process incoming tick data and generate trading signals.

        Args:
            tick_data: TickData instance containing market data

        Returns:
            List of Order instances to execute

        Requirements: 5.1, 5.3
        """
        orders: list[Order] = []

        # Validate prerequisites
        if not self.is_instrument_active(tick_data.instrument):
            return orders

        # Update technical analyzer
        self.technical_analyzer.add_price(tick_data.instrument, tick_data.timestamp, tick_data.mid)

        # Get open positions for this instrument
        open_positions = self.get_open_positions(tick_data.instrument)

        # Manage existing positions
        if open_positions:
            management_orders = self._manage_positions(tick_data, open_positions)
            if management_orders:
                orders.extend(management_orders)
            return orders

        # Check for trading opportunities
        upcoming_events = self.economic_calendar.get_upcoming_events(
            tick_data.instrument, tick_data.timestamp, self.pre_event_minutes
        )

        recent_events = self.economic_calendar.get_recent_events(
            tick_data.instrument, tick_data.timestamp, self.post_event_minutes
        )

        # Pre-event trading: avoid entering positions too close to events
        if upcoming_events:
            high_impact_upcoming = any(
                e.importance == EventImportance.HIGH for e in upcoming_events
            )
            if high_impact_upcoming:
                # Don't enter new positions before high-impact events
                return orders

        # Post-event trading: look for opportunities after events
        if recent_events:
            entry_order = self._evaluate_post_event_entry(tick_data, recent_events)
            if entry_order:
                orders.append(entry_order)

        return orders

    def _manage_positions(self, tick_data: TickData, positions: list[Position]) -> list[Order]:
        """
        Manage existing positions with stop-loss and take-profit.

        Args:
            tick_data: Current tick data
            positions: List of open positions

        Returns:
            List of close orders if targets hit
        """
        orders: list[Order] = []
        pip_value = Decimal("0.01") if "JPY" in tick_data.instrument else Decimal("0.0001")

        for position in positions:
            # Calculate current profit/loss in pips
            if position.direction == "long":
                pnl_pips = (tick_data.mid - position.entry_price) / pip_value
            else:  # short
                pnl_pips = (position.entry_price - tick_data.mid) / pip_value

            # Check take-profit
            if pnl_pips >= self.take_profit_pips:
                close_order = self._create_close_order(position, tick_data, "take_profit")
                if close_order:
                    orders.append(close_order)
                    continue

            # Check stop-loss
            if pnl_pips <= -self.stop_loss_pips:
                close_order = self._create_close_order(position, tick_data, "stop_loss")
                if close_order:
                    orders.append(close_order)

        return orders

    def _evaluate_post_event_entry(
        self, tick_data: TickData, recent_events: list[EconomicEvent]
    ) -> Order | None:
        """
        Evaluate entry opportunity after economic event.

        Args:
            tick_data: Current tick data
            recent_events: List of recent events

        Returns:
            Entry order or None
        """
        # Get most recent high or medium importance event
        significant_event = None
        for event in recent_events:
            if event.importance in [EventImportance.HIGH, EventImportance.MEDIUM]:
                significant_event = event
                break

        if not significant_event:
            return None

        # Get technical confirmation
        trend = self.technical_analyzer.detect_trend(tick_data.instrument)

        # Require trend confirmation if configured
        if self.require_trend_confirmation and trend == TrendDirection.NEUTRAL:
            return None

        # Get support/resistance levels
        support, resistance = self.technical_analyzer.find_support_resistance(tick_data.instrument)

        # Determine entry direction based on trend and price position
        direction = None
        # Enter long if bullish trend and price is near support (within 0.2%)
        if (
            trend == TrendDirection.BULLISH
            and support
            and tick_data.mid <= support * Decimal("1.002")
        ):
            direction = "long"
        # Enter short if bearish trend and price is near resistance (within 0.2%)
        elif (
            trend == TrendDirection.BEARISH
            and resistance
            and tick_data.mid >= resistance * Decimal("0.998")
        ):
            direction = "short"

        if not direction:
            return None

        # Calculate position size based on event importance
        position_size = self._calculate_position_size(significant_event.importance)

        # Create entry order
        return self._create_entry_order(
            tick_data, direction, position_size, significant_event.event_name
        )

    def _calculate_position_size(self, importance: EventImportance) -> Decimal:
        """
        Calculate position size based on event importance.

        Args:
            importance: Event importance level

        Returns:
            Position size in units
        """
        if importance == EventImportance.HIGH:
            multiplier = self.high_importance_multiplier
        elif importance == EventImportance.MEDIUM:
            multiplier = self.medium_importance_multiplier
        else:  # LOW
            multiplier = self.low_importance_multiplier

        return self.base_units * multiplier

    def _create_entry_order(
        self, tick_data: TickData, direction: str, units: Decimal, event_name: str
    ) -> Order:
        """
        Create entry order.

        Args:
            tick_data: Current tick data
            direction: Position direction ('long' or 'short')
            units: Position size
            event_name: Name of the triggering event

        Returns:
            Order instance
        """
        pip_value = Decimal("0.01") if "JPY" in tick_data.instrument else Decimal("0.0001")

        # Calculate take-profit and stop-loss
        if direction == "long":
            take_profit = tick_data.mid + (self.take_profit_pips * pip_value)
            stop_loss = tick_data.mid - (self.stop_loss_pips * pip_value)
        else:  # short
            take_profit = tick_data.mid - (self.take_profit_pips * pip_value)
            stop_loss = tick_data.mid + (self.stop_loss_pips * pip_value)

        order = Order(
            account=self.account,
            strategy=self.strategy,
            order_id=(f"fundamental_technical_{direction}_" f"{tick_data.timestamp.timestamp()}"),
            instrument=tick_data.instrument,
            order_type="market",
            direction=direction,
            units=units,
            price=tick_data.mid,
            take_profit=take_profit,
            stop_loss=stop_loss,
        )

        self.log_strategy_event(
            "fundamental_technical_entry",
            f"Fundamental + Technical entry: {direction}",
            {
                "instrument": tick_data.instrument,
                "direction": direction,
                "units": str(units),
                "price": str(tick_data.mid),
                "take_profit": str(take_profit),
                "stop_loss": str(stop_loss),
                "event_name": event_name,
            },
        )

        return order

    def _create_close_order(self, position: Position, tick_data: TickData, reason: str) -> Order:
        """
        Create order to close a position.

        Args:
            position: Position to close
            tick_data: Current tick data
            reason: Reason for closing

        Returns:
            Close order
        """
        # Reverse direction for closing
        close_direction = "short" if position.direction == "long" else "long"

        order = Order(
            account=self.account,
            strategy=self.strategy,
            order_id=(
                f"fundamental_technical_close_{position.position_id}_"
                f"{tick_data.timestamp.timestamp()}"
            ),
            instrument=position.instrument,
            order_type="market",
            direction=close_direction,
            units=position.units,
            price=tick_data.mid,
        )

        self.log_strategy_event(
            "fundamental_technical_exit",
            f"Fundamental + Technical exit: {reason}",
            {
                "position_id": position.position_id,
                "instrument": position.instrument,
                "direction": position.direction,
                "entry_price": str(position.entry_price),
                "exit_price": str(tick_data.mid),
                "units": str(position.units),
                "reason": reason,
            },
        )

        return order

    def on_position_update(self, position: Position) -> None:
        """
        Handle position updates.

        Args:
            position: Position that was updated

        Requirements: 5.1, 5.3
        """
        # Clean up tracking when position is closed
        if position.closed_at is not None:
            position_id = position.position_id
            if position_id in self.event_positions:
                del self.event_positions[position_id]

            self.log_strategy_event(
                "position_closed",
                f"Position closed: {position.position_id}",
                {
                    "position_id": position.position_id,
                    "instrument": position.instrument,
                    "direction": position.direction,
                    "entry_price": str(position.entry_price),
                    "exit_price": str(position.current_price),
                    "units": str(position.units),
                },
            )

    def validate_config(self, config: dict[str, Any]) -> bool:
        """
        Validate strategy configuration.

        Args:
            config: Configuration dictionary

        Returns:
            True if valid

        Raises:
            ValueError: If configuration is invalid

        Requirements: 5.1
        """
        # Validate base units
        self._validate_positive_decimal(config, "base_units", 1000)

        # Validate importance multipliers
        for key in [
            "high_importance_multiplier",
            "medium_importance_multiplier",
            "low_importance_multiplier",
        ]:
            self._validate_positive_decimal(config, key, 1.0)

        # Validate time windows
        for key in ["pre_event_minutes", "post_event_minutes"]:
            self._validate_positive_int(config, key, 30)

        # Validate pip values
        for key in ["take_profit_pips", "stop_loss_pips"]:
            self._validate_positive_decimal(config, key, 20)

        # Validate MA periods
        for key in ["ma_short_period", "ma_long_period"]:
            self._validate_positive_int(config, key, 20)

        # Validate short period < long period
        ma_short = int(config.get("ma_short_period", 20))
        ma_long = int(config.get("ma_long_period", 50))
        if ma_short >= ma_long:
            raise ValueError("ma_short_period must be less than ma_long_period")

        return True

    def _validate_positive_decimal(self, config: dict[str, Any], key: str, default: float) -> None:
        """
        Validate a positive decimal configuration value.

        Args:
            config: Configuration dictionary
            key: Configuration key
            default: Default value

        Raises:
            ValueError: If value is invalid or not positive
        """
        value = config.get(key, default)
        try:
            decimal_value = Decimal(str(value))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid {key}: {value}") from exc

        if decimal_value <= Decimal("0"):
            raise ValueError(f"{key} must be positive")

    def _validate_positive_int(self, config: dict[str, Any], key: str, default: int) -> None:
        """
        Validate a positive integer configuration value.

        Args:
            config: Configuration dictionary
            key: Configuration key
            default: Default value

        Raises:
            ValueError: If value is invalid or not positive
        """
        value = config.get(key, default)
        try:
            int_value = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid {key}: {value}") from exc

        if int_value <= 0:
            raise ValueError(f"{key} must be positive")


# Configuration schema for Fundamental + Technical Strategy
FUNDAMENTAL_TECHNICAL_STRATEGY_CONFIG_SCHEMA = {
    "type": "object",
    "title": "Fundamental + Technical Strategy Configuration",
    "description": (
        "Configuration for Fundamental + Technical Strategy combining "
        "economic events with technical analysis"
    ),
    "properties": {
        "base_units": {
            "type": "number",
            "title": "Base Units",
            "description": "Base position size in units",
            "default": 1000,
            "minimum": 1,
        },
        "high_importance_multiplier": {
            "type": "number",
            "title": "High Importance Multiplier",
            "description": "Position size multiplier for high-importance events",
            "default": 2.0,
            "minimum": 0.1,
        },
        "medium_importance_multiplier": {
            "type": "number",
            "title": "Medium Importance Multiplier",
            "description": "Position size multiplier for medium-importance events",
            "default": 1.5,
            "minimum": 0.1,
        },
        "low_importance_multiplier": {
            "type": "number",
            "title": "Low Importance Multiplier",
            "description": "Position size multiplier for low-importance events",
            "default": 1.0,
            "minimum": 0.1,
        },
        "pre_event_minutes": {
            "type": "number",
            "title": "Pre-Event Minutes",
            "description": "Minutes before event to avoid trading",
            "default": 30,
            "minimum": 1,
        },
        "post_event_minutes": {
            "type": "number",
            "title": "Post-Event Minutes",
            "description": "Minutes after event to look for opportunities",
            "default": 60,
            "minimum": 1,
        },
        "take_profit_pips": {
            "type": "number",
            "title": "Take Profit Pips",
            "description": "Take profit target in pips",
            "default": 30,
            "minimum": 1,
        },
        "stop_loss_pips": {
            "type": "number",
            "title": "Stop Loss Pips",
            "description": "Stop loss distance in pips",
            "default": 20,
            "minimum": 1,
        },
        "require_trend_confirmation": {
            "type": "boolean",
            "title": "Require Trend Confirmation",
            "description": "Require clear trend before entering",
            "default": True,
        },
        "ma_short_period": {
            "type": "number",
            "title": "Short MA Period",
            "description": "Short moving average period",
            "default": 20,
            "minimum": 1,
        },
        "ma_long_period": {
            "type": "number",
            "title": "Long MA Period",
            "description": "Long moving average period",
            "default": 50,
            "minimum": 1,
        },
    },
    "required": [],
}

# Register the strategy
register_strategy("fundamental_technical", FUNDAMENTAL_TECHNICAL_STRATEGY_CONFIG_SCHEMA)(
    FundamentalTechnicalStrategy
)
