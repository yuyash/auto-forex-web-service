"""
Demo Market Data Generator

This module generates simulated market data for demo/default accounts
when no OANDA account is configured.

Note: This module uses the standard `random` module for generating demo data.
This is intentional and safe as the data is only used for demonstration purposes,
not for cryptographic or security-sensitive operations.
"""

import asyncio
import logging
import random  # nosec B404 - Used only for demo data generation, not security
from datetime import datetime, timezone
from typing import Dict, Optional

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)


class DemoMarketDataGenerator:
    """
    Generates simulated market data for demo accounts.

    This class:
    - Generates realistic tick data with bid/ask spreads
    - Simulates market volatility
    - Broadcasts data via Django Channels
    - Supports multiple instruments
    """

    # Base prices for common currency pairs
    BASE_PRICES = {
        "USD_JPY": 149.50,
        "EUR_USD": 1.0850,
        "GBP_USD": 1.2650,
        "AUD_USD": 0.6550,
        "USD_CAD": 1.3850,
        "USD_CHF": 0.8850,
        "NZD_USD": 0.5950,
        "EUR_JPY": 162.25,
    }

    # Typical spreads in pips (for 5-digit pricing)
    SPREADS = {
        "USD_JPY": 0.015,  # 1.5 pips
        "EUR_USD": 0.00015,  # 1.5 pips
        "GBP_USD": 0.00020,  # 2.0 pips
        "AUD_USD": 0.00018,  # 1.8 pips
        "USD_CAD": 0.00020,  # 2.0 pips
        "USD_CHF": 0.00018,  # 1.8 pips
        "NZD_USD": 0.00025,  # 2.5 pips
        "EUR_JPY": 0.020,  # 2.0 pips
    }

    def __init__(self, user_id: int, instrument: str = "USD_JPY"):
        """
        Initialize the demo market data generator.

        Args:
            user_id: User ID for group name generation
            instrument: Currency pair to generate data for
        """
        self.user_id = user_id
        self.instrument = instrument
        self.current_price = self.BASE_PRICES.get(instrument, 100.0)
        self.spread = self.SPREADS.get(instrument, 0.0002)
        self.is_running = False
        self.task: Optional[asyncio.Task] = None

    def _generate_tick(self) -> Dict:
        """
        Generate a single tick with realistic price movement.

        Returns:
            Dictionary with tick data
        """
        # Simulate price movement (random walk with small steps)
        # Typical movement: 0.01% to 0.05% per tick
        movement_percent = random.uniform(-0.0005, 0.0005)  # nosec B311
        self.current_price *= 1 + movement_percent

        # Calculate bid/ask with spread
        mid_price = self.current_price
        bid = mid_price - (self.spread / 2)
        ask = mid_price + (self.spread / 2)

        # Generate timestamp
        timestamp = datetime.now(timezone.utc).isoformat()

        # Simulate liquidity (random between 1M and 10M)
        bid_liquidity = random.randint(1000000, 10000000)  # nosec B311
        ask_liquidity = random.randint(1000000, 10000000)  # nosec B311

        return {
            "instrument": self.instrument,
            "time": timestamp,
            "bid": round(bid, 5 if "JPY" not in self.instrument else 3),
            "ask": round(ask, 5 if "JPY" not in self.instrument else 3),
            "mid": round(mid_price, 5 if "JPY" not in self.instrument else 3),
            "spread": round(self.spread, 5 if "JPY" not in self.instrument else 3),
            "bid_liquidity": bid_liquidity,
            "ask_liquidity": ask_liquidity,
        }

    def _broadcast_tick(self, tick_data: Dict) -> None:
        """
        Broadcast tick data to WebSocket consumers.

        Args:
            tick_data: Tick data dictionary
        """
        try:
            channel_layer = get_channel_layer()
            if not channel_layer:
                logger.warning("Channel layer not configured")
                return

            # Create group name for this demo stream
            group_name = f"market_data_default_{self.user_id}_{self.instrument}"

            # Send message to the group
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    "type": "market_data_update",
                    "data": tick_data,
                },
            )

            logger.debug(
                "Broadcasted demo tick for %s to group: %s",
                self.instrument,
                group_name,
            )

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error broadcasting demo tick: %s", e)

    def _broadcast_demo_reminder(self) -> None:
        """
        Broadcast a reminder that this is demo data.
        """
        try:
            channel_layer = get_channel_layer()
            if not channel_layer:
                return

            # Create group name for this demo stream
            group_name = f"market_data_default_{self.user_id}_{self.instrument}"

            # Send reminder message
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    "type": "demo_reminder",
                    "data": {
                        "message": "Demo mode active. Register an OANDA account for real data.",
                        "is_demo": True,
                    },
                },
            )

            logger.debug("Broadcasted demo reminder to group: %s", group_name)

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error broadcasting demo reminder: %s", e)

    async def start(self, interval: float = 1.0) -> None:
        """
        Start generating and broadcasting demo market data.

        Args:
            interval: Time between ticks in seconds (default: 1.0)
        """
        self.is_running = True
        logger.info(
            "Started demo market data generator for user %s, instrument %s",
            self.user_id,
            self.instrument,
        )

        tick_count = 0
        try:
            while self.is_running:
                # Generate and broadcast tick
                tick_data = self._generate_tick()
                self._broadcast_tick(tick_data)

                tick_count += 1

                # Send periodic reminder every 60 ticks (about 1 minute)
                if tick_count % 60 == 0:
                    self._broadcast_demo_reminder()

                # Wait before next tick
                await asyncio.sleep(interval)

        except asyncio.CancelledError:
            logger.info("Demo market data generator cancelled")
            raise
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error in demo market data generator: %s", e)
        finally:
            self.is_running = False

    def stop(self) -> None:
        """Stop the demo market data generator."""
        self.is_running = False
        if self.task and not self.task.done():
            self.task.cancel()
        logger.info(
            "Stopped demo market data generator for user %s, instrument %s",
            self.user_id,
            self.instrument,
        )


# Global registry to track active demo generators
_active_generators: Dict[str, DemoMarketDataGenerator] = {}


def start_demo_stream(user_id: int, instrument: str = "USD_JPY") -> DemoMarketDataGenerator:
    """
    Start a demo market data stream for a user and instrument.

    Args:
        user_id: User ID
        instrument: Currency pair

    Returns:
        DemoMarketDataGenerator instance
    """
    key = f"{user_id}_{instrument}"

    # Stop existing generator if any
    if key in _active_generators:
        _active_generators[key].stop()

    # Create and start new generator
    generator = DemoMarketDataGenerator(user_id, instrument)
    _active_generators[key] = generator

    # Start the generator in a background task
    generator.task = asyncio.create_task(generator.start())

    logger.info("Started demo stream for user %s, instrument %s", user_id, instrument)
    return generator


def stop_demo_stream(user_id: int, instrument: str) -> None:
    """
    Stop a demo market data stream.

    Args:
        user_id: User ID
        instrument: Currency pair
    """
    key = f"{user_id}_{instrument}"

    if key in _active_generators:
        _active_generators[key].stop()
        del _active_generators[key]
        logger.info("Stopped demo stream for user %s, instrument %s", user_id, instrument)
