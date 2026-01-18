"""Strategy configuration models."""

from typing import Any

from django.db import models

from apps.trading.enums import StrategyType


class StrategyConfigurationsManager(models.Manager["StrategyConfigurations"]):
    """Custom manager for StrategyConfigurations model."""

    def create_for_user(self, user: Any, **kwargs: Any) -> "StrategyConfigurations":
        return self.create(user=user, **kwargs)

    def for_user(self, user: Any) -> models.QuerySet["StrategyConfigurations"]:
        return self.filter(user=user)


class StrategyConfigurations(models.Model):
    """Reusable strategy configuration used by TradingTasks and BacktestTasks."""

    objects = StrategyConfigurationsManager()

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
    description = models.TextField(
        blank=True,
        default="",
        help_text="Optional description of this configuration",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when the configuration was created",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when the configuration was last updated",
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

    @property
    def strategy_type_enum(self) -> "StrategyType":
        """Get strategy type as enum.

        Returns:
            StrategyType enum value
        """
        from apps.trading.enums import StrategyType

        return StrategyType(self.strategy_type)

    @property
    def config_dict(self) -> dict[str, Any]:
        """Get configuration parameters as dictionary.

        Returns:
            Configuration parameters dictionary
        """
        return self.parameters or {}

    def is_in_use(self) -> bool:
        from apps.trading.enums import TaskStatus
        from apps.trading.models.tasks import BacktestTasks, TradingTasks

        return (
            TradingTasks.objects.filter(
                config=self,
                status=TaskStatus.RUNNING,
            ).exists()
            or BacktestTasks.objects.filter(
                config=self,
                status=TaskStatus.RUNNING,
            ).exists()
        )

    def validate_parameters(self) -> tuple[bool, str | None]:
        """Validate parameters against the strategy registry schema (best-effort)."""
        from apps.trading.services.registry import registry

        if not registry.is_registered(self.strategy_type):
            return False, f"Strategy type '{self.strategy_type}' is not registered"

        if not isinstance(self.parameters, dict):
            return False, "Parameters must be a JSON object"

        return True, None
