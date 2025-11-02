"""
Configuration loader for system settings.

This module provides functionality to load and validate YAML configuration files
for the Auto Forex Trading System.
"""

from pathlib import Path
from typing import Any, Dict, Optional

import yaml


class ConfigValidationError(Exception):
    """Raised when configuration validation fails."""


class ConfigLoader:
    """
    Load and validate system configuration from YAML files.

    This class handles loading configuration from YAML files, validating
    required fields, and providing default values where appropriate.
    """

    # Required configuration sections
    REQUIRED_SECTIONS = [
        "server",
        "oanda",
        "security",
        "logging",
    ]

    # Required fields within each section
    REQUIRED_FIELDS = {
        "server": ["host", "port", "debug"],
        "oanda": ["practice_api", "live_api", "stream_timeout"],
        "security": [
            "jwt_expiration",
            "max_login_attempts",
            "lockout_duration",
            "rate_limit_requests",
            "rate_limit_window",
        ],
        "logging": ["level", "format", "retention_days"],
    }

    # Default values for optional fields
    DEFAULTS = {
        "server": {
            "allowed_hosts": ["localhost", "127.0.0.1"],
        },
        "oanda": {
            "max_reconnect_attempts": 5,
            "reconnect_intervals": [1, 2, 4, 8, 16],
        },
        "security": {
            "account_lock_threshold": 10,
            "ip_block_duration": 3600,
        },
        "logging": {
            "log_file": "logs/django.log",
            "max_file_size": 10485760,
            "backup_count": 5,
        },
        "celery": {
            "broker_url": "redis://redis:6379/0",
            "result_backend": "redis://redis:6379/0",
            "task_serializer": "json",
            "result_serializer": "json",
            "accept_content": ["json"],
            "timezone": "UTC",
            "enable_utc": True,
        },
        "database": {
            "engine": "django.db.backends.postgresql",
            "conn_max_age": 600,
            "conn_health_checks": True,
        },
        "redis": {
            "host": "redis",
            "port": 6379,
            "db": 0,
            "socket_timeout": 5,
            "socket_connect_timeout": 5,
        },
        "risk_management": {
            "atr_period": 14,
            "volatility_lock_multiplier": 5.0,
            "margin_liquidation_threshold": 1.0,
            "max_layers": 3,
        },
        "strategy": {
            "default_base_lot_size": 1.0,
            "default_scaling_mode": "additive",
            "default_retracement_pips": 30,
            "default_take_profit_pips": 25,
            "max_concurrent_strategies": 10,
        },
        "backtesting": {
            "default_slippage_pips": 0.5,
            "default_commission": 0.0,
            "max_concurrent_backtests": 5,
            "data_source": "s3",
        },
        "tick_storage": {
            "enabled": True,
            "batch_size": 100,
            "batch_timeout": 1.0,
        },
    }

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the ConfigLoader.

        Args:
            config_path: Path to the configuration file. If None, uses default path.
        """
        if config_path is None:
            # Default to config/system.yaml in the backend directory
            base_dir = Path(__file__).resolve().parent.parent
            self.config_path = base_dir / "config" / "system.yaml"
        else:
            self.config_path = Path(config_path)

        self._config: Optional[Dict[str, Any]] = None

    def load(self) -> Dict[str, Any]:
        """
        Load configuration from YAML file.

        Returns:
            Dictionary containing the loaded configuration.

        Raises:
            FileNotFoundError: If the configuration file does not exist.
            yaml.YAMLError: If the YAML file is malformed.
            ConfigValidationError: If the configuration is invalid.
        """
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise yaml.YAMLError(f"Failed to parse YAML configuration: {e}") from e

        if config is None:
            raise ConfigValidationError("Configuration file is empty")

        # Validate required sections first (before applying defaults)
        self._validate_required_sections(config)

        # Apply defaults
        config = self._apply_defaults(config)

        # Validate configuration
        self._validate(config)

        self._config = config
        return config

    def _apply_defaults(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply default values to configuration.

        Args:
            config: The loaded configuration dictionary.

        Returns:
            Configuration with defaults applied.
        """
        for section, defaults in self.DEFAULTS.items():
            if section not in config:
                config[section] = {}

            section_config = config[section]
            if isinstance(section_config, dict) and isinstance(defaults, dict):
                for key, value in defaults.items():
                    if key not in section_config:
                        section_config[key] = value

        return config

    def _validate_required_sections(self, config: Dict[str, Any]) -> None:
        """
        Validate that all required sections are present.

        Args:
            config: The configuration dictionary to validate.

        Raises:
            ConfigValidationError: If validation fails.
        """
        for section in self.REQUIRED_SECTIONS:
            if section not in config:
                raise ConfigValidationError(f"Missing required configuration section: {section}")

    def _validate(self, config: Dict[str, Any]) -> None:
        """
        Validate the configuration.

        Args:
            config: The configuration dictionary to validate.

        Raises:
            ConfigValidationError: If validation fails.
        """
        # Check required fields within sections
        for section, fields in self.REQUIRED_FIELDS.items():
            if section not in config:
                continue

            for field in fields:
                if field not in config[section]:
                    raise ConfigValidationError(
                        f"Missing required field '{field}' in section '{section}'"
                    )

        # Validate specific field types and values
        self._validate_server_config(config.get("server", {}))
        self._validate_security_config(config.get("security", {}))
        self._validate_logging_config(config.get("logging", {}))

    def _validate_server_config(self, server_config: Dict[str, Any]) -> None:
        """Validate server configuration."""
        if not isinstance(server_config.get("port"), int):
            raise ConfigValidationError("server.port must be an integer")

        if not 1 <= server_config.get("port", 0) <= 65535:
            raise ConfigValidationError("server.port must be between 1 and 65535")

        if not isinstance(server_config.get("debug"), bool):
            raise ConfigValidationError("server.debug must be a boolean")

    def _validate_security_config(self, security_config: Dict[str, Any]) -> None:
        """Validate security configuration."""
        if not isinstance(security_config.get("jwt_expiration"), int):
            raise ConfigValidationError("security.jwt_expiration must be an integer")

        if security_config.get("jwt_expiration", 0) <= 0:
            raise ConfigValidationError("security.jwt_expiration must be positive")

        if not isinstance(security_config.get("max_login_attempts"), int):
            raise ConfigValidationError("security.max_login_attempts must be an integer")

        if security_config.get("max_login_attempts", 0) <= 0:
            raise ConfigValidationError("security.max_login_attempts must be positive")

    def _validate_logging_config(self, logging_config: Dict[str, Any]) -> None:
        """Validate logging configuration."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        level = logging_config.get("level", "").upper()

        if level not in valid_levels:
            raise ConfigValidationError(
                f"logging.level must be one of {valid_levels}, got '{level}'"
            )

        valid_formats = ["json", "text"]
        format_type = logging_config.get("format", "").lower()

        if format_type not in valid_formats:
            raise ConfigValidationError(
                f"logging.format must be one of {valid_formats}, got '{format_type}'"
            )

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value by key.

        Supports dot notation for nested keys (e.g., 'server.port').

        Args:
            key: The configuration key to retrieve.
            default: Default value if key is not found.

        Returns:
            The configuration value or default.
        """
        if self._config is None:
            self.load()

        keys = key.split(".")
        value = self._config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def get_section(self, section: str) -> Dict[str, Any]:
        """
        Get an entire configuration section.

        Args:
            section: The section name to retrieve.

        Returns:
            Dictionary containing the section configuration.

        Raises:
            KeyError: If the section does not exist.
        """
        if self._config is None:
            self.load()

        if self._config is None or section not in self._config:
            raise KeyError(f"Configuration section '{section}' not found")

        section_data = self._config[section]
        if not isinstance(section_data, dict):
            raise KeyError(f"Configuration section '{section}' is not a dictionary")

        return section_data

    def reload(self) -> Dict[str, Any]:
        """
        Reload configuration from file.

        Returns:
            Dictionary containing the reloaded configuration.
        """
        self._config = None
        return self.load()

    @property
    def config(self) -> Dict[str, Any]:
        """
        Get the full configuration dictionary.

        Returns:
            The complete configuration.
        """
        if self._config is None:
            self.load()

        if self._config is None:
            raise RuntimeError("Configuration could not be loaded")

        return self._config


# Global configuration instance
_config_loader: Optional[ConfigLoader] = None


def get_config_loader(config_path: Optional[str] = None) -> ConfigLoader:
    """
    Get the global ConfigLoader instance.

    Args:
        config_path: Optional path to configuration file.

    Returns:
        The global ConfigLoader instance.
    """
    global _config_loader  # pylint: disable=global-statement

    if _config_loader is None:
        _config_loader = ConfigLoader(config_path)

    return _config_loader


def get_config(key: str, default: Any = None) -> Any:
    """
    Convenience function to get a configuration value.

    Args:
        key: The configuration key (supports dot notation).
        default: Default value if key is not found.

    Returns:
        The configuration value or default.
    """
    loader = get_config_loader()
    return loader.get(key, default)
