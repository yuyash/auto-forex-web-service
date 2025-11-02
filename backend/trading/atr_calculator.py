"""
ATR (Average True Range) Calculator for volatility monitoring.

This module provides functionality to:
- Fetch 1-hour candles from OANDA API
- Calculate 14-period ATR
- Store ATR values and normal ATR baseline

Requirements: 10.1, 10.4
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from django.utils import timezone

import v20

from accounts.models import OandaAccount

logger = logging.getLogger(__name__)


@dataclass
class Candle:
    """
    OHLC candle data.

    Attributes:
        time: Candle timestamp
        open: Opening price
        high: Highest price
        low: Lowest price
        close: Closing price
        volume: Trading volume
    """

    time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int


class ATRCalculator:
    """
    Calculate Average True Range (ATR) for volatility monitoring.

    The ATR is calculated using the 14-period moving average of True Range values.
    True Range is the greatest of:
    - Current High - Current Low
    - abs(Current High - Previous Close)
    - abs(Current Low - Previous Close)

    Requirements: 10.1, 10.4
    """

    def __init__(self, period: int = 14):
        """
        Initialize ATR calculator.

        Args:
            period: Number of periods for ATR calculation (default: 14)
        """
        self.period = period
        logger.info("Initialized ATRCalculator with period=%d", period)

    def fetch_candles(  # pylint: disable=too-many-locals
        self,
        account: OandaAccount,
        instrument: str,
        granularity: str = "H1",
        count: int = 100,
    ) -> List[Candle]:
        """
        Fetch historical candles from OANDA API.

        Args:
            account: OandaAccount instance with API credentials
            instrument: Currency pair (e.g., 'EUR_USD')
            granularity: Candle granularity (default: 'H1' for 1-hour)
            count: Number of candles to fetch (default: 100)

        Returns:
            List of Candle objects

        Raises:
            Exception: If API call fails

        Requirements: 10.1
        """
        try:
            # Initialize OANDA API context
            ctx = v20.Context(
                hostname=account.api_hostname,
                token=account.get_api_token(),
            )

            # Fetch candles from OANDA API
            response = ctx.instrument.candles(
                instrument=instrument,
                granularity=granularity,
                count=count,
            )

            # Parse candles from response
            candles = []
            if response.status == 200 and response.body:
                for candle_data in response.body.get("candles", []):
                    if not candle_data.get("complete"):
                        # Skip incomplete candles
                        continue

                    mid = candle_data.get("mid", {})
                    candle = Candle(
                        time=self._parse_timestamp(candle_data["time"]),
                        open=Decimal(str(mid.get("o", "0"))),
                        high=Decimal(str(mid.get("h", "0"))),
                        low=Decimal(str(mid.get("l", "0"))),
                        close=Decimal(str(mid.get("c", "0"))),
                        volume=int(candle_data.get("volume", 0)),
                    )
                    candles.append(candle)

            logger.info(
                "Fetched %d candles for %s with granularity %s",
                len(candles),
                instrument,
                granularity,
            )

            return candles

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(
                "Error fetching candles for %s: %s",
                instrument,
                e,
                exc_info=True,
            )
            raise

    def _parse_timestamp(self, time_str: str) -> datetime:
        """
        Parse OANDA timestamp string to datetime object.

        Args:
            time_str: ISO 8601 timestamp string from OANDA

        Returns:
            Timezone-aware datetime object
        """
        try:
            # OANDA returns timestamps in RFC3339 format
            # Example: "2024-01-15T10:30:45.123456789Z"
            dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
            # Ensure it's timezone-aware
            if dt.tzinfo is None:
                dt = timezone.make_aware(dt)
            return dt
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error parsing timestamp '%s': %s", time_str, e)
            # Fallback to current time
            return timezone.now()

    def calculate_true_range(
        self,
        current_candle: Candle,
        previous_candle: Optional[Candle] = None,
    ) -> Decimal:
        """
        Calculate True Range for a candle.

        True Range is the greatest of:
        - Current High - Current Low
        - abs(Current High - Previous Close)
        - abs(Current Low - Previous Close)

        If no previous candle is provided, True Range = High - Low.

        Args:
            current_candle: Current candle
            previous_candle: Previous candle (optional)

        Returns:
            True Range value

        Requirements: 10.1
        """
        high_low = current_candle.high - current_candle.low

        if previous_candle is None:
            return high_low

        high_prev_close = abs(current_candle.high - previous_candle.close)
        low_prev_close = abs(current_candle.low - previous_candle.close)

        true_range = max(high_low, high_prev_close, low_prev_close)

        return true_range

    def calculate_atr(self, candles: List[Candle]) -> Optional[Decimal]:
        """
        Calculate Average True Range (ATR) for the given candles.

        The ATR is calculated as the simple moving average of True Range values
        over the specified period.

        Args:
            candles: List of Candle objects (must have at least period + 1 candles)

        Returns:
            ATR value, or None if insufficient data

        Requirements: 10.1
        """
        if len(candles) < self.period + 1:
            logger.warning(
                "Insufficient candles for ATR calculation: need %d, got %d",
                self.period + 1,
                len(candles),
            )
            return None

        # Calculate True Range for each candle
        true_ranges: List[Decimal] = []
        for i in range(1, len(candles)):
            tr = self.calculate_true_range(candles[i], candles[i - 1])
            true_ranges.append(tr)

        # Calculate ATR as simple moving average of last 'period' True Ranges
        if len(true_ranges) < self.period:
            logger.warning(
                "Insufficient True Range values for ATR calculation: need %d, got %d",
                self.period,
                len(true_ranges),
            )
            return None

        recent_true_ranges = true_ranges[-self.period :]
        atr = sum(recent_true_ranges) / Decimal(str(self.period))

        logger.debug(
            "Calculated ATR: %s (from %d True Range values)",
            atr,
            len(recent_true_ranges),
        )

        return atr

    def calculate_normal_atr(
        self,
        account: OandaAccount,
        instrument: str,
        lookback_days: int = 30,
    ) -> Optional[Decimal]:
        """
        Calculate normal ATR baseline by averaging ATR over a lookback period.

        This method fetches historical candles and calculates the average ATR
        over the specified lookback period to establish a baseline for
        volatility monitoring.

        Args:
            account: OandaAccount instance with API credentials
            instrument: Currency pair (e.g., 'EUR_USD')
            lookback_days: Number of days to look back (default: 30)

        Returns:
            Normal ATR baseline value, or None if insufficient data

        Requirements: 10.1, 10.4
        """
        try:
            # Calculate number of 1-hour candles needed
            # 24 hours per day * lookback_days + period for ATR calculation
            candles_needed = (24 * lookback_days) + self.period + 1

            # Fetch candles
            candles = self.fetch_candles(
                account=account,
                instrument=instrument,
                granularity="H1",
                count=min(candles_needed, 5000),  # OANDA API limit
            )

            if len(candles) < self.period + 1:
                logger.warning(
                    "Insufficient candles for normal ATR calculation: need %d, got %d",
                    self.period + 1,
                    len(candles),
                )
                return None

            # Calculate ATR for each window
            atr_values: List[Decimal] = []
            for i in range(self.period, len(candles)):
                window = candles[i - self.period : i + 1]
                atr = self.calculate_atr(window)
                if atr is not None:
                    atr_values.append(atr)

            if not atr_values:
                logger.warning("No ATR values calculated for normal ATR baseline")
                return None

            # Calculate average ATR as normal baseline
            normal_atr = sum(atr_values) / Decimal(str(len(atr_values)))

            logger.info(
                "Calculated normal ATR baseline for %s: %s (from %d ATR values over %d days)",
                instrument,
                normal_atr,
                len(atr_values),
                lookback_days,
            )

            return normal_atr

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(
                "Error calculating normal ATR for %s: %s",
                instrument,
                e,
                exc_info=True,
            )
            return None

    def get_latest_atr(
        self,
        account: OandaAccount,
        instrument: str,
    ) -> Optional[Decimal]:
        """
        Get the latest ATR value for an instrument.

        This is a convenience method that fetches recent candles and
        calculates the current ATR.

        Args:
            account: OandaAccount instance with API credentials
            instrument: Currency pair (e.g., 'EUR_USD')

        Returns:
            Latest ATR value, or None if calculation fails

        Requirements: 10.1
        """
        try:
            # Fetch enough candles for ATR calculation
            candles = self.fetch_candles(
                account=account,
                instrument=instrument,
                granularity="H1",
                count=self.period + 10,  # Extra candles for safety
            )

            if len(candles) < self.period + 1:
                logger.warning(
                    "Insufficient candles for latest ATR: need %d, got %d",
                    self.period + 1,
                    len(candles),
                )
                return None

            # Calculate ATR using most recent candles
            atr = self.calculate_atr(candles)

            if atr is not None:
                logger.info(
                    "Latest ATR for %s: %s",
                    instrument,
                    atr,
                )

            return atr

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(
                "Error getting latest ATR for %s: %s",
                instrument,
                e,
                exc_info=True,
            )
            return None
