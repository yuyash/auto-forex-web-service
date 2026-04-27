"""Snowball strategy parameter normalization and validation."""

from __future__ import annotations

from typing import Any

from apps.trading.strategies.base import Strategy
from apps.trading.strategies.snowball.config import SnowballStrategyConfig


def parse_config(strategy_config: Any) -> SnowballStrategyConfig:
    return SnowballStrategyConfig.strict_from_dict(strategy_config.config_dict)


def config_to_parameters(config: SnowballStrategyConfig) -> dict[str, Any]:
    parameters = config.to_dict()
    if not config.preserve_highest_retracement_enabled:
        parameters.pop("preserve_highest_r_from", None)
    return parameters


def normalize_parameters(parameters: dict[str, Any]) -> dict[str, Any]:
    config = SnowballStrategyConfig.from_dict(dict(parameters))
    return config_to_parameters(config)


def default_parameters() -> dict[str, Any]:
    config = SnowballStrategyConfig.from_dict({})
    return config_to_parameters(config)


def validate_parameters(
    *,
    parameters: dict[str, Any],
    config_schema: dict[str, Any] | None = None,
) -> None:
    Strategy.validate_parameters(parameters=parameters, config_schema=config_schema)
    SnowballStrategyConfig.from_dict(parameters).validate()
