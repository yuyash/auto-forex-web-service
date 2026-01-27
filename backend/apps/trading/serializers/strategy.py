"""Serializers for strategy configuration."""

from rest_framework import serializers
from rest_framework.request import Request

from apps.trading.models import StrategyConfiguration


class StrategyConfigDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for strategy configuration full details.
    """

    user_id = serializers.IntegerField(source="user.id", read_only=True)
    is_in_use = serializers.SerializerMethodField()

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
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "user_id", "is_in_use", "created_at", "updated_at"]

    def get_is_in_use(self, obj: StrategyConfiguration) -> bool:
        """Get whether configuration is in use by active tasks."""
        return obj.is_in_use()


class StrategyConfigListSerializer(serializers.ModelSerializer):
    """
    Serializer for strategy configuration list view (summary only).
    """

    user_id = serializers.IntegerField(source="user.id", read_only=True)
    is_in_use = serializers.SerializerMethodField()

    class Meta:  # pylint: disable=missing-class-docstring,too-few-public-methods
        model = StrategyConfiguration
        fields = [
            "id",
            "user_id",
            "name",
            "strategy_type",
            "description",
            "is_in_use",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_is_in_use(self, obj: StrategyConfiguration) -> bool:
        """Get whether configuration is in use by active tasks."""
        return obj.is_in_use()


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
        from apps.trading.services.registry import registry

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

    def validate(self, attrs: dict) -> dict:
        """Validate parameters against strategy schema."""
        strategy_type = attrs.get("strategy_type")
        parameters = attrs.get("parameters", {})

        normalized_parameters = parameters
        if strategy_type == "floor":
            normalized_parameters = self._normalize_floor_parameters(parameters)

        if strategy_type:
            # Create temporary config for validation
            temp_config = StrategyConfiguration(
                strategy_type=strategy_type,
                parameters=normalized_parameters,
            )

            is_valid, error_message = temp_config.validate_parameters()
            if not is_valid:
                raise serializers.ValidationError({"parameters": error_message})

        attrs["parameters"] = normalized_parameters
        return attrs

    @staticmethod
    def _normalize_floor_parameters(parameters: dict) -> dict:
        """Drop unused floor strategy fields based on progression choices."""
        normalized = dict(parameters)

        # Rename legacy scaling fields to retracement lot fields.

        # retracement_trigger_base is deprecated; always derive from max retracements
        normalized.pop("retracement_trigger_base", None)

        retracement_progression = normalized.get("retracement_trigger_progression", "additive")
        if retracement_progression not in {"additive", "exponential"}:
            normalized.pop("retracement_trigger_increment", None)

        lot_progression = normalized.get("lot_size_progression", "additive")
        if lot_progression not in {"additive", "exponential"}:
            normalized.pop("lot_size_increment", None)

        return normalized

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

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class StrategyListSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    """
    Serializer for listing available strategies.
    """

    id = serializers.CharField(help_text="Strategy identifier")
    name = serializers.CharField(help_text="Strategy name")
    class_name = serializers.CharField(help_text="Strategy class name")
    description = serializers.CharField(help_text="Strategy description")
    config_schema = serializers.JSONField(help_text="Configuration schema")


class StrategyConfigSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    """
    Serializer for strategy configuration schema.
    """

    strategy_id = serializers.CharField(help_text="Strategy identifier")
    config_schema = serializers.JSONField(help_text="Configuration schema")
