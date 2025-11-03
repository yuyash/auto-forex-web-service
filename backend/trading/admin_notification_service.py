"""
Admin notification service.

This module provides functionality for sending notifications to admin users
for critical events such as margin liquidation, connection failures, and
system health issues.

Requirements: 33.1, 33.2, 33.3, 33.4, 33.5
"""

import logging
from typing import List

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from trading.event_models import Notification

logger = logging.getLogger(__name__)


class AdminNotificationService:
    """
    Service for sending notifications to admin users.

    This service handles creating notification records and broadcasting
    them to connected admin users via WebSocket.

    Requirements: 33.1, 33.2, 33.3, 33.4, 33.5
    """

    def __init__(self) -> None:
        """Initialize the admin notification service."""
        self.channel_layer = get_channel_layer()

    def send_notification(
        self,
        title: str,
        message: str,
        notification_type: str,
        severity: str = "info",
    ) -> Notification:
        """
        Send a notification to all admin users.

        Args:
            title: Notification title
            message: Notification message
            notification_type: Type of notification (e.g., 'margin_warning')
            severity: Severity level (info, warning, error, critical)

        Returns:
            Created Notification instance
        """
        # Create notification record
        notification = Notification.objects.create(
            title=title,
            message=message,
            notification_type=notification_type,
            severity=severity,
            is_read=False,
        )

        # Broadcast to admin users via WebSocket
        self._broadcast_to_admins(notification)

        logger.info(
            "Admin notification sent: %s (severity=%s, type=%s)",
            title,
            severity,
            notification_type,
        )

        return notification

    def send_margin_liquidation_notification(
        self,
        account_id: int,
        account_name: str,
        margin_ratio: float,
        positions_closed: int,
    ) -> Notification:
        """
        Send notification for margin liquidation event.

        Requirements: 33.1

        Args:
            account_id: OANDA account ID
            account_name: Account identifier
            margin_ratio: Margin-liquidation ratio that triggered the event
            positions_closed: Number of positions closed

        Returns:
            Created Notification instance
        """
        return self.send_notification(
            title="Margin Liquidation Triggered",
            message=(
                f"Margin protection activated for account {account_name}. "
                f"Margin ratio: {margin_ratio:.2%}. "
                f"Positions closed: {positions_closed}. "
                f"Account ID: {account_id}"
            ),
            notification_type="margin_liquidation",
            severity="critical",
        )

    def send_connection_failure_notification(
        self,
        service: str,
        error_message: str,
        retry_attempts: int,
    ) -> Notification:
        """
        Send notification for connection failure.

        Requirements: 33.2

        Args:
            service: Service that failed (e.g., "OANDA v20 Stream", "Redis")
            error_message: Error message
            retry_attempts: Number of retry attempts made

        Returns:
            Created Notification instance
        """
        return self.send_notification(
            title=f"{service} Connection Failed",
            message=(
                f"Failed to connect to {service} after {retry_attempts} attempts. "
                f"Error: {error_message}"
            ),
            notification_type="connection_failure",
            severity="error",
        )

    def send_health_critical_notification(
        self,
        component: str,
        metric: str,
        current_value: float,
        threshold: float,
    ) -> Notification:
        """
        Send notification for critical health metric.

        Requirements: 33.3

        Args:
            component: System component (e.g., "CPU", "Memory", "Database")
            metric: Metric name
            current_value: Current metric value
            threshold: Threshold that was exceeded

        Returns:
            Created Notification instance
        """
        return self.send_notification(
            title=f"Critical: {component} {metric}",
            message=(
                f"{component} {metric} has exceeded critical threshold. "
                f"Current: {current_value:.2f}, Threshold: {threshold:.2f}"
            ),
            notification_type="health_critical",
            severity="critical",
        )

    def send_volatility_lock_notification(
        self,
        account_id: int,
        account_name: str,
        instrument: str,
        current_atr: float,
        normal_atr: float,
    ) -> Notification:
        """
        Send notification for volatility lock event.

        Args:
            account_id: OANDA account ID
            account_name: Account identifier
            instrument: Currency pair
            current_atr: Current ATR value
            normal_atr: Normal ATR baseline

        Returns:
            Created Notification instance
        """
        atr_multiplier = current_atr / normal_atr if normal_atr > 0 else 0
        return self.send_notification(
            title="Volatility Lock Activated",
            message=(
                f"Trading paused for account {account_name} due to high volatility. "
                f"Instrument: {instrument}, ATR: {current_atr:.5f} "
                f"(Normal: {normal_atr:.5f}, Multiplier: {atr_multiplier:.2f}x). "
                f"Account ID: {account_id}"
            ),
            notification_type="volatility_lock",
            severity="warning",
        )

    def _broadcast_to_admins(self, notification: Notification) -> None:
        """
        Broadcast notification to all connected admin users via WebSocket.

        Args:
            notification: Notification instance to broadcast
        """
        if not self.channel_layer:
            logger.warning("Channel layer not available, skipping WebSocket broadcast")
            return

        try:
            # Prepare notification data
            notification_data = {
                "type": "admin_notification",
                "data": {
                    "id": notification.id,
                    "title": notification.title,
                    "message": notification.message,
                    "severity": notification.severity,
                    "notification_type": notification.notification_type,
                    "timestamp": notification.created_at.isoformat(),
                    "is_read": notification.is_read,
                },
            }

            # Send to admin notification group
            async_to_sync(self.channel_layer.group_send)("admin_notifications", notification_data)

            logger.debug("Notification broadcast to admin group: %s", notification.title)

        except Exception as e:
            logger.error("Failed to broadcast notification to admins: %s", e, exc_info=True)

    def get_unread_notifications(self, limit: int = 50) -> List[Notification]:
        """
        Get unread notifications for admin users.

        Args:
            limit: Maximum number of notifications to return

        Returns:
            List of unread Notification instances
        """
        return list(Notification.objects.filter(is_read=False).order_by("-created_at")[:limit])

    def mark_as_read(self, notification_id: int) -> bool:
        """
        Mark a notification as read.

        Args:
            notification_id: ID of the notification to mark as read

        Returns:
            True if successful, False otherwise
        """
        try:
            notification = Notification.objects.get(id=notification_id)
            notification.is_read = True
            notification.save(update_fields=["is_read"])
            return True
        except Notification.DoesNotExist:
            logger.warning("Notification %d not found", notification_id)
            return False
        except Exception as e:
            logger.error("Failed to mark notification as read: %s", e, exc_info=True)
            return False

    def mark_all_as_read(self) -> int:
        """
        Mark all unread notifications as read.

        Returns:
            Number of notifications marked as read
        """
        try:
            count = Notification.objects.filter(is_read=False).update(is_read=True)
            logger.info("Marked %d notifications as read", count)
            return count
        except Exception as e:
            logger.error("Failed to mark all notifications as read: %s", e, exc_info=True)
            return 0
