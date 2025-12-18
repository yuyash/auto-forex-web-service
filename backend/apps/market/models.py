"""
Market data models for storing OANDA accounts and tick data.

This module contains models for:
- OandaAccount: OANDA trading account with encrypted API token
- TickData: Historical tick data for backtesting and analysis
- MarketEvent: Persistent event log for market-related events
"""

import base64
import hashlib
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from cryptography.fernet import Fernet

from .enums import ApiType, Jurisdiction


class OandaAccount(models.Model):
    """
    OANDA trading account with encrypted API token.
    """

    user = models.ForeignKey(
        "accounts.User",
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
        max_length=20,
        choices=ApiType.choices,
        default=ApiType.PRACTICE,
        help_text="API endpoint type (practice or live)",
    )
    jurisdiction = models.CharField(
        max_length=10,
        choices=Jurisdiction.choices,
        default=Jurisdiction.OTHER,
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
    is_default = models.BooleanField(
        default=False,
        help_text="Whether this is the default account for market data collection",
    )
    is_used = models.BooleanField(
        default=False,
        help_text="Whether this account is currently used by any running process",
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
        key = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
        fernet_key = base64.urlsafe_b64encode(key)
        return Fernet(fernet_key)

    def set_api_token(self, token: str) -> None:
        cipher = self._get_cipher()
        encrypted_token = cipher.encrypt(token.encode())
        self.api_token = encrypted_token.decode()

    def get_api_token(self) -> str:
        cipher = self._get_cipher()
        decrypted_token = cipher.decrypt(self.api_token.encode())
        return decrypted_token.decode()

    @property
    def api_hostname(self) -> str:
        if self.api_type == "live":
            hostname = settings.OANDA_LIVE_API
        else:
            hostname = settings.OANDA_PRACTICE_API
        return hostname.replace("https://", "").replace("http://", "")

    def update_balance(
        self, balance: float, margin_used: float, margin_available: float, unrealized_pnl: float
    ) -> None:
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

    def activate(self) -> None:
        self.is_active = True
        self.save(update_fields=["is_active", "updated_at"])

    def deactivate(self) -> None:
        self.is_active = False
        self.save(update_fields=["is_active", "updated_at"])

    def set_as_default(self) -> None:
        OandaAccount.objects.filter(user=self.user, is_default=True).exclude(id=self.pk).update(
            is_default=False
        )
        self.is_default = True
        self.save(update_fields=["is_default", "updated_at"])


class TickData(models.Model):
    """
    Historical tick data for market analysis and backtesting.

    Stores bid, ask, and mid prices for each instrument at specific timestamps.
    Includes data retention policy for automatic cleanup of old data.
    """

    instrument = models.CharField(
        max_length=10,
        db_index=True,
        help_text="Currency pair (e.g., 'EUR_USD')",
    )
    timestamp = models.DateTimeField(
        db_index=True,
        help_text="Timestamp when the tick was received",
    )
    bid = models.DecimalField(
        max_digits=10,
        decimal_places=5,
        help_text="Bid price",
    )
    ask = models.DecimalField(
        max_digits=10,
        decimal_places=5,
        help_text="Ask price",
    )
    mid = models.DecimalField(
        max_digits=10,
        decimal_places=5,
        help_text="Mid price (average of bid and ask)",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when the record was created",
    )

    class Meta:
        db_table = "tick_data"
        verbose_name = "Tick Data"
        verbose_name_plural = "Tick Data"
        indexes = [
            # Single field indexes for basic queries
            models.Index(fields=["instrument"]),
            models.Index(fields=["timestamp"]),
            # Composite index for efficient backtesting queries
            models.Index(fields=["instrument", "timestamp"]),
            # Index for data retention cleanup
            models.Index(fields=["created_at"]),
        ]
        ordering = ["-timestamp"]

    def __str__(self) -> str:
        return f"{self.instrument} @ {self.timestamp} - Bid: {self.bid}, Ask: {self.ask}"

    @property
    def spread(self) -> Decimal:
        # Keep this simple for runtime correctness and static analysis.
        return Decimal(self.ask) - Decimal(self.bid)

    @classmethod
    def get_retention_days(cls) -> int:
        """
        Get the data retention period in days from settings.

        Returns:
            Number of days to retain tick data (default: 90)
        """
        return getattr(settings, "TICK_DATA_RETENTION_DAYS", 90)

    @classmethod
    def cleanup_old_data(cls, retention_days: int | None = None) -> int:
        """
        Delete tick data older than the retention period.

        Args:
            retention_days: Number of days to retain (uses default if None)

        Returns:
            Number of records deleted
        """
        if retention_days is None:
            retention_days = cls.get_retention_days()

        cutoff_date = timezone.now() - timedelta(days=retention_days)
        deleted_count, _ = cls.objects.filter(created_at__lt=cutoff_date).delete()
        return deleted_count

    @staticmethod
    def calculate_mid(bid: Decimal, ask: Decimal) -> Decimal:
        """
        Calculate mid price from bid and ask.

        Args:
            bid: Bid price
            ask: Ask price

        Returns:
            Mid price (average of bid and ask)
        """
        return (bid + ask) / Decimal("2")

    @staticmethod
    def calculate_spread(bid: Decimal, ask: Decimal) -> Decimal:
        """
        Calculate spread from bid and ask.

        Args:
            bid: Bid price
            ask: Ask price

        Returns:
            Spread (difference between ask and bid)
        """
        return ask - bid

    def save(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        """
        Override save to automatically calculate mid if not provided.
        """
        # Calculate mid price if not provided
        current_mid = getattr(self, "mid", None)
        if current_mid is None or current_mid == 0:
            self.mid = self.calculate_mid(self.bid, self.ask)

        super().save(*args, **kwargs)


class MarketEvent(models.Model):
    """Persistent event log for the market app.

    This is intentionally independent from any trading/accounts event mechanisms.
    """

    event_type = models.CharField(max_length=64, db_index=True)
    category = models.CharField(max_length=32, default="market", db_index=True)
    severity = models.CharField(max_length=16, default="info", db_index=True)
    description = models.TextField()

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="market_events",
    )
    account = models.ForeignKey(
        "market.OandaAccount",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="market_events",
    )
    instrument = models.CharField(max_length=32, null=True, blank=True, db_index=True)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "market_events"
        verbose_name = "Market Event"
        verbose_name_plural = "Market Events"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.created_at.isoformat()} [{self.category}/{self.severity}] {self.event_type}"


class CeleryTaskStatus(models.Model):
    """Track a Celery task instance managed by the market app.

    Long-running tasks should heartbeat and periodically check status to support
    clean shutdowns (e.g., when a cancellation signal is received).
    """

    class Status(models.TextChoices):
        RUNNING = "running", "Running"
        STOP_REQUESTED = "stop_requested", "Stop Requested"
        STOPPED = "stopped", "Stopped"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    # Celery task name (e.g. "market.tasks.subscribe_ticks_to_db")
    task_name = models.CharField(max_length=200, db_index=True)

    # Instance key differentiates multiple runs/instances of the same task.
    # Example: backtest publisher uses request_id; subscriber might use "default".
    instance_key = models.CharField(
        max_length=200,
        blank=True,
        default="default",
        db_index=True,
    )

    celery_task_id = models.CharField(max_length=200, null=True, blank=True, db_index=True)
    worker = models.CharField(max_length=200, null=True, blank=True)

    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.RUNNING,
        db_index=True,
    )

    status_message = models.TextField(null=True, blank=True)
    meta = models.JSONField(default=dict, blank=True)

    started_at = models.DateTimeField(null=True, blank=True)
    last_heartbeat_at = models.DateTimeField(null=True, blank=True)
    stopped_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "market_celery_tasks"
        verbose_name = "Celery Task Status"
        verbose_name_plural = "Celery Task Statuses"
        constraints = [
            models.UniqueConstraint(
                fields=["task_name", "instance_key"],
                name="uniq_market_task_name_instance_key",
            )
        ]
        indexes = [
            models.Index(
                fields=["task_name", "status"],
                name="market_mana_task_na_57e1fc_idx",
            ),
            models.Index(fields=["celery_task_id"], name="market_mana_celery__e5025a_idx"),
            models.Index(fields=["last_heartbeat_at"], name="market_mana_last_he_d7d6f2_idx"),
        ]

    def __str__(self) -> str:
        key = self.instance_key or "default"
        return f"{self.task_name} ({key}) [{self.status}]"


class OandaApiHealthStatus(models.Model):
    """Persisted OANDA API health check results."""

    account = models.ForeignKey(
        "market.OandaAccount",
        on_delete=models.CASCADE,
        related_name="api_health_statuses",
    )

    is_available = models.BooleanField(default=False, db_index=True)
    checked_at = models.DateTimeField(default=timezone.now, db_index=True)
    latency_ms = models.IntegerField(null=True, blank=True)
    http_status = models.IntegerField(null=True, blank=True)
    error_message = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "oanda_api_health_statuses"
        verbose_name = "OANDA API Health Status"
        verbose_name_plural = "OANDA API Health Statuses"
        ordering = ["-checked_at"]
        indexes = [
            models.Index(fields=["account", "checked_at"]),
            models.Index(fields=["account", "is_available", "checked_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.account.account_id} [{self.http_status}] available={self.is_available}"
