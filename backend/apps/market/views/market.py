"""Market status views."""

from datetime import UTC, datetime, timedelta
from logging import Logger, getLogger
from typing import Any

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

logger: Logger = getLogger(name=__name__)


class MarketStatusView(APIView):
    """
    API endpoint for fetching forex market open/close status.

    GET /api/market/status/
    - Returns current market status (open/closed)
    - Includes trading session information
    - Requires authentication
    """

    permission_classes = [IsAuthenticated]

    # Forex market sessions (in UTC)
    MARKET_SESSIONS = {
        "sydney": {"open": 21, "close": 6},  # 21:00 - 06:00 UTC
        "tokyo": {"open": 0, "close": 9},  # 00:00 - 09:00 UTC
        "london": {"open": 7, "close": 16},  # 07:00 - 16:00 UTC
        "new_york": {"open": 12, "close": 21},  # 12:00 - 21:00 UTC
    }

    @extend_schema(
        summary="GET /api/market/status/",
        description="Retrieve current forex market open/close status and trading session information",
        operation_id="get_market_status",
        tags=["market"],
        responses={200: dict},
    )
    def get(self, _request: Request) -> Response:
        """
        Get current forex market status.

        Returns:
            Response with market status and active sessions
        """
        now = datetime.now(UTC)
        current_hour = now.hour
        current_weekday = now.weekday()  # 0=Monday, 6=Sunday

        # Forex market is closed from Friday 21:00 UTC to Sunday 21:00 UTC
        is_weekend_closed = (
            (current_weekday == 4 and current_hour >= 21)  # Friday after 21:00
            or current_weekday == 5  # Saturday
            or (current_weekday == 6 and current_hour < 21)  # Sunday before 21:00
        )

        # Determine active sessions
        active_sessions = []
        for session_name, hours in self.MARKET_SESSIONS.items():
            if self._is_session_active(current_hour, hours["open"], hours["close"]):
                active_sessions.append(session_name)

        # Market is open if not weekend and at least one session is active
        is_market_open = not is_weekend_closed and len(active_sessions) > 0

        # Calculate next market open/close
        next_event = self._get_next_market_event(now, is_market_open)

        response_data = {
            "is_open": is_market_open,
            "current_time_utc": now.isoformat(),
            "active_sessions": active_sessions,
            "sessions": {
                name: {
                    "open_hour_utc": hours["open"],
                    "close_hour_utc": hours["close"],
                    "is_active": name in active_sessions,
                }
                for name, hours in self.MARKET_SESSIONS.items()
            },
            "next_event": next_event,
            "is_weekend": is_weekend_closed,
        }

        return Response(response_data, status=status.HTTP_200_OK)

    def _is_session_active(self, current_hour: int, open_hour: int, close_hour: int) -> bool:
        """Check if a trading session is currently active."""
        if open_hour < close_hour:
            return open_hour <= current_hour < close_hour
        else:  # Session spans midnight (e.g., Sydney)
            return current_hour >= open_hour or current_hour < close_hour

    def _get_next_market_event(self, now: datetime, is_open: bool) -> dict[str, Any]:
        """Calculate the next market open or close event."""
        current_weekday = now.weekday()
        current_hour = now.hour

        if is_open:
            # Market is open, find next close (Friday 21:00 UTC)
            days_until_friday = (4 - current_weekday) % 7
            if current_weekday == 4 and current_hour < 21:
                days_until_friday = 0

            next_close = now.replace(hour=21, minute=0, second=0, microsecond=0)
            if days_until_friday > 0 or (days_until_friday == 0 and current_hour >= 21):
                next_close = next_close + timedelta(days=days_until_friday)

            return {
                "event": "close",
                "time_utc": next_close.isoformat(),
                "description": "Market closes for the weekend",
            }
        else:
            # Market is closed, find next open (Sunday 21:00 UTC)
            days_until_sunday = (6 - current_weekday) % 7
            if current_weekday == 6 and current_hour >= 21:
                days_until_sunday = 7  # Next Sunday

            next_open = now.replace(hour=21, minute=0, second=0, microsecond=0)
            next_open = next_open + timedelta(days=days_until_sunday)

            return {
                "event": "open",
                "time_utc": next_open.isoformat(),
                "description": "Market opens for the week",
            }
