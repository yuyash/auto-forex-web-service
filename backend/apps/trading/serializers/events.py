"""Serializers for structured event and log data."""

from typing import Any

from rest_framework import serializers

from apps.trading.models import ExecutionStrategyEvent


class StrategyEventSerializer(serializers.ModelSerializer):
    """Serializer for ExecutionStrategyEvent with structured event parsing.

    Parses the raw event JSON into a structured format with:
    - strategy_type: Strategy identifier (e.g., 'floor', 'momentum')
    - event_type: Type of event (e.g., 'initial_entry', 'retracement', 'take_profit')
    - common_data: Common fields across all events (timestamp, price, etc.)
    - strategy_data: Strategy-specific fields (layer_number, retracement_count for Floor)

    Requirements: 1.6, 15.5
    """

    # Structured fields extracted from event JSON
    parsed_event_type = serializers.SerializerMethodField()
    parsed_timestamp = serializers.SerializerMethodField()
    common_data = serializers.SerializerMethodField()
    strategy_data = serializers.SerializerMethodField()

    class Meta:  # pylint: disable=missing-class-docstring,too-few-public-methods
        model = ExecutionStrategyEvent
        fields = [
            "sequence",
            "event_type",
            "strategy_type",
            "timestamp",
            "event",
            "created_at",
            # Structured fields
            "parsed_event_type",
            "parsed_timestamp",
            "common_data",
            "strategy_data",
        ]
        read_only_fields = fields

    def get_parsed_event_type(self, obj: ExecutionStrategyEvent) -> str:
        """Extract event_type from event JSON.

        Falls back to the event_type field if not present in event JSON.
        """
        if isinstance(obj.event, dict):
            return obj.event.get("event_type", obj.event_type)
        return obj.event_type

    def get_parsed_timestamp(self, obj: ExecutionStrategyEvent) -> str | None:
        """Extract timestamp from event JSON.

        Falls back to the timestamp field if not present in event JSON.
        """
        if isinstance(obj.event, dict):
            event_timestamp = obj.event.get("timestamp")
            if event_timestamp:
                return str(event_timestamp)

        if obj.timestamp:
            return obj.timestamp.isoformat()

        return None

    def get_common_data(self, obj: ExecutionStrategyEvent) -> dict[str, Any]:
        """Extract common data fields from event JSON.

        Common fields include: price, instrument, balance, pnl, etc.
        These are fields that are commonly present across different event types.
        """
        if not isinstance(obj.event, dict):
            return {}

        common_fields = [
            "price",
            "instrument",
            "balance",
            "pnl",
            "units",
            "direction",
            "order_id",
            "position_id",
            "message",
            "description",
        ]

        common_data = {}
        for field in common_fields:
            if field in obj.event:
                common_data[field] = obj.event[field]

        return common_data

    def get_strategy_data(self, obj: ExecutionStrategyEvent) -> dict[str, Any]:
        """Extract strategy-specific data from event JSON.

        For Floor strategy events, this includes:
        - layer_number: The layer number for layer-related events
        - retracement_count: Number of retracements for retracement events
        - take_profit_layer: Layer that triggered take profit
        - volatility_locked: Whether volatility lock is active

        For other strategies, this extracts any fields not in common_data.
        """
        if not isinstance(obj.event, dict):
            return {}

        # Floor strategy specific fields
        floor_fields = [
            "layer_number",
            "retracement_count",
            "take_profit_layer",
            "volatility_locked",
            "atr",
            "atr_threshold",
            "layers",
            "total_layers",
            "entry_price",
            "current_price",
            "pip_distance",
        ]

        strategy_data = {}

        # Extract Floor strategy fields if present
        for field in floor_fields:
            if field in obj.event:
                strategy_data[field] = obj.event[field]

        # If no Floor-specific fields found, extract all non-common fields
        if not strategy_data:
            common_field_names = [
                "event_type",
                "timestamp",
                "price",
                "instrument",
                "balance",
                "pnl",
                "units",
                "direction",
                "order_id",
                "position_id",
                "message",
                "description",
            ]

            for key, value in obj.event.items():
                if key not in common_field_names:
                    strategy_data[key] = value

        return strategy_data


class StructuredLogSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    """Serializer for transforming execution logs into structured format.

    Transforms raw log entries into structured format with:
    - log_type: Type of log entry (system, strategy_event, trade, error)
    - timestamp: Log timestamp
    - level: Log level (info, warning, error)
    - message: Log message
    - data: Extracted structured data from message

    Requirements: 8.3
    """

    log_type = serializers.SerializerMethodField()
    timestamp = serializers.CharField()
    level = serializers.CharField()
    message = serializers.CharField()
    data = serializers.SerializerMethodField()

    def get_log_type(self, obj: dict[str, Any]) -> str:
        """Determine log type from message content.

        Categories:
        - system: System-level messages (started, stopped, paused, resumed)
        - strategy_event: Strategy-related events (signals, decisions)
        - trade: Trade execution messages
        - error: Error messages
        """
        message = obj.get("message", "").lower()
        level = obj.get("level", "").lower()

        # Error logs
        if level == "error" or "error" in message or "exception" in message or "failed" in message:
            return "error"

        # Trade logs
        if any(
            keyword in message
            for keyword in [
                "trade",
                "order",
                "position",
                "buy",
                "sell",
                "executed",
                "filled",
                "closed",
            ]
        ):
            return "trade"

        # Strategy event logs
        if any(
            keyword in message
            for keyword in [
                "strategy",
                "signal",
                "layer",
                "retracement",
                "take profit",
                "volatility",
                "momentum",
                "indicator",
            ]
        ):
            return "strategy_event"

        # Default to system
        return "system"

    def get_data(self, obj: dict[str, Any]) -> dict[str, Any]:
        """Extract structured data from log message.

        Attempts to parse common patterns from log messages:
        - Trade information (instrument, direction, units, price)
        - Strategy information (layer, retracement count)
        - Error information (error type, traceback)
        """
        message = obj.get("message", "")
        data: dict[str, Any] = {}

        # Try to extract instrument - look for patterns like USD_JPY, EUR_USD
        import re

        instrument_match = re.search(r"\b([A-Z]{3}_[A-Z]{3})\b", message)
        if instrument_match:
            data["instrument"] = instrument_match.group(1)

        # Try to extract direction
        if "long" in message.lower():
            data["direction"] = "long"
        elif "short" in message.lower():
            data["direction"] = "short"

        # Try to extract layer number
        if "layer" in message.lower():
            layer_match = re.search(r"layer[:\s]+(\d+)", message.lower())
            if layer_match:
                data["layer_number"] = int(layer_match.group(1))

        # Try to extract retracement count
        if "retracement" in message.lower():
            retracement_match = re.search(r"retracement[:\s]+(\d+)", message.lower())
            if retracement_match:
                data["retracement_count"] = int(retracement_match.group(1))

        # Try to extract price - look for patterns like "price 1.1000" or "at 1.1000"
        price_match = re.search(r"(?:price|at)[:\s]+([\d.]+)", message.lower())
        if price_match:
            data["price"] = price_match.group(1)

        # Try to extract units - look for patterns like "1000 units"
        units_match = re.search(r"(\d+)\s+units", message.lower())
        if units_match:
            data["units"] = units_match.group(1)

        return data
