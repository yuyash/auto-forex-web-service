"""
API views for listing available strategies.

This module provides endpoints for retrieving information about
registered trading strategies including their display names and schemas.

Requirements: 5.1
"""

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .strategy_registry import registry


class StrategyListView(APIView):
    """
    API endpoint for listing all available trading strategies.

    GET: Returns a list of all registered strategies with their
         identifiers, display names, and configuration schemas.

    Requirements: 5.1
    """

    permission_classes = [IsAuthenticated]

    def get(self, _request: Request) -> Response:
        """
        List all available trading strategies.

        Returns:
            Response containing:
                - strategies: List of strategy objects with:
                    - id: Strategy identifier (e.g., 'floor')
                    - name: Display name (e.g., 'Floor Strategy')
                    - description: Strategy description
                    - config_schema: Configuration schema
        """
        strategies_info = registry.get_all_strategies_info()

        # Transform to frontend-friendly format
        strategies_list = []
        for strategy_id, info in strategies_info.items():
            config_schema = info.get("config_schema", {})
            display_name = config_schema.get("display_name", strategy_id)

            strategies_list.append(
                {
                    "id": strategy_id,
                    "name": display_name,
                    "description": info.get("description", "").strip(),
                    "config_schema": config_schema,
                }
            )

        # Sort by display name for consistent ordering
        strategies_list.sort(key=lambda x: x["name"])

        return Response(
            {
                "strategies": strategies_list,
                "count": len(strategies_list),
            },
            status=status.HTTP_200_OK,
        )
