"""Security-related models for user sessions, IP blocking, and security events."""

from datetime import timedelta

from django.db import models
from django.utils import timezone


class UserSession(models.Model):
    """User session tracking for security monitoring."""

    user = models.ForeignKey(
        "User",
        on_delete=models.CASCADE,
        related_name="sessions",
        help_text="User associated with this session",
    )
    session_key = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="Django session key",
    )
    ip_address = models.GenericIPAddressField(
        help_text="IP address of the session",
    )
    user_agent = models.TextField(
        default="",
        blank=True,
        help_text="User agent string from the browser",
    )
    login_time = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when the session was created",
    )
    last_activity = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp of the last activity in this session",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether the session is currently active",
    )
    logout_time = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when the session was terminated",
    )

    class Meta:
        db_table = "user_sessions"
        verbose_name = "User Session"
        verbose_name_plural = "User Sessions"
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["session_key"]),
            models.Index(fields=["ip_address"]),
            models.Index(fields=["login_time"]),
        ]
        ordering = ["-login_time"]

    def __str__(self) -> str:
        return f"Session for {self.user.email} from {self.ip_address}"

    def terminate(self) -> None:
        """Terminate the session."""
        self.is_active = False
        self.logout_time = timezone.now()
        self.save(update_fields=["is_active", "logout_time"])

    def is_expired(self, expiry_hours: int = 24) -> bool:
        """Check if the session has expired."""
        if not self.is_active:
            return True
        expiry_time = self.login_time + timedelta(hours=expiry_hours)
        return timezone.now() > expiry_time


class BlockedIP(models.Model):
    """IP address blocking for security."""

    ip_address = models.GenericIPAddressField(
        unique=True,
        db_index=True,
        help_text="Blocked IP address",
    )
    reason = models.CharField(
        max_length=255,
        help_text="Reason for blocking",
    )
    failed_attempts = models.IntegerField(
        default=0,
        help_text="Number of failed login attempts from this IP",
    )
    blocked_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when the IP was blocked",
    )
    blocked_until = models.DateTimeField(
        help_text="Timestamp when the block expires",
    )
    is_permanent = models.BooleanField(
        default=False,
        help_text="Whether the block is permanent",
    )
    created_by = models.ForeignKey(
        "User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="blocked_ips",
        help_text="Admin user who created the block (if manual)",
    )

    class Meta:
        db_table = "blocked_ips"
        verbose_name = "Blocked IP"
        verbose_name_plural = "Blocked IPs"
        indexes = [
            models.Index(fields=["ip_address"]),
            models.Index(fields=["blocked_until"]),
            models.Index(fields=["is_permanent"]),
        ]
        ordering = ["-blocked_at"]

    def __str__(self) -> str:
        return f"Blocked IP: {self.ip_address}"

    def is_active(self) -> bool:
        """Check if the block is still active."""
        if self.is_permanent:
            return True
        return timezone.now() < self.blocked_until

    def unblock(self) -> None:
        """Remove the block by setting expiry to now."""
        if not self.is_permanent:
            self.blocked_until = timezone.now()
            self.save(update_fields=["blocked_until"])


class AccountSecurityEvent(models.Model):
    """Persisted security/auth events owned by the accounts app."""

    SEVERITY_CHOICES = [
        ("debug", "Debug"),
        ("info", "Info"),
        ("warning", "Warning"),
        ("error", "Error"),
        ("critical", "Critical"),
    ]

    event_type = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Type of event (e.g., login_success, login_failed, logout)",
    )
    category = models.CharField(
        max_length=50,
        default="security",
        db_index=True,
        help_text="Event category; defaults to 'security' for auth/security events",
    )
    severity = models.CharField(
        max_length=20,
        choices=SEVERITY_CHOICES,
        default="info",
        db_index=True,
        help_text="Severity level",
    )
    description = models.TextField(
        help_text="Human-readable event description",
    )
    user = models.ForeignKey(
        "User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="security_events",
        help_text="Associated user (if known)",
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address associated with the event",
    )
    user_agent = models.TextField(
        default="",
        blank=True,
        help_text="User agent string (if available)",
    )
    details = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional structured event details",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Timestamp when the event was created",
    )

    class Meta:
        db_table = "account_security_events"
        verbose_name = "Account Security Event"
        verbose_name_plural = "Account Security Events"
        indexes = [
            models.Index(fields=["event_type", "created_at"]),
            models.Index(fields=["category", "created_at"]),
            models.Index(fields=["severity", "created_at"]),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        base = f"{self.event_type} ({self.severity})"
        if self.user_id:  # type: ignore[attr-defined]
            return f"{base} user={self.user_id}"  # type: ignore[attr-defined]
        return base
