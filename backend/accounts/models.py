"""
User authentication and management models.

This module contains models for:
- User: Extended Django user model with additional fields
- UserSettings: User preferences and strategy defaults
- UserSession: Session tracking for security monitoring
- BlockedIP: IP blocking for security
- OandaAccount: OANDA trading account with encrypted API token
"""

import base64
import hashlib
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

from cryptography.fernet import Fernet


class User(AbstractUser):
    """
    Extended Django user model with additional fields for the trading system.

    Requirements: 1.1, 1.2, 2.1, 2.2, 17.1, 17.2, 30.1, 31.1, 34.1, 34.2
    """

    email = models.EmailField(
        unique=True,
        db_index=True,
        help_text="User's email address (used for login)",
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


class UserSettings(models.Model):
    """
    User preferences and strategy defaults.

    Requirements: 17.1, 17.2, 29.1, 29.2, 29.3, 29.4
    """

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="settings",
        help_text="User associated with these settings",
    )
    default_lot_size = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=1.0,
        help_text="Default lot size for new positions",
    )
    default_scaling_mode = models.CharField(
        max_length=20,
        default="additive",
        choices=[
            ("additive", "Additive"),
            ("multiplicative", "Multiplicative"),
        ],
        help_text="Default scaling mode for strategies",
    )
    default_retracement_pips = models.IntegerField(
        default=30,
        help_text="Default retracement distance in pips",
    )
    default_take_profit_pips = models.IntegerField(
        default=25,
        help_text="Default take-profit distance in pips",
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

    Requirements: 20.1, 20.2, 20.3, 20.4, 34.1, 34.2
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

    Requirements: 34.1, 34.2, 34.3, 34.4, 34.5
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


class OandaAccount(models.Model):
    """
    OANDA trading account with encrypted API token.

    Requirements: 4.1, 4.2, 4.4, 4.5
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="oanda_accounts",
        help_text="User who owns this OANDA account",
    )
    account_id = models.CharField(
        max_length=100,
        help_text="OANDA account ID",
    )
    api_token = models.CharField(
        max_length=500,
        help_text="Encrypted OANDA API token",
    )
    api_type = models.CharField(
        max_length=10,
        choices=[
            ("practice", "Practice"),
            ("live", "Live"),
        ],
        default="practice",
        help_text="API endpoint type (practice or live)",
    )
    currency = models.CharField(
        max_length=3,
        default="USD",
        help_text="Account base currency",
    )
    balance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        help_text="Current account balance",
    )
    margin_used = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        help_text="Margin currently used by open positions",
    )
    margin_available = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        help_text="Margin available for new positions",
    )
    unrealized_pnl = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        help_text="Unrealized profit/loss from open positions",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether the account is active",
    )
    status = models.CharField(
        max_length=20,
        default="idle",
        choices=[
            ("idle", "Idle"),
            ("trading", "Trading"),
            ("paused", "Paused"),
            ("error", "Error"),
        ],
        help_text="Current account status",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when the account was added",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when the account was last updated",
    )

    class Meta:
        db_table = "oanda_accounts"
        verbose_name = "OANDA Account"
        verbose_name_plural = "OANDA Accounts"
        unique_together = [["user", "account_id"]]
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["account_id"]),
            models.Index(fields=["created_at"]),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.user.email} - {self.account_id} ({self.api_type})"

    @staticmethod
    def _get_cipher() -> Fernet:
        """
        Get Fernet cipher for encryption/decryption.
        Uses Django SECRET_KEY to derive encryption key.
        """
        # Derive a 32-byte key from Django's SECRET_KEY
        key = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
        # Fernet requires base64-encoded key
        fernet_key = base64.urlsafe_b64encode(key)
        return Fernet(fernet_key)

    def set_api_token(self, token: str) -> None:
        """
        Encrypt and store the API token.

        Args:
            token: Plain text API token
        """
        cipher = self._get_cipher()
        encrypted_token = cipher.encrypt(token.encode())
        self.api_token = encrypted_token.decode()

    def get_api_token(self) -> str:
        """
        Decrypt and return the API token.

        Returns:
            Plain text API token
        """
        cipher = self._get_cipher()
        decrypted_token = cipher.decrypt(self.api_token.encode())
        return decrypted_token.decode()

    @property
    def api_hostname(self) -> str:
        """
        Get the OANDA API hostname based on api_type.

        Returns:
            OANDA API hostname URL
        """
        if self.api_type == "live":
            return settings.OANDA_LIVE_API
        return settings.OANDA_PRACTICE_API

    def update_balance(
        self,
        balance: float,
        margin_used: float,
        margin_available: float,
        unrealized_pnl: float,
    ) -> None:
        """
        Update account balance and margin information.

        Args:
            balance: Current account balance
            margin_used: Margin used by open positions
            margin_available: Margin available for new positions
            unrealized_pnl: Unrealized profit/loss
        """
        self.balance = balance
        self.margin_used = margin_used
        self.margin_available = margin_available
        self.unrealized_pnl = unrealized_pnl
        self.save(
            update_fields=[
                "balance",
                "margin_used",
                "margin_available",
                "unrealized_pnl",
                "updated_at",
            ]
        )

    def set_status(self, status: str) -> None:
        """
        Update account status.

        Args:
            status: New status (idle, trading, paused, error)
        """
        if status in ["idle", "trading", "paused", "error"]:
            self.status = status
            self.save(update_fields=["status", "updated_at"])

    def activate(self) -> None:
        """Activate the account."""
        self.is_active = True
        self.save(update_fields=["is_active", "updated_at"])

    def deactivate(self) -> None:
        """Deactivate the account."""
        self.is_active = False
        self.status = "idle"
        self.save(update_fields=["is_active", "status", "updated_at"])
