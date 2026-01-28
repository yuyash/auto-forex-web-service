"""Strategy configuration models."""

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

        return StrategyType(self.strategy_type)

    @property
    def config_dict(self) -> dict[str, Any]:
        """Get configuration parameters as dictionary.

        Returns:
            Configuration parameters dictionary
        """
        return self.parameters or {}

    def is_in_use(self) -> bool:
        """Check if configuration is currently in use by any running tasks.

        Returns:
            True if configuration is in use, False otherwise
        """
        from apps.trading.enums import TaskStatus
        from apps.trading.models import BacktestTask, TradingTask

        return (
            TradingTask.objects.filter(
                config=self,
                status=TaskStatus.RUNNING,
            ).exists()
            or BacktestTask.objects.filter(
                config=self,
                status=TaskStatus.RUNNING,
            ).exists()
        )

    def validate_parameters(self) -> tuple[bool, str | None]:
        """Validate parameters against the strategy registry schema (best-effort).

        Returns:
            Tuple of (is_valid, error_message)
        """
        from apps.trading.strategies.registry import registry

        if not registry.is_registered(self.strategy_type):
            return False, f"Strategy type '{self.strategy_type}' is not registered"

        if not isinstance(self.parameters, dict):
            return False, "Parameters must be a JSON object"

        return True, None
