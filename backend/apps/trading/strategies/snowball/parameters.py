"""Snowball strategy parameter normalization and validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apps.trading.strategies.base import Strategy
from apps.trading.strategies.snowball.config import SnowballStrategyConfig, WARMUP_OPTIONAL_KEYS

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
        # rebuild_entry_buffer_pips is only meaningful when the rebuild
        # entry is anchored on the stop-loss exit price.  For the
        # ``original_entry`` mode the rebuild always lands at the original
        # entry, so a buffer would have no effect and we drop the field
        # from the persisted payload to keep configs minimal.
        if (
            not config.stop_loss_enabled
            or not config.rebuild_enabled
            or config.rebuild_entry_price_mode != "stop_loss_exit"
        ):
            parameters.pop("rebuild_entry_buffer_pips", None)
        # rebuild_cooldown_seconds only matters when rebuilds can fire,
        # i.e. when both stop-loss and rebuild are enabled.
        if not config.stop_loss_enabled or not config.rebuild_enabled:
            parameters.pop("rebuild_cooldown_seconds", None)
        if not config.warmup_enabled:
            for key in WARMUP_OPTIONAL_KEYS:
                if key != "warmup_enabled":
                    parameters.pop(key, None)
        elif not config.warmup_start_gate_enabled:
            for key in (
                "warmup_gate_spread_enabled",
                "warmup_gate_max_spread_pips",
                "warmup_gate_volatility_enabled",
                "warmup_gate_volatility_window_ticks",
                "warmup_gate_max_volatility_pips",
                "warmup_gate_trend_enabled",
                "warmup_gate_trend_window_ticks",
                "warmup_gate_max_trend_pips",
            ):
                parameters.pop(key, None)
        else:
            if not config.warmup_gate_spread_enabled:
                parameters.pop("warmup_gate_max_spread_pips", None)
            if not config.warmup_gate_volatility_enabled:
                parameters.pop("warmup_gate_volatility_window_ticks", None)
                parameters.pop("warmup_gate_max_volatility_pips", None)
            if not config.warmup_gate_trend_enabled:
                parameters.pop("warmup_gate_trend_window_ticks", None)
                parameters.pop("warmup_gate_max_trend_pips", None)
        if config.warmup_enabled and not config.warmup_position_limit_enabled:
            parameters.pop("warmup_max_positions", None)
        if config.warmup_enabled and not config.warmup_rebuild_limit_enabled:
            parameters.pop("warmup_max_rebuilds_per_tick", None)
        if config.warmup_enabled and config.warmup_completion_mode == "duration":
            parameters.pop("warmup_required_tp_closes", None)
        if config.warmup_enabled and config.warmup_completion_mode == "tp_closes":
            parameters.pop("warmup_min_elapsed_minutes", None)
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
