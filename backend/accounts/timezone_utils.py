"""
Timezone conversion utilities.

This module provides utilities for converting timestamps to user timezones.

Requirements: 30.1, 30.2, 30.3, 30.5
"""

import logging
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from django.utils import timezone

logger = logging.getLogger(__name__)


def convert_to_user_timezone(
    dt: datetime,
    user_timezone: Optional[str] = None,
) -> datetime:
    """
    Convert a datetime to the user's timezone.

    Args:
        dt: Datetime to convert (should be timezone-aware)
        user_timezone: User's timezone (IANA identifier), defaults to UTC

    Returns:
        Datetime converted to user's timezone

    Requirements: 30.1, 30.2, 30.3
    """
    # Ensure datetime is timezone-aware
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, ZoneInfo("UTC"))

    # Default to UTC if no timezone specified
    if not user_timezone:
        user_timezone = "UTC"

    try:
        user_tz = ZoneInfo(user_timezone)
        return dt.astimezone(user_tz)
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning(
            "Failed to convert to timezone %s: %s. Using UTC.",
            user_timezone,
            str(exc),
            extra={
                "timezone": user_timezone,
                "error": str(exc),
            },
        )
        return dt.astimezone(ZoneInfo("UTC"))


def format_datetime_for_user(
    dt: datetime,
    user_timezone: Optional[str] = None,
    format_string: str = "%Y-%m-%d %H:%M:%S %Z",
) -> str:
    """
    Format a datetime for display to the user in their timezone.

    Args:
        dt: Datetime to format
        user_timezone: User's timezone (IANA identifier), defaults to UTC
        format_string: strftime format string

    Returns:
        Formatted datetime string in user's timezone

    Requirements: 30.1, 30.2, 30.3
    """
    converted_dt = convert_to_user_timezone(dt, user_timezone)
    return converted_dt.strftime(format_string)


def get_user_timezone_offset(user_timezone: Optional[str] = None) -> str:
    """
    Get the UTC offset for a user's timezone.

    Args:
        user_timezone: User's timezone (IANA identifier), defaults to UTC

    Returns:
        UTC offset string (e.g., "+09:00", "-05:00")

    Requirements: 30.1, 30.2
    """
    if not user_timezone:
        user_timezone = "UTC"

    try:
        user_tz = ZoneInfo(user_timezone)
        now = datetime.now(user_tz)
        offset = now.strftime("%z")
        # Format as +HH:MM or -HH:MM
        if len(offset) == 5:
            return f"{offset[:3]}:{offset[3:]}"
        return offset
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning(
            "Failed to get timezone offset for %s: %s. Using UTC.",
            user_timezone,
            str(exc),
            extra={
                "timezone": user_timezone,
                "error": str(exc),
            },
        )
        return "+00:00"


def convert_from_user_timezone(
    dt: datetime,
    user_timezone: Optional[str] = None,
) -> datetime:
    """
    Convert a datetime from the user's timezone to UTC.

    Args:
        dt: Datetime in user's timezone
        user_timezone: User's timezone (IANA identifier), defaults to UTC

    Returns:
        Datetime converted to UTC

    Requirements: 30.1, 30.2, 30.3
    """
    # Default to UTC if no timezone specified
    if not user_timezone:
        user_timezone = "UTC"

    try:
        user_tz = ZoneInfo(user_timezone)

        # If datetime is naive, assume it's in user's timezone
        if timezone.is_naive(dt):
            dt = dt.replace(tzinfo=user_tz)

        # Convert to UTC
        return dt.astimezone(ZoneInfo("UTC"))
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning(
            "Failed to convert from timezone %s: %s. Assuming UTC.",
            user_timezone,
            str(exc),
            extra={
                "timezone": user_timezone,
                "error": str(exc),
            },
        )
        if timezone.is_naive(dt):
            return timezone.make_aware(dt, ZoneInfo("UTC"))
        return dt.astimezone(ZoneInfo("UTC"))
