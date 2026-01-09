"""Equity-curve related helpers.

Kept as a service to avoid view-level helper functions and to centralize
sampling/normalization logic used by results endpoints.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class DownsampleResult:
    points: list[dict]
    granularity_seconds: int | None


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
