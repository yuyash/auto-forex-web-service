"""Execution-specific API endpoints.

These endpoints work directly with execution IDs rather than task IDs,
allowing access to specific historical executions and enabling comparison
across multiple executions.

Requirements: 6.13, 6.14, 6.15, 6.16, 6.17, 6.18, 6.19, 6.20
"""

from datetime import datetime

from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.trading.enums import TaskType
from apps.trading.models import (
    Executions,
    StrategyEvents,
    TradeLogs,
    TradingMetrics,
    TradingTasks,
)
from apps.trading.models.tasks import BacktestTasks
from apps.trading.services.granularity_aggregation import GranularityAggregationService
from apps.trading.views._helpers import _paginate_list_by_page


class ExecutionDetailView(APIView):
    """Get full execution details.

    GET /api/trading/executions/{id}/
    Returns complete execution object with all related data.

    Requirements: 6.13
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="get_execution_detail",
        tags=["executions"],
        summary="Get execution details",
        description="Retrieve complete details for a specific execution including status, timing, resource usage, and logs.",
        responses={
            200: {
                "description": "Execution details retrieved successfully",
                "content": {
                    "application/json": {
                        "example": {
                            "id": 1,
                            "task_type": "backtest",
                            "task_id": 123,
                            "execution_number": 1,
                            "status": "completed",
                            "progress": 100.0,
                            "started_at": "2024-01-01T00:00:00Z",
                            "completed_at": "2024-01-01T01:00:00Z",
                            "duration": 3600,
                            "cpu_limit_cores": 2.0,
                            "memory_limit_mb": "2048",
                            "peak_memory_mb": "1536",
                            "error_message": None,
                            "error_traceback": None,
                            "logs": [],
                            "created_at": "2024-01-01T00:00:00Z",
                        }
                    }
                },
            },
            403: {"description": "Access denied - user does not own this execution's task"},
            404: {"description": "Execution not found"},
        },
    )
    def get(self, request: Request, execution_id: int) -> Response:
        """Get full execution details.

        Returns:
            Complete execution details including:
            - Basic execution info (id, task_type, task_id, status, etc.)
            - Timing information (started_at, completed_at, duration)
            - Resource usage (cpu_limit_cores, memory_limit_mb, peak_memory_mb)
            - Error information (error_message, error_traceback)
            - Logs array

        Requirements: 6.13
        """
        try:
            execution = Executions.objects.get(id=execution_id)
        except Executions.DoesNotExist:
            return Response(
                {"error": "Execution not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Verify user has access to this execution's task
        if execution.task_type == TaskType.BACKTEST:
            try:
                BacktestTasks.objects.get(id=execution.task_id, user=request.user.pk)
            except BacktestTasks.DoesNotExist:
                return Response(
                    {"error": "Access denied"},
                    status=status.HTTP_403_FORBIDDEN,
                )
        elif execution.task_type == TaskType.TRADING:
            try:
                TradingTasks.objects.get(id=execution.task_id, user=request.user.pk)
            except TradingTasks.DoesNotExist:
                return Response(
                    {"error": "Access denied"},
                    status=status.HTTP_403_FORBIDDEN,
                )

        response_data = {
            "id": execution.pk,
            "task_type": execution.task_type,
            "task_id": execution.task_id,
            "execution_number": execution.execution_number,
            "status": execution.status,
            "progress": execution.progress,
            "started_at": execution.started_at.isoformat() if execution.started_at else None,
            "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
            "duration": execution.get_duration(),
            "cpu_limit_cores": execution.cpu_limit_cores,
            "memory_limit_mb": (
                str(execution.memory_limit_mb) if execution.memory_limit_mb else None
            ),
            "peak_memory_mb": str(execution.peak_memory_mb) if execution.peak_memory_mb else None,
            "error_message": execution.error_message or None,
            "error_traceback": execution.error_traceback or None,
            "logs": execution.logs or [],
            "created_at": execution.created_at.isoformat(),
        }

        return Response(response_data, status=status.HTTP_200_OK)


class ExecutionLogsView(APIView):
    """Get execution logs with filtering.

    GET /api/trading/executions/{id}/logs/
    Supports filtering by level, start_time, end_time, limit.

    Requirements: 6.14
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="get_execution_logs",
        tags=["executions"],
        summary="Get execution logs",
        description="Retrieve execution logs with optional filtering by level, time range, and limit.",
        parameters=[
            OpenApiParameter(
                name="level",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Filter by log level (debug, info, warning, error)",
                required=False,
                enum=["debug", "info", "warning", "error"],
            ),
            OpenApiParameter(
                name="start_time",
                type=OpenApiTypes.DATETIME,
                location=OpenApiParameter.QUERY,
                description="Filter logs after this timestamp (ISO format)",
                required=False,
            ),
            OpenApiParameter(
                name="end_time",
                type=OpenApiTypes.DATETIME,
                location=OpenApiParameter.QUERY,
                description="Filter logs before this timestamp (ISO format)",
                required=False,
            ),
            OpenApiParameter(
                name="limit",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Maximum number of logs to return (default: 100, max: 1000)",
                required=False,
            ),
        ],
        responses={
            200: {
                "description": "Logs retrieved successfully",
                "content": {
                    "application/json": {
                        "example": {
                            "execution_id": 1,
                            "task_type": "backtest",
                            "task_id": 123,
                            "logs": [
                                {
                                    "timestamp": "2024-01-01T00:00:00Z",
                                    "level": "info",
                                    "message": "Strategy initialized",
                                }
                            ],
                            "count": 1,
                            "next": None,
                            "previous": None,
                        }
                    }
                },
            },
            403: {"description": "Access denied"},
            404: {"description": "Execution not found"},
        },
    )
    def get(self, request: Request, execution_id: int) -> Response:
        """Get execution logs with filtering.

        Query Parameters:
            level: Filter by log level (debug, info, warning, error)
            start_time: Filter logs after this timestamp (ISO format)
            end_time: Filter logs before this timestamp (ISO format)
            limit: Maximum number of logs to return (default: 100, max: 1000)

        Returns:
            Filtered logs array with pagination

        Requirements: 6.14
        """
        try:
            execution = Executions.objects.get(id=execution_id)
        except Executions.DoesNotExist:
            return Response(
                {"error": "Execution not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Verify user has access to this execution's task
        if execution.task_type == TaskType.BACKTEST:
            try:
                BacktestTasks.objects.get(id=execution.task_id, user=request.user.pk)
            except BacktestTasks.DoesNotExist:
                return Response(
                    {"error": "Access denied"},
                    status=status.HTTP_403_FORBIDDEN,
                )
        elif execution.task_type == TaskType.TRADING:
            try:
                TradingTasks.objects.get(id=execution.task_id, user=request.user.pk)
            except TradingTasks.DoesNotExist:
                return Response(
                    {"error": "Access denied"},
                    status=status.HTTP_403_FORBIDDEN,
                )

        # Get logs from execution
        logs = execution.logs or []

        # Apply filters
        level_filter = request.query_params.get("level")
        start_time_str = request.query_params.get("start_time")
        end_time_str = request.query_params.get("end_time")

        filtered_logs = []
        for log_entry in logs:
            # Filter by level
            if level_filter and log_entry.get("level", "").lower() != level_filter.lower():
                continue

            # Filter by start_time
            if start_time_str:
                try:
                    log_timestamp = datetime.fromisoformat(log_entry.get("timestamp", ""))
                    start_time = datetime.fromisoformat(start_time_str)
                    if log_timestamp < start_time:
                        continue
                except (ValueError, TypeError):
                    pass

            # Filter by end_time
            if end_time_str:
                try:
                    log_timestamp = datetime.fromisoformat(log_entry.get("timestamp", ""))
                    end_time = datetime.fromisoformat(end_time_str)
                    if log_timestamp > end_time:
                        continue
                except (ValueError, TypeError):
                    pass

            filtered_logs.append(log_entry)

        # Apply limit
        limit_str = request.query_params.get("limit", "100")
        try:
            limit = min(int(limit_str), 1000)  # Max 1000
        except ValueError:
            limit = 100

        # Paginate
        pagination = _paginate_list_by_page(
            request=request,
            items=filtered_logs,
            base_url=f"/api/trading/executions/{execution_id}/logs/",
            default_page_size=limit,
            max_page_size=1000,
            extra_query={
                "level": level_filter,
                "start_time": start_time_str,
                "end_time": end_time_str,
                "limit": limit_str,
            },
        )

        return Response(
            {
                "execution_id": execution.pk,
                "task_type": execution.task_type,
                "task_id": execution.task_id,
                "logs": pagination["results"],
                "count": pagination["count"],
                "next": pagination["next"],
                "previous": pagination["previous"],
            },
            status=status.HTTP_200_OK,
        )


class ExecutionStatusView(APIView):
    """Get current execution status with progress.

    GET /api/trading/executions/{id}/status/
    Returns current status with progress information.

    Requirements: 6.15
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="get_execution_status",
        tags=["executions"],
        summary="Get execution status",
        description="Retrieve current execution status including progress, timing, and estimated completion.",
        responses={
            200: {
                "description": "Status retrieved successfully",
                "content": {
                    "application/json": {
                        "example": {
                            "execution_id": 1,
                            "task_type": "backtest",
                            "task_id": 123,
                            "execution_number": 1,
                            "status": "running",
                            "progress": 75.0,
                            "started_at": "2024-01-01T00:00:00Z",
                            "completed_at": None,
                            "error_message": None,
                            "estimated_remaining_seconds": 1200,
                        }
                    }
                },
            },
            403: {"description": "Access denied"},
            404: {"description": "Execution not found"},
        },
    )
    def get(self, request: Request, execution_id: int) -> Response:
        """Get execution status with progress.

        Returns:
            Current execution status including:
            - status: Current status (created, running, completed, failed, etc.)
            - progress: Progress percentage (0-100)
            - started_at: Start timestamp
            - completed_at: Completion timestamp (if completed)
            - error_message: Error message (if failed)
            - estimated_remaining_seconds: Estimated time remaining (if running)

        Requirements: 6.15
        """
        try:
            execution = Executions.objects.get(id=execution_id)
        except Executions.DoesNotExist:
            return Response(
                {"error": "Execution not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Verify user has access to this execution's task
        if execution.task_type == TaskType.BACKTEST:
            try:
                BacktestTasks.objects.get(id=execution.task_id, user=request.user.pk)
            except BacktestTasks.DoesNotExist:
                return Response(
                    {"error": "Access denied"},
                    status=status.HTTP_403_FORBIDDEN,
                )
        elif execution.task_type == TaskType.TRADING:
            try:
                TradingTasks.objects.get(id=execution.task_id, user=request.user.pk)
            except TradingTasks.DoesNotExist:
                return Response(
                    {"error": "Access denied"},
                    status=status.HTTP_403_FORBIDDEN,
                )

        # Calculate estimated remaining time if running
        estimated_remaining_seconds = None
        if execution.status == "running" and execution.started_at and execution.progress > 0:
            from django.utils import timezone

            elapsed = (timezone.now() - execution.started_at).total_seconds()
            if execution.progress > 0:
                estimated_total = elapsed / (execution.progress / 100.0)
                estimated_remaining_seconds = int(estimated_total - elapsed)

        response_data = {
            "execution_id": execution.pk,
            "task_type": execution.task_type,
            "task_id": execution.task_id,
            "execution_number": execution.execution_number,
            "status": execution.status,
            "progress": execution.progress,
            "started_at": execution.started_at.isoformat() if execution.started_at else None,
            "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
            "error_message": execution.error_message or None,
            "estimated_remaining_seconds": estimated_remaining_seconds,
        }

        return Response(response_data, status=status.HTTP_200_OK)


class ExecutionEventsView(APIView):
    """Get strategy events for a specific execution with incremental fetching.

    GET /api/trading/executions/{id}/events/
    Supports ?since_sequence= for incremental fetching and ?event_type= for filtering.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="get_execution_events",
        tags=["executions"],
        summary="Get execution strategy events",
        description="Retrieve strategy events with optional filtering by event type and incremental fetching support.",
        parameters=[
            OpenApiParameter(
                name="since_sequence",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Return only events with sequence number greater than this value (for incremental fetching)",
                required=False,
            ),
            OpenApiParameter(
                name="event_type",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Filter by event type",
                required=False,
            ),
        ],
        responses={
            200: {
                "description": "Events retrieved successfully",
                "content": {
                    "application/json": {
                        "example": {
                            "execution_id": 1,
                            "task_type": "backtest",
                            "task_id": 123,
                            "events": [
                                {
                                    "sequence": 1,
                                    "event_type": "signal_generated",
                                    "strategy_type": "floor",
                                    "timestamp": "2024-01-01T00:00:00Z",
                                    "event": {},
                                    "created_at": "2024-01-01T00:00:00Z",
                                }
                            ],
                            "count": 1,
                            "next": None,
                            "previous": None,
                        }
                    }
                },
            },
            400: {"description": "Invalid parameters"},
            403: {"description": "Access denied"},
            404: {"description": "Execution not found"},
        },
    )
    def get(self, request: Request, execution_id: int) -> Response:
        """Get execution events with filtering and pagination."""
        try:
            execution = Executions.objects.get(id=execution_id)
        except Executions.DoesNotExist:
            return Response(
                {"error": "Execution not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Verify user has access to this execution's task
        if execution.task_type == TaskType.BACKTEST:
            try:
                BacktestTasks.objects.get(id=execution.task_id, user=request.user.pk)
            except BacktestTasks.DoesNotExist:
                return Response(
                    {"error": "Access denied"},
                    status=status.HTTP_403_FORBIDDEN,
                )
        elif execution.task_type == TaskType.TRADING:
            try:
                TradingTasks.objects.get(id=execution.task_id, user=request.user.pk)
            except TradingTasks.DoesNotExist:
                return Response(
                    {"error": "Access denied"},
                    status=status.HTTP_403_FORBIDDEN,
                )

        # Build query
        qs = StrategyEvents.objects.filter(execution=execution).order_by("sequence", "id")

        # Filter by since_sequence for incremental fetching
        since_sequence = request.query_params.get("since_sequence")
        if since_sequence:
            try:
                qs = qs.filter(sequence__gt=int(since_sequence))
            except ValueError:
                return Response(
                    {"error": "Invalid since_sequence parameter"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Filter by event_type
        event_type = request.query_params.get("event_type")
        if event_type:
            qs = qs.filter(event_type=event_type)

        # Get events
        events_data = list(
            qs.values("sequence", "event_type", "strategy_type", "timestamp", "event", "created_at")
        )

        # Format response
        events = []
        for event_row in events_data:
            events.append(
                {
                    "sequence": event_row["sequence"],
                    "event_type": event_row["event_type"],
                    "strategy_type": event_row["strategy_type"],
                    "timestamp": event_row["timestamp"].isoformat()
                    if event_row["timestamp"]
                    else None,
                    "event": event_row["event"],
                    "created_at": event_row["created_at"].isoformat(),
                }
            )

        pagination = _paginate_list_by_page(
            request=request,
            items=events,
            base_url=f"/api/trading/executions/{execution_id}/events/",
            default_page_size=1000,
            max_page_size=1000,
            extra_query={
                "since_sequence": since_sequence,
                "event_type": event_type,
            },
        )

        return Response(
            {
                "execution_id": execution.pk,
                "task_type": execution.task_type,
                "task_id": execution.task_id,
                "events": pagination["results"],
                "count": pagination["count"],
                "next": pagination["next"],
                "previous": pagination["previous"],
            },
            status=status.HTTP_200_OK,
        )


class ExecutionTradesView(APIView):
    """Get trade logs for a specific execution with incremental fetching.

    GET /api/trading/executions/{id}/trades/
    Supports ?since_sequence= for incremental fetching and filtering by instrument, direction.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="get_execution_trades",
        tags=["executions"],
        summary="Get execution trades",
        description="Retrieve trade logs with optional filtering by instrument, direction, and incremental fetching support.",
        parameters=[
            OpenApiParameter(
                name="since_sequence",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Return only trades with sequence number greater than this value (for incremental fetching)",
                required=False,
            ),
            OpenApiParameter(
                name="instrument",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Filter by instrument (e.g., EUR_USD)",
                required=False,
            ),
            OpenApiParameter(
                name="direction",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Filter by trade direction (buy/sell)",
                required=False,
                enum=["buy", "sell"],
            ),
        ],
        responses={
            200: {
                "description": "Trades retrieved successfully",
                "content": {
                    "application/json": {
                        "example": {
                            "execution_id": 1,
                            "task_type": "backtest",
                            "task_id": 123,
                            "trades": [
                                {
                                    "sequence": 1,
                                    "trade": {
                                        "instrument": "EUR_USD",
                                        "direction": "buy",
                                        "units": 1000,
                                    },
                                    "created_at": "2024-01-01T00:00:00Z",
                                }
                            ],
                            "count": 1,
                            "next": None,
                            "previous": None,
                        }
                    }
                },
            },
            400: {"description": "Invalid parameters"},
            403: {"description": "Access denied"},
            404: {"description": "Execution not found"},
        },
    )
    def get(self, request: Request, execution_id: int) -> Response:
        """Get execution trades with filtering and pagination."""
        try:
            execution = Executions.objects.get(id=execution_id)
        except Executions.DoesNotExist:
            return Response(
                {"error": "Execution not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Verify user has access to this execution's task
        if execution.task_type == TaskType.BACKTEST:
            try:
                BacktestTasks.objects.get(id=execution.task_id, user=request.user.pk)
            except BacktestTasks.DoesNotExist:
                return Response(
                    {"error": "Access denied"},
                    status=status.HTTP_403_FORBIDDEN,
                )
        elif execution.task_type == TaskType.TRADING:
            try:
                TradingTasks.objects.get(id=execution.task_id, user=request.user.pk)
            except TradingTasks.DoesNotExist:
                return Response(
                    {"error": "Access denied"},
                    status=status.HTTP_403_FORBIDDEN,
                )

        # Build query
        qs = TradeLogs.objects.filter(execution=execution).order_by("sequence", "id")

        # Filter by since_sequence for incremental fetching
        since_sequence = request.query_params.get("since_sequence")
        if since_sequence:
            try:
                qs = qs.filter(sequence__gt=int(since_sequence))
            except ValueError:
                return Response(
                    {"error": "Invalid since_sequence parameter"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Get trades
        trades_data = list(qs.values("sequence", "trade", "created_at"))

        # Apply client-side filtering for instrument and direction
        instrument = request.query_params.get("instrument")
        direction = request.query_params.get("direction")

        trades = []
        for trade_row in trades_data:
            trade = trade_row["trade"]

            # Filter by instrument
            if instrument:
                trade_instrument = trade.get("instrument") or trade.get("details", {}).get(
                    "instrument"
                )
                if trade_instrument != instrument:
                    continue

            # Filter by direction
            if direction:
                trade_direction = trade.get("direction") or trade.get("details", {}).get(
                    "direction"
                )
                if trade_direction != direction:
                    continue

            trades.append(
                {
                    "sequence": trade_row["sequence"],
                    "trade": trade,
                    "created_at": trade_row["created_at"].isoformat(),
                }
            )

        pagination = _paginate_list_by_page(
            request=request,
            items=trades,
            base_url=f"/api/trading/executions/{execution_id}/trades/",
            default_page_size=1000,
            max_page_size=1000,
            extra_query={
                "since_sequence": since_sequence,
                "instrument": instrument,
                "direction": direction,
            },
        )

        return Response(
            {
                "execution_id": execution.pk,
                "task_type": execution.task_type,
                "task_id": execution.task_id,
                "trades": pagination["results"],
                "count": pagination["count"],
                "next": pagination["next"],
                "previous": pagination["previous"],
            },
            status=status.HTTP_200_OK,
        )


class ExecutionEquityView(APIView):
    """Get equity curve for a specific execution with granularity aggregation.

    GET /api/trading/executions/{id}/equity/
    Supports granularity parameter for time binning and time range filtering.

    Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 5.9, 5.10, 5.11, 6.18
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="get_execution_equity",
        tags=["executions"],
        summary="Get execution equity curve",
        description="Retrieve equity curve data with configurable time granularity for binning and statistical aggregation.",
        parameters=[
            OpenApiParameter(
                name="granularity",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Time window in seconds for binning (default: 60)",
                required=False,
            ),
            OpenApiParameter(
                name="start_time",
                type=OpenApiTypes.DATETIME,
                location=OpenApiParameter.QUERY,
                description="Filter data after this timestamp (ISO format)",
                required=False,
            ),
            OpenApiParameter(
                name="end_time",
                type=OpenApiTypes.DATETIME,
                location=OpenApiParameter.QUERY,
                description="Filter data before this timestamp (ISO format)",
                required=False,
            ),
        ],
        responses={
            200: {
                "description": "Equity curve data retrieved successfully",
                "content": {
                    "application/json": {
                        "example": {
                            "execution_id": 1,
                            "task_type": "backtest",
                            "task_id": 123,
                            "granularity_seconds": 60,
                            "bins": [
                                {
                                    "timestamp": "2024-01-01T00:00:00Z",
                                    "realized_pnl_min": "100.0",
                                    "realized_pnl_max": "150.0",
                                    "realized_pnl_avg": "125.0",
                                    "realized_pnl_median": "120.0",
                                    "unrealized_pnl_min": "-50.0",
                                    "unrealized_pnl_max": "50.0",
                                    "unrealized_pnl_avg": "10.0",
                                    "unrealized_pnl_median": "5.0",
                                    "tick_ask_min": "1.1000",
                                    "tick_ask_max": "1.1050",
                                    "tick_ask_avg": "1.1025",
                                    "tick_ask_median": "1.1020",
                                    "tick_bid_min": "1.0990",
                                    "tick_bid_max": "1.1040",
                                    "tick_bid_avg": "1.1015",
                                    "tick_bid_median": "1.1010",
                                    "tick_mid_min": "1.0995",
                                    "tick_mid_max": "1.1045",
                                    "tick_mid_avg": "1.1020",
                                    "tick_mid_median": "1.1015",
                                    "trade_count": 5,
                                }
                            ],
                            "count": 1,
                        }
                    }
                },
            },
            400: {"description": "Invalid parameters"},
            403: {"description": "Access denied"},
            404: {"description": "Execution not found"},
        },
    )
    def get(self, request: Request, execution_id: int) -> Response:
        """Get execution equity curve with granularity aggregation.

        Query Parameters:
            granularity: Time window in seconds for binning (default: 60)
            start_time: Filter data after this timestamp (ISO format)
            end_time: Filter data before this timestamp (ISO format)

        Returns:
            Binned equity curve data with statistical summaries:
            - timestamp: Bin start timestamp
            - realized_pnl_min/max/avg/median: Realized PnL statistics
            - unrealized_pnl_min/max/avg/median: Unrealized PnL statistics
            - tick_ask_min/max/avg/median: Ask price statistics
            - tick_bid_min/max/avg/median: Bid price statistics
            - tick_mid_min/max/avg/median: Mid price statistics
            - trade_count: Number of trades in bin

        Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 5.9, 5.10, 5.11, 6.18
        """
        try:
            execution = Executions.objects.get(id=execution_id)
        except Executions.DoesNotExist:
            return Response(
                {"error": "Execution not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Verify user has access to this execution's task
        if execution.task_type == TaskType.BACKTEST:
            try:
                BacktestTasks.objects.get(id=execution.task_id, user=request.user.pk)
            except BacktestTasks.DoesNotExist:
                return Response(
                    {"error": "Access denied"},
                    status=status.HTTP_403_FORBIDDEN,
                )
        elif execution.task_type == TaskType.TRADING:
            try:
                TradingTasks.objects.get(id=execution.task_id, user=request.user.pk)
            except TradingTasks.DoesNotExist:
                return Response(
                    {"error": "Access denied"},
                    status=status.HTTP_403_FORBIDDEN,
                )

        # Get granularity parameter (default: 60 seconds)
        granularity_str = request.query_params.get("granularity", "60")
        try:
            granularity_seconds = int(granularity_str)
            if granularity_seconds <= 0:
                return Response(
                    {"error": "granularity must be positive"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except ValueError:
            return Response(
                {"error": "Invalid granularity parameter"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if execution has any metrics
        if not TradingMetrics.objects.filter(execution=execution).exists():
            return Response(
                {
                    "execution_id": execution_id,
                    "task_type": execution.task_type,
                    "task_id": execution.task_id,
                    "granularity_seconds": granularity_seconds,
                    "bins": [],
                    "count": 0,
                },
                status=status.HTTP_200_OK,
            )

        # Use GranularityAggregationService to bin metrics
        try:
            service = GranularityAggregationService()
            aggregated_bins = service.aggregate_metrics(
                execution=execution,
                granularity_seconds=granularity_seconds,
            )
        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Apply time range filters if provided
        start_time_str = request.query_params.get("start_time")
        end_time_str = request.query_params.get("end_time")

        filtered_bins = aggregated_bins

        if start_time_str:
            try:
                start_time = datetime.fromisoformat(start_time_str)
                filtered_bins = [b for b in filtered_bins if b.timestamp >= start_time]
            except ValueError:
                return Response(
                    {"error": "Invalid start_time format"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if end_time_str:
            try:
                end_time = datetime.fromisoformat(end_time_str)
                filtered_bins = [b for b in filtered_bins if b.timestamp <= end_time]
            except ValueError:
                return Response(
                    {"error": "Invalid end_time format"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Format response
        bins_data = []
        for bin_obj in filtered_bins:
            stats = bin_obj.statistics
            bins_data.append(
                {
                    "timestamp": bin_obj.timestamp.isoformat(),
                    "realized_pnl_min": str(stats.realized_pnl_min),
                    "realized_pnl_max": str(stats.realized_pnl_max),
                    "realized_pnl_avg": str(stats.realized_pnl_avg),
                    "realized_pnl_median": str(stats.realized_pnl_median),
                    "unrealized_pnl_min": str(stats.unrealized_pnl_min),
                    "unrealized_pnl_max": str(stats.unrealized_pnl_max),
                    "unrealized_pnl_avg": str(stats.unrealized_pnl_avg),
                    "unrealized_pnl_median": str(stats.unrealized_pnl_median),
                    "tick_ask_min": str(stats.tick_ask_min),
                    "tick_ask_max": str(stats.tick_ask_max),
                    "tick_ask_avg": str(stats.tick_ask_avg),
                    "tick_ask_median": str(stats.tick_ask_median),
                    "tick_bid_min": str(stats.tick_bid_min),
                    "tick_bid_max": str(stats.tick_bid_max),
                    "tick_bid_avg": str(stats.tick_bid_avg),
                    "tick_bid_median": str(stats.tick_bid_median),
                    "tick_mid_min": str(stats.tick_mid_min),
                    "tick_mid_max": str(stats.tick_mid_max),
                    "tick_mid_avg": str(stats.tick_mid_avg),
                    "tick_mid_median": str(stats.tick_mid_median),
                    "trade_count": stats.trade_count,
                }
            )

        return Response(
            {
                "execution_id": execution_id,
                "task_type": execution.task_type,
                "task_id": execution.task_id,
                "granularity_seconds": granularity_seconds,
                "bins": bins_data,
                "count": len(bins_data),
            },
            status=status.HTTP_200_OK,
        )


class ExecutionMetricsView(APIView):
    """Get metrics for a specific execution with flexible filtering.

    GET /api/trading/executions/{id}/metrics/
    Supports granularity, time range, and last_n filtering.

    Requirements: 6.19
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="get_execution_metrics",
        tags=["executions"],
        summary="Get execution metrics",
        description="Retrieve metrics data with optional granularity binning, time range filtering, or last N points.",
        parameters=[
            OpenApiParameter(
                name="granularity",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Time window in seconds for binning (optional, returns binned data if provided)",
                required=False,
            ),
            OpenApiParameter(
                name="start_time",
                type=OpenApiTypes.DATETIME,
                location=OpenApiParameter.QUERY,
                description="Filter metrics after this timestamp (ISO format)",
                required=False,
            ),
            OpenApiParameter(
                name="end_time",
                type=OpenApiTypes.DATETIME,
                location=OpenApiParameter.QUERY,
                description="Filter metrics before this timestamp (ISO format)",
                required=False,
            ),
            OpenApiParameter(
                name="last_n",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Return last N metrics points (alternative to time range)",
                required=False,
            ),
        ],
        responses={
            200: {
                "description": "Metrics retrieved successfully",
                "content": {
                    "application/json": {
                        "example": {
                            "execution_id": 1,
                            "task_type": "backtest",
                            "task_id": 123,
                            "metrics": [
                                {
                                    "sequence": 1,
                                    "timestamp": "2024-01-01T00:00:00Z",
                                    "realized_pnl": "100.0",
                                    "unrealized_pnl": "50.0",
                                    "total_pnl": "150.0",
                                    "open_positions": 2,
                                    "total_trades": 5,
                                }
                            ],
                            "count": 1,
                        }
                    }
                },
            },
            400: {"description": "Invalid parameters"},
            403: {"description": "Access denied"},
            404: {"description": "Execution not found"},
        },
    )
    def get(self, request: Request, execution_id: int) -> Response:
        """Get execution metrics with filtering.

        Query Parameters:
            granularity: Time window in seconds for binning (optional)
            start_time: Filter metrics after this timestamp (ISO format)
            end_time: Filter metrics before this timestamp (ISO format)
            last_n: Return last N metrics points (alternative to time range)

        Returns:
            Metrics data (raw or binned depending on granularity parameter)

        Requirements: 6.19
        """
        try:
            execution = Executions.objects.get(id=execution_id)
        except Executions.DoesNotExist:
            return Response(
                {"error": "Execution not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Verify user has access to this execution's task
        if execution.task_type == TaskType.BACKTEST:
            try:
                BacktestTasks.objects.get(id=execution.task_id, user=request.user.pk)
            except BacktestTasks.DoesNotExist:
                return Response(
                    {"error": "Access denied"},
                    status=status.HTTP_403_FORBIDDEN,
                )
        elif execution.task_type == TaskType.TRADING:
            try:
                TradingTasks.objects.get(id=execution.task_id, user=request.user.pk)
            except TradingTasks.DoesNotExist:
                return Response(
                    {"error": "Access denied"},
                    status=status.HTTP_403_FORBIDDEN,
                )

        # Check for granularity parameter
        granularity_str = request.query_params.get("granularity")

        if granularity_str:
            # Use granularity aggregation (similar to equity endpoint)
            try:
                granularity_seconds = int(granularity_str)
                if granularity_seconds <= 0:
                    return Response(
                        {"error": "granularity must be positive"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            except ValueError:
                return Response(
                    {"error": "Invalid granularity parameter"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Check if execution has any metrics
            if not TradingMetrics.objects.filter(execution=execution).exists():
                return Response(
                    {
                        "execution_id": execution_id,
                        "task_type": execution.task_type,
                        "task_id": execution.task_id,
                        "granularity_seconds": granularity_seconds,
                        "metrics": [],
                        "count": 0,
                    },
                    status=status.HTTP_200_OK,
                )

            # Use GranularityAggregationService
            try:
                service = GranularityAggregationService()
                aggregated_bins = service.aggregate_metrics(
                    execution=execution,
                    granularity_seconds=granularity_seconds,
                )
            except ValueError as e:
                return Response(
                    {"error": str(e)},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Format binned metrics
            metrics_data = []
            for bin_obj in aggregated_bins:
                stats = bin_obj.statistics
                metrics_data.append(
                    {
                        "timestamp": bin_obj.timestamp.isoformat(),
                        "realized_pnl_min": str(stats.realized_pnl_min),
                        "realized_pnl_max": str(stats.realized_pnl_max),
                        "realized_pnl_avg": str(stats.realized_pnl_avg),
                        "realized_pnl_median": str(stats.realized_pnl_median),
                        "unrealized_pnl_min": str(stats.unrealized_pnl_min),
                        "unrealized_pnl_max": str(stats.unrealized_pnl_max),
                        "unrealized_pnl_avg": str(stats.unrealized_pnl_avg),
                        "unrealized_pnl_median": str(stats.unrealized_pnl_median),
                        "trade_count": stats.trade_count,
                    }
                )

            return Response(
                {
                    "execution_id": execution_id,
                    "task_type": execution.task_type,
                    "task_id": execution.task_id,
                    "granularity_seconds": granularity_seconds,
                    "metrics": metrics_data,
                    "count": len(metrics_data),
                },
                status=status.HTTP_200_OK,
            )

        # No granularity - return raw metrics with filtering
        qs = TradingMetrics.objects.filter(execution=execution).order_by("sequence")

        # Apply time range filters
        start_time_str = request.query_params.get("start_time")
        end_time_str = request.query_params.get("end_time")

        if start_time_str:
            try:
                start_time = datetime.fromisoformat(start_time_str)
                qs = qs.filter(timestamp__gte=start_time)
            except ValueError:
                return Response(
                    {"error": "Invalid start_time format"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if end_time_str:
            try:
                end_time = datetime.fromisoformat(end_time_str)
                qs = qs.filter(timestamp__lte=end_time)
            except ValueError:
                return Response(
                    {"error": "Invalid end_time format"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Apply last_n filter
        last_n_str = request.query_params.get("last_n")
        if last_n_str:
            try:
                last_n = int(last_n_str)
                if last_n > 0:
                    qs = qs.order_by("-sequence")[:last_n]
                    # Reverse to get chronological order
                    qs = list(reversed(qs))
            except ValueError:
                return Response(
                    {"error": "Invalid last_n parameter"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Format raw metrics
        metrics_data = []
        for metric in qs:
            metrics_data.append(
                {
                    "sequence": metric.sequence,
                    "timestamp": metric.timestamp.isoformat(),
                    "realized_pnl": str(metric.realized_pnl),
                    "unrealized_pnl": str(metric.unrealized_pnl),
                    "total_pnl": str(metric.total_pnl),
                    "open_positions": metric.open_positions,
                    "total_trades": metric.total_trades,
                    "tick_ask_min": str(metric.tick_ask_min),
                    "tick_ask_max": str(metric.tick_ask_max),
                    "tick_ask_avg": str(metric.tick_ask_avg),
                    "tick_bid_min": str(metric.tick_bid_min),
                    "tick_bid_max": str(metric.tick_bid_max),
                    "tick_bid_avg": str(metric.tick_bid_avg),
                    "tick_mid_min": str(metric.tick_mid_min),
                    "tick_mid_max": str(metric.tick_mid_max),
                    "tick_mid_avg": str(metric.tick_mid_avg),
                }
            )

        return Response(
            {
                "execution_id": execution_id,
                "task_type": execution.task_type,
                "task_id": execution.task_id,
                "metrics": metrics_data,
                "count": len(metrics_data),
            },
            status=status.HTTP_200_OK,
        )


class ExecutionLatestMetricsView(APIView):
    """Get the most recent metrics snapshot for a specific execution.

    GET /api/trading/executions/{id}/metrics/latest/
    Returns the latest TradingMetrics record.

    Requirements: 6.20
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="get_execution_latest_metrics",
        tags=["executions"],
        summary="Get latest execution metrics",
        description="Retrieve the most recent metrics snapshot for an execution.",
        responses={
            200: {
                "description": "Latest metrics retrieved successfully",
                "content": {
                    "application/json": {
                        "example": {
                            "execution_id": 1,
                            "task_type": "backtest",
                            "task_id": 123,
                            "has_metrics": True,
                            "metrics": {
                                "sequence": 100,
                                "timestamp": "2024-01-01T01:00:00Z",
                                "realized_pnl": "500.0",
                                "unrealized_pnl": "100.0",
                                "total_pnl": "600.0",
                                "open_positions": 3,
                                "total_trades": 25,
                                "tick_ask_min": "1.1000",
                                "tick_ask_max": "1.1050",
                                "tick_ask_avg": "1.1025",
                                "tick_bid_min": "1.0990",
                                "tick_bid_max": "1.1040",
                                "tick_bid_avg": "1.1015",
                                "tick_mid_min": "1.0995",
                                "tick_mid_max": "1.1045",
                                "tick_mid_avg": "1.1020",
                                "created_at": "2024-01-01T01:00:00Z",
                            },
                        }
                    }
                },
            },
            403: {"description": "Access denied"},
            404: {"description": "Execution not found"},
        },
    )
    def get(self, request: Request, execution_id: int) -> Response:
        """Get latest metrics snapshot for execution.

        Returns:
            Most recent TradingMetrics snapshot with all fields

        Requirements: 6.20
        """
        try:
            execution = Executions.objects.get(id=execution_id)
        except Executions.DoesNotExist:
            return Response(
                {"error": "Execution not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Verify user has access to this execution's task
        if execution.task_type == TaskType.BACKTEST:
            try:
                BacktestTasks.objects.get(id=execution.task_id, user=request.user.pk)
            except BacktestTasks.DoesNotExist:
                return Response(
                    {"error": "Access denied"},
                    status=status.HTTP_403_FORBIDDEN,
                )
        elif execution.task_type == TaskType.TRADING:
            try:
                TradingTasks.objects.get(id=execution.task_id, user=request.user.pk)
            except TradingTasks.DoesNotExist:
                return Response(
                    {"error": "Access denied"},
                    status=status.HTTP_403_FORBIDDEN,
                )

        # Get latest metrics
        latest_metric = (
            TradingMetrics.objects.filter(execution=execution).order_by("-sequence").first()
        )

        if not latest_metric:
            return Response(
                {
                    "execution_id": execution_id,
                    "task_type": execution.task_type,
                    "task_id": execution.task_id,
                    "has_metrics": False,
                    "metrics": None,
                },
                status=status.HTTP_200_OK,
            )

        metrics_data = {
            "sequence": latest_metric.sequence,
            "timestamp": latest_metric.timestamp.isoformat(),
            "realized_pnl": str(latest_metric.realized_pnl),
            "unrealized_pnl": str(latest_metric.unrealized_pnl),
            "total_pnl": str(latest_metric.total_pnl),
            "open_positions": latest_metric.open_positions,
            "total_trades": latest_metric.total_trades,
            "tick_ask_min": str(latest_metric.tick_ask_min),
            "tick_ask_max": str(latest_metric.tick_ask_max),
            "tick_ask_avg": str(latest_metric.tick_ask_avg),
            "tick_bid_min": str(latest_metric.tick_bid_min),
            "tick_bid_max": str(latest_metric.tick_bid_max),
            "tick_bid_avg": str(latest_metric.tick_bid_avg),
            "tick_mid_min": str(latest_metric.tick_mid_min),
            "tick_mid_max": str(latest_metric.tick_mid_max),
            "tick_mid_avg": str(latest_metric.tick_mid_avg),
            "created_at": latest_metric.created_at.isoformat(),
        }

        return Response(
            {
                "execution_id": execution_id,
                "task_type": execution.task_type,
                "task_id": execution.task_id,
                "has_metrics": True,
                "metrics": metrics_data,
            },
            status=status.HTTP_200_OK,
        )
