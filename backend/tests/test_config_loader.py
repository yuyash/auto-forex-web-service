"""
Unit tests for ConfigLoader class.

Tests YAML loading, parsing, validation, default value handling,
and error handling for invalid configurations.
"""

import tempfile
from pathlib import Path

import pytest
import yaml

from trading_system.config_loader import (
    ConfigLoader,
    ConfigValidationError,
    get_config,
    get_config_loader,
)


class TestConfigLoader:
    """Test suite for ConfigLoader class."""

    @pytest.fixture
    def valid_config(self):
        """Fixture providing a valid configuration dictionary."""
        return {
            "server": {
                "host": "0.0.0.0",
                "port": 8000,
                "debug": False,
            },
            "oanda": {
                "practice_api": "https://api-fxpractice.oanda.com",
                "live_api": "https://api-fxtrade.oanda.com",
                "stream_timeout": 30,
            },
            "security": {
                "jwt_expiration": 86400,
                "max_login_attempts": 5,
                "lockout_duration": 900,
                "rate_limit_requests": 100,
                "rate_limit_window": 60,
            },
            "logging": {
                "level": "INFO",
                "format": "json",
                "retention_days": 90,
            },
        }

    @pytest.fixture
    def temp_config_file(self, valid_config):
        """Fixture providing a temporary configuration file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(valid_config, f)
            temp_path = f.name

        yield temp_path

        # Cleanup
        Path(temp_path).unlink(missing_ok=True)

    def test_load_valid_config(self, temp_config_file):
        """Test loading a valid configuration file."""
        loader = ConfigLoader(temp_config_file)
        config = loader.load()

        assert config is not None
        assert "server" in config
        assert "oanda" in config
        assert "security" in config
        assert "logging" in config

    def test_load_nonexistent_file(self):
        """Test loading a non-existent configuration file."""
        loader = ConfigLoader("/nonexistent/path/config.yaml")

        with pytest.raises(FileNotFoundError):
            loader.load()

    def test_load_empty_file(self):
        """Test loading an empty configuration file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("")
            temp_path = f.name

        try:
            loader = ConfigLoader(temp_path)
            with pytest.raises(ConfigValidationError, match="Configuration file is empty"):
                loader.load()
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_load_invalid_yaml(self):
        """Test loading a malformed YAML file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("invalid: yaml: content:\n  - broken")
            temp_path = f.name

        try:
            loader = ConfigLoader(temp_path)
            with pytest.raises(yaml.YAMLError):
                loader.load()
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_missing_required_section(self):
        """Test validation fails when required section is missing."""
        # Create config without required section
        config = {
            "oanda": {
                "practice_api": "https://api-fxpractice.oanda.com",
                "live_api": "https://api-fxtrade.oanda.com",
                "stream_timeout": 30,
            },
            "security": {
                "jwt_expiration": 86400,
                "max_login_attempts": 5,
                "lockout_duration": 900,
                "rate_limit_requests": 100,
                "rate_limit_window": 60,
            },
            "logging": {
                "level": "INFO",
                "format": "json",
                "retention_days": 90,
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config, f)
            temp_path = f.name

        try:
            loader = ConfigLoader(temp_path)
            with pytest.raises(
                ConfigValidationError, match="Missing required configuration section: server"
            ):
                loader.load()
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_missing_required_field(self, temp_config_file):
        """Test validation fails when required field is missing."""
        # Load and modify config to remove required field
        with open(temp_config_file, "r") as f:
            config = yaml.safe_load(f)

        del config["server"]["port"]

        with open(temp_config_file, "w") as f:
            yaml.dump(config, f)

        loader = ConfigLoader(temp_config_file)
        with pytest.raises(
            ConfigValidationError, match="Missing required field 'port' in section 'server'"
        ):
            loader.load()

    def test_default_values_applied(self, temp_config_file):
        """Test that default values are applied for optional fields."""
        loader = ConfigLoader(temp_config_file)
        config = loader.load()

        # Check that defaults are applied
        assert "allowed_hosts" in config["server"]
        assert config["server"]["allowed_hosts"] == ["localhost", "127.0.0.1"]

        assert "max_reconnect_attempts" in config["oanda"]
        assert config["oanda"]["max_reconnect_attempts"] == 5

        assert "account_lock_threshold" in config["security"]
        assert config["security"]["account_lock_threshold"] == 10

    def test_invalid_port_type(self, temp_config_file):
        """Test validation fails for invalid port type."""
        with open(temp_config_file, "r") as f:
            config = yaml.safe_load(f)

        config["server"]["port"] = "not_an_integer"

        with open(temp_config_file, "w") as f:
            yaml.dump(config, f)

        loader = ConfigLoader(temp_config_file)
        with pytest.raises(ConfigValidationError, match="server.port must be an integer"):
            loader.load()

    def test_invalid_port_range(self, temp_config_file):
        """Test validation fails for port out of valid range."""
        with open(temp_config_file, "r") as f:
            config = yaml.safe_load(f)

        config["server"]["port"] = 70000

        with open(temp_config_file, "w") as f:
            yaml.dump(config, f)

        loader = ConfigLoader(temp_config_file)
        with pytest.raises(ConfigValidationError, match="server.port must be between 1 and 65535"):
            loader.load()

    def test_invalid_debug_type(self, temp_config_file):
        """Test validation fails for invalid debug type."""
        with open(temp_config_file, "r") as f:
            config = yaml.safe_load(f)

        config["server"]["debug"] = "not_a_boolean"

        with open(temp_config_file, "w") as f:
            yaml.dump(config, f)

        loader = ConfigLoader(temp_config_file)
        with pytest.raises(ConfigValidationError, match="server.debug must be a boolean"):
            loader.load()

    def test_invalid_jwt_expiration(self, temp_config_file):
        """Test validation fails for invalid JWT expiration."""
        with open(temp_config_file, "r") as f:
            config = yaml.safe_load(f)

        config["security"]["jwt_expiration"] = -100

        with open(temp_config_file, "w") as f:
            yaml.dump(config, f)

        loader = ConfigLoader(temp_config_file)
        with pytest.raises(ConfigValidationError, match="security.jwt_expiration must be positive"):
            loader.load()

    def test_invalid_logging_level(self, temp_config_file):
        """Test validation fails for invalid logging level."""
        with open(temp_config_file, "r") as f:
            config = yaml.safe_load(f)

        config["logging"]["level"] = "INVALID"

        with open(temp_config_file, "w") as f:
            yaml.dump(config, f)

        loader = ConfigLoader(temp_config_file)
        with pytest.raises(ConfigValidationError, match="logging.level must be one of"):
            loader.load()

    def test_invalid_logging_format(self, temp_config_file):
        """Test validation fails for invalid logging format."""
        with open(temp_config_file, "r") as f:
            config = yaml.safe_load(f)

        config["logging"]["format"] = "invalid_format"

        with open(temp_config_file, "w") as f:
            yaml.dump(config, f)

        loader = ConfigLoader(temp_config_file)
        with pytest.raises(ConfigValidationError, match="logging.format must be one of"):
            loader.load()

    def test_get_config_value(self, temp_config_file):
        """Test getting configuration values by key."""
        loader = ConfigLoader(temp_config_file)
        loader.load()

        assert loader.get("server.port") == 8000
        assert loader.get("server.host") == "0.0.0.0"
        assert loader.get("security.jwt_expiration") == 86400

    def test_get_config_value_with_default(self, temp_config_file):
        """Test getting configuration value with default."""
        loader = ConfigLoader(temp_config_file)
        loader.load()

        assert loader.get("nonexistent.key", "default_value") == "default_value"

    def test_get_section(self, temp_config_file):
        """Test getting entire configuration section."""
        loader = ConfigLoader(temp_config_file)
        loader.load()

        server_config = loader.get_section("server")
        assert isinstance(server_config, dict)
        assert "host" in server_config
        assert "port" in server_config
        assert "debug" in server_config

    def test_get_nonexistent_section(self, temp_config_file):
        """Test getting non-existent section raises KeyError."""
        loader = ConfigLoader(temp_config_file)
        loader.load()

        with pytest.raises(KeyError, match="Configuration section 'nonexistent' not found"):
            loader.get_section("nonexistent")

    def test_reload_config(self, temp_config_file):
        """Test reloading configuration from file."""
        loader = ConfigLoader(temp_config_file)
        config1 = loader.load()

        # Modify the file
        with open(temp_config_file, "r") as f:
            config = yaml.safe_load(f)

        config["server"]["port"] = 9000

        with open(temp_config_file, "w") as f:
            yaml.dump(config, f)

        # Reload
        config2 = loader.reload()

        assert config2["server"]["port"] == 9000
        assert config1["server"]["port"] != config2["server"]["port"]

    def test_config_property(self, temp_config_file):
        """Test accessing full configuration via property."""
        loader = ConfigLoader(temp_config_file)
        config = loader.config

        assert config is not None
        assert isinstance(config, dict)
        assert "server" in config

    def test_global_config_loader(self, temp_config_file):
        """Test global config loader singleton."""
        loader1 = get_config_loader(temp_config_file)
        loader2 = get_config_loader()

        assert loader1 is loader2

    def test_get_config_convenience_function(self, valid_config):
        """Test convenience function for getting config values."""
        # Create a persistent temp file for this test
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(valid_config, f)
            temp_path = f.name

        try:
            # Reset global loader
            import trading_system.config_loader as config_module

            config_module._config_loader = None

            # Initialize global loader
            get_config_loader(temp_path)

            value = get_config("server.port", 8080)
            assert value == 8000

            default_value = get_config("nonexistent.key", "default")
            assert default_value == "default"
        finally:
            Path(temp_path).unlink(missing_ok=True)
            # Reset global loader again
            config_module._config_loader = None
