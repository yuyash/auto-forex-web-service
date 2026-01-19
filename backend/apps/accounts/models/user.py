"""User model and related models."""

from datetime import timedelta

from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

username_validator = RegexValidator(
    regex=r"^[a-zA-Z0-9._-]+$",
    message="Username can only contain letters, numbers, underscores, periods, and dashes.",
    code="invalid_username",
)


class WhitelistedEmail(models.Model):
    """Email whitelist for registration and login control."""

    email_pattern = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="Email address or domain pattern (e.g., user@example.com or *@example.com)",
    )
    description = models.CharField(
        max_length=255,
        blank=True,
        help_text="Optional description for this whitelist entry",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this whitelist entry is active",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when the entry was created",
    )
    created_by = models.ForeignKey(
        "User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="whitelisted_emails_created",
        help_text="Admin user who created this entry",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when the entry was last updated",
    )

    class Meta:
        db_table = "whitelisted_emails"
        verbose_name = "Whitelisted Email"
        verbose_name_plural = "Whitelisted Emails"
        indexes = [
            models.Index(fields=["email_pattern"]),
            models.Index(fields=["is_active"]),
        ]
        ordering = ["email_pattern"]

    def __str__(self) -> str:
        return f"{self.email_pattern} ({'Active' if self.is_active else 'Inactive'})"

    @classmethod
    def is_email_whitelisted(cls, email: str) -> bool:
        """Check if an email address is whitelisted."""
        email_lower = email.lower().strip()

        if cls.objects.filter(email_pattern__iexact=email_lower, is_active=True).exists():
            return True

        if "@" not in email_lower:
            return False

        domain = email_lower.split("@")[1]
        domain_patterns = [f"*@{domain}", f"@{domain}"]
        return cls.objects.filter(
            email_pattern__in=domain_patterns,
            is_active=True,
        ).exists()


class User(AbstractUser):
    """Extended Django user model with additional fields for the trading system."""

    email = models.EmailField(
        unique=True,
        db_index=True,
        help_text="User's email address (used for login)",
    )
    email_verified = models.BooleanField(
        default=False,
        help_text="Whether the user's email address has been verified",
    )
    email_verification_token = models.CharField(
        max_length=100,
        default="",
        blank=True,
        help_text="Token for email verification",
    )
    email_verification_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when verification email was last sent",
    )
    timezone = models.CharField(
        max_length=50,
        default="UTC",
        help_text="User's preferred timezone (IANA timezone identifier)",
    )
    language = models.CharField(
        max_length=5,
        default="en",
        choices=[("en", "English"), ("ja", "Japanese")],
        help_text="User's preferred language",
    )
    is_locked = models.BooleanField(
        default=False,
        help_text="Whether the account is locked due to failed login attempts",
    )
    failed_login_attempts = models.IntegerField(
        default=0,
        help_text="Number of consecutive failed login attempts",
    )
    last_login_attempt = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of the last login attempt",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when the user account was created",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when the user account was last updated",
    )

    username = models.CharField(
        max_length=150,
        unique=True,
        validators=[username_validator],
        help_text="Username (auto-generated from email if not provided)",
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        db_table = "users"
        verbose_name = "User"
        verbose_name_plural = "Users"
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["is_locked"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.email} ({self.username})"

    def increment_failed_login(self) -> None:
        """Increment failed login attempts counter."""
        self.failed_login_attempts += 1
        self.last_login_attempt = timezone.now()
        self.save(update_fields=["failed_login_attempts", "last_login_attempt"])

    def reset_failed_login(self) -> None:
        """Reset failed login attempts counter."""
        self.failed_login_attempts = 0
        self.last_login_attempt = None
        self.save(update_fields=["failed_login_attempts", "last_login_attempt"])

    def lock_account(self) -> None:
        """Lock the user account."""
        self.is_locked = True
        self.save(update_fields=["is_locked"])

    def unlock_account(self) -> None:
        """Unlock the user account."""
        self.is_locked = False
        self.failed_login_attempts = 0
        self.save(update_fields=["is_locked", "failed_login_attempts"])

    def generate_verification_token(self) -> str:
        """Generate a unique email verification token."""
        import secrets

        token = secrets.token_urlsafe(32)
        self.email_verification_token = token
        self.email_verification_sent_at = timezone.now()
        self.save(update_fields=["email_verification_token", "email_verification_sent_at"])
        return token

    def verify_email(self, token: str) -> bool:
        """Verify email with the provided token."""
        if not self.email_verification_token:
            return False

        if self.email_verification_token != token:
            return False

        if self.email_verification_sent_at:
            expiry_time = self.email_verification_sent_at + timedelta(hours=24)
            if timezone.now() > expiry_time:
                return False

        self.email_verified = True
        self.email_verification_token = ""
        self.email_verification_sent_at = None
        self.save(
            update_fields=[
                "email_verified",
                "email_verification_token",
                "email_verification_sent_at",
            ]
        )
        return True


class UserNotification(models.Model):
    """Notification targeted to a specific user."""

    SEVERITY_CHOICES = [
        ("info", "Info"),
        ("warning", "Warning"),
        ("error", "Error"),
        ("critical", "Critical"),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notifications",
        help_text="User who should receive this notification",
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Timestamp when the notification was created",
    )
    notification_type = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Type of notification (e.g., 'trade_closed', 'account_alert')",
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
    extra_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Optional additional notification payload",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when the notification was created",
    )

    class Meta:
        db_table = "user_notifications"
        verbose_name = "User Notification"
        verbose_name_plural = "User Notifications"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["user", "timestamp"]),
            models.Index(fields=["user", "is_read", "timestamp"]),
            models.Index(fields=["notification_type", "timestamp"]),
        ]

    def __str__(self) -> str:
        status = "Read" if self.is_read else "Unread"
        return f"{self.user_id}: [{self.severity.upper()}] {self.title} - {status}"  # type: ignore[attr-defined]

    def mark_as_read(self) -> None:
        """Mark notification as read."""
        self.is_read = True
        self.save(update_fields=["is_read"])

    def mark_as_unread(self) -> None:
        """Mark notification as unread."""
        self.is_read = False
        self.save(update_fields=["is_read"])
