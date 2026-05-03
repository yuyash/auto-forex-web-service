"""SnowballNet strategy parameter normalization and validation."""

from __future__ import annotations

from typing import Any

from apps.trading.strategies.base import Strategy
from apps.trading.strategies.snowball_net.config import SnowballNetConfig


def parse_config(strategy_config: Any) -> SnowballNetConfig:
    return SnowballNetConfig.strict_from_dict(strategy_config.config_dict)


def normalize_parameters(parameters: dict[str, Any]) -> dict[str, Any]:
    return SnowballNetConfig.from_dict(dict(parameters)).to_dict()


def default_parameters() -> dict[str, Any]:
    return SnowballNetConfig.from_dict({}).to_dict()


def validate_parameters(
    *,
    parameters: dict[str, Any],
    config_schema: dict[str, Any] | None = None,
) -> None:
    Strategy.validate_parameters(parameters=parameters, config_schema=config_schema)
    SnowballNetConfig.from_dict(parameters).validate()
