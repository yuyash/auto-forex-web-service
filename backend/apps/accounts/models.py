"""
User authentication and management models.

This module contains models for:
- User: Extended Django user model with additional fields
- UserSettings: User preferences and notification settings
- UserSession: Session tracking for security monitoring
- BlockedIP: IP blocking for security
- OandaAccount: OANDA trading account with encrypted API token
"""

from datetime import timedelta
from typing import Any

from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

# Username validator: alphanumeric, underscore, period, dash only
username_validator = RegexValidator(
    regex=r"^[a-zA-Z0-9._-]+$",
    message="Username can only contain letters, numbers, underscores, periods, and dashes.",
    code="invalid_username",
)


class WhitelistedEmail(models.Model):
    """
    Email whitelist for registration and login control.

    This model stores email addresses or domains that are allowed to register
    and login to the system when email whitelist is enabled.

    Supports both exact email matches (user@example.com) and domain wildcards
    (*@example.com or @example.com).
    """

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
        """
        Check if an email address is whitelisted.

        Supports exact matches and domain wildcards:
        - Exact: user@example.com matches user@example.com
        - Domain: *@example.com or @example.com matches any@example.com

        Args:
            email: Email address to check

        Returns:
            True if email is whitelisted, False otherwise
        """
        email_lower = email.lower().strip()

        # Check for exact match
        if cls.objects.filter(email_pattern__iexact=email_lower, is_active=True).exists():
            return True

        # Extract domain from email
        if "@" not in email_lower:
            return False

        domain = email_lower.split("@")[1]

        # Check for domain wildcards (*@domain.com or @domain.com)
        domain_patterns = [f"*@{domain}", f"@{domain}"]
        if cls.objects.filter(
            email_pattern__in=domain_patterns,
            is_active=True,
        ).exists():
            return True

        return False


class User(AbstractUser):
    """
    Extended Django user model with additional fields for the trading system.
    """

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
        null=True,
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

    # Override username to make it optional (we use email for login)
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
        """
        Generate a unique email verification token.

        Returns:
            Verification token string
        """
        import secrets

        token = secrets.token_urlsafe(32)
        self.email_verification_token = token
        self.email_verification_sent_at = timezone.now()
        self.save(update_fields=["email_verification_token", "email_verification_sent_at"])
        return token

    def verify_email(self, token: str) -> bool:
        """
        Verify email with the provided token.

        Args:
            token: Verification token to check

        Returns:
            True if verification successful, False otherwise
        """
        if not self.email_verification_token:
            return False

        if self.email_verification_token != token:
            return False

        # Check if token is expired (24 hours)
        if self.email_verification_sent_at:
            expiry_time = self.email_verification_sent_at + timedelta(hours=24)
            if timezone.now() > expiry_time:
                return False

        # Mark email as verified
        self.email_verified = True
        self.email_verification_token = None
        self.email_verification_sent_at = None
        self.save(
            update_fields=[
                "email_verified",
                "email_verification_token",
                "email_verification_sent_at",
            ]
        )
        return True


class UserSettings(models.Model):
    """
    User preferences and notification settings.
    """

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="settings",
        help_text="User associated with these settings",
    )
    notification_enabled = models.BooleanField(
        default=True,
        help_text="Whether notifications are enabled",
    )
    notification_email = models.BooleanField(
        default=True,
        help_text="Whether to send email notifications",
    )
    notification_browser = models.BooleanField(
        default=True,
        help_text="Whether to send browser notifications",
    )
    settings_json = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional settings stored as JSON",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when settings were created",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when settings were last updated",
    )

    class Meta:
        db_table = "user_settings"
        verbose_name = "User Settings"
        verbose_name_plural = "User Settings"

    def __str__(self) -> str:
        return f"Settings for {self.user.email}"


class UserSession(models.Model):
    """
    User session tracking for security monitoring.
    """

    user = models.ForeignKey(
        User,
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
    """
    IP address blocking for security.
    """

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
        User,
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


class PublicAccountSettings(models.Model):
    """
    Public account settings for the application.

    This is a singleton model - only one instance should exist.
    Use get_settings() class method to retrieve the settings.

    Contains authentication-related settings that control user access.
    """

    # Authentication settings
    registration_enabled = models.BooleanField(
        default=True,
        help_text="Whether new user registration is enabled",
    )
    login_enabled = models.BooleanField(
        default=True,
        help_text="Whether user login is enabled",
    )
    email_whitelist_enabled = models.BooleanField(
        default=False,
        help_text="Whether email whitelist is enforced for registration/login",
    )

    # Timestamps
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when settings were last updated",
    )

    class Meta:
        db_table = "public_account_settings"
        verbose_name = "Public Account Settings"
        verbose_name_plural = "Public Account Settings"

    def __str__(self) -> str:
        return (
            f"Public Account Settings (Registration: {self.registration_enabled}, "
            f"Login: {self.login_enabled}, "
            f"Email Whitelist: {self.email_whitelist_enabled})"
        )

    @classmethod
    def get_settings(cls) -> "PublicAccountSettings":
        """
        Get or create the singleton PublicAccountSettings instance.

        Returns:
            PublicAccountSettings: The public account settings instance
        """
        settings, _ = cls.objects.get_or_create(pk=1)
        return settings

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Override save to ensure only one instance exists."""
        self.pk = 1
        super().save(*args, **kwargs)
