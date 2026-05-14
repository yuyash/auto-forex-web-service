"""Serializers for instrument metadata payloads."""

from rest_framework import serializers


class InstrumentMetadataSerializer(serializers.Serializer):
    """Serializer for instrument metadata derived from the instrument symbol."""

    normalized_name = serializers.CharField()
    base_currency = serializers.CharField()
    quote_currency = serializers.CharField()
    pip_size = serializers.CharField()
    is_high_value_quote = serializers.BooleanField()


class TaskInstrumentContextSerializer(serializers.Serializer):
    """Serializer for task-level instrument and pip-size diagnostics."""

    instrument = serializers.CharField()
    instrument_metadata = InstrumentMetadataSerializer()
    configured_pip_size = serializers.CharField(allow_blank=True)
    default_pip_size = serializers.CharField()
    effective_pip_size = serializers.CharField()
    pip_size_source = serializers.CharField()
    pip_size_matches_instrument = serializers.BooleanField()
