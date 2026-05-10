"""Strategy configuration models."""

import hashlib
import json
from typing import TYPE_CHECKING, Any

from django.db import models

from apps.trading.enums import StrategyType
from apps.trading.models.base import UUIDModel

if TYPE_CHECKING:
    from apps.trading.models import BacktestTask, TradingTask


class StrategyConfigurationManager(models.Manager["StrategyConfiguration"]):
    """Custom manager for StrategyConfiguration model."""

    def create_for_user(self, user: Any, **kwargs: Any) -> "StrategyConfiguration":
        return self.create(user=user, **kwargs)

    def for_user(self, user: Any) -> models.QuerySet["StrategyConfiguration"]:
        return self.filter(user=user)


class StrategyConfiguration(UUIDModel):
    """Reusable strategy configuration used by TradingTask and BacktestTask.

    Inherits UUID primary key and timestamps from UUIDModel.
    """

    objects = StrategyConfigurationManager()

    # Type hints for reverse relations (created by ForeignKey related_name)
    if TYPE_CHECKING:
        backtest_tasks: models.Manager["BacktestTask"]
        trading_tasks: models.Manager["TradingTask"]

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="strategy_configs",
        help_text="User who created this configuration",
    )
    name = models.CharField(
        max_length=255,
        help_text="Human-readable name for this configuration",
    )
    strategy_type = models.CharField(
        max_length=50,
        help_text="Type of strategy (e.g., 'floor', 'ma_crossover', 'rsi')",
    )
    parameters = models.JSONField(
        default=dict,
        help_text="Strategy-specific configuration parameters",
    )
    revision = models.PositiveIntegerField(
        default=1,
        help_text="Monotonic revision for runtime-affecting configuration changes",
    )
    config_hash = models.CharField(
        max_length=64,
        blank=True,
        default="",
        db_index=True,
        help_text="Stable hash of strategy_type and parameters for this revision",
    )
    description = models.TextField(
        blank=True,
        default="",
        help_text="Optional description of this configuration",
    )

    class Meta:
        db_table = "strategy_configurations"
        verbose_name = "Strategy Configuration"
        verbose_name_plural = "Strategy Configurations"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "strategy_type"]),
            models.Index(fields=["created_at"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["user", "name"], name="unique_user_config_name")
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.strategy_type})"

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary.

        Returns:
            Dictionary representation of the configuration
        """
        return {
            "id": str(self.id),
            "user_id": self.user.pk,
            "name": self.name,
            "strategy_type": self.strategy_type,
            "parameters": self.parameters,
            "revision": self.revision,
            "config_hash": self.config_hash,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], user: Any) -> "StrategyConfiguration":
        """Create configuration from dictionary.

        Args:
            data: Dictionary containing configuration data
            user: User instance to associate with the configuration

        Returns:
            StrategyConfiguration instance
        """
        return cls(
            user=user,
            name=data["name"],
            strategy_type=data["strategy_type"],
            parameters=data.get("parameters", {}),
            description=data.get("description", ""),
        )

    @property
    def strategy_type_enum(self) -> "StrategyType":
        """Get strategy type as enum.

        Returns:
            StrategyType enum value
        """
        from apps.trading.enums import StrategyType

        try:
            return StrategyType(self.strategy_type)
        except ValueError:
            return StrategyType.CUSTOM

    @property
    def config_dict(self) -> dict[str, Any]:
        """Get configuration parameters as dictionary.

        Returns:
            Configuration parameters dictionary
        """
        return self.parameters or {}

    def runtime_config_hash(self) -> str:
        """Return a stable hash for runtime-affecting configuration fields."""
        return hash_runtime_config(
            strategy_type=self.strategy_type,
            parameters=self.parameters or {},
        )

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Ensure every persisted configuration has a runtime config hash."""
        runtime_hash = self.runtime_config_hash()
        if self.config_hash != runtime_hash:
            self.config_hash = runtime_hash
            update_fields = kwargs.get("update_fields")
            if update_fields is not None:
                kwargs["update_fields"] = {*update_fields, "config_hash"}
        super().save(*args, **kwargs)

    def is_in_use(self) -> bool:
        """Check if configuration is referenced by any tasks.

        Returns:
            True if any trading or backtest tasks reference this configuration,
            False otherwise.
        """
        from apps.trading.models import BacktestTask, TradingTask

        return (
            TradingTask.objects.filter(config=self).exists()
            or BacktestTask.objects.filter(config=self).exists()
        )

    def has_active_tasks(self) -> bool:
        """Check if configuration is used by tasks currently owned by workers.

        Returns:
            True if any actively executing tasks reference this configuration,
            False otherwise.
        """
        from apps.trading.models import BacktestTask, TradingTask
        from apps.trading.services.task_policy import CONFIGURATION_LOCK_STATUSES

        return (
            TradingTask.objects.filter(
                config=self,
                status__in=CONFIGURATION_LOCK_STATUSES,
            ).exists()
            or BacktestTask.objects.filter(
                config=self,
                status__in=CONFIGURATION_LOCK_STATUSES,
            ).exists()
        )

    @classmethod
    def user_has_running_tasks(cls, user: Any) -> bool:
        """Return True when the given user has at least one running task.

        Configuration updates are globally locked per user while any trading or
        backtest task is actively owned by a worker.
        """
        from apps.trading.models import BacktestTask, TradingTask
        from apps.trading.services.task_policy import CONFIGURATION_LOCK_STATUSES

        user_id = getattr(user, "pk", user)
        return (
            TradingTask.objects.filter(
                user=user_id, status__in=CONFIGURATION_LOCK_STATUSES
            ).exists()
            or BacktestTask.objects.filter(
                user=user_id, status__in=CONFIGURATION_LOCK_STATUSES
            ).exists()
        )

    def validate_parameters(self) -> tuple[bool, str | None]:
        """Validate parameters through strategy registry plugins.

        Returns:
            Tuple of (is_valid, error_message)
        """
        from apps.trading.strategies.registry import registry

        if not registry.is_registered(self.strategy_type):
            return False, f"Strategy type '{self.strategy_type}' is not registered"

        if not isinstance(self.parameters, dict):
            return False, "Parameters must be a JSON object"

        try:
            normalized = registry.normalize_parameters(
                identifier=self.strategy_type,
                parameters=self.parameters,
            )
            registry.validate_parameters(
                identifier=self.strategy_type,
                parameters=normalized,
            )
        except ValueError as exc:
            return False, str(exc)

        return True, None


def hash_runtime_config(*, strategy_type: str, parameters: dict[str, Any]) -> str:
    """Hash the fields that affect strategy runtime behavior."""
    payload = {
        "strategy_type": str(strategy_type),
        "parameters": _normalize_for_hash(parameters or {}),
    }
    normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def _normalize_for_hash(value: Any) -> Any:
    return json.loads(json.dumps(value, sort_keys=True, default=str))
