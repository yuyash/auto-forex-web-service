"""Strategy-related views."""

from typing import Any, cast

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.trading.serializers import StrategyListSerializer


class StrategyView(APIView):
    """API endpoint for listing all available trading strategies."""

    permission_classes = [IsAuthenticated]
    serializer_class = StrategyListSerializer

    @extend_schema(operation_id="trading_strategies_list", tags=["Trading"])
    def get(self, _request: Request) -> Response:
        from apps.trading.strategies.registry import registry

        strategies_info = registry.get_all_strategies_info()

        strategies_list: list[dict] = []
        for strategy_id, info in strategies_info.items():
            config_schema = info.get("config_schema", {})
            display_name = config_schema.get("display_name", strategy_id)
            strategies_list.append(
                {
                    "id": strategy_id,
                    "name": display_name,
                    "class_name": info.get("strategy_class", ""),
                    "description": (info.get("description") or "").strip(),
                    "config_schema": config_schema,
                }
            )

        strategies_list.sort(key=lambda x: x["name"])
        return Response(
            {"strategies": strategies_list, "count": len(strategies_list)},
            status=status.HTTP_200_OK,
        )


class StrategyDefaultsView(APIView):
    """API endpoint for returning default parameters for a strategy."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="trading_strategy_defaults",
        tags=["Trading"],
        responses={
            200: inline_serializer(
                "StrategyDefaultsResponse",
                fields={
                    "strategy_id": serializers.CharField(),
                    "defaults": serializers.DictField(),
                },
            ),
            404: inline_serializer(
                "StrategyDefaultsNotFound",
                fields={"detail": serializers.CharField()},
            ),
        },
        description="Get default parameters for a strategy.",
    )
    def get(self, _request: Request, strategy_id: str) -> Response:
        from apps.trading.strategies.registry import registry

        strategy_key = str(strategy_id or "").strip()
        if not registry.is_registered(strategy_key):
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        strategies_info = registry.get_all_strategies_info()
        config_schema = cast(
            dict[str, Any],
            (strategies_info.get(strategy_key) or {}).get("config_schema") or {},
        )
        properties = config_schema.get("properties")
        schema_keys: set[str] = set(properties.keys()) if isinstance(properties, dict) else set()

        defaults = registry.get_defaults(identifier=strategy_key)

        # Only return keys that are part of the schema (if schema keys are known).
        if schema_keys:
            defaults = {k: v for k, v in defaults.items() if k in schema_keys}

        return Response(
            {"strategy_id": strategy_key, "defaults": defaults},
            status=status.HTTP_200_OK,
        )
