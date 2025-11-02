"""
Event logging models for system, trading, and security events.

This module contains models for:
- Event: System event log for all categories
- Notification: Admin notifications for critical events

Requirements: 24.1, 24.2, 24.3, 24.5, 25.1, 25.2, 25.5, 26.1, 26.2, 26.5, 27.1
"""

from typing import TYPE_CHECKING

from django.contrib.auth import get_user_model
from django.db import models

from accounts.models import OandaAccount

if TYPE_CHECKING:
    from accounts.models import User as UserType
else:
    UserType = None

User = get_user_model()


class Event(models.Model):
    """
    System event log for all categories.

    This model stores all system events including trading operations,
    system health, security events, and admin actions.

    Requirements: 24.1, 24.2, 24.3, 24.5, 25.1, 25.2, 25.5, 26.1, 26.2, 26.5, 27.1
    """

    CATEGORY_CHOICES = [
        ("trading", "Trading"),
        ("system", "System"),
        ("security", "Security"),
        ("admin", "Admin"),
    ]

    SEVERITY_CHOICES = [
        ("debug", "Debug"),
        ("info", "Info"),
        ("warning", "Warning"),
        ("error", "Error"),
        ("critical", "Critical"),
    ]

    timestamp = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Timestamp when the event occurred",
    )
    category = models.CharField(
        max_length=50,
        db_index=True,
        choices=CATEGORY_CHOICES,
        help_text="Event category (trading, system, security, admin)",
    )
    event_type = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Specific event type (e.g., 'order_submitted', 'login_failed')",
    )
    severity = models.CharField(
        max_length=20,
        db_index=True,
        choices=SEVERITY_CHOICES,
        help_text="Event severity level",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="events",
        help_text="User associated with this event",
    )
    account = models.ForeignKey(
        OandaAccount,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="events",
        help_text="OANDA account associated with this event",
    )
    description = models.TextField(
        help_text="Human-readable description of the event",
    )
    details = models.JSONField(
        default=dict,
        help_text="Additional event details in JSON format",
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address associated with the event",
    )
    user_agent = models.TextField(
        null=True,
        blank=True,
        help_text="User agent string (for HTTP requests)",
    )

    class Meta:
        db_table = "events"
        verbose_name = "Event"
        verbose_name_plural = "Events"
        indexes = [
            models.Index(fields=["timestamp", "category"]),
            models.Index(fields=["timestamp", "severity"]),
            models.Index(fields=["user", "timestamp"]),
            models.Index(fields=["category", "event_type"]),
            models.Index(fields=["severity", "timestamp"]),
        ]
        ordering = ["-timestamp"]

    def __str__(self) -> str:
        return f"[{self.severity.upper()}] {self.category}: {self.event_type} at {self.timestamp}"

    @classmethod
    def log_trading_event(
        cls,
        event_type: str,
        description: str,
        *,
        severity: str = "info",
        user: "UserType | None" = None,
        account: OandaAccount | None = None,
        details: dict | None = None,
    ) -> "Event":
        """
        Log a trading event.

        Args:
            event_type: Type of trading event
            description: Event description
            severity: Event severity level
            user: User associated with the event
            account: OANDA account associated with the event
            details: Additional event details

        Returns:
            Created Event instance
        """
        return cls.objects.create(
            category="trading",
            event_type=event_type,
            description=description,
            severity=severity,
            user=user,
            account=account,
            details=details or {},
        )

    @classmethod
    def log_system_event(
        cls,
        event_type: str,
        description: str,
        severity: str = "info",
        details: dict | None = None,
    ) -> "Event":
        """
        Log a system event.

        Args:
            event_type: Type of system event
            description: Event description
            severity: Event severity level
            details: Additional event details

        Returns:
            Created Event instance
        """
        return cls.objects.create(
            category="system",
            event_type=event_type,
            description=description,
            severity=severity,
            details=details or {},
        )

    @classmethod
    def log_security_event(
        cls,
        event_type: str,
        description: str,
        *,
        severity: str = "warning",
        user: "UserType | None" = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        details: dict | None = None,
    ) -> "Event":
        """
        Log a security event.

        Args:
            event_type: Type of security event
            description: Event description
            severity: Event severity level
            user: User associated with the event
            ip_address: IP address associated with the event
            user_agent: User agent string
            details: Additional event details

        Returns:
            Created Event instance
        """
        return cls.objects.create(
            category="security",
            event_type=event_type,
            description=description,
            severity=severity,
            user=user,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details or {},
        )

    @classmethod
    def log_admin_event(
        cls,
        event_type: str,
        description: str,
        *,
        severity: str = "info",
        user: "UserType | None" = None,
        details: dict | None = None,
    ) -> "Event":
        """
        Log an admin event.

        Args:
            event_type: Type of admin event
            description: Event description
            severity: Event severity level
            user: Admin user who performed the action
            details: Additional event details

        Returns:
            Created Event instance
        """
        return cls.objects.create(
            category="admin",
            event_type=event_type,
            description=description,
            severity=severity,
            user=user,
            details=details or {},
        )


class Notification(models.Model):
    """
    Admin notification for critical events.

    This model stores notifications that should be sent to admin users
    for critical system events, margin warnings, and other important alerts.

    Requirements: 33.1, 33.2, 33.3, 33.4, 33.5
    """

    SEVERITY_CHOICES = [
        ("info", "Info"),
        ("warning", "Warning"),
        ("error", "Error"),
        ("critical", "Critical"),
    ]

    timestamp = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Timestamp when the notification was created",
    )
    notification_type = models.CharField(
        max_length=50,
        help_text="Type of notification (e.g., 'margin_warning', 'connection_failure')",
    )
    title = models.CharField(
        max_length=200,
        help_text="Notification title",
    )
    message = models.TextField(
        help_text="Notification message",
    )
    severity = models.CharField(
        max_length=20,
        choices=SEVERITY_CHOICES,
        help_text="Notification severity level",
    )
    is_read = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether the notification has been read",
    )
    related_event = models.ForeignKey(
        Event,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
        help_text="Related event that triggered this notification",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when the notification was created",
    )

    class Meta:
        db_table = "notifications"
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        indexes = [
            models.Index(fields=["timestamp", "is_read"]),
            models.Index(fields=["severity", "is_read"]),
            models.Index(fields=["notification_type"]),
        ]
        ordering = ["-timestamp"]

    def __str__(self) -> str:
        status = "Read" if self.is_read else "Unread"
        return f"[{self.severity.upper()}] {self.title} - {status}"

    def mark_as_read(self) -> None:
        """Mark the notification as read."""
        self.is_read = True
        self.save(update_fields=["is_read"])

    def mark_as_unread(self) -> None:
        """Mark the notification as unread."""
        self.is_read = False
        self.save(update_fields=["is_read"])

    @classmethod
    def create_margin_warning(
        cls,
        account: OandaAccount,
        ratio: float,
        event: Event | None = None,
    ) -> "Notification":
        """
        Create a margin warning notification.

        Args:
            account: OANDA account with margin issues
            ratio: Current margin-liquidation ratio
            event: Related event

        Returns:
            Created Notification instance
        """
        return cls.objects.create(
            notification_type="margin_warning",
            title=f"Margin Warning: {account.account_id}",
            message=f"Margin-liquidation ratio reached {ratio:.2%}. "
            f"Account: {account.account_id}",
            severity="critical",
            related_event=event,
        )

    @classmethod
    def create_connection_failure(
        cls,
        account: OandaAccount,
        error_message: str,
        event: Event | None = None,
    ) -> "Notification":
        """
        Create a connection failure notification.

        Args:
            account: OANDA account with connection issues
            error_message: Error message
            event: Related event

        Returns:
            Created Notification instance
        """
        return cls.objects.create(
            notification_type="connection_failure",
            title=f"Connection Failure: {account.account_id}",
            message=f"Failed to connect to OANDA API for account {account.account_id}. "
            f"Error: {error_message}",
            severity="error",
            related_event=event,
        )

    @classmethod
    def create_system_health_alert(
        cls,
        title: str,
        message: str,
        severity: str = "warning",
        event: Event | None = None,
    ) -> "Notification":
        """
        Create a system health alert notification.

        Args:
            title: Notification title
            message: Notification message
            severity: Notification severity
            event: Related event

        Returns:
            Created Notification instance
        """
        return cls.objects.create(
            notification_type="system_health",
            title=title,
            message=message,
            severity=severity,
            related_event=event,
        )
