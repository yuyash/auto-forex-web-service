"""Equity-curve related helpers.

Kept as a service to avoid view-level helper functions and to centralize
sampling/normalization logic used by results endpoints.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class DownsampleResult:
    points: list[dict]
    granularity_seconds: int | None


@dataclass(frozen=True)
class EquityStatistics:
    """Statistics calculated from equity curve data."""

    peak: Decimal
    trough: Decimal
    volatility: Decimal
    peak_timestamp: datetime | None
    trough_timestamp: datetime | None
    total_points: int


class EquityService:
    def parse_iso_dt(self, value: object) -> datetime | None:
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        try:
            # Django's parse_datetime handles ISO 8601, including timezone offsets.
            from django.utils.dateparse import parse_datetime

            return parse_datetime(str(value))
        except Exception:  # pylint: disable=broad-exception-caught
            return None

    def downsample_equity_curve(
        self,
        equity_curve: object,
        *,
        max_points: int = 500,
        start_dt: object | None = None,
        end_dt: object | None = None,
    ) -> DownsampleResult:
        """Downsample equity curve to <= max_points using time-based bucketing.

        The bucket size (granularity) is computed from elapsed time.
        """

        if not isinstance(equity_curve, list):
            return DownsampleResult(points=[], granularity_seconds=None)

        raw_points = [p for p in equity_curve if isinstance(p, dict)]
        if not raw_points:
            return DownsampleResult(points=[], granularity_seconds=None)

        # Normalize timestamps so charts don't collapse points when timestamps are
        # missing/invalid/duplicated (common in older persisted metrics or running trades).
        points = [dict(p) for p in raw_points]

        parsed_ts: list[datetime | None] = [self.parse_iso_dt(p.get("timestamp")) for p in points]

        start = self.parse_iso_dt(start_dt) or next((t for t in parsed_ts if t is not None), None)
        if start is None:
            # Fallback to a stable base time.
            from django.utils import timezone

            start = timezone.now()

        end = (
            self.parse_iso_dt(end_dt)
            or next((t for t in reversed(parsed_ts) if t is not None), None)
            or start
        )

        # Ensure end >= start and give some span if we have multiple points.
        if end < start:
            end = start
        if end == start and len(points) > 1:
            end = start + timedelta(seconds=len(points) - 1)

        span_seconds = max(1, int((end - start).total_seconds()))
        step_seconds = max(1, span_seconds // max(1, (len(points) - 1)))

        last_ts: datetime | None = None
        for idx, point in enumerate(points):
            ts = self.parse_iso_dt(point.get("timestamp"))
            if ts is None:
                ts = start + timedelta(seconds=idx * step_seconds)
                point["timestamp"] = ts.isoformat()

            if last_ts is not None and ts <= last_ts:
                ts = last_ts + timedelta(seconds=1)
                point["timestamp"] = ts.isoformat()
            last_ts = ts

        if len(points) <= max_points:
            return DownsampleResult(points=points, granularity_seconds=None)

        parsed_ts = [self.parse_iso_dt(p.get("timestamp")) for p in points]
        # At this point, normalization should guarantee parseability, but keep a safe fallback.
        if any(t is None for t in parsed_ts):
            stride = max(1, len(points) // max_points)
            sampled = points[::stride]
            if sampled[-1] is not points[-1]:
                sampled.append(points[-1])
            return DownsampleResult(points=sampled[:max_points], granularity_seconds=None)

        elapsed_seconds = max(1, int((end - start).total_seconds()))
        granularity_seconds = max(1, (elapsed_seconds + (max_points - 2)) // (max_points - 1))

        buckets: dict[int, dict] = {}
        for point, ts in zip(points, parsed_ts, strict=False):
            if ts is None:
                idx = 0
            else:
                idx = int((ts - start).total_seconds() // granularity_seconds)
            buckets[idx] = point

        sampled = [buckets[k] for k in sorted(buckets.keys())]
        if sampled and sampled[0] is not points[0]:
            sampled.insert(0, points[0])
        if sampled and sampled[-1] is not points[-1]:
            sampled.append(points[-1])

        if len(sampled) > max_points:
            stride = max(1, len(sampled) // max_points)
            sampled = sampled[::stride]
            if sampled[-1] is not points[-1]:
                sampled.append(points[-1])
            sampled = sampled[:max_points]

        return DownsampleResult(points=sampled, granularity_seconds=granularity_seconds)

    def calculate_equity_statistics(
        self,
        equity_curve: list[dict[str, Any]] | None,
    ) -> EquityStatistics | None:
        """Calculate statistics from equity curve data.

        Calculates:
        - Peak: Maximum balance value
        - Trough: Minimum balance value
        - Volatility: Standard deviation of balance values

        Args:
            equity_curve: List of equity points with 'balance' and 'timestamp' fields

        Returns:
            EquityStatistics object with calculated values, or None if insufficient data
        """
        if not equity_curve or not isinstance(equity_curve, list):
            return None

        # Extract valid balance values
        balances: list[tuple[Decimal, datetime | None]] = []
        for point in equity_curve:
            if not isinstance(point, dict):
                continue

            balance_value = point.get("balance")
            if balance_value is None:
                continue

            # Convert to Decimal
            try:
                if isinstance(balance_value, (int, float)):
                    balance = Decimal(str(balance_value))
                elif isinstance(balance_value, str):
                    balance = Decimal(balance_value)
                elif isinstance(balance_value, Decimal):
                    balance = balance_value
                else:
                    continue
            except (ValueError, TypeError, Exception):
                # Skip invalid balance values (e.g., "invalid", nested dicts)
                continue

            timestamp = self.parse_iso_dt(point.get("timestamp"))
            balances.append((balance, timestamp))

        if not balances:
            return None

        # Calculate peak
        peak_balance, peak_ts = max(balances, key=lambda x: x[0])

        # Calculate trough
        trough_balance, trough_ts = min(balances, key=lambda x: x[0])

        # Calculate volatility (standard deviation)
        balance_values = [b for b, _ in balances]
        n = len(balance_values)

        if n < 2:
            # Need at least 2 points for volatility
            volatility = Decimal("0")
        else:
            # Calculate mean
            mean = sum(balance_values) / n

            # Calculate variance
            variance = sum((float(b) - float(mean)) ** 2 for b in balance_values) / (n - 1)

            # Calculate standard deviation
            # Use float for sqrt, then convert back to Decimal
            import math

            volatility = Decimal(str(math.sqrt(float(variance))))

        return EquityStatistics(
            peak=peak_balance,
            trough=trough_balance,
            volatility=volatility,
            peak_timestamp=peak_ts,
            trough_timestamp=trough_ts,
            total_points=n,
        )
