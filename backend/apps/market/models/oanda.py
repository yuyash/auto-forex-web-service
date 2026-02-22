"""OANDA account model."""

import base64
import hashlib

from cryptography.fernet import Fernet
from django.conf import settings
from django.db import models

from apps.market.enums import ApiType, Jurisdiction


class OandaAccounts(models.Model):
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
        unique_together = [["user", "account_id", "api_type"]]
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
        token = token.strip()
        encrypted_token = cipher.encrypt(token.encode())
        self.api_token = encrypted_token.decode()

    def get_api_token(self) -> str:
        cipher = self._get_cipher()
        decrypted_token = cipher.decrypt(self.api_token.encode())
        return decrypted_token.decode().strip()

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
