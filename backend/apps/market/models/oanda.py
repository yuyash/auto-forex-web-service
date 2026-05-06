"""OANDA account model."""

from collections.abc import Collection, Iterable
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models

from apps.market.enums import ApiType, Jurisdiction
from apps.market.services.cache import invalidate_market_metadata_cache


class OandaAccounts(models.Model):
    """
    OANDA trading account with encrypted API token.
    """

    class SnapshotRefreshStatus(models.TextChoices):
        IDLE = "idle", "Idle"
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

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
    nav = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        help_text="Latest cached net asset value from OANDA",
    )
    open_trade_count = models.PositiveIntegerField(
        default=0,
        help_text="Latest cached open trade count from OANDA",
    )
    open_position_count = models.PositiveIntegerField(
        default=0,
        help_text="Latest cached open position count from OANDA",
    )
    pending_order_count = models.PositiveIntegerField(
        default=0,
        help_text="Latest cached pending order count from OANDA",
    )
    hedging_enabled = models.BooleanField(
        null=True,
        blank=True,
        help_text="Latest cached OANDA hedging capability for this account",
    )
    snapshot_refreshed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when the cached OANDA account snapshot was refreshed",
    )
    snapshot_refresh_error = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Last safe error message from refreshing the OANDA account snapshot",
    )
    snapshot_refresh_task_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
        db_index=True,
        help_text="Latest manual OANDA account snapshot refresh Celery task ID",
    )
    snapshot_refresh_status = models.CharField(
        max_length=20,
        choices=SnapshotRefreshStatus.choices,
        default=SnapshotRefreshStatus.IDLE,
        db_index=True,
        help_text="Latest manual OANDA account snapshot refresh task status",
    )
    snapshot_refresh_status_updated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when the manual OANDA account snapshot refresh status changed",
    )
    live_max_exposure_guard_enabled = models.BooleanField(
        default=False,
        help_text=(
            "Whether to enforce the maximum estimated gross units check before starting "
            "non-dry-run trading tasks on this account"
        ),
    )
    live_max_estimated_exposure_units = models.PositiveIntegerField(
        default=200000,
        help_text=(
            "Account-specific maximum estimated gross units allowed when the live max exposure "
            "guard is enabled"
        ),
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
        unique_together = [["user", "account_id", "api_type"]]
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["account_id"]),
            models.Index(fields=["user", "is_default"]),
            models.Index(fields=["created_at"]),
            models.Index(
                fields=["user", "snapshot_refresh_status"],
                name="oanda_user_refresh_stat_idx",
            ),
            models.Index(
                fields=["user", "snapshot_refreshed_at"],
                name="oanda_user_snap_ref_idx",
            ),
        ]
        ordering = ["-created_at"]

    MARKET_METADATA_DEPENDENCY_FIELDS = frozenset(
        {"account_id", "api_type", "api_token", "is_active", "is_default", "user"}
    )

    def __str__(self) -> str:
        return f"{self.user.email} - {self.account_id} ({self.api_type})"

    @classmethod
    def _get_encryption_cipher(cls) -> Fernet:
        return Fernet(settings.OANDA_TOKEN_ENCRYPTION_KEY.encode("utf-8"))

    @classmethod
    def _get_decryption_ciphers(cls) -> Iterable[Fernet]:
        keys = [settings.OANDA_TOKEN_ENCRYPTION_KEY, *settings.OANDA_TOKEN_ENCRYPTION_FALLBACK_KEYS]
        for key in keys:
            yield Fernet(key.encode("utf-8"))

    def set_api_token(self, token: str) -> None:
        cipher = self._get_encryption_cipher()
        token = token.strip()
        encrypted_token = cipher.encrypt(token.encode())
        self.api_token = encrypted_token.decode()

    def get_api_token(self) -> str:
        """Decrypt the OANDA API token, trying fallback keys if needed."""
        encrypted = self.api_token.encode()
        for key_index, cipher in enumerate(self._get_decryption_ciphers()):
            try:
                decrypted_token = cipher.decrypt(encrypted)
                if key_index > 0:
                    import logging

                    logging.getLogger(__name__).info(
                        "OANDA token for account %s decrypted with fallback key index %d "
                        "— consider re-encrypting with the primary key",
                        self.account_id,
                        key_index,
                    )
                return decrypted_token.decode().strip()
            except InvalidToken:
                continue
        raise ValueError("Unable to decrypt OANDA API token with configured keys.")

    @property
    def api_hostname(self) -> str:
        # OANDA account IDs commonly encode environment:
        # - Practice: 101-...
        # - Live:     001-...
        # Prefer this signal to avoid accidentally calling the wrong host.
        account_id = (self.account_id or "").strip()
        if account_id.startswith("101-"):
            hostname = settings.OANDA_PRACTICE_API
        elif account_id.startswith("001-") or self.api_type == "live":
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
        OandaAccounts.objects.filter(user=self.user, is_default=True).exclude(id=self.pk).update(
            is_default=False
        )
        self.is_default = True
        self.save(update_fields=["is_default", "updated_at"])

    @classmethod
    def _should_invalidate_market_metadata(
        cls, update_fields: Collection[str] | None, is_create: bool
    ) -> bool:
        if is_create or update_fields is None:
            return True
        return bool(cls.MARKET_METADATA_DEPENDENCY_FIELDS.intersection(update_fields))

    def save(self, *args: Any, **kwargs: Any) -> None:
        update_fields = kwargs.get("update_fields")
        is_create = self._state.adding
        previous_hostname: str | None = None

        if self.pk and self._should_invalidate_market_metadata(update_fields, is_create):
            previous = type(self).objects.filter(pk=self.pk).only("account_id", "api_type").first()
            if previous is not None:
                previous_hostname = previous.api_hostname

        super().save(*args, **kwargs)

        if self._should_invalidate_market_metadata(update_fields, is_create):
            hostnames = {self.api_hostname}
            if previous_hostname:
                hostnames.add(previous_hostname)
            invalidate_market_metadata_cache(hostnames)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        hostname = self.api_hostname
        result = super().delete(*args, **kwargs)
        invalidate_market_metadata_cache({hostname})
        return result
