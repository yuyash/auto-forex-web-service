"""Serializers for strategy configuration."""

import logging
from typing import Any

from rest_framework import serializers
from rest_framework.request import Request

from apps.trading.models import StrategyConfiguration

logger = logging.getLogger(__name__)


class StrategyConfigDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for strategy configuration full details.
    """

    user_id = serializers.IntegerField(source="user.id", read_only=True)
    is_in_use = serializers.SerializerMethodField()
    has_running_tasks = serializers.SerializerMethodField()

    class Meta:  # pylint: disable=missing-class-docstring,too-few-public-methods
        model = StrategyConfiguration
        fields = [
            "id",
            "user_id",
            "name",
            "strategy_type",
            "parameters",
            "description",
            "is_in_use",
            "has_running_tasks",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "user_id",
            "is_in_use",
            "has_running_tasks",
            "created_at",
            "updated_at",
        ]

    def get_is_in_use(self, obj: StrategyConfiguration) -> bool:
        """Get whether configuration is in use by active tasks."""
        return obj.is_in_use()

    def get_has_running_tasks(self, obj: StrategyConfiguration) -> bool:
        """Get whether this configuration is currently used by a running task."""
        return obj.has_active_tasks()


class StrategyConfigListSerializer(serializers.ModelSerializer):
    """
    Serializer for strategy configuration list view (summary only).
    """

    user_id = serializers.IntegerField(source="user.id", read_only=True)
    is_in_use = serializers.SerializerMethodField()
    has_running_tasks = serializers.SerializerMethodField()

    class Meta:  # pylint: disable=missing-class-docstring,too-few-public-methods
        model = StrategyConfiguration
        fields = [
            "id",
            "user_id",
            "name",
            "strategy_type",
            "description",
            "is_in_use",
            "has_running_tasks",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_is_in_use(self, obj: StrategyConfiguration) -> bool:
        """Get whether configuration is in use by active tasks."""
        return obj.is_in_use()

    def get_has_running_tasks(self, obj: StrategyConfiguration) -> bool:
        """Get whether this configuration is currently used by a running task."""
        return obj.has_active_tasks()


class StrategyConfigCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating and updating strategy configurations.

    Includes validation against strategy registry.
    """

    class Meta:  # pylint: disable=missing-class-docstring,too-few-public-methods
        model = StrategyConfiguration
        fields = [
            "name",
            "strategy_type",
            "parameters",
            "description",
        ]

    def validate_strategy_type(self, value: str) -> str:
        """Validate strategy type exists in registry."""
        from apps.trading.strategies.registry import registry

        if not registry.is_registered(value):
            available = ", ".join(registry.list_strategies())
            raise serializers.ValidationError(
                f"Strategy type '{value}' is not registered. Available strategies: {available}"
            )
        return value

    def validate_parameters(self, value: dict) -> dict:
        """Validate parameters is a dictionary."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Parameters must be a JSON object")
        return value

    def validate_name(self, value: str) -> str:
        """Validate configuration name uniqueness per user."""
        request: Request = self.context["request"]
        query = StrategyConfiguration.objects.filter(user=request.user, name=value)
        if self.instance is not None:
            query = query.exclude(pk=self.instance.pk)
        if query.exists():
            raise serializers.ValidationError("A configuration with this name already exists.")
        return value

    def validate(self, attrs: dict) -> dict:
        """Validate parameters against strategy schema."""
        from apps.trading.strategies.registry import registry

        instance = getattr(self, "instance", None)
        strategy_type = attrs.get("strategy_type") or (
            instance.strategy_type if instance is not None else None
        )
        has_parameters = "parameters" in attrs
        parameters_raw = (
            attrs.get("parameters")
            if has_parameters
            else (instance.parameters if instance is not None else {})
        )
        if parameters_raw is None:
            parameters: dict[str, Any] = {}
        elif isinstance(parameters_raw, dict):
            parameters = dict(parameters_raw)
        else:
            raise serializers.ValidationError({"parameters": "Parameters must be a JSON object"})

        normalized_parameters: dict[str, Any] = parameters

        if strategy_type:
            try:
                normalized_parameters = registry.normalize_parameters(
                    identifier=strategy_type,
                    parameters=parameters,
                )
                registry.validate_parameters(
                    identifier=strategy_type,
                    parameters=normalized_parameters,
                )
            except ValueError:
                logger.warning(
                    "Strategy configuration parameter validation failed",
                    extra={"strategy_type": strategy_type},
                    exc_info=True,
                )
                raise serializers.ValidationError(
                    {"parameters": "Invalid strategy parameters."}
                ) from None

        attrs["parameters"] = normalized_parameters
        return attrs

    def create(self, validated_data: dict) -> StrategyConfiguration:
        """Create strategy configuration with user from context."""
        request: Request = self.context["request"]
        user = request.user
        # Type narrowing: request.user is authenticated in view
        return StrategyConfiguration.objects.create_for_user(user, **validated_data)

    def update(
        self, instance: StrategyConfiguration, validated_data: dict
    ) -> StrategyConfiguration:
        """Update strategy configuration."""
        from apps.trading.services.task_audit import (
            audit_strategy_config_update,
            changed_field_values,
        )

        if instance.has_active_tasks():
            raise serializers.ValidationError(
                {
                    "detail": (
                        "Strategy configurations cannot be updated while tasks using this "
                        "configuration are running."
                    )
                }
            )

        # Don't allow updating strategy_type if config is in use
        if (
            "strategy_type" in validated_data
            and instance.is_in_use()
            and validated_data["strategy_type"] != instance.strategy_type
        ):
            raise serializers.ValidationError(
                {
                    "strategy_type": "Cannot change strategy type for configuration "
                    "that is in use by active tasks"
                }
            )

        changes = changed_field_values(instance, validated_data)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        audit_strategy_config_update(config=instance, changes=changes)
        return instance


class StrategyListSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    """
    Serializer for listing available strategies.
    """

    id = serializers.CharField(help_text="Strategy identifier")
    name = serializers.CharField(help_text="Strategy name")
    class_name = serializers.CharField(help_text="Strategy class name")
    description = serializers.CharField(help_text="Strategy description")
    capabilities = serializers.JSONField(help_text="Strategy capabilities")
    config_schema = serializers.JSONField(help_text="Configuration schema")


class StrategyConfigSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    """
    Serializer for strategy configuration schema.
    """

    strategy_id = serializers.CharField(help_text="Strategy identifier")
    config_schema = serializers.JSONField(help_text="Configuration schema")
