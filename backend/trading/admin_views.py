"""
Admin dashboard views and operations.

This module provides admin-only endpoints for:
- System health monitoring
- User session management
- Running strategies monitoring
- User kick-off functionality
- Admin strategy stop functionality
- Admin dashboard aggregation

Requirements: 19.1-19.5, 20.1-20.5, 21.1-21.5, 22.1-22.5, 23.1-23.5, 28.1-28.5
"""

import logging
from datetime import timedelta

from django.utils import timezone

import psutil
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from accounts.models import User, UserSession
from accounts.permissions import IsAdminUser
from trading.event_logger import EventLogger
from trading.models import Position, Strategy
from trading.position_manager import PositionManager
from trading.system_health_monitor import SystemHealthMonitor

logger = logging.getLogger(__name__)


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsAdminUser])
def get_system_health(request: Request) -> Response:
    """
    Get comprehensive system health metrics.

    This endpoint provides CPU, memory, database, Redis, and OANDA API
    connection status, along with active streams and Celery task counts.

    Requirements: 19.1, 19.2, 19.3, 19.4

    Args:
        request: HTTP request object

    Returns:
        Response with system health metrics
    """
    try:
        monitor = SystemHealthMonitor()
        health_data = monitor.get_health_summary()

        # Log health check
        admin_email = str(request.user.email) if hasattr(request.user, "email") else "unknown"
        logger.info(
            "System health check by admin %s: Status=%s",
            admin_email,
            health_data["overall_status"],
        )

        return Response(health_data, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error("Failed to get system health: %s", e, exc_info=True)
        return Response(
            {"error": "Failed to retrieve system health metrics"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsAdminUser])
def get_online_users(request: Request) -> Response:  # pylint: disable=unused-argument
    """
    Get list of all currently logged-in users with session details.

    Requirements: 20.1, 20.2, 20.3, 20.4

    Args:
        request: HTTP request object

    Returns:
        Response with list of online users
    """
    try:
        # Get all active sessions
        active_sessions = (
            UserSession.objects.filter(is_active=True)
            .select_related("user")
            .order_by("-last_activity")
        )

        users_data = []
        for session in active_sessions:
            users_data.append(
                {
                    "user_id": session.user.id,
                    "username": session.user.username,
                    "email": session.user.email,
                    "session_id": session.id,
                    "session_key": session.session_key,
                    "ip_address": session.ip_address,
                    "user_agent": session.user_agent,
                    "login_time": session.login_time.isoformat(),
                    "last_activity": session.last_activity.isoformat(),
                    "is_staff": session.user.is_staff,
                }
            )

        return Response(
            {
                "count": len(users_data),
                "users": users_data,
                "timestamp": timezone.now().isoformat(),
            },
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        logger.error("Failed to get online users: %s", e, exc_info=True)
        return Response(
            {"error": "Failed to retrieve online users"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsAdminUser])
def get_running_strategies(request: Request) -> Response:  # pylint: disable=unused-argument
    """
    Get list of all active strategies across all users.

    Requirements: 21.1, 21.2, 21.3, 21.4

    Args:
        request: HTTP request object

    Returns:
        Response with list of running strategies
    """
    try:
        # Get all active strategies
        active_strategies = (
            Strategy.objects.filter(is_active=True)
            .select_related("account__user")
            .prefetch_related("account__positions")
        )

        strategies_data = []
        for strategy in active_strategies:
            # Calculate position count and total P&L
            positions = strategy.account.positions.filter(
                opened_at__isnull=False, closed_at__isnull=True
            )
            position_count = positions.count()
            total_pnl = sum(pos.unrealized_pnl for pos in positions)

            strategies_data.append(
                {
                    "strategy_id": strategy.id,
                    "strategy_type": strategy.strategy_type,
                    "user_id": strategy.account.user.id,
                    "username": strategy.account.user.username,
                    "email": strategy.account.user.email,
                    "account_id": strategy.account.id,
                    "oanda_account_id": strategy.account.account_id,
                    "instruments": strategy.instruments,
                    "started_at": (
                        strategy.started_at.isoformat() if strategy.started_at else None
                    ),
                    "position_count": position_count,
                    "total_unrealized_pnl": float(total_pnl),
                }
            )

        return Response(
            {
                "count": len(strategies_data),
                "strategies": strategies_data,
                "timestamp": timezone.now().isoformat(),
            },
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        logger.error("Failed to get running strategies: %s", e, exc_info=True)
        return Response(
            {"error": "Failed to retrieve running strategies"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsAdminUser])
def kickoff_user(request: Request, user_id: int) -> Response:
    """
    Forcibly disconnect a user session.

    This endpoint invalidates all JWT tokens for the user and closes
    all active v20 streams.

    Requirements: 22.1, 22.2, 22.3, 22.4

    Args:
        request: HTTP request object
        user_id: ID of the user to kick off

    Returns:
        Response indicating success or failure
    """
    try:
        # Get the target user
        target_user = User.objects.get(id=user_id)

        # Terminate all active sessions
        active_sessions = UserSession.objects.filter(user=target_user, is_active=True)

        session_count = active_sessions.count()
        for session in active_sessions:
            session.terminate()

        # Close all active v20 streams for this user
        streams_closed = _close_user_streams(target_user)

        # Log the kick-off event
        event_logger = EventLogger()
        admin_email = str(request.user.email) if hasattr(request.user, "email") else "unknown"
        event_logger.log_event(
            category="admin",
            event_type="user_kickoff",
            severity="warning",
            description=f"Admin {admin_email} kicked off user {target_user.email}",
            details={
                "admin_user_id": request.user.id,
                "admin_email": admin_email,
                "target_user_id": target_user.id,
                "target_email": target_user.email,
                "sessions_terminated": session_count,
                "streams_closed": streams_closed,
            },
            user=request.user if hasattr(request.user, "id") else None,  # type: ignore[arg-type]
        )

        logger.warning(
            "Admin %s kicked off user %s (%d sessions terminated)",
            admin_email,
            target_user.email,
            session_count,
        )

        return Response(
            {
                "message": f"User {target_user.email} has been kicked off",
                "sessions_terminated": session_count,
                "streams_closed": streams_closed,
            },
            status=status.HTTP_200_OK,
        )

    except User.DoesNotExist:
        return Response(
            {"error": "User not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        logger.error("Failed to kick off user: %s", e, exc_info=True)
        return Response(
            {"error": "Failed to kick off user"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsAdminUser])
def stop_strategy(request: Request, strategy_id: int) -> Response:
    """
    Stop a running trading strategy.

    This endpoint stops strategy execution within 1 second and closes
    all open positions associated with the strategy.

    Requirements: 23.1, 23.2, 23.3, 23.4

    Args:
        request: HTTP request object
        strategy_id: ID of the strategy to stop

    Returns:
        Response indicating success or failure
    """
    try:
        # Get the strategy
        strategy = Strategy.objects.select_related("account__user").get(id=strategy_id)

        if not strategy.is_active:
            return Response(
                {"error": "Strategy is not currently active"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Stop the strategy
        strategy.is_active = False
        strategy.stopped_at = timezone.now()
        strategy.save(update_fields=["is_active", "stopped_at"])

        # Close all open positions for this strategy
        positions_closed = _close_strategy_positions(strategy)

        # Log the admin stop event
        event_logger = EventLogger()
        admin_email = str(request.user.email) if hasattr(request.user, "email") else "unknown"
        description = (
            f"Admin {admin_email} stopped strategy {strategy.strategy_type} "
            f"for user {strategy.account.user.email}"
        )
        event_logger.log_event(
            category="admin",
            event_type="strategy_stop",
            severity="warning",
            description=description,
            details={
                "admin_user_id": request.user.id,
                "admin_email": admin_email,
                "strategy_id": strategy.id,
                "strategy_type": strategy.strategy_type,
                "target_user_id": strategy.account.user.id,
                "target_email": strategy.account.user.email,
                "account_id": strategy.account.id,
                "positions_closed": positions_closed,
            },
            user=request.user if hasattr(request.user, "id") else None,  # type: ignore[arg-type]
            account=strategy.account,
        )

        logger.warning(
            "Admin %s stopped strategy %s for user %s",
            admin_email,
            strategy.strategy_type,
            strategy.account.user.email,
        )

        return Response(
            {
                "message": f"Strategy {strategy.strategy_type} has been stopped",
                "strategy_id": strategy.id,
                "positions_closed": positions_closed,
            },
            status=status.HTTP_200_OK,
        )

    except Strategy.DoesNotExist:
        return Response(
            {"error": "Strategy not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        logger.error("Failed to stop strategy: %s", e, exc_info=True)
        return Response(
            {"error": "Failed to stop strategy"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsAdminUser])
def get_admin_dashboard(request: Request) -> Response:
    # pylint: disable=unused-argument,too-many-locals
    """
    Get comprehensive admin dashboard data.

    This endpoint aggregates health metrics, online users, running strategies,
    and recent events into a single response.

    Requirements: 28.1, 28.2, 28.3, 28.4

    Args:
        request: HTTP request object

    Returns:
        Response with aggregated dashboard data
    """
    try:
        # Import here to avoid circular imports
        from trading.event_models import Event

        # Get system health
        monitor = SystemHealthMonitor()
        health_data = monitor.get_health_summary()

        # Transform health data to match frontend expectations
        health = {
            "cpu_usage": health_data.get("cpu", {}).get("cpu_percent", 0),
            "memory_usage": health_data.get("memory", {}).get("percent", 0),
            "disk_usage": psutil.disk_usage("/").percent,
            "database_status": (
                "connected" if health_data.get("database", {}).get("connected") else "disconnected"
            ),
            "redis_status": (
                "connected" if health_data.get("redis", {}).get("connected") else "disconnected"
            ),
            "oanda_api_status": (
                "connected"
                if health_data.get("oanda_api", {}).get("status") == "healthy"
                else "disconnected"
            ),
            "active_streams": health_data.get("active_streams", 0),
            "celery_tasks": health_data.get("celery_tasks", {}).get("total", 0),
            "timestamp": health_data.get("timestamp"),
        }

        # Get online users with session details
        active_sessions = (
            UserSession.objects.filter(is_active=True)
            .select_related("user")
            .order_by("-last_activity")
        )

        online_users = [
            {
                "user_id": session.user.id,
                "username": session.user.username,
                "email": session.user.email,
                "session_id": session.id,
                "session_key": session.session_key,
                "ip_address": session.ip_address,
                "user_agent": session.user_agent,
                "login_time": session.login_time.isoformat(),
                "last_activity": session.last_activity.isoformat(),
                "is_staff": session.user.is_staff,
            }
            for session in active_sessions
        ]

        # Get running strategies with details
        active_strategies = (
            Strategy.objects.filter(is_active=True)
            .select_related("account__user")
            .prefetch_related("account__positions")
        )

        running_strategies = []
        for strategy in active_strategies:
            positions = strategy.account.positions.filter(
                opened_at__isnull=False, closed_at__isnull=True
            )
            position_count = positions.count()
            total_pnl = sum(pos.unrealized_pnl for pos in positions)

            running_strategies.append(
                {
                    "strategy_id": strategy.id,
                    "strategy_type": strategy.strategy_type,
                    "user_id": strategy.account.user.id,
                    "username": strategy.account.user.username,
                    "email": strategy.account.user.email,
                    "account_id": strategy.account.id,
                    "oanda_account_id": strategy.account.account_id,
                    "instruments": strategy.instruments,
                    "started_at": (
                        strategy.started_at.isoformat() if strategy.started_at else None
                    ),
                    "position_count": position_count,
                    "total_unrealized_pnl": float(total_pnl),
                }
            )

        # Get recent events (last 10)
        recent_events = Event.objects.order_by("-timestamp")[:10]
        events_data = [
            {
                "id": event.id,
                "timestamp": event.timestamp.isoformat(),
                "category": event.category,
                "event_type": event.event_type,
                "severity": event.severity,
                "description": event.description,
            }
            for event in recent_events
        ]

        # Get critical alerts (errors and warnings from last hour)
        one_hour_ago = timezone.now() - timedelta(hours=1)
        critical_alerts = Event.objects.filter(
            timestamp__gte=one_hour_ago, severity__in=["error", "critical", "warning"]
        ).count()

        dashboard_data = {
            "timestamp": timezone.now().isoformat(),
            "health": health,
            "online_users": online_users,
            "running_strategies": running_strategies,
            "critical_alerts_count": critical_alerts,
            "recent_events": events_data,
        }

        return Response(dashboard_data, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error("Failed to get admin dashboard: %s", e, exc_info=True)
        return Response(
            {"error": "Failed to retrieve admin dashboard data"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


def _get_failed_logins_data(one_day_ago):  # type: ignore[no-untyped-def]
    """Get failed login attempts data."""
    from trading.event_models import Event

    failed_logins = Event.objects.filter(
        category="security",
        event_type="login_failed",
        timestamp__gte=one_day_ago,
    ).order_by("-timestamp")[:50]

    return [
        {
            "id": event.id,
            "timestamp": event.timestamp.isoformat(),
            "ip_address": event.ip_address,
            "user_email": event.details.get("email", "unknown"),
            "user_agent": event.user_agent,
            "description": event.description,
        }
        for event in failed_logins
    ], failed_logins.count()


def _get_blocked_ips_data():  # type: ignore[no-untyped-def]
    """Get blocked IP addresses data."""
    from accounts.models import BlockedIP

    blocked_ips = BlockedIP.objects.filter(blocked_until__gt=timezone.now()).order_by("-blocked_at")

    return [
        {
            "id": blocked_ip.id,
            "ip_address": blocked_ip.ip_address,
            "reason": blocked_ip.reason,
            "failed_attempts": blocked_ip.failed_attempts,
            "blocked_at": blocked_ip.blocked_at.isoformat(),
            "blocked_until": blocked_ip.blocked_until.isoformat(),
            "is_permanent": blocked_ip.is_permanent,
        }
        for blocked_ip in blocked_ips
    ]


def _get_locked_accounts_data():  # type: ignore[no-untyped-def]
    """Get locked user accounts data."""
    locked_accounts = User.objects.filter(is_locked=True).order_by("-last_login_attempt")

    return [
        {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "failed_attempts": user.failed_login_attempts,
            "last_login_attempt": (
                user.last_login_attempt.isoformat() if user.last_login_attempt else None
            ),
            "locked_since": user.updated_at.isoformat(),
        }
        for user in locked_accounts
    ]


def _get_http_access_patterns(one_hour_ago):  # type: ignore[no-untyped-def]
    """Get HTTP access patterns data."""
    from trading.event_models import Event

    http_events = Event.objects.filter(
        category="security",
        event_type__in=["http_request", "api_request"],
        timestamp__gte=one_hour_ago,
    )

    # Aggregate requests by IP address
    ip_request_counts: dict[str, int] = {}
    for event in http_events:
        ip = event.ip_address
        if ip:
            ip_request_counts[ip] = ip_request_counts.get(ip, 0) + 1

    # Sort by request count (descending) and get top 20
    return [
        {"ip_address": ip, "request_count": count}
        for ip, count in sorted(
            ip_request_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:20]
    ]


def _get_suspicious_patterns_data(one_day_ago):  # type: ignore[no-untyped-def]
    """Get suspicious activity patterns data."""
    from trading.event_models import Event

    suspicious_events = Event.objects.filter(
        category="security",
        event_type__in=[
            "suspicious_activity",
            "sql_injection_attempt",
            "path_traversal_attempt",
            "rate_limit_exceeded",
        ],
        timestamp__gte=one_day_ago,
    ).order_by("-timestamp")[:50]

    return [
        {
            "id": event.id,
            "timestamp": event.timestamp.isoformat(),
            "event_type": event.event_type,
            "ip_address": event.ip_address,
            "severity": event.severity,
            "description": event.description,
            "details": event.details,
        }
        for event in suspicious_events
    ], suspicious_events.count()


def _get_filtered_events_data(security_events_query):  # type: ignore[no-untyped-def]
    """Get filtered security events data."""
    filtered_events = security_events_query.order_by("-timestamp")[:100]

    return [
        {
            "id": event.id,
            "timestamp": event.timestamp.isoformat(),
            "event_type": event.event_type,
            "severity": event.severity,
            "ip_address": event.ip_address,
            "user_email": event.user.email if event.user else None,
            "description": event.description,
            "details": event.details,
        }
        for event in filtered_events
    ]


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsAdminUser])
def get_security_dashboard(request: Request) -> Response:  # pylint: disable=too-many-locals
    """
    Get comprehensive security monitoring dashboard data.

    This endpoint provides security event monitoring including:
    - Failed login attempts
    - Blocked IP addresses
    - Locked user accounts
    - HTTP access patterns
    - Suspicious activity patterns

    Supports filtering by:
    - event_type: Type of security event
    - severity: Event severity level
    - ip_address: Specific IP address
    - start_date: Start of date range (ISO format)
    - end_date: End of date range (ISO format)

    Requirements: 37.1, 37.2, 37.3, 37.4

    Args:
        request: HTTP request object with optional query parameters

    Returns:
        Response with security dashboard data
    """
    try:
        # Import here to avoid circular imports
        from trading.event_models import Event

        # Get query parameters for filtering
        filters = {
            "event_type": request.query_params.get("event_type"),
            "severity": request.query_params.get("severity"),
            "ip_address": request.query_params.get("ip_address"),
            "start_date": request.query_params.get("start_date"),
            "end_date": request.query_params.get("end_date"),
        }

        # Build base query for security events
        security_events_query = Event.objects.filter(category="security")

        # Apply filters
        if filters["event_type"]:
            security_events_query = security_events_query.filter(event_type=filters["event_type"])
        if filters["severity"]:
            security_events_query = security_events_query.filter(severity=filters["severity"])
        if filters["ip_address"]:
            security_events_query = security_events_query.filter(ip_address=filters["ip_address"])
        if filters["start_date"]:
            security_events_query = security_events_query.filter(
                timestamp__gte=filters["start_date"]
            )
        if filters["end_date"]:
            security_events_query = security_events_query.filter(timestamp__lte=filters["end_date"])

        # Get time ranges
        one_day_ago = timezone.now() - timedelta(days=1)
        one_hour_ago = timezone.now() - timedelta(hours=1)

        # Get all data sections using helper functions
        failed_logins_data, failed_logins_count = _get_failed_logins_data(one_day_ago)
        blocked_ips_data = _get_blocked_ips_data()
        locked_accounts_data = _get_locked_accounts_data()
        http_access_patterns = _get_http_access_patterns(one_hour_ago)
        suspicious_patterns_data, suspicious_count = _get_suspicious_patterns_data(one_day_ago)
        filtered_events_data = _get_filtered_events_data(security_events_query)

        # Build response
        dashboard_data = {
            "timestamp": timezone.now().isoformat(),
            "summary": {
                "failed_logins_24h": failed_logins_count,
                "blocked_ips_active": len(blocked_ips_data),
                "locked_accounts": len(locked_accounts_data),
                "suspicious_events_24h": suspicious_count,
            },
            "failed_logins": failed_logins_data,
            "blocked_ips": blocked_ips_data,
            "locked_accounts": locked_accounts_data,
            "http_access_patterns": http_access_patterns,
            "suspicious_patterns": suspicious_patterns_data,
            "filtered_events": filtered_events_data,
            "filters_applied": filters,
        }

        logger.info(
            "Security dashboard accessed by admin %s",
            request.user.email if hasattr(request.user, "email") else "unknown",
        )

        return Response(dashboard_data, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error("Failed to get security dashboard: %s", e, exc_info=True)
        return Response(
            {"error": "Failed to retrieve security dashboard data"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


def _close_strategy_positions(strategy: Strategy) -> int:
    """
    Close all open positions for a strategy.

    This helper function closes all positions associated with a strategy
    by fetching current market prices and closing each position.

    Args:
        strategy: Strategy whose positions should be closed

    Returns:
        Number of positions closed
    """
    try:
        # Get all open positions for this strategy
        open_positions = Position.objects.filter(strategy=strategy, closed_at__isnull=True)

        positions_closed = 0

        # Group positions by instrument to minimize API calls
        positions_by_instrument: dict[str, list[Position]] = {}
        for position in open_positions:
            if position.instrument not in positions_by_instrument:
                positions_by_instrument[position.instrument] = []
            positions_by_instrument[position.instrument].append(position)

        # Close positions for each instrument
        for instrument, positions in positions_by_instrument.items():
            try:
                # Use current price from the first position as exit price
                # In production, you would fetch the latest market price from OANDA
                exit_price = positions[0].current_price

                for position in positions:
                    PositionManager.close_position(
                        position=position, exit_price=exit_price, create_trade_record=True
                    )
                    positions_closed += 1

                logger.info(
                    "Closed %d positions for instrument %s in strategy %s",
                    len(positions),
                    instrument,
                    strategy.id,
                )

            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error(
                    "Failed to close positions for instrument %s: %s", instrument, e, exc_info=True
                )

        return positions_closed

    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Failed to close positions for strategy %s: %s", strategy.id, e, exc_info=True)
        return 0


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsAdminUser])
def get_notifications(request: Request) -> Response:  # pylint: disable=unused-argument
    """
    Get unread admin notifications.

    This endpoint returns the most recent unread notifications for admin users.

    Args:
        request: HTTP request object

    Returns:
        Response with list of notifications
    """
    try:
        from trading.admin_notification_service import AdminNotificationService

        service = AdminNotificationService()
        notifications = service.get_unread_notifications(limit=50)

        notifications_data = [
            {
                "id": notification.id,
                "title": notification.title,
                "message": notification.message,
                "severity": notification.severity,
                "timestamp": notification.timestamp.isoformat(),
                "read": notification.is_read,
                "notification_type": notification.notification_type,
            }
            for notification in notifications
        ]

        return Response(notifications_data, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error("Failed to get notifications: %s", e, exc_info=True)
        return Response(
            {"error": "Failed to retrieve notifications"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsAdminUser])
def mark_notification_read(request: Request, notification_id: int) -> Response:
    """
    Mark a specific notification as read.

    Args:
        request: HTTP request object
        notification_id: ID of the notification to mark as read

    Returns:
        Response indicating success or failure
    """
    try:
        from trading.event_models import Notification

        notification = Notification.objects.get(id=notification_id)
        notification.is_read = True
        notification.save(update_fields=["is_read"])

        logger.info(
            "Admin %s marked notification %d as read",
            request.user.email if hasattr(request.user, "email") else "unknown",
            notification_id,
        )

        return Response({"message": "Notification marked as read"}, status=status.HTTP_200_OK)

    except Notification.DoesNotExist:
        return Response(
            {"error": "Notification not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        logger.error("Failed to mark notification as read: %s", e, exc_info=True)
        return Response(
            {"error": "Failed to mark notification as read"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsAdminUser])
def mark_all_notifications_read(request: Request) -> Response:
    """
    Mark all notifications as read.

    Args:
        request: HTTP request object

    Returns:
        Response indicating success or failure
    """
    try:
        from trading.admin_notification_service import AdminNotificationService

        service = AdminNotificationService()
        count = service.mark_all_as_read()

        logger.info(
            "Admin %s marked %d notifications as read",
            request.user.email if hasattr(request.user, "email") else "unknown",
            count,
        )

        return Response(
            {"message": f"{count} notifications marked as read", "count": count},
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        logger.error("Failed to mark all notifications as read: %s", e, exc_info=True)
        return Response(
            {"error": "Failed to mark all notifications as read"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


def _close_user_streams(user: User) -> int:
    """
    Close all active v20 streams for a user.

    This function closes all market data streams associated with the user's
    OANDA accounts by removing their cache entries, which signals the
    streaming tasks to stop.

    Args:
        user: User whose streams should be closed

    Returns:
        Number of streams closed
    """
    from django.core.cache import cache

    from accounts.models import OandaAccount

    streams_closed = 0

    try:
        # Get all OANDA accounts for this user
        user_accounts = OandaAccount.objects.filter(user=user)

        # Close stream for each account
        for account in user_accounts:
            cache_key = f"market_data_stream:{account.id}"

            # Check if stream is active
            if cache.get(cache_key):
                # Delete cache entry to signal stream should stop
                cache.delete(cache_key)
                streams_closed += 1

                logger.info(
                    "Closed market data stream for account %s (user: %s)",
                    account.account_id,
                    user.email,
                    extra={
                        "user_id": user.id,
                        "account_id": account.id,
                        "oanda_account_id": account.account_id,
                    },
                )

        if streams_closed > 0:
            logger.info(
                "Successfully closed %d stream(s) for user %s",
                streams_closed,
                user.email,
                extra={
                    "user_id": user.id,
                    "streams_closed": streams_closed,
                },
            )

        return streams_closed

    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Failed to close streams for user %s: %s", user.email, e, exc_info=True)
        return streams_closed
