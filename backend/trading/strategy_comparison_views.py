"""
Views for strategy comparison operations.

This module contains views for:
- Creating and executing parallel strategy comparisons
- Retrieving comparison results

Requirements: 5.1, 5.3, 12.4
"""

import logging
from datetime import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .backtest_models import StrategyComparison
from .historical_data_loader import HistoricalDataLoader
from .parallel_strategy_executor import (
    ParallelStrategyExecutor,
    StrategyComparisonConfig,
    StrategyComparisonEngine,
)

logger = logging.getLogger(__name__)

User = get_user_model()


class StrategyCompareView(APIView):  # pylint: disable=too-many-instance-attributes
    """
    API endpoint for executing parallel strategy comparison.

    POST /api/strategies/compare
    - Execute parallel comparison of multiple strategies
    - Validate strategy configurations
    - Return comparison ID for result retrieval

    Request Body:
        {
            "strategy_configs": [
                {
                    "strategy_type": "floor",
                    "name": "Floor Strategy A",
                    "config": {...}
                },
                {
                    "strategy_type": "trend_following",
                    "name": "Trend Following B",
                    "config": {...}
                }
            ],
            "instruments": ["EUR_USD", "GBP_USD"],
            "start_date": "2024-01-01T00:00:00Z",
            "end_date": "2024-12-31T23:59:59Z",
            "initial_balance": 10000,
            "commission_per_trade": 2.0
        }

    Requirements: 5.1, 5.3, 12.4
    """

    permission_classes = [IsAuthenticated]

    def _validate_request_data(  # pylint: disable=too-many-return-statements
        self, request_data: dict
    ) -> tuple[Response | None, dict | None]:
        """Validate request data and return error response if invalid."""
        strategy_configs = request_data.get("strategy_configs", [])
        instruments = request_data.get("instruments", [])
        start_date_str = request_data.get("start_date")
        end_date_str = request_data.get("end_date")

        if not strategy_configs:
            return (
                Response(
                    {"error": "strategy_configs is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                ),
                None,
            )

        if len(strategy_configs) > 10:
            return (
                Response(
                    {"error": "Maximum 10 strategies allowed for comparison"},
                    status=status.HTTP_400_BAD_REQUEST,
                ),
                None,
            )

        if not instruments:
            return (
                Response(
                    {"error": "instruments is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                ),
                None,
            )

        if not start_date_str or not end_date_str:
            return (
                Response(
                    {"error": "start_date and end_date are required"},
                    status=status.HTTP_400_BAD_REQUEST,
                ),
                None,
            )

        # Validate strategy configs
        for i, config in enumerate(strategy_configs):
            if "strategy_type" not in config:
                return (
                    Response(
                        {"error": f"strategy_type missing in strategy_configs[{i}]"},
                        status=status.HTTP_400_BAD_REQUEST,
                    ),
                    None,
                )
            if "config" not in config:
                return (
                    Response(
                        {"error": f"config missing in strategy_configs[{i}]"},
                        status=status.HTTP_400_BAD_REQUEST,
                    ),
                    None,
                )

        # Parse dates
        try:
            start_date = datetime.fromisoformat(start_date_str.replace("Z", "+00:00"))
            end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
        except ValueError as e:
            return (
                Response(
                    {"error": f"Invalid date format: {e}"},
                    status=status.HTTP_400_BAD_REQUEST,
                ),
                None,
            )

        return None, {
            "strategy_configs": strategy_configs,
            "instruments": instruments,
            "start_date": start_date,
            "end_date": end_date,
            "initial_balance": request_data.get("initial_balance", 10000),
            "commission_per_trade": request_data.get("commission_per_trade", 0),
        }

    def post(self, request: Request) -> Response:  # pylint: disable=too-many-locals
        """
        Execute parallel strategy comparison.

        Args:
            request: HTTP request with comparison configuration

        Returns:
            Response with comparison ID and initial status
        """
        # Ensure user is authenticated
        if not isinstance(request.user, User):
            return Response(
                {"error": "Authentication required"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Validate request data
        error_response, validated_data = self._validate_request_data(request.data)
        if error_response:
            return error_response

        assert validated_data is not None
        strategy_configs = validated_data["strategy_configs"]
        instruments = validated_data["instruments"]
        start_date = validated_data["start_date"]
        end_date = validated_data["end_date"]
        initial_balance = validated_data["initial_balance"]
        commission_per_trade = validated_data["commission_per_trade"]

        # Create comparison record
        comparison = StrategyComparison.objects.create(  # pylint: disable=no-member
            user=request.user,
            strategy_configs=strategy_configs,
            instruments=instruments,
            start_date=start_date,
            end_date=end_date,
            initial_balance=Decimal(str(initial_balance)),
            commission_per_trade=Decimal(str(commission_per_trade)),
            status="pending",
        )

        # Execute comparison asynchronously (in this implementation, synchronously for simplicity)
        try:
            comparison.status = "running"
            comparison.save()

            # Load historical data
            logger.info("Loading historical data for comparison %s", comparison.id)
            data_loader = HistoricalDataLoader()
            # Load data for the first instrument (simplified for now)
            tick_data = data_loader.load_data(
                instrument=instruments[0],
                start_date=start_date,
                end_date=end_date,
            )

            if not tick_data:
                raise ValueError("No historical data found for the specified period")

            # Create comparison config
            comparison_config = StrategyComparisonConfig(
                strategy_configs=strategy_configs,
                instruments=instruments,
                start_date=start_date,
                end_date=end_date,
                initial_balance=Decimal(str(initial_balance)),
                commission_per_trade=Decimal(str(commission_per_trade)),
                max_workers=min(len(strategy_configs), 10),
            )

            # Execute strategies in parallel
            logger.info("Executing %d strategies in parallel", len(strategy_configs))
            executor = ParallelStrategyExecutor(comparison_config)
            strategy_results = executor.execute_strategies(tick_data)

            # Generate comparison report
            logger.info("Generating comparison report for comparison %s", comparison.id)
            comparison_engine = StrategyComparisonEngine(strategy_results)
            comparison_report = comparison_engine.generate_comparison_report()

            # Store results
            comparison.results = comparison_report
            comparison.status = "completed"
            comparison.completed_at = timezone.now()
            comparison.save()

            logger.info(
                "Strategy comparison completed: %s",
                comparison.id,
                extra={
                    "user_id": request.user.id,
                    "comparison_id": comparison.id,
                    "total_strategies": len(strategy_configs),
                    "successful": comparison_report["successful_strategies"],
                },
            )

            return Response(
                {
                    "id": comparison.id,
                    "status": comparison.status,
                    "message": "Comparison completed successfully",
                    "total_strategies": len(strategy_configs),
                    "successful_strategies": comparison_report["successful_strategies"],
                },
                status=status.HTTP_201_CREATED,
            )

        except (ValueError, RuntimeError) as e:
            logger.error("Strategy comparison failed: %s", str(e), exc_info=True)
            comparison.status = "failed"
            comparison.error_message = str(e)
            comparison.completed_at = timezone.now()
            comparison.save()

            return Response(
                {
                    "id": comparison.id,
                    "status": "failed",
                    "error": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class StrategyCompareResultsView(APIView):
    """
    API endpoint for retrieving strategy comparison results.

    GET /api/strategies/compare/{id}/results
    - Get complete comparison results
    - Returns metrics table, equity curves, rankings, and summary

    Requirements: 5.1, 5.3, 12.4
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, comparison_id: int) -> Response:
        """
        Retrieve strategy comparison results.

        Args:
            request: HTTP request
            comparison_id: Comparison ID

        Returns:
            Response with comparison results
        """
        # Ensure user is authenticated
        if not isinstance(request.user, User):
            return Response(
                {"error": "Authentication required"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        try:
            comparison = StrategyComparison.objects.get(  # pylint: disable=no-member
                id=comparison_id,
                user=request.user,
            )
        except StrategyComparison.DoesNotExist:  # pylint: disable=no-member
            return Response(
                {"error": "Comparison not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check if comparison is completed
        if comparison.status != "completed":
            return Response(
                {
                    "id": comparison.id,
                    "status": comparison.status,
                    "error_message": comparison.error_message,
                    "message": "Comparison is not completed yet",
                },
                status=status.HTTP_200_OK,
            )

        logger.info(
            "Strategy comparison results retrieved: %s",
            comparison.id,
            extra={
                "user_id": request.user.id,
                "comparison_id": comparison.id,
            },
        )

        return Response(
            {
                "id": comparison.id,
                "status": comparison.status,
                "strategy_configs": comparison.strategy_configs,
                "instruments": comparison.instruments,
                "start_date": comparison.start_date.isoformat(),
                "end_date": comparison.end_date.isoformat(),
                "initial_balance": float(comparison.initial_balance),
                "results": comparison.results,
                "created_at": comparison.created_at.isoformat(),
                "completed_at": (
                    comparison.completed_at.isoformat() if comparison.completed_at else None
                ),
            },
            status=status.HTTP_200_OK,
        )
