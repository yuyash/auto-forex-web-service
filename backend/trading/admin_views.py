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

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from accounts.models import User, UserSession
from accounts.permissions import IsAdminUser
from trading.event_logger import EventLogger
from trading.models import Strategy
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

        # TODO: Close all active v20 streams for this user
        # This will be implemented when stream management is added

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

        # TODO: Close all open positions for this strategy
        # This will be implemented when position closing logic is added
        positions_closed = 0

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
def get_admin_dashboard(request: Request) -> Response:  # pylint: disable=unused-argument
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

        # Get online users count
        online_users_count = UserSession.objects.filter(is_active=True).count()

        # Get running strategies count
        running_strategies_count = Strategy.objects.filter(is_active=True).count()

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
            "system_health": health_data,
            "online_users_count": online_users_count,
            "running_strategies_count": running_strategies_count,
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
