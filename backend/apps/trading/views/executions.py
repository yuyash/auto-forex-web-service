"""Execution-specific API endpoints (Task 14).

These endpoints work directly with execution IDs rather than task IDs,
allowing access to specific historical executions and enabling comparison
across multiple executions.
"""

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.trading.enums import TaskType
from apps.trading.models import TradingTasks
from apps.trading.models.execution import Executions
from apps.trading.models.tasks import BacktestTasks
from apps.trading.views._helpers import _paginate_list_by_page


class ExecutionDetailView(APIView):
    """Get full execution details.

    GET /api/trading/executions/{id}/
    Returns complete execution object with all related data.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, execution_id: int) -> Response:
        """Get full execution details."""
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

        # TODO: Update to use TradingMetrics model
        assert isinstance(execution, Executions)
        checkpoint = None

        response_data = {
            "id": execution.pk,
            "execution_id": execution.pk,
            "task_type": execution.task_type,
            "task_id": execution.task_id,
            "execution_number": execution.execution_number,
            "status": execution.status,
            "progress": execution.progress,
            "started_at": execution.started_at.isoformat() if execution.started_at else None,
            "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
            "error_message": execution.error_message or None,
            "logs": execution.logs or [],
            "metrics": None,
        }

        if checkpoint:
            response_data["metrics"] = {
                "processed": checkpoint.processed,
                "total_return": str(checkpoint.total_return),
                "total_pnl": str(checkpoint.total_pnl),
                "realized_pnl": str(checkpoint.realized_pnl),
                "unrealized_pnl": str(checkpoint.unrealized_pnl),
                "total_trades": checkpoint.total_trades,
                "winning_trades": checkpoint.winning_trades,
                "losing_trades": checkpoint.losing_trades,
                "win_rate": str(checkpoint.win_rate),
                "max_drawdown": str(checkpoint.max_drawdown),
                "sharpe_ratio": (
                    str(checkpoint.sharpe_ratio) if checkpoint.sharpe_ratio is not None else None
                ),
                "profit_factor": (
                    str(checkpoint.profit_factor) if checkpoint.profit_factor is not None else None
                ),
                "average_win": str(checkpoint.average_win),
                "average_loss": str(checkpoint.average_loss),
            }

        return Response(response_data, status=status.HTTP_200_OK)


class ExecutionStatusView(APIView):
    """Get current status with metrics from ExecutionMetricsCheckpoint for a specific execution.

    GET /api/trading/executions/{id}/status/
    Returns current status with metrics from ExecutionMetricsCheckpoint.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, execution_id: int) -> Response:
        """Get execution status with latest metrics checkpoint."""
        try:
            execution = Executions.objects.get(id=execution_id)  # type: ignore[name-defined]  # noqa: F823
        except Executions.DoesNotExist:  # type: ignore[name-defined]  # noqa: F823
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

        # TODO: Update to use TradingMetrics model
        checkpoint = None

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
            "has_checkpoint": checkpoint is not None,
            "checkpoint": None,
            # Add metrics at top level for frontend compatibility
            "ticks_processed": 0,
            "trades_executed": 0,
            "current_balance": "0",
            "current_pnl": "0",
            "realized_pnl": "0",
            "unrealized_pnl": "0",
            "last_tick_timestamp": None,
        }

        if checkpoint:
            # Update top-level metrics from checkpoint
            response_data["ticks_processed"] = checkpoint.processed
            response_data["trades_executed"] = checkpoint.total_trades
            response_data["current_balance"] = str(checkpoint.total_return)  # Using return as proxy
            response_data["current_pnl"] = str(checkpoint.total_pnl)
            response_data["realized_pnl"] = str(checkpoint.realized_pnl)
            response_data["unrealized_pnl"] = str(checkpoint.unrealized_pnl)

            response_data["checkpoint"] = {
                "id": checkpoint.pk,
                "processed": checkpoint.processed,
                "total_return": str(checkpoint.total_return),
                "total_pnl": str(checkpoint.total_pnl),
                "realized_pnl": str(checkpoint.realized_pnl),
                "unrealized_pnl": str(checkpoint.unrealized_pnl),
                "total_trades": checkpoint.total_trades,
                "winning_trades": checkpoint.winning_trades,
                "losing_trades": checkpoint.losing_trades,
                "win_rate": str(checkpoint.win_rate),
                "max_drawdown": str(checkpoint.max_drawdown),
                "sharpe_ratio": (
                    str(checkpoint.sharpe_ratio) if checkpoint.sharpe_ratio is not None else None
                ),
                "profit_factor": (
                    str(checkpoint.profit_factor) if checkpoint.profit_factor is not None else None
                ),
                "average_win": str(checkpoint.average_win),
                "average_loss": str(checkpoint.average_loss),
                "created_at": checkpoint.created_at.isoformat(),
            }

        return Response(response_data, status=status.HTTP_200_OK)


class ExecutionEventsView(APIView):
    """Get strategy events for a specific execution with incremental fetching.

    GET /api/trading/executions/{id}/events/
    Supports ?since_sequence= for incremental fetching and ?event_type= for filtering.
    """

    permission_classes = [IsAuthenticated]

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

        from apps.trading.models import StrategyEvents

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

        from apps.trading.models import TradeLogs

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
    """Get equity curve for a specific execution with incremental fetching.

    GET /api/trading/executions/{id}/equity/
    Supports ?since_sequence= for incremental fetching and time range filtering.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, execution_id: int) -> Response:
        """Get execution equity curve with filtering and pagination."""
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
                BacktestTasks.objects.get(id=execution.task_id, user=request.user.pk)  # type: ignore[name-defined]  # noqa: F823
            except BacktestTasks.DoesNotExist:  # type: ignore[name-defined]  # noqa: F823
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

        # TODO: This endpoint will be replaced by execution-based endpoints
        # The old ExecutionEquityPoint model has been removed
        # Use the new TradingMetrics model with granularity aggregation instead
        return Response(
            {
                "execution_id": execution_id,
                "task_type": execution.task_type,
                "task_id": execution.task_id,
                "equity_curve": [],
                "count": 0,
                "granularity_seconds": None,
            },
            status=status.HTTP_200_OK,
        )


class ExecutionMetricsView(APIView):
    """Get latest metrics checkpoint for a specific execution.

    GET /api/trading/executions/{id}/metrics/latest/
    Returns latest ExecutionMetricsCheckpoint.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, execution_id: int) -> Response:
        """Get latest metrics checkpoint for execution."""
        try:
            execution = Executions.objects.get(id=execution_id)  # type: ignore[name-defined]  # noqa: F823
        except Executions.DoesNotExist:  # type: ignore[name-defined]  # noqa: F823
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

        # TODO: Update to use TradingMetrics model
        checkpoint = None

        if not checkpoint:
            return Response(
                {
                    "execution_id": execution.pk,
                    "task_type": execution.task_type,
                    "task_id": execution.task_id,
                    "has_checkpoint": False,
                    "checkpoint": None,
                },
                status=status.HTTP_200_OK,
            )

        return Response(
            {
                "execution_id": execution.pk,
                "task_type": execution.task_type,
                "task_id": execution.task_id,
                "has_checkpoint": True,
                "checkpoint": {
                    "id": checkpoint.pk,
                    "processed": checkpoint.processed,
                    "total_return": str(checkpoint.total_return),
                    "total_pnl": str(checkpoint.total_pnl),
                    "realized_pnl": str(checkpoint.realized_pnl),
                    "unrealized_pnl": str(checkpoint.unrealized_pnl),
                    "total_trades": checkpoint.total_trades,
                    "winning_trades": checkpoint.winning_trades,
                    "losing_trades": checkpoint.losing_trades,
                    "win_rate": str(checkpoint.win_rate),
                    "max_drawdown": str(checkpoint.max_drawdown),
                    "sharpe_ratio": (
                        str(checkpoint.sharpe_ratio)
                        if checkpoint.sharpe_ratio is not None
                        else None
                    ),
                    "profit_factor": (
                        str(checkpoint.profit_factor)
                        if checkpoint.profit_factor is not None
                        else None
                    ),
                    "average_win": str(checkpoint.average_win),
                    "average_loss": str(checkpoint.average_loss),
                    "created_at": checkpoint.created_at.isoformat(),
                },
            },
            status=status.HTTP_200_OK,
        )
