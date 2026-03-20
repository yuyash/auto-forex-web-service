"""Serializers for strategy visualization responses."""

from rest_framework import serializers


class StrategyVisualizationSerializer(serializers.Serializer):
    """Serializer for strategy visualization read model."""

    strategy_type = serializers.CharField()
    supported = serializers.BooleanField()
    execution_id = serializers.CharField(allow_null=True)
    generated_at = serializers.DateTimeField(allow_null=True)
    summary = serializers.JSONField()
    view_model = serializers.JSONField()
    message = serializers.CharField(required=False, allow_blank=True)
