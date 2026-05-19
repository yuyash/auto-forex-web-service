"""Snowball strategy parameter normalization and validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apps.trading.strategies.base import Strategy
from apps.trading.strategies.snowball.config import SnowballStrategyConfig

__all__ = ["SNOWBALL_PARAMETER_SERVICE", "SnowballParameterService"]


@dataclass(frozen=True, slots=True)
class SnowballParameterService:
    """Own Snowball parameter parsing, normalization, defaults, and validation."""

    def parse_config(self, strategy_config: Any) -> SnowballStrategyConfig:
        """Parse persisted strategy configuration into a strict Snowball config."""
        return SnowballStrategyConfig.strict_from_dict(strategy_config.config_dict)

    def config_to_parameters(self, config: SnowballStrategyConfig) -> dict[str, Any]:
        """Return the persisted parameter payload for a config object."""
        parameters = config.to_dict()
        if not config.base_units_auto_adjust_enabled:
            parameters.pop("base_units_balance_ratio", None)
            parameters.pop("base_units_step", None)
        if not config.preserve_highest_retracement_enabled:
            parameters.pop("preserve_highest_r_from", None)
        return parameters

    def normalize_parameters(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Normalize user-supplied parameters through Snowball config defaults."""
        config = SnowballStrategyConfig.from_dict(dict(parameters))
        return self.config_to_parameters(config)

    def default_parameters(self) -> dict[str, Any]:
        """Return default Snowball parameters in persisted shape."""
        config = SnowballStrategyConfig.from_dict({})
        return self.config_to_parameters(config)

    def validate_parameters(
        self,
        *,
        parameters: dict[str, Any],
        config_schema: dict[str, Any] | None = None,
    ) -> None:
        """Validate schema-level and Snowball-specific parameter rules."""
        Strategy.validate_parameters(parameters=parameters, config_schema=config_schema)
        SnowballStrategyConfig.from_dict(parameters).validate()


SNOWBALL_PARAMETER_SERVICE = SnowballParameterService()
