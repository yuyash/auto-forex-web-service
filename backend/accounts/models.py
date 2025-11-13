"""
User authentication and management models.

This module contains models for:
- User: Extended Django user model with additional fields
- UserSettings: User preferences and strategy defaults
- UserSession: Session tracking for security monitoring
- BlockedIP: IP blocking for security
- OandaAccount: OANDA trading account with encrypted API token
"""

# pylint: disable=too-many-lines

import base64
import hashlib
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

from cryptography.fernet import Fernet


class SystemSettings(models.Model):
    """
    System-wide settings (singleton pattern).

    This model stores global system settings that affect all users.
    Only one instance should exist in the database.

    Requirements: 1.1, 2.1, 19.5, 28.5
    """

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
        help_text="Whether email whitelist is enforced for registration and login",
    )

    # Debug Settings
    debug_mode = models.BooleanField(
        default=False,
        help_text="Enable debug mode (should be False in production)",
    )

    # Email Settings - SMTP
    email_backend_type = models.CharField(
        max_length=10,
        choices=[("smtp", "SMTP"), ("ses", "AWS SES")],
        default="smtp",
        help_text="Type of email backend to use",
    )
    email_host = models.CharField(
        max_length=255,
        default="smtp.gmail.com",
        help_text="SMTP server hostname",
    )
    email_port = models.IntegerField(
        default=587,
        help_text="SMTP server port",
    )
    email_use_tls = models.BooleanField(
        default=True,
        help_text="Enable TLS for email connection",
    )
    email_use_ssl = models.BooleanField(
        default=False,
        help_text="Enable SSL for email connection",
    )
    email_host_user = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="SMTP authentication username",
    )
    email_host_password = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="SMTP authentication password",
    )
    default_from_email = models.EmailField(
        default="noreply@example.com",
        help_text="Default sender email address",
    )

    # AWS Settings
    aws_credential_method = models.CharField(
        max_length=20,
        choices=[
            ("profile", "AWS Profile"),
            ("profile_role", "AWS Profile + Assume Role"),
            ("credentials_file", "Credentials File"),
            ("access_keys", "Access Key ID + Secret"),
        ],
        default="profile",
        help_text="Method for AWS authentication",
    )
    aws_profile_name = models.CharField(
        max_length=255,
        blank=True,
        default="default",
        help_text="AWS profile name (for profile and profile_role methods)",
    )
    aws_role_arn = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="AWS role ARN to assume (for profile_role method)",
    )
    aws_credentials_file_path = models.CharField(
        max_length=500,
        blank=True,
        default="",
        help_text="Path to AWS credentials file (for credentials_file method)",
    )
    aws_access_key_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="AWS access key ID (for access_keys method)",
    )
    aws_secret_access_key = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="AWS secret access key (for access_keys method)",
    )
    aws_ses_region = models.CharField(
        max_length=50,
        default="us-east-1",
        help_text="AWS SES region (if using SES for email)",
    )
    aws_region = models.CharField(
        max_length=50,
        default="us-east-1",
        help_text="Default AWS region",
    )
    # Athena Settings for Historical Data
    athena_database_name = models.CharField(
        max_length=255,
        blank=True,
        default="forex_hist_data_db",
        help_text="Athena database name for historical forex data",
    )
    athena_table_name = models.CharField(
        max_length=255,
        blank=True,
        default="quotes",
        help_text="Athena table name for historical forex quotes",
    )
    athena_output_bucket = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="S3 bucket for Athena query results (e.g., my-athena-results)",
    )
    athena_instruments = models.TextField(
        blank=True,
        default="EUR_USD,GBP_USD,USD_JPY,USD_CHF,AUD_USD,USD_CAD,NZD_USD",
        help_text=(
            "Comma-separated list of instruments to import from Athena " "(e.g., EUR_USD,GBP_USD)"
        ),
    )

    # Logging Settings
    django_log_level = models.CharField(
        max_length=20,
        choices=[
            ("DEBUG", "Debug"),
            ("INFO", "Info"),
            ("WARNING", "Warning"),
            ("ERROR", "Error"),
            ("CRITICAL", "Critical"),
        ],
        default="INFO",
        help_text="Logging level for Django",
    )

    # Application Settings
    tick_data_retention_days = models.IntegerField(
        default=90,
        help_text="Number of days to retain tick data before cleanup",
    )
    oanda_sync_interval_seconds = models.IntegerField(
        default=300,
        help_text=(
            "Interval in seconds for OANDA account synchronization " "(default: 300 = 5 minutes)"
        ),
    )
    oanda_fetch_duration_days = models.IntegerField(
        default=365,
        help_text="Number of days to fetch orders and positions from OANDA (default: 365 = 1 year)",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when settings were last updated",
    )
    updated_by = models.ForeignKey(
        "User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="system_settings_updates",
        help_text="Admin user who last updated the settings",
    )

    class Meta:
        db_table = "system_settings"
        verbose_name = "System Settings"
        verbose_name_plural = "System Settings"

    def __str__(self) -> str:
        return (
            f"System Settings (Registration: {self.registration_enabled}, "
            f"Login: {self.login_enabled}, "
            f"Email Whitelist: {self.email_whitelist_enabled})"
        )

    def save(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        """
        Override save to enforce singleton pattern.
        Only one SystemSettings instance should exist.

        Also triggers container restart if debug_mode or django_log_level changes.
        """
        import logging
        import os
        import subprocess  # nosec B404 - subprocess used for controlled container restart only

        logger = logging.getLogger(__name__)

        # Check if this is an update (not initial creation)
        restart_required = False
        if self.pk:
            try:
                old_instance = SystemSettings.objects.get(pk=1)
                # Check if debug_mode or django_log_level changed
                if (
                    old_instance.debug_mode != self.debug_mode
                    or old_instance.django_log_level != self.django_log_level
                ):
                    restart_required = True
                    logger.info(
                        "Settings change detected - Debug: %s->%s, Log Level: %s->%s",
                        old_instance.debug_mode,
                        self.debug_mode,
                        old_instance.django_log_level,
                        self.django_log_level,
                    )
            except SystemSettings.DoesNotExist:
                pass

        self.pk = 1
        super().save(*args, **kwargs)

        # Trigger restart if needed
        if restart_required:
            logger.warning("Debug mode or log level changed. Container restart recommended.")
            # Try to restart container automatically
            script_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "scripts", "restart_container.sh"
            )
            if os.path.exists(script_path):
                try:
                    # pylint: disable=consider-using-with
                    # Script path is controlled and validated, not user input
                    process = subprocess.Popen(  # nosec B603
                        [script_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                    )
                    # Don't wait for process to complete (background execution)
                    process.poll()
                    logger.info("Container restart initiated")
                except Exception as e:  # pylint: disable=broad-exception-caught
                    logger.error("Failed to initiate container restart: %s", e)

    @classmethod
    def get_settings(cls) -> "SystemSettings":
        """
        Get the singleton SystemSettings instance.
        Creates one with defaults if it doesn't exist.

        Returns:
            SystemSettings instance
        """
        obj, _ = cls.objects.get_or_create(
            pk=1,
            defaults={
                "registration_enabled": True,
                "login_enabled": True,
                "email_whitelist_enabled": False,
            },
        )
        return obj


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

    Requirements: 1.1, 1.2, 2.1, 2.2, 17.1, 17.2, 30.1, 31.1, 34.1, 34.2
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

    Requirements: 4.1, 4.2, 4.4, 4.5, 8.1, 8.2
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
    jurisdiction = models.CharField(
        max_length=10,
        choices=[
            ("US", "United States"),
            ("JP", "Japan"),
            ("EU", "European Union"),
            ("UK", "United Kingdom"),
            ("AU", "Australia"),
            ("OTHER", "Other/International"),
        ],
        default="OTHER",
        help_text="Regulatory jurisdiction for this account",
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
    enable_position_differentiation = models.BooleanField(
        default=False,
        help_text="Enable automatic position differentiation for FIFO flexibility",
    )
    position_diff_increment = models.IntegerField(
        default=1,
        help_text="Increment amount for position differentiation (1-100 units)",
    )
    position_diff_pattern = models.CharField(
        max_length=20,
        default="increment",
        choices=[
            ("increment", "Increment"),
            ("decrement", "Decrement"),
            ("alternating", "Alternating"),
        ],
        help_text="Pattern for position differentiation",
    )
    is_default = models.BooleanField(
        default=False,
        help_text="Whether this is the default account for market data collection",
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
            models.Index(fields=["user", "is_default"]),
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
            OANDA API hostname (without protocol, as required by v20 library)
        """
        if self.api_type == "live":
            hostname = settings.OANDA_LIVE_API
        else:
            hostname = settings.OANDA_PRACTICE_API

        # Strip protocol if present (v20 library expects hostname only)
        return hostname.replace("https://", "").replace("http://", "")

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

    def set_as_default(self) -> None:
        """
        Set this account as the default account for the user.
        Automatically unsets any other default account for the same user.
        """
        # Unset any existing default account for this user
        OandaAccount.objects.filter(user=self.user, is_default=True).exclude(id=self.id).update(
            is_default=False
        )
        # Set this account as default
        self.is_default = True
        self.save(update_fields=["is_default", "updated_at"])
