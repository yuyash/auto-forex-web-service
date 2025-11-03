"""
Strategy configuration API views.

This module contains views for:
- Listing available strategies
- Getting strategy configuration schemas
- Starting and stopping strategies
- Getting strategy status
- Updating strategy configuration

Requirements: 5.1, 5.2, 5.3, 5.4, 5.5
"""

import logging

from django.db import transaction

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import OandaAccount

from .models import Strategy, StrategyState
from .serializers import (
    StrategyConfigSerializer,
    StrategyListSerializer,
    StrategySerializer,
    StrategyStartSerializer,
    StrategyStatusSerializer,
)
from .strategy_registry import registry

logger = logging.getLogger(__name__)


class StrategyListView(APIView):
    """
    API endpoint for listing available strategies.

    GET /api/strategies
    - List all registered strategies with their configuration schemas
    - Returns strategy name, description, and config schema

    Requirements: 5.1
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        """
        List all available strategies.

        Args:
            request: HTTP request

        Returns:
            Response with list of strategies
        """
        strategies_info = registry.get_all_strategies_info()

        # Convert to list format for serializer
        strategies_list = [
            {
                "id": name,
                "name": info["name"],
                "class_name": info["class_name"],
                "description": info["description"],
                "config_schema": info["config_schema"],
            }
            for name, info in strategies_info.items()
        ]

        serializer = StrategyListSerializer(strategies_list, many=True)

        logger.info(
            "Strategies list retrieved",
            extra={
                "user_id": request.user.id,
                "strategy_count": len(strategies_list),
            },
        )

        return Response(serializer.data, status=status.HTTP_200_OK)


class StrategyConfigView(APIView):
    """
    API endpoint for getting strategy configuration schema.

    GET /api/strategies/{id}/config
    - Get configuration schema for a specific strategy
    - Returns JSON schema describing required and optional parameters

    Requirements: 5.1
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, strategy_id: str) -> Response:
        """
        Get configuration schema for a strategy.

        Args:
            request: HTTP request
            strategy_id: Strategy identifier

        Returns:
            Response with configuration schema
        """
        try:
            config_schema = registry.get_config_schema(strategy_id)

            serializer = StrategyConfigSerializer(
                {
                    "strategy_id": strategy_id,
                    "config_schema": config_schema,
                }
            )

            logger.info(
                "Strategy config schema retrieved",
                extra={
                    "user_id": request.user.id,
                    "strategy_id": strategy_id,
                },
            )

            return Response(serializer.data, status=status.HTTP_200_OK)

        except KeyError as e:
            logger.warning(
                "Strategy not found",
                extra={
                    "user_id": request.user.id,
                    "strategy_id": strategy_id,
                    "error": str(e),
                },
            )
            return Response(
                {"error": str(e)},
                status=status.HTTP_404_NOT_FOUND,
            )


class AccountStrategyStartView(APIView):
    """
    API endpoint for starting a strategy on an account.

    POST /api/accounts/{id}/strategy/start
    - Start a strategy for a specific OANDA account
    - Requires strategy_type, config, and instruments
    - Creates Strategy and StrategyState records
    - Validates configuration before starting

    Requirements: 5.2, 5.3, 5.4
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, account_id: int) -> Response:
        """
        Start a strategy for an account.

        Args:
            request: HTTP request with strategy configuration
            account_id: OANDA account ID

        Returns:
            Response with created strategy details
        """
        # Get the account and verify ownership
        try:
            account = OandaAccount.objects.get(id=account_id, user=request.user.id)
        except OandaAccount.DoesNotExist:
            logger.warning(
                "Account not found or access denied",
                extra={
                    "user_id": request.user.id,
                    "account_id": account_id,
                },
            )
            return Response(
                {"error": "Account not found or access denied"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check if account already has an active strategy
        if Strategy.objects.filter(account=account, is_active=True).exists():
            logger.warning(
                "Account already has an active strategy",
                extra={
                    "user_id": request.user.id,
                    "account_id": account_id,
                },
            )
            return Response(
                {"error": "Account already has an active strategy. Stop it first."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate request data
        serializer = StrategyStartSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST,
            )

        strategy_type = serializer.validated_data["strategy_type"]
        config = serializer.validated_data["config"]
        instruments = serializer.validated_data["instruments"]

        # Verify strategy exists in registry
        try:
            strategy_class = registry.get_strategy_class(strategy_type)
        except KeyError as e:
            logger.warning(
                "Strategy type not found",
                extra={
                    "user_id": request.user.id,
                    "strategy_type": strategy_type,
                    "error": str(e),
                },
            )
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Create and start strategy
        strategy_data = {
            "account": account,
            "strategy_type": strategy_type,
            "config": config,
            "instruments": instruments,
            "strategy_class": strategy_class,
            "account_id": account_id,
        }
        return self._create_and_start_strategy(strategy_data)

    def _create_and_start_strategy(self, strategy_data: dict) -> Response:
        """Create and start a strategy with validation."""
        account = strategy_data["account"]
        strategy_type = strategy_data["strategy_type"]
        config = strategy_data["config"]
        instruments = strategy_data["instruments"]
        strategy_class = strategy_data["strategy_class"]
        account_id = strategy_data["account_id"]
        try:
            with transaction.atomic():
                # Create Strategy record
                strategy = Strategy.objects.create(
                    account=account,
                    strategy_type=strategy_type,
                    config=config,
                    instruments=instruments,
                    is_active=False,
                )

                # Create StrategyState record
                StrategyState.objects.create(strategy=strategy)

                # Instantiate strategy class to validate config
                strategy_instance = strategy_class(strategy)
                strategy_instance.validate_config(config)

                # If validation passes, activate the strategy
                strategy.start()

                logger.info(
                    "Strategy started",
                    extra={
                        "user_id": self.request.user.id,
                        "account_id": account_id,
                        "strategy_id": strategy.id,
                        "strategy_type": strategy_type,
                    },
                )

                # Return strategy details
                response_serializer = StrategySerializer(strategy)
                return Response(
                    response_serializer.data,
                    status=status.HTTP_201_CREATED,
                )

        except ValueError as e:
            logger.warning(
                "Strategy configuration validation failed",
                extra={
                    "user_id": self.request.user.id,
                    "strategy_type": strategy_type,
                    "error": str(e),
                },
            )
            return Response(
                {"error": f"Configuration validation failed: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except (KeyError, TypeError, AttributeError) as e:
            logger.error(
                "Failed to start strategy",
                extra={
                    "user_id": self.request.user.id,
                    "account_id": account_id,
                    "strategy_type": strategy_type,
                    "error": str(e),
                },
                exc_info=True,
            )
            return Response(
                {"error": f"Failed to start strategy: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class AccountStrategyStopView(APIView):
    """
    API endpoint for stopping a strategy on an account.

    POST /api/accounts/{id}/strategy/stop
    - Stop the active strategy for a specific OANDA account
    - Sets is_active to False and records stopped_at timestamp

    Requirements: 5.4, 5.5
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, account_id: int) -> Response:
        """
        Stop the active strategy for an account.

        Args:
            request: HTTP request
            account_id: OANDA account ID

        Returns:
            Response with stopped strategy details
        """
        # Get the account and verify ownership
        try:
            account = OandaAccount.objects.get(id=account_id, user=request.user.id)
        except OandaAccount.DoesNotExist:
            logger.warning(
                "Account not found or access denied",
                extra={
                    "user_id": request.user.id,
                    "account_id": account_id,
                },
            )
            return Response(
                {"error": "Account not found or access denied"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Get the active strategy
        try:
            strategy = Strategy.objects.get(account=account, is_active=True)
        except Strategy.DoesNotExist:
            logger.warning(
                "No active strategy found for account",
                extra={
                    "user_id": request.user.id,
                    "account_id": account_id,
                },
            )
            return Response(
                {"error": "No active strategy found for this account"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Stop the strategy
        strategy.stop()

        logger.info(
            "Strategy stopped",
            extra={
                "user_id": request.user.id,
                "account_id": account_id,
                "strategy_id": strategy.id,
                "strategy_type": strategy.strategy_type,
            },
        )

        # Return strategy details
        serializer = StrategySerializer(strategy)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AccountStrategyStatusView(APIView):
    """
    API endpoint for getting strategy status for an account.

    GET /api/accounts/{id}/strategy/status
    - Get the current strategy status for a specific OANDA account
    - Returns strategy details, state, and performance metrics

    Requirements: 5.5
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, account_id: int) -> Response:
        """
        Get strategy status for an account.

        Args:
            request: HTTP request
            account_id: OANDA account ID

        Returns:
            Response with strategy status
        """
        # Get the account and verify ownership
        try:
            account = OandaAccount.objects.get(id=account_id, user=request.user.id)
        except OandaAccount.DoesNotExist:
            logger.warning(
                "Account not found or access denied",
                extra={
                    "user_id": request.user.id,
                    "account_id": account_id,
                },
            )
            return Response(
                {"error": "Account not found or access denied"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Get the active strategy (if any)
        try:
            strategy = Strategy.objects.get(account=account, is_active=True)
            has_active_strategy = True
        except Strategy.DoesNotExist:
            # No active strategy, return idle status
            has_active_strategy = False
            strategy = None

        if not has_active_strategy:
            return Response(
                {
                    "account_id": account_id,
                    "has_active_strategy": False,
                    "status": "idle",
                    "strategy": None,
                },
                status=status.HTTP_200_OK,
            )

        # Get strategy state
        strategy_state = None
        if strategy and hasattr(strategy, "state"):
            strategy_state = strategy.state

        # Build status response
        serializer = StrategyStatusSerializer(
            {
                "account_id": account_id,
                "has_active_strategy": True,
                "status": "trading",
                "strategy": strategy,
                "strategy_state": strategy_state,
            }
        )

        logger.info(
            "Strategy status retrieved",
            extra={
                "user_id": request.user.id,
                "account_id": account_id,
                "strategy_id": strategy.id if strategy else None,
            },
        )

        return Response(serializer.data, status=status.HTTP_200_OK)


class AccountStrategyConfigView(APIView):
    """
    API endpoint for updating strategy configuration.

    PUT /api/accounts/{id}/strategy/config
    - Update configuration for the active strategy
    - Validates new configuration before applying
    - Strategy must be stopped to update configuration

    Requirements: 5.2, 5.3
    """

    permission_classes = [IsAuthenticated]

    def put(self, request: Request, account_id: int) -> Response:
        """
        Update strategy configuration for an account.

        Args:
            request: HTTP request with new configuration
            account_id: OANDA account ID

        Returns:
            Response with updated strategy details
        """
        # Get the account and verify ownership
        try:
            account = OandaAccount.objects.get(id=account_id, user=request.user.id)
        except OandaAccount.DoesNotExist:
            logger.warning(
                "Account not found or access denied",
                extra={
                    "user_id": request.user.id,
                    "account_id": account_id,
                },
            )
            return Response(
                {"error": "Account not found or access denied"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Get the most recent strategy (active or inactive)
        try:
            strategy = Strategy.objects.filter(account=account).latest("created_at")
        except Strategy.DoesNotExist:
            logger.warning(
                "No strategy found for account",
                extra={
                    "user_id": request.user.id,
                    "account_id": account_id,
                },
            )
            return Response(
                {"error": "No strategy found for this account"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check if strategy is active
        if strategy.is_active:
            logger.warning(
                "Cannot update config while strategy is active",
                extra={
                    "user_id": request.user.id,
                    "account_id": account_id,
                    "strategy_id": strategy.id,
                },
            )
            return Response(
                {"error": "Cannot update configuration while strategy is active. Stop it first."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate request data
        if "config" not in request.data:
            return Response(
                {"error": "Missing 'config' field in request"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        new_config = request.data["config"]

        # Update configuration
        return self._update_strategy_config(strategy, new_config, account_id)

    def _update_strategy_config(
        self, strategy: Strategy, new_config: dict, account_id: int
    ) -> Response:
        """Update and validate strategy configuration."""
        try:
            strategy_class = registry.get_strategy_class(strategy.strategy_type)
            strategy_instance = strategy_class(strategy)
            strategy_instance.validate_config(new_config)

            # Update configuration
            strategy.update_config(new_config)

            logger.info(
                "Strategy configuration updated",
                extra={
                    "user_id": self.request.user.id,
                    "account_id": account_id,
                    "strategy_id": strategy.id,
                },
            )

            # Return updated strategy
            serializer = StrategySerializer(strategy)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except KeyError as e:
            logger.warning(
                "Strategy type not found",
                extra={
                    "user_id": self.request.user.id,
                    "strategy_type": strategy.strategy_type,
                    "error": str(e),
                },
            )
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except ValueError as e:
            logger.warning(
                "Configuration validation failed",
                extra={
                    "user_id": self.request.user.id,
                    "strategy_id": strategy.id,
                    "error": str(e),
                },
            )
            return Response(
                {"error": f"Configuration validation failed: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except (TypeError, AttributeError) as e:
            logger.error(
                "Failed to update strategy configuration",
                extra={
                    "user_id": self.request.user.id,
                    "account_id": account_id,
                    "strategy_id": strategy.id,
                    "error": str(e),
                },
                exc_info=True,
            )
            return Response(
                {"error": f"Failed to update configuration: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
