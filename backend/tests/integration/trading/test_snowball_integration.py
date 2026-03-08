"""Integration tests for Snowball strategy.

Tests the full normalize → validate → persist → retrieve pipeline
through the Django ORM and strategy registry.
"""

from __future__ import annotations

from typing import Any

import pytest
from rest_framework.test import APIRequestFactory

from apps.trading.models import StrategyConfiguration
from apps.trading.serializers.strategy import StrategyConfigCreateSerializer
from apps.trading.strategies.registry import registry
from tests.integration.factories import StrategyConfigurationFactory, UserFactory

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SNOWBALL_DEFAULTS: dict[str, Any] = {
    "base_units": 1000,
    "m_pips": 50,
    "r_max": 7,
    "m_pips_max": 55,
}

SNOWBALL_FULL_PARAMS: dict[str, Any] = {
    "base_units": 2000,
    "m_pips": "40",
    "trend_lot_size": 2,
    "r_max": 5,
    "f_max": 2,
    "post_r_max_base_factor": "1.5",
    "n_pips_head": "25",
    "n_pips_tail": "10",
    "n_pips_flat_steps": 1,
    "n_pips_gamma": "1.2",
    "interval_mode": "additive",
    "counter_tp_mode": "fixed",
    "counter_tp_pips": "20",
    "counter_tp_step_amount": "3",
    "counter_tp_multiplier": "1.5",
    "round_step_pips": "0.5",
    "dynamic_tp_enabled": False,
    "atr_timeframe": "M5",
    "shrink_enabled": True,
    "m_th": "70",
    "lock_enabled": True,
    "n_th": "85",
    "m_pips_min": "12",
    "m_pips_max": "55",
}


def _make_request(user):
    """Create a fake DRF request with the given user."""
    factory = APIRequestFactory()
    request = factory.post("/fake/")
    request.user = user
    return request


# ===================================================================
# Registry integration
# ===================================================================


@pytest.mark.django_db
class TestSnowballRegistry:
    """Test that snowball is properly registered and usable via the registry."""

    def test_snowball_is_registered(self):
        assert registry.is_registered("snowball")

    def test_snowball_in_list(self):
        assert "snowball" in registry.list_strategies()

    def test_get_snowball_info(self):
        info = registry.get("snowball")
        assert info.identifier == "snowball"
        assert info.display_name == "Snowball Strategy"
        assert "properties" in info.config_schema

    def test_normalize_parameters(self):
        normalised = registry.normalize_parameters(
            identifier="snowball",
            parameters={"base_units": 2000, "atr_timeframe": "h1"},
        )
        assert normalised["base_units"] == 2000
        assert normalised["atr_timeframe"] == "H1"

    def test_normalize_then_validate_defaults(self):
        """Full round-trip: normalize defaults → validate against schema."""
        normalised = registry.normalize_parameters(
            identifier="snowball",
            parameters={"m_pips_max": "55"},
        )
        # Should not raise
        registry.validate_parameters(
            identifier="snowball",
            parameters=normalised,
        )

    def test_normalize_then_validate_lowercase_timeframe(self):
        """Regression: lowercase atr_timeframe must survive normalize → validate."""
        normalised = registry.normalize_parameters(
            identifier="snowball",
            parameters={"atr_timeframe": "m1", "m_pips_max": "55"},
        )
        assert normalised["atr_timeframe"] == "M1"
        registry.validate_parameters(
            identifier="snowball",
            parameters=normalised,
        )

    def test_validate_rejects_invalid_base_units(self):
        normalised = registry.normalize_parameters(
            identifier="snowball",
            parameters={"base_units": 0},
        )
        with pytest.raises(ValueError):
            registry.validate_parameters(
                identifier="snowball",
                parameters=normalised,
            )

    def test_get_defaults(self):
        defaults = registry.get_defaults(identifier="snowball")
        assert "base_units" in defaults
        assert defaults["base_units"] == 1000


# ===================================================================
# Model integration (ORM)
# ===================================================================


@pytest.mark.django_db
class TestSnowballModelIntegration:
    """Test StrategyConfiguration model with snowball strategy type."""

    def test_create_snowball_config(self):
        user = UserFactory()
        config = StrategyConfiguration.objects.create_for_user(
            user,
            name="Snowball Test",
            strategy_type="snowball",
            parameters=SNOWBALL_FULL_PARAMS,
        )
        assert config.pk is not None
        assert config.strategy_type == "snowball"
        assert config.parameters["base_units"] == 2000

    def test_validate_parameters_valid(self):
        user = UserFactory()
        config = StrategyConfiguration.objects.create_for_user(
            user,
            name="Snowball Valid",
            strategy_type="snowball",
            parameters=SNOWBALL_FULL_PARAMS,
        )
        is_valid, error = config.validate_parameters()
        assert is_valid is True, error

    def test_validate_parameters_with_defaults(self):
        """Config with minimal params (relying on from_dict defaults) should validate."""
        user = UserFactory()
        config = StrategyConfiguration.objects.create_for_user(
            user,
            name="Snowball Defaults",
            strategy_type="snowball",
            parameters=SNOWBALL_DEFAULTS,
        )
        is_valid, error = config.validate_parameters()
        assert is_valid is True, error

    def test_validate_parameters_empty_dict(self):
        """Config with empty params should validate (needs m_pips_max >= m_pips default)."""
        user = UserFactory()
        config = StrategyConfiguration.objects.create_for_user(
            user,
            name="Snowball Empty",
            strategy_type="snowball",
            parameters={"m_pips_max": 55},
        )
        is_valid, error = config.validate_parameters()
        assert is_valid is True, error

    def test_validate_parameters_invalid(self):
        user = UserFactory()
        config = StrategyConfiguration.objects.create_for_user(
            user,
            name="Snowball Invalid",
            strategy_type="snowball",
            parameters={"base_units": 0},  # below minimum
        )
        is_valid, error = config.validate_parameters()
        assert is_valid is False

    def test_config_dict_property(self):
        config = StrategyConfigurationFactory(
            strategy_type="snowball",
            parameters=SNOWBALL_FULL_PARAMS,
        )
        assert config.config_dict == SNOWBALL_FULL_PARAMS

    def test_for_user_queryset(self):
        user = UserFactory()
        StrategyConfigurationFactory(user=user, strategy_type="snowball", name="SB1")
        StrategyConfigurationFactory(user=user, strategy_type="snowball", name="SB2")
        other = UserFactory()
        StrategyConfigurationFactory(user=other, strategy_type="snowball", name="SB3")
        assert (
            StrategyConfiguration.objects.for_user(user).filter(strategy_type="snowball").count()
            == 2
        )


# ===================================================================
# Serializer integration
# ===================================================================


@pytest.mark.django_db
class TestSnowballSerializerIntegration:
    """Test StrategyConfigCreateSerializer with real snowball registry."""

    def test_create_with_full_params(self):
        user = UserFactory()
        data = {
            "name": "Snowball Full",
            "strategy_type": "snowball",
            "parameters": SNOWBALL_FULL_PARAMS,
        }
        serializer = StrategyConfigCreateSerializer(
            data=data,
            context={"request": _make_request(user)},
        )
        assert serializer.is_valid(), serializer.errors
        config = serializer.save()
        assert config.strategy_type == "snowball"
        assert config.parameters["base_units"] == 2000

    def test_create_with_defaults_only(self):
        user = UserFactory()
        data = {
            "name": "Snowball Defaults",
            "strategy_type": "snowball",
            "parameters": SNOWBALL_DEFAULTS,
        }
        serializer = StrategyConfigCreateSerializer(
            data=data,
            context={"request": _make_request(user)},
        )
        assert serializer.is_valid(), serializer.errors
        config = serializer.save()
        # Normalised parameters should have all fields populated
        assert "interval_mode" in config.parameters

    def test_create_with_empty_params(self):
        """Empty params should be normalised to full defaults (with m_pips_max fix)."""
        user = UserFactory()
        data = {
            "name": "Snowball Empty Params",
            "strategy_type": "snowball",
            "parameters": {"m_pips_max": 55},
        }
        serializer = StrategyConfigCreateSerializer(
            data=data,
            context={"request": _make_request(user)},
        )
        assert serializer.is_valid(), serializer.errors
        config = serializer.save()
        assert config.parameters["base_units"] == 1000
        assert config.parameters["atr_timeframe"] == "M1"

    def test_create_normalises_lowercase_timeframe(self):
        """Regression: lowercase atr_timeframe must be accepted and normalised."""
        user = UserFactory()
        data = {
            "name": "Snowball Lowercase TF",
            "strategy_type": "snowball",
            "parameters": {"atr_timeframe": "m5", "m_pips_max": 55},
        }
        serializer = StrategyConfigCreateSerializer(
            data=data,
            context={"request": _make_request(user)},
        )
        assert serializer.is_valid(), serializer.errors
        config = serializer.save()
        assert config.parameters["atr_timeframe"] == "M5"

    def test_create_rejects_invalid_base_units(self):
        user = UserFactory()
        data = {
            "name": "Snowball Bad Units",
            "strategy_type": "snowball",
            "parameters": {"base_units": 0},
        }
        serializer = StrategyConfigCreateSerializer(
            data=data,
            context={"request": _make_request(user)},
        )
        assert not serializer.is_valid()
        assert "parameters" in serializer.errors

    def test_update_preserves_strategy_type(self):
        user = UserFactory()
        config = StrategyConfigurationFactory(
            user=user,
            strategy_type="snowball",
            parameters=SNOWBALL_FULL_PARAMS,
            name="Snowball Update",
        )
        data = {"parameters": {**SNOWBALL_FULL_PARAMS, "base_units": 3000}}
        serializer = StrategyConfigCreateSerializer(
            instance=config,
            data=data,
            partial=True,
            context={"request": _make_request(user)},
        )
        assert serializer.is_valid(), serializer.errors
        updated = serializer.save()
        assert updated.parameters["base_units"] == 3000
        assert updated.strategy_type == "snowball"

    def test_create_rejects_invalid_interval_mode(self):
        user = UserFactory()
        data = {
            "name": "Snowball Bad Mode",
            "strategy_type": "snowball",
            "parameters": {"interval_mode": "invalid_mode"},
        }
        serializer = StrategyConfigCreateSerializer(
            data=data,
            context={"request": _make_request(user)},
        )
        assert not serializer.is_valid()

    def test_create_rejects_manual_intervals_count_mismatch(self):
        user = UserFactory()
        data = {
            "name": "Snowball Bad Manual",
            "strategy_type": "snowball",
            "parameters": {
                "interval_mode": "manual",
                "manual_intervals": [10, 20],
                "r_max": 5,
            },
        }
        serializer = StrategyConfigCreateSerializer(
            data=data,
            context={"request": _make_request(user)},
        )
        assert not serializer.is_valid()
