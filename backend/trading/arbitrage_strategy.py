"""
Arbitrage Strategy implementation for multi-broker price differences.

This module implements an Arbitrage Strategy that:
- Detects price differences between brokers
- Implements simultaneous buy/sell execution
- Implements spread monitoring and profit calculation
- Implements risk management for execution delays

Requirements: 5.1, 5.3
"""

from decimal import Decimal
from typing import Any

from .base_strategy import BaseStrategy
from .models import Order, Position
from .strategy_registry import register_strategy
from .tick_data_models import TickData


class PriceDifferenceDetector:
    """
    Detect price differences between brokers.

    Requirements: 5.1, 5.3
    """

    def __init__(self, min_spread_pips: Decimal | None = None) -> None:
        """
        Initialize the price difference detector.

        Args:
            min_spread_pips: Minimum spread in pips to trigger arbitrage
        """
        self.min_spread_pips = min_spread_pips if min_spread_pips is not None else Decimal("2.0")
        self.broker_prices: dict[str, dict[str, dict[str, Decimal]]] = {}

    def update_price(self, broker: str, instrument: str, bid: Decimal, ask: Decimal) -> None:
        """
        Update price for a broker.

        Args:
            broker: Broker identifier
            instrument: Currency pair
            bid: Bid price
            ask: Ask price
        """
        if broker not in self.broker_prices:
            self.broker_prices[broker] = {}

        self.broker_prices[broker][instrument] = {"bid": bid, "ask": ask, "mid": (bid + ask) / 2}

    def detect_arbitrage_opportunity(
        self, instrument: str, pip_value: Decimal
    ) -> tuple[bool, str | None, str | None, Decimal | None]:
        """
        Detect arbitrage opportunity between brokers.

        Args:
            instrument: Currency pair
            pip_value: Pip value for the instrument

        Returns:
            Tuple of (has_opportunity, buy_broker, sell_broker, spread_pips)
        """
        # Need at least 2 brokers to arbitrage
        if len(self.broker_prices) < 2:
            return False, None, None, None

        # Find brokers with prices for this instrument
        brokers_with_prices = [
            broker for broker, prices in self.broker_prices.items() if instrument in prices
        ]

        if len(brokers_with_prices) < 2:
            return False, None, None, None

        # Find best bid and ask across brokers
        best_bid = Decimal("0")
        best_bid_broker = None
        best_ask = Decimal("999999")
        best_ask_broker = None

        for broker in brokers_with_prices:
            instrument_prices = self.broker_prices[broker][instrument]
            bid = instrument_prices["bid"]
            ask = instrument_prices["ask"]

            if bid > best_bid:
                best_bid = bid
                best_bid_broker = broker

            if ask < best_ask:
                best_ask = ask
                best_ask_broker = broker

        # Check if we can buy low and sell high
        if best_bid_broker and best_ask_broker and best_bid_broker != best_ask_broker:
            spread = best_bid - best_ask
            spread_pips = spread / pip_value

            if spread_pips >= self.min_spread_pips:
                # Buy at best_ask_broker, sell at best_bid_broker
                return True, best_ask_broker, best_bid_broker, spread_pips

        return False, None, None, None


class ArbitrageStrategy(BaseStrategy):
    """
    Arbitrage Strategy for multi-broker trading.

    This strategy:
    - Detects price differences between brokers
    - Implements simultaneous buy/sell execution
    - Implements spread monitoring and profit calculation
    - Implements risk management for execution delays

    Requirements: 5.1, 5.3
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the Arbitrage Strategy."""
        super().__init__(*args, **kwargs)

        # Configuration
        self.base_units = Decimal(str(self.get_config_value("base_units", 1000)))
        self.min_spread_pips = Decimal(str(self.get_config_value("min_spread_pips", 2.0)))
        self.max_execution_delay_ms = int(self.get_config_value("max_execution_delay_ms", 500))
        self.max_slippage_pips = Decimal(str(self.get_config_value("max_slippage_pips", 0.5)))
        self.profit_target_pips = Decimal(str(self.get_config_value("profit_target_pips", 1.5)))

        # Components
        self.price_detector = PriceDifferenceDetector(self.min_spread_pips)

        # Track arbitrage pairs
        self.active_arbitrage_pairs: dict[str, dict[str, Any]] = {}

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

        # Update price for this broker (using account as broker identifier)
        if not self.account:
            return orders
        broker_id = str(self.account.account_id)
        self.price_detector.update_price(
            broker_id, tick_data.instrument, tick_data.bid, tick_data.ask
        )

        # Get pip value for this instrument
        pip_value = Decimal("0.01") if "JPY" in tick_data.instrument else Decimal("0.0001")

        # Check for existing arbitrage pairs and manage them
        close_orders = self._manage_existing_pairs(tick_data, pip_value)
        if close_orders:
            orders.extend(close_orders)

        # Don't open new arbitrage if we already have one for this instrument
        if tick_data.instrument in self.active_arbitrage_pairs:
            return orders

        # Detect arbitrage opportunity
        has_opportunity, buy_broker, sell_broker, spread_pips = (
            self.price_detector.detect_arbitrage_opportunity(tick_data.instrument, pip_value)
        )

        if not has_opportunity or buy_broker is None or sell_broker is None:
            return orders

        # Generate simultaneous buy/sell orders
        arbitrage_orders = self._create_arbitrage_orders(
            tick_data, buy_broker, sell_broker, spread_pips
        )
        if arbitrage_orders:
            orders.extend(arbitrage_orders)

        return orders

    def _manage_existing_pairs(self, tick_data: TickData, pip_value: Decimal) -> list[Order]:
        """
        Manage existing arbitrage pairs.

        Args:
            tick_data: Current tick data
            pip_value: Pip value for the instrument

        Returns:
            List of close orders if profit target reached
        """
        orders: list[Order] = []

        if tick_data.instrument not in self.active_arbitrage_pairs:
            return orders

        pair_info = self.active_arbitrage_pairs[tick_data.instrument]
        buy_position = pair_info.get("buy_position")
        sell_position = pair_info.get("sell_position")

        if not buy_position or not sell_position:
            return orders

        # Calculate current profit
        buy_profit = (tick_data.mid - buy_position.entry_price) / pip_value
        sell_profit = (sell_position.entry_price - tick_data.mid) / pip_value
        total_profit_pips = buy_profit + sell_profit

        # Check if profit target reached
        if total_profit_pips >= self.profit_target_pips:
            # Close both positions
            buy_close = self._create_close_order(buy_position, tick_data, "profit_target")
            sell_close = self._create_close_order(sell_position, tick_data, "profit_target")

            if buy_close:
                orders.append(buy_close)
            if sell_close:
                orders.append(sell_close)

            # Remove from active pairs
            del self.active_arbitrage_pairs[tick_data.instrument]

            self.log_strategy_event(
                "arbitrage_closed",
                f"Arbitrage pair closed with profit: {total_profit_pips} pips",
                {
                    "instrument": tick_data.instrument,
                    "total_profit_pips": str(total_profit_pips),
                    "buy_profit_pips": str(buy_profit),
                    "sell_profit_pips": str(sell_profit),
                },
            )

        # Check for excessive slippage or loss
        elif total_profit_pips < -self.max_slippage_pips:
            # Close both positions to limit loss
            buy_close = self._create_close_order(buy_position, tick_data, "stop_loss")
            sell_close = self._create_close_order(sell_position, tick_data, "stop_loss")

            if buy_close:
                orders.append(buy_close)
            if sell_close:
                orders.append(sell_close)

            # Remove from active pairs
            del self.active_arbitrage_pairs[tick_data.instrument]

            self.log_strategy_event(
                "arbitrage_stopped",
                f"Arbitrage pair stopped due to slippage: {total_profit_pips} pips",
                {
                    "instrument": tick_data.instrument,
                    "total_profit_pips": str(total_profit_pips),
                    "max_slippage_pips": str(self.max_slippage_pips),
                },
            )

        return orders

    def _create_arbitrage_orders(
        self,
        tick_data: TickData,
        buy_broker: str,
        sell_broker: str,
        spread_pips: Decimal | None,
    ) -> list[Order]:
        """
        Create simultaneous buy and sell orders for arbitrage.

        Args:
            tick_data: Current tick data
            buy_broker: Broker to buy from
            sell_broker: Broker to sell to
            spread_pips: Expected spread in pips

        Returns:
            List of orders (buy and sell)
        """
        orders: list[Order] = []

        # Create buy order (buy at lower price)
        buy_order = Order(
            account=self.account,
            strategy=self.strategy,
            order_id=f"arbitrage_buy_{tick_data.instrument}_{tick_data.timestamp.timestamp()}",
            instrument=tick_data.instrument,
            order_type="market",
            direction="long",
            units=self.base_units,
            price=tick_data.ask,  # Buy at ask price
        )
        orders.append(buy_order)

        # Create sell order (sell at higher price)
        sell_order = Order(
            account=self.account,
            strategy=self.strategy,
            order_id=f"arbitrage_sell_{tick_data.instrument}_{tick_data.timestamp.timestamp()}",
            instrument=tick_data.instrument,
            order_type="market",
            direction="short",
            units=self.base_units,
            price=tick_data.bid,  # Sell at bid price
        )
        orders.append(sell_order)

        self.log_strategy_event(
            "arbitrage_opened",
            f"Arbitrage opportunity detected: {spread_pips} pips spread",
            {
                "instrument": tick_data.instrument,
                "buy_broker": buy_broker,
                "sell_broker": sell_broker,
                "spread_pips": str(spread_pips) if spread_pips else None,
                "buy_price": str(tick_data.ask),
                "sell_price": str(tick_data.bid),
                "units": str(self.base_units),
            },
        )

        return orders

    def _create_close_order(
        self, position: Position, tick_data: TickData, reason: str
    ) -> Order | None:
        """
        Create order to close a position.

        Args:
            position: Position to close
            tick_data: Current tick data
            reason: Reason for closing

        Returns:
            Close order or None
        """
        # Reverse direction for closing
        close_direction = "short" if position.direction == "long" else "long"

        order = Order(
            account=self.account,
            strategy=self.strategy,
            order_id=(f"arbitrage_close_{position.position_id}_{tick_data.timestamp.timestamp()}"),
            instrument=position.instrument,
            order_type="market",
            direction=close_direction,
            units=position.units,
            price=tick_data.mid,
        )

        self.log_strategy_event(
            "arbitrage_position_closed",
            f"Arbitrage position closed: {reason}",
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
        # Track arbitrage pairs
        if position.closed_at is None:
            # Position opened - track it
            if position.instrument not in self.active_arbitrage_pairs:
                self.active_arbitrage_pairs[position.instrument] = {}

            if position.direction == "long":
                self.active_arbitrage_pairs[position.instrument]["buy_position"] = position
            else:  # short
                self.active_arbitrage_pairs[position.instrument]["sell_position"] = position

            self.log_strategy_event(
                "arbitrage_position_opened",
                f"Arbitrage position opened: {position.direction}",
                {
                    "position_id": position.position_id,
                    "instrument": position.instrument,
                    "direction": position.direction,
                    "entry_price": str(position.entry_price),
                    "units": str(position.units),
                },
            )
        else:
            # Position closed - clean up tracking
            if position.instrument in self.active_arbitrage_pairs:
                pair_info = self.active_arbitrage_pairs[position.instrument]

                if position.direction == "long" and "buy_position" in pair_info:
                    del pair_info["buy_position"]
                elif position.direction == "short" and "sell_position" in pair_info:
                    del pair_info["sell_position"]

                # Remove pair if both positions closed
                if not pair_info.get("buy_position") and not pair_info.get("sell_position"):
                    del self.active_arbitrage_pairs[position.instrument]

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
        base_units = config.get("base_units", 1000)
        try:
            base_units_decimal = Decimal(str(base_units))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid base_units: {base_units}") from exc

        if base_units_decimal <= Decimal("0"):
            raise ValueError("base_units must be positive")

        # Validate min spread pips
        min_spread_pips = config.get("min_spread_pips", 2.0)
        try:
            min_spread_decimal = Decimal(str(min_spread_pips))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid min_spread_pips: {min_spread_pips}") from exc

        if min_spread_decimal <= Decimal("0"):
            raise ValueError("min_spread_pips must be positive")

        # Validate max execution delay
        max_execution_delay_ms = config.get("max_execution_delay_ms", 500)
        try:
            delay_int = int(max_execution_delay_ms)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid max_execution_delay_ms: {max_execution_delay_ms}") from exc

        if delay_int <= 0:
            raise ValueError("max_execution_delay_ms must be positive")

        # Validate max slippage pips
        max_slippage_pips = config.get("max_slippage_pips", 0.5)
        try:
            slippage_decimal = Decimal(str(max_slippage_pips))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid max_slippage_pips: {max_slippage_pips}") from exc

        if slippage_decimal <= Decimal("0"):
            raise ValueError("max_slippage_pips must be positive")

        # Validate profit target pips
        profit_target_pips = config.get("profit_target_pips", 1.5)
        try:
            profit_decimal = Decimal(str(profit_target_pips))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid profit_target_pips: {profit_target_pips}") from exc

        if profit_decimal <= Decimal("0"):
            raise ValueError("profit_target_pips must be positive")

        return True


# Configuration schema for Arbitrage Strategy
ARBITRAGE_STRATEGY_CONFIG_SCHEMA = {
    "type": "object",
    "title": "Arbitrage Strategy Configuration",
    "description": (
        "Configuration for Arbitrage Strategy with multi-broker price difference detection"
    ),
    "properties": {
        "base_units": {
            "type": "number",
            "title": "Base Units",
            "description": "Base position size in units",
            "default": 1000,
            "minimum": 1,
        },
        "min_spread_pips": {
            "type": "number",
            "title": "Minimum Spread Pips",
            "description": "Minimum spread in pips to trigger arbitrage",
            "default": 2.0,
            "minimum": 0.1,
        },
        "max_execution_delay_ms": {
            "type": "number",
            "title": "Max Execution Delay (ms)",
            "description": ("Maximum acceptable execution delay in milliseconds"),
            "default": 500,
            "minimum": 1,
        },
        "max_slippage_pips": {
            "type": "number",
            "title": "Max Slippage Pips",
            "description": ("Maximum acceptable slippage in pips before closing positions"),
            "default": 0.5,
            "minimum": 0.1,
        },
        "profit_target_pips": {
            "type": "number",
            "title": "Profit Target Pips",
            "description": "Profit target in pips to close arbitrage pair",
            "default": 1.5,
            "minimum": 0.1,
        },
    },
    "required": [],
}

# Register the strategy
register_strategy("arbitrage", ARBITRAGE_STRATEGY_CONFIG_SCHEMA, display_name="Arbitrage Strategy")(
    ArbitrageStrategy
)
